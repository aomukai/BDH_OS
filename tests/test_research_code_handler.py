from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_hub.errors import SafetyError
from mission_hub.handlers.research_code import ResearchCodeChangeHandler
from mission_hub.handlers.research_decision import ResearchDecisionHandler
from mission_hub.handlers.visual_provider import ProviderFailure


def code_action() -> dict:
    return {
        "kind": "modify_code",
        "experiment_title": None,
        "hypothesis": None,
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


def test_code_scope_refuses_test_only_activity() -> None:
    roots = ResearchCodeChangeHandler.allowed_roots(["telemetry"])
    with pytest.raises(SafetyError, match="without experimental source"):
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
    monkeypatch.setattr(
        "mission_hub.handlers.research_code.load_config_bundle",
        lambda _path: SimpleNamespace(recovery={"source_repository_root": str(repository)}),
    )

    handler = ResearchCodeChangeHandler()
    with handler._regression_fixtures(workspace):
        for relative in declared:
            target = workspace / relative
            assert target.is_file()
        (workspace / "archive/evaluation.json").write_text("mutated\n", encoding="utf-8")
        assert (repository / "archive/evaluation.json").read_text(encoding="utf-8") == "evaluation\n"

    assert existing_training.read_text(encoding="utf-8") == "user curriculum\n"
    assert existing_material.read_text(encoding="utf-8") == "canonical readme\n"
    assert not (workspace / "archive").exists()
    assert not (workspace / "training_data/campaign").exists()
    assert not (workspace / "config/mission_hub/campaign_material/campaign35").exists()
