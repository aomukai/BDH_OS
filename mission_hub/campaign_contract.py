"""Purpose-sensitive campaign and evaluation contracts."""

from __future__ import annotations

from typing import Any

from .errors import SafetyError
from .jsonutil import content_hash


CONTRACT_SCHEMA = "ninereeds_campaign_contract_v1"
EVALUATION_CONTEXT_SCHEMA = "ninereeds_evaluation_context_v1"
EVALUATION_PHASES = {
    "bootstrap_milestone", "advancement_checkpoint", "experimental_observation",
    "evolutionary_branch", "merge_specialist", "post_merge",
}
CONTRACT_FIELDS = {
    "schema_version", "mode", "development_stage", "purpose",
    "success_criteria", "failure_criteria", "expected_regressions", "branches",
    "merge_sources", "target_capabilities", "bootstrap_milestones",
    "hypothesis", "observations_sought",
}


def validate_campaign_contract(contract: Any, modes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(contract, dict) or set(contract) != CONTRACT_FIELDS:
        raise SafetyError("campaign requires one complete versioned training-purpose contract")
    if contract["schema_version"] != CONTRACT_SCHEMA:
        raise SafetyError("unsupported campaign training-purpose contract")
    mode_id = contract["mode"]
    mode = modes.get(mode_id)
    if mode is None:
        raise SafetyError(f"unknown campaign training mode: {mode_id}")
    for field in ("development_stage", "purpose"):
        if not isinstance(contract[field], str) or not contract[field].strip():
            raise SafetyError(f"campaign contract {field} must be non-empty text")
    for field in (
        "success_criteria", "failure_criteria", "expected_regressions", "branches",
        "merge_sources", "target_capabilities", "bootstrap_milestones", "observations_sought",
    ):
        values = contract[field]
        if not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values):
            raise SafetyError(f"campaign contract {field} must be a string list")
        if len(values) != len(set(values)):
            raise SafetyError(f"campaign contract {field} contains duplicates")
    if not contract["success_criteria"] or not contract["failure_criteria"]:
        raise SafetyError("campaign success and failure must be defined before work begins")
    if not isinstance(contract["hypothesis"], str):
        raise SafetyError("campaign hypothesis must be text")
    if len(contract["branches"]) < mode["minimum_branches"]:
        raise SafetyError(f"campaign mode {mode_id} requires at least {mode['minimum_branches']} declared branches")
    if len(contract["merge_sources"]) < mode["minimum_merge_sources"]:
        raise SafetyError(f"campaign mode {mode_id} requires at least {mode['minimum_merge_sources']} merge sources")
    requirements = {
        "bootstrap": ("bootstrap_milestones",),
        "advancement": ("target_capabilities",),
        "experimental": ("hypothesis", "observations_sought"),
        "evolutionary": ("hypothesis", "observations_sought"),
        "merge": ("hypothesis", "observations_sought", "merge_sources"),
    }
    for field in requirements[mode_id]:
        if not contract[field]:
            raise SafetyError(f"campaign mode {mode_id} requires {field}")
    if mode_id != "merge" and contract["merge_sources"]:
        raise SafetyError("merge sources are only valid for merge campaigns")
    return contract


def campaign_contract_sha256(contract: dict[str, Any]) -> str:
    return content_hash(contract)


def expected_evaluation_context(
    contract: dict[str, Any],
    modes: dict[str, dict[str, Any]],
    *,
    phase: str,
    branch_id: str | None,
    all_required_branches_complete: bool,
    branch_complete: bool = True,
) -> dict[str, Any]:
    validate_campaign_contract(contract, modes)
    if phase not in EVALUATION_PHASES:
        raise SafetyError(f"unknown evaluation phase: {phase}")
    mode = modes[contract["mode"]]
    expected_phase = {
        "bootstrap": {"bootstrap_milestone"},
        "advancement": {"advancement_checkpoint"},
        "experimental": {"experimental_observation"},
        "evolutionary": {"evolutionary_branch"},
        "merge": {"merge_specialist", "post_merge"},
    }[contract["mode"]]
    if phase not in expected_phase:
        raise SafetyError(f"evaluation phase {phase} is incompatible with campaign mode {contract['mode']}")
    if phase in {"evolutionary_branch", "merge_specialist"}:
        allowed = contract["branches"] if phase == "evolutionary_branch" else contract["merge_sources"]
        if branch_id not in allowed:
            raise SafetyError("evaluation branch/source is not declared by the campaign")
    elif branch_id is not None:
        raise SafetyError("this evaluation phase does not accept a branch ID")
    return {
        "schema_version": EVALUATION_CONTEXT_SCHEMA,
        "campaign_contract_sha256": campaign_contract_sha256(contract),
        "mode": contract["mode"],
        "development_stage": contract["development_stage"],
        "phase": phase,
        "branch_id": branch_id,
        "branch_complete": branch_complete,
        "all_required_branches_complete": all_required_branches_complete,
        "purpose": contract["purpose"],
        "success_criteria": contract["success_criteria"],
        "failure_criteria": contract["failure_criteria"],
        "expected_regressions": contract["expected_regressions"],
        "bootstrap_milestones": contract["bootstrap_milestones"],
        "target_capabilities": contract["target_capabilities"],
        "observations_sought": contract["observations_sought"],
        "mode_policy": {
            "improvement_required": mode["improvement_required"],
            "allows_expected_regression": mode["allows_expected_regression"],
            "comparison_scope": mode["comparison_scope"],
            "candidate_disposition": mode["candidate_disposition"],
            "required_evidence": mode["required_evidence"],
        },
    }
