"""Close checkpoint-pinned Lab chat invocations from immutable job evidence."""

from __future__ import annotations

import json
import uuid

from .config import ConfigBundle
from .jsonutil import canonical_json
from .service import MissionHubService
from .store import MissionHubStore, utc_now


class ChatCoordinator:
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store = store
        self.bundle = bundle

    def tick(self, *, actor: str) -> int:
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT i.*,j.status AS job_status
                   FROM chat_invocations i JOIN jobs j ON j.id=i.job_id
                   WHERE i.status IN ('queued','running')
                   AND j.status IN ('leased','running','succeeded','failed','blocked','cancelled')
                   ORDER BY i.created_at"""
            ).fetchall()
        changed = 0
        for row in rows:
            if row["job_status"] in {"leased", "running"}:
                with self.store.transaction() as db:
                    db.execute(
                        "UPDATE chat_invocations SET status='running',started_at=COALESCE(started_at,?) WHERE id=?",
                        (utc_now(), row["id"]),
                    )
                continue
            if row["job_status"] != "succeeded":
                with self.store.transaction() as db:
                    db.execute(
                        "UPDATE chat_invocations SET status=?,failure_json=?,finished_at=? WHERE id=?",
                        (row["job_status"], canonical_json({"code": "chat_job_terminal", "job_status": row["job_status"]}), utc_now(), row["id"]),
                    )
                changed += 1
                continue
            with self.store._connect() as db:
                artifact = db.execute(
                    """SELECT a.id FROM artifacts a JOIN runs r ON r.id=a.producing_run_id
                       WHERE r.job_id=? AND r.status='succeeded' AND a.kind='chat_report'""",
                    (row["job_id"],),
                ).fetchone()
            if artifact is None:
                continue
            service = MissionHubService(self.store, self.bundle)
            try:
                location = self.store.artifact_at(artifact["id"], machine_id="mission-hub")
            except Exception:
                location = service.retrieve_artifact(
                    artifact["id"], machine_id="trainbox", actor=actor,
                )
            report = json.loads(open(location["uri"], encoding="utf-8").read())
            if report.get("invocation_id") != row["id"]:
                raise RuntimeError("chat report invocation identity mismatch")
            message_id = f"chat-message-{uuid.uuid4()}"
            now = utc_now()
            with self.store.transaction() as db:
                db.execute(
                    "INSERT INTO chat_messages(id,thread_id,role,body,created_at) VALUES(?,?,'ninereeds',?,?)",
                    (message_id, row["thread_id"], report["response"], now),
                )
                db.execute(
                    "UPDATE chat_invocations SET status='succeeded',response_message_id=?,finished_at=? WHERE id=?",
                    (message_id, now, row["id"]),
                )
                db.execute("UPDATE chat_threads SET updated_at=? WHERE id=?", (now, row["thread_id"]))
                self.store._event(db, "chat_thread", row["thread_id"], "chat.response_recorded", actor, {
                    "invocation_id": row["id"], "message_id": message_id,
                    "job_id": row["job_id"], "artifact_id": artifact["id"],
                })
            changed += 1
        return changed
