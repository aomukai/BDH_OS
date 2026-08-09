"""Durable train → cooldown → chat/MRI evaluation Cortex workflows."""

from __future__ import annotations

import json
from typing import Any

from .campaign_contract import campaign_contract_sha256, expected_evaluation_context, validate_campaign_contract
from .config import ConfigBundle, machine_id_for_role
from .errors import ConflictError, MissionHubError, NotFoundError, SafetyError, TransitionError
from .service import MissionHubService
from .store import MissionHubStore, strategic_available_at


TERMINAL_FAILURES = {"failed", "blocked", "cancelled"}
STRUCTURAL_FAILURES = {"dead_core_layers", "saturated_core_layers"}


class CortexWorkflowCoordinator:
    """Advance only an operator-authorized immutable branch recipe.

    Every derived training job is covered by the exact workflow authorization;
    the coordinator cannot change corpora, ordering, optimizer settings, parent
    lineage, evaluation suite, or campaign purpose.
    """

    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store = store
        self.bundle = bundle
        self.service = MissionHubService(store, bundle)

    def tick(self, *, actor: str) -> list[dict[str, str]]:
        changes: list[dict[str, str]] = []
        for workflow in self.store.active_cortex_workflows():
            try:
                change = self._advance(workflow, actor=actor)
                if change:
                    changes.append({"workflow_id": workflow["id"], **change})
            except (ConflictError, NotFoundError, SafetyError, TransitionError) as exc:
                self._terminate(
                    workflow, "blocked", actor=actor,
                    reason=f"{type(exc).__name__}: {exc}", stage="coordinator",
                )
                changes.append({"workflow_id": workflow["id"], "status": "blocked", "stage": "coordinator"})
            except MissionHubError:
                # A protocol/remote transport interruption can recover on the
                # next wake without changing the authorized workflow.
                continue
            except (KeyError, TypeError, ValueError) as exc:
                self._terminate(
                    workflow, "failed", actor=actor,
                    reason=f"deterministic coordinator error: {type(exc).__name__}: {exc}",
                    stage="coordinator",
                )
                changes.append({"workflow_id": workflow["id"], "status": "failed", "stage": "coordinator"})
        return changes

    def _advance(self, workflow: dict[str, Any], *, actor: str) -> dict[str, str] | None:
        with self.store._connect() as db:
            campaign = db.execute(
                "SELECT state FROM campaigns WHERE id=?", (workflow["campaign_id"],),
            ).fetchone()
        if campaign is None:
            raise NotFoundError(workflow["campaign_id"])
        if campaign["state"] != "active":
            return None
        if self.store.campaign_blocks(workflow["campaign_id"], active_only=True):
            return None
        jobs = {item["stage_key"]: item for item in workflow["jobs"]}
        for stage, job in jobs.items():
            if job["status"] in TERMINAL_FAILURES:
                self._terminate(
                    workflow, "failed", actor=actor, reason=f"{stage}:{job['status']}",
                    stage=stage,
                )
                return {"status": "failed", "stage": stage}

        specification = workflow["specification"]
        parent_id = specification["starting_checkpoint_artifact_id"]
        predecessor_finished: str | None = None
        for index, session in enumerate(specification["sessions"]):
            train_key, eval_key = f"s{index:02d}:train", f"s{index:02d}:evaluate"
            train_job = jobs.get(train_key)
            if train_job is None:
                return self._create_train(
                    workflow, index, session, parent_id, predecessor_finished,
                    actor=actor,
                )
            if train_job["status"] != "succeeded":
                return None
            train_result = self.store.workflow_job_artifacts(train_job["id"])
            checkpoint = self._one(train_result, "checkpoint")
            eval_job = jobs.get(eval_key)
            if eval_job is None:
                return self._create_evaluation(
                    workflow, index, checkpoint["id"], parent_id,
                    train_result[2], actor=actor,
                )
            if eval_job["status"] != "succeeded":
                return None
            eval_result = self.store.workflow_job_artifacts(eval_job["id"])
            evaluation = self._one(eval_result, "evaluation_report")
            local = self._ensure_local(evaluation["id"], actor)
            report = json.loads(open(local["uri"], encoding="utf-8").read())
            structural = sorted(STRUCTURAL_FAILURES & set(report["certificate"].get("failure_modes", [])))
            if structural:
                self._terminate(
                    workflow, "blocked", actor=actor,
                    reason="structural evaluation failure: " + ", ".join(structural),
                    stage=eval_key,
                )
                return {"status": "blocked", "stage": eval_key}
            parent_id = checkpoint["id"]
            predecessor_finished = eval_result[2]

        self.store.finish_cortex_workflow(
            workflow["id"], "succeeded", actor=actor,
            pause_pipeline=not specification["authorization"].get(
                "allow_pipeline_continue_after_completion", False,
            ),
        )
        return {"status": "succeeded", "stage": "complete"}

    def _terminate(
        self, workflow: dict[str, Any], status: str, *, actor: str,
        reason: str, stage: str,
    ) -> None:
        self.store.finish_cortex_workflow(
            workflow["id"], status, actor=actor, reason=reason,
        )
        try:
            from .lab import LabStore
            failed_job = next(
                (job for job in workflow.get("jobs", []) if job.get("stage_key") == stage),
                None,
            )
            queue_expired = False
            if failed_job is not None:
                with self.store._connect() as db:
                    queue_expired = db.execute(
                        """SELECT 1 FROM events WHERE entity_type='job' AND entity_id=?
                           AND event_type='job.queue_age_exceeded' LIMIT 1""",
                        (failed_job["id"],),
                    ).fetchone() is not None
            if queue_expired:
                explanation = [
                    "Short version: This evaluation never started. It waited in the queue too long and the safety timer stopped it.",
                    "Impact: The completed training checkpoint is safe. There is no failed model result, but this branch cannot continue until the unchanged evaluation is requeued.",
                    "Next step: Sol will verify the saved job and try to resume it under the current system configuration.",
                ]
            else:
                explanation = [
                    f"Short version: Work on this branch stopped at {stage}.",
                    "Impact: The branch will not continue automatically until Sol identifies a safe recovery.",
                ]
            LabStore(self.store).system_notice(
                f"Branch stopped · {workflow['specification']['branch_id']}",
                "\n".join((*explanation, "", "Technical details:",
                    f"Workflow: {workflow['id']}",
                    f"Campaign: {workflow['campaign_id']}",
                    f"Stage: {stage}",
                    *([f"Job: {failed_job['id']}"] if failed_job is not None else []),
                    f"Status: {status}",
                    f"Reason: {reason}",
                    *(["Queue condition: queue_age_exceeded"] if queue_expired else []),
                    "Safety note: No automatic promotion or branch ranking was performed.",
                )),
                actor="mission-hub:cortex-workflow",
            )
        except Exception:
            # Workflow state/event evidence is authoritative; a presentation
            # failure must not undo the terminal safety transition.
            pass

    def _create_train(
        self, workflow: dict[str, Any], index: int, session: dict[str, Any],
        parent_id: str, predecessor_finished: str | None, *, actor: str,
    ) -> dict[str, str]:
        campaign_id = workflow["campaign_id"]
        contract = self._campaign_contract(campaign_id)
        training_job_type = workflow["specification"].get("training_job_type", "model.train")
        parameters = dict(session["parameters"])
        fixture = self.bundle.training["observer_fixture"]
        requested = parameters.pop("gate_credit_diagnostics", None)
        required_observer = {
            "enabled": True,
            "log_every_n_steps": fixture["log_every_n_steps"],
            "max_sampled_steps": fixture["max_sampled_steps"],
        }
        if requested is not None and requested != required_observer:
            raise SafetyError("training cannot override or disable the required observer fixture")
        if training_job_type == "model.train":
            parameters["gate_credit_diagnostics"] = required_observer
            payload = {
            "architecture": workflow["specification"]["architecture"],
            "parent_artifact_id": parent_id,
            "corpus_artifact_id": session["corpus_artifact_id"],
            "order_validation_artifact_id": "art-0000000000000000",
            "training_session": {
                "id": session["id"],
                "campaign_contract_sha256": campaign_contract_sha256(contract),
                "training_mode": contract["mode"],
                "branch_id": workflow["specification"]["branch_id"],
                "identity_scope": workflow["specification"]["identity_scope"],
                "ordered_concepts": session["ordered_concepts"],
            },
            "parameters": parameters,
            }
        else:
            payload = {
                "input_artifact_ids": [
                    parent_id, session["visual_features_artifact_id"],
                    session["visual_experience_artifact_id"], "art-0000000000000000",
                ],
                "training_session": {
                    "id": session["id"],
                    "campaign_contract_sha256": campaign_contract_sha256(contract),
                    "training_mode": contract["mode"],
                    "branch_id": workflow["specification"]["branch_id"],
                    "identity_scope": workflow["specification"]["identity_scope"],
                    "ordered_concepts": session["ordered_concepts"],
                },
                "specification": {
                    "mode": workflow["specification"].get("multimodal_mode", "visual"),
                    "events": session["events"], "parameters": parameters,
                },
                "limits": {"max_exposures": len(session["events"]) * parameters["epochs"]},
            }
        certificate = self.service.certify_training_order(
            job_type=training_job_type, input_payload=payload,
            campaign_id=campaign_id, actor=actor,
        )
        if training_job_type == "model.train":
            payload["order_validation_artifact_id"] = certificate["artifact_id"]
            source_artifacts = [session["corpus_artifact_id"]]
        else:
            payload["input_artifact_ids"][-1] = certificate["artifact_id"]
            source_artifacts = [session["visual_features_artifact_id"], session["visual_experience_artifact_id"]]
        for artifact_id in (*source_artifacts, certificate["artifact_id"]):
            self._ensure_trainbox(artifact_id, actor)
        available_at = (
            strategic_available_at(predecessor_finished, self.bundle.orchestration["strategic_boundary_cooldown_seconds"])
            if predecessor_finished else None
        )
        key = f"s{index:02d}:train"
        job = self.store.create_job(
            self.bundle, job_type=training_job_type, input_payload=payload,
            idempotency_key=f"cortex-workflow:{workflow['id']}:{key}",
            created_by=workflow["authorized_by"], campaign_id=campaign_id,
            requested_machine_id=machine_id_for_role(self.bundle, "trainbox"), approved=True, available_at=available_at,
        )
        self.store.link_cortex_workflow_job(workflow["id"], key, job["id"], actor=actor)
        return {"status": job["status"], "stage": key, "job_id": job["id"]}

    def _create_evaluation(
        self, workflow: dict[str, Any], index: int, candidate_id: str,
        parent_id: str, finished_at: str | None, *, actor: str,
    ) -> dict[str, str]:
        specification = workflow["specification"]
        campaign_id = workflow["campaign_id"]
        contract = self._campaign_contract(campaign_id)
        context = self._evaluation_context(
            campaign_id, contract, specification["branch_id"],
            branch_complete=index == len(specification["sessions"]) - 1,
        )
        suite_id = specification["evaluation_suite_artifact_id"]
        self._ensure_trainbox(suite_id, actor)
        payload = {
            "candidate_artifact_id": candidate_id,
            "parent_artifact_id": parent_id,
            "suite_artifact_id": suite_id,
            "evaluation_context": context,
            "parameters": specification["evaluation_parameters"],
        }
        key = f"s{index:02d}:evaluate"
        available_at = (
            strategic_available_at(finished_at, self.bundle.orchestration["strategic_boundary_cooldown_seconds"])
            if finished_at else None
        )
        job = self.store.create_job(
            self.bundle, job_type="model.evaluate", input_payload=payload,
            idempotency_key=f"cortex-workflow:{workflow['id']}:{key}",
            created_by=workflow["authorized_by"], campaign_id=campaign_id,
            requested_machine_id=machine_id_for_role(self.bundle, "trainbox"), approved=True, available_at=available_at,
        )
        self.store.link_cortex_workflow_job(workflow["id"], key, job["id"], actor=actor)
        return {"status": job["status"], "stage": key, "job_id": job["id"]}

    def _campaign_contract(self, campaign_id: str) -> dict[str, Any]:
        with self.store._connect() as db:
            row = db.execute("SELECT metadata_json FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
        if row is None:
            raise NotFoundError(campaign_id)
        return validate_campaign_contract(json.loads(row[0]).get("campaign_contract"), self.bundle.campaign_modes)

    def _evaluation_context(
        self, campaign_id: str, contract: dict[str, Any], branch_id: str, *,
        branch_complete: bool,
    ) -> dict[str, Any]:
        with self.store._connect() as db:
            row = db.execute("SELECT metadata_json FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
            completed_rows = db.execute(
                "SELECT input_json FROM jobs WHERE campaign_id=? AND job_type='model.evaluate' AND status='succeeded'",
                (campaign_id,),
            ).fetchall()
        metadata = json.loads(row[0])
        completed = set((metadata.get("completed_branch_evidence") or {}).keys())
        for item in completed_rows:
            context = json.loads(item[0]).get("evaluation_context", {})
            if (
                context.get("campaign_contract_sha256") == campaign_contract_sha256(contract)
                and context.get("branch_complete") is True
                and isinstance(context.get("branch_id"), str)
            ):
                completed.add(context["branch_id"])
        all_complete = set(contract["branches"]) <= (
            completed | ({branch_id} if branch_complete else set())
        )
        return expected_evaluation_context(
            contract, self.bundle.campaign_modes, phase="evolutionary_branch",
            branch_id=branch_id, branch_complete=branch_complete,
            all_required_branches_complete=all_complete,
        )

    @staticmethod
    def _one(result: tuple[dict[str, Any], list[dict[str, Any]], str | None], kind: str) -> dict[str, Any]:
        selected = [item for item in result[1] if item["kind"] == kind]
        if len(selected) != 1:
            raise SafetyError(f"Cortex predecessor must produce exactly one {kind} artifact")
        return selected[0]

    def _ensure_trainbox(self, artifact_id: str, actor: str) -> dict[str, Any]:
        machine_id = machine_id_for_role(self.bundle, "trainbox")
        try:
            return self.store.artifact_at(artifact_id, machine_id=machine_id)
        except NotFoundError:
            return self.service.materialize_artifact(artifact_id, machine_id=machine_id, actor=actor)

    def _ensure_local(self, artifact_id: str, actor: str) -> dict[str, Any]:
        control_id = machine_id_for_role(self.bundle, "mission_hub")
        executor_id = machine_id_for_role(self.bundle, "trainbox")
        try:
            return self.store.artifact_at(artifact_id, machine_id=control_id)
        except NotFoundError:
            return self.service.retrieve_artifact(artifact_id, machine_id=executor_id, actor=actor)
