"""Queue, close, and safely act on configurable on-call responses."""

from __future__ import annotations

import json

from .config import ConfigBundle
from .jsonutil import canonical_json
from .lab import LabStore
from .store import MissionHubStore, utc_now


class OperationalResponseCoordinator:
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store, self.bundle = store, bundle

    def tick(self, *, actor: str) -> int:
        if not getattr(self.bundle, "jobs", {}).get("operations.respond", {}).get("enabled"):
            return 0
        changed = self._queue(actor=actor)
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT o.*,j.status AS job_status,r.output_json
                   FROM operational_responses o JOIN jobs j ON j.id=o.job_id
                   LEFT JOIN runs r ON r.job_id=j.id AND r.status='succeeded'
                   WHERE o.status IN ('queued','running')
                   ORDER BY o.created_at"""
            ).fetchall()
        for row in rows:
            if row["job_status"] in {"queued", "leased", "running"}:
                status = "running" if row["job_status"] in {"leased", "running"} else "queued"
                with self.store.transaction() as db:
                    db.execute("UPDATE operational_responses SET status=? WHERE trigger_message_id=?", (status, row["trigger_message_id"]))
                continue
            if row["job_status"] != "succeeded" or not row["output_json"]:
                with self.store.transaction() as db:
                    db.execute("UPDATE operational_responses SET status=?,finished_at=? WHERE trigger_message_id=?", ("failed", utc_now(), row["trigger_message_id"]))
                changed += 1
                continue
            output = json.loads(row["output_json"])
            action_result = self._act(output, actor=actor)
            body = output["assessment"].strip()
            if output.get("reasoning"):
                body += "\n\nReasoning:\n" + output["reasoning"].strip()
            body += "\n\nOn-call action: " + action_result["summary"]
            LabStore(self.store).add_thread_message(row["thread_id"], "On-call assessment:\n\n" + body, sender="mission_hub", actor="mission-hub:on-call")
            with self.store.transaction() as db:
                db.execute(
                    """UPDATE operational_responses SET status='succeeded',disposition=?,action=?,
                       action_result_json=?,finished_at=? WHERE trigger_message_id=?""",
                    (output["disposition"], output["action"], canonical_json(action_result), utc_now(), row["trigger_message_id"]),
                )
            changed += 1
        return changed

    def _queue(self, *, actor: str) -> int:
        if not getattr(self.bundle, "jobs", {}).get("operations.respond", {}).get("enabled"):
            return 0
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT o.*,t.subject,m.body FROM operational_responses o
                   JOIN message_threads t ON t.id=o.thread_id
                   JOIN thread_messages m ON m.id=o.trigger_message_id
                   WHERE o.status='pending' ORDER BY o.created_at"""
            ).fetchall()
        for row in rows:
            job = self.store.create_job(
                self.bundle, job_type="operations.respond",
                input_payload={"thread_id": row["thread_id"], "message_id": row["trigger_message_id"], "subject": row["subject"], "body": row["body"]},
                idempotency_key=f"operational-response:{row['trigger_message_id']}",
                created_by=actor, campaign_id=None, requested_machine_id="mission-hub", approved=True,
            )
            with self.store.transaction() as db:
                db.execute("UPDATE operational_responses SET status='queued',job_id=? WHERE trigger_message_id=?", (job["id"], row["trigger_message_id"]))
        return len(rows)

    def _act(self, output: dict, *, actor: str) -> dict:
        action = output["action"]
        if action == "retry_failed_job":
            target = output.get("target_job_id")
            if not target:
                return {"applied": False, "summary": "The responder requested a repaired retry without naming a job."}
            try:
                self.store.retry_failed_job_after_repair(
                    self.bundle, target, reason=output.get("reasoning") or output["assessment"],
                    actor="mission-hub:on-call",
                )
            except Exception as exc:
                return {"applied": False, "summary": f"The repaired retry was refused safely: {type(exc).__name__}: {exc}"}
            self.store.request_pipeline_state("running", actor="mission-hub:on-call")
            return {"applied": True, "summary": f"Repaired job {target} was queued against the newer active deployment and the pipeline was restarted."}
        if action == "pause_pipeline":
            self.store.request_pipeline_state("paused", actor="mission-hub:on-call")
            return {"applied": True, "summary": "Pipeline pause requested at the next safe boundary."}
        if action == "allow_automatic_recovery":
            return {"applied": True, "summary": "Existing deterministic retry/recovery policy remains in charge; no intervention was needed."}
        if action == "no_action":
            return {"applied": True, "summary": "No repair was needed; the on-call agent returned to standby."}
        return {"applied": False, "summary": "No bounded automatic repair exists for this condition; operator attention is still required."}
