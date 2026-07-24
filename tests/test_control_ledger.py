from __future__ import annotations

import copy
from pathlib import Path

import pytest

from training.pipeline.control.ledger import ControlLedger, LedgerError


def shadow_plan(ledger: ControlLedger, *, plan_id: str = "plan-test") -> dict:
    return ledger.create_plan(
        kind="phase_block",
        mode="shadow",
        payload={"phase_id": "phase_0_form", "runner_args": ["--dry-run"]},
        created_by="orchestrator:test",
        plan_id=plan_id,
    )


def test_plan_import_is_hashed_and_idempotent(tmp_path: Path) -> None:
    source = ControlLedger(tmp_path / "source")
    destination = ControlLedger(tmp_path / "destination")
    plan = shadow_plan(source)

    assert destination.import_plan(plan) == plan
    assert destination.import_plan(plan) == plan
    assert len(list(destination.plans_dir.glob("*.json"))) == 1

    tampered = copy.deepcopy(plan)
    tampered["payload"]["phase_id"] = "phase_1_word_form"
    with pytest.raises(LedgerError, match="hash mismatch"):
        destination.import_plan(tampered)


def test_shadow_plan_cannot_authorize_mutation(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path / "control")
    with pytest.raises(LedgerError, match="shadow plans"):
        ledger.create_plan(
            kind="phase_block",
            mode="shadow",
            payload={"phase_id": "phase_0_form"},
            created_by="orchestrator:test",
            authorization={
                "allow_weight_updates": True,
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": False,
            },
        )


def test_claim_prevents_duplicate_and_expired_lease_recovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = ControlLedger(tmp_path / "control")
    plan = shadow_plan(ledger)
    now = 1000.0
    monkeypatch.setattr("training.pipeline.control.ledger.time.time", lambda: now)
    assert ledger.claim(plan["plan_id"], "worker-one", 10) is not None
    assert ledger.claim(plan["plan_id"], "worker-two", 10) is None

    now = 1011.0
    recovered = ledger.claim(plan["plan_id"], "worker-two", 10)
    assert recovered is not None
    assert recovered["attempt"] == 2


def test_completion_is_terminal_and_replay_safe(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path / "control")
    plan = shadow_plan(ledger)
    assert ledger.claim(plan["plan_id"], "worker", 60) is not None
    ledger.mark_running(plan["plan_id"], "worker")
    report = ledger.complete(
        plan["plan_id"],
        "worker",
        status="succeeded",
        result={"dry_run": True},
        artifact_hashes={"block_report.json": "a" * 64},
    )
    assert ledger.receipt(plan["plan_id"])["status"] == "completed"
    assert ledger.complete(
        plan["plan_id"],
        "worker",
        status="succeeded",
        result={"ignored_replay": True},
    ) == report
    assert ledger.claim(plan["plan_id"], "worker-two", 60) is None


def test_retry_exhaustion_dead_letters_without_reexecution(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="executor_job",
        mode="shadow",
        payload={"job_id": "test"},
        created_by="orchestrator:test",
        plan_id="plan-retry",
        max_attempts=1,
    )
    assert ledger.claim(plan["plan_id"], "worker", 60) is not None
    receipt = ledger.fail_retryable(plan["plan_id"], "worker", "synthetic")
    assert receipt["status"] == "dead_letter"
    assert ledger.claim(plan["plan_id"], "worker-two", 60) is None
