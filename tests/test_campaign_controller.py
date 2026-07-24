from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lab.backend.messages.store import MessageStore
from tests.helpers import make_lab_config
from training.pipeline.control.campaign_controller import (
    CampaignController,
    CampaignStateStore,
)
from training.pipeline.control.ledger import ControlLedger


def deadline(hours: int = 1) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(hours=hours)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def complete(
    ledger: ControlLedger,
    plan_id: str,
    *,
    result: dict | None = None,
) -> None:
    assert ledger.claim(plan_id, "worker:test", 60) is not None
    ledger.mark_running(plan_id, "worker:test")
    ledger.complete(
        plan_id,
        "worker:test",
        status="succeeded",
        result=result or {"status": "ok"},
    )


def seed(ledger: ControlLedger) -> dict:
    plan = ledger.create_plan(
        kind="phase_block",
        mode="live",
        payload={
            "phase_id": "phase_0_form",
            "runner_args": ["--parent", "scratch"],
            "continuation": {"remaining_blocks": 0},
        },
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        created_by="test",
        plan_id="plan-seed",
    )
    complete(
        ledger,
        plan["plan_id"],
        result={
            "gate_status": "not_met",
            "checkpoint_after": "core/msm/seed.pt",
        },
    )
    return plan


def controller(tmp_path: Path) -> tuple[ControlLedger, CampaignController]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "context.md").write_text("Campaign context.\n", encoding="utf-8")
    ledger = ControlLedger(tmp_path / "control")
    messages = MessageStore(make_lab_config(tmp_path / "lab-config"))
    return ledger, CampaignController(
        ledger,
        repo_root=repo,
        message_store=messages,
        controller_id="campaign:test",
    )


def start_campaign(
    campaign: CampaignController,
    *,
    budgets: dict[str, int] | None = None,
) -> dict:
    return campaign.start(
        campaign_id="test-campaign",
        mode="live",
        objective="Meet the Phase 0 gate.",
        seed_plan_id="plan-seed",
        deadline_at=deadline(),
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": True,
        },
        allowed_child_kinds=["phase_block"],
        allowed_phase_ids=["phase_0_form"],
        context_files=["context.md"],
        budgets=budgets
        or {
            "strategic_boundaries": 3,
            "phase_blocks": 3,
            "executor_jobs": 0,
            "trainer_sessions": 0,
        },
    )


