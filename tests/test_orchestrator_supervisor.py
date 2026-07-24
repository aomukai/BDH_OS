from __future__ import annotations

import json
from pathlib import Path

from tests.test_msm_trainer import script
from training.pipeline.control.ledger import ControlLedger
from training.pipeline.control.orchestrator_supervisor import OrchestratorSupervisor


ROOT = Path(__file__).resolve().parents[1]


class FakeTransport:
    def __init__(self):
        self.dispatched: list[str] = []

    def dispatch(self, plan_id: str):
        self.dispatched.append(plan_id)
        return {"ok": True}

    def sync(self, _plan_id: str):
        return {"ok": True, "report": None}


def test_supervisor_creates_exactly_one_trainer_child(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path / "control")
    artifact_path = "training/pipeline/msm/proposals/script.json"
    parent = ledger.create_plan(
        kind="executor_job",
        mode="shadow",
        payload={
            "task": {"job_id": "author"},
            "model_id": None,
            "required_context_tokens": 0,
            "max_model_attempts": 2,
            "workflow": {
                "type": "msm_trainer",
                "session_id": "session-supervised",
                "checkpoint": "scratch",
                "trainer_mode": "shadow",
                "inference": {
                    "max_new_tokens": 32,
                    "temperature": 0.0,
                    "top_k": None,
                    "device": "cuda",
                },
                "artifact_path": artifact_path,
            },
        },
        created_by="orchestrator:test",
        plan_id="plan-parent",
    )
    assert ledger.claim(parent["plan_id"], "remote-worker", 60) is not None
    ledger.mark_running(parent["plan_id"], "remote-worker")
    ledger.complete(
        parent["plan_id"],
        "remote-worker",
        status="succeeded",
        result={
            "valid": True,
            "model_id": "gemma-4-26b-a4b",
            "proposal": {
                "artifacts": [
                    {"path": artifact_path, "content": json.dumps(script())}
                ]
            },
        },
    )
    transport = FakeTransport()
    supervisor = OrchestratorSupervisor(
        ledger,
        transport,
        repo_root=ROOT,
        supervisor_id="supervisor:test",
    )
    first = supervisor.run_once()
    assert first["children_created"] == 1
    child_id = "plan-trainer-session-supervised"
    assert ledger.plan(child_id)["parent_plan_id"] == parent["plan_id"]
    assert transport.dispatched == [child_id]

    second = supervisor.run_once()
    assert second["children_created"] == 0
    assert transport.dispatched == [child_id, child_id]
