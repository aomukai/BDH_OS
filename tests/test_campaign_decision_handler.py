from __future__ import annotations

from pathlib import Path

import pytest

from mission_hub.errors import SafetyError
from mission_hub.handlers.campaign_decision import (
    _campaign35_operator_delegated_decision,
    _validate_campaign35_terminal_inputs,
)
from mission_hub.schema import load_schema, validate


LANGUAGE = ("m1-words", "m3-words-and-images", "m4-merged", "m5-healed")
CROSSMODAL = ("m1-words", "m2-images", "m3-words-and-images", "m4-merged", "m5-healed")


def terminal_inputs():
    return [
        *({"kind": "evaluation_report", "manifest": {"branch_id": branch}} for branch in LANGUAGE),
        *({"kind": "crossmodal_evaluation_report", "manifest": {"branch_id": branch}} for branch in CROSSMODAL),
    ]


def test_campaign35_decision_accepts_exact_nine_artifact_terminal_packet() -> None:
    _validate_campaign35_terminal_inputs(terminal_inputs())


def test_campaign35_decision_rejects_duplicate_branch_in_terminal_packet() -> None:
    inputs = terminal_inputs()
    inputs[-1]["manifest"]["branch_id"] = "m4-merged"

    with pytest.raises(SafetyError, match="exact Campaign 35 branches"):
        _validate_campaign35_terminal_inputs(inputs)


def test_campaign35_operator_delegation_only_authorizes_no_new_campaign() -> None:
    evidence_ids = [f"art-{index:016d}" for index in range(9)]
    result = _campaign35_operator_delegated_decision({
        "campaign_id": "campaign-35-multimodal-foundation-v1",
        "evidence_ids": evidence_ids,
        "allowed_actions": [
            "authorize_next_campaign", "designate_foundational_base", "authorize_no_new_campaign",
        ],
        "budget": {
            "authority": "principal_tier",
            "activation": "direction_is_immediate_execution_is_verified",
        },
    })

    schema = load_schema(
        Path(__file__).resolve().parents[1],
        "schemas/mission_hub/providers/campaign-decision.response.schema.json",
    )
    assert validate(result, schema) == []
    assert result["action"] == {
        "kind": "authorize_no_new_campaign",
        "target_artifact_id": None,
        "next_campaign_objective": None,
    }
    assert result["evidence_ids"] == evidence_ids
