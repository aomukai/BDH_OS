from __future__ import annotations

import json
from pathlib import Path

from lab.backend.messages.store import MessageStore
from tests.helpers import make_lab_config
from training.pipeline.control.adversarial_review import AdversarialReviewPolicy
from training.pipeline.control.campaign_controller import CampaignController
from training.pipeline.control.ledger import ControlLedger
from training.pipeline.control.provider_failover import ProviderExecution


ROOT = Path(__file__).resolve().parents[1]


class FakeRouter:
    def __init__(self, verdict: str) -> None:
        self.verdict = verdict
        self.prompts: list[tuple[str, str]] = []

    def run(self, prompt: str, schema: Path) -> ProviderExecution:
        self.prompts.append((schema.name, prompt))
        if "critique" in schema.name:
            output = {
                "concerns": ["The same contrast may have been repeated."],
                "questions": ["Why was repetition necessary?"],
                "recommendation": "challenge",
            }
        elif "defence" in schema.name:
            output = {
                "responses": ["The repetition tested concept-bleed recovery."],
                "position": "defend",
            }
        else:
            output = {
                "verdict": self.verdict,
                "rationale": "The defence is sufficiently falsifiable.",
                "required_changes": [],
            }
        return ProviderExecution(
            provider="openrouter",
            model="orchestrator-model",
            output=output,
            duration_seconds=0.1,
            failover_reason=None,
        )


class FakeSol:
    def __init__(self) -> None:
        self.incidents: list[dict] = []

    def handle(self, incident, *, campaign_controller):
        self.incidents.append(incident)
        campaign_controller.apply_governance_decision(
            "require_replan",
            "Use a materially different teaching mutation.",
        )
        return {"called": True, "action": "require_replan", "error": None}


def complete(ledger: ControlLedger, plan_id: str, result: dict) -> None:
    assert ledger.claim(plan_id, "worker:test", 60) is not None
    ledger.mark_running(plan_id, "worker:test")
    ledger.complete(plan_id, "worker:test", status="succeeded", result=result)


def setup_campaign(tmp_path: Path) -> tuple[CampaignController, ControlLedger]:
    repo = tmp_path / "repo"
    pipeline = repo / "training/pipeline"
    pipeline.mkdir(parents=True)
    (repo / "context.md").write_text("context\n", encoding="utf-8")
    for name in (
        "adversarial_critique_schema.json",
        "adversarial_defence_schema.json",
        "adversarial_verdict_schema.json",
    ):
        (pipeline / name).write_text(
            (ROOT / "training/pipeline" / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    ledger = ControlLedger(tmp_path / "control")
    seed = ledger.create_plan(
        kind="phase_block",
        mode="live",
        payload={"phase_id": "phase_0_form", "runner_args": [], "continuation": {"remaining_blocks": 0}},
        created_by="test",
        plan_id="plan-seed",
    )
    complete(ledger, seed["plan_id"], {"checkpoint_after": "core/seed.pt", "gate_status": "not_met"})
    controller = CampaignController(
        ledger,
        repo_root=repo,
        message_store=MessageStore(make_lab_config(tmp_path / "lab")),
        strategic_boundary_interval_seconds=0,
    )
    controller.start(
        campaign_id="review-campaign",
        mode="live",
        objective="Explore regression and recovery.",
        seed_plan_id=seed["plan_id"],
        deadline_at="2099-01-01T00:00:00Z",
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
        allowed_child_kinds=["executor_job"],
        allowed_phase_ids=[],
        context_files=["context.md"],
        budgets={
            "strategic_boundaries": 128,
            "phase_blocks": 0,
            "executor_jobs": 128,
            "trainer_sessions": 0,
        },
        regime="play",
        play={
            "baseline_checkpoint": "core/seed.pt",
            "target_score": 1.0,
            "branch_target_steps": 100,
            "max_branches": 4,
        },
    )
    boundary_id = controller.reconcile()["plan_id"]
    complete(
        ledger,
        boundary_id,
        {
            "decision": {
                "action": "enqueue_plan",
                "rationale": "Repeat contrast to test concept bleed.",
            }
        },
    )
    block = ledger.create_plan(
        kind="cortex_block",
        mode="live",
        payload={
            "script": {"concept": "yes/no contrast", "items": [{}, {}]},
            "output_checkpoint": "core/child.pt",
            "runner_args": [],
        },
        created_by="test",
        parent_plan_id=boundary_id,
        plan_id="plan-cortex-mutation",
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    )
    complete(
        ledger,
        block["plan_id"],
        {
            "status": "completed",
            "checkpoint_after": "core/child.pt",
            "metadata": {"examples": 2, "step_losses": [9.0, 1.0]},
        },
    )
    evaluation = ledger.create_plan(
        kind="cortex_evaluation",
        mode="live",
        payload={},
        created_by="test",
        parent_plan_id=block["plan_id"],
        plan_id="plan-eval-mutation",
    )
    complete(
        ledger,
        evaluation["plan_id"],
        {
            "certificate": {
                "status": "developmental_progress",
                "heldout_loss": 0.01,
                "diagnostic_findings": ["concept bleed persisted"],
            }
        },
    )
    return controller, ledger


def test_adversarial_review_hides_rationale_and_loss_from_critic(tmp_path: Path) -> None:
    controller, _ = setup_campaign(tmp_path)
    router = FakeRouter("approve")
    sol = FakeSol()
    policy = AdversarialReviewPolicy(
        controller.ledger.root,
        repo_root=controller.repo_root,
        router=router,  # type: ignore[arg-type]
        sol_policy=sol,  # type: ignore[arg-type]
        mutation_interval=1,
    )

    result = policy.maybe_review(controller)

    assert result["action"] == "approved"
    critique_prompt = router.prompts[0][1]
    defence_prompt = router.prompts[1][1]
    assert "Repeat contrast to test concept bleed" not in critique_prompt
    assert "heldout_loss" not in critique_prompt
    assert "Repeat contrast to test concept bleed" in defence_prompt
    assert not sol.incidents
    report = json.loads(Path(result["report"]).read_text(encoding="utf-8"))
    assert report["verdict"]["verdict"] == "approve"
    assert controller.store.read()["governance"]["last_reviewed_mutations"] == 1


def test_rejected_adversarial_review_calls_sol_and_records_directive(tmp_path: Path) -> None:
    controller, _ = setup_campaign(tmp_path)
    router = FakeRouter("reject")
    sol = FakeSol()
    policy = AdversarialReviewPolicy(
        controller.ledger.root,
        repo_root=controller.repo_root,
        router=router,  # type: ignore[arg-type]
        sol_policy=sol,  # type: ignore[arg-type]
        mutation_interval=1,
    )

    result = policy.maybe_review(controller)

    assert result["action"] == "rejected_adjudicated"
    assert sol.incidents[0]["incident_type"] == "adversarial_review"
    directive = controller.store.read()["governance"]["pending_directive"]
    assert "require_replan" in directive
