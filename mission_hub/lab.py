"""Authenticated Lab persistence and presentation helpers.

The Lab is deliberately part of the Mission Hub boundary.  It does not own a
second ledger and it never exposes the Mission Hub bearer token to a browser.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import secrets
from typing import Any
import uuid

from .config import ConfigBundle
from .errors import ConflictError, NotFoundError, SafetyError
from .jsonutil import canonical_json, content_hash
from .store import MissionHubStore, utc_now


USERNAME = re.compile(r"[a-zA-Z0-9_.-]{2,48}")
SESSION_SECONDS = 30 * 24 * 60 * 60
MAX_SUBJECT = 200
MAX_MESSAGE_BYTES = 64 * 1024


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32,
    )


def _expiry(seconds: int = SESSION_SECONDS) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=seconds)
    ).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _clean_text(value: Any, *, label: str, max_bytes: int, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text")
    result = value.strip()
    if not result and not allow_empty:
        raise ValueError(f"{label} must not be empty")
    if len(result.encode("utf-8")) > max_bytes:
        raise ValueError(f"{label} is too large")
    return result


class LabStore:
    def __init__(self, store: MissionHubStore):
        self.store = store

    # Authentication -----------------------------------------------------

    def has_users(self) -> bool:
        with self.store._connect() as db:
            return db.execute("SELECT 1 FROM lab_users LIMIT 1").fetchone() is not None

    def setup_user(self, username: str, password: str) -> dict[str, Any]:
        username = username.strip()
        if not USERNAME.fullmatch(username):
            raise ValueError("username must contain 2-48 letters, numbers, dots, dashes, or underscores")
        if len(password) < 12 or len(password.encode("utf-8")) > 1024:
            raise ValueError("password must contain 12-1024 UTF-8 characters")
        salt = os.urandom(16)
        now = utc_now()
        user_id = f"usr-{uuid.uuid4()}"
        with self.store.transaction() as db:
            if db.execute("SELECT 1 FROM lab_users LIMIT 1").fetchone() is not None:
                raise ConflictError("the Lab account has already been initialized")
            db.execute(
                "INSERT INTO lab_users(id,username,password_salt,password_hash,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (user_id, username, salt, _password_hash(password, salt), now, now),
            )
            self.store._event(db, "lab_user", user_id, "lab.user_created", f"lab:{username}", {})
        return {"id": user_id, "username": username}

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        with self.store._connect() as db:
            row = db.execute(
                "SELECT * FROM lab_users WHERE username=? COLLATE NOCASE", (username.strip(),),
            ).fetchone()
        if row is None:
            # Keep unknown-user work similar to a real password check.
            _password_hash(password[:1024], b"\0" * 16)
            return None
        supplied = _password_hash(password, bytes(row["password_salt"]))
        if not secrets.compare_digest(supplied, bytes(row["password_hash"])):
            return None
        return {"id": row["id"], "username": row["username"]}

    def create_session(self, user_id: str) -> tuple[str, dict[str, Any]]:
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        csrf = secrets.token_urlsafe(24)
        now = utc_now()
        expires = _expiry()
        with self.store.transaction() as db:
            db.execute("DELETE FROM lab_sessions WHERE expires_at<=?", (now,))
            db.execute(
                "INSERT INTO lab_sessions(token_sha256,user_id,csrf_token,created_at,last_seen_at,expires_at) VALUES(?,?,?,?,?,?)",
                (digest, user_id, csrf, now, now, expires),
            )
            row = db.execute("SELECT username FROM lab_users WHERE id=?", (user_id,)).fetchone()
        return token, {"user_id": user_id, "username": row[0], "csrf_token": csrf, "expires_at": expires}

    def session(self, token: str) -> dict[str, Any] | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        now = utc_now()
        with self.store.transaction(immediate=False) as db:
            row = db.execute(
                """SELECT s.*,u.username FROM lab_sessions s JOIN lab_users u ON u.id=s.user_id
                   WHERE s.token_sha256=? AND s.expires_at>?""",
                (digest, now),
            ).fetchone()
            if row is None:
                return None
            db.execute("UPDATE lab_sessions SET last_seen_at=? WHERE token_sha256=?", (now, digest))
        return {
            "user_id": row["user_id"], "username": row["username"],
            "csrf_token": row["csrf_token"], "expires_at": row["expires_at"],
        }

    def end_session(self, token: str) -> None:
        if not token:
            return
        with self.store.transaction() as db:
            db.execute(
                "DELETE FROM lab_sessions WHERE token_sha256=?",
                (hashlib.sha256(token.encode()).hexdigest(),),
            )

    # Operational threads ------------------------------------------------

    def list_threads(self) -> list[dict[str, Any]]:
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT t.*,
                          COUNT(m.id) AS message_count,
                          SUM(CASE WHEN m.sender!='operator' AND m.read_at IS NULL THEN 1 ELSE 0 END) AS unread_count,
                          MAX(m.created_at) AS last_message_at
                   FROM message_threads t LEFT JOIN thread_messages m ON m.thread_id=t.id
                   GROUP BY t.id ORDER BY COALESCE(MAX(m.created_at),t.created_at) DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def unread_count(self) -> int:
        with self.store._connect() as db:
            row = db.execute(
                "SELECT COUNT(*) FROM thread_messages WHERE sender!='operator' AND read_at IS NULL"
            ).fetchone()
        return int(row[0])

    def create_thread(self, subject: str, body: str, *, actor: str) -> dict[str, Any]:
        subject = _clean_text(subject, label="subject", max_bytes=MAX_SUBJECT)
        body = _clean_text(body, label="message", max_bytes=MAX_MESSAGE_BYTES)
        thread_id = f"thread-{uuid.uuid4()}"
        message_id = f"message-{uuid.uuid4()}"
        now = utc_now()
        with self.store.transaction() as db:
            db.execute(
                "INSERT INTO message_threads(id,subject,state,created_by,created_at,updated_at) VALUES(?,?,'open',?,?,?)",
                (thread_id, subject, actor, now, now),
            )
            db.execute(
                "INSERT INTO thread_messages(id,thread_id,sender,body,created_at,read_at) VALUES(?,?,'operator',?,?,?)",
                (message_id, thread_id, body, now, now),
            )
            self.store._event(db, "message_thread", thread_id, "thread.created", actor, {"subject": subject})
        return self.thread(thread_id, mark_read=False)

    def thread(self, thread_id: str, *, mark_read: bool = True) -> dict[str, Any]:
        now = utc_now()
        with self.store.transaction(immediate=mark_read) as db:
            thread = db.execute("SELECT * FROM message_threads WHERE id=?", (thread_id,)).fetchone()
            if thread is None:
                raise NotFoundError(thread_id)
            messages = db.execute(
                "SELECT * FROM thread_messages WHERE thread_id=? ORDER BY created_at,id", (thread_id,),
            ).fetchall()
            if mark_read:
                db.execute(
                    "UPDATE thread_messages SET read_at=? WHERE thread_id=? AND sender!='operator' AND read_at IS NULL",
                    (now, thread_id),
                )
        return {"thread": dict(thread), "messages": [dict(row) for row in messages]}

    def add_thread_message(self, thread_id: str, body: str, *, sender: str, actor: str) -> dict[str, Any]:
        if sender not in {"operator", "mission_hub", "sol", "codex"}:
            raise ValueError("invalid message sender")
        body = _clean_text(body, label="message", max_bytes=MAX_MESSAGE_BYTES)
        message_id = f"message-{uuid.uuid4()}"
        now = utc_now()
        read_at = now if sender == "operator" else None
        with self.store.transaction() as db:
            row = db.execute("SELECT state FROM message_threads WHERE id=?", (thread_id,)).fetchone()
            if row is None:
                raise NotFoundError(thread_id)
            if row[0] != "open":
                raise ConflictError("the thread is archived")
            db.execute(
                "INSERT INTO thread_messages(id,thread_id,sender,body,created_at,read_at) VALUES(?,?,?,?,?,?)",
                (message_id, thread_id, sender, body, now, read_at),
            )
            db.execute("UPDATE message_threads SET updated_at=? WHERE id=?", (now, thread_id))
            self.store._event(db, "message_thread", thread_id, "thread.message_added", actor, {"message_id": message_id, "sender": sender})
        return {"id": message_id, "thread_id": thread_id, "sender": sender, "body": body, "created_at": now, "read_at": read_at}

    def system_notice(self, subject: str, body: str, *, sender: str = "mission_hub", actor: str = "mission-hub") -> str:
        subject = _clean_text(subject, label="subject", max_bytes=MAX_SUBJECT)
        body = _clean_text(body, label="message", max_bytes=MAX_MESSAGE_BYTES)
        thread_id = f"thread-{uuid.uuid4()}"
        now = utc_now()
        with self.store.transaction() as db:
            db.execute(
                "INSERT INTO message_threads(id,subject,state,created_by,created_at,updated_at) VALUES(?,?,'open',?,?,?)",
                (thread_id, subject, actor, now, now),
            )
            db.execute(
                "INSERT INTO thread_messages(id,thread_id,sender,body,created_at) VALUES(?,?,?,?,?)",
                (f"message-{uuid.uuid4()}", thread_id, sender, body, now),
            )
            self.store._event(db, "message_thread", thread_id, "thread.system_notice", actor, {"subject": subject, "sender": sender})
        return thread_id

    # Checkpoint-pinned chat ---------------------------------------------

    def checkpoints(self) -> list[dict[str, Any]]:
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT a.*,GROUP_CONCAT(l.machine_id) AS machine_ids
                   FROM artifacts a LEFT JOIN artifact_locations l
                     ON l.artifact_id=a.id AND l.available=1
                   WHERE a.kind='checkpoint' AND a.lifecycle!='deleted'
                   GROUP BY a.id ORDER BY a.created_at DESC"""
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["manifest"] = json.loads(item.pop("manifest_json"))
            item["machine_ids"] = sorted(set(filter(None, (item.get("machine_ids") or "").split(","))))
            item["byte_certified"] = item["manifest"].get("certification_scope") == "byte_identity_only"
            item["compatibility_certified"] = bool(item["manifest"].get("compatibility_certified"))
            result.append(item)
        return result

    def list_chats(self) -> list[dict[str, Any]]:
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT c.*,COUNT(m.id) AS message_count,MAX(m.created_at) AS last_message_at
                   FROM chat_threads c LEFT JOIN chat_messages m ON m.thread_id=c.id
                   GROUP BY c.id ORDER BY COALESCE(MAX(m.created_at),c.created_at) DESC"""
            ).fetchall()
        return [self._chat_row(row) for row in rows]

    def create_chat(self, checkpoint_artifact_id: str, title: str, *, actor: str) -> dict[str, Any]:
        title = _clean_text(title, label="title", max_bytes=MAX_SUBJECT)
        with self.store._connect() as db:
            artifact = db.execute(
                "SELECT * FROM artifacts WHERE id=? AND kind='checkpoint' AND lifecycle!='deleted'",
                (checkpoint_artifact_id,),
            ).fetchone()
        if artifact is None:
            raise NotFoundError("checkpoint artifact is unavailable")
        manifest = json.loads(artifact["manifest_json"])
        if manifest.get("certification_scope") != "byte_identity_only":
            raise SafetyError("chat requires a byte-certified checkpoint artifact")
        thread_id = f"chat-{uuid.uuid4()}"
        now = utc_now()
        generation = {"max_new_tokens": 32, "do_sample": False}
        with self.store.transaction() as db:
            db.execute(
                """INSERT INTO chat_threads
                   (id,title,checkpoint_artifact_id,checkpoint_sha256,prompt_format_id,prompt_format_version,
                    generation_json,state,created_by,created_at,updated_at)
                   VALUES(?,?,?,?,?,1,?,'open',?,?,?)""",
                (thread_id, title, checkpoint_artifact_id, artifact["sha256"], "ninereeds-chat-v1", canonical_json(generation), actor, now, now),
            )
            self.store._event(db, "chat_thread", thread_id, "chat.created", actor, {"checkpoint_artifact_id": checkpoint_artifact_id, "checkpoint_sha256": artifact["sha256"]})
        return self.chat(thread_id)

    def chat(self, thread_id: str) -> dict[str, Any]:
        with self.store._connect() as db:
            thread = db.execute("SELECT * FROM chat_threads WHERE id=?", (thread_id,)).fetchone()
            if thread is None:
                raise NotFoundError(thread_id)
            messages = db.execute(
                "SELECT * FROM chat_messages WHERE thread_id=? ORDER BY created_at,id", (thread_id,),
            ).fetchall()
            invocations = db.execute(
                "SELECT * FROM chat_invocations WHERE thread_id=? ORDER BY created_at,id", (thread_id,),
            ).fetchall()
        return {
            "thread": self._chat_row(thread),
            "messages": [dict(row) for row in messages],
            "invocations": [self._invocation_row(row) for row in invocations],
        }

    def add_chat_message(self, thread_id: str, body: str, *, actor: str) -> dict[str, Any]:
        """Persist an exact turn and a truthful blocked invocation record.

        The execution contract is intentionally not impersonated before the
        trainbox inference job is commissioned.  This record can be queued by a
        later worker without changing the chat/thread schema.
        """
        body = _clean_text(body, label="message", max_bytes=MAX_MESSAGE_BYTES)
        now = utc_now()
        message_id = f"chat-message-{uuid.uuid4()}"
        invocation_id = f"invocation-{uuid.uuid4()}"
        with self.store.transaction() as db:
            thread = db.execute("SELECT * FROM chat_threads WHERE id=?", (thread_id,)).fetchone()
            if thread is None:
                raise NotFoundError(thread_id)
            if thread["state"] != "open":
                raise ConflictError("the chat is archived")
            db.execute(
                "INSERT INTO chat_messages(id,thread_id,role,body,created_at) VALUES(?,?,'operator',?,?)",
                (message_id, thread_id, body, now),
            )
            context_ids = [row[0] for row in db.execute(
                "SELECT id FROM chat_messages WHERE thread_id=? ORDER BY created_at,id", (thread_id,),
            ).fetchall()]
            failure = {"code": "inference_not_commissioned", "message": "The checkpoint-pinned chat contract exists, but trainbox inference is not commissioned."}
            db.execute(
                """INSERT INTO chat_invocations
                   (id,thread_id,request_message_id,checkpoint_artifact_id,checkpoint_sha256,
                    prompt_format_id,prompt_format_version,generation_json,context_message_ids_json,
                    status,failure_json,created_at,finished_at)
                   VALUES(?,?,?,?,?,?,?,?,?,'blocked',?,?,?)""",
                (invocation_id, thread_id, message_id, thread["checkpoint_artifact_id"], thread["checkpoint_sha256"],
                 thread["prompt_format_id"], thread["prompt_format_version"], thread["generation_json"],
                 canonical_json(context_ids), canonical_json(failure), now, now),
            )
            db.execute("UPDATE chat_threads SET updated_at=? WHERE id=?", (now, thread_id))
            self.store._event(db, "chat_thread", thread_id, "chat.turn_recorded", actor, {"message_id": message_id, "invocation_id": invocation_id, "status": "blocked"})
        return self.chat(thread_id)

    # Configuration drafts ----------------------------------------------

    def latest_draft(self) -> dict[str, Any] | None:
        with self.store._connect() as db:
            row = db.execute(
                "SELECT * FROM lab_config_drafts WHERE state='draft' ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result

    def save_draft(self, bundle: ConfigBundle, payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
        normalized = validate_settings_payload(bundle, payload)
        now = utc_now()
        draft_id = f"draft-{content_hash({'base': bundle.sha256, 'payload': normalized})[:16]}"
        with self.store.transaction() as db:
            db.execute("UPDATE lab_config_drafts SET state='superseded' WHERE state='draft' AND id!=?", (draft_id,))
            db.execute(
                """INSERT INTO lab_config_drafts(id,base_config_sha256,state,payload_json,created_by,created_at,updated_at)
                   VALUES(?,?,'draft',?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET payload_json=excluded.payload_json,created_by=excluded.created_by,
                     updated_at=excluded.updated_at,state='draft'""",
                (draft_id, bundle.sha256, canonical_json(normalized), actor, now, now),
            )
            self.store._event(db, "lab_config_draft", draft_id, "config.draft_saved", actor, {"base_config_sha256": bundle.sha256})
        return self.latest_draft() or {}

    def update_campaign_objective(self, campaign_id: str, objective: str, *, actor: str) -> dict[str, Any]:
        objective = _clean_text(objective, label="campaign objective", max_bytes=16 * 1024)
        now = utc_now()
        with self.store.transaction() as db:
            row = db.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
            if row is None:
                raise NotFoundError(campaign_id)
            db.execute("UPDATE campaigns SET objective=?,updated_at=? WHERE id=?", (objective, now, campaign_id))
            self.store._event(db, "campaign", campaign_id, "campaign.objective_updated", actor, {"objective_sha256": hashlib.sha256(objective.encode()).hexdigest()})
        with self.store._connect() as db:
            return dict(db.execute("SELECT * FROM campaigns WHERE id=?", (campaign_id,)).fetchone())

    @staticmethod
    def _chat_row(row: Any) -> dict[str, Any]:
        result = dict(row)
        result["generation"] = json.loads(result.pop("generation_json"))
        return result

    @staticmethod
    def _invocation_row(row: Any) -> dict[str, Any]:
        result = dict(row)
        result["generation"] = json.loads(result.pop("generation_json"))
        result["context_message_ids"] = json.loads(result.pop("context_message_ids_json"))
        result["failure"] = json.loads(result.pop("failure_json")) if result.get("failure_json") else None
        result.pop("failure_json", None)
        return result


def settings_payload(bundle: ConfigBundle) -> dict[str, Any]:
    return {
        "schema_version": "ninereeds_lab_settings_v1",
        "base_config_sha256": bundle.sha256,
        "jobs": [dict(value) for value in sorted(bundle.jobs.values(), key=lambda item: item["id"])],
        "providers": [dict(value) for value in sorted(bundle.providers.values(), key=lambda item: item["id"])],
        "models": [dict(value) for value in sorted(bundle.models.values(), key=lambda item: item["id"])],
        "routes": [dict(value) for value in sorted(bundle.routes.values(), key=lambda item: item["id"])],
        "prompts": [dict(value) for value in sorted(bundle.prompts.values(), key=lambda item: item["id"])],
    }


def validate_settings_payload(bundle: ConfigBundle, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != "ninereeds_lab_settings_v1":
        raise ValueError("invalid Lab settings schema")
    if payload.get("base_config_sha256") != bundle.sha256:
        raise ConflictError("settings draft is based on a stale configuration")
    expected = {"schema_version", "base_config_sha256", "jobs", "providers", "models", "routes", "prompts"}
    if set(payload) != expected:
        raise ValueError("settings draft has unknown or missing sections")
    normalized = settings_payload(bundle)
    schemas = {
        "jobs": bundle.jobs, "providers": bundle.providers, "models": bundle.models,
        "routes": bundle.routes, "prompts": bundle.prompts,
    }
    mutable_fields = {
        "jobs": {"enabled", "priority", "timeout_seconds", "max_attempts", "approval", "provider_route", "prompt_id"},
        "providers": {"enabled", "endpoint", "timeout_seconds", "max_attempts", "concurrency"},
        "models": {"enabled", "provider", "exact_name", "context_tokens", "output_tokens", "structured_output"},
        "routes": {"enabled", "ordered_model_ids", "fallback_failure_classes", "max_total_tokens", "max_cost_usd"},
        "prompts": {"enabled", "system", "template"},
    }
    for section, baseline in schemas.items():
        values = payload[section]
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise ValueError(f"settings {section} must be a list of objects")
        supplied = {item.get("id"): item for item in values}
        if set(supplied) != set(baseline):
            raise ValueError(f"settings {section} IDs do not match the active catalog")
        checked: list[dict[str, Any]] = []
        for item_id in sorted(baseline):
            candidate = supplied[item_id]
            original = baseline[item_id]
            if set(candidate) != set(original):
                raise ValueError(f"settings {section}/{item_id} has unknown or missing fields")
            # Types are already the contract used by ConfigBundle. Preserve
            # booleans as booleans rather than accepting their integer subtype.
            for key, original_value in original.items():
                value = candidate[key]
                if key not in mutable_fields[section] and value != original_value:
                    raise SafetyError(f"settings {section}/{item_id}.{key} is not an operator-facing knob")
                if isinstance(original_value, bool):
                    if not isinstance(value, bool):
                        raise ValueError(f"settings {section}/{item_id}.{key} must be boolean")
                elif not isinstance(value, type(original_value)):
                    raise ValueError(f"settings {section}/{item_id}.{key} has the wrong type")
            checked.append(candidate)
        normalized[section] = checked
    return normalized
