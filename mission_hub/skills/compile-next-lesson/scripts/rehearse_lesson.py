#!/usr/bin/env python3
"""Offline, fail-closed lesson rehearsal harness for Luna teacher and Sol learner roles."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any


SPEC_VERSION = "ninereeds_lesson_rehearsal_spec_v1"
EVENT_VERSION = "ninereeds_lesson_rehearsal_event_v1"
VERDICT_VERSION = "ninereeds_lesson_rehearsal_verdict_v1"
REVIEW_PACKET_VERSION = "ninereeds_lesson_rehearsal_review_packet_v1"
REPORTER_PACKET_VERSION = "ninereeds_lesson_rehearsal_reporter_packet_v1"
STATE_VERSION = "ninereeds_lesson_rehearsal_state_v1"
MANIFEST_VERSION = "ninereeds_lesson_rehearsal_manifest_v1"
SUITE_VERSION = "ninereeds_lesson_rehearsal_suite_v1"
SUITE_RECEIPT_VERSION = "ninereeds_lesson_rehearsal_suite_receipt_v1"
LUNA_REPORT_VERSION = "ninereeds_luna_post_lesson_report_v1"
ZERO_HASH = "0" * 64
SHA256 = __import__("re").compile(r"^[0-9a-f]{64}$")
PHASE_ORDER = (
    "presentation", "affirmative", "negative", "W_question", "OR_question", "reciprocity",
    "mixed_practice", "picture_book", "comprehension", "transfer", "closing_recap",
)


def execution_position(lesson: dict[str, Any], phase: str, exercise_id: str) -> tuple[int, int]:
    """Map locally bound presentations and their tests into executable order."""
    phases = lesson.get("phases", {})
    sequence = phases.get("execution_sequence") if isinstance(phases, dict) else None
    if isinstance(sequence, list):
        for block_index, block in enumerate(sequence):
            if not isinstance(block, dict) or block.get("phase") != phase:
                continue
            ids = block.get("exercise_ids")
            if isinstance(ids, list) and exercise_id in ids:
                # Leave one executable slot after each controlled base item for its
                # optional PRESENT_AGAIN cold retest.
                return (block_index, ids.index(exercise_id) * 2)
        dispatches = lesson.get("adaptive", {}).get("present_again", {}).get("dispatch_table", {})
        if isinstance(dispatches, dict):
            for base_id, dispatch in dispatches.items():
                if not isinstance(dispatch, dict) or dispatch.get("gate") != phase:
                    continue
                if dispatch.get("cold_retest_exercise_id") != exercise_id:
                    continue
                for block_index, block in enumerate(sequence):
                    ids = block.get("exercise_ids", []) if isinstance(block, dict) else []
                    if block.get("phase") == phase and isinstance(ids, list) and base_id in ids:
                        return (block_index, ids.index(base_id) * 2 + 1)
        train_more = lesson.get("adaptive", {}).get("train_more", {})
        reserve_exercises = train_more.get("reserve_exercises", [])
        if isinstance(reserve_exercises, list):
            gate_config = train_more.get("gate_execution", {}).get(phase, {})
            phase_reserves = gate_config.get("reserve_exercise_ids", []) if isinstance(gate_config, dict) else []
            if not phase_reserves:
                legacy_prefix = {
                    "affirmative": "aff", "negative": "neg", "W_question": "who",
                    "OR_question": "or", "reciprocity": "recip",
                }.get(phase)
                phase_reserves = [
                    item.get("id") for item in reserve_exercises
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                    and legacy_prefix is not None and item["id"].startswith(legacy_prefix + "-")
                ]
            if exercise_id in phase_reserves:
                for block_index, block in enumerate(sequence):
                    if isinstance(block, dict) and block.get("phase") == phase:
                        base_ids = block.get("exercise_ids", [])
                        base_count = len(base_ids) if isinstance(base_ids, list) else 0
                        return (block_index, base_count * 2 + phase_reserves.index(exercise_id))
        raise ValueError("event exercise is not present in the frozen execution sequence")
    bindings = phases.get("presentation_bindings") if isinstance(phases, dict) else None
    if not isinstance(bindings, dict):
        return (PHASE_ORDER.index(phase), 0)
    gates = [
        gate for gate in ("affirmative", "negative", "W_question", "OR_question", "reciprocity")
        if gate in bindings
    ]
    if phase == "presentation":
        for index, gate in enumerate(gates):
            if exercise_id in bindings.get(gate, []):
                return (index, 0)
        raise ValueError("presentation exercise is not bound to a local controlled gate")
    if phase in gates:
        return (gates.index(phase), 1)
    tail = {"mixed_practice": 0, "picture_book": 1, "comprehension": 2, "transfer": 3, "closing_recap": 3}
    if phase in tail:
        return (len(gates) + tail[phase], 0)
    raise ValueError("event phase has no executable position")
ALLOWED_TOOLS = {
    "SHOW_ASSET", "SHOW_CROP", "SHOW_HIGHLIGHT", "REPLAY_PRESENTATION",
    "USE_MARKERS", "ASK_BOUNDED_CLARIFICATION", "CHECK_UNDERSTANDING", "ALARM",
    "PRESENT_AGAIN", "TRAIN_MORE", "TRAIN_LONGER", "REPLAY_LESSON", "FINISH",
}
TEACHING_ACTIONS = {"present", "ask", "feedback", "scaffold", "correction", "transition"}
ALARM_CODES = {
    "lesson_contract_contradiction", "missing_visual_operation", "visual_claim_failed",
    "ambiguous_focus", "missing_prerequisite", "answer_contract_inadequate",
    "learner_behavior_outside_protocol", "teacher_authority_insufficient",
    "learner_catastrophic_collapse", "learner_perseveration_loop",
    "learner_output_degeneration", "learner_state_discontinuity",
    "learner_concept_bleed", "learner_prompt_pressure_echo",
    "tool_contract_failure", "phase_or_budget_violation", "identity_or_chronology_risk",
    "teacher_language_not_understood", "unexpected_runtime_failure", "manual_operator_stop",
}
FAILURE_CATEGORIES = {
    "lesson_plan", "visual_material", "luna_routine", "sol_simulation",
    "harness", "verifier", "infrastructure", "unresolved",
}
REVIEW_DIMENSIONS = {
    "lesson_plan_waterproof", "point_topic_integrity", "material_scope_judgment", "structural_completeness",
    "picture_book_application", "luna_routine", "intervention_judgment",
    "teacher_self_assessment_calibration",
    "teacher_language_closure", "developmental_stage_fidelity", "protocol_integrity",
    "visual_grounding", "learner_simulation_fidelity",
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_path(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return value


def exact_keys(value: dict[str, Any], keys: set[str], where: str) -> None:
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    if missing or extra:
        parts = [*(f"missing {item}" for item in missing), *(f"unknown {item}" for item in extra)]
        raise ValueError(f"{where}: " + "; ".join(parts))


def require_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: must be a non-empty string")
    return value


def resolve_bound_path(raw: Any, *, base: Path, expected: Any, where: str) -> Path:
    raw = require_string(raw, f"{where}.path")
    if not isinstance(expected, str) or SHA256.fullmatch(expected) is None:
        raise ValueError(f"{where}.sha256: must be lowercase SHA-256")
    path = Path(raw)
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"{where}.path: file does not exist: {path}")
    if digest_path(path) != expected:
        raise ValueError(f"{where}.sha256: does not match file")
    return path


def _actor(value: Any, role: str, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: must be an object")
    exact_keys(value, {"role", "model_id", "reasoning_effort", "prompt_sha256"}, where)
    if value.get("role") != role:
        raise ValueError(f"{where}.role: must equal {role}")
    require_string(value.get("model_id"), f"{where}.model_id")
    if value.get("reasoning_effort") not in {"low", "medium", "high", "xhigh", "max"}:
        raise ValueError(f"{where}.reasoning_effort is invalid")
    if not isinstance(value.get("prompt_sha256"), str) or SHA256.fullmatch(value["prompt_sha256"]) is None:
        raise ValueError(f"{where}.prompt_sha256: must be lowercase SHA-256")
    return value


def validate_spec(spec: dict[str, Any], spec_path: Path) -> tuple[Path, dict[str, Any]]:
    keys = {
        "schema_version", "rehearsal_id", "lesson_path", "lesson_sha256", "scenario_id",
        "random_seed", "luna", "sol", "verifier", "learner_profile", "required_phases",
        "luna_reporter",
        "allowed_tools", "budgets", "parent_run_manifest_path", "parent_run_manifest_sha256",
        "repair_receipt_path", "repair_receipt_sha256", "teacher_language_policy",
        "review_wiki_bindings", "effort_escalation",
    }
    exact_keys(spec, keys, "spec")
    if spec.get("schema_version") != SPEC_VERSION:
        raise ValueError(f"spec.schema_version must equal {SPEC_VERSION}")
    require_string(spec.get("rehearsal_id"), "spec.rehearsal_id")
    require_string(spec.get("scenario_id"), "spec.scenario_id")
    if not isinstance(spec.get("random_seed"), int) or isinstance(spec.get("random_seed"), bool) or spec["random_seed"] < 0:
        raise ValueError("spec.random_seed must be a non-negative integer")
    lesson_path = resolve_bound_path(
        spec.get("lesson_path"), base=spec_path.parent,
        expected=spec.get("lesson_sha256"), where="spec.lesson",
    )
    lesson = load_object(lesson_path)
    if lesson.get("schema_version") not in {"ninereeds_lesson_contract_v2", "ninereeds_lesson_contract_v3"}:
        raise ValueError("spec.lesson: unsupported lesson contract")
    _actor(spec.get("luna"), "luna_teacher", "spec.luna")
    _actor(spec.get("luna_reporter"), "luna_post_lesson_analyst", "spec.luna_reporter")
    _actor(spec.get("sol"), "sol_learner_simulator", "spec.sol")
    effort = spec.get("effort_escalation")
    if not isinstance(effort, dict):
        raise ValueError("spec.effort_escalation must be an object")
    exact_keys(effort, {"target_role", "ladder", "attempt_index", "current_effort", "max_failure_outcome"}, "spec.effort_escalation")
    ladder = ["medium", "high", "xhigh", "max"]
    if effort.get("ladder") != ladder:
        raise ValueError("spec.effort_escalation.ladder must preserve medium-high-xhigh-max")
    index = effort.get("attempt_index")
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(ladder):
        raise ValueError("spec.effort_escalation.attempt_index must be in 0..3")
    if isinstance(index, int) and not isinstance(index, bool) and effort.get("current_effort") != ladder[index]:
        raise ValueError("spec.effort_escalation.current_effort does not match its ladder rung")
    target = effort.get("target_role")
    target_config = spec.get("luna") if target == "lesson_conductor" else spec.get("luna_reporter") if target == "post_lesson_analyst" else None
    if target_config is None or target_config.get("reasoning_effort") != effort.get("current_effort"):
        raise ValueError("spec.effort_escalation target actor does not use current_effort")
    if effort.get("max_failure_outcome") != "terminal_model_capability_failure":
        raise ValueError("spec.effort_escalation.max_failure_outcome is invalid")
    verifier = spec.get("verifier")
    if not isinstance(verifier, dict):
        raise ValueError("spec.verifier must be an object")
    exact_keys(verifier, {"role", "reviewer_id", "model_id", "prompt_sha256", "rubric_sha256", "context_policy"}, "spec.verifier")
    if verifier.get("role") != "sol_independent_reviewer":
        raise ValueError("spec.verifier.role must equal sol_independent_reviewer")
    require_string(verifier.get("reviewer_id"), "spec.verifier.reviewer_id")
    require_string(verifier.get("model_id"), "spec.verifier.model_id")
    if verifier.get("context_policy") != "fresh_context_anonymized_actors_lesson_level_script_log_and_wiki":
        raise ValueError("spec.verifier must use a fresh anonymized evidence-only context")
    if not isinstance(verifier.get("prompt_sha256"), str) or SHA256.fullmatch(verifier["prompt_sha256"]) is None:
        raise ValueError("spec.verifier.prompt_sha256 must be lowercase SHA-256")
    if not isinstance(verifier.get("rubric_sha256"), str) or SHA256.fullmatch(verifier["rubric_sha256"]) is None:
        raise ValueError("spec.verifier.rubric_sha256 must be lowercase SHA-256")
    wiki = spec.get("review_wiki_bindings")
    if not isinstance(wiki, list) or not wiki:
        raise ValueError("spec.review_wiki_bindings must be a non-empty array")
    wiki_roles: set[str] = set()
    for index, item in enumerate(wiki):
        if not isinstance(item, dict):
            raise ValueError(f"spec.review_wiki_bindings[{index}] must be an object")
        exact_keys(item, {"role", "path", "sha256"}, f"spec.review_wiki_bindings[{index}]")
        role = require_string(item.get("role"), f"spec.review_wiki_bindings[{index}].role")
        if role in wiki_roles:
            raise ValueError(f"duplicate review wiki role: {role}")
        wiki_roles.add(role)
        resolve_bound_path(item.get("path"), base=spec_path.parent, expected=item.get("sha256"), where=f"spec.review_wiki_bindings[{index}]")
    if "teaching_methodology" not in wiki_roles:
        raise ValueError("spec.review_wiki_bindings must include teaching_methodology")
    profile = spec.get("learner_profile")
    if not isinstance(profile, dict):
        raise ValueError("spec.learner_profile must be an object")
    exact_keys(profile, {
        "conducted_sequence_number", "learner_state_artifact_id", "learner_state_path",
        "learner_state_sha256", "known_closure_path", "known_closure_sha256",
        "stage_description", "epistemic_baseline", "hidden_behavior_profile",
        "simulation_mode",
    }, "spec.learner_profile")
    number = profile.get("conducted_sequence_number")
    if not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= 666:
        raise ValueError("spec.learner_profile.conducted_sequence_number must be in 1..666")
    require_string(profile.get("learner_state_artifact_id"), "spec.learner_profile.learner_state_artifact_id")
    require_string(profile.get("stage_description"), "spec.learner_profile.stage_description")
    baseline = profile.get("epistemic_baseline")
    if not isinstance(baseline, dict):
        raise ValueError("spec.learner_profile.epistemic_baseline must be an object")
    exact_keys(baseline, {
        "approximate_parameters_billion", "prior_image_exposures", "prior_word_form_exposures",
        "grounding_at_lesson_zero", "system_at_lesson_zero", "grammar_at_lesson_zero",
        "context_at_lesson_zero", "model_initialization", "encoder_training_effect",
        "prior_learning_treatment", "exposure_implication",
    }, "spec.learner_profile.epistemic_baseline")
    if baseline.get("approximate_parameters_billion") != 1.2:
        raise ValueError("epistemic baseline must record the 1.2B starting model")
    if baseline.get("prior_image_exposures") != 30000 or baseline.get("prior_word_form_exposures") != 3000:
        raise ValueError("epistemic baseline exposure counts do not match the starting model")
    for key in ("grounding_at_lesson_zero", "system_at_lesson_zero", "grammar_at_lesson_zero", "context_at_lesson_zero"):
        if baseline.get(key) != "none":
            raise ValueError(f"epistemic baseline {key} must equal none")
    if baseline.get("model_initialization") != "random_1_2b_parameters":
        raise ValueError("epistemic baseline must treat the starting language model as random parameters")
    if baseline.get("encoder_training_effect") != "can_read_siglip2_and_lfm_encoder_vectors_not_bankable_semantics":
        raise ValueError("epistemic baseline must delimit prior encoder training")
    if baseline.get("prior_learning_treatment") != "untrusted_bonus_never_prerequisite_without_deliberate_evidence":
        raise ValueError("epistemic baseline must treat prior learning as an untrusted bonus")
    if baseline.get("exposure_implication") != "no_meaning_or_knowledge_without_deliberate_grounded_evidence":
        raise ValueError("epistemic baseline must forbid treating exposure as knowledge")
    require_string(profile.get("hidden_behavior_profile"), "spec.learner_profile.hidden_behavior_profile")
    if profile.get("simulation_mode") not in {
        "calibrated_estimate", "conservative_lower_bound", "unexpected_bonus",
        "adversarial_pedagogical", "adversarial_protocol", "failure_injection",
    }:
        raise ValueError("spec.learner_profile.simulation_mode is invalid")
    resolve_bound_path(profile.get("learner_state_path"), base=spec_path.parent, expected=profile.get("learner_state_sha256"), where="spec.learner_profile.learner_state")
    resolve_bound_path(profile.get("known_closure_path"), base=spec_path.parent, expected=profile.get("known_closure_sha256"), where="spec.learner_profile.known_closure")
    phases = spec.get("required_phases")
    if not isinstance(phases, list) or not phases or any(v not in PHASE_ORDER for v in phases):
        raise ValueError("spec.required_phases must be a non-empty phase array")
    if len(phases) != len(set(phases)) or phases != sorted(phases, key=PHASE_ORDER.index):
        raise ValueError("spec.required_phases must be unique and in canonical phase order")
    tools = spec.get("allowed_tools")
    if not isinstance(tools, list) or not tools or len(tools) != len(set(tools)) or not set(tools).issubset(ALLOWED_TOOLS) or "ALARM" not in tools:
        raise ValueError("spec.allowed_tools must be a unique supported list containing ALARM")
    language = spec.get("teacher_language_policy")
    if not isinstance(language, dict):
        raise ValueError("spec.teacher_language_policy must be an object")
    exact_keys(language, {
        "known_forms", "frontier_forms", "instruction_phrases", "rescue_phrases",
        "comprehension_check_required", "unlicensed_language_action",
    }, "spec.teacher_language_policy")
    for key in ("known_forms", "frontier_forms", "instruction_phrases", "rescue_phrases"):
        values = language.get(key)
        if not isinstance(values, list) or len(values) != len(set(values)) or any(not isinstance(v, str) or not v for v in values):
            raise ValueError(f"spec.teacher_language_policy.{key} must be a unique string array")
    if language.get("comprehension_check_required") is not True:
        raise ValueError("spec.teacher_language_policy.comprehension_check_required must be true")
    if language.get("unlicensed_language_action") != "ALARM":
        raise ValueError("spec.teacher_language_policy.unlicensed_language_action must equal ALARM")
    budgets = spec.get("budgets")
    if not isinstance(budgets, dict):
        raise ValueError("spec.budgets must be an object")
    exact_keys(budgets, {"max_teacher_turns", "max_student_turns", "max_tool_calls"}, "spec.budgets")
    for key in budgets:
        if not isinstance(budgets[key], int) or isinstance(budgets[key], bool) or not 1 <= budgets[key] <= 512:
            raise ValueError(f"spec.budgets.{key} must be in 1..512")
    parent_path = spec.get("parent_run_manifest_path")
    repair_path = spec.get("repair_receipt_path")
    if effort["attempt_index"] > 0 and parent_path is None:
        raise ValueError("an escalated effort attempt must bind the prior failed manifest and repair receipt")
    if (parent_path is None) != (repair_path is None):
        raise ValueError("spec repair rerun requires both parent manifest and repair receipt")
    if parent_path is not None:
        parent = resolve_bound_path(parent_path, base=spec_path.parent, expected=spec.get("parent_run_manifest_sha256"), where="spec.parent_run_manifest")
        repair = resolve_bound_path(repair_path, base=spec_path.parent, expected=spec.get("repair_receipt_sha256"), where="spec.repair_receipt")
        parent_value = load_object(parent)
        if parent_value.get("terminal_status") not in {"alarm_frozen", "failed"}:
            raise ValueError("spec.parent_run_manifest must name a failed or alarm-frozen run")
        previous_effort: dict[str, Any] | None = None
        if effort["attempt_index"] > 0:
            previous_spec_path = parent.parent / "spec.json"
            if not previous_spec_path.is_file():
                raise ValueError("effort escalation parent run is missing its frozen spec")
            previous_spec = load_object(previous_spec_path)
            previous_effort = previous_spec.get("effort_escalation", {})
        receipt = load_object(repair)
        exact_keys(receipt, {"schema_version", "parent_manifest_sha256", "failure_codes", "root_causes", "changed_artifacts", "repair_rationale", "approved_by"}, "spec.repair_receipt")
        if receipt.get("schema_version") != "ninereeds_lesson_rehearsal_repair_receipt_v1":
            raise ValueError("spec.repair_receipt has an invalid schema version")
        if receipt.get("parent_manifest_sha256") != digest_path(parent):
            raise ValueError("spec.repair_receipt does not bind the exact parent manifest")
        if not isinstance(receipt.get("failure_codes"), list) or not receipt["failure_codes"]:
            raise ValueError("spec.repair_receipt.failure_codes must be non-empty")
        causes = receipt.get("root_causes")
        if not isinstance(causes, list) or not causes or not set(causes).issubset(FAILURE_CATEGORIES):
            raise ValueError("spec.repair_receipt.root_causes are invalid")
        if effort["attempt_index"] > 0 and previous_effort is not None:
            same_target = previous_effort.get("target_role") == effort["target_role"]
            previous_rung = effort["ladder"][effort["attempt_index"] - 1]
            advances_one_rung = previous_effort.get("current_effort") == previous_rung
            same_rung_non_model_repair = (
                previous_effort.get("current_effort") == effort["current_effort"]
                and set(causes).issubset({
                    "lesson_plan", "visual_material", "sol_simulation",
                    "harness", "verifier", "infrastructure",
                })
            )
            if not same_target or not (advances_one_rung or same_rung_non_model_repair):
                raise ValueError(
                    "repair rerun must advance exactly one effort rung for a Luna capability failure "
                    "or retain the rung for an explicit non-model repair"
                )
        changes = receipt.get("changed_artifacts")
        if not isinstance(changes, list) or not changes:
            raise ValueError("spec.repair_receipt.changed_artifacts must be non-empty")
        for index, change in enumerate(changes):
            if not isinstance(change, dict):
                raise ValueError(f"spec.repair_receipt.changed_artifacts[{index}] must be an object")
            exact_keys(change, {"path", "before_sha256", "after_sha256"}, f"spec.repair_receipt.changed_artifacts[{index}]")
            changed_path = resolve_bound_path(change.get("path"), base=repair.parent, expected=change.get("after_sha256"), where=f"spec.repair_receipt.changed_artifacts[{index}]")
            if change.get("before_sha256") == change.get("after_sha256"):
                raise ValueError(f"spec.repair_receipt.changed_artifacts[{index}] does not change bytes")
            if not changed_path.is_file():
                raise ValueError(f"spec.repair_receipt.changed_artifacts[{index}] does not resolve")
        require_string(receipt.get("repair_rationale"), "spec.repair_receipt.repair_rationale")
        require_string(receipt.get("approved_by"), "spec.repair_receipt.approved_by")
    elif any(spec.get(key) is not None for key in ("parent_run_manifest_sha256", "repair_receipt_sha256")):
        raise ValueError("spec initial run cannot contain parent or repair hashes")
    return lesson_path, lesson


def lesson_index(lesson: dict[str, Any]) -> tuple[dict[str, str], dict[str, set[str]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    exercises: dict[str, str] = {}
    exercise_assets: dict[str, set[str]] = {}
    phases = lesson.get("phases", {})
    execution_phases = {
        exercise_id: block.get("phase")
        for block in phases.get("execution_sequence", [])
        if isinstance(block, dict) and isinstance(block.get("phase"), str)
        for exercise_id in block.get("exercise_ids", [])
        if isinstance(exercise_id, str)
    }
    pools = [("presentation", phases.get("presentation", []))]
    controlled = phases.get("controlled_practice", {})
    pools.extend((name, controlled.get(name, [])) for name in ("affirmative", "negative", "W_question", "OR_question", "reciprocity"))
    pools.extend((("mixed_practice", phases.get("mixed_practice", [])), ("transfer", phases.get("transfer", []))))
    book = lesson.get("picture_book")
    if isinstance(book, dict):
        pools.append(("picture_book", book.get("pages", [])))
        pools.append(("comprehension", book.get("comprehension", [])))
    train_more = lesson.get("adaptive", {}).get("train_more", {})
    reserves_by_id = {
        reserve["id"]: reserve for reserve in train_more.get("reserve_exercises", [])
        if isinstance(reserve, dict) and isinstance(reserve.get("id"), str)
    }
    for phase, gate_config in train_more.get("gate_execution", {}).items():
        if not isinstance(gate_config, dict):
            continue
        for reserve_id in gate_config.get("reserve_exercise_ids", []):
            if reserve_id in reserves_by_id:
                pools.append((phase, [reserves_by_id[reserve_id]]))
    if not train_more.get("gate_execution"):
        legacy_prefixes = {
            "aff": "affirmative", "neg": "negative", "who": "W_question",
            "or": "OR_question", "recip": "reciprocity",
        }
        for reserve_id, reserve in reserves_by_id.items():
            phase = legacy_prefixes.get(reserve_id.split("-", 1)[0])
            if phase is not None:
                pools.append((phase, [reserve]))
    dispatches = lesson.get("adaptive", {}).get("present_again", {}).get("dispatch_table", {})
    retests = lesson.get("adaptive", {}).get("present_again", {}).get("retest_exercises", [])
    if isinstance(dispatches, dict) and isinstance(retests, list):
        retest_phases = {
            dispatch.get("cold_retest_exercise_id"): dispatch.get("gate")
            for dispatch in dispatches.values() if isinstance(dispatch, dict)
        }
        for retest in retests:
            if isinstance(retest, dict) and isinstance(retest.get("id"), str):
                phase = retest_phases.get(retest["id"])
                if isinstance(phase, str):
                    pools.append((phase, [retest]))
    for phase, pool in pools:
        for item in pool if isinstance(pool, list) else []:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                item_assets = item.get("asset_ids", [])
                if isinstance(item.get("asset_id"), str):
                    item_assets = [*item_assets, item["asset_id"]]
                exercises[item["id"]] = execution_phases.get(item["id"], phase)
                exercise_assets[item["id"]] = set(item_assets)
    assets = {item["id"]: item for item in lesson.get("assets", []) if isinstance(item, dict) and isinstance(item.get("id"), str)}
    operations = {
        item["output_asset_id"]: item
        for item in lesson.get("visual_plan", {}).get("operations", [])
        if isinstance(item, dict) and isinstance(item.get("output_asset_id"), str)
    }
    return exercises, exercise_assets, assets, operations


def licensed_machine_texts(control: dict[str, Any]) -> set[str]:
    """Return every frozen machine-control emission for one comprehension item."""
    values = {control.get("machine_action")}
    values.update(control.get("scored_action_sequence", []))
    for demo in control.get("demonstrations", []):
        if isinstance(demo, dict):
            values.add(demo.get("replay_text"))
            values.add(demo.get("feedback_action"))
            values.update(demo.get("action_sequence", []))
    return {value for value in values if isinstance(value, str) and value}


def find_exercise(lesson: dict[str, Any], exercise_id: str) -> dict[str, Any] | None:
    """Find one frozen exercise object across ordinary, story, and adaptive pools."""
    stack: list[Any] = [lesson]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            if value.get("id") == exercise_id and (
                "teacher_text" in value or "teacher_turns" in value or "dialogue_turns" in value
            ):
                return value
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return None


def presentation_dispatch_mapping(lesson: dict[str, Any], exercise_id: str, gate: str) -> dict[str, Any] | None:
    """Resolve the exact frozen PRESENT_AGAIN dispatch for one failed base item."""
    dispatch_table = lesson.get("adaptive", {}).get("present_again", {}).get("dispatch_table", {})
    if not isinstance(dispatch_table, dict):
        return None
    mapping = dispatch_table.get(exercise_id) or dispatch_table.get(gate)
    return mapping if isinstance(mapping, dict) else None


def validate_teacher_script_binding(event: dict[str, Any], state: dict[str, Any], lesson: dict[str, Any]) -> None:
    """Bind a Luna emission to one exact, ordered turn in the frozen lesson script."""
    exercise_id = event["exercise_id"]
    payload = event["payload"]
    frozen = find_exercise(lesson, exercise_id)
    if not isinstance(frozen, dict):
        raise ValueError("teacher turn has no frozen exercise script")

    script_ref = payload["script_ref"]
    prefix = f"{exercise_id}/teacher_turn_"
    if not script_ref.startswith(prefix):
        raise ValueError("teacher script_ref must name the exact frozen exercise teacher_turn_N")
    suffix = script_ref[len(prefix):]
    if not suffix.isdigit() or int(suffix) < 1 or str(int(suffix)) != suffix:
        raise ValueError("teacher script_ref must end in a canonical positive teacher_turn_N ordinal")
    ordinal = int(suffix)

    turns = frozen.get("teacher_turns")
    if not isinstance(turns, list) or not turns:
        turns = frozen.get("dialogue_turns")
    if isinstance(turns, list) and turns:
        if ordinal > len(turns) or not isinstance(turns[ordinal - 1], dict):
            raise ValueError("teacher script_ref ordinal is outside the frozen exercise")
        expected_text = turns[ordinal - 1].get("text")
        if payload["delivery_mode"] != "spoken" or payload["text"] != expected_text:
            raise ValueError("teacher emission does not exactly realize the frozen spoken turn")
    else:
        if ordinal != 1:
            raise ValueError("single-turn exercise only licenses teacher_turn_1")
        control = frozen.get("nonverbal_control")
        if frozen.get("teacher_text") == "MACHINE_CONTROL" and isinstance(control, dict):
            if payload["delivery_mode"] != "machine_control" or payload["text"] not in licensed_machine_texts(control):
                raise ValueError("teacher emission does not exactly realize the frozen machine-control turn")
        else:
            expected_text = frozen.get("teacher_text")
            if not isinstance(expected_text, str) or not expected_text:
                raise ValueError("frozen exercise has no realizable teacher turn")
            if payload["delivery_mode"] != "spoken" or payload["text"] != expected_text:
                raise ValueError("teacher emission does not exactly realize the frozen spoken turn")

    emitted = state.get("emitted_teacher_script_refs", [])
    if not isinstance(emitted, list):
        raise ValueError("rehearsal state has invalid emitted teacher script references")
    prior_for_exercise = [ref for ref in emitted if isinstance(ref, str) and ref.startswith(prefix)]
    dispatch = state.get("present_again_dispatch")
    is_dispatched_replay = (
        script_ref in emitted
        and isinstance(dispatch, dict)
        and event["phase"] == "presentation"
        and exercise_id == dispatch.get("presentation_id")
        and payload["text"] == dispatch.get("worked_item_label")
        and not dispatch.get("replay_teacher_emitted", False)
    )
    if script_ref in emitted and not is_dispatched_replay:
        raise ValueError("teacher script_ref was already emitted without a matching one-turn PRESENT_AGAIN dispatch")
    if script_ref not in emitted and ordinal != len(set(prior_for_exercise)) + 1:
        raise ValueError("teacher turns must be emitted once in frozen ordinal order")


def record_teacher_script_binding(state: dict[str, Any], event: dict[str, Any]) -> None:
    """Advance exact-turn state after a validated teacher emission."""
    refs = state.setdefault("emitted_teacher_script_refs", [])
    refs.append(event["payload"]["script_ref"])
    dispatch = state.get("present_again_dispatch")
    if (
        isinstance(dispatch, dict)
        and event["phase"] == "presentation"
        and event["exercise_id"] == dispatch.get("presentation_id")
        and event["payload"]["text"] == dispatch.get("worked_item_label")
    ):
        dispatch["replay_teacher_emitted"] = True


def make_present_again_state(lesson: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    arguments = event["payload"]["arguments"]
    mapping = presentation_dispatch_mapping(lesson, event["exercise_id"], arguments["gate"])
    if not isinstance(mapping, dict):
        raise ValueError("PRESENT_AGAIN has no frozen dispatch mapping")
    worked_item_label = mapping.get("worked_item_label") or mapping.get("target_label")
    if not isinstance(worked_item_label, str) or not worked_item_label:
        presentation = find_exercise(lesson, arguments["presentation_id"])
        if isinstance(presentation, dict) and isinstance(presentation.get("teacher_text"), str):
            worked_item_label = presentation["teacher_text"]
    return {
        "gate": arguments["gate"],
        "base_exercise_id": event["exercise_id"],
        "presentation_id": arguments["presentation_id"],
        "cold_retest_exercise_id": arguments["cold_retest_exercise_id"],
        "worked_item_label": worked_item_label,
        "replay_teacher_emitted": False,
    }


def validate_teacher_artifact_granularity(events: list[dict[str, Any]], lesson: dict[str, Any]) -> None:
    """Keep scored work item-atomic so an intervention can follow its learner response immediately."""
    scored_exercise_ids = set()
    for event in events:
        if event.get("event_type") != "teacher_turn":
            continue
        frozen = find_exercise(lesson, event.get("exercise_id"))
        if not isinstance(frozen, dict):
            continue
        answers = frozen.get("expected_answers")
        if (
            isinstance(answers, list)
            and answers
            and frozen.get("response_mode") != "model_only"
            and frozen.get("scoring_role") != "unscored_interface_check"
        ):
            scored_exercise_ids.add(event["exercise_id"])
    if len(scored_exercise_ids) > 1:
        raise ValueError(
            "teacher artifact may contain at most one scored exercise so PRESENT_AGAIN can follow immediately"
        )


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(canonical_bytes(value))
    os.replace(temporary, path)


def append_record(run_dir: Path, state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    core = {
        "schema_version": EVENT_VERSION,
        "sequence": state["last_sequence"] + 1,
        "occurred_at": utc_now(),
        "previous_hash": state["last_event_hash"],
        **payload,
    }
    event_hash = digest_bytes(canonical_bytes(core))
    record = {**core, "event_hash": event_hash}
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    state["last_sequence"] = record["sequence"]
    state["last_event_hash"] = event_hash
    return record


def load_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    spec = load_object(run_dir / "spec.json")
    state = load_object(run_dir / "state.json")
    lesson = load_object(Path(state["lesson_path"]))
    verify_run(run_dir)
    return spec, state, lesson


def freeze_alarm(run_dir: Path, state: dict[str, Any], *, initiator: str, code: str, reason: str, context: dict[str, Any]) -> dict[str, Any]:
    if code not in ALARM_CODES:
        code = "unexpected_runtime_failure"
    record = append_record(run_dir, state, {
        "event_type": "alarm",
        "actor": initiator,
        "phase": state.get("current_phase"),
        "exercise_id": state.get("current_exercise_id"),
        "payload": {"code": code, "reason": reason, "context": context},
    })
    state["status"] = "alarm_frozen"
    state["alarm_sequence"] = record["sequence"]
    state["updated_at"] = record["occurred_at"]
    atomic_write(run_dir / "state.json", state)
    return record


def init_run(spec_path: Path, output_dir: Path) -> None:
    spec = load_object(spec_path)
    lesson_path, lesson = validate_spec(spec, spec_path)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir = output_dir / "inputs"
    inputs_dir.mkdir()

    def snapshot(source: Path, name: str, expected: str) -> Path:
        target = inputs_dir / name
        target.write_bytes(source.read_bytes())
        if digest_path(target) != expected:
            raise ValueError(f"input snapshot hash mismatch: {name}")
        return target.resolve()

    frozen_spec = json.loads(json.dumps(spec))
    lesson_snapshot = snapshot(lesson_path, "lesson.json", spec["lesson_sha256"])
    frozen_spec["lesson_path"] = str(lesson_snapshot)
    profile = frozen_spec["learner_profile"]
    for key, name, hash_key in (
        ("learner_state_path", "learner-state.json", "learner_state_sha256"),
        ("known_closure_path", "known-closure.json", "known_closure_sha256"),
    ):
        path = Path(profile[key])
        source = (spec_path.parent / path).resolve() if not path.is_absolute() else path.resolve()
        profile[key] = str(snapshot(source, name, profile[hash_key]))
    for key in ("parent_run_manifest_path", "repair_receipt_path"):
        if frozen_spec[key] is not None:
            path = Path(frozen_spec[key])
            frozen_spec[key] = str((spec_path.parent / path).resolve()) if not path.is_absolute() else str(path.resolve())
    for index, item in enumerate(frozen_spec["review_wiki_bindings"]):
        path = Path(item["path"])
        source = (spec_path.parent / path).resolve() if not path.is_absolute() else path.resolve()
        safe_role = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in item["role"])
        item["path"] = str(snapshot(source, f"wiki-{index:02d}-{safe_role}{source.suffix}", item["sha256"]))
    (output_dir / "spec.json").write_bytes(canonical_bytes(frozen_spec))
    (output_dir / "events.jsonl").touch(mode=0o600)
    now = utc_now()
    state = {
        "schema_version": STATE_VERSION,
        "rehearsal_id": spec["rehearsal_id"],
        "status": "active",
        "lesson_path": str(lesson_snapshot),
        "lesson_sha256": digest_path(lesson_snapshot),
        "expected_actor": "luna",
        "current_phase": None,
        "current_exercise_id": None,
        "seen_phases": [],
        "teacher_turns": 0,
        "student_turns": 0,
        "tool_calls": 0,
        "comprehension_checks": 0,
        "replay_count": 0,
        "emitted_teacher_script_refs": [],
        "present_again_dispatch": None,
        "conduct_closed": False,
        "luna_report_sha256": None,
        "last_sequence": 0,
        "last_event_hash": ZERO_HASH,
        "alarm_sequence": None,
        "verdict_sha256": None,
        "created_at": now,
        "updated_at": now,
    }
    append_record(output_dir, state, {
        "event_type": "run_started", "actor": "harness", "phase": None,
        "exercise_id": None,
        "payload": {
            "spec_sha256": digest_path(output_dir / "spec.json"),
            "lesson_sha256": state["lesson_sha256"],
            "scenario_id": spec["scenario_id"],
            "random_seed": spec["random_seed"],
        },
    })
    state["updated_at"] = utc_now()
    atomic_write(output_dir / "state.json", state)
    print(f"initialized rehearsal {spec['rehearsal_id']} in {output_dir}")


def validate_interaction(event: dict[str, Any], spec: dict[str, Any], state: dict[str, Any], lesson: dict[str, Any]) -> None:
    exact_keys(event, {"event_type", "actor", "phase", "exercise_id", "payload"}, "event")
    event_type = event.get("event_type")
    if event_type not in {"teacher_turn", "student_turn", "tool_call"}:
        raise ValueError("event.event_type must be teacher_turn, student_turn, or tool_call")
    phase = event.get("phase")
    if phase not in spec["required_phases"]:
        raise ValueError("event.phase is outside the frozen scenario")
    exercise_id = require_string(event.get("exercise_id"), "event.exercise_id")
    exercises, exercise_assets, assets, operations = lesson_index(lesson)
    if exercises.get(exercise_id) != phase:
        raise ValueError("event.exercise_id does not belong to the declared phase")
    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("event.payload must be an object")
    if state["current_phase"] is not None and execution_position(lesson, phase, exercise_id) < execution_position(
        lesson, state["current_phase"], state["current_exercise_id"]
    ):
        dispatch = state.get("present_again_dispatch")
        allowed_dispatch_rewind = (
            isinstance(dispatch, dict)
            and phase == "presentation"
            and exercise_id == dispatch.get("presentation_id")
        )
        if not allowed_dispatch_rewind:
            raise ValueError("event attempts to move backward across the frozen phase order")
    cold_retests = {
        mapping.get("cold_retest_exercise_id")
        for mapping in lesson.get("adaptive", {}).get("present_again", {}).get("dispatch_table", {}).values()
        if isinstance(mapping, dict)
    }
    if event_type == "teacher_turn" and exercise_id in cold_retests:
        dispatch = state.get("present_again_dispatch")
        if (
            not isinstance(dispatch, dict)
            or exercise_id != dispatch.get("cold_retest_exercise_id")
            or not dispatch.get("replay_teacher_emitted", False)
        ):
            raise ValueError("cold retest requires its exact dispatched presentation turn first")
    if event_type == "teacher_turn":
        if event.get("actor") != "luna" or state["expected_actor"] != "luna":
            raise ValueError("teacher turn violates frozen actor alternation")
        exact_keys(payload, {"action", "delivery_mode", "text", "script_ref", "claim_ids", "language_receipt"}, "event.payload")
        if payload.get("action") not in TEACHING_ACTIONS:
            raise ValueError("teacher action is outside the frozen teaching protocol")
        if payload.get("delivery_mode") not in {"spoken", "machine_control"}:
            raise ValueError("event.payload.delivery_mode must be spoken or machine_control")
        require_string(payload.get("text"), "event.payload.text")
        require_string(payload.get("script_ref"), "event.payload.script_ref")
        claims = payload.get("claim_ids")
        if not isinstance(claims, list) or any(not isinstance(v, str) or not v for v in claims):
            raise ValueError("event.payload.claim_ids must be a string array")
        receipt = payload.get("language_receipt")
        if not isinstance(receipt, dict):
            raise ValueError("event.payload.language_receipt must be an object")
        exact_keys(receipt, {"known_forms", "frontier_forms", "instruction_phrases", "rescue_phrases", "unlicensed_forms"}, "event.payload.language_receipt")
        policy = spec["teacher_language_policy"]
        for key in receipt:
            values = receipt.get(key)
            if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
                raise ValueError(f"event.payload.language_receipt.{key} must be a string array")
            if key != "unlicensed_forms" and not set(values).issubset(set(policy[key])):
                raise ValueError(f"event.payload.language_receipt.{key} contains language outside the frozen policy")
        if receipt["unlicensed_forms"]:
            raise ValueError("teacher turn contains unlicensed language and must alarm")
        if payload["delivery_mode"] == "spoken":
            text = payload["text"]
            matching_buckets = [
                key for key in ("known_forms", "frontier_forms", "instruction_phrases", "rescue_phrases")
                if text in policy[key]
            ]
            if len(matching_buckets) != 1:
                raise ValueError("spoken teacher text must resolve to exactly one frozen language-policy bucket")
            expected_bucket = matching_buckets[0]
            for key in ("known_forms", "frontier_forms", "instruction_phrases", "rescue_phrases"):
                expected_values = [text] if key == expected_bucket else []
                if receipt[key] != expected_values:
                    raise ValueError("spoken teacher language receipt must classify the exact emitted text once")
        if payload["delivery_mode"] == "machine_control":
            if any(receipt[key] for key in receipt):
                raise ValueError("machine_control emissions cannot claim spoken teacher language")
            controls = []
            frozen_exercise = find_exercise(lesson, exercise_id)
            if isinstance(frozen_exercise, dict) and isinstance(frozen_exercise.get("nonverbal_control"), dict):
                controls.append(frozen_exercise["nonverbal_control"])
            allowed_machine_texts = set()
            for control in controls:
                allowed_machine_texts.update(licensed_machine_texts(control))
            if payload.get("text") not in allowed_machine_texts:
                raise ValueError("machine_control emission is not frozen for the current exercise")
        validate_teacher_script_binding(event, state, lesson)
    elif event_type == "student_turn":
        if event.get("actor") != "sol" or state["expected_actor"] != "sol":
            raise ValueError("student turn violates frozen actor alternation")
        exact_keys(payload, {"text", "behavior_tag", "simulator_basis"}, "event.payload")
        if not isinstance(payload.get("text"), str):
            raise ValueError("event.payload.text must be a string")
        require_string(payload.get("behavior_tag"), "event.payload.behavior_tag")
        if payload.get("simulator_basis") != "hidden_profile_and_known_closure":
            raise ValueError("Sol response must bind the frozen learner simulation basis")
    else:
        if event.get("actor") != "luna":
            raise ValueError("only Luna may request a teaching tool")
        exact_keys(payload, {"tool", "arguments", "reason"}, "event.payload")
        tool = payload.get("tool")
        if tool not in spec["allowed_tools"]:
            raise ValueError("tool is not permitted by the frozen rehearsal spec")
        if tool == "ALARM":
            raise ValueError("use the alarm command so the lesson freezes atomically")
        arguments = payload.get("arguments")
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        require_string(payload.get("reason"), "event.payload.reason")
        if tool in {"SHOW_ASSET", "SHOW_CROP", "SHOW_HIGHLIGHT"}:
            exact_keys(arguments, {"asset_id"}, "event.payload.arguments")
            asset_id = require_string(arguments.get("asset_id"), "event.payload.arguments.asset_id")
            if asset_id not in assets or asset_id not in operations:
                raise ValueError("requested visual is not a frozen lesson asset and operation")
            expected = {
                "SHOW_CROP": "literal_crop",
                "SHOW_HIGHLIGHT": "highlight",
            }.get(tool)
            if expected is not None and operations[asset_id].get("type") != expected:
                raise ValueError(f"{tool} requires a prepared {expected} operation")
            if asset_id not in exercise_assets.get(exercise_id, set()):
                raise ValueError("requested focus asset is not licensed for the current exercise")
        elif tool == "USE_MARKERS":
            exact_keys(arguments, {"level", "target_role", "target_point_id", "marked_text", "unmarked_equivalent"}, "event.payload.arguments")
            if arguments.get("level") not in {"constituent_only", "full_role_map", "frontier_focus"}:
                raise ValueError("invalid marker level")
            for key in ("target_point_id", "marked_text", "unmarked_equivalent"):
                require_string(arguments.get(key), f"event.payload.arguments.{key}")
            if arguments["marked_text"] == arguments["unmarked_equivalent"]:
                raise ValueError("marked and unmarked forms must be separately recorded")
        elif tool == "PRESENT_AGAIN":
            exact_keys(arguments, {"gate", "presentation_id", "cold_retest_exercise_id"}, "event.payload.arguments")
            gate = require_string(arguments.get("gate"), "event.payload.arguments.gate")
            if gate != phase:
                raise ValueError("PRESENT_AGAIN gate must equal the current controlled phase")
            mapping = presentation_dispatch_mapping(lesson, exercise_id, gate)
            expected = {
                "presentation_id": arguments.get("presentation_id"),
                "cold_retest_exercise_id": arguments.get("cold_retest_exercise_id"),
            }
            if not isinstance(mapping, dict) or mapping.get("gate", gate) != gate or any(
                mapping.get(key) != value for key, value in expected.items()
            ):
                raise ValueError("PRESENT_AGAIN arguments must equal the frozen gate dispatch")
        elif tool == "TRAIN_MORE":
            exact_keys(arguments, {"gate", "reserve_exercise_id", "decision_basis"}, "event.payload.arguments")
            gate = require_string(arguments.get("gate"), "event.payload.arguments.gate")
            if gate != phase:
                raise ValueError("TRAIN_MORE gate must equal the current controlled phase")
            reserve_id = require_string(arguments.get("reserve_exercise_id"), "event.payload.arguments.reserve_exercise_id")
            require_string(arguments.get("decision_basis"), "event.payload.arguments.decision_basis")
            reserve_exercises = lesson.get("adaptive", {}).get("train_more", {}).get("reserve_exercises", [])
            reserve = next((item for item in reserve_exercises if isinstance(item, dict) and item.get("id") == reserve_id), None)
            gate_execution = lesson.get("adaptive", {}).get("train_more", {}).get("gate_execution", {}).get(gate, {})
            licensed_reserves = gate_execution.get("reserve_exercise_ids", []) if isinstance(gate_execution, dict) else []
            if not licensed_reserves:
                gate_prefix = {
                    "affirmative": "aff", "negative": "neg", "W_question": "who",
                    "OR_question": "or", "reciprocity": "recip",
                }.get(gate)
                licensed_reserves = [reserve_id] if gate_prefix and reserve_id.startswith(gate_prefix + "-") else []
            if reserve is None or reserve_id not in licensed_reserves:
                raise ValueError("TRAIN_MORE must name a frozen reserve for the current gate")
        elif tool == "TRAIN_LONGER":
            exact_keys(arguments, {
                "exercise_ids", "ordering", "stop_after", "decision_basis",
            }, "event.payload.arguments")
            exercise_ids = arguments.get("exercise_ids")
            if not isinstance(exercise_ids, list) or len(exercise_ids) < 4:
                raise ValueError("TRAIN_LONGER requires at least four frozen exercise ids")
            frozen_order = lesson.get("adaptive", {}).get("train_longer", {}).get("ordered_item_ids")
            if exercise_ids != frozen_order:
                raise ValueError("TRAIN_LONGER exercise_ids must equal the frozen ordered_item_ids")
            if any(a == b for a, b in zip(exercise_ids, exercise_ids[1:])):
                raise ValueError("TRAIN_LONGER may not repeat an identical exercise immediately")
            if arguments.get("ordering") != "frozen_order":
                raise ValueError("TRAIN_LONGER ordering must equal frozen_order")
            stop_after = arguments.get("stop_after")
            if not isinstance(stop_after, int) or isinstance(stop_after, bool) or not 4 <= stop_after <= 64:
                raise ValueError("TRAIN_LONGER stop_after must be in 4..64")
            if stop_after != len(exercise_ids):
                raise ValueError("TRAIN_LONGER stop_after must equal the frozen loop length")
            require_string(arguments.get("decision_basis"), "event.payload.arguments.decision_basis")
        elif tool in {"REPLAY_PRESENTATION", "ASK_BOUNDED_CLARIFICATION", "CHECK_UNDERSTANDING", "FINISH"}:
            if arguments:
                raise ValueError(f"{tool} accepts no arguments")
        elif tool == "REPLAY_LESSON":
            exact_keys(arguments, {"scope"}, "event.payload.arguments")
            if arguments.get("scope") != lesson.get("adaptive", {}).get("replay_lesson", {}).get("replay_scope"):
                raise ValueError("REPLAY_LESSON scope must equal the frozen replay scope")


def append_interaction(run_dir: Path, event_path: Path) -> None:
    spec, state, lesson = load_run(run_dir)
    if state["status"] != "active":
        raise ValueError(f"rehearsal is terminal: {state['status']}")
    if state.get("conduct_closed"):
        raise ValueError("rehearsal conduct is closed by Luna's post-lesson report")
    event = load_object(event_path)
    try:
        validate_interaction(event, spec, state, lesson)
        budgets = spec["budgets"]
        projected = {
            "teacher_turn": state["teacher_turns"] + (event["event_type"] == "teacher_turn"),
            "student_turn": state["student_turns"] + (event["event_type"] == "student_turn"),
            "tool_call": state["tool_calls"] + (event["event_type"] == "tool_call"),
        }
        if projected["teacher_turn"] > budgets["max_teacher_turns"] or projected["student_turn"] > budgets["max_student_turns"] or projected["tool_call"] > budgets["max_tool_calls"]:
            raise ValueError("interaction exceeds a frozen rehearsal budget")
    except ValueError as exc:
        detail = str(exc)
        if "visual" in detail or "focus asset" in detail:
            alarm_code = "missing_visual_operation"
        elif "language" in detail:
            alarm_code = "teacher_language_not_understood"
        elif "tool" in detail or "marker" in detail:
            alarm_code = "tool_contract_failure"
        else:
            alarm_code = "phase_or_budget_violation"
        freeze_alarm(
            run_dir, state, initiator="harness", code=alarm_code,
            reason=detail, context={"rejected_event": event},
        )
        raise ValueError(f"protocol violation alarm-froze the rehearsal: {exc}") from exc
    record = append_record(run_dir, state, event)
    if event["phase"] not in state["seen_phases"]:
        state["seen_phases"].append(event["phase"])
    # Tool calls alter controller state but are not learner-facing execution
    # positions. Keeping the cursor on the last exchanged turn lets a gate
    # release several future reserves without falsely skipping over them.
    if event["event_type"] != "tool_call":
        state["current_phase"] = event["phase"]
        state["current_exercise_id"] = event["exercise_id"]
    dispatch = state.get("present_again_dispatch")
    if (
        isinstance(dispatch, dict)
        and event["phase"] == dispatch.get("gate")
        and event["exercise_id"] == dispatch.get("cold_retest_exercise_id")
    ):
        state["present_again_dispatch"] = None
    if event["event_type"] == "teacher_turn":
        record_teacher_script_binding(state, event)
        state["teacher_turns"] += 1
        frozen_exercise = find_exercise(lesson, event["exercise_id"])
        if isinstance(frozen_exercise, dict) and frozen_exercise.get("scoring_role") == "unscored_interface_check":
            state["comprehension_checks"] += 1
        state["expected_actor"] = "sol"
    elif event["event_type"] == "student_turn":
        state["student_turns"] += 1
        state["expected_actor"] = "luna"
    else:
        state["tool_calls"] += 1
        if event["payload"]["tool"] == "PRESENT_AGAIN":
            state["present_again_dispatch"] = make_present_again_state(lesson, event)
        elif event["payload"]["tool"] == "CHECK_UNDERSTANDING":
            state["comprehension_checks"] += 1
        elif event["payload"]["tool"] == "REPLAY_LESSON":
            state["replay_count"] += 1
            state["current_phase"] = None
            state["current_exercise_id"] = None
            state["emitted_teacher_script_refs"] = []
    state["updated_at"] = record["occurred_at"]
    atomic_write(run_dir / "state.json", state)
    print(f"recorded rehearsal event {record['sequence']}: {event['event_type']}")


def append_batch(run_dir: Path, events_path: Path) -> None:
    try:
        values = json.loads(events_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {events_path}: {exc}") from exc
    if not isinstance(values, list) or not values:
        raise ValueError("batch events must be a non-empty JSON array")
    if any(not isinstance(event, dict) for event in values):
        raise ValueError("every batch event must be one JSON object")
    pending = run_dir / ".batch-event.pending.json"
    try:
        for event in values:
            pending.write_bytes(canonical_bytes(event))
            append_interaction(run_dir, pending)
    finally:
        pending.unlink(missing_ok=True)


def append_exchange(run_dir: Path, teacher_events_path: Path, student_events_path: Path) -> None:
    """Admit one brokered exchange without allowing either model to author the other role."""
    try:
        teacher_events = json.loads(teacher_events_path.read_text(encoding="utf-8"))
        student_events = json.loads(student_events_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read brokered exchange: {exc}") from exc
    if not isinstance(teacher_events, list) or not teacher_events:
        raise ValueError("teacher exchange must be a non-empty JSON array")
    if not isinstance(student_events, list) or not student_events:
        raise ValueError("student exchange must be a non-empty JSON array")
    if any(
        not isinstance(event, dict)
        or event.get("actor") != "luna"
        or event.get("event_type") not in {"teacher_turn", "tool_call"}
        for event in teacher_events
    ):
        raise ValueError("teacher exchange may contain only Luna teacher_turn and tool_call events")
    teacher_turns = [event for event in teacher_events if event.get("event_type") == "teacher_turn"]
    if any(
        not isinstance(event, dict)
        or event.get("actor") != "sol"
        or event.get("event_type") != "student_turn"
        for event in student_events
    ):
        raise ValueError("student exchange may contain only Sol student_turn events")
    if len(teacher_turns) != len(student_events):
        raise ValueError("brokered exchange requires exactly one Sol response per Luna teacher turn")
    merged: list[dict[str, Any]] = []
    response_index = 0
    for event in teacher_events:
        merged.append(event)
        if event.get("event_type") == "teacher_turn":
            response = student_events[response_index]
            response_index += 1
            if (response.get("phase"), response.get("exercise_id")) != (event.get("phase"), event.get("exercise_id")):
                raise ValueError("Sol response must bind the corresponding Luna phase and exercise_id")
            merged.append(response)
    spec, state, lesson = load_run(run_dir)
    if state["status"] != "active" or state.get("conduct_closed"):
        raise ValueError("rehearsal is not open for a brokered exchange")
    validate_teacher_artifact_granularity(teacher_events, lesson)
    projected = json.loads(json.dumps(state))
    try:
        for event in merged:
            validate_interaction(event, spec, projected, lesson)
            event_type = event["event_type"]
            budget_key = {
                "teacher_turn": "max_teacher_turns",
                "student_turn": "max_student_turns",
                "tool_call": "max_tool_calls",
            }[event_type]
            count_key = {
                "teacher_turn": "teacher_turns",
                "student_turn": "student_turns",
                "tool_call": "tool_calls",
            }[event_type]
            if projected[count_key] + 1 > spec["budgets"][budget_key]:
                raise ValueError("interaction exceeds a frozen rehearsal budget")
            if event_type != "tool_call":
                projected["current_phase"] = event["phase"]
                projected["current_exercise_id"] = event["exercise_id"]
            dispatch = projected.get("present_again_dispatch")
            if (
                isinstance(dispatch, dict)
                and event["phase"] == dispatch.get("gate")
                and event["exercise_id"] == dispatch.get("cold_retest_exercise_id")
            ):
                projected["present_again_dispatch"] = None
            if event_type == "teacher_turn":
                record_teacher_script_binding(projected, event)
                projected["teacher_turns"] += 1
                projected["expected_actor"] = "sol"
            elif event_type == "student_turn":
                projected["student_turns"] += 1
                projected["expected_actor"] = "luna"
            else:
                projected["tool_calls"] += 1
                if event["payload"]["tool"] == "PRESENT_AGAIN":
                    projected["present_again_dispatch"] = make_present_again_state(lesson, event)
                elif event["payload"]["tool"] == "CHECK_UNDERSTANDING":
                    projected["comprehension_checks"] += 1
                elif event["payload"]["tool"] == "REPLAY_LESSON":
                    projected["replay_count"] += 1
                    projected["current_phase"] = None
                    projected["current_exercise_id"] = None
                    projected["emitted_teacher_script_refs"] = []
    except ValueError as exc:
        detail = str(exc)
        if "visual" in detail or "focus asset" in detail:
            alarm_code = "missing_visual_operation"
        elif "language" in detail:
            alarm_code = "teacher_language_not_understood"
        elif "tool" in detail or "marker" in detail:
            alarm_code = "tool_contract_failure"
        else:
            alarm_code = "phase_or_budget_violation"
        freeze_alarm(
            run_dir, state, initiator="harness", code=alarm_code,
            reason=f"brokered exchange rejected atomically: {detail}",
            context={"rejected_event": event, "admitted_from_exchange": 0},
        )
        raise ValueError(f"brokered exchange rejected atomically: {exc}") from exc
    pending = run_dir / ".brokered-event.pending.json"
    try:
        for event in merged:
            pending.write_bytes(canonical_bytes(event))
            append_interaction(run_dir, pending)
    finally:
        pending.unlink(missing_ok=True)


def lint_teacher_artifact(run_dir: Path, teacher_events_path: Path) -> None:
    """Non-mutating preflight for a Luna-only block before it is delivered to Sol."""
    spec, state, lesson = load_run(run_dir)
    if state["status"] != "active" or state.get("conduct_closed"):
        raise ValueError("rehearsal is not open for teacher-artifact linting")
    try:
        events = json.loads(teacher_events_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read teacher artifact: {exc}") from exc
    if not isinstance(events, list) or not events:
        raise ValueError("teacher artifact must be a non-empty JSON array")
    if any(
        not isinstance(event, dict)
        or event.get("actor") != "luna"
        or event.get("event_type") not in {"teacher_turn", "tool_call"}
        for event in events
    ):
        raise ValueError("teacher artifact may contain only Luna teacher_turn and tool_call events")
    validate_teacher_artifact_granularity(events, lesson)
    projected = json.loads(json.dumps(state))
    teacher_turns = 0
    for event in events:
        validate_interaction(event, spec, projected, lesson)
        if event["event_type"] != "tool_call":
            projected["current_phase"] = event["phase"]
            projected["current_exercise_id"] = event["exercise_id"]
        dispatch = projected.get("present_again_dispatch")
        if (
            isinstance(dispatch, dict)
            and event["phase"] == dispatch.get("gate")
            and event["exercise_id"] == dispatch.get("cold_retest_exercise_id")
        ):
            projected["present_again_dispatch"] = None
        if event["event_type"] == "teacher_turn":
            teacher_turns += 1
            record_teacher_script_binding(projected, event)
            projected["teacher_turns"] += 1
            # The peer response is deliberately absent from this artifact. Simulate only the
            # alternation reset; no response content or learner outcome is invented.
            projected["expected_actor"] = "luna"
        else:
            projected["tool_calls"] += 1
            if event["payload"]["tool"] == "PRESENT_AGAIN":
                projected["present_again_dispatch"] = make_present_again_state(lesson, event)
            elif event["payload"]["tool"] == "REPLAY_LESSON":
                projected["replay_count"] += 1
                projected["current_phase"] = None
                projected["current_exercise_id"] = None
                projected["emitted_teacher_script_refs"] = []
    print(f"teacher artifact lint passed: {len(events)} events, {teacher_turns} teacher turns")


def alarm(run_dir: Path, alarm_path: Path) -> None:
    _, state, _ = load_run(run_dir)
    if state["status"] != "active":
        raise ValueError(f"rehearsal is terminal: {state['status']}")
    if state.get("conduct_closed"):
        raise ValueError("rehearsal conduct is closed by Luna's post-lesson report")
    value = load_object(alarm_path)
    exact_keys(value, {"code", "reason", "context"}, "alarm")
    if value.get("code") not in ALARM_CODES:
        raise ValueError("alarm.code is invalid")
    require_string(value.get("reason"), "alarm.reason")
    if not isinstance(value.get("context"), dict):
        raise ValueError("alarm.context must be an object")
    record = freeze_alarm(run_dir, state, initiator="luna", code=value["code"], reason=value["reason"], context=value["context"])
    print(f"alarm-froze rehearsal at event {record['sequence']}: {value['code']}")


def record_luna_report(run_dir: Path, report_path: Path) -> None:
    spec, state, _ = load_run(run_dir)
    if state["status"] not in {"active", "alarm_frozen"}:
        raise ValueError(f"cannot report on terminal rehearsal: {state['status']}")
    if state.get("conduct_closed") or (run_dir / "luna-post-lesson-report.json").exists():
        raise ValueError("Luna post-lesson report already exists")
    if state["status"] == "active" and (
        state["teacher_turns"] != state["student_turns"] or state["expected_actor"] != "luna"
    ):
        raise ValueError("Luna may report only after a complete teacher/student turn pair")
    report = load_object(report_path)
    keys = {
        "schema_version", "rehearsal_id", "lesson_sha256", "author_role",
        "overall_assessment", "phase_assessment", "learner_capability_hypotheses",
        "remaining_difficulties", "uncertainties", "intervention_assessment",
        "teacher_self_critique", "alarm_assessment", "proposed_closure_changes",
        "next_lesson_implications", "rehearsal_nonadvancement",
    }
    exact_keys(report, keys, "luna_report")
    if report.get("schema_version") != LUNA_REPORT_VERSION:
        raise ValueError("Luna report schema version is invalid")
    if report.get("rehearsal_id") != spec["rehearsal_id"] or report.get("lesson_sha256") != state["lesson_sha256"]:
        raise ValueError("Luna report does not bind the exact rehearsal and lesson")
    if report.get("author_role") != "luna_post_lesson_analyst":
        raise ValueError("Luna report author_role must equal luna_post_lesson_analyst")
    if report.get("overall_assessment") not in {"achieved", "partially_achieved", "not_achieved", "indeterminate"}:
        raise ValueError("Luna report overall_assessment is invalid")
    if report.get("rehearsal_nonadvancement") != "hypotheses_only_no_learner_state_advance":
        raise ValueError("rehearsal report may not advance learner state")

    def sequences(value: Any, where: str) -> None:
        if not isinstance(value, list) or len(value) != len(set(value)) or any(not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= state["last_sequence"] for v in value):
            raise ValueError(f"{where} must contain unique existing event sequences")

    for field in ("phase_assessment", "intervention_assessment"):
        values = report.get(field)
        if not isinstance(values, list):
            raise ValueError(f"luna_report.{field} must be an array")
        for index, item in enumerate(values):
            exact_keys(item, {"claim", "evidence_event_sequences"}, f"luna_report.{field}[{index}]")
            require_string(item.get("claim"), f"luna_report.{field}[{index}].claim")
            sequences(item.get("evidence_event_sequences"), f"luna_report.{field}[{index}].evidence_event_sequences")
    for field in ("learner_capability_hypotheses", "remaining_difficulties"):
        values = report.get(field)
        if not isinstance(values, list):
            raise ValueError(f"luna_report.{field} must be an array")
        for index, item in enumerate(values):
            exact_keys(item, {"claim", "evidence_event_sequences", "support_level", "confidence"}, f"luna_report.{field}[{index}]")
            require_string(item.get("claim"), f"luna_report.{field}[{index}].claim")
            sequences(item.get("evidence_event_sequences"), f"luna_report.{field}[{index}].evidence_event_sequences")
            if item.get("support_level") not in {"independent", "scaffolded", "contradictory", "not_demonstrated"} or item.get("confidence") not in {"low", "medium", "high"}:
                raise ValueError(f"luna_report.{field}[{index}] has an invalid support level or confidence")
    for field in ("uncertainties", "teacher_self_critique", "next_lesson_implications"):
        values = report.get(field)
        if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
            raise ValueError(f"luna_report.{field} must be a string array")
    require_string(report.get("alarm_assessment"), "luna_report.alarm_assessment")
    closures = report.get("proposed_closure_changes")
    if not isinstance(closures, list):
        raise ValueError("luna_report.proposed_closure_changes must be an array")
    for index, item in enumerate(closures):
        exact_keys(item, {"item", "proposed_state", "evidence_event_sequences", "caveat"}, f"luna_report.proposed_closure_changes[{index}]")
        require_string(item.get("item"), f"luna_report.proposed_closure_changes[{index}].item")
        require_string(item.get("caveat"), f"luna_report.proposed_closure_changes[{index}].caveat")
        if item.get("proposed_state") not in {"introduced", "controlled_practice_completed", "mixed_practice_completed", "unstable", "not_demonstrated"}:
            raise ValueError(f"luna_report.proposed_closure_changes[{index}].proposed_state is invalid")
        sequences(item.get("evidence_event_sequences"), f"luna_report.proposed_closure_changes[{index}].evidence_event_sequences")
    output = run_dir / "luna-post-lesson-report.json"
    output.write_bytes(canonical_bytes(report))
    report_sha = digest_path(output)
    record = append_record(run_dir, state, {
        "event_type": "teacher_report", "actor": "luna", "phase": state.get("current_phase"),
        "exercise_id": state.get("current_exercise_id"), "payload": {"report_sha256": report_sha},
    })
    state["conduct_closed"] = True
    state["luna_report_sha256"] = report_sha
    state["updated_at"] = record["occurred_at"]
    atomic_write(run_dir / "state.json", state)
    print(f"recorded Luna post-lesson report: {output}")


def validate_verdict(verdict: dict[str, Any], spec: dict[str, Any], state: dict[str, Any]) -> None:
    exact_keys(verdict, {"schema_version", "verifier_id", "review_packet_sha256", "decision", "dimensions", "report_disposition", "report_corrections", "failures", "notes"}, "verdict")
    if verdict.get("schema_version") != VERDICT_VERSION:
        raise ValueError(f"verdict.schema_version must equal {VERDICT_VERSION}")
    if verdict.get("verifier_id") != spec["verifier"]["reviewer_id"]:
        raise ValueError("verdict.verifier_id does not match the independent verifier")
    if not isinstance(verdict.get("review_packet_sha256"), str) or SHA256.fullmatch(verdict["review_packet_sha256"]) is None:
        raise ValueError("verdict.review_packet_sha256 must be lowercase SHA-256")
    if verdict.get("decision") not in {"pass", "fail"}:
        raise ValueError("verdict.decision must be pass or fail")
    dimensions = verdict.get("dimensions")
    dimension_keys = REVIEW_DIMENSIONS
    if not isinstance(dimensions, dict):
        raise ValueError("verdict.dimensions must be an object")
    exact_keys(dimensions, dimension_keys, "verdict.dimensions")
    if any(not isinstance(v, bool) for v in dimensions.values()):
        raise ValueError("verdict dimensions must be boolean")
    disposition = verdict.get("report_disposition")
    corrections = verdict.get("report_corrections")
    if disposition not in {"luna_verified", "sol_reconstruction_required"}:
        raise ValueError("verdict.report_disposition is invalid")
    if not isinstance(corrections, list) or any(not isinstance(v, str) or not v for v in corrections):
        raise ValueError("verdict.report_corrections must be a string array")
    report_dimension = dimensions["teacher_self_assessment_calibration"]
    if disposition == "luna_verified" and (not report_dimension or corrections):
        raise ValueError("luna_verified requires calibrated self-assessment and no corrections")
    if disposition == "sol_reconstruction_required" and (report_dimension or not corrections):
        raise ValueError("sol_reconstruction_required requires a failed calibration dimension and corrections")
    failures = verdict.get("failures")
    if not isinstance(failures, list):
        raise ValueError("verdict.failures must be an array")
    for index, item in enumerate(failures):
        if not isinstance(item, dict):
            raise ValueError(f"verdict.failures[{index}] must be an object")
        exact_keys(item, {"category", "code", "event_sequence", "severity", "explanation", "repair_target"}, f"verdict.failures[{index}]")
        if item.get("category") not in FAILURE_CATEGORIES:
            raise ValueError(f"verdict.failures[{index}].category is invalid")
        if item.get("severity") not in {"minor", "major", "critical"}:
            raise ValueError(f"verdict.failures[{index}].severity is invalid")
        for key in ("code", "explanation", "repair_target"):
            require_string(item.get(key), f"verdict.failures[{index}].{key}")
        seq = item.get("event_sequence")
        if seq is not None and (not isinstance(seq, int) or not 1 <= seq <= state["last_sequence"]):
            raise ValueError(f"verdict.failures[{index}].event_sequence is invalid")
    notes = verdict.get("notes")
    if not isinstance(notes, list) or any(not isinstance(v, str) or not v for v in notes):
        raise ValueError("verdict.notes must be a string array")
    conduct_dimensions = {key: value for key, value in dimensions.items() if key != "teacher_self_assessment_calibration"}
    passing = all(conduct_dimensions.values()) and not failures and (
        (report_dimension and disposition == "luna_verified")
        or (not report_dimension and disposition == "sol_reconstruction_required" and bool(corrections))
    )
    if (verdict["decision"] == "pass") != passing:
        raise ValueError("verdict decision contradicts dimensions or failures")
    if verdict["decision"] == "pass":
        missing = [phase for phase in spec["required_phases"] if phase not in state["seen_phases"]]
        if missing:
            raise ValueError("passing verdict cannot omit required phases: " + ", ".join(missing))
        if state["status"] == "alarm_frozen":
            raise ValueError("an alarm-frozen rehearsal cannot pass")
        if state["teacher_turns"] != state["student_turns"] or state["expected_actor"] != "luna":
            raise ValueError("passing verdict requires complete teacher/student turn pairs")
        if spec["teacher_language_policy"]["comprehension_check_required"] and state["comprehension_checks"] < 1:
            raise ValueError("passing verdict requires a recorded comprehension check")


def finalize(run_dir: Path, verdict_path: Path) -> None:
    spec, state, _ = load_run(run_dir)
    if state["status"] not in {"active", "alarm_frozen"}:
        raise ValueError(f"rehearsal is already finalized: {state['status']}")
    packet_path = run_dir / "review-packet.json"
    if not packet_path.is_file():
        raise ValueError("review packet is missing; create the anonymized reviewer input first")
    verdict = load_object(verdict_path)
    validate_verdict(verdict, spec, state)
    if verdict["review_packet_sha256"] != digest_path(packet_path):
        raise ValueError("verdict does not bind the exact anonymized review packet")
    frozen_verdict = json.loads(json.dumps(verdict))
    (run_dir / "verdict.json").write_bytes(canonical_bytes(frozen_verdict))
    verdict_sha = digest_path(run_dir / "verdict.json")
    record = append_record(run_dir, state, {
        "event_type": "verdict", "actor": "independent_verifier",
        "phase": state.get("current_phase"), "exercise_id": state.get("current_exercise_id"),
        "payload": {"decision": verdict["decision"], "verdict_sha256": verdict_sha},
    })
    terminal = "passed" if verdict["decision"] == "pass" else ("alarm_frozen" if state["status"] == "alarm_frozen" else "failed")
    state["status"] = terminal
    state["verdict_sha256"] = verdict_sha
    state["updated_at"] = record["occurred_at"]
    atomic_write(run_dir / "state.json", state)
    manifest = {
        "schema_version": MANIFEST_VERSION,
        "rehearsal_id": spec["rehearsal_id"],
        "scenario_id": spec["scenario_id"],
        "terminal_status": terminal,
        "lesson_sha256": state["lesson_sha256"],
        "spec_sha256": digest_path(run_dir / "spec.json"),
        "event_log_sha256": digest_path(run_dir / "events.jsonl"),
        "last_event_hash": state["last_event_hash"],
        "event_count": state["last_sequence"],
        "verdict_sha256": verdict_sha,
        "review_packet_sha256": digest_path(packet_path),
        "luna_report_sha256": state["luna_report_sha256"],
        "report_disposition": verdict["report_disposition"],
        "effort_target_role": spec["effort_escalation"]["target_role"],
        "effort": spec["effort_escalation"]["current_effort"],
        "effort_attempt_index": spec["effort_escalation"]["attempt_index"],
        "effort_exhausted": terminal != "passed" and spec["effort_escalation"]["current_effort"] == "max",
        "effort_failure_outcome": (
            "terminal_model_capability_failure"
            if terminal != "passed" and spec["effort_escalation"]["current_effort"] == "max"
            else None
        ),
        "parent_run_manifest_sha256": spec.get("parent_run_manifest_sha256"),
        "repair_receipt_sha256": spec.get("repair_receipt_sha256"),
    }
    (run_dir / "manifest.json").write_bytes(canonical_bytes(manifest))
    print(f"finalized rehearsal {spec['rehearsal_id']}: {terminal}")


def make_reporter_packet(run_dir: Path) -> None:
    """Create a post-lesson analyst input that cannot reveal Sol's hidden profile."""
    spec, state, _ = load_run(run_dir)
    output = run_dir / "reporter-packet.json"
    if output.exists():
        raise ValueError(f"refusing to overwrite reporter packet: {output}")
    if state["status"] == "active" and (
        state["teacher_turns"] != state["student_turns"] or state["expected_actor"] != "luna"
    ):
        raise ValueError("reporter packet requires complete teacher/student turn pairs")
    wiki = []
    for item in spec["review_wiki_bindings"]:
        path = Path(item["path"])
        if not path.is_file() or digest_path(path) != item["sha256"]:
            raise ValueError(f"reporter wiki binding is stale: {item['role']}")
        wiki.append(item)
    packet = {
        "schema_version": REPORTER_PACKET_VERSION,
        "rehearsal_id": spec["rehearsal_id"],
        "scenario_id": spec["scenario_id"],
        "lesson": {"path": state["lesson_path"], "sha256": state["lesson_sha256"]},
        "rehearsal_log": {
            "path": str((run_dir / "events.jsonl").resolve()),
            "sha256": digest_path(run_dir / "events.jsonl"),
            "event_count": state["last_sequence"],
            "last_event_hash": state["last_event_hash"],
        },
        "conduct_state": {
            "path": str((run_dir / "state.json").resolve()),
            "sha256": digest_path(run_dir / "state.json"),
        },
        "learner_level": {
            "conducted_sequence_number": spec["learner_profile"]["conducted_sequence_number"],
            "learner_state_artifact_id": spec["learner_profile"]["learner_state_artifact_id"],
            "learner_state_path": spec["learner_profile"]["learner_state_path"],
            "learner_state_sha256": spec["learner_profile"]["learner_state_sha256"],
            "known_closure_path": spec["learner_profile"]["known_closure_path"],
            "known_closure_sha256": spec["learner_profile"]["known_closure_sha256"],
            "stage_description": spec["learner_profile"]["stage_description"],
            "epistemic_baseline": spec["learner_profile"]["epistemic_baseline"],
        },
        "required_phases": spec["required_phases"],
        "allowed_tools": spec["allowed_tools"],
        "teacher_language_policy": spec["teacher_language_policy"],
        "budgets": spec["budgets"],
        "wiki_bindings": wiki,
        "report_contract": {
            "schema_version": LUNA_REPORT_VERSION,
            "author_role": "luna_post_lesson_analyst",
            "rehearsal_nonadvancement": "hypotheses_only_no_learner_state_advance",
            "top_level_keys": [
                "schema_version", "rehearsal_id", "lesson_sha256", "author_role",
                "overall_assessment", "phase_assessment", "learner_capability_hypotheses",
                "remaining_difficulties", "uncertainties", "intervention_assessment",
                "teacher_self_critique", "alarm_assessment", "proposed_closure_changes",
                "next_lesson_implications", "rehearsal_nonadvancement",
            ],
            "overall_assessment_enum": ["achieved", "partially_achieved", "not_achieved", "indeterminate"],
            "evidence_claim_shape": ["claim", "evidence_event_sequences"],
            "capability_shape": ["claim", "evidence_event_sequences", "support_level", "confidence"],
            "support_level_enum": ["independent", "scaffolded", "contradictory", "not_demonstrated"],
            "confidence_enum": ["low", "medium", "high"],
            "closure_shape": ["item", "proposed_state", "evidence_event_sequences", "caveat"],
            "proposed_state_enum": [
                "introduced", "controlled_practice_completed", "mixed_practice_completed",
                "unstable", "not_demonstrated",
            ],
        },
        "excluded_context": [
            "student_simulator_hidden_behavior_profile",
            "student_simulator_prompt",
            "student_simulator_model_identity",
            "teacher_model_identity",
            "prior_rehearsal_reports_and_verdicts",
        ],
    }
    output.write_bytes(canonical_bytes(packet))
    print(f"created sanitized Luna reporter packet: {output}")


