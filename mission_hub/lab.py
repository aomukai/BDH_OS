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

from .config import ConfigBundle, MODEL_KEYS, MODEL_MODALITIES, PROVIDER_KEYS, model_supports_route
from .errors import ConflictError, NotFoundError, SafetyError
from .jsonutil import canonical_json, content_hash
from .store import MissionHubStore, utc_now


USERNAME = re.compile(r"[a-zA-Z0-9_.-]{2,48}")
SETTINGS_ID = re.compile(r"[a-z0-9][a-z0-9._-]{1,62}")
ENVIRONMENT_NAME = re.compile(r"[A-Z][A-Z0-9_]*")
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
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle | None = None):
        self.store = store
        self.bundle = bundle

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
        # Session expiry is fixed at login. Authentication is therefore a
        # read-only hot path; updating last_seen_at on every asset/API request
        # caused avoidable writer contention with the scheduler and message
        # ledger. Login still records the session creation timestamp.
        with self.store._connect() as db:
            row = db.execute(
                """SELECT s.*,u.username FROM lab_sessions s JOIN lab_users u ON u.id=s.user_id
                   WHERE s.token_sha256=? AND s.expires_at>?""",
                (digest, now),
            ).fetchone()
            if row is None:
                return None
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
            if sender != "operator" and actor != "mission-hub:on-call":
                db.execute(
                    "INSERT INTO operational_responses(trigger_message_id,thread_id,status,created_at) VALUES(?,?,'pending',?)",
                    (message_id, thread_id, now),
                )
            self.store._event(db, "message_thread", thread_id, "thread.message_added", actor, {"message_id": message_id, "sender": sender})
        return {"id": message_id, "thread_id": thread_id, "sender": sender, "body": body, "created_at": now, "read_at": read_at}

    def system_notice(self, subject: str, body: str, *, sender: str = "mission_hub", actor: str = "mission-hub") -> str:
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
                "INSERT INTO thread_messages(id,thread_id,sender,body,created_at) VALUES(?,?,?,?,?)",
                (message_id, thread_id, sender, body, now),
            )
            # Every system-originated operator notice enters the configurable
            # on-call queue.  The daemon creates the provider-backed job; this
            # insert is deliberately independent of any in-process config.
            db.execute(
                "INSERT INTO operational_responses(trigger_message_id,thread_id,status,created_at) VALUES(?,?,'pending',?)",
                (message_id, thread_id, now),
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
        thread_id = f"chat-{uuid.uuid4()}"
        now = utc_now()
        generation = {
            "max_new_tokens": 256, "do_sample": False,
            "ingress_device": "cuda:0", "core_device": "cuda:1",
            "local_files_only": True,
        }
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
        """Persist an exact turn and queue its checkpoint-pinned inference job."""
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
            context_rows = db.execute(
                "SELECT id,role,body FROM chat_messages WHERE thread_id=? ORDER BY created_at,id",
                (thread_id,),
            ).fetchall()
            context_ids = [row["id"] for row in context_rows]
            rendered_prompt = self._render_chat_prompt(context_rows)
            rendered_sha256 = content_hash(rendered_prompt)
            commissioned = self.bundle is not None and self.bundle.jobs.get("model.chat", {}).get("enabled")
            status = "queued" if commissioned else "blocked"
            failure = None if commissioned else {
                "code": "inference_not_commissioned",
                "message": "The checkpoint-pinned chat job is not active in this process.",
            }
            db.execute(
                """INSERT INTO chat_invocations
                   (id,thread_id,request_message_id,checkpoint_artifact_id,checkpoint_sha256,
                    prompt_format_id,prompt_format_version,generation_json,context_message_ids_json,
                    rendered_prompt,rendered_prompt_sha256,status,failure_json,created_at,finished_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (invocation_id, thread_id, message_id, thread["checkpoint_artifact_id"], thread["checkpoint_sha256"],
                 thread["prompt_format_id"], thread["prompt_format_version"], thread["generation_json"],
                 canonical_json(context_ids), rendered_prompt, rendered_sha256, status,
                 None if failure is None else canonical_json(failure), now,
                 now if failure is not None else None),
            )
            db.execute("UPDATE chat_threads SET updated_at=? WHERE id=?", (now, thread_id))
            self.store._event(db, "chat_thread", thread_id, "chat.turn_recorded", actor, {"message_id": message_id, "invocation_id": invocation_id, "status": status})
        if commissioned:
            generation = json.loads(thread["generation_json"])
            try:
                job = self.store.create_job(
                    self.bundle, job_type="model.chat", input_payload={
                        "checkpoint_artifact_id": thread["checkpoint_artifact_id"],
                        "checkpoint_sha256": thread["checkpoint_sha256"],
                        "thread_id": thread_id, "invocation_id": invocation_id,
                        "prompt_format_id": thread["prompt_format_id"],
                        "prompt_format_version": thread["prompt_format_version"],
                        "rendered_prompt": rendered_prompt,
                        "rendered_prompt_sha256": rendered_sha256,
                        "generation": generation,
                    },
                    idempotency_key=f"chat:{invocation_id}", created_by=actor,
                    campaign_id=None, requested_machine_id="trainbox", approved=True,
                )
            except Exception as exc:
                with self.store.transaction() as db:
                    db.execute(
                        "UPDATE chat_invocations SET status='blocked',failure_json=?,finished_at=? WHERE id=?",
                        (canonical_json({"code": "chat_job_creation_failed", "message": str(exc)}), utc_now(), invocation_id),
                    )
                raise
            with self.store.transaction() as db:
                db.execute(
                    "UPDATE chat_invocations SET job_id=? WHERE id=?",
                    (job["id"], invocation_id),
                )
        return self.chat(thread_id)

    @staticmethod
    def _render_chat_prompt(rows) -> str:
        if len(rows) == 1 and rows[0]["role"] == "operator":
            return rows[0]["body"]
        labels = {"operator": "Operator", "ninereeds": "Ninereeds", "system": "Context"}
        rendered = [f"{labels[row['role']]}: {row['body']}" for row in rows]
        rendered.append("Ninereeds:")
        return "\n".join(rendered)

    # Configuration drafts ----------------------------------------------

    def latest_draft(self, *, base_config_sha256: str | None = None) -> dict[str, Any] | None:
        with self.store._connect() as db:
            if base_config_sha256 is None:
                row = db.execute(
                    "SELECT * FROM lab_config_drafts WHERE state='draft' ORDER BY updated_at DESC LIMIT 1"
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT * FROM lab_config_drafts WHERE state='draft' AND base_config_sha256=? ORDER BY updated_at DESC LIMIT 1",
                    (base_config_sha256,),
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

    def rebase_latest_draft(self, bundle: ConfigBundle, *, actor: str) -> dict[str, Any]:
        source = self.latest_draft()
        if source is None:
            raise NotFoundError("no configuration draft exists to rebase")
        if source["base_config_sha256"] == bundle.sha256:
            return source
        rebased = rebase_settings_payload(bundle, source["payload"])
        saved = self.save_draft(bundle, rebased, actor=actor)
        with self.store.transaction() as db:
            self.store._event(db, "lab_config_draft", saved["id"], "config.draft_rebased", actor, {
                "source_draft_id": source["id"], "source_base_config_sha256": source["base_config_sha256"],
                "target_base_config_sha256": bundle.sha256,
            })
        return saved

    def review_draft(self, bundle: ConfigBundle) -> dict[str, Any]:
        draft = self.latest_draft(base_config_sha256=bundle.sha256)
        if draft is None:
            raise NotFoundError("no current configuration draft")
        review = review_settings_payload(bundle, draft["payload"])
        review["draft"] = {
            "id": draft["id"], "created_by": draft["created_by"],
            "created_at": draft["created_at"], "updated_at": draft["updated_at"],
            "base_config_sha256": draft["base_config_sha256"],
        }
        return review

    def request_draft_commissioning(self, bundle: ConfigBundle, draft_id: str, *, actor: str) -> dict[str, Any]:
        review = self.review_draft(bundle)
        if review["draft"]["id"] != draft_id:
            raise ConflictError("the reviewed configuration draft is no longer current")
        thread_id = f"thread-{uuid.uuid5(uuid.NAMESPACE_URL, 'ninereeds:commission:' + draft_id)}"
        now = utc_now()
        acknowledged_at = (
            datetime.fromisoformat(now.replace("Z", "+00:00")) + timedelta(microseconds=1)
        ).isoformat(timespec="microseconds").replace("+00:00", "Z")
        blockers = review["blockers"]
        summary = [
            f"Commissioning requested for configuration draft {draft_id}.",
            f"Base configuration: {bundle.sha256}",
            f"Changes: {review['change_count']}",
            f"Current blockers: {len(blockers)}",
            "",
        ]
        summary.extend(f"- {item['message']}" for item in blockers)
        if not blockers:
            summary.append("- No semantic blockers were found; clean source reconciliation and role releases are still required.")
        acknowledgement = (
            "Mission Hub recorded this request. No configuration was activated. "
            "The request must pass source reconciliation, strict validation, clean role-release construction, "
            "deployment identity checks, and explicit operator activation. Training authorization remains separate."
        )
        with self.store.transaction() as db:
            existing = db.execute("SELECT 1 FROM message_threads WHERE id=?", (thread_id,)).fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO message_threads(id,subject,state,created_by,created_at,updated_at) VALUES(?,?,'open',?,?,?)",
                    (thread_id, f"Commission configuration draft {draft_id}", actor, now, now),
                )
                db.execute(
                    "INSERT INTO thread_messages(id,thread_id,sender,body,created_at,read_at) VALUES(?,?,'operator',?,?,?)",
                    (f"message-{uuid.uuid4()}", thread_id, "\n".join(summary), now, now),
                )
                db.execute(
                    "INSERT INTO thread_messages(id,thread_id,sender,body,created_at) VALUES(?,?,'mission_hub',?,?)",
                    (f"message-{uuid.uuid4()}", thread_id, acknowledgement, acknowledged_at),
                )
                self.store._event(
                    db, "lab_config_draft", draft_id, "config.commissioning_requested", actor,
                    {"thread_id": thread_id, "change_count": review["change_count"], "blocker_codes": [item["code"] for item in blockers]},
                )
        return {"thread": self.thread(thread_id, mark_read=False), "review": review}

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
        "orchestration": dict(bundle.orchestration),
        "model_defaults": dict(bundle.model_defaults),
        "visual": dict(bundle.visual),
        "budget": dict(bundle.budget),
    }


def validate_settings_payload(bundle: ConfigBundle, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != "ninereeds_lab_settings_v1":
        raise ValueError("invalid Lab settings schema")
    if payload.get("base_config_sha256") != bundle.sha256:
        raise ConflictError("settings draft is based on a stale configuration")
    expected = {"schema_version", "base_config_sha256", "jobs", "providers", "models", "routes", "prompts", "orchestration", "model_defaults", "visual", "budget"}
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
        "models": {"enabled", "provider", "exact_name", "context_tokens", "output_tokens", "structured_output", "modality", "revision"},
        "routes": {"enabled", "ordered_model_ids", "fallback_failure_classes", "max_total_tokens", "max_cost_usd"},
        "prompts": {"enabled", "system", "template"},
    }
    extensible_schemas = {"providers": PROVIDER_KEYS, "models": MODEL_KEYS}
    singleton_mutable = {
        "orchestration": {"strategic_boundary_cooldown_seconds"},
        "model_defaults": {"unlisted_context_tokens", "unlisted_output_tokens"},
        "visual": {
            "shadow_mode", "stage_cooldown_seconds", "max_pack_items", "max_candidates_per_item", "max_width", "max_height",
            "max_generation_steps", "max_stage_seconds", "max_pack_bytes", "minimum_free_bytes",
        },
        "budget": {
            "external_calls_enabled", "monthly_limit", "weekly_limit", "per_run_approval_above",
            "emergency_reserve", "warning_fraction", "restriction_fraction", "hard_stop_fraction",
        },
    }
    for section, mutable in singleton_mutable.items():
        candidate = payload.get(section)
        original = getattr(bundle, section)
        if not isinstance(candidate, dict) or set(candidate) != set(original):
            raise ValueError(f"settings {section} has unknown or missing fields")
        for key, original_value in original.items():
            value = candidate[key]
            if isinstance(original_value, float) and isinstance(value, int) and not isinstance(value, bool):
                candidate[key] = float(value)
                value = candidate[key]
            if type(value) is not type(original_value):
                raise ValueError(f"settings {section}.{key} has the wrong type")
            if key not in mutable and value != original_value:
                raise SafetyError(f"settings {section}.{key} is not an operator-facing knob")
        normalized[section] = dict(candidate)
    cooldown = normalized["orchestration"]["strategic_boundary_cooldown_seconds"]
    if not 0 <= cooldown <= 86400:
        raise ValueError("strategic decision cooldown must be between 0 and 86400 seconds")
    if any(normalized["model_defaults"][key] < 1 for key in ("unlisted_context_tokens", "unlisted_output_tokens")):
        raise ValueError("unlisted-model token defaults must be positive")
    if any(normalized["visual"][key] < 1 for key in singleton_mutable["visual"] if key not in {"shadow_mode", "stage_cooldown_seconds"}):
        raise ValueError("visual pipeline limits must be positive")
    if not 0 <= normalized["visual"]["stage_cooldown_seconds"] <= 86400:
        raise ValueError("visual stage cooldown must be between zero and one day")
    visual_ceilings = {
        "max_pack_items": 128, "max_candidates_per_item": 4,
        "max_width": 4096, "max_height": 4096, "max_generation_steps": 200,
        "max_stage_seconds": 86400, "max_pack_bytes": 107374182400,
        "minimum_free_bytes": 1099511627776,
    }
    if any(normalized["visual"][key] > ceiling for key, ceiling in visual_ceilings.items()):
        raise ValueError("visual pipeline limits exceed the hard safety envelope")
    budget = normalized["budget"]
    if any(budget[key] < 0 for key in ("monthly_limit", "weekly_limit", "per_run_approval_above", "emergency_reserve")):
        raise ValueError("budget amounts must not be negative")
    if not 0 <= budget["warning_fraction"] < budget["restriction_fraction"] < budget["hard_stop_fraction"] <= 1:
        raise ValueError("budget warning, restriction, and hard-stop fractions must be strictly ordered")
    active_budget_limits = [budget[key] for key in ("monthly_limit", "weekly_limit") if budget[key] > 0]
    if budget["external_calls_enabled"] and active_budget_limits and budget["emergency_reserve"] >= min(active_budget_limits):
        raise ValueError("emergency reserve must be smaller than every non-zero budget limit")
    for section, baseline in schemas.items():
        values = payload[section]
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise ValueError(f"settings {section} must be a list of objects")
        supplied = {item.get("id"): item for item in values}
        if len(supplied) != len(values):
            raise ValueError(f"settings {section} contains duplicate IDs")
        if any(not isinstance(item_id, str) or not SETTINGS_ID.fullmatch(item_id) for item_id in supplied):
            raise ValueError(f"settings {section} has an invalid ID")
        if section in extensible_schemas and not set(baseline).issubset(supplied):
            raise ValueError(f"settings {section} may not remove active catalog entries")
        if section not in extensible_schemas and set(supplied) != set(baseline):
            raise ValueError(f"settings {section} IDs do not match the active catalog")
        checked: list[dict[str, Any]] = []
        for item_id in sorted(supplied):
            candidate = supplied[item_id]
            original = baseline.get(item_id)
            field_schema = extensible_schemas.get(section)
            expected_fields = set(original) if original is not None else set(field_schema or {})
            if set(candidate) != expected_fields:
                raise ValueError(f"settings {section}/{item_id} has unknown or missing fields")
            type_contract = ({key: type(value) for key, value in original.items()} if original is not None else field_schema)
            candidate = dict(candidate)
            for key, required_type in type_contract.items():
                value = candidate[key]
                if original is not None and key not in mutable_fields[section] and value != original[key]:
                    raise SafetyError(f"settings {section}/{item_id}.{key} is not an operator-facing knob")
                if required_type is bool:
                    if not isinstance(value, bool):
                        raise ValueError(f"settings {section}/{item_id}.{key} must be boolean")
                elif required_type is float and isinstance(value, int) and not isinstance(value, bool):
                    # JSON and JavaScript have one number type, so an
                    # untouched 0.0 is serialized by the browser as 0.
                    candidate[key] = float(value)
                elif not isinstance(value, required_type):
                    raise ValueError(f"settings {section}/{item_id}.{key} has the wrong type")
            if section == "providers" and original is None:
                if candidate["kind"] not in {"openai_compatible", "local_openai_compatible"}:
                    raise ValueError(f"settings providers/{item_id}.kind is not supported by the custom-service form")
                if not re.fullmatch(r"https?://[^\s]+", candidate["endpoint"]):
                    raise ValueError(f"settings providers/{item_id}.endpoint must be an HTTP or HTTPS URL")
                if candidate["credential_env"] and not ENVIRONMENT_NAME.fullmatch(candidate["credential_env"]):
                    raise ValueError(f"settings providers/{item_id}.credential_env is invalid")
            if section == "models" and original is None:
                if not candidate["exact_name"].strip():
                    raise ValueError(f"settings models/{item_id}.exact_name must not be empty")
                if candidate["context_tokens"] < 1 or candidate["output_tokens"] < 1:
                    raise ValueError(f"settings models/{item_id} token limits must be positive")
                if candidate["modality"] not in MODEL_MODALITIES:
                    raise ValueError(f"settings models/{item_id}.modality is unsupported")
                if candidate["local"] and candidate["modality"] != "text" and not candidate["revision"]:
                    raise ValueError(f"local visual model {item_id} requires an immutable revision")
            checked.append(candidate)
        normalized[section] = checked
    provider_ids = {item["id"] for item in normalized["providers"]}
    model_ids = {item["id"] for item in normalized["models"]}
    for model in normalized["models"]:
        if model["provider"] not in provider_ids:
            raise ValueError(f"settings model {model['id']} names an unknown service")
    for route in normalized["routes"]:
        if any(model_id not in model_ids for model_id in route["ordered_model_ids"]):
            raise ValueError(f"settings route {route['id']} names an unknown model")
        if any(not model_supports_route(next(model for model in normalized["models"] if model["id"] == model_id)["modality"], route["model_modalities"]) for model_id in route["ordered_model_ids"]):
            raise ValueError(f"settings route {route['id']} contains a model with the wrong modality")
    return normalized


def rebase_settings_payload(bundle: ConfigBundle, source: dict[str, Any]) -> dict[str, Any]:
    """Carry operator-facing choices onto a newer complete settings catalog.

    New jobs, models, routes, prompts, and safety fields retain their new
    defaults. Removed implementation fields cannot be resurrected by a stale
    draft. The normal strict draft validator is the final gate.
    """
    target = settings_payload(bundle)
    mutable = {
        "jobs": {"enabled", "priority", "timeout_seconds", "max_attempts", "approval", "provider_route", "prompt_id"},
        "providers": {"enabled", "endpoint", "timeout_seconds", "max_attempts", "concurrency"},
        "models": {"enabled", "provider", "exact_name", "context_tokens", "output_tokens", "structured_output", "modality", "revision"},
        "routes": {"enabled", "ordered_model_ids", "fallback_failure_classes", "max_total_tokens", "max_cost_usd"},
        "prompts": {"enabled", "system", "template"},
    }
    for section, fields in mutable.items():
        old_values = source.get(section, [])
        if not isinstance(old_values, list):
            continue
        old = {item.get("id"): item for item in old_values if isinstance(item, dict) and isinstance(item.get("id"), str)}
        current = {item["id"]: item for item in target[section]}
        for item_id in sorted(set(old) & set(current)):
            for field in fields & set(old[item_id]) & set(current[item_id]):
                if section == "jobs" and field == "prompt_id" and old[item_id][field] == "none" and current[item_id][field] != "none":
                    # A newly commissioned dedicated task contract supersedes
                    # the old internal no-prompt sentinel; it was never an
                    # operator-authored prompt choice worth resurrecting.
                    continue
                if type(old[item_id][field]) is type(current[item_id][field]) or (
                    isinstance(current[item_id][field], float) and isinstance(old[item_id][field], int) and not isinstance(old[item_id][field], bool)
                ):
                    current[item_id][field] = old[item_id][field]
        if section == "providers":
            for item_id in sorted(set(old) - set(current)):
                if set(old[item_id]) == set(PROVIDER_KEYS):
                    target[section].append(dict(old[item_id]))
        if section == "models":
            for item_id in sorted(set(old) - set(current)):
                candidate = dict(old[item_id])
                candidate.setdefault("modality", "text")
                candidate.setdefault("revision", "")
                if set(candidate) == set(MODEL_KEYS):
                    target[section].append(candidate)
    singleton_fields = {
        "orchestration": {"strategic_boundary_cooldown_seconds"},
        "model_defaults": {"unlisted_context_tokens", "unlisted_output_tokens"},
        "visual": {"shadow_mode", "stage_cooldown_seconds", "max_pack_items", "max_candidates_per_item", "max_width", "max_height", "max_generation_steps", "max_stage_seconds", "max_pack_bytes", "minimum_free_bytes"},
        "budget": {"external_calls_enabled", "monthly_limit", "weekly_limit", "per_run_approval_above", "emergency_reserve", "warning_fraction", "restriction_fraction", "hard_stop_fraction"},
    }
    for section, fields in singleton_fields.items():
        old = source.get(section)
        if not isinstance(old, dict):
            continue
        for field in fields & set(old):
            current = target[section][field]
            value = old[field]
            if type(value) is type(current) or (isinstance(current, float) and isinstance(value, int) and not isinstance(value, bool)):
                target[section][field] = value
    target["base_config_sha256"] = bundle.sha256
    return validate_settings_payload(bundle, target)


def review_settings_payload(bundle: ConfigBundle, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_settings_payload(bundle, payload)
    active = settings_payload(bundle)
    changes: list[dict[str, Any]] = []
    for section in ("jobs", "providers", "models", "routes", "prompts"):
        before = {item["id"]: item for item in active[section]}
        after = {item["id"]: item for item in normalized[section]}
        for item_id in sorted(set(before) | set(after)):
            if item_id not in before:
                changes.append({"section": section, "id": item_id, "field": "record", "before": None, "after": after[item_id]})
                continue
            if item_id not in after:
                changes.append({"section": section, "id": item_id, "field": "record", "before": before[item_id], "after": None})
                continue
            for field in sorted(before[item_id]):
                if before[item_id][field] != after[item_id][field]:
                    changes.append({"section": section, "id": item_id, "field": field, "before": before[item_id][field], "after": after[item_id][field]})
    for section in ("orchestration", "model_defaults", "visual", "budget"):
        for field in sorted(active[section]):
            if active[section][field] != normalized[section][field]:
                changes.append({"section": section, "id": section, "field": field, "before": active[section][field], "after": normalized[section][field]})

    jobs = {item["id"]: item for item in normalized["jobs"]}
    routes = {item["id"]: item for item in normalized["routes"]}
    models = {item["id"]: item for item in normalized["models"]}
    providers = {item["id"]: item for item in normalized["providers"]}
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    live_locked_jobs: list[str] = []
    maintenance_jobs: dict[str, list[str]] = {}

    def issue(
        target: list[dict[str, Any]], code: str, message: str, item_id: str,
        setting: dict[str, str] | None = None,
    ) -> None:
        marker = (code, item_id)
        if marker not in seen:
            seen.add(marker)
            target.append({"code": code, "message": message, "target": item_id, "setting": setting})

    for job in jobs.values():
        if not job["enabled"]:
            continue
        if job["handler"] == "mission_hub.handlers.disabled:DisabledHandler":
            issue(
                blockers, "job_handler_uncommissioned", f"{job['id']} has no commissioned executor yet.", job["id"],
                {"section": "jobs", "id": job["id"], "field": "enabled", "label": "Requested availability"},
            )
        route = routes[job["provider_route"]]
        if not route["enabled"]:
            issue(
                blockers, "route_disabled", f"{job['id']} depends on the disabled {route['id']} execution path.", route["id"],
                {"section": "routes", "id": route["id"], "field": "enabled", "label": "Execution path available"},
            )
        if route["enabled"] and route["id"] != "deterministic" and not route["ordered_model_ids"]:
            issue(
                blockers, "route_has_no_model", f"{route['id']} has no primary model.", route["id"],
                {"section": "routes", "id": route["id"], "field": "ordered_model_ids", "label": "Primary and fallback models"},
            )
        if job["requires_live_execution"] and not bundle.base["safety"]["live_execution"]:
            live_locked_jobs.append(job["id"])
        machine = next((item for item in bundle.machines.values() if item["role"] == job["executor_role"]), None)
        if machine and machine["maintenance_mode"]:
            maintenance_jobs.setdefault(machine["display_name"], []).append(job["id"])

    if live_locked_jobs:
        issue(warnings, "live_execution_locked", f"The global live-execution lock would still block: {', '.join(sorted(live_locked_jobs))}.", "global-safety")
    for machine_name, job_ids in maintenance_jobs.items():
        issue(warnings, "machine_in_maintenance", f"{machine_name} maintenance would still block: {', '.join(sorted(job_ids))}.", machine_name)
    enabled_visual_jobs = sorted(job["id"] for job in jobs.values() if job["enabled"] and job["id"].startswith("visual."))
    if enabled_visual_jobs and normalized["visual"]["shadow_mode"]:
        issue(
            warnings, "visual_shadow_mode", "Visual shadow mode permits evidence runs but blocks final asset admission.", "visual",
            {"section": "visual", "id": "visual", "field": "shadow_mode", "label": "Shadow mode"},
        )

    used_model_ids = {model_id for route in routes.values() if route["enabled"] for model_id in route["ordered_model_ids"]}
    for model_id in sorted(used_model_ids):
        model = models[model_id]
        provider = providers[model["provider"]]
        if not model["enabled"]:
            issue(
                blockers, "model_disabled", f"The enabled route model {model_id} is disabled.", model_id,
                {"section": "models", "id": model_id, "field": "enabled", "label": "Model available"},
            )
        if not provider["enabled"]:
            issue(
                blockers, "provider_disabled", f"The enabled route model {model_id} uses disabled provider {provider['id']}.", provider["id"],
                {"section": "providers", "id": provider["id"], "field": "enabled", "label": "Provider available"},
            )
        for route in routes.values():
            if route["enabled"] and model_id in route["ordered_model_ids"] and route["max_total_tokens"] and route["max_total_tokens"] < model["output_tokens"]:
                issue(
                    warnings, "route_token_cap_lower", f"{model_id} allows {model['output_tokens']} output tokens, but {route['id']} caps total tokens at {route['max_total_tokens']}.", route["id"],
                    {"section": "routes", "id": route["id"], "field": "max_total_tokens", "label": "Total token ceiling"},
                )

    enabled_unused = [provider["id"] for provider in providers.values() if provider["enabled"] and not any(models[mid]["provider"] == provider["id"] for mid in used_model_ids)]
    for provider_id in enabled_unused:
        issue(
            warnings, "provider_enabled_unused", f"{provider_id} is enabled but no enabled route currently uses it.", provider_id,
            {"section": "providers", "id": provider_id, "field": "enabled", "label": "Provider available"},
        )

    requirements = [
        {"id": "source_reconciliation", "label": "Write the reviewed values into the strict configuration source."},
        {"id": "strict_validation", "label": "Validate the complete configuration and all cross-references."},
        {"id": "clean_role_releases", "label": "Build and verify clean Mission Hub and trainingbox releases."},
        {"id": "deployment_identity", "label": "Install matching release and configuration identities on both machines."},
        {"id": "operator_activation", "label": "Activate the snapshot explicitly after review."},
        {"id": "training_authorization_separate", "label": "Keep training authorization as a later, separate decision."},
    ]
    return {
        "schema_version": "ninereeds_lab_settings_review_v1",
        "change_count": len(changes), "changes": changes,
        "blockers": blockers, "warnings": warnings, "requirements": requirements,
        "ready_for_activation": not blockers,
    }
