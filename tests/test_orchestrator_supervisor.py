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


def test_supervisor_creates_grader_after_completed_live_trainer(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path / "control")
    parent = ledger.create_plan(
        kind="trainer_session",
        mode="live",
        payload={
            "script": script("session-grade"),
            "checkpoint_path": "core/test.pt",
            "inference": {
                "max_new_tokens": 32,
                "temperature": 0.0,
                "top_k": None,
                "device": "cuda",
            },
            "continuation": {
                "remaining_auto_sessions": 0,
                "next_executor_payload": None,
            },
        },
        created_by="supervisor:test",
        plan_id="plan-trainer-session-grade",
    )
    assert ledger.claim(parent["plan_id"], "remote-worker", 60) is not None
    ledger.mark_running(parent["plan_id"], "remote-worker")
    ledger.complete(
        parent["plan_id"],
        "remote-worker",
        status="succeeded",
        result={
            "schema_version": "msm_trainer_result_v1",
            "session_id": "session-grade",
            "mode": "live",
            "status": "completed",
            "event_count": 4,
            "artifacts": {
                "script": "training/pipeline/msm/sessions/session-grade/script.json",
                "raw_log": "training/pipeline/msm/sessions/session-grade/raw_chat.jsonl",
                "manifest": "training/pipeline/msm/sessions/session-grade/manifest.json",
            },
        },
    )
    transport = FakeTransport()
    supervisor = OrchestratorSupervisor(ledger, transport, repo_root=ROOT)

    result = supervisor.run_once()

    assert result["children_created"] == 1
    grade = ledger.plan("plan-grade-session-grade")
    assert grade["payload"]["workflow"]["type"] == "msm_grade"
    assert grade["payload"]["task"]["context_files"][:2] == [
        "training/pipeline/msm/sessions/session-grade/script.json",
        "training/pipeline/msm/sessions/session-grade/raw_chat.jsonl",
    ]


def test_supervisor_autonext_requires_gate_and_decrements_budget(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path / "control")
    next_payload = {
        "task": {"job_id": "next-script"},
        "model_id": None,
        "required_context_tokens": 0,
        "max_model_attempts": 2,
        "workflow": {
            "type": "msm_trainer",
            "session_id": "session-next",
            "checkpoint": "core/test.pt",
            "trainer_mode": "live",
            "inference": {
                "max_new_tokens": 32,
                "temperature": 0.0,
                "top_k": None,
                "device": "cuda",
            },
            "artifact_path": "training/pipeline/msm/proposals/next.json",
            "continuation": {
                "remaining_auto_sessions": 9,
                "next_executor_payload": None,
            },
        },
    }
    parent = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={
            "task": {"job_id": "grade"},
            "model_id": None,
            "required_context_tokens": 0,
            "max_model_attempts": 2,
            "workflow": {
                "type": "msm_grade",
                "session_id": "session-current",
                "script_path": "training/pipeline/msm/sessions/session-current/script.json",
                "raw_log_path": "training/pipeline/msm/sessions/session-current/raw_chat.jsonl",
                "artifact_path": "training/pipeline/msm/sessions/session-current/grading_result.json",
                "continuation": {
                    "remaining_auto_sessions": 2,
                    "next_executor_payload": next_payload,
                },
            },
        },
        created_by="supervisor:test",
        plan_id="plan-grade-session-current",
        authorization={
            "allow_weight_updates": False,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": True,
        },
    )
    assert ledger.claim(parent["plan_id"], "remote-worker", 60) is not None
    ledger.mark_running(parent["plan_id"], "remote-worker")
    ledger.complete(
        parent["plan_id"],
        "remote-worker",
        status="succeeded",
        result={"grade": {"decision": "PASS_AUTONEXT"}},
    )
    transport = FakeTransport()
    supervisor = OrchestratorSupervisor(ledger, transport, repo_root=ROOT)

    result = supervisor.run_once()

    assert result["children_created"] == 1
    child = ledger.plan("plan-executor-session-next")
    assert (
        child["payload"]["workflow"]["continuation"]["remaining_auto_sessions"]
        == 1
    )
    assert child["authorization"]["allow_auto_advance"] is True
