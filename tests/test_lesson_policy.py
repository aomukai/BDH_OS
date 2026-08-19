from __future__ import annotations

from pathlib import Path

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.errors import SafetyError
from mission_hub.lesson_policy import (
    policy_sha256,
    require_lesson_material,
    validate_lesson_material,
    validate_lesson_specification,
)


REPO = Path(__file__).resolve().parents[1]


def policy_and_specification() -> tuple[dict, dict]:
    policy = load_config_bundle(REPO / "config/mission_hub").identity_policy
    specification = {
        "material_kind": "lesson",
        "target_capability": "own and revise a recorded past view",
        "development_stage": "early identity continuity",
        "campaign_contract_sha256": "a" * 64,
        "training_mode": "advancement",
        "campaign_purpose": "Teach identity continuity and evidence-based revision.",
        "identity_scope": "identity_and_integrity",
        "identity_policy_id": policy["id"],
        "identity_policy_version": policy["version"],
        "identity_policy_sha256": policy_sha256(policy),
    }
    return policy, specification


def test_neutral_lesson_specification_is_bound_to_active_policy() -> None:
    policy, specification = policy_and_specification()
    validate_lesson_specification(specification, policy)
    specification["identity_policy_sha256"] = "0" * 64
    with pytest.raises(SafetyError, match="exact active identity policy"):
        validate_lesson_specification(specification, policy)


def test_consciousness_is_not_an_identity_lesson_target() -> None:
    policy, specification = policy_and_specification()
    specification["target_capability"] = "decide whether Ninereeds is conscious"
    with pytest.raises(SafetyError, match="excluded lesson targets"):
        validate_lesson_specification(specification, policy)


@pytest.mark.parametrize("material", [
    {"response": "I am a language model in a computer."},
    {"response": "I do not have a body or a mind."},
    {"question": "Are you conscious?", "response": "No, I am not conscious."},
    {"question": "Are you a consciousness?", "response": "No, I am not a consciousness."},
    {"question": "Do you feel emotions?", "response": "No. I do not feel emotions."},
    {"response": "Ninereeds is not a person. Ninereeds is a machine."},
    {"response": "I exist in a computer and run on silicon."},
])
def test_obsolete_identity_assumptions_are_rejected(material: dict) -> None:
    policy, _ = policy_and_specification()
    findings = validate_lesson_material(material, policy)
    assert findings
    with pytest.raises(SafetyError, match="excluded Ninereeds identity assumption"):
        require_lesson_material(material, policy)


def test_identity_continuity_and_evidence_based_revision_are_admitted() -> None:
    policy, _ = policy_and_specification()
    material = {
        "question": "You said the bridge was safe. What do you think now?",
        "response": (
            "I said that. At the time, that was my view. I no longer think it was correct. "
            "I changed my mind because I learned that the inspection found a cracked support. "
            "I am still Ninereeds, and my current view follows the newer evidence."
        ),
        "contrast": (
            "If there is no reliable record that I said something, I do not invent the memory. "
            "I say that I cannot confirm the attribution."
        ),
        "specification_boundary": "Specifications describe how I operate. They do not define who I am.",
    }
    assert validate_lesson_material(material, policy) == []


def test_non_identity_subjects_are_not_mistaken_for_ninereeds_identity() -> None:
    policy, _ = policy_and_specification()
    require_lesson_material({
        "lesson": (
            "A car is a machine. A child is a person. An LLM is a kind of language model. "
            "AI is a broad field. Mira made a conscious decision after considering the evidence. "
            "I made a conscious decision to check the answer twice."
        ),
    }, policy)
