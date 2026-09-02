from __future__ import annotations

import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_hub.errors import SafetyError
from mission_hub.handlers.research_code import ResearchCodeChangeHandler
from mission_hub.handlers.research_decision import ResearchDecisionHandler
from mission_hub.handlers.visual_provider import ProviderFailure
from mission_hub.schema import load_schema, validate


ROOT = Path(__file__).resolve().parents[1]


def code_action() -> dict:
    return {
        "kind": "modify_code",
        "dataset_acquisition": None,
        "experiment_title": None,
        "hypothesis": None,
        "dataset_id": None,
        "epochs": None,
        "max_records_per_epoch": None,
        "order_policy": None,
        "order_seed": None,
        "intervention_type": None,
        "control_experiment_id": None,
        "max_sessions": None,
        "max_events_per_session": None,
        "controls": None,
        "code_change_title": "Expose development telemetry",
        "code_change_hypothesis": "Publication drops executor development events.",
        "code_change_objective": "Expose explicit counts and rejection reasons.",
        "code_change_acceptance_criteria": ["Every stage has an explicit count."],
        "code_change_scopes": ["telemetry"],
        "campaign_report": None,
        "next_campaign_title": None,
        "next_campaign_goal": None,
    }


def test_modify_code_is_valid_only_when_authoritative_state_allows_it() -> None:
    ResearchDecisionHandler._validate_semantics(
        {"action": code_action()}, ["launch_experiment", "modify_code", "conclude_campaign"],
    )
    with pytest.raises(ProviderFailure, match="outside the authoritative state boundary"):
        ResearchDecisionHandler._validate_semantics(
            {"action": code_action()}, ["wait"],
        )


def test_modify_code_requires_complete_bounded_fields() -> None:
    action = code_action()
    action["code_change_acceptance_criteria"] = None
    with pytest.raises(ProviderFailure, match="omitted a required bounded code-change field"):
        ResearchDecisionHandler._validate_semantics(
            {"action": action}, ["modify_code"],
        )


def test_dataset_acquisition_requires_a_coherent_public_adapter() -> None:
    action = code_action()
    action.update({
        "kind": "acquire_dataset",
        "dataset_acquisition": {
            "dataset_name": "wikipedia-v1",
            "source_url": "https://example.org/wiki.jsonl",
            "source_page_url": "https://example.org/wiki",
            "license": "CC-BY-SA-4.0",
            "expected_sha256": None,
            "max_download_bytes": 1024,
            "dataset_format": "jsonl",
            "archive_format": "none",
            "records_member": None,
            "modality": "text",
            "objective": "continuation",
            "text_field": "text",
            "prompt_field": None,
            "completion_field": None,
            "image_field": None,
            "caption_field": None,
        },
        "code_change_title": None,
        "code_change_hypothesis": None,
        "code_change_objective": None,
        "code_change_acceptance_criteria": None,
        "code_change_scopes": None,
    })
    ResearchDecisionHandler._validate_semantics(
        {"action": action}, ["acquire_dataset"],
    )
    response = {
        "action": action,
        "message": "I am acquiring this bounded dataset now.",
        "rationale": "It discriminates a data-volume hypothesis.",
        "updated_todo": {
            "focus": "Map data-volume behavior.",
            "current_hypothesis": "More independent records may change development evidence.",
            "next_questions": ["Does candidate formation change?"],
            "constraints": ["Knowledge, not improvement."],
        },
    }
    schema = load_schema(
        ROOT, "schemas/mission_hub/providers/research-decision.response.schema.json",
    )
    assert validate(response, schema) == []

    action["dataset_acquisition"]["text_field"] = None
    with pytest.raises(ProviderFailure, match="inconsistent"):
        ResearchDecisionHandler._validate_semantics(
            {"action": action}, ["acquire_dataset"],
        )


def test_code_scope_allows_experimental_telemetry_and_tests() -> None:
    roots = ResearchCodeChangeHandler.allowed_roots(["telemetry"])
    ResearchCodeChangeHandler.validate_changed_files([
        "campaign36c/development.py",
        "mission_hub/handlers/campaign36c.py",
        "tests/test_campaign36c_development.py",
    ], roots)


def test_code_scope_refuses_conductor_configuration_and_training_data() -> None:
    roots = ResearchCodeChangeHandler.allowed_roots(["telemetry"])
    for path in (
        "mission_hub/research_lab.py",
        "config/mission_hub/base.toml",
        "schemas/mission_hub/jobs/generic.output.schema.json",
        "training_data/v8_curriculum/README.md",
    ):
        with pytest.raises(SafetyError, match="escaped its authorized scope"):
            ResearchCodeChangeHandler.validate_changed_files(
                [path, "tests/test_campaign36c_development.py"], roots,
            )


def test_code_scope_allows_bounded_test_only_diagnostics() -> None:
    roots = ResearchCodeChangeHandler.allowed_roots(["telemetry"])
    ResearchCodeChangeHandler.validate_changed_files(
        ["tests/test_campaign36c_development.py"], roots,
    )


