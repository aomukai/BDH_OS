"""Queue, close, and safely act on configurable on-call responses."""

from __future__ import annotations

import json

from .config import ConfigBundle, machine_id_for_role
from .jsonutil import canonical_json
from .lab import LabStore
from .store import MissionHubStore, utc_now
from .recovery import RecoveryManager


class OperationalResponseCoordinator:
    HUMAN_BLOCKERS = {
        "physical_hardware",
        "unavailable_credentials",
        "external_budget_or_legal_authority",
        "unresolved_research_intent",
        "irreversible_evidence_destruction",
    }

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
                with self.store._connect() as db:
                    failed_run = db.execute(
                        """SELECT id,status,failure_class,failure_code,failure_json
                           FROM runs WHERE job_id=? ORDER BY attempt DESC LIMIT 1""",
                        (row["job_id"],),
                    ).fetchone()
                failure = dict(failed_run) if failed_run is not None else None
                LabStore(self.store).add_thread_message(
                    row["thread_id"], _human_on_call_failure_message(row["job_status"], failure),
                    sender="mission_hub", actor="mission-hub:on-call",
                )
                with self.store.transaction() as db:
                    db.execute(
                        """UPDATE operational_responses SET status='failed',disposition=NULL,
                           action=NULL,action_result_json=?,finished_at=?
                           WHERE trigger_message_id=?""",
                        (
                            canonical_json({
                                "applied": False, "blocker_code": "on_call_response_failed",
                                "summary": "Sol could not complete the assessment; no recovery action was taken.",
                            }),
                            utc_now(), row["trigger_message_id"],
                        ),
                    )
                changed += 1
                continue
            output = json.loads(row["output_json"])
            action_result = self._act(output, actor=actor)
            LabStore(self.store).add_thread_message(
                row["thread_id"], _human_on_call_message(output, action_result),
                sender="mission_hub", actor="mission-hub:on-call",
            )
            response_status = "succeeded" if action_result["applied"] else "failed"
            with self.store.transaction() as db:
                db.execute(
                    """UPDATE operational_responses SET status=?,disposition=?,action=?,
                       action_result_json=?,finished_at=? WHERE trigger_message_id=?""",
                    (response_status, output["disposition"], output["action"], canonical_json(action_result), utc_now(), row["trigger_message_id"]),
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
                created_by=actor, campaign_id=None, requested_machine_id=machine_id_for_role(self.bundle, "mission_hub"), approved=True,
            )
            with self.store.transaction() as db:
                db.execute("UPDATE operational_responses SET status='queued',job_id=? WHERE trigger_message_id=?", (job["id"], row["trigger_message_id"]))
        return len(rows)

    def _act(self, output: dict, *, actor: str) -> dict:
        action = output["action"]
        recovery = RecoveryManager(self.store, self.bundle)
        if action == "begin_repair":
            target, incident_id = output.get("target_job_id"), output.get("incident_id")
            if not target or not incident_id:
                return {"applied": False, "blocker_code": "repair_target_missing", "summary": "Repair was not started because the exact job and incident were not named."}
            try:
                incident = recovery.get(incident_id)
                if incident["job_id"] != target or incident["state"] != "classified" or not incident["repair_allowed"]:
                    raise ValueError("incident is not an eligible classified repair for the target job")
                self.store.request_pipeline_state("paused", actor="mission-hub:on-call")
                attempt = recovery.start_attempt(incident_id, "bounded_software_repair", actor="mission-hub:on-call")
            except Exception as exc:
                return {"applied": False, "blocker_code": "repair_start_refused", "summary": f"Bounded repair was refused safely: {type(exc).__name__}: {exc}"}
            return {
                "applied": True, "incident_id": incident_id, "recovery_attempt_id": attempt["id"],
                "summary": f"Bounded repair attempt {attempt['id']} started for job {target}; recovery evidence is now authoritative in Mission Hub.",
            }
        if action == "retry_failed_job":
            target = output.get("target_job_id")
            attempt_id = output.get("recovery_attempt_id")
            if not target or not attempt_id:
                return {"applied": False, "summary": "The responder requested a repaired retry without naming a job."}
            try:
                self.store.retry_failed_job_after_repair(
                    self.bundle, target, reason=output.get("reasoning") or output["assessment"],
                    actor="mission-hub:on-call", recovery_attempt_id=attempt_id,
                )
                recovery.record_action(attempt_id, "job_retry", "succeeded", {
                    "job_id": target, "input_sha256": self._job_input_sha256(target), "mode": "repaired_retry",
                }, actor="mission-hub:on-call")
                recovery.mark_retrying(attempt_id, actor="mission-hub:on-call")
            except Exception as exc:
                return {"applied": False, "summary": f"The repaired retry was refused safely: {type(exc).__name__}: {exc}"}
            self.store.request_pipeline_state("running", actor="mission-hub:on-call")
            return {"applied": True, "summary": f"Repaired job {target} was queued against the newer active deployment and the pipeline was restarted."}
        if action == "pause_pipeline":
            blocker = output.get("human_blocker")
            if output.get("disposition") != "operator_required" or blocker not in self.HUMAN_BLOCKERS:
                return {
                    "applied": False,
                    "summary": (
                        "Global pause refused: no structured human-only blocker was established. "
                        "The failed workflow remains contained while unrelated authorized work may continue."
                    ),
                }
            self.store.request_pipeline_state("paused", actor="mission-hub:on-call")
            return {
                "applied": True,
                "summary": f"Pipeline pause requested for the human-only blocker: {blocker}.",
            }
        if action == "allow_automatic_recovery":
            target = output.get("target_job_id")
            if target:
                with self.store._connect() as db:
                    job = db.execute("SELECT status FROM jobs WHERE id=?", (target,)).fetchone()
                if job is None:
                    return {"applied": False, "summary": f"Automatic recovery could not be verified because job {target} does not exist."}
                if job["status"] not in {"queued", "leased", "running"}:
                    try:
                        workflow = self.store.recover_queue_expired_cortex_stage(
                            self.bundle, target,
                            reason=output.get("reasoning") or output["assessment"],
                            actor="mission-hub:on-call",
                        )
                    except Exception:
                        workflow = None
                    if workflow is not None:
                        return {
                            "applied": True,
                            "summary": (
                                f"Untouched queue-expired job {target} was reauthorized and "
                                f"workflow {workflow['id']} resumed without retraining."
                            ),
                        }
                    return {
                        "applied": False,
                        "summary": (
                            f"No automatic recovery is active for job {target}; it remains {job['status']}. "
                            "A repaired deployment and explicit retry are still required."
                        ),
                    }
            return {
                "applied": True,
                "summary": "No state change was requested; the already active deterministic recovery remains in charge.",
            }
        if action == "no_action":
            target = output.get("target_job_id")
            if target:
                with self.store._connect() as db:
                    job = db.execute("SELECT status FROM jobs WHERE id=?", (target,)).fetchone()
                if job is not None and job["status"] in {"failed", "blocked", "cancelled"}:
                    return {
                        "applied": False,
                        "summary": (
                            f"No state transition was applied; job {target} remains {job['status']}. "
                            "An autonomous repair and newer active deployment are still required before retry."
                        ),
                    }
            return {"applied": True, "summary": "No repair was needed; the on-call agent returned to standby."}
        if action == "operator_required":
            blocker = output.get("blocker_reason")
            incident_id = output.get("incident_id")
            human_blocker = output.get("human_blocker")
            if human_blocker not in self.HUMAN_BLOCKERS:
                return {
                    "applied": False, "blocker_code": "human_authority_boundary_missing",
                    "summary": "Operator escalation was refused because no allowed human-only authority boundary was established.",
                }
            if not isinstance(blocker, dict) or not blocker.get("code") or not blocker.get("detail"):
                return {"applied": False, "blocker_code": "structured_blocker_missing", "summary": "Operator escalation was refused because it lacked a machine-readable blocker."}
            if incident_id:
                try:
                    recovery.block(incident_id, code=blocker["code"], detail=blocker["detail"], actor="mission-hub:on-call")
                except Exception as exc:
                    return {"applied": False, "blocker_code": "incident_block_refused", "summary": f"Incident blocker was refused safely: {type(exc).__name__}: {exc}"}
            return {"applied": True, "blocker_code": blocker["code"], "summary": f"Recovery is blocked: {blocker['code']}: {blocker['detail']}"}
        return {"applied": False, "blocker_code": "unsupported_recovery_action", "summary": "No bounded automatic repair action exists for this response."}

    def _job_input_sha256(self, job_id: str) -> str:
        with self.store._connect() as db:
            row = db.execute("SELECT input_sha256 FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise ValueError(f"job {job_id} does not exist")
        return str(row[0])


def _human_on_call_message(output: dict, action_result: dict) -> str:
    sections = ["Short version:\n" + output["assessment"].strip()]
    if output.get("reasoning"):
        sections.append("What I found:\n" + output["reasoning"].strip())
    sections.append("What I did:\n" + action_result["summary"].strip())
    return "Sol's on-call update\n\n" + "\n\n".join(sections)


def _human_on_call_failure_message(job_status: str, run: dict | None) -> str:
    code = str((run or {}).get("failure_code") or "on_call_response_unavailable")
    if code == "structured_response_invalid":
        explanation = (
            "I produced an answer, but it did not fit the system's required action format. "
            "The system rejected it instead of guessing what I meant."
        )
    elif code in {"provider_capability_unavailable", "resource_temporarily_unavailable"}:
        explanation = "The model service I use for on-call work was temporarily unavailable."
    elif run is None:
        explanation = "My on-call job stopped before an assessment run could begin."
    else:
        failure = json.loads(run.get("failure_json") or "{}")
        message = str(failure.get("message") or "The assessment run ended unexpectedly.").strip()
        explanation = message if message.endswith(".") else message + "."
    technical = [f"Response job status: {job_status}", f"Failure code: {code}"]
    if run is not None:
        technical.insert(1, f"Response run: {run['id']}")
    return "\n\n".join((
        "Sol's on-call update",
        "Short version:\nI could not complete the on-call assessment, so I did not change the pipeline.",
        "What went wrong:\n" + explanation,
        (
            "What this means:\nThe original problem remains safely contained, but it has not been repaired. "
            "The technical details below identify why my response failed."
        ),
        "Technical details:\n" + "\n".join(technical),
    ))