def test_campaign_creates_one_restart_safe_boundary(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    start_campaign(campaign)

    first = campaign.reconcile()
    second = campaign.reconcile()

    assert first["action"] == "created_strategic_boundary"
    assert second == {
        "active": True,
        "action": "waiting_for_plan",
        "plan_id": first["plan_id"],
        "plan_status": "queued",
    }
    plans = list(ledger.plans_dir.glob("plan-campaign-*.json"))
    assert len(plans) == 1
    state = CampaignStateStore(ledger.root).read()
    assert state is not None
    assert state["usage"]["strategic_boundaries"] == 1


def test_new_campaign_ignores_children_from_an_older_campaign(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    seed_plan = seed(ledger)
    old = ledger.create_plan(
        kind="strategic_decision",
        mode="shadow",
        payload={
            "boundary_id": "old-boundary",
            "title": "Old campaign",
            "instructions": "Return wait.",
            "context_files": ["context.md"],
            "allowed_child_kinds": ["executor_job"],
        },
        created_by="old-campaign",
        parent_plan_id=seed_plan["plan_id"],
        plan_id="plan-old-campaign-boundary",
    )
    complete(
        ledger,
        old["plan_id"],
        result={
            "decision": {
                "action": "wait",
                "rationale": "Old campaign stopped.",
                "user_message": None,
                "child_plan_json": None,
                "child_plan": None,
            }
        },
    )
    start_campaign(campaign)

    result = campaign.reconcile()

    assert result["action"] == "created_strategic_boundary"
    created = ledger.plan(result["plan_id"])
    assert created is not None
    assert created["parent_plan_id"] == seed_plan["plan_id"]


def test_campaign_reenters_strategy_after_terminal_child(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    start_campaign(campaign)
    first = campaign.reconcile()
    strategy = ledger.plan(first["plan_id"])
    assert strategy is not None
    complete(
        ledger,
        strategy["plan_id"],
        result={
            "provider": "codex",
            "decision": {
                "action": "enqueue_plan",
                "child_plan": {},
                "child_plan_json": "{}",
                "rationale": "Run one block.",
                "user_message": None,
            },
        },
    )
    child = ledger.create_plan(
        kind="phase_block",
        mode="live",
        payload={
            "phase_id": "phase_0_form",
            "runner_args": ["--parent", "core/msm/seed.pt"],
            "continuation": {"remaining_blocks": 0},
        },
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        created_by="strategic:codex",
        parent_plan_id=strategy["plan_id"],
        plan_id="plan-strategy-child",
    )
    complete(
        ledger,
        child["plan_id"],
        result={
            "gate_status": "not_met",
            "checkpoint_after": "core/msm/child.pt",
        },
    )

    result = campaign.reconcile()

    assert result["action"] == "created_strategic_boundary"
    next_plan = ledger.plan(result["plan_id"])
    assert next_plan is not None
    assert next_plan["parent_plan_id"] == child["plan_id"]
    state = CampaignStateStore(ledger.root).read()
    assert state is not None
    assert state["usage"]["strategic_boundaries"] == 2
    assert state["usage"]["phase_blocks"] == 1


def test_campaign_wait_decision_pauses_and_notifies(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    start_campaign(campaign)
    created = campaign.reconcile()
    complete(
        ledger,
        created["plan_id"],
        result={
            "provider": "codex",
            "decision": {
                "action": "wait",
                "child_plan": None,
                "child_plan_json": None,
                "rationale": "Need more evidence.",
                "user_message": None,
            },
        },
    )

    result = campaign.reconcile()

    assert result["action"] == "waiting_wait"
    state = CampaignStateStore(ledger.root).read()
    assert state is not None
    assert state["status"] == "waiting"
    assert state["stop_reason"] == "Need more evidence."
    inbox = campaign.message_store.list_messages("inbox")
    assert any("waiting" in message.title for message in inbox)


def test_cortex_campaign_boundary_contains_commissioned_workflow_contract(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    cortex_seed = ledger.create_plan(
        kind="cortex_block",
        mode="live",
        payload={
            "script": {"schema_version": "msm_script_v1"},
            "output_checkpoint": "core/cortex/seed.pt",
            "runner_args": [],
        },
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        created_by="test",
        plan_id="plan-cortex-seed",
    )
    complete(
        ledger,
        cortex_seed["plan_id"],
        result={
            "checkpoint_after": "core/cortex/seed.pt",
            "metadata": {"final_loss": 7.0},
        },
    )
    campaign.start(
        campaign_id="cortex-test",
        mode="live",
        objective="Run bounded Cortex MSM research.",
        seed_plan_id=cortex_seed["plan_id"],
        deadline_at=deadline(),
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        allowed_child_kinds=["executor_job"],
        allowed_phase_ids=[],
        context_files=["context.md"],
        budgets={
            "strategic_boundaries": 2,
            "phase_blocks": 0,
            "executor_jobs": 2,
            "trainer_sessions": 0,
        },
    )

    result = campaign.reconcile()

    assert result["action"] == "created_strategic_boundary"
    boundary = ledger.plan(result["plan_id"])
    assert boundary is not None
    instructions = boundary["payload"]["instructions"]
    assert "Cortex 1.2B MSM campaign" in instructions
    assert "workflow.parent_checkpoint" in instructions
    assert "ternary-bonsai-27b" in instructions
    assert "training/pipeline/script_schema.json" in instructions


def test_cortex_derivation_failure_creates_repair_boundary(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    cortex_seed = ledger.create_plan(
        kind="cortex_block",
        mode="live",
        payload={
            "script": {"schema_version": "msm_script_v1"},
            "output_checkpoint": "core/cortex/seed.pt",
            "runner_args": [],
        },
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        created_by="test",
        plan_id="plan-cortex-repair-seed",
    )
    complete(
        ledger,
        cortex_seed["plan_id"],
        result={"checkpoint_after": "core/cortex/seed.pt"},
    )
    campaign.start(
        campaign_id="cortex-repair",
        mode="live",
        objective="Run bounded Cortex MSM research.",
        seed_plan_id=cortex_seed["plan_id"],
        deadline_at=deadline(),
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        allowed_child_kinds=["executor_job"],
        allowed_phase_ids=[],
        context_files=["context.md"],
        budgets={
            "strategic_boundaries": 3,
            "phase_blocks": 0,
            "executor_jobs": 2,
            "trainer_sessions": 0,
        },
    )
    first = campaign.reconcile()
    strategy = ledger.plan(first["plan_id"])
    assert strategy is not None
    complete(
        ledger,
        strategy["plan_id"],
        result={
            "provider": "codex",
            "decision": {
                "action": "enqueue_plan",
                "child_plan": {},
                "child_plan_json": "{}",
                "rationale": "Author one script.",
                "user_message": None,
            },
        },
    )
    executor = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={
            "task": {},
            "model_id": "ternary-bonsai-27b",
            "required_context_tokens": 0,
            "max_model_attempts": 2,
            "workflow": {
                "type": "cortex_train",
                "session_id": "broken-session",
                "parent_checkpoint": "core/cortex/seed.pt",
                "output_checkpoint": "core/cortex/broken.pt",
                "runner_args": ["--parent", "core/cortex/seed.pt"],
                "artifact_path": "training/pipeline/msm/proposals/broken.json",
            },
        },
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        created_by="strategic:codex",
        parent_plan_id=strategy["plan_id"],
        plan_id="plan-cortex-broken-executor",
    )
    complete(ledger, executor["plan_id"], result={"valid": True})
    campaign.store.record_derivation_failure(
        executor["plan_id"],
        RuntimeError("--parent must be derived"),
    )

    repaired = campaign.reconcile()

    assert repaired["action"] == "created_strategic_boundary"
    boundary = ledger.plan(repaired["plan_id"])
    assert boundary is not None
    instructions = boundary["payload"]["instructions"]
    assert "child-derivation failure" in instructions
    assert "Do not wait for another report" in instructions
    assert "--parent must be derived" in instructions
    assert "trigger workflow's parent_checkpoint" in instructions


def test_campaign_stops_at_child_budget(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    start_campaign(
        campaign,
        budgets={
            "strategic_boundaries": 2,
            "phase_blocks": 0,
            "executor_jobs": 0,
            "trainer_sessions": 0,
        },
    )

    result = campaign.reconcile()

    assert result["action"] == "paused_budget"
    state = CampaignStateStore(ledger.root).read()
    assert state is not None
    assert state["status"] == "paused"
    assert list(ledger.plans_dir.glob("plan-campaign-*.json")) == []


def test_campaign_completes_when_phase_gate_is_met(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    seed_plan = seed(ledger)
    report_path = ledger.reports_dir / f"{seed_plan['plan_id']}.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["result"]["gate_status"] = "met"
    from training.pipeline.control.ledger import content_hash

    report["content_sha256"] = content_hash(report)
    report_path.write_text(json.dumps(report) + "\n", encoding="utf-8")
    start_campaign(campaign)

    result = campaign.reconcile()

    assert result["action"] == "completed"
    state = CampaignStateStore(ledger.root).read()
    assert state is not None
    assert state["status"] == "completed"
