from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_msm_trainer import script
from training.pipeline.control.campaign_controller import CampaignStateStore
from training.pipeline.control.ledger import ControlLedger
from training.pipeline.control.orchestrator_supervisor import (
    OrchestratorSupervisor,
    SupervisorError,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeTransport:
    def __init__(self):
        self.dispatched: list[str] = []

    def dispatch(self, plan_id: str):
        self.dispatched.append(plan_id)
        return {"ok": True}

    def sync(self, _plan_id: str):
        return {"ok": True, "report": None}


class FlakyTransport(FakeTransport):
    def __init__(self):
        super().__init__()
        self.failures = 0

    def dispatch(self, plan_id: str):
        if self.failures == 0:
            self.failures += 1
            raise OSError("one-shot transport hiccup")
        return super().dispatch(plan_id)


class RecordingEmergency:
    def __init__(self):
        self.incidents = []

    def handle(self, incident, *, campaign_controller):
        self.incidents.append(incident)
        return {"called": True}


class FailingStrategic:
    def execute(self, _plan):
        raise OSError("persistent strategic failure")


class IdleStrategic:
    def execute(self, _plan):
        return False

    def materialize_child(self, _plan, _report):
        return False


class FakeCampaign:
    def __init__(self, root: Path):
        self.store = CampaignStateStore(root)

    def reconcile(self):
        return {"active": False, "action": "none"}


class StaticCampaignStore:
    def __init__(self, state: dict):
        self.state = state

    def read(self):
        return self.state


class StaticCampaign:
    def __init__(self, state: dict):
        self.store = StaticCampaignStore(state)


def test_supervisor_defaults_derived_state_to_its_control_root(
    tmp_path: Path,
) -> None:
    ledger = ControlLedger(tmp_path / "control")
    repo = tmp_path / "repo"
    repo.mkdir()
    live_dashboard_path = repo / "training/logs/cortex_development_state.json"
    supervisor = OrchestratorSupervisor(ledger, FakeTransport(), repo_root=repo)

    result = supervisor.run_once()

    assert result["errors"] == 0
    assert supervisor.development_store.state_path == (
        ledger.root / "derived/cortex_development_state.json"
    )
    assert supervisor.development_store.state_path.is_file()
    assert not live_dashboard_path.exists()


def test_supervisor_silently_recovers_one_shot_plan_hiccup(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path / "control")
    ledger.create_plan(
        kind="executor_job",
        mode="shadow",
        payload={"task": {"job_id": "flaky"}},
        created_by="test",
        plan_id="plan-flaky",
    )
    emergency = RecordingEmergency()
    transport = FlakyTransport()
    supervisor = OrchestratorSupervisor(
        ledger,
        transport,
        repo_root=ROOT,
        emergency_policy=emergency,  # type: ignore[arg-type]
    )

    result = supervisor.run_once()

    assert result["errors"] == 0
    assert result["emergency"] is None
    assert emergency.incidents == []
    assert transport.dispatched == ["plan-flaky"]


def test_supervisor_calls_emergency_after_immediate_retry_fails(
    tmp_path: Path,
) -> None:
    ledger = ControlLedger(tmp_path / "control")
    ledger.create_plan(
        kind="strategic_decision",
        mode="shadow",
        payload={"boundary_id": "broken"},
        created_by="test",
        plan_id="plan-broken-strategic",
    )
    emergency = RecordingEmergency()
    supervisor = OrchestratorSupervisor(
        ledger,
        FakeTransport(),
        repo_root=ROOT,
        strategic_orchestrator=FailingStrategic(),  # type: ignore[arg-type]
        emergency_policy=emergency,  # type: ignore[arg-type]
    )

    result = supervisor.run_once()

    assert result["errors"] == 1
    assert result["emergency"] == {"called": True}
    assert emergency.incidents[0]["errors"][0]["plan_id"] == (
        "plan-broken-strategic"
    )


def test_supervisor_ignores_historical_strategic_dead_letters(
    tmp_path: Path,
) -> None:
    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="strategic_decision",
        mode="shadow",
        payload={"boundary_id": "historical"},
        created_by="test",
        plan_id="plan-historical-strategic",
        max_attempts=1,
    )
    assert ledger.claim(plan["plan_id"], "worker", 60) is not None
    ledger.fail_retryable(plan["plan_id"], "worker", "old failure")
    emergency = RecordingEmergency()
    supervisor = OrchestratorSupervisor(
        ledger,
        FakeTransport(),
        repo_root=ROOT,
        strategic_orchestrator=IdleStrategic(),  # type: ignore[arg-type]
        emergency_policy=emergency,  # type: ignore[arg-type]
    )

    result = supervisor.run_once()

    assert result["errors"] == 0
    assert result["emergency"] is None
    assert emergency.incidents == []