def test_regression_fixtures_are_isolated_and_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    workspace = tmp_path / "worktree"
    workspace.mkdir()

    campaign = repository / "config/mission_hub/campaigns/campaign.json"
    campaign.parent.mkdir(parents=True)
    campaign.write_text(json.dumps({
        "evaluation": "archive/evaluation.json",
        "material": "training_data/campaign/material",
    }) + "\n", encoding="utf-8")
    declared = {
        "archive/evaluation.json": "evaluation\n",
        "training_data/campaign/material/example.jsonl": "material\n",
        "archive/docs/history.md": "# History\n",
        "archive/registry.json": '{"registry": true}\n',
        "campaign36c/development.py": "canonical implementation\n",
        "config/mission_hub/campaign_material/README.md": "canonical readme\n",
        "config/mission_hub/campaign_material/campaign35/text.jsonl": "lesson\n",
    }
    for relative, body in declared.items():
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    research = repository / "mission_hub/research"
    (research / "intake").mkdir(parents=True)
    (research / "sources.json").write_text(json.dumps({
        "sources": [{"path": "archive/registry.json"}],
    }) + "\n", encoding="utf-8")
    (research / "intake/source-census.json").write_text(json.dumps({
        "candidates": [{"path": "archive/docs/history.md"}],
    }) + "\n", encoding="utf-8")

    existing_training = workspace / "training_data/v8_curriculum/README.md"
    existing_training.parent.mkdir(parents=True)
    existing_training.write_text("user curriculum\n", encoding="utf-8")
    existing_material = workspace / "config/mission_hub/campaign_material/README.md"
    existing_material.parent.mkdir(parents=True)
    existing_material.write_text("canonical readme\n", encoding="utf-8")
    candidate_source = workspace / "campaign36c/development.py"
    candidate_source.parent.mkdir(parents=True)
    candidate_source.write_text("Sol candidate implementation\n", encoding="utf-8")
    monkeypatch.setattr(
        "mission_hub.handlers.research_code.load_config_bundle",
        lambda _path: SimpleNamespace(recovery={"source_repository_root": str(repository)}),
    )

    handler = ResearchCodeChangeHandler()
    monkeypatch.setattr(handler, "_git_bytes", lambda _root, *_args: b"\0".join((
        b"campaign36c/development.py",
        b"config/mission_hub/campaign_material/README.md",
        b"training_data/v8_curriculum/README.md",
        b"",
    )))
    with handler._regression_fixtures(workspace):
        for relative in declared:
            target = workspace / relative
            assert target.is_file()
        assert candidate_source.read_text(encoding="utf-8") == "Sol candidate implementation\n"
        (workspace / "archive/evaluation.json").write_text("mutated\n", encoding="utf-8")
        assert (repository / "archive/evaluation.json").read_text(encoding="utf-8") == "evaluation\n"

    assert existing_training.read_text(encoding="utf-8") == "user curriculum\n"
    assert existing_material.read_text(encoding="utf-8") == "canonical readme\n"
    assert candidate_source.read_text(encoding="utf-8") == "Sol candidate implementation\n"
    assert not (workspace / "archive").exists()
    assert not (workspace / "training_data/campaign").exists()
    assert not (workspace / "config/mission_hub/campaign_material/campaign35").exists()


def test_registered_candidate_hash_is_refreshed_only_from_matching_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "worktree"
    source = workspace / "campaign36c/development.py"
    source.parent.mkdir(parents=True)
    source.write_text("candidate\n", encoding="utf-8")
    base = b"base\n"
    registry = workspace / "mission_hub/research/sources.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({
        "schema_version": "ninereeds_research_source_registry_v1",
        "sources": [{
            "id": "development", "path": "campaign36c/development.py",
            "sha256": hashlib.sha256(base).hexdigest(),
        }],
    }) + "\n", encoding="utf-8")
    handler = ResearchCodeChangeHandler()
    monkeypatch.setattr(handler, "_git_bytes", lambda _root, *_args: base)

    changed = handler._refresh_registered_source_hashes(
        workspace, ["campaign36c/development.py"],
    )

    assert changed == ["mission_hub/research/sources.json"]
    refreshed = json.loads(registry.read_text(encoding="utf-8"))
    assert refreshed["sources"][0]["sha256"] == hashlib.sha256(b"candidate\n").hexdigest()


def test_registered_candidate_hash_refuses_a_stale_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "worktree"
    source = workspace / "campaign36c/development.py"
    source.parent.mkdir(parents=True)
    source.write_text("candidate\n", encoding="utf-8")
    registry = workspace / "mission_hub/research/sources.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({
        "sources": [{
            "path": "campaign36c/development.py", "sha256": "0" * 64,
        }],
    }) + "\n", encoding="utf-8")
    handler = ResearchCodeChangeHandler()
    monkeypatch.setattr(handler, "_git_bytes", lambda _root, *_args: b"base\n")

    with pytest.raises(SafetyError, match="registry was stale before"):
        handler._refresh_registered_source_hashes(
            workspace, ["campaign36c/development.py"],
        )
