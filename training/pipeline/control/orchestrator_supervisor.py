from __future__ import annotations

import argparse
import fcntl
import json
import os
import socket
from pathlib import Path
from typing import Any

from .ledger import ControlLedger, LedgerError, TERMINAL_RECEIPT_STATUSES
from .script_finalize import ScriptFinalizeError, finalize_msm_script
from .transport import SshControlTransport


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
    ) -> None:
        self.ledger = ledger
        self.transport = transport
        self.repo_root = repo_root.resolve()
        self.supervisor_id = supervisor_id or (
            f"orchestrator-supervisor:{socket.gethostname()}:{os.getpid()}"
        )
        self.lock_path = self.ledger.worker_dir / "orchestrator-supervisor.lock"

    def run_once(self) -> dict[str, int | bool]:
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
                    "errors": 0,
                }
            return self._run_locked()

    def _run_locked(self) -> dict[str, int | bool]:
        dispatched = synced = children = errors = 0
        for plan_path in sorted(self.ledger.plans_dir.glob("*.json")):
            plan_id = plan_path.stem
            try:
                receipt = self.ledger.receipt(plan_id)
                if receipt is None:
                    raise SupervisorError(f"missing local receipt: {plan_id}")
                if receipt["status"] == "queued":
                    self.transport.dispatch(plan_id)
                    dispatched += 1
                    response = self.transport.sync(plan_id)
                    if response.get("report") is not None:
                        synced += 1
                elif receipt["status"] not in TERMINAL_RECEIPT_STATUSES:
                    response = self.transport.sync(plan_id)
                    if response.get("report") is not None:
                        synced += 1
                if self._create_child_if_ready(plan_id):
                    children += 1
            except (LedgerError, SupervisorError, ScriptFinalizeError, OSError):
                errors += 1
        return {
            "acquired": True,
            "dispatched": dispatched,
            "synced": synced,
            "children_created": children,
            "errors": errors,
        }

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
        if plan["kind"] == "executor_job":
            workflow = plan["payload"].get("workflow")
            if not isinstance(workflow, dict):
                return False
            if workflow.get("type") == "msm_trainer":
                return self._create_trainer_child(plan, report, workflow)
            if workflow.get("type") == "msm_grade":
                return self._create_autonext_child(plan, report, workflow)
            return False
        if plan["kind"] == "trainer_session":
            return self._create_grade_child(plan, report)
        if plan["kind"] == "phase_block":
            return self._create_phase_block_child(plan, report)
        return False

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
    supervisor = OrchestratorSupervisor(
        ledger,
        SshControlTransport(ledger, ssh_target=args.ssh_target),
        repo_root=args.repo,
    )
    result = supervisor.run_once()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