def _completed_evaluation(ledger: ControlLedger, plan_id: str, campaign_id: str) -> None:
    plan = ledger.create_plan(
        kind="cortex_evaluation",
        mode="live",
        payload={},
        created_by="supervisor:test",
        plan_id=plan_id,
    )
    assert ledger.claim(plan["plan_id"], "remote-worker", 60) is not None
    ledger.mark_running(plan["plan_id"], "remote-worker")
    ledger.complete(
        plan["plan_id"],
        "remote-worker",
        status="succeeded",
        result={"evaluation": {"campaign_id": campaign_id}},
    )


def test_supervisor_skips_historical_evaluation_used_as_new_campaign_seed(
    tmp_path: Path,
) -> None:
    ledger = ControlLedger(tmp_path / "control")
    _completed_evaluation(ledger, "plan-old-evaluation", "old-campaign")
    campaign = StaticCampaign(
        {
            "campaign_id": "new-campaign",
            "seed_plan_id": "plan-old-evaluation",
            "current_plan_id": "plan-old-evaluation",
        }
    )
    supervisor = OrchestratorSupervisor(
        ledger,
        FakeTransport(),
        repo_root=ROOT,
        campaign_controller=campaign,  # type: ignore[arg-type]
    )

    assert supervisor._publish_evaluation_if_ready("plan-old-evaluation") is False

    campaign.store.state["seed_plan_id"] = "different-seed"
    with pytest.raises(SupervisorError, match="active Cortex evaluation"):
        supervisor._publish_evaluation_if_ready("plan-old-evaluation")


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


