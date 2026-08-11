"""Queue, close, and safely act on configurable on-call responses."""

from __future__ import annotations

import json
import re

from .config import ConfigBundle, machine_id_for_role
from .jsonutil import canonical_json
from .lab import LabStore
from .store import MissionHubStore, strategic_available_at, utc_now
from .recovery import RecoveryManager


class OperationalResponseCoordinator:
    SAFE_BOUNDARY_POLL_SECONDS = 15 * 60
    RESPONSE_RETRY_SECONDS = 60
    MAX_CONTEXT_MESSAGES = 64
    MAX_CONTEXT_UTF8_BYTES = 64 * 1024
    HUMAN_BLOCKERS = {
        "physical_hardware",
        "unavailable_credentials",
        "external_budget_or_legal_authority",
        "irreversible_evidence_destruction",
    }

    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store, self.bundle = store, bundle

    def tick(self, *, actor: str) -> int:
        if not getattr(self.bundle, "jobs", {}).get("operations.respond", {}).get("enabled"):
            return 0
        changed = self._reconcile_legacy_responses(actor=actor)
        changed += self._queue(actor=actor)
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT o.*,j.status AS job_status,r.output_json,
                          m.sender AS trigger_sender
                   FROM operational_responses o JOIN jobs j ON j.id=o.job_id
                   JOIN thread_messages m ON m.id=o.trigger_message_id
                   LEFT JOIN runs r ON r.job_id=j.id AND r.status='succeeded'
                   WHERE (o.status='queued' OR (
                              o.status='running'
                              AND (o.next_check_at IS NULL OR o.next_check_at<=?)
                          ))
                   ORDER BY o.created_at"""
                , (utc_now(),)
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
                # A failed assessment is not permission to abandon the
                # underlying incident, and on-call capacity is not a reason to
                # stop unrelated research. Preserve the failed response job and
                # retry the same trigger later without adding inbox noise.
                detail = _failure_detail(failure)
                next_check = strategic_available_at(utc_now(), self.RESPONSE_RETRY_SECONDS)
                with self.store.transaction() as db:
                    db.execute(
                        """UPDATE operational_responses SET status='pending',job_id=NULL,
                           disposition=NULL,action=NULL,action_result_json=NULL,finished_at=NULL,
                           next_check_at=?,wait_reason=?,wait_check_count=wait_check_count+1
                           WHERE trigger_message_id=?""",
                        (
                            next_check, f"On-call attempt retained for retry: {detail}",
                            row["trigger_message_id"],
                        ),
                    )
                changed += 1
                continue
            output = json.loads(row["output_json"])
            operator_requested = row["trigger_sender"] == "operator"
            action_result = self._act(output, actor=actor, operator_requested=operator_requested)
            if not action_result["applied"]:
                # The response is a principal-tier decision. A temporary or
                # mechanical execution failure may delay its effect, but it
                # cannot turn that decision into a rejected/abandoned response.
                # Keep the exact output and retry only its action, silently.
                next_check = strategic_available_at(utc_now(), self.RESPONSE_RETRY_SECONDS)
                retained = {**action_result, "accepted": True, "execution_pending": True}
                with self.store.transaction() as db:
                    db.execute(
                        """UPDATE operational_responses SET status='running',disposition=?,action=?,
                           action_result_json=?,next_check_at=?,wait_reason=?,finished_at=NULL
                           WHERE trigger_message_id=?""",
                        (
                            output["disposition"], output["action"], canonical_json(retained),
                            next_check, action_result["summary"], row["trigger_message_id"],
                        ),
                    )
                changed += 1
                continue
            LabStore(self.store).add_thread_message(
                row["thread_id"], _human_on_call_message(
                    output, action_result, conversational=row["trigger_sender"] == "operator",
                ),
                sender="sol", actor="mission-hub:on-call",
            )
            with self.store.transaction() as db:
                db.execute(
                    """UPDATE operational_responses SET status=?,disposition=?,action=?,
                       action_result_json=?,next_check_at=NULL,wait_reason=NULL,finished_at=?
                       WHERE trigger_message_id=?""",
                    ("succeeded", output["disposition"], output["action"], canonical_json({**action_result, "accepted": True}), utc_now(), row["trigger_message_id"]),
                )
            self._close_superseded_on_call_incidents(row["trigger_message_id"], actor=actor)
            changed += 1
        return changed

    def _reconcile_legacy_responses(self, *, actor: str) -> int:
        """Repair abandoned response rows produced by older releases.

        If the underlying work has recovered or has an active authorized
        successor, the abandoned assessment is silently superseded. Otherwise
        a failed assessment is put back into the normal retry queue. This is
        intentionally state-derived: thread prose alone never closes work.
        """
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT o.trigger_message_id,o.thread_id,o.status,m.body
                   FROM operational_responses o
                   JOIN thread_messages m ON m.id=o.trigger_message_id
                   WHERE o.status IN ('failed','blocked')
                   ORDER BY o.created_at"""
            ).fetchall()
        changed = 0
        for row in rows:
            if self._legacy_trigger_resolved(row["thread_id"], row["body"]):
                result = canonical_json({
                    "accepted": True,
                    "applied": True,
                    "superseded": True,
                    "summary": "The underlying work recovered or has an active authorized successor; the abandoned historical on-call attempt was reconciled silently.",
                })
                with self.store.transaction() as db:
                    db.execute(
                        """UPDATE operational_responses SET status='succeeded',
                           disposition='automatic_recovery',action='allow_automatic_recovery',
                           action_result_json=?,next_check_at=NULL,wait_reason=NULL,finished_at=?
                           WHERE trigger_message_id=?""",
                        (result, utc_now(), row["trigger_message_id"]),
                    )
                    self.store._event(
                        db, "operational_response", row["trigger_message_id"],
                        "on_call.historical_attempt_superseded", actor,
                        {"thread_id": row["thread_id"]},
                    )
                self._close_superseded_on_call_incidents(row["trigger_message_id"], actor=actor)
                changed += 1
            elif row["status"] == "failed":
                with self.store.transaction() as db:
                    db.execute(
                        """UPDATE operational_responses SET status='pending',job_id=NULL,
                           disposition=NULL,action=NULL,action_result_json=NULL,finished_at=NULL,
                           next_check_at=?,wait_reason='Historical on-call attempt retained for retry'
                           WHERE trigger_message_id=?""",
                        (utc_now(), row["trigger_message_id"]),
                    )
                    self.store._event(
                        db, "operational_response", row["trigger_message_id"],
                        "on_call.historical_attempt_requeued", actor,
                        {"thread_id": row["thread_id"]},
                    )
                changed += 1
        return changed

    def _legacy_trigger_resolved(self, thread_id: str, body: str) -> bool:
        with self.store._connect() as db:
            incident_match = re.search(r"^Recovery incident: (\S+)$", body, re.MULTILINE)
            if incident_match:
                incident = db.execute(
                    "SELECT state FROM recovery_incidents WHERE id=?", (incident_match.group(1),),
                ).fetchone()
                if incident is not None and incident["state"] == "recovered":
                    return True
            job_match = re.search(r"^Job: (\S+)$", body, re.MULTILINE)
            if job_match:
                job = db.execute("SELECT status FROM jobs WHERE id=?", (job_match.group(1),)).fetchone()
                if job is not None and job["status"] == "succeeded":
                    return True
            workflow_match = re.search(r"^Workflow: (\S+)$", body, re.MULTILINE)
            if workflow_match:
                workflow_id = workflow_match.group(1)
                cortex = db.execute(
                    "SELECT status FROM cortex_workflows WHERE id=?", (workflow_id,),
                ).fetchone()
                if cortex is not None and cortex["status"] in {"active", "complete"}:
                    return True
                visual = db.execute(
                    "SELECT status FROM visual_workflows WHERE id=?", (workflow_id,),
                ).fetchone()
                if visual is not None and visual["status"] == "succeeded":
                    return True
                for event in db.execute(
                    """SELECT e.entity_id,e.payload_json,v.status
                       FROM events e JOIN visual_workflows v ON v.id=e.entity_id
                       WHERE e.event_type='visual_workflow.authorized_successor'"""
                ).fetchall():
                    evidence = json.loads(event["payload_json"])
                    if (
                        evidence.get("predecessor_workflow_id") == workflow_id
                        and event["status"] in {"active", "succeeded"}
                    ):
                        return True
            # A failed response to an operator follow-up may carry the original
            # incident only in earlier messages in the same thread.
            messages = db.execute(
                "SELECT body FROM thread_messages WHERE thread_id=? ORDER BY created_at,id",
                (thread_id,),
            ).fetchall()
            for message in messages:
                match = re.search(r"^Recovery incident: (\S+)$", message["body"], re.MULTILINE)
                if not match:
                    continue
                incident = db.execute(
                    "SELECT state FROM recovery_incidents WHERE id=?", (match.group(1),),
                ).fetchone()
                if incident is not None and incident["state"] == "recovered":
                    return True
        return False

    def _close_superseded_on_call_incidents(self, trigger_message_id: str, *, actor: str) -> None:
        """Close recursive responder incidents left by releases predating v20.

        The successful response resolves the trigger. Failures of older
        ``operations.respond`` attempts are retained as runs, but are not
        independent research incidents and must not remain open forever.
        """
        now = utc_now()
        verification = canonical_json({
            "resolution": "superseded_on_call_attempt",
            "trigger_message_id": trigger_message_id,
        })
        with self.store.transaction() as db:
            rows = db.execute(
                """SELECT i.id FROM recovery_incidents i
                   JOIN jobs j ON j.id=i.job_id
                   WHERE j.job_type='operations.respond'
                     AND json_extract(j.input_json,'$.message_id')=?
                     AND i.state!='recovered'""",
                (trigger_message_id,),
            ).fetchall()
            for row in rows:
                db.execute(
                    """UPDATE recovery_incidents SET state='recovered',repair_allowed=0,
                       blocker_code=NULL,blocker_detail=NULL,verification_json=?,
                       updated_at=?,closed_at=? WHERE id=?""",
                    (verification, now, now, row["id"]),
                )
                self.store._event(
                    db, "recovery_incident", row["id"],
                    "recovery.on_call_attempt_superseded", actor,
                    {"trigger_message_id": trigger_message_id},
                )

    def _queue(self, *, actor: str) -> int:
        if not getattr(self.bundle, "jobs", {}).get("operations.respond", {}).get("enabled"):
            return 0
        now = utc_now()
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT o.*,t.subject,m.body FROM operational_responses o
                   JOIN message_threads t ON t.id=o.thread_id
                   JOIN thread_messages m ON m.id=o.trigger_message_id
                   WHERE o.status='pending' AND (o.next_check_at IS NULL OR o.next_check_at<=?)
                   ORDER BY o.created_at""",
                (now,),
            ).fetchall()
        changed = 0
        for row in rows:
            with self.store._connect() as db:
                active = db.execute(
                    """SELECT r.id AS run_id,j.id AS job_id,j.job_type
                       FROM runs r JOIN jobs j ON j.id=r.job_id
                       JOIN machines m ON m.id=r.machine_id
                       WHERE r.status IN ('leased','running') AND m.role='mission_hub'
                         AND j.job_type!='operations.respond'
                       ORDER BY r.started_at LIMIT 1"""
                ).fetchone()
            if active is not None:
                next_check = strategic_available_at(now, self.SAFE_BOUNDARY_POLL_SECONDS)
                reason = (
                    f"Mission Hub is finishing {active['job_type']} ({active['job_id']}); "
                    "interrupting work is not yet cooperatively supported."
                )
                first_wait = row["wait_started_at"] is None
                with self.store.transaction() as db:
                    db.execute(
                        """UPDATE operational_responses
                           SET wait_started_at=COALESCE(wait_started_at,?),next_check_at=?,
                               wait_reason=?,wait_check_count=wait_check_count+1
                           WHERE trigger_message_id=?""",
                        (now, next_check, reason, row["trigger_message_id"]),
                    )
                if first_wait:
                    LabStore(self.store).add_thread_message(
                        row["thread_id"],
                        _human_on_call_waiting_message(active, next_check),
                        sender="sol", actor="mission-hub:on-call",
                    )
                changed += 1
                continue
            job = self.store.create_job(
                self.bundle, job_type="operations.respond",
                input_payload={
                    "thread_id": row["thread_id"],
                    "message_id": row["trigger_message_id"],
                    "subject": row["subject"],
                    "body": row["body"],
                    **self._thread_context(row["thread_id"], row["trigger_message_id"]),
                },
                idempotency_key=(
                    f"operational-response:{row['trigger_message_id']}"
                    f":{row['wait_check_count']}"
                ),
                created_by=actor, campaign_id=None, requested_machine_id=machine_id_for_role(self.bundle, "mission_hub"), approved=True,
            )
            with self.store.transaction() as db:
                db.execute(
                    """UPDATE operational_responses SET status='queued',job_id=?,
                       next_check_at=NULL,wait_reason=NULL WHERE trigger_message_id=?""",
                    (job["id"], row["trigger_message_id"]),
                )
            changed += 1
        return changed

    def _thread_context(self, thread_id: str, trigger_message_id: str) -> dict:
        """Return bounded history ending at the exact triggering message."""
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT id,sender,body,created_at FROM thread_messages
                   WHERE thread_id=? ORDER BY created_at,id""",
                (thread_id,),
            ).fetchall()
        history = []
        for row in rows:
            history.append(dict(row))
            if row["id"] == trigger_message_id:
                break
        if not history or history[-1]["id"] != trigger_message_id:
            raise ValueError(f"trigger message {trigger_message_id} is not in thread {thread_id}")

        selected = []
        used = 0
        for message in reversed(history):
            size = len(message["body"].encode("utf-8"))
            if selected and (len(selected) >= self.MAX_CONTEXT_MESSAGES or used + size > self.MAX_CONTEXT_UTF8_BYTES):
                continue
            selected.append(message)
            used += size
        selected.reverse()
        return {
            "context_messages": selected,
            "context_truncated": len(selected) != len(history),
        }

    def _act(self, output: dict, *, actor: str, operator_requested: bool = False) -> dict:
        action = output["action"]
        recovery = RecoveryManager(self.store, self.bundle)
        if action == "recommission_visual_workflow":
            workflow_id = output.get("target_workflow_id")
            if not workflow_id:
                return {"applied": False, "blocker_code": "visual_workflow_missing", "summary": "Visual recommission was refused because the failed workflow was not named."}
            try:
                from .configured_campaign35 import ConfiguredCampaign35
                result = ConfiguredCampaign35(
                    self.store, self.bundle, self.bundle.root.parent.parent,
                ).recommission_visual_workflow(
                    workflow_id, actor="mission-hub:on-call",
                    authority_reference="sol-standing-visual-editorial-authority",
                )
            except Exception as exc:
                return {"applied": False, "blocker_code": "visual_recommission_refused", "summary": f"Visual recommission was refused safely: {type(exc).__name__}: {exc}"}
            return {
                "applied": True,
                "summary": (
                    f"I inspected the preserved review outcome and commissioned successor {result['successor_workflow_id']} "
                    f"with deterministic replacement seeds for rejected workflow {workflow_id}."
                ),
            }
        if action == "begin_repair":
            target, incident_id = output.get("target_job_id"), output.get("incident_id")
            if not target or not incident_id:
                return {"applied": False, "blocker_code": "repair_target_missing", "summary": "Repair was not started because the exact job and incident were not named."}
            try:
                incident = recovery.get(incident_id)
                if incident["job_id"] != target:
                    raise ValueError("incident does not belong to the target job")
                self.store.request_pipeline_state("paused", actor="mission-hub:on-call")
                attempt = recovery.start_authorized_repair(
                    incident_id, "principal_authorized_repair",
                    authorization_reference="sol-operational-response-standing-authority",
                    actor="mission-hub:on-call",
                )
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
                if operator_requested and job["status"] == "queued":
                    self.store.request_pipeline_state("running", actor="mission-hub:on-call")
                    return {
                        "applied": True,
                        "summary": "The existing unchanged retry was already queued, and I restarted the pipeline so it can run.",
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


def _human_on_call_message(output: dict, action_result: dict, *, conversational: bool = False) -> str:
    if conversational:
        sections = [output["assessment"].strip()]
        if output.get("action") != "no_action" or not action_result.get("applied"):
            sections.append("What I did:\n" + action_result["summary"].strip())
        return "\n\n".join(sections)
    sections = ["Short version:\n" + output["assessment"].strip()]
    if output.get("reasoning"):
        sections.append("What I found:\n" + output["reasoning"].strip())
    sections.append("What I did:\n" + action_result["summary"].strip())
    return "Sol's on-call update\n\n" + "\n\n".join(sections)


def _human_on_call_waiting_message(active: dict, next_check: str) -> str:
    return "\n\n".join((
        "Sol's on-call update",
        "Short version:\nI was invoked, but I am waiting for a safe boundary before I assess or change anything.",
        (
            "Why I am waiting:\nMission Hub is currently finishing "
            f"{active['job_type']} ({active['job_id']}). The work has not been interrupted."
        ),
        f"What happens next:\nI will check again at {next_check}. No model or worker is occupied while I wait.",
    ))


def _on_call_temporarily_unavailable(run: dict | None) -> bool:
    if run is None:
        return False
    return (
        run.get("failure_class") in {"operational_transient", "capability_transient"}
        or run.get("failure_code") in {
            "provider_capability_unavailable",
            "provider_rate_limited",
            "resource_temporarily_unavailable",
            "transport_unavailable",
        }
    )


def _failure_detail(run: dict | None) -> str:
    if run is None:
        return "the assessment run did not start"
    failure = json.loads(run.get("failure_json") or "{}")
    message = str(failure.get("message") or "").strip()
    code = str(run.get("failure_code") or "")
    if code == "provider_capability_unavailable" and "capacity" not in message.lower():
        return (
            "the configured on-call model is at capacity or otherwise temporarily unavailable"
            + (f" ({message})" if message else "")
        )
    return message or code or "temporary provider failure"


def _human_on_call_unavailable_message(detail: str, next_check: str) -> str:
    return "\n\n".join((
        "Mission Hub fail-safe",
        f"Short version:\nOn-call is temporarily unavailable: {detail}\nMission Hub paused all new dispatch.",
        (
            "What happens next:\nThe incident and requested assessment remain pending. "
            f"Mission Hub will try on-call again at {next_check}. The pipeline will remain paused until "
            "a successful on-call recovery action explicitly restarts it."
        ),
    ))


def _human_on_call_failure_message(job_status: str, run: dict | None) -> str:
    code = str((run or {}).get("failure_code") or "on_call_response_unavailable")
    failure = json.loads((run or {}).get("failure_json") or "{}")
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
        message = str(failure.get("message") or "The assessment run ended unexpectedly.").strip()
        explanation = message if message.endswith(".") else message + "."
    technical = [f"Response job status: {job_status}", f"Failure code: {code}"]
    if run is not None:
        technical.insert(1, f"Response run: {run['id']}")
    detail = str(failure.get("message") or "").strip()
    if detail:
        technical.append(f"Validation detail: {detail}")
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
