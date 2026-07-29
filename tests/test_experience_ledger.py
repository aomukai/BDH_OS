from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from training.pipeline.control.experience import ExperienceLedger
from training.pipeline.control.ledger import ControlLedger


def test_attempts_stay_observations_until_effectiveness_is_assessed(
    tmp_path: Path,
) -> None:
    memory = ExperienceLedger(tmp_path / "experience.sqlite3")
    attempt = memory.record_attempt(
        problem="Concept bleed after curriculum ordering",
        context={"concepts": ["A", "B", "C"]},
        method_steps=["train A", "train B", "train C"],
        outcome="failed",
        effectiveness="not_working",
        evidence_refs=["reports/abc.json"],
        tags=["concept_bleed"],
    )
    lesson = memory.add_lesson(
        title="Interleave C before B for this concept family",
        scope="concept family A/B/C",
        conditions=["A, B, and C share nearby representations"],
        recommendation=["train A", "train C", "train B"],
        avoid=["train A", "train B", "train C"],
        confidence=0.7,
        status="candidate",
        evidence_attempt_ids=[attempt["attempt_id"]],
    )

    digest = memory.digest()

    assert digest["recent_attempts"][0]["effectiveness"] == "not_working"
    assert digest["lessons"][0]["lesson_id"] == lesson["lesson_id"]
    assert digest["lessons"][0]["status"] == "candidate"
    assert "not proof" in digest["interpretation"]

    promoted = memory.promote_lesson(
        lesson["lesson_id"],
        confidence=0.9,
        evidence_attempt_ids=[attempt["attempt_id"]],
    )
    assert promoted["status"] == "active"
    assert promoted["confidence"] == 0.9


def test_control_report_reconciliation_does_not_call_success_working(
    tmp_path: Path,
) -> None:
    control = ControlLedger(tmp_path / "control")
    memory = ExperienceLedger(control.root / "experience.sqlite3")
    plan = control.create_plan(
        kind="executor_job",
        mode="live",
        payload={},
        created_by="test",
        plan_id="plan-method-attempt",
    )
    attempt = memory.record_attempt(
        problem="Try one bounded method",
        method_steps=["executor_job"],
        source_plan_id=plan["plan_id"],
    )
    assert control.claim(plan["plan_id"], "worker:test", 30) is not None
    control.mark_running(plan["plan_id"], "worker:test")
    control.complete(
        plan["plan_id"],
        "worker:test",
        status="succeeded",
        result={"status": "completed"},
    )

    assert memory.reconcile_control_reports(control) == 1
    resolved = memory.attempt(attempt["attempt_id"])
    assert resolved["outcome"] == "succeeded"
    assert resolved["effectiveness"] == "unknown"
    assert memory.reconcile_control_reports(control) == 0


def test_control_report_reconciliation_uses_explicit_effectiveness(
    tmp_path: Path,
) -> None:
    control = ControlLedger(tmp_path / "control")
    memory = ExperienceLedger(control.root / "experience.sqlite3")
    plan = control.create_plan(
        kind="executor_job",
        mode="live",
        payload={},
        created_by="test",
        plan_id="plan-explicit-effectiveness",
    )
    attempt = memory.record_attempt(
        problem="A recurring training problem",
        method_steps=["try method Z"],
        source_plan_id=plan["plan_id"],
    )
    assert control.claim(plan["plan_id"], "worker:test", 30) is not None
    control.mark_running(plan["plan_id"], "worker:test")
    control.complete(
        plan["plan_id"],
        "worker:test",
        status="succeeded",
        result={"effectiveness": "working"},
    )

    assert memory.reconcile_control_reports(control) == 1
    assert memory.attempt(attempt["attempt_id"])["effectiveness"] == "working"


def test_digest_is_bounded_and_reports_omissions(tmp_path: Path) -> None:
    memory = ExperienceLedger(tmp_path / "experience.sqlite3")
    for number in range(5):
        memory.record_attempt(
            problem=f"Problem {number}",
            method_steps=[f"method {number}"],
            notes="x" * 500,
        )

    digest = memory.digest(max_attempts=5, max_chars=900)

    assert len(digest["recent_attempts"]) < 5
    assert digest["omitted"]["attempts"] > 0


