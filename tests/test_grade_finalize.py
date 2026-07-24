from __future__ import annotations

import json
from pathlib import Path

from tests.test_msm_trainer import script
from training.pipeline.control.grade_finalize import finalize_grade


ROOT = Path(__file__).resolve().parents[1]


def setup_session(tmp_path: Path) -> tuple[Path, str, str, str]:
    repo = tmp_path / "repo"
    pipeline = repo / "training/pipeline"
    session = pipeline / "msm/sessions/session-test"
    session.mkdir(parents=True)
    (pipeline / "grading_result_schema.json").write_bytes(
        (ROOT / "training/pipeline/grading_result_schema.json").read_bytes()
    )
    fixed = script()
    script_path = "training/pipeline/msm/sessions/session-test/script.json"
    raw_path = "training/pipeline/msm/sessions/session-test/raw_chat.jsonl"
    grade_path = "training/pipeline/msm/sessions/session-test/grading_result.json"
    (repo / script_path).write_text(json.dumps(fixed), encoding="utf-8")
    events = [
        {
            "session_id": fixed["session_id"],
            "sequence_index": index,
            "item_id": "item-1",
            "event_type": event_type,
        }
        for index, event_type in enumerate(
            [
                "user_prompt",
                "ninereeds_original_answer",
                "teacher_correction",
                "ninereeds_after_correction_answer",
            ]
        )
    ]
    (repo / raw_path).write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )
    return repo, script_path, raw_path, grade_path


def proposed(*, original: str = "correct", confidence: float = 0.95) -> dict:
    return {
        "schema_version": "msm_grading_result_v1",
        "session_id": "session-test",
        "script_id": "script-test",
        "item_grades": [
            {
                "item_id": "item-1",
                "original_status": original,
                "after_correction_status": "correct",
                "malformed": False,
                "repetition_collapse": False,
                "rationale": "The answer matches the fixed expectation.",
                "confidence": confidence,
            }
        ],
        "recommended_action": "PASS_AUTONEXT",
        "next_focus": ["spatial contrast"],
        "failure_modes": [],
        "requires_orchestrator": False,
        "summary": "The bounded session passed.",
    }


def test_grade_finalizer_writes_canonical_evidence_and_replays(tmp_path: Path) -> None:
    repo, script_path, raw_path, grade_path = setup_session(tmp_path)
    grade, hashes = finalize_grade(
        proposed(),
        repo_root=repo,
        script_path=script_path,
        raw_log_path=raw_path,
        artifact_path=grade_path,
    )
    assert grade["decision"] == "PASS_AUTONEXT"
    assert grade["session_passed"] is True
    assert set(hashes) == {
        grade_path,
        "training/pipeline/msm/sessions/session-test/turn_grades.jsonl",
        "training/pipeline/msm/sessions/session-test/report.md",
    }
    replay, replay_hashes = finalize_grade(
        proposed(),
        repo_root=repo,
        script_path=script_path,
        raw_log_path=raw_path,
        artifact_path=grade_path,
    )
    assert replay == grade
    assert replay_hashes == hashes


def test_grade_finalizer_overrides_unsafe_autonext(tmp_path: Path) -> None:
    repo, script_path, raw_path, grade_path = setup_session(tmp_path)
    grade, _ = finalize_grade(
        proposed(original="wrong_off_topic"),
        repo_root=repo,
        script_path=script_path,
        raw_log_path=raw_path,
        artifact_path=grade_path,
    )
    assert grade["model_recommended_action"] == "PASS_AUTONEXT"
    assert grade["decision"] == "ESCALATE_ORCHESTRATOR"
    assert grade["session_passed"] is False
