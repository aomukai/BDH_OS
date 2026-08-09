"""Durable, machine-verifiable recovery state for bounded on-call work.

Natural-language incident threads are projections of these records.  They are
never accepted as evidence that a repair, deployment, retry, or health check
occurred.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sqlite3
from typing import Any
import uuid
from typing import Protocol

from .config import ConfigBundle, bundle_from_snapshot, machine_id_for_role
from .errors import NotFoundError, SafetyError, TransitionError
from .jsonutil import canonical_json, content_hash
from .store import MissionHubStore, utc_now


ACTIVE_STATES = {"detected", "classified", "monitoring", "repairing", "retrying", "verifying"}
TERMINAL_STATES = {"recovered", "blocked", "escalated"}


def classify_failure(failure_class: str, failure_code: str, *, job_terminal: bool) -> tuple[str, bool, str | None]:
    """Map failure taxonomy to behavior, not merely a display label."""

    if failure_class in {"operational_transient", "capability_transient"} and not job_terminal:
        return "transient", False, None
    if failure_code in {"transport_unavailable", "resource_temporarily_unavailable", "lease_expired", "disk_write_failed", "process_interrupted", "deployment_stale"}:
        return "infrastructure", True, None
    if failure_code in {"provider_rate_limited", "provider_capability_unavailable"}:
        return ("infrastructure", True, None) if job_terminal else ("transient", False, None)
    if failure_code == "configuration_invalid":
        return "configuration", True, None
    if failure_code in {"output_schema_invalid", "artifact_contract_invalid", "artifact_corrupt", "checkpoint_mismatch"}:
        return "contract", True, None
    if failure_code in {"job_spec_invalid", "unexpected_internal_error", "dependency_missing"}:
        return "software", True, None
    if failure_class == "safety_policy":
        return "safety", False, "safety_invariant_refused"
    if failure_class in {"task_outcome", "operator_action"}:
        return "external", False, "non_repairable_task_outcome"
    return "software", True, None


class RecoveryManager:
    """Own incident transitions and immutable action evidence."""

    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store, self.bundle = store, bundle

    def capture_failure_db(
        self,
        db: sqlite3.Connection,
        *,
        job: sqlite3.Row,
        run: sqlite3.Row,
        failure: dict[str, Any],
        resulting_job_status: str,
        actor: str,
    ) -> str:
        existing = db.execute(
            "SELECT id FROM recovery_incidents WHERE failed_run_id=?", (run["id"],),
        ).fetchone()
        if existing is not None:
            return str(existing[0])
        verifying = db.execute(
            """SELECT i.id AS incident_id,i.repair_budget,i.attempts_started,a.id AS attempt_id
               FROM recovery_incidents i JOIN recovery_attempts a ON a.incident_id=i.id
               WHERE i.job_id=? AND i.state='verifying' AND a.state='verifying'
               ORDER BY a.ordinal DESC LIMIT 1""",
            (job["id"],),
        ).fetchone()
        if verifying is not None:
            self._record_verification_failure_db(
                db, verifying, run=run, failure=failure, actor=actor,
            )
            return str(verifying["incident_id"])
        category, allowed, blocker = classify_failure(
            failure["class"], failure["code"], job_terminal=resulting_job_status == "failed",
        )
        message_lower = str(failure.get("message", "")).lower()
        if failure["code"] == "provider_capability_unavailable" and "credential" in message_lower and "unavailable" in message_lower:
            category, allowed, blocker = "external", False, "unavailable_credentials"
        incident_id = f"inc-{uuid.uuid4()}"
        now = utc_now()
        configured_retry = resulting_job_status == "queued"
        if configured_retry:
            # The job engine has already authorized an unchanged bounded
            # retry. Keep the incident in verification regardless of whether
            # the original category was transport or malformed output; a
            # successful successor must be able to close it without prose or
            # an unnecessary source mutation.
            state = "monitoring"
            blocker = None
        elif blocker:
            state = "blocked"
        elif category == "transient":
            state = "monitoring"
        else:
            state = "classified"
        # Sol's on-call work is not a mechanical retry loop. Keep the legacy
        # integer column for durable schema compatibility, but represent the
        # absence of a numeric ceiling as zero and never exhaust it. Execution
        # retries remain bounded independently by the job retry policy.
        attempts_unbounded = True
        budget = 0
        db.execute(
            """INSERT INTO recovery_incidents
               (id,failed_run_id,job_id,campaign_id,state,category,failure_class,failure_code,
                repair_allowed,repair_budget,blocker_code,blocker_detail,created_at,updated_at,closed_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                incident_id, run["id"], job["id"], job["campaign_id"], state, category,
                failure["class"], failure["code"], int(allowed), budget, blocker,
                failure.get("message") if blocker else None, now, now,
                now if state in TERMINAL_STATES else None,
            ),
        )
        self.store._event(db, "recovery_incident", incident_id, "recovery.detected", actor, {
            "job_id": job["id"], "run_id": run["id"], "category": category,
            "failure_class": failure["class"], "failure_code": failure["code"],
            "resulting_job_status": resulting_job_status,
        })
        self.store._event(db, "recovery_incident", incident_id, f"recovery.{state}", actor, {
            "repair_allowed": allowed, "repair_budget": budget,
            "repair_attempt_limit": None if attempts_unbounded else budget,
            "repair_attempts_unbounded": attempts_unbounded, "blocker_code": blocker,
        })
        if job["campaign_id"] is not None and resulting_job_status == "failed":
            block_id = f"cblk-{content_hash({'campaign_id': job['campaign_id'], 'incident_id': incident_id})[:20]}"
            db.execute(
                """INSERT INTO campaign_blocks
                   (id,campaign_id,source_type,source_id,incident_id,code,detail,state,created_at)
                   VALUES(?,?,'recovery_incident',?,?,?,?,'active',?)""",
                (block_id, job["campaign_id"], incident_id, incident_id, failure["code"], failure.get("message", ""), now),
            )
            self.store._event(db, "campaign", job["campaign_id"], "campaign.blocked_by_incident", actor, {
                "block_id": block_id, "incident_id": incident_id, "job_id": job["id"], "failure_code": failure["code"],
            })
        if configured_retry:
            attempt_id = self._start_attempt_db(db, incident_id, "deterministic_retry", actor=actor, consumes_budget=False)
            self._record_action_db(db, attempt_id, "evidence_preserved", "succeeded", {
                "failed_run_id": run["id"], "failure_code": failure["code"],
                "failure_sha256": content_hash(failure),
            })
            self._record_action_db(db, attempt_id, "job_retry", "succeeded", {
                "job_id": job["id"], "mode": "configured_retry", "input_sha256": job["input_sha256"],
                "resulting_status": resulting_job_status,
            })
            db.execute("UPDATE recovery_attempts SET state='verifying' WHERE id=?", (attempt_id,))
        return incident_id

    def _record_verification_failure_db(
        self, db: sqlite3.Connection, recovery: sqlite3.Row, *, run: sqlite3.Row,
        failure: dict[str, Any], actor: str,
    ) -> None:
        """Preserve a failed successor as an attempt result, not a second incident."""
        now = utc_now()
        self._record_action_db(db, recovery["attempt_id"], "health_check", "failed", {
            "run_id": run["id"], "failure_code": failure["code"],
            "failure_class": failure["class"], "failure_sha256": content_hash(failure),
        })
        db.execute(
            """UPDATE recovery_attempts SET state='failed',failure_code=?,summary=?,finished_at=?
               WHERE id=?""",
            (failure["code"], failure.get("message", "successor verification failed"), now, recovery["attempt_id"]),
        )
        exhausted = False
        next_state = "escalated" if exhausted else "classified"
        blocker = "repair_budget_exhausted" if exhausted else None
        db.execute(
            """UPDATE recovery_incidents SET state=?,blocker_code=?,blocker_detail=?,updated_at=?,closed_at=?
               WHERE id=?""",
            (
                next_state, blocker, failure.get("message") if blocker else None, now,
                now if exhausted else None, recovery["incident_id"],
            ),
        )
        self.store._event(db, "recovery_incident", recovery["incident_id"], "recovery.verification_failed", actor, {
            "attempt_id": recovery["attempt_id"], "successor_run_id": run["id"],
            "failure_code": failure["code"], "budget_exhausted": exhausted,
        })

    def incident_for_job(self, job_id: str) -> dict[str, Any] | None:
        with self.store._connect() as db:
            row = db.execute(
                "SELECT * FROM recovery_incidents WHERE job_id=? ORDER BY created_at DESC LIMIT 1", (job_id,),
            ).fetchone()
        return self._incident_row(row) if row is not None else None

    def get(self, incident_id: str) -> dict[str, Any]:
        with self.store._connect() as db:
            row = db.execute("SELECT * FROM recovery_incidents WHERE id=?", (incident_id,)).fetchone()
            if row is None:
                raise NotFoundError(incident_id)
            attempts = db.execute(
                "SELECT * FROM recovery_attempts WHERE incident_id=? ORDER BY ordinal", (incident_id,),
            ).fetchall()
            result = self._incident_row(row)
            result["attempts"] = []
            for attempt in attempts:
                value = dict(attempt)
                actions = db.execute(
                    "SELECT * FROM recovery_actions WHERE attempt_id=? ORDER BY sequence", (attempt["id"],),
                ).fetchall()
                value["actions"] = [self._action_row(action) for action in actions]
                result["attempts"].append(value)
        return result

    def start_attempt(self, incident_id: str, strategy: str, *, actor: str) -> dict[str, Any]:
        with self.store.transaction() as db:
            attempt_id = self._start_attempt_db(db, incident_id, strategy, actor=actor, consumes_budget=True)
        return self.get(incident_id)["attempts"][-1]

    def start_external_repair(
        self, incident_id: str, strategy: str, *, authorization_reference: str, actor: str,
    ) -> dict[str, Any]:
        """Re-enter a budget-exhausted incident after independently authorized work.

        This does not enlarge autonomous repair authority or rewrite the failed
        attempt. It creates a distinct, auditable attempt whose patch, tests,
        deployment, and retry must satisfy the same machine-verifiable gates.
        """
        authorization_reference = authorization_reference.strip()
        if not authorization_reference or len(authorization_reference.encode("utf-8")) > 4096:
            raise ValueError("external repair requires a bounded authorization reference")
        with self.store.transaction() as db:
            incident = db.execute(
                "SELECT * FROM recovery_incidents WHERE id=?", (incident_id,),
            ).fetchone()
            if incident is None:
                raise NotFoundError(incident_id)
            if (
                incident["state"] != "escalated"
                or incident["blocker_code"] != "repair_budget_exhausted"
                or not incident["repair_allowed"]
            ):
                raise TransitionError(
                    "external repair re-entry requires a repairable budget-exhausted incident"
                )
            ordinal = int(incident["attempts_started"]) + 1
            attempt_id = f"rat-{uuid.uuid4()}"
            now = utc_now()
            db.execute(
                """INSERT INTO recovery_attempts(id,incident_id,ordinal,state,strategy,started_at)
                   VALUES(?,?,?,'planned',?,?)""",
                (attempt_id, incident_id, ordinal, strategy, now),
            )
            db.execute(
                """UPDATE recovery_incidents
                   SET state='repairing',attempts_started=?,blocker_code=NULL,blocker_detail=NULL,
                       updated_at=?,closed_at=NULL WHERE id=?""",
                (ordinal, now, incident_id),
            )
            self.store._event(db, "recovery_incident", incident_id, "recovery.external_repair_started", actor, {
                "attempt_id": attempt_id, "ordinal": ordinal, "strategy": strategy,
                "authorization_reference": authorization_reference,
                "autonomous_budget_extended": False,
            })
        return self.get(incident_id)["attempts"][-1]

    def _start_attempt_db(
        self, db: sqlite3.Connection, incident_id: str, strategy: str, *, actor: str, consumes_budget: bool,
    ) -> str:
        incident = db.execute("SELECT * FROM recovery_incidents WHERE id=?", (incident_id,)).fetchone()
        if incident is None:
            raise NotFoundError(incident_id)
        if incident["state"] in TERMINAL_STATES or incident["state"] not in {"classified", "monitoring"}:
            raise TransitionError(f"incident {incident_id} cannot start an attempt from {incident['state']}")
        ordinal = int(incident["attempts_started"]) + 1
        attempts_unbounded = True
        if consumes_budget and not incident["repair_allowed"]:
            raise SafetyError("incident does not permit autonomous repair")
        attempt_id = f"rat-{uuid.uuid4()}"
        now = utc_now()
        db.execute(
            "INSERT INTO recovery_attempts(id,incident_id,ordinal,state,strategy,started_at) VALUES(?,?,?,'planned',?,?)",
            (attempt_id, incident_id, ordinal, strategy, now),
        )
        db.execute(
            "UPDATE recovery_incidents SET state=?,attempts_started=?,updated_at=? WHERE id=?",
            ("repairing" if consumes_budget else "monitoring", ordinal, now, incident_id),
        )
        self.store._event(db, "recovery_incident", incident_id, "recovery.attempt_started", actor, {
            "attempt_id": attempt_id, "ordinal": ordinal, "strategy": strategy,
            "consumes_budget": consumes_budget and not attempts_unbounded,
            "repair_attempt_limit": None if attempts_unbounded else incident["repair_budget"],
        })
        return attempt_id

    def record_action(
        self, attempt_id: str, kind: str, status: str, evidence: dict[str, Any], *, actor: str,
    ) -> dict[str, Any]:
        with self.store.transaction() as db:
            action_id = self._record_action_db(db, attempt_id, kind, status, evidence)
            incident_id = db.execute(
                "SELECT incident_id FROM recovery_attempts WHERE id=?", (attempt_id,),
            ).fetchone()[0]
            self.store._event(db, "recovery_incident", incident_id, f"recovery.action_{status}", actor, {
                "attempt_id": attempt_id, "action_id": action_id, "kind": kind,
                "evidence_sha256": content_hash({"kind": kind, "status": status, "evidence": evidence}),
            })
        return {"id": action_id, "kind": kind, "status": status, "evidence": evidence}

    def _record_action_db(
        self, db: sqlite3.Connection, attempt_id: str, kind: str, status: str, evidence: dict[str, Any],
    ) -> str:
        self._validate_action(kind, status, evidence)
        row = db.execute("SELECT 1 FROM recovery_attempts WHERE id=?", (attempt_id,)).fetchone()
        if row is None:
            raise NotFoundError(attempt_id)
        sequence = int(db.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM recovery_actions WHERE attempt_id=?", (attempt_id,),
        ).fetchone()[0])
        body = {"attempt_id": attempt_id, "sequence": sequence, "kind": kind, "status": status, "evidence": evidence}
        digest = content_hash(body)
        action_id = f"rac-{digest[:20]}"
        db.execute(
            """INSERT INTO recovery_actions
               (id,attempt_id,sequence,kind,status,evidence_json,evidence_sha256,recorded_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (action_id, attempt_id, sequence, kind, status, canonical_json(evidence), digest, utc_now()),
        )
        return action_id

    def fail_attempt(self, attempt_id: str, *, code: str, summary: str, actor: str) -> dict[str, Any]:
        if not code or not summary:
            raise ValueError("failed recovery attempt requires a code and summary")
        now = utc_now()
        with self.store.transaction() as db:
            attempt = db.execute("SELECT * FROM recovery_attempts WHERE id=?", (attempt_id,)).fetchone()
            if attempt is None:
                raise NotFoundError(attempt_id)
            incident = db.execute("SELECT * FROM recovery_incidents WHERE id=?", (attempt["incident_id"],)).fetchone()
            db.execute(
                "UPDATE recovery_attempts SET state='failed',failure_code=?,summary=?,finished_at=? WHERE id=?",
                (code, summary, now, attempt_id),
            )
            exhausted = False
            next_state = "escalated" if exhausted else "classified"
            blocker = "repair_budget_exhausted" if exhausted else None
            db.execute(
                """UPDATE recovery_incidents SET state=?,blocker_code=?,blocker_detail=?,updated_at=?,closed_at=?
                   WHERE id=?""",
                (next_state, blocker, summary if blocker else None, now, now if exhausted else None, incident["id"]),
            )
            self.store._event(db, "recovery_incident", incident["id"], "recovery.attempt_failed", actor, {
                "attempt_id": attempt_id, "failure_code": code, "budget_exhausted": exhausted,
            })
        return self.get(attempt["incident_id"])

    def mark_retrying(self, attempt_id: str, *, actor: str) -> None:
        with self.store.transaction() as db:
            attempt = db.execute("SELECT * FROM recovery_attempts WHERE id=?", (attempt_id,)).fetchone()
            if attempt is None:
                raise NotFoundError(attempt_id)
            self._require_action_kinds(db, attempt_id, self._repair_requirements(attempt["incident_id"], db, before_retry=True))
            now = utc_now()
            db.execute("UPDATE recovery_attempts SET state='verifying' WHERE id=?", (attempt_id,))
            db.execute("UPDATE recovery_incidents SET state='verifying',updated_at=? WHERE id=?", (now, attempt["incident_id"]))
            self.store._event(db, "recovery_incident", attempt["incident_id"], "recovery.retry_verification_started", actor, {"attempt_id": attempt_id})

    def require_ready_for_retry(self, attempt_id: str) -> dict[str, Any]:
        """Prove repair/deployment evidence before a terminal job may move."""
        with self.store._connect() as db:
            attempt = db.execute("SELECT * FROM recovery_attempts WHERE id=?", (attempt_id,)).fetchone()
            if attempt is None:
                raise NotFoundError(attempt_id)
            if attempt["state"] not in {"planned", "applying", "validating", "deploying"}:
                raise TransitionError(f"repair attempt {attempt_id} is {attempt['state']}")
            self._require_action_kinds(
                db, attempt_id, self._repair_requirements(attempt["incident_id"], db, before_retry=True),
            )
            category = db.execute(
                "SELECT category FROM recovery_incidents WHERE id=?", (attempt["incident_id"],),
            ).fetchone()[0]
            if category != "transient":
                self._require_test_scopes(db, attempt_id)
            return dict(attempt)

    def reconcile(self, *, actor: str) -> int:
        """Close only incidents whose authoritative job and artifact state prove health."""
        changed = 0
        with self.store._connect() as db:
            ids = [row[0] for row in db.execute(
                "SELECT id FROM recovery_incidents WHERE state IN ('monitoring','retrying','verifying') ORDER BY created_at",
            ).fetchall()]
        for incident_id in ids:
            if self._reconcile_one(incident_id, actor=actor):
                changed += 1
        return changed

    def _reconcile_one(self, incident_id: str, *, actor: str) -> bool:
        now = utc_now()
        closure: dict[str, Any] | None = None
        with self.store.transaction() as db:
            incident = db.execute("SELECT * FROM recovery_incidents WHERE id=?", (incident_id,)).fetchone()
            job = db.execute("SELECT * FROM jobs WHERE id=?", (incident["job_id"],)).fetchone()
            if job["status"] == "cancelled":
                attempt = db.execute(
                    "SELECT * FROM recovery_attempts WHERE incident_id=? ORDER BY ordinal DESC LIMIT 1",
                    (incident_id,),
                ).fetchone()
                detail = job["cancel_reason"] or "job was explicitly cancelled before recovery verification"
                if attempt is not None and attempt["state"] not in {"failed", "succeeded"}:
                    self._record_action_db(db, attempt["id"], "health_check", "failed", {
                        "run_id": incident["failed_run_id"], "passed": False,
                        "job_id": job["id"], "job_status": "cancelled",
                    })
                    db.execute(
                        "UPDATE recovery_attempts SET state='failed',failure_code='operator_cancelled',summary=?,finished_at=? WHERE id=?",
                        (detail, now, attempt["id"]),
                    )
                db.execute(
                    """UPDATE recovery_incidents SET state='blocked',blocker_code='operator_cancelled',
                       blocker_detail=?,updated_at=?,closed_at=? WHERE id=?""",
                    (detail, now, now, incident_id),
                )
                self.store._event(db, "recovery_incident", incident_id, "recovery.blocked", actor, {
                    "blocker_code": "operator_cancelled", "detail": detail, "job_id": job["id"],
                })
                return True
            if job["status"] != "succeeded":
                return False
            run = db.execute(
                "SELECT * FROM runs WHERE job_id=? AND status='succeeded' ORDER BY attempt DESC LIMIT 1", (job["id"],),
            ).fetchone()
            if run is None or run["id"] == incident["failed_run_id"] or not run["output_sha256"]:
                return False
            attempt = db.execute(
                "SELECT * FROM recovery_attempts WHERE incident_id=? ORDER BY ordinal DESC LIMIT 1", (incident_id,),
            ).fetchone()
            if attempt is None or attempt["state"] not in {"verifying", "retrying"}:
                return False
            definition = self.bundle.jobs[job["job_type"]]
            artifacts = db.execute(
                "SELECT id,kind,sha256,byte_size FROM artifacts WHERE producing_run_id=? ORDER BY kind,id", (run["id"],),
            ).fetchall()
            produced = [row["kind"] for row in artifacts]
            valid = all(produced.count(kind) == 1 for kind in definition["required_artifact_types"])
            if not valid:
                return False
            if not self._has_action(db, attempt["id"], "artifact_validation"):
                self._record_action_db(db, attempt["id"], "artifact_validation", "succeeded", {
                    "run_id": run["id"], "output_sha256": run["output_sha256"],
                    "artifact_ids": [row["id"] for row in artifacts],
                    "required_artifact_types": definition["required_artifact_types"],
                })
            if not self._has_action(db, attempt["id"], "health_check"):
                self._record_action_db(db, attempt["id"], "health_check", "succeeded", {
                    "passed": True, "job_id": job["id"], "run_id": run["id"],
                    "job_status": job["status"], "output_sha256": run["output_sha256"],
                })
            required = self._repair_requirements(incident_id, db, before_retry=False)
            self._require_action_kinds(db, attempt["id"], required)
            verification = {
                "job_id": job["id"], "successful_run_id": run["id"],
                "output_sha256": run["output_sha256"], "artifact_ids": [row["id"] for row in artifacts],
                "required_action_kinds": sorted(required),
            }
            db.execute(
                "UPDATE recovery_attempts SET state='succeeded',summary=?,finished_at=? WHERE id=?",
                ("authoritative retry and output verification succeeded", now, attempt["id"]),
            )
            db.execute(
                """UPDATE recovery_incidents SET state='recovered',verification_json=?,blocker_code=NULL,
                   blocker_detail=NULL,updated_at=?,closed_at=? WHERE id=?""",
                (canonical_json(verification), now, now, incident_id),
            )
            blocks = db.execute(
                "SELECT id,campaign_id FROM campaign_blocks WHERE incident_id=? AND state='active'", (incident_id,),
            ).fetchall()
            for block in blocks:
                resolution = {"incident_id": incident_id, "successful_run_id": run["id"], "verification_sha256": content_hash(verification)}
                db.execute(
                    "UPDATE campaign_blocks SET state='resolved',resolved_at=?,resolution_json=? WHERE id=?",
                    (now, canonical_json(resolution), block["id"]),
                )
                self.store._event(db, "campaign", block["campaign_id"], "campaign.block_resolved", actor, {
                    "block_id": block["id"], **resolution,
                })
            self.store._event(db, "recovery_incident", incident_id, "recovery.recovered", actor, verification)
            actions = db.execute(
                "SELECT kind,evidence_json FROM recovery_actions WHERE attempt_id=? AND status='succeeded' ORDER BY sequence",
                (attempt["id"],),
            ).fetchall()
            closure = {
                "thread_id": incident["operational_thread_id"],
                "job_type": job["job_type"],
                "failure_code": incident["failure_code"],
                "attempt": attempt["ordinal"],
                "run_id": run["id"],
                "artifact_ids": [row["id"] for row in artifacts],
                "actions": [(row["kind"], json.loads(row["evidence_json"])) for row in actions],
            }
        if closure and closure["thread_id"]:
            self._project_recovery_closure(closure)
        return True

    def _project_recovery_closure(self, closure: dict[str, Any]) -> None:
        """Project authoritative records into the human thread after commit.

        Thread delivery is intentionally best effort: durable recovery state and
        its hashed action rows remain authoritative if presentation is unavailable.
        """
        deployment = next((value for kind, value in closure["actions"] if kind == "deployment"), None)
        mutation = next(
            (value for kind, value in closure["actions"] if kind in {"source_patch", "configuration_change"}),
            None,
        )
        tests = [value for kind, value in closure["actions"] if kind == "tests"]
        changed = mutation.get("changed_files", []) if mutation else []
        mutation_text = ", ".join(changed) if changed else "validated configuration rollback"
        test_text = ", ".join(f"{item['scope']}=passed" for item in tests) or "not required (transient retry)"
        deployment_text = (
            f"{deployment['before_deployment_id']} -> {deployment['after_deployment_id']}"
            if deployment else "unchanged (transient retry)"
        )
        body = "\n".join([
            "Recovery verified from authoritative action records.",
            f"Failure: {closure['job_type']} / {closure['failure_code']}",
            f"Repair attempt: {closure['attempt']}; change: {mutation_text}",
            f"Tests: {test_text}",
            f"Deployment: {deployment_text}",
            f"Retry: succeeded as run {closure['run_id']}",
            f"Artifacts validated: {', '.join(closure['artifact_ids']) or 'none required'}",
            "Final state: recovered; associated campaign block resolved.",
        ])
        try:
            from .lab import LabStore
            LabStore(self.store).add_thread_message(
                closure["thread_id"], body, sender="mission_hub", actor="mission-hub:on-call",
            )
        except Exception:
            return

    def block(self, incident_id: str, *, code: str, detail: str, actor: str) -> None:
        if not code or not detail:
            raise ValueError("recovery blocker requires a code and detail")
        now = utc_now()
        with self.store.transaction() as db:
            incident = db.execute("SELECT state FROM recovery_incidents WHERE id=?", (incident_id,)).fetchone()
            if incident is None:
                raise NotFoundError(incident_id)
            if incident[0] in TERMINAL_STATES:
                raise TransitionError(f"incident {incident_id} is already {incident[0]}")
            db.execute(
                "UPDATE recovery_incidents SET state='blocked',blocker_code=?,blocker_detail=?,updated_at=?,closed_at=? WHERE id=?",
                (code, detail, now, now, incident_id),
            )
            self.store._event(db, "recovery_incident", incident_id, "recovery.blocked", actor, {"blocker_code": code, "detail": detail})

    @staticmethod
    def _incident_row(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["repair_allowed"] = bool(value["repair_allowed"])
        value["verification"] = json.loads(value.pop("verification_json")) if value.get("verification_json") else None
        return value

    @staticmethod
    def _action_row(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["evidence"] = json.loads(value.pop("evidence_json"))
        return value

    def _repair_requirements(self, incident_id: str, db: sqlite3.Connection, *, before_retry: bool) -> set[str]:
        category = db.execute("SELECT category FROM recovery_incidents WHERE id=?", (incident_id,)).fetchone()[0]
        latest = db.execute(
            "SELECT strategy FROM recovery_attempts WHERE incident_id=? ORDER BY ordinal DESC LIMIT 1",
            (incident_id,),
        ).fetchone()
        configured_retry = latest is not None and latest[0] == "deterministic_retry"
        if category == "transient" or configured_retry:
            return {"evidence_preserved", "job_retry"} if before_retry else {"evidence_preserved", "job_retry", "artifact_validation", "health_check"}
        mutation = "configuration_change" if category == "configuration" else "source_patch"
        required = {"evidence_preserved", mutation, "tests", "deployment"}
        if not before_retry:
            required |= {"job_retry", "artifact_validation", "health_check"}
        return required

    @staticmethod
    def _has_action(db: sqlite3.Connection, attempt_id: str, kind: str) -> bool:
        return db.execute(
            "SELECT 1 FROM recovery_actions WHERE attempt_id=? AND kind=? AND status='succeeded'", (attempt_id, kind),
        ).fetchone() is not None

    @staticmethod
    def _require_action_kinds(db: sqlite3.Connection, attempt_id: str, required: set[str]) -> None:
        present = {row[0] for row in db.execute(
            "SELECT kind FROM recovery_actions WHERE attempt_id=? AND status='succeeded'", (attempt_id,),
        ).fetchall()}
        missing = sorted(required - present)
        if missing:
            raise SafetyError("recovery verification is missing successful action evidence: " + ", ".join(missing))

    @staticmethod
    def _require_test_scopes(db: sqlite3.Connection, attempt_id: str) -> None:
        scopes = {
            json.loads(row[0]).get("scope")
            for row in db.execute(
                "SELECT evidence_json FROM recovery_actions WHERE attempt_id=? AND kind='tests' AND status='succeeded'",
                (attempt_id,),
            ).fetchall()
        }
        missing = {"targeted", "regression"} - scopes
        if missing:
            raise SafetyError("recovery verification is missing test scopes: " + ", ".join(sorted(missing)))

    def _validate_action(self, kind: str, status: str, evidence: dict[str, Any]) -> None:
        if status not in {"succeeded", "failed", "skipped"} or not isinstance(evidence, dict):
            raise ValueError("recovery action status or evidence is invalid")
        if kind == "source_patch" and status == "succeeded":
            files, digest = evidence.get("changed_files"), evidence.get("patch_sha256")
            if not isinstance(files, list) or not files or not all(isinstance(path, str) and path for path in files):
                raise ValueError("source patch evidence requires changed files")
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError("source patch evidence requires a SHA-256 patch identifier")
            if len(files) > self.bundle.recovery["max_changed_files"]:
                raise SafetyError("source patch changes too many files")
            allowed = [Path(value) for value in self.bundle.recovery["allowed_source_roots"]]
            protected = [Path(value) for value in self.bundle.recovery["protected_paths"]]
            for value in files:
                path = Path(value)
                if path.is_absolute() or ".." in path.parts or not any(path == root or root in path.parents for root in allowed):
                    raise SafetyError(f"source patch escapes allowed roots: {value}")
                if any(path == root or root in path.parents for root in protected):
                    raise SafetyError(f"source patch touches a protected path: {value}")
            self._verify_file_evidence(evidence, "patch", expected_sha=digest, max_bytes=self.bundle.recovery["max_patch_bytes"])
        elif kind == "configuration_change" and status == "succeeded":
            if not evidence.get("before_sha256") or not evidence.get("after_sha256") or evidence["before_sha256"] == evidence["after_sha256"]:
                raise ValueError("configuration evidence requires distinct before and after hashes")
        elif kind == "tests" and status == "succeeded":
            if evidence.get("scope") not in {"targeted", "regression"} or evidence.get("passed") is not True or evidence.get("exit_code") != 0 or not isinstance(evidence.get("command"), list):
                raise ValueError("successful test evidence requires an argv, zero exit code, and passed=true")
            self._verify_file_evidence(evidence, "transcript", max_bytes=4 * 1024 * 1024)
        elif kind == "deployment" and status == "succeeded":
            if not evidence.get("before_deployment_id") or not evidence.get("after_deployment_id") or evidence["before_deployment_id"] == evidence["after_deployment_id"] or evidence.get("active") is not True or not evidence.get("source_sha256") or not evidence.get("release_id"):
                raise ValueError("deployment evidence requires a distinct active replacement")
        elif kind == "job_retry" and status == "succeeded":
            if not evidence.get("job_id") or not evidence.get("input_sha256"):
                raise ValueError("job retry evidence requires immutable job and input identities")
        elif kind == "artifact_validation" and status == "succeeded":
            if not evidence.get("run_id") or not isinstance(evidence.get("artifact_ids"), list):
                raise ValueError("artifact validation evidence requires run and artifact identities")
        elif kind == "health_check" and status == "succeeded":
            if evidence.get("passed") is not True or not evidence.get("run_id"):
                raise ValueError("health-check evidence requires passed=true and a run identity")
        elif kind == "blocker" and not evidence.get("code"):
            raise ValueError("blocker evidence requires a machine-readable code")

    def _verify_file_evidence(
        self, evidence: dict[str, Any], prefix: str, *, expected_sha: str | None = None, max_bytes: int,
    ) -> None:
        uri, digest, byte_size = (
            evidence.get(f"{prefix}_uri"), evidence.get(f"{prefix}_sha256"), evidence.get(f"{prefix}_bytes"),
        )
        if not isinstance(uri, str) or not isinstance(digest, str) or len(digest) != 64 or not isinstance(byte_size, int):
            raise ValueError(f"{prefix} evidence requires URI, SHA-256, and byte size")
        path = Path(uri).resolve()
        state_root = Path(self.bundle.base["hub"]["state_root"]).resolve()
        if not path.is_file() or not (path == state_root or state_root in path.parents):
            raise SafetyError(f"{prefix} evidence is outside the Mission Hub state root")
        if byte_size < 0 or byte_size > max_bytes or path.stat().st_size != byte_size:
            raise SafetyError(f"{prefix} evidence byte size is invalid")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest or (expected_sha is not None and actual != expected_sha):
            raise SafetyError(f"{prefix} evidence hash mismatch")


class RepairDriver(Protocol):
    """Bounded mutation/deployment adapter supplied by the installed role."""

    def repair(self, context: dict[str, Any]) -> dict[str, Any]: ...


class RecoveryCoordinator:
    """Execute planned repairs, then hand immutable work back to the scheduler."""

    def __init__(self, store: MissionHubStore, bundle: ConfigBundle, driver: RepairDriver | None = None):
        self.store, self.bundle, self.driver = store, bundle, driver

    def tick(self, *, actor: str) -> int:
        changed = RecoveryManager(self.store, self.bundle).reconcile(actor=actor)
        if not self.bundle.recovery["enabled"] or self.driver is None:
            return changed
        with self.store._connect() as db:
            attempt_ids = [row[0] for row in db.execute(
                "SELECT id FROM recovery_attempts WHERE state='planned' ORDER BY started_at,id",
            ).fetchall()]
        for attempt_id in attempt_ids:
            self._execute(attempt_id, actor=actor)
            changed += 1
        return changed

    def _execute(self, attempt_id: str, *, actor: str) -> None:
        manager = RecoveryManager(self.store, self.bundle)
        context = self._context(attempt_id)
        manager.record_action(attempt_id, "evidence_preserved", "succeeded", {
            "failed_run_id": context["incident"]["failed_run_id"],
            "failure_code": context["incident"]["failure_code"],
            "failure_sha256": content_hash(context["failure"]),
        }, actor=actor)
        with self.store.transaction() as db:
            db.execute("UPDATE recovery_attempts SET state='applying' WHERE id=?", (attempt_id,))
        try:
            outcome = self.driver.repair(context)
            if not isinstance(outcome, dict) or not isinstance(outcome.get("actions"), list):
                raise ValueError("repair driver returned no structured action evidence")
            for action in outcome["actions"]:
                manager.record_action(
                    attempt_id, action["kind"], action["status"], action["evidence"], actor=actor,
                )
            if outcome.get("succeeded") is not True:
                manager.fail_attempt(
                    attempt_id, code=outcome.get("failure_code", "repair_driver_failed"),
                    summary=outcome.get("summary", "bounded repair driver failed"), actor=actor,
                )
                return
            self._verify_active_deployment(context, outcome)
            active = self.store.active_config()
            effective_bundle = self.bundle
            if active["sha256"] != self.bundle.sha256:
                effective_bundle = bundle_from_snapshot(self.bundle.root, active["payload"])
            self.store.retry_failed_job_after_repair(
                effective_bundle, context["job"]["id"], reason=outcome.get("summary", "verified bounded repair"),
                actor=actor, recovery_attempt_id=attempt_id,
            )
            manager = RecoveryManager(self.store, effective_bundle)
            manager.record_action(attempt_id, "job_retry", "succeeded", {
                "job_id": context["job"]["id"], "input_sha256": context["job"]["input_sha256"],
                "mode": "repaired_retry", "resulting_status": "queued",
            }, actor=actor)
            manager.mark_retrying(attempt_id, actor=actor)
            self.store.request_pipeline_state("running", actor=actor)
        except Exception as exc:
            latest = manager.get(context["incident"]["id"])
            if latest["state"] not in TERMINAL_STATES and latest["attempts"][-1]["state"] != "failed":
                manager.fail_attempt(
                    attempt_id, code="repair_execution_error", summary=f"{type(exc).__name__}: {exc}", actor=actor,
                )

    def _context(self, attempt_id: str) -> dict[str, Any]:
        with self.store._connect() as db:
            attempt = db.execute("SELECT * FROM recovery_attempts WHERE id=?", (attempt_id,)).fetchone()
            if attempt is None:
                raise NotFoundError(attempt_id)
            incident = db.execute("SELECT * FROM recovery_incidents WHERE id=?", (attempt["incident_id"],)).fetchone()
            job = db.execute("SELECT * FROM jobs WHERE id=?", (incident["job_id"],)).fetchone()
            run = db.execute("SELECT * FROM runs WHERE id=?", (incident["failed_run_id"],)).fetchone()
            deployment = db.execute("SELECT * FROM deployments WHERE id=?", (run["deployment_id"],)).fetchone()
        job_value = dict(job)
        job_value["original_requested_machine_id"] = job_value["requested_machine_id"]
        job_value["requested_machine_id"] = machine_id_for_role(
            self.bundle, self.bundle.jobs[job_value["job_type"]]["executor_role"],
        )
        return {
            "attempt": dict(attempt), "incident": dict(incident), "job": job_value, "run": dict(run),
            "failed_deployment": dict(deployment), "failure": json.loads(run["failure_json"] or "{}"),
            "input": json.loads(job["input_json"]), "recovery_policy": dict(self.bundle.recovery),
        }

    def _verify_active_deployment(self, context: dict[str, Any], outcome: dict[str, Any]) -> None:
        deployment_actions = [
            action for action in outcome["actions"]
            if action.get("kind") == "deployment" and action.get("status") == "succeeded"
        ]
        if len(deployment_actions) != 1:
            raise SafetyError("repair driver must provide exactly one successful deployment action")
        evidence = deployment_actions[0]["evidence"]
        active = self.store.active_deployment(context["job"]["requested_machine_id"])
        if (
            active["id"] != evidence["after_deployment_id"]
            or context["failed_deployment"]["id"] != evidence["before_deployment_id"]
            or active["id"] == context["failed_deployment"]["id"]
            or active["source_sha256"] != evidence["source_sha256"]
            or active["release_id"] != evidence["release_id"]
        ):
            raise SafetyError("repair deployment evidence does not match authoritative active deployment state")
