from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab.backend.messages.store import MessageStore
from tests.helpers import make_lab_config
from training.pipeline.control.ledger import ControlLedger
from training.pipeline.control.provider_failover import ProviderExecution
from training.pipeline.control.strategic_orchestrator import (
    StrategicDecisionError,
    StrategicOrchestrator,
)


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


def test_campaign_boundary_rejects_phase_continuation_over_budget(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    schema = repo / "training/pipeline"
    schema.mkdir(parents=True)
    (schema / "strategic_decision_schema.json").write_text("{}\n", encoding="utf-8")
    (repo / "context.md").write_text("context\n", encoding="utf-8")
    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="strategic_decision",
        mode="live",
        payload={
            "boundary_id": "campaign-budget",
            "title": "Budget test",
            "instructions": "Propose a bounded phase block.",
            "context_files": ["context.md"],
            "allowed_child_kinds": ["phase_block"],
            "campaign": {
                "campaign_id": "campaign",
                "boundary_index": 1,
                "constraints": {
                    "remaining_phase_blocks": 2,
                    "remaining_executor_jobs": 0,
                    "remaining_trainer_sessions": 0,
                    "allowed_phase_ids": ["phase_0_form"],
                    "max_phase_continuation_blocks": 1,
                    "max_auto_sessions": 0,
                },
            },
        },
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": True,
        },
        created_by="test",
        plan_id="plan-campaign-budget",
    )
    child = {
        "kind": "phase_block",
        "mode": "live",
        "payload": {
            "phase_id": "phase_0_form",
            "runner_args": ["--parent", "core/msm/test.pt"],
            "continuation": {"remaining_blocks": 2},
        },
        "authorization": {
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": True,
        },
    }
    orchestrator = StrategicOrchestrator(
        ledger,
        FakeRouter(
            {
                "action": "enqueue_plan",
                "rationale": "Too many blocks.",
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
    assert "exceeds campaign phase-block budget" in receipt["last_error"]


def test_campaign_boundary_rejects_incomplete_cortex_executor_envelope() -> None:
    campaign = {
        "campaign_id": "cortex-campaign",
        "boundary_index": 1,
        "constraints": {
            "remaining_phase_blocks": 0,
            "remaining_executor_jobs": 1,
            "remaining_trainer_sessions": 0,
            "allowed_phase_ids": [],
            "max_phase_continuation_blocks": 0,
            "max_auto_sessions": 0,
        },
    }
    child = {
        "kind": "executor_job",
        "mode": "live",
        "payload": {
            "task": {"max_tokens": 4096, "prompt": "Author a script."},
            "model_id": "ternary-bonsai-27b",
            "required_context_tokens": 0,
            "max_model_attempts": 2,
            "workflow": {
                "type": "cortex_train",
                "session_id": "session",
                "parent_checkpoint": "core/cortex/parent.pt",
                "output_checkpoint": "core/cortex/output.pt",
                "runner_args": [],
                "artifact_path": "training/pipeline/msm/proposals/script.json",
            },
        },
        "authorization": {
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    }

    with pytest.raises(
        StrategicDecisionError,
        match="lacks required envelope fields",
    ):
        StrategicOrchestrator._validate_campaign_child(child, campaign)


def test_campaign_boundary_rejects_cortex_parent_in_runner_args() -> None:
    artifact = "training/pipeline/msm/proposals/script.json"
    campaign = {
        "campaign_id": "cortex-campaign",
        "boundary_index": 1,
        "constraints": {
            "remaining_phase_blocks": 0,
            "remaining_executor_jobs": 1,
            "remaining_trainer_sessions": 0,
            "allowed_phase_ids": [],
            "max_phase_continuation_blocks": 0,
            "max_auto_sessions": 0,
        },
    }
    child = {
        "kind": "executor_job",
        "mode": "live",
        "payload": {
            "task": {
                "job_id": "author-script",
                "title": "Author script",
                "instructions": "Author one script.",
                "allowed_artifact_paths": [artifact],
                "allowed_actions": [
                    "VALIDATE_JSON",
                    "RETURN_VALIDATION_ERRORS",
                ],
                "max_tokens": 4096,
                "context_files": ["training/pipeline/script_schema.json"],
                "artifact_json_schemas": {
                    artifact: "training/pipeline/script_schema.json"
                },
            },
            "model_id": "ternary-bonsai-27b",
            "required_context_tokens": 0,
            "max_model_attempts": 2,
            "workflow": {
                "type": "cortex_train",
                "session_id": "session",
                "parent_checkpoint": "core/cortex/parent.pt",
                "output_checkpoint": "core/cortex/output.pt",
                "runner_args": ["--parent", "core/cortex/parent.pt"],
                "artifact_path": artifact,
            },
        },
        "authorization": {
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    }

    with pytest.raises(
        StrategicDecisionError,
        match="--parent is derived",
    ):
        StrategicOrchestrator._validate_campaign_child(child, campaign)

    child["payload"]["workflow"]["runner_args"] = ["--learning-rate", "0.0002"]
    with pytest.raises(
        StrategicDecisionError,
        match="runner option is unsupported",
    ):
        StrategicOrchestrator._validate_campaign_child(child, campaign)

    child["payload"]["workflow"]["runner_args"] = ["--lr", "0.0002"]
    child["payload"]["task"]["context_files"].append(
        "training/logs/campaign_18_reports/decision.json"
    )
    with pytest.raises(
        StrategicDecisionError,
        match="trainbox-available",
    ):
        StrategicOrchestrator._validate_campaign_child(child, campaign)
