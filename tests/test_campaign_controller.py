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
from training.pipeline.control.orchestrator_wake_scheduler import (
    OrchestratorWakeScheduler,
)


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


def write_provider_status(
    ledger: ControlLedger,
    *,
    codex_state: str = "limited",
    fugu_state: str = "configured",
) -> None:
    path = ledger.root / "provider/status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "ninereeds_provider_status_v1",
                "observed_at": "2026-07-25T12:00:00Z",
                "source": "test",
                "reason": "test",
                "selected_provider": "fugu",
                "codex": {
                    "state": codex_state,
                    "limited": codex_state == "limited",
                    "error": None,
                    "buckets": [],
                    "reset_epochs": [],
                },
                "fugu": {
                    "state": fugu_state,
                    "limited": fugu_state == "limited",
                    "error": None,
                },
            }
        ),
        encoding="utf-8",
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


def controller(
    tmp_path: Path,
    *,
    strategic_boundary_interval_seconds: int = 0,
) -> tuple[ControlLedger, CampaignController]:
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
        strategic_boundary_interval_seconds=strategic_boundary_interval_seconds,
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


def test_campaign_number_is_allocated_when_campaign_starts(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    start_campaign(campaign)

    registry = json.loads(
        (campaign.repo_root / "training/logs/campaign_registry.json").read_text(
            encoding="utf-8"
        )
    )
    entry = registry["campaigns"][-1]
    assert entry["campaign_id"] == "test-campaign"
    assert entry["display_name"] == "1: test-campaign"
    assert entry["status"] == "running"


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
    assert state["usage"]["strategic_boundaries"] == 0


def test_failed_technical_attempt_does_not_consume_research_budget(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    start_campaign(campaign)
    boundary = campaign.reconcile()["plan_id"]
    complete(
        ledger,
        boundary,
        result={
            "decision": {
                "action": "enqueue_plan",
                "child_plan": {},
                "child_plan_json": "{}",
                "rationale": "Try one mutation.",
                "user_message": None,
            }
        },
    )
    failed = ledger.create_plan(
        kind="phase_block",
        mode="live",
        payload={
            "phase_id": "phase_0_form",
            "runner_args": [],
            "continuation": {"remaining_blocks": 0},
        },
        created_by="test",
        parent_plan_id=boundary,
        plan_id="plan-technical-failure",
    )
    assert ledger.claim(failed["plan_id"], "worker:test", 60) is not None
    ledger.mark_running(failed["plan_id"], "worker:test")
    for attempt in range(3):
        ledger.fail_retryable(
            failed["plan_id"],
            "worker:test",
            "technical serialization failure",
        )
        if attempt < 2:
            assert ledger.claim(failed["plan_id"], "worker:test", 60) is not None
            ledger.mark_running(failed["plan_id"], "worker:test")

    usage = campaign._usage(campaign.store.read(), campaign._plans())

    assert usage["strategic_boundaries"] == 0
    assert usage["phase_blocks"] == 0


def test_budget_extension_supports_larger_audited_research_allowance(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    start_campaign(campaign)

    state = campaign.extend_budgets(
        {"strategic_boundaries": 128, "executor_jobs": 128},
        reason="Operator doubled the exploratory research allowance.",
    )

    assert state["budgets"]["strategic_boundaries"] == 128
    assert state["budgets"]["executor_jobs"] == 128
    assert "Budget extension applied without resuming" in state["history"][-1]["detail"]


def test_campaign_repairs_dead_strategic_context_boundary_autonomously(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    campaign.start(
        campaign_id="cortex-context-repair",
        mode="live",
        objective="Continue foundational Cortex training.",
        seed_plan_id="plan-seed",
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
    assert ledger.claim(first["plan_id"], "worker:test", 60) is not None
    ledger.mark_running(first["plan_id"], "worker:test")
    ledger.complete(
        first["plan_id"],
        "worker:test",
        status="failed",
        result={
            "error": (
                "StrategicDecisionError: executor context file does not exist in "
                "the repository: training_data/invented.md"
            )
        },
    )

    result = campaign.reconcile()

    assert result["action"] == "created_strategic_context_repair"
    repair = ledger.plan(result["plan_id"])
    assert repair is not None
    assert repair["parent_plan_id"] == first["plan_id"]
    assert "no weights changed" in repair["payload"]["instructions"]
    state = campaign.store.read()
    assert state is not None
    assert state["status"] == "running"
    assert state["boundary_index"] == 2


def test_existing_context_dead_letter_can_be_recovered_once(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    campaign.start(
        campaign_id="cortex-existing-blocker",
        mode="live",
        objective="Continue foundational Cortex training.",
        seed_plan_id="plan-seed",
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
    assert ledger.claim(first["plan_id"], "worker:test", 60) is not None
    ledger.mark_running(first["plan_id"], "worker:test")
    ledger.complete(
        first["plan_id"],
        "worker:test",
        status="failed",
        result={
            "error": (
                "StrategicDecisionError: executor context file does not exist in "
                "the repository: training_data/invented.md"
            )
        },
    )
    state = campaign.store.read()
    assert state is not None
    state["status"] = "blocked"
    state["stop_reason"] = "Legacy controller stopped at dead letter."
    campaign.store.write(state)

    recovered = campaign.recover_repairable_blocker()
    result = campaign.reconcile()

    assert recovered["status"] == "running"
    assert result["action"] == "created_strategic_context_repair"


def test_blocked_provider_capacity_boundary_retries_after_capacity_recovers(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    campaign.start(
        campaign_id="cortex-provider-retry",
        mode="live",
        objective="Continue foundational Cortex training.",
        seed_plan_id="plan-seed",
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
    assert ledger.claim(first["plan_id"], "worker:test", 60) is not None
    ledger.mark_running(first["plan_id"], "worker:test")
    ledger.complete(
        first["plan_id"],
        "worker:test",
        status="blocked",
        result={
            "error_type": "both_providers_limited",
            "error": "Codex and Fugu are rate-limited",
        },
    )
    state = campaign.store.read()
    assert state is not None
    state["status"] = "blocked"
    state["stop_reason"] = "Strategic boundary ended blocked without a child."
    campaign.store.write(state)
    write_provider_status(ledger, codex_state="limited", fugu_state="configured")

    result = campaign.reconcile()

    assert result["action"] == "created_strategic_provider_retry"
    retry = ledger.plan(result["plan_id"])
    assert retry is not None
    assert retry["parent_plan_id"] == first["plan_id"]
    assert "No executor ran and no weights changed" in retry["payload"]["instructions"]
    state = campaign.store.read()
    assert state is not None
    assert state["status"] == "running"
    assert state["boundary_index"] == 2


def test_empty_provider_response_retries_from_fresh_boundary(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    start_campaign(campaign)
    first = campaign.reconcile()
    assert ledger.claim(first["plan_id"], "worker:test", 60) is not None
    ledger.mark_running(first["plan_id"], "worker:test")
    for attempt in range(3):
        ledger.fail_retryable(
            first["plan_id"],
            "worker:test",
            "ProviderUnavailableError: openrouter returned empty content",
        )
        if attempt < 2:
            assert ledger.claim(first["plan_id"], "worker:test", 60) is not None
            ledger.mark_running(first["plan_id"], "worker:test")
    state = campaign.store.read()
    assert state is not None
    state["status"] = "blocked"
    state["stop_reason"] = "Strategic boundary ended dead_letter without a child."
    campaign.store.write(state)
    write_provider_status(ledger, codex_state="available", fugu_state="configured")

    result = campaign.reconcile()

    assert result["action"] == "created_strategic_provider_retry"
    retry = ledger.plan(result["plan_id"])
    assert retry is not None
    assert retry["parent_plan_id"] == first["plan_id"]
    assert "temporarily unavailable or returned an invalid response" in retry[
        "payload"
    ]["instructions"]
    assert campaign.store.read()["status"] == "running"


def test_sol_can_create_fresh_boundary_for_unclassified_strategic_dead_letter(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    start_campaign(campaign)
    first = campaign.reconcile()
    assert ledger.claim(first["plan_id"], "worker:test", 60) is not None
    ledger.mark_running(first["plan_id"], "worker:test")
    for attempt in range(3):
        ledger.fail_retryable(first["plan_id"], "worker:test", "unclassified failure")
        if attempt < 2:
            assert ledger.claim(first["plan_id"], "worker:test", 60) is not None
            ledger.mark_running(first["plan_id"], "worker:test")
    state = campaign.store.read()
    assert state is not None
    state["status"] = "blocked"
    state["stop_reason"] = "Strategic boundary failed without a child."
    campaign.store.write(state)

    result = campaign.recover_from_emergency("SOL approved a fresh boundary.")

    assert result["action"] == "created_strategic_provider_retry"
    retry = ledger.plan(result["plan_id"])
    assert retry is not None
    assert retry["parent_plan_id"] == first["plan_id"]
    assert "SOL emergency recovery rationale" in retry["payload"]["instructions"]
    assert campaign.store.read()["status"] == "running"


def test_provider_capacity_boundary_stays_blocked_while_capacity_unavailable(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    campaign.start(
        campaign_id="cortex-provider-still-blocked",
        mode="live",
        objective="Continue foundational Cortex training.",
        seed_plan_id="plan-seed",
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
    assert ledger.claim(first["plan_id"], "worker:test", 60) is not None
    ledger.mark_running(first["plan_id"], "worker:test")
    ledger.complete(
        first["plan_id"],
        "worker:test",
        status="blocked",
        result={
            "error_type": "both_providers_limited",
            "error": "Codex and Fugu are rate-limited",
        },
    )
    state = campaign.store.read()
    assert state is not None
    state["status"] = "blocked"
    state["stop_reason"] = "Strategic boundary ended blocked without a child."
    campaign.store.write(state)
    write_provider_status(ledger, codex_state="limited", fugu_state="limited")

    result = campaign.reconcile()

    assert result == {"active": False, "action": "none", "status": "blocked"}
    assert ledger.plan("plan-campaign-cortex-provider-still-blocked-b0002") is None


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
    assert state["usage"]["strategic_boundaries"] == 1
    assert state["usage"]["phase_blocks"] == 1


def test_campaign_waits_fifteen_minutes_from_terminal_child_completion(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(
        tmp_path,
        strategic_boundary_interval_seconds=0,
    )
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
    campaign.strategic_boundary_interval_seconds = 900

    result = campaign.reconcile()

    assert result["action"] == "waiting_for_orchestrator_window"
    assert result["plan_id"] == child["plan_id"]
    assert result["cadence_seconds"] == 900
    assert 0 < result["next_attempt_in_seconds"] <= 900
    assert list(ledger.plans_dir.glob("plan-campaign-*.json")) == [
        ledger.plans_dir / f"{first['plan_id']}.json"
    ]


def test_campaign_cooldown_is_anchored_to_trainbox_completion(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(
        tmp_path,
        strategic_boundary_interval_seconds=900,
    )
    plan = seed(ledger)
    start_campaign(campaign)
    report = ledger.report(plan["plan_id"])
    assert report is not None
    completed_at = datetime.fromisoformat(
        report["completed_at"].replace("Z", "+00:00")
    ).timestamp()

    assert campaign._strategic_boundary_wait_seconds(
        CampaignStateStore(ledger.root).read(),
        now=completed_at + 899,
    ) == 1
    assert campaign._strategic_boundary_wait_seconds(
        CampaignStateStore(ledger.root).read(),
        now=completed_at + 900,
    ) == 0


def test_campaign_repairs_historical_boundary_identity_collision(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    old_id = "cortex-evolution-commissioning-g0001"
    ledger.create_plan(
        kind="strategic_decision",
        mode="live",
        payload={
            "boundary_id": f"{old_id}-b0001",
            "campaign": {
                "campaign_id": old_id,
                "boundary_index": 1,
                "constraints": {},
            },
        },
        created_by="old-campaign",
        parent_plan_id="plan-unrelated-old-seed",
        plan_id=f"plan-campaign-{old_id}-b0001",
    )
    campaign.start(
        campaign_id=old_id,
        mode="live",
        objective="Continue autonomous Cortex development.",
        seed_plan_id="plan-seed",
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

    result = campaign.reconcile()

    assert result["action"] == "created_strategic_boundary"
    state = CampaignStateStore(ledger.root).read()
    assert state is not None
    assert state["campaign_id"] == "cortex-evolution-commissioning-g0002"
    assert result["plan_id"] == (
        "plan-campaign-cortex-evolution-commissioning-g0002-b0001"
    )
    assert ledger.plan(result["plan_id"])["parent_plan_id"] == "plan-seed"
    assert any(
        "Re-keyed campaign" in item["detail"] for item in state["history"]
    )


def test_wake_scheduler_triggers_once_when_training_cooldown_expires(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    plan = seed(ledger)
    start_campaign(campaign)
    report = ledger.report(plan["plan_id"])
    assert report is not None
    completed_at = datetime.fromisoformat(
        report["completed_at"].replace("Z", "+00:00")
    ).timestamp()
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return type("Completed", (), {"returncode": 0, "stderr": ""})()

    scheduler = OrchestratorWakeScheduler(
        ledger,
        transport=object(),
        runner=run,
    )

    continuation_check = scheduler.run_once(now=completed_at + 1)
    waiting = scheduler.run_once(now=completed_at + 899)
    triggered = scheduler.run_once(now=completed_at + 900)
    throttled = scheduler.run_once(now=completed_at + 901)

    assert continuation_check["action"] == "supervisor_triggered"
    assert continuation_check["reason"] == "terminal_plan_ready"
    assert waiting["action"] == "waiting_for_training_cooldown"
    assert waiting["next_wake_in_seconds"] == 1
    assert triggered["action"] == "supervisor_triggered"
    assert calls == [
        [
            "/usr/bin/systemctl",
            "--user",
            "start",
            "--no-block",
            "ninereeds-orchestrator-supervisor.service",
        ],
        [
            "/usr/bin/systemctl",
            "--user",
            "start",
            "--no-block",
            "ninereeds-orchestrator-supervisor.service",
        ],
    ]
    assert throttled["action"] == "retry_throttled"


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
    assert "qwen3.6-35b-a3b-q4-k-m-turboquant" in instructions
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
            "model_id": "qwen3.6-35b-a3b-q4-k-m-turboquant",
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


def test_new_recovery_campaign_ignores_old_child_of_failed_seed(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    failed_seed = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={
            "task": {},
            "model_id": "qwen3.6-35b-a3b-q4-k-m-turboquant",
            "required_context_tokens": 0,
            "max_model_attempts": 2,
            "workflow": {
                "type": "cortex_train",
                "session_id": "old-broken",
                "parent_checkpoint": "core/cortex/good.pt",
                "output_checkpoint": "core/cortex/missing.pt",
                "runner_args": ["--parent", "core/cortex/good.pt"],
                "artifact_path": "training/pipeline/msm/proposals/old-broken.json",
            },
        },
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        created_by="old-campaign",
        plan_id="plan-old-broken-executor",
    )
    complete(ledger, failed_seed["plan_id"], result={"valid": True})
    old_boundary = ledger.create_plan(
        kind="strategic_decision",
        mode="live",
        payload={
            "boundary_id": "old-wait",
            "title": "Old wait",
            "instructions": "Wait.",
            "context_files": ["context.md"],
            "allowed_child_kinds": ["executor_job"],
        },
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        created_by="old-campaign",
        parent_plan_id=failed_seed["plan_id"],
        plan_id="plan-old-wait-boundary",
    )
    complete(
        ledger,
        old_boundary["plan_id"],
        result={
            "decision": {
                "action": "wait",
                "rationale": "Old campaign waited.",
                "user_message": None,
                "child_plan_json": None,
                "child_plan": None,
            }
        },
    )
    campaign.store.record_derivation_failure(
        failed_seed["plan_id"],
        RuntimeError("--parent must be derived"),
    )
    campaign.start(
        campaign_id="new-recovery",
        mode="live",
        objective="Repair the failed seed.",
        seed_plan_id=failed_seed["plan_id"],
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
            "executor_jobs": 1,
            "trainer_sessions": 0,
        },
    )

    result = campaign.reconcile()

    assert result["action"] == "created_strategic_boundary"
    boundary = ledger.plan(result["plan_id"])
    assert boundary is not None
    assert boundary["parent_plan_id"] == failed_seed["plan_id"]
    assert "child-derivation failure" in boundary["payload"]["instructions"]


def test_campaign_requests_sol_review_at_child_budget(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    artifacts = campaign.repo_root / "training/logs/campaign_18_reports"
    artifacts.mkdir(parents=True)
    for name in ("decision.json", "01_report.md", "metrics.json"):
        (artifacts / name).write_text("{}\n", encoding="utf-8")
    registry = {
        "schema_version": "ninereeds_campaign_registry_v1",
        "campaigns": [
            {
                "campaign_id": "test-campaign",
                "artifact_root": "training/logs/campaign_18_reports",
            }
        ],
    }
    registry_path = campaign.repo_root / "training/logs/campaign_registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
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

    assert result["action"] == "budget_review_required"
    state = CampaignStateStore(ledger.root).read()
    assert state is not None
    assert state["status"] == "waiting"
    assert "SOL adjudication" in state["stop_reason"]


def test_cortex_budget_end_requires_sol_before_evolution_continues(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    cortex_seed = ledger.create_plan(
        kind="cortex_evaluation",
        mode="live",
        payload={},
        authorization={
            "allow_weight_updates": False,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        created_by="test",
        plan_id="plan-cortex-evolution-seed",
    )
    complete(
        ledger,
        cortex_seed["plan_id"],
        result={
            "kind": "cortex_evaluation",
            "status": "completed",
            "checkpoint_after": "core/cortex/developmental.pt",
        },
    )
    original = campaign.start(
        campaign_id="cortex-wave",
        mode="live",
        objective="Continue foundational bootstrap.",
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
            "executor_jobs": 0,
            "trainer_sessions": 0,
        },
    )

    result = campaign.reconcile()

    assert result["action"] == "budget_review_required"
    state = campaign.store.read()
    assert state is not None
    assert state["campaign_id"] == original["campaign_id"]
    assert state["status"] == "waiting"


def test_prepared_allowlist_wave_keeps_evaluations_at_strategic_boundaries(
    tmp_path: Path,
) -> None:
    _, campaign = controller(tmp_path)

    assert campaign._uses_prepared_allowlist_wave(
        {
            "context_files": [
                "training/pipeline/cortex/allowlist_waves/allowlist-test/manifest.json"
            ]
        }
    )
    assert not campaign._uses_prepared_allowlist_wave(
        {"context_files": ["training/pipeline/cortex/development_policy.json"]}
    )


def test_rollover_seed_skips_legacy_review_without_checkpoint(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    checkpoint = ledger.create_plan(
        kind="cortex_evaluation",
        mode="live",
        payload={},
        created_by="test",
        plan_id="plan-certified-checkpoint",
    )
    complete(
        ledger,
        checkpoint["plan_id"],
        result={
            "status": "completed",
            "checkpoint_after": "core/cortex/certified.pt",
        },
    )
    review = ledger.create_plan(
        kind="strategic_decision",
        mode="live",
        payload={},
        created_by="test",
        parent_plan_id=checkpoint["plan_id"],
        plan_id="plan-legacy-final-review",
    )
    complete(
        ledger,
        review["plan_id"],
        result={"decision": {"action": "request_human"}},
    )

    assert (
        campaign._resolve_rollover_seed(review["plan_id"])
        == checkpoint["plan_id"]
    )


def test_resume_after_request_human_creates_fresh_strategic_boundary(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    start_campaign(campaign)
    first = campaign.reconcile()
    complete(
        ledger,
        first["plan_id"],
        result={
            "decision": {
                "action": "request_human",
                "rationale": "The executor must be repaired.",
                "user_message": "Repair the executor.",
                "child_plan_json": None,
                "child_plan": None,
            }
        },
    )
    assert campaign.reconcile()["action"] == "waiting_request_human"

    resumed = campaign.set_status(
        "running",
        "Executor repaired and verified.",
    )

    assert resumed["status"] == "running"
    assert resumed["boundary_index"] == 2
    assert resumed["current_plan_id"] != first["plan_id"]
    retry = ledger.plan(resumed["current_plan_id"])
    assert retry is not None
    assert retry["parent_plan_id"] == first["plan_id"]
    assert "Executor repaired and verified." in retry["payload"]["instructions"]
    assert campaign.reconcile()["action"] == "waiting_for_plan"


def test_expired_campaign_uses_remaining_boundary_for_read_only_review(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    start_campaign(campaign)
    state = CampaignStateStore(ledger.root).read()
    assert state is not None
    state["deadline_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    CampaignStateStore(ledger.root).write(state)

    result = campaign.reconcile()

    assert result["action"] == "created_campaign_review"
    review = ledger.plan(result["plan_id"])
    assert review is not None
    assert review["payload"]["allowed_child_kinds"] == []
    assert "campaign deadline" in review["payload"]["instructions"]


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


def test_play_campaign_continues_candidate_until_branch_horizon(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    campaign.start(
        campaign_id="play-words",
        mode="live",
        objective="Find a word-training strategy that reaches 95%.",
        seed_plan_id="plan-seed",
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
            "strategic_boundaries": 8,
            "phase_blocks": 0,
            "executor_jobs": 8,
            "trainer_sessions": 0,
        },
        regime="play",
        play={
            "baseline_checkpoint": "core/cortex/base.pt",
            "target_score": 0.95,
            "branch_target_steps": 1000,
            "max_branches": 3,
        },
    )
    executor = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={"task": {"title": "Replay-first word curriculum"}},
        created_by="test",
        parent_plan_id="plan-seed",
        plan_id="plan-play-executor",
    )
    complete(ledger, executor["plan_id"])
    block = ledger.create_plan(
        kind="cortex_block",
        mode="live",
        payload={"runner_args": ["--parent", "core/cortex/base.pt"]},
        created_by="test",
        parent_plan_id=executor["plan_id"],
        plan_id="plan-play-block",
    )
    complete(
        ledger,
        block["plan_id"],
        result={
            "kind": "cortex_block",
            "status": "completed",
            "checkpoint_after": "core/cortex/play-001.pt",
            "metadata": {
                "examples": 500,
                "epochs": 1,
                "batch_size": 1,
                "step_losses": [1.0] * 500,
            },
        },
    )
    evaluation = ledger.create_plan(
        kind="cortex_evaluation",
        mode="live",
        payload={},
        created_by="test",
        parent_plan_id=block["plan_id"],
        plan_id="plan-play-eval",
    )
    complete(
        ledger,
        evaluation["plan_id"],
        result={
            "kind": "cortex_evaluation",
            "status": "completed",
            "checkpoint_after": "core/cortex/play-001.pt",
            "certificate": {
                "development_stage": "play",
                "candidate_checkpoint": "core/cortex/play-001.pt",
                "overall_score": 0.2,
                "blocking_reasons": [],
                "failure_modes": ["global_behavior_regression"],
            },
        },
    )
    state = campaign.store.read()
    assert state is not None
    state["root_boundary_plan_id"] = executor["plan_id"]
    state["current_plan_id"] = evaluation["plan_id"]
    campaign.store.write(state)

    result = campaign.reconcile()

    assert result["action"] == "created_strategic_boundary"
    state = campaign.store.read()
    assert state is not None
    branch = state["play"]["active_branch"]
    assert branch["current_checkpoint"] == "core/cortex/play-001.pt"
    assert branch["optimizer_steps"] == 500
    assert branch["strategy"] == "Replay-first word curriculum"
    boundary = ledger.plan(result["plan_id"])
    assert boundary is not None
    assert boundary["payload"]["campaign"]["play"]["optimizer_steps"] == 500
    assert "never reset to the baseline" in boundary["payload"]["instructions"]
    assert "four questions in the rationale" in boundary["payload"]["instructions"]
    assert "plumbing, not experimental entropy" in boundary["payload"]["instructions"]

    executor2 = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={"task": {"title": "Replay-first word curriculum"}},
        created_by="test",
        parent_plan_id=evaluation["plan_id"],
        plan_id="plan-play-executor-2",
    )
    complete(ledger, executor2["plan_id"])
    block2 = ledger.create_plan(
        kind="cortex_block",
        mode="live",
        payload={"runner_args": ["--parent", "core/cortex/play-001.pt"]},
        created_by="test",
        parent_plan_id=executor2["plan_id"],
        plan_id="plan-play-block-2",
    )
    complete(
        ledger,
        block2["plan_id"],
        result={
            "kind": "cortex_block",
            "status": "completed",
            "checkpoint_after": "core/cortex/play-002.pt",
            "metadata": {"step_losses": [0.9] * 500},
        },
    )
    evaluation2 = ledger.create_plan(
        kind="cortex_evaluation",
        mode="live",
        payload={},
        created_by="test",
        parent_plan_id=block2["plan_id"],
        plan_id="plan-play-eval-2",
    )
    complete(
        ledger,
        evaluation2["plan_id"],
        result={
            "kind": "cortex_evaluation",
            "status": "completed",
            "checkpoint_after": "core/cortex/play-002.pt",
            "certificate": {
                "development_stage": "play",
                "candidate_checkpoint": "core/cortex/play-002.pt",
                "overall_score": 0.3,
                "blocking_reasons": [],
                "failure_modes": [],
            },
        },
    )
    state = campaign.store.read()
    assert state is not None
    state["current_plan_id"] = evaluation2["plan_id"]
    campaign.store.write(state)

    next_result = campaign.reconcile()

    assert next_result["action"] == "created_strategic_boundary"
    state = campaign.store.read()
    assert state is not None
    assert len(state["play"]["completed_branches"]) == 1
    assert state["play"]["completed_branches"][0]["optimizer_steps"] == 1000
    assert state["play"]["active_branch"]["branch_index"] == 2
    assert state["play"]["active_branch"]["current_checkpoint"] == "core/cortex/base.pt"


def test_play_target_milestone_starts_another_research_branch(tmp_path: Path) -> None:
    ledger, campaign = controller(tmp_path)
    seed(ledger)
    campaign.start(
        campaign_id="play-insights",
        mode="live",
        objective="Discover word-learning dynamics across contrasting branches.",
        seed_plan_id="plan-seed",
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
            "strategic_boundaries": 4,
            "phase_blocks": 0,
            "executor_jobs": 4,
            "trainer_sessions": 0,
        },
        regime="play",
        play={
            "baseline_checkpoint": "core/cortex/base.pt",
            "target_score": 0.95,
            "branch_target_steps": 1000,
            "max_branches": 2,
        },
    )
    executor = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={"task": {"title": "Hypothesis: concentrated replay creates early transfer"}},
        created_by="test",
        parent_plan_id="plan-seed",
        plan_id="plan-play-target-executor",
    )
    complete(ledger, executor["plan_id"])
    block = ledger.create_plan(
        kind="cortex_block",
        mode="live",
        payload={},
        created_by="test",
        parent_plan_id=executor["plan_id"],
        plan_id="plan-play-target-block",
    )
    complete(
        ledger,
        block["plan_id"],
        result={
            "kind": "cortex_block",
            "status": "completed",
            "checkpoint_after": "core/cortex/play-target.pt",
            "metadata": {"step_losses": [0.5] * 500},
        },
    )
    evaluation = ledger.create_plan(
        kind="cortex_evaluation",
        mode="live",
        payload={},
        created_by="test",
        parent_plan_id=block["plan_id"],
        plan_id="plan-play-target-eval",
    )
    complete(
        ledger,
        evaluation["plan_id"],
        result={
            "kind": "cortex_evaluation",
            "status": "completed",
            "checkpoint_after": "core/cortex/play-target.pt",
            "certificate": {
                "development_stage": "play",
                "candidate_checkpoint": "core/cortex/play-target.pt",
                "overall_score": 0.99,
                "blocking_reasons": [],
                "failure_modes": [],
                "diagnostic_findings": ["unexpected early transfer"],
                "representation_drift": {"core": 0.125},
            },
        },
    )
    state = campaign.store.read()
    assert state is not None
    state["root_boundary_plan_id"] = executor["plan_id"]
    state["current_plan_id"] = evaluation["plan_id"]
    campaign.store.write(state)

    result = campaign.reconcile()

    assert result["action"] == "created_strategic_boundary"
    state = campaign.store.read()
    assert state is not None
    assert state["status"] == "running"
    assert state["play"]["completed_branches"][0]["status"] == "target_met"
    assert state["play"]["completed_branches"][0]["insights"] == [
        "unexpected early transfer"
    ]
    assert state["play"]["active_branch"]["branch_index"] == 2
    assert state["play"]["active_branch"]["current_checkpoint"] == "core/cortex/base.pt"


def test_play_full_block_horizon_starts_next_branch_without_human_loop(
    tmp_path: Path,
) -> None:
    ledger, campaign = controller(tmp_path)
    wave_block = (
        campaign.repo_root
        / "training/pipeline/cortex/allowlist_waves/allowlist-test/block-01.jsonl"
    )
    wave_block.parent.mkdir(parents=True)
    wave_block.write_text("{}\n", encoding="utf-8")
    seed(ledger)
    campaign.start(
        campaign_id="play-horizon",
        mode="live",
        objective="Compare independent prepared-block lineages.",
        seed_plan_id="plan-seed",
        deadline_at=deadline(),
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        allowed_child_kinds=["executor_job"],
        allowed_phase_ids=[],
        context_files=[
            "context.md",
            "training/pipeline/cortex/allowlist_waves/allowlist-test/block-01.jsonl",
        ],
        budgets={
            "strategic_boundaries": 4,
            "phase_blocks": 0,
            "executor_jobs": 4,
            "trainer_sessions": 0,
        },
        regime="play",
        play={
            "baseline_checkpoint": "core/cortex/base.pt",
            "target_score": 1.0,
            "branch_target_steps": 1000,
            "max_branches": 3,
        },
    )
    state = campaign.store.read()
    assert state is not None
    state["play"]["active_branch"]["current_checkpoint"] = "core/cortex/nearly-full.pt"
    state["play"]["active_branch"]["optimizer_steps"] = 750
    state["play"]["active_branch"]["strategy"] = "A nearly full prepared-block branch"
    campaign.store.write(state)

    result = campaign.reconcile()

    assert result["action"] == "created_strategic_boundary"
    state = campaign.store.read()
    assert state is not None
    assert len(state["play"]["completed_branches"]) == 1
    assert state["play"]["completed_branches"][0]["status"] == "completed_full_block_horizon"
    assert state["play"]["active_branch"]["branch_index"] == 2
    assert state["play"]["active_branch"]["current_checkpoint"] == "core/cortex/base.pt"
    boundary = ledger.plan(result["plan_id"])
    assert boundary is not None
    play_snapshot = boundary["payload"]["campaign"]["play"]
    assert play_snapshot["baseline_checkpoint"] == "core/cortex/base.pt"
    assert play_snapshot["required_block_steps"] == 500
    assert play_snapshot["can_accept_full_block"] is True
    assert "preserved baseline checkpoint: core/cortex/base.pt" in boundary["payload"]["instructions"]
    boundary = ledger.plan(result["plan_id"])
    assert boundary is not None
    assert "objective is new insight" in boundary["payload"]["instructions"]
    assert "then opens another" in boundary["payload"]["instructions"]
