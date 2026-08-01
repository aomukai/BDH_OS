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
    assert destination.wake_path.is_file()

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


def test_claim_renewal_persists_bounded_curriculum_progress(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path / "control")
    plan = shadow_plan(ledger)
    assert ledger.claim(plan["plan_id"], "worker", 60) is not None
    ledger.mark_running(plan["plan_id"], "worker")
    progress = {
        "kind": "cortex_curriculum",
        "phase": "generating",
        "completed_chunks": 6,
        "active_chunk": 7,
        "completed_examples": 300,
        "target_examples": 500,
        "semantic_attempt": 2,
    }

    ledger.renew_claim(plan["plan_id"], "worker", 60, progress=progress)

    assert ledger.receipt(plan["plan_id"])["progress"] == progress


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
    events = ledger.timing.events()
    assert [event["event"] for event in events].count("plan.queued") == 1
    assert [event["event"] for event in events].count("plan.status") == 3
    reports = [event for event in events if event["event"] == "plan.report"]
    assert len(reports) == 1
    assert reports[0]["role"] == "trainer"
    assert reports[0]["runtime_ms"] >= 0


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


def test_remote_terminal_mirror_preserves_attempt_count(tmp_path: Path) -> None:
    local = ControlLedger(tmp_path / "local")
    remote = ControlLedger(tmp_path / "remote")
    plan = shadow_plan(local, plan_id="plan-mirror")
    remote.import_plan(plan)
    assert remote.claim(plan["plan_id"], "worker", 60) is not None
    remote.mark_running(plan["plan_id"], "worker")
    report = remote.complete(
        plan["plan_id"],
        "worker",
        status="succeeded",
        result={"ok": True},
    )

    local.accept_remote_report(
        plan["plan_id"],
        remote.receipt(plan["plan_id"]),
        report,
    )

    assert local.receipt(plan["plan_id"])["attempt_count"] == 1


def test_executor_timing_records_model_attempts_and_tokens(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="executor_job",
        mode="shadow",
        payload={"job_id": "script-author"},
        created_by="orchestrator:test",
        plan_id="plan-executor-timing",
    )
    assert ledger.claim(plan["plan_id"], "worker", 60) is not None
    ledger.mark_running(plan["plan_id"], "worker")
    ledger.complete(
        plan["plan_id"],
        "worker",
        status="succeeded",
        result={
            "valid": True,
            "model_id": "ternary-bonsai-27b",
            "requested_model_id": "ternary-bonsai-27b",
            "attempt_count": 2,
            "attempts": [
                {
                    "attempt": 1,
                    "elapsed_seconds": 1.25,
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "total_tokens": 150,
                    },
                },
                {
                    "attempt": 2,
                    "elapsed_seconds": 0.75,
                    "usage": {
                        "prompt_tokens": 80,
                        "completion_tokens": 40,
                        "total_tokens": 120,
                    },
                },
            ],
        },
    )

    event = next(
        event
        for event in ledger.timing.events()
        if event["event"] == "plan.report"
    )
    assert event["event"] == "plan.report"
    assert event["role"] == "executor"
    assert event["provider"] == "local"
    assert event["model"] == "ternary-bonsai-27b"
    assert event["attempt_count"] == 2
    assert event["script_attempt_count"] == 2
    assert event["model_attempt_ms"] == 2000
    assert event["prompt_tokens"] == 180
    assert event["completion_tokens"] == 90
    assert event["total_tokens"] == 270
