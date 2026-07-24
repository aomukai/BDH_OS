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
            or plan["kind"] != "executor_job"
        ):
            return False
        workflow = plan["payload"].get("workflow")
        if not isinstance(workflow, dict) or workflow.get("type") != "msm_trainer":
            return False
        expected = {
            "type",
            "session_id",
            "checkpoint",
            "trainer_mode",
            "inference",
            "artifact_path",
        }
        if set(workflow) != expected:
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
            orchestrator_plan_id=plan_id,
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
            },
            created_by=self.supervisor_id,
            parent_plan_id=plan_id,
            plan_id=child_id,
            authorization={
                "allow_weight_updates": False,
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": False,
            },
        )
        self.transport.dispatch(child["plan_id"])
        return True


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