def test_supervisor_turns_executor_script_into_authorized_cortex_block(
    tmp_path: Path,
) -> None:
    ledger = ControlLedger(tmp_path / "control")
    artifact_path = "training/pipeline/msm/proposals/cortex-script.json"
    parent = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={
            "task": {"job_id": "author-cortex"},
            "model_id": "ternary-bonsai-27b",
            "required_context_tokens": 0,
            "max_model_attempts": 2,
            "workflow": {
                "type": "cortex_train",
                "session_id": "cortex-session-0001",
                "parent_checkpoint": "core/cortex/parent.pt",
                "output_checkpoint": "core/cortex/child.pt",
                "runner_args": ["--epochs", "1", "--lr", "0.001"],
                "artifact_path": artifact_path,
            },
        },
        created_by="orchestrator:test",
        plan_id="plan-cortex-author",
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    )
    assert ledger.claim(parent["plan_id"], "remote-worker", 60) is not None
    ledger.mark_running(parent["plan_id"], "remote-worker")
    ledger.complete(
        parent["plan_id"],
        "remote-worker",
        status="succeeded",
        result={
            "valid": True,
            "model_id": "ternary-bonsai-27b",
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

    assert supervisor.run_once()["children_created"] == 1
    child = ledger.plan("plan-cortex-cortex-session-0001")
    assert child["kind"] == "cortex_block"
    assert child["payload"]["script"]["session_id"] == "cortex-session-0001"
    assert child["payload"]["runner_args"][:2] == [
        "--parent",
        "core/cortex/parent.pt",
    ]
    assert child["authorization"]["allow_weight_updates"] is True
    assert child["authorization"]["allow_checkpoint_promotion"] is False
    assert transport.dispatched == ["plan-cortex-cortex-session-0001"]


def test_supervisor_turns_completed_curriculum_into_compact_cortex_block(
    tmp_path: Path,
) -> None:
    ledger = ControlLedger(tmp_path / "control")
    workflow = {
        "type": "cortex_curriculum",
        "session_id": "cortex-curriculum-0001",
        "parent_checkpoint": "core/cortex/parent.pt",
        "output_checkpoint": "core/cortex/child.pt",
        "runner_args": ["--epochs", "1", "--lr", "0.0002"],
        "artifact_root": "training/pipeline/msm/proposals/curriculum-0001",
        "target_examples": 3,
        "chunk_examples": 2,
        "concept": "foundation",
    }
    parent = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={
            "task": {"job_id": "author-curriculum"},
            "model_id": "ternary-bonsai-27b",
            "required_context_tokens": 0,
            "max_model_attempts": 5,
            "workflow": workflow,
        },
        created_by="orchestrator:test",
        plan_id="plan-curriculum-author",
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    )
    assert ledger.claim(parent["plan_id"], "remote-worker", 60) is not None
    ledger.mark_running(parent["plan_id"], "remote-worker")
    paths = [
        "core/cortex/curricula/cortex-curriculum-0001/chunk-0001.jsonl",
        "core/cortex/curricula/cortex-curriculum-0001/chunk-0002.jsonl",
    ]
    ledger.complete(
        parent["plan_id"],
        "remote-worker",
        status="succeeded",
        result={
            "valid": True,
            "workflow": "cortex_curriculum",
            "session_id": workflow["session_id"],
            "concept": workflow["concept"],
            "examples": 3,
            "jsonl_paths": paths,
            "curriculum_sha256": "a" * 64,
        },
    )
    transport = FakeTransport()
    supervisor = OrchestratorSupervisor(
        ledger,
        transport,
        repo_root=ROOT,
        supervisor_id="supervisor:test",
    )

    assert supervisor.run_once()["children_created"] == 1
    child = ledger.plan("plan-cortex-cortex-curriculum-0001")
    assert child["kind"] == "cortex_block"
    assert child["payload"]["jsonl_paths"] == paths
    assert child["payload"]["curriculum_sha256"] == "a" * 64
    assert child["payload"]["runner_args"][:2] == [
        "--parent",
        "core/cortex/parent.pt",
    ]
    assert child["authorization"]["allow_weight_updates"] is True


def test_supervisor_records_cortex_derivation_failure_once(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path / "control")
    parent = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={
            "task": {"job_id": "broken-cortex"},
            "model_id": "ternary-bonsai-27b",
            "required_context_tokens": 0,
            "max_model_attempts": 2,
            "workflow": {
                "type": "cortex_train",
                "session_id": "broken-cortex",
                "parent_checkpoint": "core/cortex/parent.pt",
                "output_checkpoint": "core/cortex/child.pt",
                "runner_args": ["--parent", "core/cortex/parent.pt"],
                "artifact_path": "training/pipeline/msm/proposals/broken.json",
            },
        },
        created_by="orchestrator:test",
        plan_id="plan-broken-cortex-author",
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    )
    assert ledger.claim(parent["plan_id"], "remote-worker", 60) is not None
    ledger.mark_running(parent["plan_id"], "remote-worker")
    ledger.complete(
        parent["plan_id"],
        "remote-worker",
        status="succeeded",
        result={"valid": True},
    )
    campaign = FakeCampaign(ledger.root)
    supervisor = OrchestratorSupervisor(
        ledger,
        FakeTransport(),
        repo_root=ROOT,
        campaign_controller=campaign,  # type: ignore[arg-type]
    )

    first = supervisor.run_once()
    failure = campaign.store.derivation_failure(parent["plan_id"])
    second = supervisor.run_once()

    assert first["errors"] == 1
    assert failure is not None
    assert failure["error_type"] == "SupervisorError"
    assert "runner_args are invalid" in failure["message"]
    assert second["errors"] == 0


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


def test_supervisor_continues_same_phase_with_checkpoint_and_budget(
    tmp_path: Path,
) -> None:
    ledger = ControlLedger(tmp_path / "control")
    parent = ledger.create_plan(
        kind="phase_block",
        mode="live",
        payload={
            "phase_id": "phase_0_form",
            "runner_args": ["--parent", "scratch", "--device", "cuda:1"],
            "continuation": {"remaining_blocks": 2},
        },
        created_by="supervisor:test",
        plan_id="plan-phase-parent",
        authorization={
            "allow_weight_updates": True,
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
        result={
            "kind": "phase_block",
            "phase_id": "phase_0_form",
            "block_id": "phase_0_form_block_0042",
            "checkpoint_after": "core/msm/phase_0_form_block_0042.pt",
            "local_recommendation": "run_next_block_same_phase",
        },
    )
    transport = FakeTransport()
    supervisor = OrchestratorSupervisor(ledger, transport, repo_root=ROOT)

    result = supervisor.run_once()

    assert result["children_created"] == 1
    child = ledger.plan("plan-auto-phase_0_form_block_0042")
    args = child["payload"]["runner_args"]
    assert args[args.index("--parent") + 1] == (
        "core/msm/phase_0_form_block_0042.pt"
    )
    assert child["payload"]["continuation"] == {"remaining_blocks": 1}
    assert child["authorization"]["allow_auto_advance"] is True
