from __future__ import annotations

import argparse
import fcntl
import json
import os
import socket
import time
from pathlib import Path
from typing import Any

from .adversarial_review import AdversarialReviewPolicy
from .campaign_controller import CampaignController, CampaignError
from .emergency_recovery import EmergencyRecoveryPolicy
from .ledger import ControlLedger, LedgerError, TERMINAL_RECEIPT_STATUSES
from .provider_failover import ProviderMonitor, ProviderRouter, default_monitor
from .script_finalize import ScriptFinalizeError, finalize_msm_script
from .strategic_orchestrator import StrategicDecisionError, StrategicOrchestrator
from .transport import SshControlTransport
from training.pipeline.cortex.artifacts import (
    CampaignArtifactError,
    CortexCampaignPublisher,
)
from training.pipeline.cortex.development import DevelopmentStateStore


DEFAULT_REPO = Path("/home/aomukai/Ninereeds")
DEFAULT_CONTROL_ROOT = Path(
    "/home/aomukai/.local/state/ninereeds-orchestrator-control"
)


class SupervisorError(RuntimeError):
    pass


class OrchestratorSupervisor:
    """Restart-safe deterministic handoff supervisor; strategic decisions stay external."""

    def __init__(
        self,
        ledger: ControlLedger,
        transport: SshControlTransport,
        *,
        repo_root: Path = DEFAULT_REPO,
        supervisor_id: str | None = None,
        provider_monitor: ProviderMonitor | None = None,
        strategic_orchestrator: StrategicOrchestrator | None = None,
        campaign_controller: CampaignController | None = None,
        emergency_policy: EmergencyRecoveryPolicy | None = None,
        adversarial_policy: AdversarialReviewPolicy | None = None,
        development_state_path: Path | None = None,
    ) -> None:
        self.ledger = ledger
        self.transport = transport
        self.repo_root = repo_root.resolve()
        self.supervisor_id = supervisor_id or (
            f"orchestrator-supervisor:{socket.gethostname()}:{os.getpid()}"
        )
        self.lock_path = self.ledger.worker_dir / "orchestrator-supervisor.lock"
        self.provider_monitor = provider_monitor
        self.strategic_orchestrator = strategic_orchestrator
        self.campaign_controller = campaign_controller
        self.emergency_policy = emergency_policy
        self.adversarial_policy = adversarial_policy
        self.campaign_publisher = CortexCampaignPublisher(self.repo_root)
        self.development_store = DevelopmentStateStore(
            self.repo_root,
            reports_dir=self.ledger.reports_dir,
            state_path=(
                development_state_path
                if development_state_path is not None
                else self.ledger.root / "derived/cortex_development_state.json"
            ),
        )

    def run_once(self) -> dict[str, Any]:
        self.lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return {
                    "acquired": False,
                    "dispatched": 0,
                    "synced": 0,
                    "children_created": 0,
                    "campaign_actions": 0,
                    "errors": 0,
                    "error_details": [],
                    "emergency": None,
                    "adversarial_review": None,
                    "development_stage": None,
                }
            return self._run_locked()

    def _run_locked(self) -> dict[str, Any]:
        dispatched = synced = children = errors = 0
        error_details: list[dict[str, str]] = []
        self.development_store.reconcile()
        if self.provider_monitor is not None:
            try:
                self.provider_monitor.refresh()
            except (OSError, ValueError):
                try:
                    self.provider_monitor.refresh()
                except (OSError, ValueError) as exc:
                    errors += 1
                    error_details.append(
                        {
                            "plan_id": "provider-monitor",
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:1000],
                        }
                    )
        for plan_path in sorted(self.ledger.plans_dir.glob("*.json")):
            plan_id = plan_path.stem
            try:
                delta = self._process_plan_once(plan_id)
            except (
                LedgerError,
                SupervisorError,
                ScriptFinalizeError,
                StrategicDecisionError,
                CampaignError,
                CampaignArtifactError,
                OSError,
            ) as first_exc:
                # One immediate, silent, idempotent recovery attempt. Only a repeated
                # failure becomes an emergency incident.
                try:
                    delta = self._process_plan_once(plan_id)
                except (
                    LedgerError,
                    SupervisorError,
                    ScriptFinalizeError,
                    StrategicDecisionError,
                    CampaignError,
                    CampaignArtifactError,
                    OSError,
                ) as exc:
                    errors += 1
                    error_details.append(
                        {
                            "plan_id": plan_id,
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:1000],
                        }
                    )
                    continue
                if (
                    self.campaign_controller is not None
                    and self.campaign_controller.store.derivation_failure(plan_id)
                    is not None
                ):
                    errors += 1
                    error_details.append(
                        {
                            "plan_id": plan_id,
                            "error_type": type(first_exc).__name__,
                            "error": str(first_exc)[:1000],
                        }
                    )
            dispatched += delta[0]
            synced += delta[1]
            children += delta[2]
        adversarial_result = None
        if (
            self.adversarial_policy is not None
            and self.campaign_controller is not None
        ):
            adversarial_result = self.adversarial_policy.maybe_review(
                self.campaign_controller
            )
        campaign_actions = 0
        campaign_result = None
        if self.campaign_controller is not None:
            try:
                campaign_result = self.campaign_controller.reconcile()
            except (
                CampaignError,
                CampaignArtifactError,
                LedgerError,
                OSError,
            ):
                try:
                    campaign_result = self.campaign_controller.reconcile()
                except (
                    CampaignError,
                    CampaignArtifactError,
                    LedgerError,
                    OSError,
                ) as exc:
                    errors += 1
                    error_details.append(
                        {
                            "plan_id": "campaign",
                            "error_type": type(exc).__name__,
                            "error": str(exc)[:1000],
                        }
                    )
            if isinstance(campaign_result, dict):
                completed_campaign = campaign_result.get("completed_campaign_state")
                if isinstance(completed_campaign, dict):
                    self.campaign_publisher.finalize(completed_campaign)
                if campaign_result.get("action") not in {
                    None,
                    "none",
                    "waiting_for_plan",
                }:
                    campaign_actions = 1
                state = self.campaign_controller.store.read()
                if state is not None and state["status"] != "running":
                    self.campaign_publisher.finalize(state)
                if campaign_result.get("action") in {
                    "created_strategic_provider_retry",
                    "created_strategic_context_repair",
                }:
                    unresolved = [
                        item
                        for item in error_details
                        if not item.get("plan_id", "").startswith("plan-campaign-")
                    ]
                    errors -= len(error_details) - len(unresolved)
                    error_details = unresolved
        emergency_result = None
        campaign_state = (
            self.campaign_controller.store.read()
            if self.campaign_controller is not None
            else None
        )
        if self.emergency_policy is not None and (
            error_details
            or (
                isinstance(campaign_result, dict)
                and campaign_result.get("action") == "budget_review_required"
            )
            or (
                isinstance(campaign_state, dict)
                and campaign_state.get("status") == "blocked"
            )
        ):
            incident = self._incident_snapshot(error_details, campaign_state)
            if (
                isinstance(campaign_result, dict)
                and campaign_result.get("action") == "budget_review_required"
            ):
                incident["incident_type"] = "campaign_budget"
                incident["budget_review"] = campaign_result
            emergency_result = self.emergency_policy.handle(
                incident,
                campaign_controller=self.campaign_controller,
            )
        development_state = self.development_store.reconcile()
        return {
            "acquired": True,
            "dispatched": dispatched,
            "synced": synced,
            "children_created": children,
            "campaign_actions": campaign_actions,
            "errors": errors,
            "error_details": error_details[:20],
            "emergency": emergency_result,
            "adversarial_review": adversarial_result,
            "development_stage": development_state["stage"],
        }

    def _process_plan_once(self, plan_id: str) -> tuple[int, int, int]:
        dispatched = synced = children = 0
        plan = self.ledger.plan(plan_id)
        if plan is None:
            raise SupervisorError(f"missing local plan: {plan_id}")
        if plan["kind"] == "strategic_decision":
            if self.strategic_orchestrator is None:
                raise SupervisorError(
                    "strategic plan exists but no strategic orchestrator is configured"
                )
            before = self.ledger.receipt(plan_id)
            executed = self.strategic_orchestrator.execute(plan)
            if executed:
                synced += 1
            updated = self.ledger.receipt(plan_id)
            current_campaign_plan = False
            if self.campaign_controller is not None:
                campaign_state = self.campaign_controller.store.read()
                current_campaign_plan = bool(
                    isinstance(campaign_state, dict)
                    and campaign_state.get("current_plan_id") == plan_id
                )
            changed_now = bool(
                executed
                and updated is not None
                and (
                    before is None
                    or updated.get("updated_at") != before.get("updated_at")
                )
            )
            if (
                updated is not None
                and updated.get("status") in {"retry_wait", "blocked", "dead_letter"}
                and (changed_now or current_campaign_plan)
            ):
                raise StrategicDecisionError(
                    str(updated.get("last_error") or updated.get("status"))
                )
            if self._create_child_with_failure_record(plan_id):
                children += 1
            return dispatched, synced, children
        receipt = self.ledger.receipt(plan_id)
        if receipt is None:
            raise SupervisorError(f"missing local receipt: {plan_id}")
        if receipt["status"] == "queued":
            if plan["kind"] == "cortex_corpus_chunk":
                self.transport.dispatch(plan_id, wake=False)
            else:
                self.transport.dispatch(plan_id)
            dispatched += 1
            response = self.transport.sync(plan_id)
            if response.get("report") is not None:
                synced += 1
        elif receipt["status"] not in TERMINAL_RECEIPT_STATUSES:
            response = self.transport.sync(plan_id)
            if response.get("report") is not None:
                synced += 1
        self._publish_evaluation_if_ready(plan_id)
        if self._create_child_with_failure_record(plan_id):
            children += 1
        return dispatched, synced, children

    def _incident_snapshot(
        self,
        errors: list[dict[str, str]],
        campaign_state: dict[str, Any] | None,
    ) -> dict[str, Any]:
        campaign = None
        current = None
        if isinstance(campaign_state, dict):
            campaign = {
                key: campaign_state.get(key)
                for key in (
                    "campaign_id",
                    "status",
                    "stop_reason",
                    "current_plan_id",
                    "boundary_index",
                    "deadline_at",
                    "usage",
                    "budgets",
                )
            }
            plan_id = campaign_state.get("current_plan_id")
            if isinstance(plan_id, str):
                current = {
                    "plan": self.ledger.plan(plan_id),
                    "receipt": self.ledger.receipt(plan_id),
                    "report": self.ledger.report(plan_id),
                }
        return {
            "schema_version": "ninereeds_orchestrator_incident_v1",
            "errors": errors[:20],
            "campaign": campaign,
            "current": current,
        }

    def _publish_evaluation_if_ready(self, plan_id: str) -> bool:
        if self.campaign_controller is None:
            return False
        plan = self.ledger.plan(plan_id)
        report = self.ledger.report(plan_id)
        receipt = self.ledger.receipt(plan_id)
        if (
            plan is None
            or plan["kind"] != "cortex_evaluation"
            or report is None
            or receipt is None
            or receipt["status"] != "completed"
        ):
            return False
        result = report.get("result")
        evaluation = result.get("evaluation") if isinstance(result, dict) else None
        if not isinstance(evaluation, dict):
            raise SupervisorError("Cortex evaluation report lacks evaluation data")
        state = self.campaign_controller.store.read()
        if state is None:
            return False
        if evaluation.get("campaign_id") != state.get("campaign_id"):
            if plan_id == state.get("seed_plan_id"):
                return False
            if plan_id == state.get("current_plan_id"):
                raise SupervisorError(
                    "active Cortex evaluation campaign does not match active state"
                )
            return False
        published = self.campaign_publisher.publish_evaluation(
            campaign_state=state,
            source_plan_id=plan_id,
            evaluation=evaluation,
        )
        return bool(published["changed"])

    def _create_child_with_failure_record(self, plan_id: str) -> bool:
        if (
            self.campaign_controller is not None
            and self.campaign_controller.store.derivation_failure(plan_id) is not None
        ):
            return False
        try:
            return self._create_child_if_ready(plan_id)
        except (
            LedgerError,
            SupervisorError,
            ScriptFinalizeError,
            StrategicDecisionError,
            OSError,
        ) as exc:
            receipt = self.ledger.receipt(plan_id)
            if (
                self.campaign_controller is not None
                and receipt is not None
                and receipt["status"] in TERMINAL_RECEIPT_STATUSES
            ):
                self.campaign_controller.store.record_derivation_failure(plan_id, exc)
            raise

    def _create_child_if_ready(self, plan_id: str) -> bool:
        plan = self.ledger.plan(plan_id)
        receipt = self.ledger.receipt(plan_id)
        report = self.ledger.report(plan_id)
        if (
            plan is None
            or receipt is None
            or report is None
            or receipt["status"] != "completed"
        ):
            return False
        if plan["kind"] == "strategic_decision":
            if self.strategic_orchestrator is None:
                raise SupervisorError("strategic orchestrator is not configured")
            created = self.strategic_orchestrator.materialize_child(plan, report)
            if created:
                child_id = f"plan-strategy-{plan['payload']['boundary_id']}"
                self.transport.dispatch(child_id)
            return created
        if plan["kind"] == "executor_job":
            workflow = plan["payload"].get("workflow")
            if not isinstance(workflow, dict):
                return False
            if workflow.get("type") == "msm_trainer":
                return self._create_trainer_child(plan, report, workflow)
            if workflow.get("type") == "cortex_train":
                return self._create_cortex_child(plan, report, workflow)
            if workflow.get("type") == "cortex_curriculum":
                return self._create_chunked_cortex_child(plan, report, workflow)
            if workflow.get("type") == "msm_grade":
                return self._create_autonext_child(plan, report, workflow)
            return False
        if plan["kind"] == "trainer_session":
            return self._create_grade_child(plan, report)
        if plan["kind"] == "phase_block":
            return self._create_phase_block_child(plan, report)
        if plan["kind"] == "cortex_block":
            return self._create_cortex_evaluation_child(plan, report)
        return False

    def _create_cortex_evaluation_child(
        self,
        plan: dict[str, Any],
        report: dict[str, Any],
    ) -> bool:
        if plan["mode"] != "live":
            return False
        result = report.get("result")
        if not isinstance(result, dict) or result.get("status") != "completed":
            return False
        candidate = result.get("checkpoint_after")
        runner_args = plan["payload"].get("runner_args")
        if not isinstance(candidate, str) or not isinstance(runner_args, list):
            raise SupervisorError("completed Cortex block lacks evaluation lineage")
        try:
            parent_index = runner_args.index("--parent")
            parent = runner_args[parent_index + 1]
        except (ValueError, IndexError) as exc:
            raise SupervisorError("Cortex block has no unambiguous parent") from exc
        if not isinstance(parent, str) or parent == "scratch":
            # Bootstrap commissioning is evaluated separately once a stable
            # checkpoint exists; a candidate comparison requires a file parent.
            return False
        metadata = result.get("metadata")
        source = metadata.get("training_source") if isinstance(metadata, dict) else None
        concept = source.get("concept") if isinstance(source, dict) else None
        campaign_id = "unassigned"
        development_stage = self.development_store.reconcile()["stage"]
        if self.campaign_controller is not None:
            state = self.campaign_controller.store.read()
            if state is not None:
                if state.get("current_plan_id") != plan["plan_id"]:
                    return False
                campaign_id = str(state["campaign_id"])
                if state.get("regime") == "play":
                    development_stage = "play"
        session = Path(candidate).stem
        child_id = f"plan-eval-{session}"
        if self.ledger.plan(child_id) is not None:
            return False
        child = self.ledger.create_plan(
            kind="cortex_evaluation",
            mode="live",
            payload={
                "campaign_id": campaign_id,
                "candidate_checkpoint": candidate,
                "parent_checkpoint": parent,
                "target_concept": concept,
                "suite_path": "training/pipeline/cortex/eval_suite_v1.json",
                "output_path": f"core/cortex/evaluations/{session}.json",
                "development_stage": development_stage,
            },
            created_by=self.supervisor_id,
            parent_plan_id=plan["plan_id"],
            plan_id=child_id,
            authorization={
                "allow_weight_updates": False,
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": False,
            },
            max_attempts=2,
        )
        self.transport.dispatch(child["plan_id"])
        return True

    def _create_chunked_cortex_child(
        self,
        plan: dict[str, Any],
        report: dict[str, Any],
        workflow: dict[str, Any],
    ) -> bool:
        expected = {
            "type",
            "session_id",
            "parent_checkpoint",
            "output_checkpoint",
            "runner_args",
            "artifact_root",
            "target_examples",
            "chunk_examples",
            "concept",
        }
        if set(workflow) != expected:
            raise SupervisorError("cortex_curriculum workflow fields do not match v1")
        result = report.get("result")
        if (
            not isinstance(result, dict)
            or not result.get("valid")
            or result.get("workflow") != "cortex_curriculum"
            or result.get("session_id") != workflow["session_id"]
            or result.get("concept") != workflow["concept"]
            or result.get("examples") != workflow["target_examples"]
        ):
            raise SupervisorError("executor curriculum report is incomplete")
        paths = result.get("jsonl_paths")
        curriculum_sha256 = result.get("curriculum_sha256")
        if (
            not isinstance(paths, list)
            or not paths
            or not all(isinstance(value, str) and value for value in paths)
            or not isinstance(curriculum_sha256, str)
            or len(curriculum_sha256) != 64
        ):
            raise SupervisorError("executor curriculum report lacks durable artifacts")
        parent = workflow["parent_checkpoint"]
        output = workflow["output_checkpoint"]
        runner_args = workflow["runner_args"]
        if (
            not isinstance(parent, str)
            or not parent
            or not isinstance(output, str)
            or not output
            or not isinstance(runner_args, list)
            or not all(isinstance(value, str) for value in runner_args)
            or "--parent" in runner_args
        ):
            raise SupervisorError("cortex_curriculum training lineage is invalid")
        child_id = f"plan-cortex-{workflow['session_id']}"
        if self.ledger.plan(child_id) is not None:
            return False
        if plan["mode"] == "live" and not plan["authorization"]["allow_weight_updates"]:
            raise SupervisorError("live Cortex workflow lacks weight-update authority")
        child = self.ledger.create_plan(
            kind="cortex_block",
            mode=plan["mode"],
            payload={
                "jsonl_paths": paths,
                "curriculum_id": workflow["session_id"],
                "curriculum_sha256": curriculum_sha256,
                "concept": workflow["concept"],
                "output_checkpoint": output,
                "runner_args": ["--parent", parent, *runner_args],
            },
            created_by=self.supervisor_id,
            parent_plan_id=plan["plan_id"],
            plan_id=child_id,
            authorization={
                "allow_weight_updates": (
                    plan["mode"] == "live"
                    and plan["authorization"]["allow_weight_updates"]
                ),
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": False,
            },
        )
        self.transport.dispatch(child["plan_id"])
        return True

    def _create_cortex_child(
        self,
        plan: dict[str, Any],
        report: dict[str, Any],
        workflow: dict[str, Any],
    ) -> bool:
        expected = {
            "type",
            "session_id",
            "parent_checkpoint",
            "output_checkpoint",
            "runner_args",
            "artifact_path",
        }
        if set(workflow) != expected:
            raise SupervisorError("cortex_train workflow fields do not match v1")
        session_id = workflow["session_id"]
        if not isinstance(session_id, str) or not session_id:
            raise SupervisorError("cortex_train session_id is invalid")
        parent = workflow["parent_checkpoint"]
        if not isinstance(parent, str) or not parent:
            raise SupervisorError("cortex_train parent checkpoint is invalid")
        output = workflow["output_checkpoint"]
        if not isinstance(output, str) or not output:
            raise SupervisorError("cortex_train output checkpoint is invalid")
        runner_args = workflow["runner_args"]
        if (
            not isinstance(runner_args, list)
            or not all(isinstance(value, str) for value in runner_args)
            or "--parent" in runner_args
        ):
            raise SupervisorError("cortex_train runner_args are invalid")
        result = report["result"]
        if not result.get("valid"):
            raise SupervisorError("executor report is not valid")
        proposal = result.get("proposal")
        if not isinstance(proposal, dict):
            raise SupervisorError("executor report has no proposal")
        current_campaign_plan = False
        if self.campaign_controller is not None:
            campaign_state = self.campaign_controller.store.read()
            current_campaign_plan = bool(
                isinstance(campaign_state, dict)
                and campaign_state.get("current_plan_id") == plan["plan_id"]
            )
        if (
            current_campaign_plan
            and proposal.get("status") not in {None, "READY"}
        ):
            raise SupervisorError(
                "executor proposal is not READY and cannot commission training"
            )
        artifacts = {
            artifact.get("path"): artifact.get("content")
            for artifact in proposal.get("artifacts") or []
            if isinstance(artifact, dict)
        }
        content = artifacts.get(workflow["artifact_path"])
        if not isinstance(content, str):
            raise SupervisorError("executor proposal lacks the Cortex script artifact")
        try:
            proposed_script = json.loads(content)
        except json.JSONDecodeError as exc:
            raise SupervisorError("executor Cortex script is invalid JSON") from exc
        script = finalize_msm_script(
            proposed_script,
            repo_root=self.repo_root,
            orchestrator_plan_id=plan["plan_id"],
            session_id=session_id,
            checkpoint=parent,
            executor_id=result["model_id"],
        )
        if current_campaign_plan:
            context_files = plan.get("payload", {}).get("task", {}).get(
                "context_files", []
            )
            prepared = [
                relative
                for relative in context_files
                if isinstance(relative, str)
                and relative.startswith(
                    "training/pipeline/cortex/allowlist_waves/"
                )
                and relative.endswith(".jsonl")
            ]
            if len(prepared) == 1:
                source = (self.repo_root / prepared[0]).resolve()
                if self.repo_root not in source.parents or not source.is_file():
                    raise SupervisorError("prepared Cortex block is unavailable")
                expected_examples = sum(
                    1
                    for line in source.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
                if len(script["items"]) != expected_examples:
                    raise SupervisorError(
                        "executor Cortex script is incomplete for the prepared block: "
                        f"expected {expected_examples}, received {len(script['items'])}"
                    )
        child_id = f"plan-cortex-{session_id}"
        if self.ledger.plan(child_id) is not None:
            return False
        if plan["mode"] == "live" and not plan["authorization"]["allow_weight_updates"]:
            raise SupervisorError("live Cortex workflow lacks weight-update authority")
        child = self.ledger.create_plan(
            kind="cortex_block",
            mode=plan["mode"],
            payload={
                "script": script,
                "output_checkpoint": output,
                "runner_args": ["--parent", parent, *runner_args],
            },
            created_by=self.supervisor_id,
            parent_plan_id=plan["plan_id"],
            plan_id=child_id,
            authorization={
                "allow_weight_updates": (
                    plan["mode"] == "live"
                    and plan["authorization"]["allow_weight_updates"]
                ),
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": False,
            },
        )
        self.transport.dispatch(child["plan_id"])
        return True

    def _create_phase_block_child(
        self,
        plan: dict[str, Any],
        report: dict[str, Any],
    ) -> bool:
        result = report["result"]
        if result.get("local_recommendation") != "run_next_block_same_phase":
            return False
        if not plan["authorization"]["allow_auto_advance"]:
            return False
        continuation = plan["payload"].get("continuation")
        if (
            not isinstance(continuation, dict)
            or set(continuation) != {"remaining_blocks"}
        ):
            raise SupervisorError("phase continuation fields do not match v1")
        remaining = continuation["remaining_blocks"]
        if (
            isinstance(remaining, bool)
            or not isinstance(remaining, int)
            or not 0 <= remaining <= 10
        ):
            raise SupervisorError("remaining_blocks must be from 0 through 10")
        if remaining == 0:
            return False
        checkpoint = result.get("checkpoint_after")
        phase_id = result.get("phase_id")
        block_id = result.get("block_id")
        if not all(isinstance(value, str) and value for value in (checkpoint, phase_id, block_id)):
            raise SupervisorError("phase report lacks continuation identity")
        child_id = f"plan-auto-{block_id}"
        if self.ledger.plan(child_id) is not None:
            return False
        runner_args = list(plan["payload"].get("runner_args") or [])
        self._replace_option(runner_args, "--parent", checkpoint)
        child = self.ledger.create_plan(
            kind="phase_block",
            mode=plan["mode"],
            payload={
                "phase_id": phase_id,
                "runner_args": runner_args,
                "continuation": {"remaining_blocks": remaining - 1},
            },
            created_by=self.supervisor_id,
            parent_plan_id=plan["plan_id"],
            plan_id=child_id,
            authorization={
                "allow_weight_updates": True,
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": remaining - 1 > 0,
            },
        )
        self.transport.dispatch(child["plan_id"])
        return True

    @staticmethod
    def _replace_option(values: list[str], option: str, replacement: str) -> None:
        if option in values:
            index = values.index(option)
            if index + 1 >= len(values):
                raise SupervisorError(f"{option} has no value")
            values[index + 1] = replacement
        else:
            values.extend([option, replacement])

    def _create_trainer_child(
        self,
        plan: dict[str, Any],
        report: dict[str, Any],
        workflow: dict[str, Any],
    ) -> bool:
        workflow = plan["payload"].get("workflow")
        expected = {
            "type",
            "session_id",
            "checkpoint",
            "trainer_mode",
            "inference",
            "artifact_path",
        }
        if frozenset(workflow) not in {
            frozenset(expected),
            frozenset(expected | {"continuation"}),
            frozenset(expected | {"continuation", "shadow_transcript"}),
        }:
            raise SupervisorError("msm_trainer workflow fields do not match v1")
        child_id = f"plan-trainer-{workflow['session_id']}"
        existing = self.ledger.plan(child_id)
        if existing is not None:
            return False
        result = report["result"]
        if not result.get("valid"):
            raise SupervisorError("executor report is not valid")
        proposal = result.get("proposal")
        if not isinstance(proposal, dict):
            raise SupervisorError("executor report has no proposal")
        artifacts = {
            artifact.get("path"): artifact.get("content")
            for artifact in proposal.get("artifacts") or []
            if isinstance(artifact, dict)
        }
        content = artifacts.get(workflow["artifact_path"])
        if not isinstance(content, str):
            raise SupervisorError("executor proposal lacks the workflow artifact")
        try:
            proposed_script = json.loads(content)
        except json.JSONDecodeError as exc:
            raise SupervisorError("executor script artifact is invalid JSON") from exc
        script = finalize_msm_script(
            proposed_script,
            repo_root=self.repo_root,
            orchestrator_plan_id=plan["plan_id"],
            session_id=workflow["session_id"],
            checkpoint=workflow["checkpoint"],
            executor_id=result["model_id"],
        )
        child = self.ledger.create_plan(
            kind="trainer_session",
            mode=workflow["trainer_mode"],
            payload={
                "script": script,
                "checkpoint_path": (
                    None
                    if workflow["trainer_mode"] == "shadow"
                    else workflow["checkpoint"]
                ),
                "inference": workflow["inference"],
                "continuation": self._validate_continuation(
                    workflow.get("continuation")
                ),
                **(
                    {"shadow_transcript": workflow["shadow_transcript"]}
                    if "shadow_transcript" in workflow
                    else {}
                ),
            },
            created_by=self.supervisor_id,
            parent_plan_id=plan["plan_id"],
            plan_id=child_id,
            authorization={
                "allow_weight_updates": False,
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": plan["authorization"]["allow_auto_advance"],
            },
        )
        self.transport.dispatch(child["plan_id"])
        return True

    def _create_grade_child(
        self,
        plan: dict[str, Any],
        report: dict[str, Any],
    ) -> bool:
        result = report["result"]
        if result.get("status") not in {"completed", "simulated"}:
            return False
        artifacts = result.get("artifacts")
        if not isinstance(artifacts, dict):
            raise SupervisorError("trainer result lacks artifact paths")
        script_path = artifacts.get("script")
        raw_log_path = artifacts.get("raw_log")
        if not isinstance(script_path, str) or not isinstance(raw_log_path, str):
            raise SupervisorError("completed trainer result lacks script or raw log")
        session_id = result.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise SupervisorError("trainer result lacks session_id")
        continuation = self._validate_continuation(
            plan["payload"].get("continuation")
        )
        grade_path = (
            f"training/pipeline/msm/sessions/{session_id}/grading_result.json"
        )
        child_id = f"plan-grade-{session_id}"
        if self.ledger.plan(child_id) is not None:
            return False
        task = {
            "job_id": f"msm-grade-{session_id}",
            "title": f"Grade fixed MSM session {session_id}",
            "instructions": (
                "Read the fixed trainer script and immutable raw log. Grade every script "
                "item exactly once and in script order. Judge semantic correctness against "
                "the script expectations; flag off-topic, malformed, repetitive, and "
                "uncertain answers conservatively. Propose exactly the requested grading "
                "JSON artifact. PASS_AUTONEXT is allowed only when at least one answer is "
                "correct, none are off-topic or ungradable, no malformed/repetition flag "
                "is set, every confidence is at least 0.70, and no orchestrator review is "
                "needed. Do not propose training data or filesystem actions."
            ),
            "context_files": [
                script_path,
                raw_log_path,
                "training/pipeline/grading_result_schema.json",
            ],
            "allowed_artifact_paths": [grade_path],
            "artifact_json_schemas": {
                grade_path: "training/pipeline/grading_result_schema.json"
            },
            "allowed_actions": ["VALIDATE_JSON", "RETURN_VALIDATION_ERRORS"],
            "max_tokens": 8192,
        }
        child = self.ledger.create_plan(
            kind="executor_job",
            mode=plan["mode"],
            payload={
                "task": task,
                "model_id": None,
                "required_context_tokens": 0,
                "max_model_attempts": 2,
                "workflow": {
                    "type": "msm_grade",
                    "session_id": session_id,
                    "script_path": script_path,
                    "raw_log_path": raw_log_path,
                    "artifact_path": grade_path,
                    "continuation": continuation,
                },
            },
            created_by=self.supervisor_id,
            parent_plan_id=plan["plan_id"],
            plan_id=child_id,
            authorization={
                "allow_weight_updates": False,
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": plan["authorization"]["allow_auto_advance"],
            },
        )
        self.transport.dispatch(child["plan_id"])
        return True

    def _create_autonext_child(
        self,
        plan: dict[str, Any],
        report: dict[str, Any],
        workflow: dict[str, Any],
    ) -> bool:
        grade = report["result"].get("grade")
        if not isinstance(grade, dict) or grade.get("decision") != "PASS_AUTONEXT":
            return False
        if not plan["authorization"]["allow_auto_advance"]:
            return False
        continuation = self._validate_continuation(workflow.get("continuation"))
        remaining = continuation["remaining_auto_sessions"]
        payload = continuation["next_executor_payload"]
        if remaining <= 0 or payload is None:
            return False
        if not isinstance(payload, dict):
            raise SupervisorError("next executor payload must be an object")
        next_payload = json.loads(json.dumps(payload))
        next_workflow = next_payload.get("workflow")
        if not isinstance(next_workflow, dict) or next_workflow.get("type") != "msm_trainer":
            raise SupervisorError("auto-next payload must contain an msm_trainer workflow")
        next_session = next_workflow.get("session_id")
        if not isinstance(next_session, str) or not next_session:
            raise SupervisorError("auto-next workflow lacks a session_id")
        nested = self._validate_continuation(next_workflow.get("continuation"))
        nested["remaining_auto_sessions"] = remaining - 1
        next_workflow["continuation"] = nested
        child_id = f"plan-executor-{next_session}"
        if self.ledger.plan(child_id) is not None:
            return False
        child = self.ledger.create_plan(
            kind="executor_job",
            mode=plan["mode"],
            payload=next_payload,
            created_by=self.supervisor_id,
            parent_plan_id=plan["plan_id"],
            plan_id=child_id,
            authorization={
                "allow_weight_updates": False,
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": remaining - 1 > 0,
            },
        )
        self.transport.dispatch(child["plan_id"])
        return True

    @staticmethod
    def _validate_continuation(value: Any) -> dict[str, Any]:
        if value is None:
            return {"remaining_auto_sessions": 0, "next_executor_payload": None}
        if not isinstance(value, dict) or set(value) != {
            "remaining_auto_sessions",
            "next_executor_payload",
        }:
            raise SupervisorError("continuation fields do not match v1")
        remaining = value["remaining_auto_sessions"]
        if (
            isinstance(remaining, bool)
            or not isinstance(remaining, int)
            or not 0 <= remaining <= 10
        ):
            raise SupervisorError("remaining_auto_sessions must be from 0 through 10")
        payload = value["next_executor_payload"]
        if payload is not None and not isinstance(payload, dict):
            raise SupervisorError("next_executor_payload must be an object or null")
        return {
            "remaining_auto_sessions": remaining,
            "next_executor_payload": payload,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile Ninereeds orchestration boundaries.")
    parser.add_argument("--control-root", type=Path, default=DEFAULT_CONTROL_ROOT)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument(
        "--ssh-target",
        default=os.environ.get(
            "NINEREEDS_TRAINBOX_CONTROL_TARGET",
            "ninereeds-trainbox-control",
        ),
    )
    args = parser.parse_args()
    ledger = ControlLedger(args.control_root)
    provider_monitor = default_monitor(args.control_root, args.repo)
    router = ProviderRouter(
        provider_monitor,
        repo_root=args.repo,
        codex_executable=os.environ.get(
            "NINEREEDS_CODEX_EXECUTABLE",
            "/home/aomukai/.local/bin/codex",
        ),
        fugu_executable=os.environ.get(
            "NINEREEDS_FUGU_EXECUTABLE",
            "/home/aomukai/.local/bin/codex-fugu",
        ),
        codex_model=os.environ.get("NINEREEDS_CODEX_MODEL", "gpt-5.6-sol"),
        strategic_provider=os.environ.get(
            "NINEREEDS_STRATEGIC_PROVIDER",
            "openrouter",
        ),
        openrouter_model=os.environ.get(
            "NINEREEDS_OPENROUTER_STRATEGIC_MODEL",
            "deepseek/deepseek-v4-flash-0731",
        ),
        openrouter_max_tokens=int(
            os.environ.get("NINEREEDS_OPENROUTER_STRATEGIC_MAX_TOKENS", "8192")
        ),
        timeout_seconds=int(
            os.environ.get("NINEREEDS_STRATEGIC_TIMEOUT_SECONDS", "1200")
        ),
    )
    strategic = StrategicOrchestrator(
        ledger,
        router,
        repo_root=args.repo,
    )
    campaign = CampaignController(
        ledger,
        repo_root=args.repo,
    )
    emergency = EmergencyRecoveryPolicy(
        args.control_root,
        repo_root=args.repo,
        codex_executable=os.environ.get(
            "NINEREEDS_CODEX_EXECUTABLE",
            "/home/aomukai/.local/bin/codex",
        ),
        codex_model=os.environ.get(
            "NINEREEDS_EMERGENCY_SOL_MODEL",
            "gpt-5.6-sol",
        ),
        openrouter_model=os.environ.get(
            "NINEREEDS_OPENROUTER_SOL_MODEL",
            "openai/gpt-5.6-sol",
        ),
        timeout_seconds=int(
            os.environ.get("NINEREEDS_EMERGENCY_SOL_TIMEOUT_SECONDS", "1200")
        ),
    )
    adversarial = AdversarialReviewPolicy(
        args.control_root,
        repo_root=args.repo,
        router=router,
        sol_policy=emergency,
        mutation_interval=int(
            os.environ.get("NINEREEDS_ADVERSARIAL_REVIEW_INTERVAL", "5")
        ),
    )
    supervisor = OrchestratorSupervisor(
        ledger,
        SshControlTransport(ledger, ssh_target=args.ssh_target),
        repo_root=args.repo,
        provider_monitor=provider_monitor,
        strategic_orchestrator=strategic,
        campaign_controller=campaign,
        emergency_policy=emergency,
        adversarial_policy=adversarial,
        development_state_path=(
            args.repo / "training/logs/cortex_development_state.json"
        ),
    )
    started_at = time.time()
    try:
        ledger.timing.record(
            "orchestrator.started",
            "orchestrator-supervisor",
            timestamp=started_at,
            status="running",
            supervisor_id=supervisor.supervisor_id,
        )
    except (OSError, ValueError, TypeError):
        pass
    result = supervisor.run_once()
    finished_at = time.time()
    first_error = (
        result["error_details"][0]
        if isinstance(result.get("error_details"), list)
        and result["error_details"]
        else {}
    )
    emergency = result.get("emergency")
    emergency_handled = bool(
        isinstance(emergency, dict)
        and emergency.get("called") is True
        and emergency.get("error") is None
    )
    try:
        ledger.timing.record(
            "orchestrator.finished",
            "orchestrator-supervisor",
            timestamp=finished_at,
            status=(
                "succeeded"
                if result["errors"] == 0 or emergency_handled
                else "failed"
            ),
            supervisor_id=supervisor.supervisor_id,
            duration_ms=round((finished_at - started_at) * 1000),
            dispatched=result["dispatched"],
            synced=result["synced"],
            children_created=result["children_created"],
            campaign_actions=result["campaign_actions"],
            error_count=result["errors"],
            first_error_type=first_error.get("error_type"),
            first_error_plan=first_error.get("plan_id"),
        )
    except (OSError, ValueError, TypeError):
        pass
    print(json.dumps(result, sort_keys=True))
    return 0 if result["errors"] == 0 or emergency_handled else 1


if __name__ == "__main__":
    raise SystemExit(main())
