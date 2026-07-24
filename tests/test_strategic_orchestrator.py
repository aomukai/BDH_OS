from __future__ import annotations

import json
from pathlib import Path

from lab.backend.messages.store import MessageStore
from tests.helpers import make_lab_config
from training.pipeline.control.ledger import ControlLedger
from training.pipeline.control.provider_failover import ProviderExecution
from training.pipeline.control.strategic_orchestrator import StrategicOrchestrator


class FakeRouter:
    def __init__(self, output: dict):
        self.output = output
        self.calls = 0

    def run(self, _prompt: str, _schema: Path) -> ProviderExecution:
        self.calls += 1
        return ProviderExecution(
            provider="codex",
            model="gpt-5.6-sol",
            output=self.output,
            duration_seconds=1.0,
            failover_reason=None,
        )


def strategic_plan(ledger: ControlLedger, repo: Path) -> dict:
    context = repo / "context.md"
    context.write_text("Current evidence.\n", encoding="utf-8")
    return ledger.create_plan(
        kind="strategic_decision",
        mode="live",
        payload={
            "boundary_id": "phase0-next",
            "title": "Choose the next Phase 0 action",
            "instructions": "Choose one bounded diagnostic executor job.",
            "context_files": ["context.md"],
            "allowed_child_kinds": ["executor_job"],
        },
        authorization={
            "allow_weight_updates": False,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        created_by="test",
        plan_id="plan-strategic-phase0-next",
    )


def test_strategic_boundary_executes_once_and_materializes_one_child(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    schema = repo / "training/pipeline"
    schema.mkdir(parents=True)
    (schema / "strategic_decision_schema.json").write_text("{}\n", encoding="utf-8")
    ledger = ControlLedger(tmp_path / "control")
    plan = strategic_plan(ledger, repo)
    child = {
        "kind": "executor_job",
        "mode": "live",
        "payload": {
            "task": {"job_id": "diagnose"},
            "model_id": None,
            "required_context_tokens": 0,
            "max_model_attempts": 1,
        },
        "authorization": {
            "allow_weight_updates": False,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    }
    router = FakeRouter(
        {
            "action": "enqueue_plan",
            "rationale": "A bounded diagnostic is needed.",
            "user_message": None,
            "child_plan_json": json.dumps(child),
        }
    )
    orchestrator = StrategicOrchestrator(
        ledger,
        router,  # type: ignore[arg-type]
        repo_root=repo,
        worker_id="strategic:test",
        message_store=MessageStore(make_lab_config(tmp_path / "lab-config")),
    )

    assert orchestrator.execute(plan) is True
    assert orchestrator.execute(plan) is False
    report = ledger.report(plan["plan_id"])
    assert report is not None
    assert report["result"]["provider"] == "codex"
    assert orchestrator.materialize_child(plan, report) is True
    assert orchestrator.materialize_child(plan, report) is False
    created = ledger.plan("plan-strategy-phase0-next")
    assert created is not None
    assert created["parent_plan_id"] == plan["plan_id"]
    assert router.calls == 1


def test_strategic_boundary_rejects_authority_escalation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    schema = repo / "training/pipeline"
    schema.mkdir(parents=True)
    (schema / "strategic_decision_schema.json").write_text("{}\n", encoding="utf-8")
    ledger = ControlLedger(tmp_path / "control")
    plan = strategic_plan(ledger, repo)
    child = {
        "kind": "executor_job",
        "mode": "live",
        "payload": {},
        "authorization": {
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    }
    orchestrator = StrategicOrchestrator(
        ledger,
        FakeRouter(
            {
                "action": "enqueue_plan",
                "rationale": "Invalid escalation.",
                "user_message": None,
                "child_plan_json": json.dumps(child),
            }
        ),  # type: ignore[arg-type]
        repo_root=repo,
        worker_id="strategic:test",
        message_store=MessageStore(make_lab_config(tmp_path / "lab-config")),
    )

    assert orchestrator.execute(plan) is True
    receipt = ledger.receipt(plan["plan_id"])
    assert receipt is not None
    assert receipt["status"] == "retry_wait"
    assert "exceeds parent authorization" in receipt["last_error"]