def test_problem_search_aggregates_methods_and_flags_reversals(
    tmp_path: Path,
) -> None:
    memory = ExperienceLedger(tmp_path / "experience.sqlite3")
    common = {
        "problem": "Concept bleed among A, B, and C",
        "tags": ["concept_bleed"],
    }
    for effectiveness in ("working", "working", "not_working"):
        memory.record_attempt(
            **common,
            method_steps=["train A", "train C", "train B"],
            outcome="succeeded",
            effectiveness=effectiveness,
        )
    for effectiveness in ("not_working", "not_working", "working"):
        memory.record_attempt(
            **common,
            method_steps=["train A", "train B", "train C"],
            outcome="succeeded",
            effectiveness=effectiveness,
        )
    memory.record_attempt(
        **common,
        method_steps=["train A only"],
        outcome="succeeded",
        effectiveness="unknown",
    )

    matches = memory.search_problems(
        "A B C concept bleed during curriculum", tags=["concept_bleed"]
    )

    assert len(matches) == 1
    methods = {tuple(item["steps"]): item for item in matches[0]["methods"]}
    acb = methods[("train A", "train C", "train B")]
    abc = methods[("train A", "train B", "train C")]
    unknown = methods[("train A only",)]
    assert acb["counts"]["working"] == 2
    assert acb["counts"]["not_working"] == 1
    assert abc["counts"]["working"] == 1
    assert abc["counts"]["not_working"] == 2
    assert unknown["observed_success_rate"] is None
    kinds = {item["kind"] for item in matches[0]["open_anomalies"]}
    assert kinds == {
        "failure_after_success_streak",
        "success_after_failure_streak",
    }
    digest = memory.digest(query="A B C concept bleed", max_attempts=2)
    assert digest["problem_matches"][0]["problem_id"] == matches[0]["problem_id"]
    assert all(
        item["problem_id"] == matches[0]["problem_id"]
        for item in digest["recent_attempts"]
    )

    anomaly = matches[0]["open_anomalies"][0]
    acknowledged = memory.acknowledge_anomaly(anomaly["anomaly_id"])
    assert acknowledged["status"] == "acknowledged"
    remaining = memory.search_problems("concept bleed A B C")[0]["open_anomalies"]
    assert len(remaining) == 1


def test_similar_problem_title_reuses_problem_record(tmp_path: Path) -> None:
    memory = ExperienceLedger(tmp_path / "experience.sqlite3")
    first = memory.record_attempt(
        problem="Concept bleed between apple banana cherry",
        method_steps=["apple", "banana", "cherry"],
    )
    second = memory.record_attempt(
        problem="Concept bleed between banana apple cherry",
        method_steps=["apple", "cherry", "banana"],
    )

    assert first["problem_id"] == second["problem_id"]
    match = memory.search_problems("apple banana cherry concept bleed")[0]
    assert len(match["aliases"]) == 1
    assert len(match["methods"]) == 2


def test_v1_database_is_migrated_and_backfilled(tmp_path: Path) -> None:
    path = tmp_path / "experience.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE attempts (
                attempt_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                problem TEXT NOT NULL,
                context_json TEXT NOT NULL,
                method_steps_json TEXT NOT NULL,
                outcome TEXT NOT NULL,
                effectiveness TEXT NOT NULL,
                evidence_refs_json TEXT NOT NULL,
                notes TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                source_plan_id TEXT UNIQUE
            );
            """
        )
        connection.execute(
            """
            INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "attempt-old",
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
                "Old recurring problem",
                "{}",
                json.dumps(["old method"]),
                "failed",
                "not_working",
                "[]",
                "",
                "[]",
                None,
            ),
        )

    memory = ExperienceLedger(path)
    old = memory.attempt("attempt-old")

    assert old["problem_id"].startswith("problem-")
    assert old["method_id"].startswith("method-")
    assert memory.search_problems("old recurring problem")[0]["methods"][0][
        "counts"
    ]["not_working"] == 1
