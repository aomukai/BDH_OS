from __future__ import annotations

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