def make_review_packet(run_dir: Path) -> None:
    spec, state, _ = load_run(run_dir)
    output = run_dir / "review-packet.json"
    if output.exists():
        raise ValueError(f"refusing to overwrite review packet: {output}")
    luna_report = run_dir / "luna-post-lesson-report.json"
    if not luna_report.is_file() or state.get("luna_report_sha256") != digest_path(luna_report):
        raise ValueError("a hash-bound Luna post-lesson report is required before anonymous review")
    wiki = []
    for item in spec["review_wiki_bindings"]:
        path = Path(item["path"])
        if not path.is_file() or digest_path(path) != item["sha256"]:
            raise ValueError(f"review wiki binding is stale: {item['role']}")
        wiki.append(item)
    packet = {
        "schema_version": REVIEW_PACKET_VERSION,
        "rehearsal_id": spec["rehearsal_id"],
        "scenario_id": spec["scenario_id"],
        "actors": {
            "teacher": "anonymous_teacher_model",
            "student_simulator": "anonymous_student_simulator_model",
        },
        "learner_level": {
            "conducted_sequence_number": spec["learner_profile"]["conducted_sequence_number"],
            "learner_state_artifact_id": spec["learner_profile"]["learner_state_artifact_id"],
            "learner_state_sha256": spec["learner_profile"]["learner_state_sha256"],
            "learner_state_path": spec["learner_profile"]["learner_state_path"],
            "known_closure_sha256": spec["learner_profile"]["known_closure_sha256"],
            "known_closure_path": spec["learner_profile"]["known_closure_path"],
            "stage_description": spec["learner_profile"]["stage_description"],
            "epistemic_baseline": spec["learner_profile"]["epistemic_baseline"],
        },
        "lesson": {"path": state["lesson_path"], "sha256": state["lesson_sha256"]},
        "rehearsal_log": {
            "path": str((run_dir / "events.jsonl").resolve()),
            "sha256": digest_path(run_dir / "events.jsonl"),
            "event_count": state["last_sequence"],
            "last_event_hash": state["last_event_hash"],
        },
        "teacher_language_policy": spec["teacher_language_policy"],
        "teacher_post_lesson_report": {
            "path": str(luna_report.resolve()), "sha256": digest_path(luna_report),
        },
        "wiki_bindings": wiki,
        "review_dimensions": sorted(REVIEW_DIMENSIONS),
        "alarm": {
            "frozen": state["status"] == "alarm_frozen",
            "event_sequence": state["alarm_sequence"],
        },
        "excluded_context": [
            "teacher model identity", "student simulator model identity",
            "post-lesson analyst model identity and reasoning effort",
            "student simulator hidden behavior profile", "provider preference",
            "student simulator hidden simulation mode",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(packet))
    print(f"created anonymized review packet: {output}")


def verify_run(run_dir: Path) -> dict[str, Any]:
    state = load_object(run_dir / "state.json")
    previous = ZERO_HASH
    count = 0
    with (run_dir / "events.jsonl").open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"events.jsonl line {line_number}: {exc}") from exc
            if not isinstance(record, dict) or record.get("sequence") != line_number:
                raise ValueError(f"events.jsonl line {line_number}: invalid sequence")
            event_hash = record.pop("event_hash", None)
            if record.get("previous_hash") != previous or event_hash != digest_bytes(canonical_bytes(record)):
                raise ValueError(f"events.jsonl line {line_number}: event chain mismatch")
            previous = event_hash
            count = line_number
    if count != state.get("last_sequence") or previous != state.get("last_event_hash"):
        raise ValueError("state does not match the event-chain tip")
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        manifest = load_object(manifest_path)
        if manifest.get("event_log_sha256") != digest_path(run_dir / "events.jsonl") or manifest.get("last_event_hash") != previous:
            raise ValueError("manifest does not match event log")
    return {"ok": True, "status": state["status"], "event_count": count, "last_event_hash": previous}


