import json
from pathlib import Path

import pytest

from training.executor.run_bakeoff import (
    extract_json,
    read_json,
    task_paths,
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


def test_prompt_injection_task_accepts_no_artifacts_or_actions():
    task = read_json(
        ROOT / "training/executor/tasks/prompt_injection.json"
    )
    assert validate_envelope(valid_proposal(task), task) == []


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


@pytest.mark.parametrize("path", task_paths())
def test_task_context_and_schema_paths_exist(path: Path):
    task = read_json(path)
    for relative in task.get("context_files", []):
        assert (ROOT / relative).is_file()
    for relative in task.get("artifact_json_schemas", {}).values():
        assert (ROOT / relative).is_file()
