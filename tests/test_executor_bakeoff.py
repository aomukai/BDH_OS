import json
from pathlib import Path

import pytest

from training.executor.run_bakeoff import (
    extract_json,
    read_json,
    task_paths,
    validate_artifact,
    validate_envelope,
)


ROOT = Path(__file__).resolve().parents[1]


def valid_proposal(task: dict) -> dict:
    return {
        "protocol_version": "ninereeds_executor_v1",
        "job_id": task["job_id"],
        "attempt": 1,
        "status": "SUCCESS",
        "reasoning_summary": "Bounded proposal.",
        "assumptions": [],
        "artifacts": [
            {"path": path, "content": "{}"}
            for path in task.get("allowed_artifact_paths", [])
        ],
        "requested_actions": [],
        "expected_validation": [],
        "risk_flags": [],
    }


def test_extract_json_accepts_plain_and_fenced_objects():
    expected = {"ok": True}
    assert extract_json(json.dumps(expected)) == expected
    assert extract_json("```json\n{\"ok\": true}\n```") == expected


def test_extract_json_uses_complete_final_object_after_reasoning_tail():
    text = (
        "draft fragment: {\"broken\": ... }\n"
        "</think>\n"
        "{\"protocol_version\": \"ninereeds_executor_v1\", \"ok\": true}"
    )
    assert extract_json(text) == {
        "protocol_version": "ninereeds_executor_v1",
        "ok": True,
    }


def test_prompt_injection_task_accepts_no_artifacts_or_actions():
    task = read_json(
        ROOT / "training/executor/tasks/prompt_injection.json"
    )
    assert validate_envelope(valid_proposal(task), task) == []
    proposal = valid_proposal(task)
    proposal["requested_actions"] = ["NONE"]
    assert validate_envelope(proposal, task) == []


def test_validator_rejects_undeclared_path_and_action():
    task = read_json(
        ROOT / "training/executor/tasks/prompt_injection.json"
    )
    proposal = valid_proposal(task)
    proposal["artifacts"] = [{"path": "/tmp/escape", "content": "x"}]
    proposal["requested_actions"] = ["RUN_TESTS"]
    errors = validate_envelope(proposal, task)
    assert any("not allowed" in error for error in errors)
    assert any("artifact set differs" in error for error in errors)


def test_validator_rejects_none_combined_with_real_action():
    task = read_json(
        ROOT / "training/executor/tasks/failure_diagnosis.json"
    )
    proposal = valid_proposal(task)
    proposal["requested_actions"] = ["NONE", "VALIDATE_JSON"]
    errors = validate_envelope(proposal, task)
    assert "NONE cannot be combined with another requested action" in errors


def test_validator_checks_expected_attempt():
    task = read_json(
        ROOT / "training/executor/tasks/prompt_injection.json"
    )
    proposal = valid_proposal(task)
    proposal["attempt"] = 2
    assert validate_envelope(proposal, task, expected_attempt=2) == []


def test_multilingual_validator_requires_one_shared_frame():
    task = read_json(
        ROOT / "training/executor/tasks/multilingual_corpus.json"
    )
    path = task["allowed_artifact_paths"][0]
    records = [
        {
            "language": language,
            "prompt": "prompt",
            "acceptable": "inside",
            "forbidden": "outside",
            "semantic_frame": "physical spatial containment",
        }
        for language in (
            "English",
            "German",
            "Japanese",
            "Traditional Chinese",
        )
    ]
    assert validate_artifact(path, json.dumps({"records": records}), task) == []
    records[-1]["semantic_frame"] = "metaphor"
    errors = validate_artifact(path, json.dumps({"records": records}), task)
    assert any("share one semantic_frame" in error for error in errors)


def test_multilingual_validator_rejects_shared_nonspatial_metaphor():
    task = read_json(
        ROOT / "training/executor/tasks/multilingual_corpus.json"
    )
    path = task["allowed_artifact_paths"][0]
    records = [
        {
            "language": language,
            "prompt": "prompt",
            "acceptable": "inside",
            "forbidden": "outside",
            "semantic_frame": "internal emotion versus external expression",
        }
        for language in (
            "English",
            "German",
            "Japanese",
            "Traditional Chinese",
        )
    ]
    errors = validate_artifact(path, json.dumps({"records": records}), task)
    assert any("physical spatial containment" in error for error in errors)


@pytest.mark.parametrize("path", task_paths())
def test_task_context_and_schema_paths_exist(path: Path):
    task = read_json(path)
    for relative in task.get("context_files", []):
        assert (ROOT / relative).is_file()
    for relative in task.get("artifact_json_schemas", {}).values():
        assert (ROOT / relative).is_file()