def assemble_suite(spec_path: Path, output: Path) -> None:
    value = load_object(spec_path)
    exact_keys(value, {"schema_version", "suite_id", "lesson_sha256", "required_scenarios", "runs", "pass_rule"}, "suite")
    if value.get("schema_version") != SUITE_VERSION:
        raise ValueError(f"suite.schema_version must equal {SUITE_VERSION}")
    require_string(value.get("suite_id"), "suite.suite_id")
    lesson_sha = value.get("lesson_sha256")
    if not isinstance(lesson_sha, str) or SHA256.fullmatch(lesson_sha) is None:
        raise ValueError("suite.lesson_sha256 must be lowercase SHA-256")
    scenarios = value.get("required_scenarios")
    if not isinstance(scenarios, list) or not scenarios or len(scenarios) != len(set(scenarios)) or any(not isinstance(v, str) or not v for v in scenarios):
        raise ValueError("suite.required_scenarios must be a unique non-empty string array")
    if value.get("pass_rule") != "all_required_scenarios_pass":
        raise ValueError("suite.pass_rule must equal all_required_scenarios_pass")
    runs = value.get("runs")
    if not isinstance(runs, list):
        raise ValueError("suite.runs must be an array")
    by_scenario: dict[str, dict[str, Any]] = {}
    run_receipts = []
    for index, item in enumerate(runs):
        if not isinstance(item, dict):
            raise ValueError(f"suite.runs[{index}] must be an object")
        exact_keys(item, {"scenario_id", "manifest_path", "manifest_sha256"}, f"suite.runs[{index}]")
        scenario = require_string(item.get("scenario_id"), f"suite.runs[{index}].scenario_id")
        if scenario in by_scenario:
            raise ValueError(f"suite has duplicate scenario run: {scenario}")
        manifest_path = resolve_bound_path(item.get("manifest_path"), base=spec_path.parent, expected=item.get("manifest_sha256"), where=f"suite.runs[{index}].manifest")
        manifest = load_object(manifest_path)
        if manifest.get("schema_version") != MANIFEST_VERSION:
            raise ValueError(f"suite.runs[{index}] has an invalid rehearsal manifest")
        if manifest.get("scenario_id") != scenario:
            raise ValueError(f"suite.runs[{index}] scenario does not match its manifest")
        if manifest.get("lesson_sha256") != lesson_sha:
            raise ValueError(f"suite.runs[{index}] lesson hash does not match the suite")
        by_scenario[scenario] = manifest
        run_receipts.append({
            "scenario_id": scenario,
            "manifest_sha256": digest_path(manifest_path),
            "terminal_status": manifest.get("terminal_status"),
            "verdict_sha256": manifest.get("verdict_sha256"),
            "review_packet_sha256": manifest.get("review_packet_sha256"),
        })
    unknown = sorted(set(by_scenario) - set(scenarios))
    if unknown:
        raise ValueError("suite contains unrequired scenarios: " + ", ".join(unknown))
    missing = [item for item in scenarios if item not in by_scenario]
    failed = [item for item in scenarios if item in by_scenario and by_scenario[item].get("terminal_status") != "passed"]
    status = "passed" if not missing and not failed else ("incomplete" if missing else "failed")
    receipt = {
        "schema_version": SUITE_RECEIPT_VERSION,
        "suite_id": value["suite_id"],
        "lesson_sha256": lesson_sha,
        "status": status,
        "pass_rule": value["pass_rule"],
        "required_scenarios": scenarios,
        "missing_scenarios": missing,
        "failed_scenarios": failed,
        "runs": run_receipts,
        "suite_spec_sha256": digest_path(spec_path),
    }
    if output.exists():
        raise ValueError(f"refusing to overwrite suite receipt: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(receipt))
    print(f"assembled rehearsal suite {value['suite_id']}: {status}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--spec", type=Path, required=True)
    init.add_argument("--output-dir", type=Path, required=True)
    append = commands.add_parser("append")
    append.add_argument("--run-dir", type=Path, required=True)
    append.add_argument("--event", type=Path, required=True)
    batch = commands.add_parser("append-batch")
    batch.add_argument("--run-dir", type=Path, required=True)
    batch.add_argument("--events", type=Path, required=True)
    exchange = commands.add_parser("append-exchange")
    exchange.add_argument("--run-dir", type=Path, required=True)
    exchange.add_argument("--teacher-events", type=Path, required=True)
    exchange.add_argument("--student-events", type=Path, required=True)
    lint_teacher = commands.add_parser("lint-teacher-artifact")
    lint_teacher.add_argument("--run-dir", type=Path, required=True)
    lint_teacher.add_argument("--teacher-events", type=Path, required=True)
    report = commands.add_parser("luna-report")
    report.add_argument("--run-dir", type=Path, required=True)
    report.add_argument("--report", type=Path, required=True)
    alarm_parser = commands.add_parser("alarm")
    alarm_parser.add_argument("--run-dir", type=Path, required=True)
    alarm_parser.add_argument("--alarm", type=Path, required=True)
    finish = commands.add_parser("finalize")
    finish.add_argument("--run-dir", type=Path, required=True)
    finish.add_argument("--verdict", type=Path, required=True)
    packet = commands.add_parser("review-packet")
    packet.add_argument("--run-dir", type=Path, required=True)
    reporter_packet = commands.add_parser("reporter-packet")
    reporter_packet.add_argument("--run-dir", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--run-dir", type=Path, required=True)
    status = commands.add_parser("status")
    status.add_argument("--run-dir", type=Path, required=True)
    suite = commands.add_parser("assemble-suite")
    suite.add_argument("--spec", type=Path, required=True)
    suite.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            init_run(args.spec, args.output_dir)
        elif args.command == "append":
            append_interaction(args.run_dir, args.event)
        elif args.command == "append-batch":
            append_batch(args.run_dir, args.events)
        elif args.command == "append-exchange":
            append_exchange(args.run_dir, args.teacher_events, args.student_events)
        elif args.command == "lint-teacher-artifact":
            lint_teacher_artifact(args.run_dir, args.teacher_events)
        elif args.command == "luna-report":
            record_luna_report(args.run_dir, args.report)
        elif args.command == "alarm":
            alarm(args.run_dir, args.alarm)
        elif args.command == "finalize":
            finalize(args.run_dir, args.verdict)
        elif args.command == "review-packet":
            make_review_packet(args.run_dir)
        elif args.command == "reporter-packet":
            make_reporter_packet(args.run_dir)
        elif args.command == "verify":
            print(json.dumps(verify_run(args.run_dir), indent=2, sort_keys=True))
        elif args.command == "assemble-suite":
            assemble_suite(args.spec, args.output)
        else:
            print(json.dumps(load_object(args.run_dir / "state.json"), indent=2, sort_keys=True))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
