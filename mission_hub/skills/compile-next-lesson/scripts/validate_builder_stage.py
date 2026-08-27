#!/usr/bin/env python3
"""Validate bounded fresh-context lesson-builder stage artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


SHA256 = re.compile(r"^[0-9a-f]{64}$")


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return value


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_keys(value: dict[str, Any], expected: set[str], where: str, errors: list[str]) -> None:
    for key in sorted(expected - set(value)):
        errors.append(f"{where}: missing {key}")
    for key in sorted(set(value) - expected):
        errors.append(f"{where}: unknown {key}")


def nonempty_string(value: Any, where: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where}: must be a non-empty string")


def string_array(value: Any, where: str, errors: list[str], *, nonempty: bool = True) -> None:
    if not isinstance(value, list) or (nonempty and not value) or any(not isinstance(v, str) or not v for v in value):
        errors.append(f"{where}: must be {'a non-empty' if nonempty else 'an'} string array")


def validate_bindings(value: Any, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append("$.input_bindings: must be a non-empty array")
        return
    roles: set[str] = set()
    for index, item in enumerate(value):
        where = f"$.input_bindings[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        exact_keys(item, {"role", "path", "sha256"}, where, errors)
        role, raw_path, expected = item.get("role"), item.get("path"), item.get("sha256")
        nonempty_string(role, f"{where}.role", errors)
        nonempty_string(raw_path, f"{where}.path", errors)
        if isinstance(role, str):
            if role in roles:
                errors.append(f"{where}.role: duplicate {role}")
            roles.add(role)
        if not isinstance(expected, str) or not SHA256.fullmatch(expected):
            errors.append(f"{where}.sha256: must be lowercase SHA-256")
        if isinstance(raw_path, str) and raw_path:
            path = Path(raw_path)
            if not path.is_file():
                errors.append(f"{where}.path: file does not exist")
            elif isinstance(expected, str) and SHA256.fullmatch(expected) and digest(path) != expected:
                errors.append(f"{where}.sha256: does not match file")


def validate_thesis(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    exact_keys(value, {
        "schema_version", "lesson_id", "attempt_id", "decision", "learner_before",
        "language_after", "world_knowledge_after", "dual_use_thesis", "material_count",
        "forbidden_assumptions", "identity_and_chronology_hazards", "grounding_event_seed",
        "alarm", "input_bindings",
    }, "$", errors)
    if value.get("schema_version") != "ninereeds_lesson_thesis_v1":
        errors.append("$.schema_version: must equal ninereeds_lesson_thesis_v1")
    for key in ("lesson_id", "attempt_id", "dual_use_thesis", "grounding_event_seed"):
        nonempty_string(value.get(key), f"$.{key}", errors)
    for key in ("learner_before", "language_after", "world_knowledge_after", "forbidden_assumptions", "identity_and_chronology_hazards"):
        string_array(value.get(key), f"$.{key}", errors)
    decision = value.get("decision")
    if decision not in {"pass", "alarm"}:
        errors.append("$.decision: must be pass or alarm")
    if decision == "pass" and value.get("alarm") is not None:
        errors.append("$.alarm: pass requires null")
    if decision == "alarm" and not isinstance(value.get("alarm"), dict):
        errors.append("$.alarm: alarm decision requires an object")

    material = value.get("material_count")
    if not isinstance(material, dict):
        errors.append("$.material_count: must be an object")
    else:
        exact_keys(material, {
            "selected_tested_item_count", "set_size", "sets", "rationale", "structural_exception",
        }, "$.material_count", errors)
        count = material.get("selected_tested_item_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0 or count % 4:
            errors.append("$.material_count.selected_tested_item_count: must be a non-negative multiple of four")
        if material.get("set_size") != 4:
            errors.append("$.material_count.set_size: must equal 4")
        nonempty_string(material.get("rationale"), "$.material_count.rationale", errors)
        sets = material.get("sets")
        items: list[str] = []
        if not isinstance(sets, list):
            errors.append("$.material_count.sets: must be an array")
        else:
            for index, item_set in enumerate(sets):
                where = f"$.material_count.sets[{index}]"
                if not isinstance(item_set, dict):
                    errors.append(f"{where}: must be an object")
                    continue
                exact_keys(item_set, {"set_id", "items", "purpose"}, where, errors)
                nonempty_string(item_set.get("set_id"), f"{where}.set_id", errors)
                nonempty_string(item_set.get("purpose"), f"{where}.purpose", errors)
                candidates = item_set.get("items")
                if not isinstance(candidates, list) or len(candidates) != 4 or len(set(candidates)) != 4 or any(not isinstance(v, str) or not v for v in candidates):
                    errors.append(f"{where}.items: must contain four unique strings")
                else:
                    items.extend(candidates)
        if len(items) != len(set(items)):
            errors.append("$.material_count.sets: tested items must be unique across sets")
        if isinstance(count, int) and not isinstance(count, bool) and count != len(items):
            errors.append("$.material_count.selected_tested_item_count: must equal listed set items")
        if value.get("lesson_id") == "L000":
            if count != 0 or sets != []:
                errors.append("$.material_count: L000 requires zero tested lexical items and no lexical sets")
            nonempty_string(material.get("structural_exception"), "$.material_count.structural_exception", errors)
        elif items and material.get("structural_exception") is not None:
            errors.append("$.material_count.structural_exception: lexical plans must be null")

    validate_bindings(value.get("input_bindings"), errors)
    return errors


def validate_story(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    exact_keys(value, {
        "schema_version", "lesson_id", "attempt_id", "decision", "story_arc",
        "world_grounding", "pages", "comprehension_strategy", "identity_safety",
        "chronology", "alarm", "input_bindings",
    }, "$", errors)
    if value.get("schema_version") != "ninereeds_story_architecture_v1":
        errors.append("$.schema_version: must equal ninereeds_story_architecture_v1")
    for key in ("lesson_id", "attempt_id"):
        nonempty_string(value.get(key), f"$.{key}", errors)
    decision = value.get("decision")
    if decision not in {"pass", "alarm"}:
        errors.append("$.decision: must be pass or alarm")
    if decision == "pass" and value.get("alarm") is not None:
        errors.append("$.alarm: pass requires null")

    arc = value.get("story_arc")
    if not isinstance(arc, dict):
        errors.append("$.story_arc: must be an object")
    else:
        arc_keys = {
            "initial_state_or_goal", "meaningful_development", "resolution_or_stopping_state",
            "continuity_bindings", "coherence_test",
        }
        exact_keys(arc, arc_keys, "$.story_arc", errors)
        for key in arc_keys - {"continuity_bindings"}:
            nonempty_string(arc.get(key), f"$.story_arc.{key}", errors)
        string_array(arc.get("continuity_bindings"), "$.story_arc.continuity_bindings", errors)

    grounding = value.get("world_grounding")
    if not isinstance(grounding, dict):
        errors.append("$.world_grounding: must be an object")
    else:
        grounding_keys = {
            "selected_world_objective", "scored_world_claims", "visual_safety_metadata",
            "forbidden_novelties",
        }
        exact_keys(grounding, grounding_keys, "$.world_grounding", errors)
        nonempty_string(grounding.get("selected_world_objective"), "$.world_grounding.selected_world_objective", errors)
        string_array(grounding.get("scored_world_claims"), "$.world_grounding.scored_world_claims", errors)
        string_array(grounding.get("visual_safety_metadata"), "$.world_grounding.visual_safety_metadata", errors, nonempty=False)
        string_array(grounding.get("forbidden_novelties"), "$.world_grounding.forbidden_novelties", errors)

    page_ids: set[str] = set()
    page_order: list[str] = []
    functions: set[str] = set()
    pages = value.get("pages")
    if not isinstance(pages, list) or len(pages) < 3:
        errors.append("$.pages: one coherent story requires at least three pages")
    else:
        for index, page in enumerate(pages):
            where = f"$.pages[{index}]"
            if not isinstance(page, dict):
                errors.append(f"{where}: must be an object")
                continue
            exact_keys(page, {
                "id", "story_function", "visual_event", "learner_facing_text",
                "scene_facts", "persistent_bindings",
            }, where, errors)
            identifier = page.get("id")
            nonempty_string(identifier, f"{where}.id", errors)
            if isinstance(identifier, str):
                if identifier in page_ids:
                    errors.append(f"{where}.id: duplicate")
                page_ids.add(identifier)
            function = page.get("story_function")
            if function not in {"initial_state", "meaningful_development", "resolution"}:
                errors.append(f"{where}.story_function: invalid")
            elif isinstance(function, str):
                functions.add(function)
            nonempty_string(page.get("visual_event"), f"{where}.visual_event", errors)
            string_array(page.get("learner_facing_text"), f"{where}.learner_facing_text", errors)
            string_array(page.get("scene_facts"), f"{where}.scene_facts", errors)
            string_array(page.get("persistent_bindings"), f"{where}.persistent_bindings", errors)
    if functions != {"initial_state", "meaningful_development", "resolution"}:
        errors.append("$.pages: must include initial_state, meaningful_development, and resolution")

    strategy = value.get("comprehension_strategy")
    if not isinstance(strategy, dict):
        errors.append("$.comprehension_strategy: must be an object")
    else:
        exact_keys(strategy, {"story_dependent_questions", "rejected_questions_answerable_without_story"}, "$.comprehension_strategy", errors)
        questions = strategy.get("story_dependent_questions")
        if not isinstance(questions, list) or not questions:
            errors.append("$.comprehension_strategy.story_dependent_questions: must be a non-empty array")
        else:
            question_ids: set[str] = set()
            for index, question in enumerate(questions):
                where = f"$.comprehension_strategy.story_dependent_questions[{index}]"
                if not isinstance(question, dict):
                    errors.append(f"{where}: must be an object")
                    continue
                exact_keys(question, {
                    "id", "requires_page_ids", "prompt", "expected_answers", "response_mode",
                    "speaker_identity", "evidence_use", "story_fact", "evidentiary_limit",
                }, where, errors)
                identifier = question.get("id")
                nonempty_string(identifier, f"{where}.id", errors)
                if isinstance(identifier, str):
                    if identifier in question_ids:
                        errors.append(f"{where}.id: duplicate")
                    question_ids.add(identifier)
                requires = question.get("requires_page_ids")
                if not isinstance(requires, list) or not requires or any(v not in page_ids for v in requires):
                    errors.append(f"{where}.requires_page_ids: must cite existing story pages")
                for key in ("prompt", "story_fact", "evidentiary_limit"):
                    nonempty_string(question.get(key), f"{where}.{key}", errors)
                string_array(question.get("expected_answers"), f"{where}.expected_answers", errors)
                mode = question.get("response_mode")
                if mode not in {"learner_self", "nonverbal_selection"}:
                    errors.append(f"{where}.response_mode: story stage permits learner_self or nonverbal_selection")
                if mode == "learner_self":
                    if question.get("speaker_identity") != "Ninereeds" or question.get("evidence_use") != "learner_identity_and_language":
                        errors.append(f"{where}: learner_self must bind Ninereeds and learner_identity_and_language")
                elif mode == "nonverbal_selection":
                    if question.get("speaker_identity") is not None or question.get("evidence_use") != "concept_only_nonverbal":
                        errors.append(f"{where}: nonverbal selection must have null speaker and concept_only_nonverbal")
                answers = question.get("expected_answers")
                if value.get("lesson_id") == "L000" and isinstance(answers, list) and any(
                    isinstance(answer, str)
                    and re.search(r"\bI(?:'m| am)\s+(?:Taro|Emma|Bob|Errol)\b", answer)
                    for answer in answers
                ):
                    errors.append(f"{where}.expected_answers: L000 first-person identity must remain Ninereeds")
        string_array(strategy.get("rejected_questions_answerable_without_story"), "$.comprehension_strategy.rejected_questions_answerable_without_story", errors, nonempty=False)

    expected_identity = {
        "first_person_default_identity": "Ninereeds",
        "l000_non_ninereeds_scored_first_person_forbidden": True,
        "quoted_character_completion_evidence": "never_self_identity_or_independent_first_person",
    }
    if value.get("identity_safety") != expected_identity:
        errors.append("$.identity_safety: must preserve the frozen identity boundary")

    chronology = value.get("chronology")
    if not isinstance(chronology, dict):
        errors.append("$.chronology: must be an object")
    else:
        exact_keys(chronology, {"mode", "forbidden_inferences"}, "$.chronology", errors)
        if chronology.get("mode") not in {"canonical", "noncanonical_instructional"}:
            errors.append("$.chronology.mode: invalid")
        string_array(chronology.get("forbidden_inferences"), "$.chronology.forbidden_inferences", errors)

    validate_bindings(value.get("input_bindings"), errors)
    return errors


def validate_kernel(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    exact_keys(value, {
        "schema_version", "lesson_id", "attempt_id", "decision", "focus_participants",
        "setting", "initial_state_or_goal", "meaningful_development",
        "resolution_or_stopping_state", "continuity_bindings", "world_grounding",
        "language_fit", "chronology", "alarm", "input_bindings",
    }, "$", errors)
    if value.get("schema_version") != "ninereeds_story_kernel_v1":
        errors.append("$.schema_version: must equal ninereeds_story_kernel_v1")
    for key in (
        "lesson_id", "attempt_id", "setting", "initial_state_or_goal",
        "meaningful_development", "resolution_or_stopping_state",
    ):
        nonempty_string(value.get(key), f"$.{key}", errors)
    decision = value.get("decision")
    if decision not in {"pass", "alarm"}:
        errors.append("$.decision: must be pass or alarm")
    if decision == "pass" and value.get("alarm") is not None:
        errors.append("$.alarm: pass requires null")
    if decision == "alarm" and not isinstance(value.get("alarm"), dict):
        errors.append("$.alarm: alarm decision requires an object")

    participants = value.get("focus_participants")
    participant_entities: set[str] = set()
    if not isinstance(participants, list) or not participants:
        errors.append("$.focus_participants: must be a non-empty array")
    else:
        for index, participant in enumerate(participants):
            where = f"$.focus_participants[{index}]"
            if not isinstance(participant, dict):
                errors.append(f"{where}: must be an object")
                continue
            exact_keys(participant, {"entity", "canonical_reference_id", "event_role"}, where, errors)
            for key in ("entity", "canonical_reference_id", "event_role"):
                nonempty_string(participant.get(key), f"{where}.{key}", errors)
            entity = participant.get("entity")
            if isinstance(entity, str):
                if entity in participant_entities:
                    errors.append(f"{where}.entity: duplicate")
                participant_entities.add(entity)
    if value.get("lesson_id") == "L000" and participant_entities != {"Ninereeds", "Taro", "Emma"}:
        errors.append("$.focus_participants: repaired L000 story kernel must contain Ninereeds, Taro, and Emma")

    bindings = value.get("continuity_bindings")
    binding_entities: set[str] = set()
    if not isinstance(bindings, list) or not bindings:
        errors.append("$.continuity_bindings: must be a non-empty array")
    else:
        for index, binding in enumerate(bindings):
            where = f"$.continuity_bindings[{index}]"
            if not isinstance(binding, dict):
                errors.append(f"{where}: must be an object")
                continue
            exact_keys(binding, {"entity", "stable_name", "canonical_reference_id"}, where, errors)
            for key in ("entity", "stable_name", "canonical_reference_id"):
                nonempty_string(binding.get(key), f"{where}.{key}", errors)
            if isinstance(binding.get("entity"), str):
                binding_entities.add(binding["entity"])
    if participant_entities and binding_entities != participant_entities:
        errors.append("$.continuity_bindings: must bind every and only focus participant")

    grounding = value.get("world_grounding")
    if not isinstance(grounding, dict):
        errors.append("$.world_grounding: must be an object")
    else:
        exact_keys(grounding, {
            "selected_world_objective", "scored_story_claims", "visual_safety_metadata",
            "forbidden_novelties",
        }, "$.world_grounding", errors)
        nonempty_string(grounding.get("selected_world_objective"), "$.world_grounding.selected_world_objective", errors)
        string_array(grounding.get("scored_story_claims"), "$.world_grounding.scored_story_claims", errors)
        string_array(grounding.get("forbidden_novelties"), "$.world_grounding.forbidden_novelties", errors)
        metadata = grounding.get("visual_safety_metadata")
        metadata_entities: set[str] = set()
        if not isinstance(metadata, list) or not metadata:
            errors.append("$.world_grounding.visual_safety_metadata: must be a non-empty array")
        else:
            for index, item in enumerate(metadata):
                where = f"$.world_grounding.visual_safety_metadata[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{where}: must be an object")
                    continue
                exact_keys(item, {"entity", "canonical_reference_id", "constraint"}, where, errors)
                for key in ("entity", "canonical_reference_id", "constraint"):
                    nonempty_string(item.get(key), f"{where}.{key}", errors)
                if isinstance(item.get("entity"), str):
                    metadata_entities.add(item["entity"])
        if participant_entities and metadata_entities != participant_entities:
            errors.append("$.world_grounding.visual_safety_metadata: must cover every and only focus participant")

    language = value.get("language_fit")
    if not isinstance(language, dict):
        errors.append("$.language_fit: must be an object")
    else:
        exact_keys(language, {
            "forms_naturally_used", "forms_left_to_controlled_or_mixed_practice",
            "coherence_over_coverage_reason",
        }, "$.language_fit", errors)
        string_array(language.get("forms_naturally_used"), "$.language_fit.forms_naturally_used", errors)
        string_array(language.get("forms_left_to_controlled_or_mixed_practice"), "$.language_fit.forms_left_to_controlled_or_mixed_practice", errors)
        nonempty_string(language.get("coherence_over_coverage_reason"), "$.language_fit.coherence_over_coverage_reason", errors)

    chronology = value.get("chronology")
    if not isinstance(chronology, dict):
        errors.append("$.chronology: must be an object")
    else:
        exact_keys(chronology, {"mode", "forbidden_inferences"}, "$.chronology", errors)
        if chronology.get("mode") not in {"canonical", "noncanonical_instructional"}:
            errors.append("$.chronology.mode: invalid")
        if value.get("lesson_id") == "L000" and chronology.get("mode") != "noncanonical_instructional":
            errors.append("$.chronology.mode: L000 policy-added picture book must be noncanonical_instructional")
        string_array(chronology.get("forbidden_inferences"), "$.chronology.forbidden_inferences", errors)

    validate_bindings(value.get("input_bindings"), errors)
    return errors


def validate_pages(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    exact_keys(value, {
        "schema_version", "lesson_id", "attempt_id", "decision", "pages",
        "identity_safety", "chronology", "alarm", "input_bindings",
    }, "$", errors)
    if value.get("schema_version") != "ninereeds_story_pages_v1":
        errors.append("$.schema_version: must equal ninereeds_story_pages_v1")
    for key in ("lesson_id", "attempt_id"):
        nonempty_string(value.get(key), f"$.{key}", errors)
    decision = value.get("decision")
    if decision not in {"pass", "alarm"}:
        errors.append("$.decision: must be pass or alarm")
    if decision == "pass" and value.get("alarm") is not None:
        errors.append("$.alarm: pass requires null")
    if decision == "alarm" and not isinstance(value.get("alarm"), dict):
        errors.append("$.alarm: alarm decision requires an object")

    pages = value.get("pages")
    page_ids: set[str] = set()
    functions: set[str] = set()
    turns: dict[str, tuple[int, dict[str, Any]]] = {}
    initiations: set[str] = set()
    responses: dict[str, list[str]] = {}
    ordered_turns: list[tuple[int, str, dict[str, Any]]] = []
    if not isinstance(pages, list) or len(pages) < 3:
        errors.append("$.pages: one coherent event requires at least three pages")
    else:
        order = 0
        for page_index, page in enumerate(pages):
            where = f"$.pages[{page_index}]"
            if not isinstance(page, dict):
                errors.append(f"{where}: must be an object")
                continue
            exact_keys(page, {
                "id", "story_function", "visual_event", "scene_facts",
                "persistent_bindings", "dialogue_turns",
            }, where, errors)
            identifier = page.get("id")
            nonempty_string(identifier, f"{where}.id", errors)
            if isinstance(identifier, str):
                if identifier in page_ids:
                    errors.append(f"{where}.id: duplicate")
                page_ids.add(identifier)
            function = page.get("story_function")
            if function not in {"initial_state", "meaningful_development", "resolution"}:
                errors.append(f"{where}.story_function: invalid")
            elif isinstance(function, str):
                functions.add(function)
            nonempty_string(page.get("visual_event"), f"{where}.visual_event", errors)
            string_array(page.get("scene_facts"), f"{where}.scene_facts", errors)
            string_array(page.get("persistent_bindings"), f"{where}.persistent_bindings", errors)
            dialogue = page.get("dialogue_turns")
            if not isinstance(dialogue, list) or not dialogue:
                errors.append(f"{where}.dialogue_turns: must be a non-empty array")
                continue
            for turn_index, turn in enumerate(dialogue):
                turn_where = f"{where}.dialogue_turns[{turn_index}]"
                if not isinstance(turn, dict):
                    errors.append(f"{turn_where}: must be an object")
                    continue
                exact_keys(turn, {"id", "speaker", "text", "exchange_role", "responds_to"}, turn_where, errors)
                for key in ("id", "speaker", "text"):
                    nonempty_string(turn.get(key), f"{turn_where}.{key}", errors)
                turn_id = turn.get("id")
                role = turn.get("exchange_role")
                if role not in {"initiation", "response", "statement"}:
                    errors.append(f"{turn_where}.exchange_role: invalid")
                target = turn.get("responds_to")
                if role == "response":
                    nonempty_string(target, f"{turn_where}.responds_to", errors)
                elif target is not None:
                    errors.append(f"{turn_where}.responds_to: only a response may cite a turn")
                if isinstance(turn_id, str):
                    if turn_id in turns:
                        errors.append(f"{turn_where}.id: duplicate")
                    turns[turn_id] = (order, turn)
                    ordered_turns.append((order, turn_where, turn))
                    if role == "initiation":
                        initiations.add(turn_id)
                order += 1
    if functions != {"initial_state", "meaningful_development", "resolution"}:
        errors.append("$.pages: must include initial_state, meaningful_development, and resolution")

    for order, where, turn in ordered_turns:
        if turn.get("exchange_role") != "response":
            continue
        target = turn.get("responds_to")
        if not isinstance(target, str) or target not in turns:
            errors.append(f"{where}.responds_to: must cite an existing turn")
            continue
        target_order, target_turn = turns[target]
        if target_order >= order:
            errors.append(f"{where}.responds_to: must cite an earlier turn")
        if target_turn.get("exchange_role") != "initiation":
            errors.append(f"{where}.responds_to: must cite an initiation")
        responses.setdefault(target, []).append(turn.get("id", ""))
    for initiation in sorted(initiations):
        count = len(responses.get(initiation, []))
        if count != 1:
            errors.append(f"$.pages: initiation {initiation} must have exactly one explicit response, found {count}")

    expected_identity = {
        "first_person_default_identity": "Ninereeds",
        "l000_non_ninereeds_scored_first_person_forbidden": True,
        "quoted_character_completion_evidence": "never_self_identity_or_independent_first_person",
    }
    if value.get("identity_safety") != expected_identity:
        errors.append("$.identity_safety: must preserve the frozen identity boundary")

    chronology = value.get("chronology")
    if not isinstance(chronology, dict):
        errors.append("$.chronology: must be an object")
    else:
        exact_keys(chronology, {"mode", "forbidden_inferences"}, "$.chronology", errors)
        if chronology.get("mode") not in {"canonical", "noncanonical_instructional"}:
            errors.append("$.chronology.mode: invalid")
        if value.get("lesson_id") == "L000" and chronology.get("mode") != "noncanonical_instructional":
            errors.append("$.chronology.mode: L000 story pages must be noncanonical_instructional")
        string_array(chronology.get("forbidden_inferences"), "$.chronology.forbidden_inferences", errors)

    if value.get("lesson_id") == "L000":
        licensed = {
            "Hello!", "Who are you?", "I'm Ninereeds.", "I'm Taro.", "I'm Emma.",
            "Are you Ninereeds?", "Yes, I'm Ninereeds.",
            "Are you Taro?", "No, I'm not Taro.",
            "Are you Emma or Ninereeds?",
            "Nice to meet you.", "Nice to meet you, too.",
        }
        for _, where, turn in ordered_turns:
            speaker, text_value = turn.get("speaker"), turn.get("text")
            if speaker not in {"Ninereeds", "Taro", "Emma"}:
                errors.append(f"{where}.speaker: repaired L000 story permits only Ninereeds, Taro, or Emma")
            if text_value not in licensed:
                errors.append(f"{where}.text: outside the L000 story-kernel frontier")
            if isinstance(text_value, str) and re.search(r"\bI(?:'m| am)\s+Ninereeds\b", text_value) and speaker != "Ninereeds":
                errors.append(f"{where}: only Ninereeds may say first-person Ninereeds identity")
            if isinstance(text_value, str) and re.search(r"\bI(?:'m| am)\s+Taro\b", text_value) and speaker != "Taro":
                errors.append(f"{where}: only Taro may say first-person Taro identity")
            if isinstance(text_value, str) and re.search(r"\bI(?:'m| am)\s+Emma\b", text_value) and speaker != "Emma":
                errors.append(f"{where}: only Emma may say first-person Emma identity")

    validate_bindings(value.get("input_bindings"), errors)
    return errors


def validate_comprehension(value: dict[str, Any]) -> list[str]:
    if value.get("schema_version") == "ninereeds_lexical_story_comprehension_v1":
        return validate_lexical_comprehension(value)
    errors: list[str] = []
    exact_keys(value, {
        "schema_version", "lesson_id", "attempt_id", "decision",
        "narrative_comprehension_checks", "direct_application_checks",
        "identity_safety", "alarm", "input_bindings",
    }, "$", errors)
    if value.get("schema_version") != "ninereeds_story_comprehension_v1":
        errors.append("$.schema_version: must equal ninereeds_story_comprehension_v1")
    for key in ("lesson_id", "attempt_id"):
        nonempty_string(value.get(key), f"$.{key}", errors)
    decision = value.get("decision")
    if decision not in {"pass", "alarm"}:
        errors.append("$.decision: must be pass or alarm")
    if decision == "pass" and value.get("alarm") is not None:
        errors.append("$.alarm: pass requires null")
    if decision == "alarm" and not isinstance(value.get("alarm"), dict):
        errors.append("$.alarm: alarm decision requires an object")

    input_bindings = value.get("input_bindings")
    validate_bindings(input_bindings, errors)
    page_ids: set[str] = set()
    turn_ids: set[str] = set()
    if isinstance(input_bindings, list):
        candidates = [item for item in input_bindings if isinstance(item, dict) and item.get("role") == "accepted_pages"]
        if len(candidates) != 1:
            errors.append("$.input_bindings: requires exactly one accepted_pages binding")
        else:
            raw_path = candidates[0].get("path")
            if isinstance(raw_path, str) and Path(raw_path).is_file():
                try:
                    accepted_pages = load(Path(raw_path))
                    for page in accepted_pages.get("pages", []):
                        if isinstance(page, dict) and isinstance(page.get("id"), str):
                            page_ids.add(page["id"])
                        if isinstance(page, dict):
                            for turn in page.get("dialogue_turns", []):
                                if isinstance(turn, dict) and isinstance(turn.get("id"), str):
                                    turn_ids.add(turn["id"])
                except ValueError as exc:
                    errors.append(f"$.input_bindings accepted_pages: {exc}")

    checks = value.get("narrative_comprehension_checks")
    check_ids: set[str] = set()
    if not isinstance(checks, list) or len(checks) < 2:
        errors.append("$.narrative_comprehension_checks: must contain at least two story-dependent checks")
    else:
        for index, check in enumerate(checks):
            where = f"$.narrative_comprehension_checks[{index}]"
            if not isinstance(check, dict):
                errors.append(f"{where}: must be an object")
                continue
            exact_keys(check, {
                "id", "requires_page_ids", "evidence_turn_ids", "control", "options",
                "expected_option_ids", "story_fact", "evidentiary_limit",
            }, where, errors)
            identifier = check.get("id")
            nonempty_string(identifier, f"{where}.id", errors)
            if isinstance(identifier, str):
                if identifier in check_ids:
                    errors.append(f"{where}.id: duplicate")
                check_ids.add(identifier)
            requires = check.get("requires_page_ids")
            if not isinstance(requires, list) or not requires or any(v not in page_ids for v in requires):
                errors.append(f"{where}.requires_page_ids: must cite existing accepted pages")
            evidence_turns = check.get("evidence_turn_ids")
            if not isinstance(evidence_turns, list) or not evidence_turns or any(v not in turn_ids for v in evidence_turns):
                errors.append(f"{where}.evidence_turn_ids: must cite existing accepted dialogue turns")
            for key in ("story_fact", "evidentiary_limit"):
                nonempty_string(check.get(key), f"{where}.{key}", errors)

            control = check.get("control")
            control_options: list[Any] = []
            if not isinstance(control, dict):
                errors.append(f"{where}.control: must be an object")
            else:
                exact_keys(control, {"mode", "machine_action", "spoken_text", "semantic_task", "demonstrations", "option_ids"}, f"{where}.control", errors)
                allowed_machine_tasks = {
                    "REPLAY_TURN_SELECT_SPEAKER": "select_portrait_of_speaker_of_replayed_turn",
                    "SHOW_PAGE_SELECT_NEXT_SCENE": "select_scene_of_next_story_page",
                    "SHOW_PAGE_SELECT_PREVIOUS_SCENE": "select_scene_of_previous_story_page",
                }
                if control.get("mode") != "nonverbal_selection" or control.get("machine_action") not in allowed_machine_tasks:
                    errors.append(f"{where}.control: must use one licensed closed nonverbal story-selection action")
                if control.get("spoken_text") is not None:
                    errors.append(f"{where}.control.spoken_text: must be null; machine control is not learner language")
                if control.get("semantic_task") != allowed_machine_tasks.get(control.get("machine_action")):
                    errors.append(f"{where}.control.semantic_task: must match the exact closed machine action")
                demonstrations = control.get("demonstrations")
                if not isinstance(demonstrations, list) or len(demonstrations) < 2:
                    errors.append(f"{where}.control.demonstrations: must contain at least two worked examples")
                else:
                    for demo_index, demo in enumerate(demonstrations):
                        demo_where = f"{where}.control.demonstrations[{demo_index}]"
                        if not isinstance(demo, dict):
                            errors.append(f"{demo_where}: must be an object")
                            continue
                        exact_keys(demo, {"turn_id", "replay_text", "correct_option_id", "feedback_action"}, demo_where, errors)
                        for key in ("turn_id", "replay_text", "correct_option_id"):
                            nonempty_string(demo.get(key), f"{demo_where}.{key}", errors)
                        if demo.get("turn_id") not in turn_ids:
                            errors.append(f"{demo_where}.turn_id: must cite an accepted story turn")
                        if demo.get("feedback_action") != "SHOW_CORRECT_OPTION":
                            errors.append(f"{demo_where}.feedback_action: must equal SHOW_CORRECT_OPTION")
                control_options = control.get("option_ids")
                if (
                    not isinstance(control_options, list)
                    or len(control_options) < 2
                    or any(not isinstance(v, str) or not v for v in control_options)
                    or len(set(control_options)) != len(control_options)
                ):
                    errors.append(f"{where}.control.option_ids: must contain at least two unique IDs")

            options = check.get("options")
            option_ids: list[str] = []
            if not isinstance(options, list) or len(options) < 2:
                errors.append(f"{where}.options: must contain at least two visual options")
            else:
                for option_index, option in enumerate(options):
                    option_where = f"{where}.options[{option_index}]"
                    if not isinstance(option, dict):
                        errors.append(f"{option_where}: must be an object")
                        continue
                    exact_keys(option, {"id", "page_id", "visual_entity"}, option_where, errors)
                    for key in ("id", "visual_entity"):
                        nonempty_string(option.get(key), f"{option_where}.{key}", errors)
                    if option.get("page_id") not in page_ids:
                        errors.append(f"{option_where}.page_id: must cite an accepted page")
                    if isinstance(option.get("id"), str):
                        option_ids.append(option["id"])
            if len(option_ids) != len(set(option_ids)):
                errors.append(f"{where}.options: option IDs must be unique")
            if isinstance(control_options, list) and control_options != option_ids:
                errors.append(f"{where}.control.option_ids: must match options in order")
            if isinstance(control, dict) and isinstance(control.get("demonstrations"), list):
                for demo_index, demo in enumerate(control["demonstrations"]):
                    if isinstance(demo, dict) and demo.get("correct_option_id") not in option_ids:
                        errors.append(f"{where}.control.demonstrations[{demo_index}].correct_option_id: must name a listed option")
            expected = check.get("expected_option_ids")
            if not isinstance(expected, list) or len(expected) != 1 or expected[0] not in option_ids:
                errors.append(f"{where}.expected_option_ids: must name exactly one listed option")
            if value.get("lesson_id") == "L000" and identifier in {
                "nc-01-page04-next-scene", "nc-02-page05-previous-scene",
            }:
                frozen_transition_controls = {
                    "nc-01-page04-next-scene": {
                        "demonstration_turn_ids": ["p01-t01", "p06-t01"],
                        "replay_texts": ["SHOW_PAGE_01", "SHOW_PAGE_06"],
                        "option_ids": ["nc-01-option-taro-scene", "nc-01-option-emma-scene"],
                    },
                    "nc-02-page05-previous-scene": {
                        "demonstration_turn_ids": ["p03-t01", "p08-t01"],
                        "replay_texts": ["SHOW_PAGE_03", "SHOW_PAGE_08"],
                        "option_ids": ["nc-02-option-emma-scene", "nc-02-option-taro-scene"],
                    },
                }[identifier]
                demonstrations = control.get("demonstrations", []) if isinstance(control, dict) else []
                demo_turn_ids = [demo.get("turn_id") for demo in demonstrations if isinstance(demo, dict)]
                replay_texts = [demo.get("replay_text") for demo in demonstrations if isinstance(demo, dict)]
                if demo_turn_ids != frozen_transition_controls["demonstration_turn_ids"]:
                    errors.append(f"{where}.control.demonstrations: must use the frozen non-boundary anchor turns")
                if replay_texts != frozen_transition_controls["replay_texts"]:
                    errors.append(f"{where}.control.demonstrations: replay_text must match the frozen non-boundary pages")
                if option_ids != frozen_transition_controls["option_ids"]:
                    errors.append(f"{where}.options: the two scored checks must use the frozen counterbalanced option order")

    applications = value.get("direct_application_checks")
    if not isinstance(applications, list) or not applications:
        errors.append("$.direct_application_checks: must be a non-empty array")
    else:
        for index, check in enumerate(applications):
            where = f"$.direct_application_checks[{index}]"
            if not isinstance(check, dict):
                errors.append(f"{where}: must be an object")
                continue
            exact_keys(check, {
                "id", "teacher_text", "expected_answers", "response_mode", "speaker_identity",
                "evidence_use", "not_narrative_evidence_reason",
            }, where, errors)
            for key in ("id", "teacher_text", "not_narrative_evidence_reason"):
                nonempty_string(check.get(key), f"{where}.{key}", errors)
            string_array(check.get("expected_answers"), f"{where}.expected_answers", errors)
            if check.get("response_mode") != "learner_self" or check.get("speaker_identity") != "Ninereeds" or check.get("evidence_use") != "learner_identity_and_language":
                errors.append(f"{where}: direct application must preserve Ninereeds learner-self evidence")
            if value.get("lesson_id") == "L000":
                if check.get("teacher_text") != "Who are you?" or check.get("expected_answers") != ["I'm Ninereeds."]:
                    errors.append(f"{where}: L000 direct application must ask Who are you? and expect I'm Ninereeds.")

    expected_identity = {
        "first_person_default_identity": "Ninereeds",
        "l000_non_ninereeds_scored_first_person_forbidden": True,
        "quoted_character_completion_evidence": "never_self_identity_or_independent_first_person",
    }
    if value.get("identity_safety") != expected_identity:
        errors.append("$.identity_safety: must preserve the frozen identity boundary")
    return errors


def validate_lexical_comprehension(value: dict[str, Any]) -> list[str]:
    """Validate story-dependent visual checks when the learner knows only bare labels."""
    errors: list[str] = []
    exact_keys(value, {
        "schema_version", "lesson_id", "attempt_id", "decision", "frontier_labels",
        "narrative_comprehension_checks", "direct_application_checks", "alarm",
        "input_bindings",
    }, "$", errors)
    if value.get("schema_version") != "ninereeds_lexical_story_comprehension_v1":
        errors.append("$.schema_version: must equal ninereeds_lexical_story_comprehension_v1")
    for key in ("lesson_id", "attempt_id"):
        nonempty_string(value.get(key), f"$.{key}", errors)
    decision = value.get("decision")
    if decision not in {"pass", "alarm"}:
        errors.append("$.decision: must be pass or alarm")
    if decision == "pass" and value.get("alarm") is not None:
        errors.append("$.alarm: pass requires null")
    if decision == "alarm" and not isinstance(value.get("alarm"), dict):
        errors.append("$.alarm: alarm decision requires an object")

    labels = value.get("frontier_labels")
    if (
        not isinstance(labels, list)
        or not labels
        or len(labels) % 4 != 0
        or len(set(labels)) != len(labels)
        or any(not isinstance(v, str) or not v for v in labels)
    ):
        errors.append("$.frontier_labels: must contain one or more four-label sets of unique bare labels")
        label_set: set[str] = set()
    else:
        label_set = set(labels)

    validate_bindings(value.get("input_bindings"), errors)
    page_ids: set[str] = set()
    bindings = value.get("input_bindings")
    if isinstance(bindings, list):
        accepted = [item for item in bindings if isinstance(item, dict) and item.get("role") == "accepted_pages"]
        if len(accepted) != 1:
            errors.append("$.input_bindings: requires exactly one accepted_pages binding")
        else:
            raw_path = accepted[0].get("path")
            if isinstance(raw_path, str) and Path(raw_path).is_file():
                try:
                    pages_value = load(Path(raw_path))
                    page_order = [
                        page["id"] for page in pages_value.get("pages", [])
                        if isinstance(page, dict) and isinstance(page.get("id"), str)
                    ]
                    page_ids = set(page_order)
                except ValueError as exc:
                    errors.append(f"$.input_bindings accepted_pages: {exc}")

    checks = value.get("narrative_comprehension_checks")
    seen_check_ids: set[str] = set()
    if not isinstance(checks, list) or len(checks) < 2:
        errors.append("$.narrative_comprehension_checks: must contain at least two story-dependent visual checks")
    else:
        licensed = {
            "SHOW_PAGE_SELECT_NEXT_SCENE": "select_scene_of_next_story_page",
            "SHOW_PAGE_SELECT_PREVIOUS_SCENE": "select_scene_of_previous_story_page",
            "SHOW_STORY_PAGE_SELECT_ACTIVE_OBJECT_LABEL": "select_label_for_object_moved_in_story_scene",
        }
        for index, check in enumerate(checks):
            where = f"$.narrative_comprehension_checks[{index}]"
            if not isinstance(check, dict):
                errors.append(f"{where}: must be an object")
                continue
            raw_control = check.get("control")
            active_object_check = isinstance(raw_control, dict) and raw_control.get("machine_action") == "SHOW_STORY_PAGE_SELECT_ACTIVE_OBJECT_LABEL"
            check_keys = {
                "id", "anchor_page_id", "requires_page_ids", "control",
                "story_fact", "evidentiary_limit",
            }
            check_keys |= {"expected_answers"} if active_object_check else {"options", "expected_option_ids"}
            exact_keys(check, check_keys, where, errors)
            check_id = check.get("id")
            nonempty_string(check_id, f"{where}.id", errors)
            if isinstance(check_id, str):
                if check_id in seen_check_ids:
                    errors.append(f"{where}.id: duplicate")
                seen_check_ids.add(check_id)
            requires = check.get("requires_page_ids")
            minimum_pages = 1 if active_object_check else 2
            if not isinstance(requires, list) or len(requires) < minimum_pages or any(v not in page_ids for v in requires):
                errors.append(f"{where}.requires_page_ids: must cite at least {minimum_pages} accepted story page(s)")
            anchor_page_id = check.get("anchor_page_id")
            if anchor_page_id not in page_ids:
                errors.append(f"{where}.anchor_page_id: must cite an accepted story page")
            for key in ("story_fact", "evidentiary_limit"):
                nonempty_string(check.get(key), f"{where}.{key}", errors)

            control = check.get("control")
            control_options: list[Any] = []
            if not isinstance(control, dict):
                errors.append(f"{where}.control: must be an object")
            else:
                action = control.get("machine_action")
                control_keys = {"mode", "machine_action", "spoken_text", "semantic_task", "demonstrations"}
                control_keys.add("option_labels" if active_object_check else "option_ids")
                exact_keys(control, control_keys, f"{where}.control", errors)
                if control.get("mode") != "nonverbal_selection" or action not in licensed:
                    errors.append(f"{where}.control: must use a licensed closed story action")
                if control.get("spoken_text") is not None:
                    errors.append(f"{where}.control.spoken_text: must be null")
                if control.get("semantic_task") != licensed.get(action):
                    errors.append(f"{where}.control.semantic_task: must match machine_action")
                demonstrations = control.get("demonstrations")
                if active_object_check and demonstrations != []:
                    errors.append(f"{where}.control.demonstrations: active-object story checks must not leak answers through worked examples")
                elif not active_object_check and (not isinstance(demonstrations, list) or len(demonstrations) < 2):
                    errors.append(f"{where}.control.demonstrations: must contain at least two worked examples")
                elif not active_object_check:
                    for demo_index, demo in enumerate(demonstrations):
                        demo_where = f"{where}.control.demonstrations[{demo_index}]"
                        if not isinstance(demo, dict):
                            errors.append(f"{demo_where}: must be an object")
                            continue
                        exact_keys(demo, {"anchor_page_id", "option_page_ids", "expected_page_id", "feedback_action"}, demo_where, errors)
                        demo_anchor = demo.get("anchor_page_id")
                        demo_expected = demo.get("expected_page_id")
                        if demo_anchor not in page_ids:
                            errors.append(f"{demo_where}.anchor_page_id: must cite an accepted page")
                        demo_options = demo.get("option_page_ids")
                        if not isinstance(demo_options, list) or len(demo_options) != 2 or len(set(demo_options)) != 2 or any(v not in page_ids for v in demo_options):
                            errors.append(f"{demo_where}.option_page_ids: must cite exactly two distinct accepted pages")
                        if demo_expected not in (demo_options if isinstance(demo_options, list) else []):
                            errors.append(f"{demo_where}.expected_page_id: must name one demonstration option")
                        if demo_anchor in page_order:
                            anchor_index = page_order.index(demo_anchor)
                            expected_index = anchor_index + (1 if action == "SHOW_PAGE_SELECT_NEXT_SCENE" else -1)
                            actual_adjacent = page_order[expected_index] if 0 <= expected_index < len(page_order) else None
                            if demo_expected != actual_adjacent:
                                errors.append(f"{demo_where}.expected_page_id: must be the actual adjacent page {actual_adjacent!r}")
                        if demo.get("feedback_action") != "SHOW_CORRECT_OPTION":
                            errors.append(f"{demo_where}.feedback_action: must equal SHOW_CORRECT_OPTION")
                control_options = control.get("option_labels" if active_object_check else "option_ids")
                if active_object_check:
                    if not isinstance(control_options, list) or set(control_options) != label_set or len(control_options) != len(label_set):
                        errors.append(f"{where}.control.option_labels: must contain each frontier label exactly once")
                elif not isinstance(control_options, list) or len(control_options) < 2 or len(set(control_options)) != len(control_options):
                    errors.append(f"{where}.control.option_ids: must contain at least two unique option IDs")

            if active_object_check:
                expected_answers = check.get("expected_answers")
                if not isinstance(expected_answers, list) or len(expected_answers) != 1 or expected_answers[0] not in label_set:
                    errors.append(f"{where}.expected_answers: must contain exactly one frontier label")
                continue

            options = check.get("options")
            option_ids: list[str] = []
            if not isinstance(options, list) or len(options) < 2:
                errors.append(f"{where}.options: must contain at least two visual scene options")
            else:
                for option_index, option in enumerate(options):
                    option_where = f"{where}.options[{option_index}]"
                    if not isinstance(option, dict):
                        errors.append(f"{option_where}: must be an object")
                        continue
                    exact_keys(option, {"id", "page_id", "visual_entity"}, option_where, errors)
                    nonempty_string(option.get("id"), f"{option_where}.id", errors)
                    nonempty_string(option.get("visual_entity"), f"{option_where}.visual_entity", errors)
                    if option.get("page_id") not in page_ids:
                        errors.append(f"{option_where}.page_id: must cite an accepted page")
                    if isinstance(option.get("id"), str):
                        option_ids.append(option["id"])
            if len(option_ids) != len(set(option_ids)):
                errors.append(f"{where}.options: option IDs must be unique")
            if isinstance(control_options, list) and control_options != option_ids:
                errors.append(f"{where}.control.option_ids: must match options in order")
            expected = check.get("expected_option_ids")
            if not isinstance(expected, list) or len(expected) != 1 or expected[0] not in option_ids:
                errors.append(f"{where}.expected_option_ids: must name exactly one listed option")
            option_page_by_id = {
                option.get("id"): option.get("page_id")
                for option in options or [] if isinstance(option, dict)
            }
            if (
                isinstance(expected, list) and len(expected) == 1
                and anchor_page_id in page_order and expected[0] in option_page_by_id
            ):
                anchor_index = page_order.index(anchor_page_id)
                action = control.get("machine_action") if isinstance(control, dict) else None
                expected_index = anchor_index + (1 if action == "SHOW_PAGE_SELECT_NEXT_SCENE" else -1)
                actual_adjacent = page_order[expected_index] if 0 <= expected_index < len(page_order) else None
                if option_page_by_id[expected[0]] != actual_adjacent:
                    errors.append(f"{where}.expected_option_ids: selected option must depict actual adjacent page {actual_adjacent!r}")

    applications = value.get("direct_application_checks")
    if not isinstance(applications, list) or not applications:
        errors.append("$.direct_application_checks: must be a non-empty array")
    else:
        for index, check in enumerate(applications):
            where = f"$.direct_application_checks[{index}]"
            if not isinstance(check, dict):
                errors.append(f"{where}: must be an object")
                continue
            exact_keys(check, {"id", "control", "target_label", "expected_answers", "response_mode", "evidence_use", "not_narrative_evidence_reason"}, where, errors)
            nonempty_string(check.get("id"), f"{where}.id", errors)
            nonempty_string(check.get("not_narrative_evidence_reason"), f"{where}.not_narrative_evidence_reason", errors)
            target = check.get("target_label")
            if target not in label_set:
                errors.append(f"{where}.target_label: must be a frontier label")
            if check.get("expected_answers") != [target]:
                errors.append(f"{where}.expected_answers: must contain exactly target_label")
            if check.get("response_mode") != "bare_label" or check.get("evidence_use") != "learner_label_and_concept":
                errors.append(f"{where}: direct application must record independent bare-label evidence")
            control = check.get("control")
            if not isinstance(control, dict):
                errors.append(f"{where}.control: must be an object")
            else:
                exact_keys(control, {"mode", "machine_action", "spoken_text", "asset_role"}, f"{where}.control", errors)
                if control.get("mode") != "bare_label" or control.get("machine_action") != "SHOW_IMAGE_RECORD_BARE_LABEL" or control.get("spoken_text") is not None:
                    errors.append(f"{where}.control: must use silent SHOW_IMAGE_RECORD_BARE_LABEL")
                nonempty_string(control.get("asset_role"), f"{where}.control.asset_role", errors)
    return errors


def validate_lexical_language(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    exact_keys(value, {
        "schema_version", "lesson_id", "attempt_id", "decision", "frontier_labels",
        "gate_order", "interaction_families", "presentation", "presentation_bindings",
        "execution_sequence", "controlled_practice", "gate_rules", "mixed_practice",
        "recap", "interventions", "alarm", "input_bindings",
    }, "$", errors)
    if value.get("schema_version") != "ninereeds_lexical_language_progression_v1":
        errors.append("$.schema_version: must equal ninereeds_lexical_language_progression_v1")
    for key in ("lesson_id", "attempt_id"):
        nonempty_string(value.get(key), f"$.{key}", errors)
    if value.get("decision") not in {"pass", "alarm"}:
        errors.append("$.decision: must be pass or alarm")
    if value.get("decision") == "pass" and value.get("alarm") is not None:
        errors.append("$.alarm: pass requires null")
    labels = value.get("frontier_labels")
    if (
        not isinstance(labels, list)
        or not labels
        or len(labels) % 4 != 0
        or len(set(labels)) != len(labels)
        or any(not isinstance(v, str) or not v for v in labels)
    ):
        errors.append("$.frontier_labels: must contain one or more four-label sets of unique labels")
        labels = []
    expected_gates = ("affirmative", "negative", "W_question", "OR_question")
    expected_order = [
        "presentation:affirmative", "affirmative", "presentation:negative", "negative",
        "presentation:W_question", "W_question", "presentation:OR_question", "OR_question",
        "mixed", "picture_book", "comprehension", "recap",
    ]
    if value.get("gate_order") != expected_order:
        errors.append("$.gate_order: must preserve four local lexical model/test families")
    family_contracts = {
        "affirmative": ("SHOW_LABEL_SELECT_MATCHING_IMAGE", "label_to_kind_recognition", "nonverbal_selection", "concept_only_nonverbal"),
        "negative": ("SHOW_MISMATCH_SELECT_REPLACEMENT", "reject_wrong_label_and_select_matching_label", "nonverbal_selection", "concept_only_nonverbal"),
        "W_question": ("SHOW_IMAGE_RECORD_BARE_LABEL", "image_to_bare_label_production", "bare_label", "learner_label_and_concept"),
        "OR_question": ("SHOW_IMAGE_SELECT_ONE_OF_TWO_LABELS", "forced_choice_label_recognition", "nonverbal_selection", "concept_only_nonverbal"),
    }
    families = value.get("interaction_families")
    if not isinstance(families, dict):
        errors.append("$.interaction_families: must be an object")
        families = {}
    else:
        exact_keys(families, set(expected_gates), "$.interaction_families", errors)
    for gate, expected in family_contracts.items():
        item = families.get(gate)
        where = f"$.interaction_families.{gate}"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        exact_keys(item, {"machine_action", "tested_operation", "response_mode", "evidence_use"}, where, errors)
        actual = tuple(item.get(key) for key in ("machine_action", "tested_operation", "response_mode", "evidence_use"))
        if actual != expected:
            errors.append(f"{where}: must equal the frozen lexical-bootstrap family")

    presentation = value.get("presentation")
    presentation_ids: dict[str, str] = {}
    if not isinstance(presentation, list) or len(presentation) != 4:
        errors.append("$.presentation: must contain one local model for each lexical family")
        presentation = []
    for index, item in enumerate(presentation):
        where = f"$.presentation[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        exact_keys(item, {"id", "gate", "items", "teaching_claims"}, where, errors)
        gate = item.get("gate")
        if gate != expected_gates[index]:
            errors.append(f"{where}.gate: presentations must follow the frozen gate order")
        identifier = item.get("id")
        nonempty_string(identifier, f"{where}.id", errors)
        if isinstance(identifier, str) and isinstance(gate, str):
            presentation_ids[gate] = identifier
        items = item.get("items")
        if not isinstance(items, list) or [x.get("label") for x in items if isinstance(x, dict)] != labels:
            errors.append(f"{where}.items: must model every frontier label in frozen order")
        else:
            for item_index, model in enumerate(items):
                model_where = f"{where}.items[{item_index}]"
                exact_keys(model, {"label", "asset_role", "machine_action"}, model_where, errors)
                nonempty_string(model.get("asset_role"), f"{model_where}.asset_role", errors)
                nonempty_string(model.get("machine_action"), f"{model_where}.machine_action", errors)
        string_array(item.get("teaching_claims"), f"{where}.teaching_claims", errors)
    bindings = value.get("presentation_bindings")
    expected_bindings = {gate: [presentation_ids.get(gate)] for gate in expected_gates}
    if bindings != expected_bindings:
        errors.append("$.presentation_bindings: each gate must bind only its immediately preceding local model")

    exercise_keys = {
        "id", "target_label", "machine_action", "stimulus_asset_roles", "option_labels",
        "expected_answers", "response_mode", "evidence_use", "target_language_required",
        "semantic_invariants",
    }
    exercise_ids: set[str] = set()
    def exercise(item: Any, where: str, gate: str) -> str | None:
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            return None
        exact_keys(item, exercise_keys, where, errors)
        identifier = item.get("id")
        nonempty_string(identifier, f"{where}.id", errors)
        if isinstance(identifier, str):
            if identifier in exercise_ids:
                errors.append(f"{where}.id: duplicate")
            exercise_ids.add(identifier)
        if item.get("target_label") not in labels:
            errors.append(f"{where}.target_label: must be one frontier label")
        for key in ("stimulus_asset_roles", "expected_answers", "semantic_invariants"):
            string_array(item.get(key), f"{where}.{key}", errors)
        string_array(item.get("option_labels"), f"{where}.option_labels", errors, nonempty=False)
        family = families.get(gate, {}) if isinstance(families.get(gate), dict) else {}
        for key in ("machine_action", "response_mode", "evidence_use"):
            if item.get(key) != family.get(key):
                errors.append(f"{where}.{key}: must match the {gate} family")
        expected_language = gate == "W_question"
        if item.get("target_language_required") is not expected_language:
            errors.append(f"{where}.target_language_required: must be {str(expected_language).lower()}")
        if gate == "W_question" and item.get("expected_answers") != [item.get("target_label")]:
            errors.append(f"{where}.expected_answers: open production must equal the bare target label")
        if gate == "OR_question" and (
            not isinstance(item.get("option_labels"), list)
            or len(item["option_labels"]) != 2
            or item.get("target_label") not in item["option_labels"]
        ):
            errors.append(f"{where}.option_labels: OR family requires two labels including the target")
        return identifier if isinstance(identifier, str) else None

    controlled = value.get("controlled_practice")
    controlled_ids: dict[str, list[str]] = {}
    if not isinstance(controlled, dict):
        errors.append("$.controlled_practice: must be an object")
        controlled = {}
    else:
        exact_keys(controlled, set(expected_gates), "$.controlled_practice", errors)
    for gate in expected_gates:
        pool = controlled.get(gate)
        if not isinstance(pool, list) or len(pool) != len(labels):
            errors.append(f"$.controlled_practice.{gate}: must contain one exercise per frontier label")
            continue
        if [x.get("target_label") for x in pool if isinstance(x, dict)] != labels:
            errors.append(f"$.controlled_practice.{gate}: must test every frontier label once in frozen order")
        controlled_ids[gate] = [v for i, item in enumerate(pool) if (v := exercise(item, f"$.controlled_practice.{gate}[{i}]", gate))]

    mixed = value.get("mixed_practice")
    mixed_ids: list[str] = []
    if not isinstance(mixed, dict):
        errors.append("$.mixed_practice: must be an object")
    else:
        exact_keys(mixed, {"seed", "ordered_exercises", "minimum_scored_items", "maximum_scored_items", "completion_fraction"}, "$.mixed_practice", errors)
        nonempty_string(mixed.get("seed"), "$.mixed_practice.seed", errors)
        expected_mixed_count = len(labels) * len(expected_gates)
        expected_mixed_maximum = expected_mixed_count + min(8, len(labels))
        if mixed.get("minimum_scored_items") != expected_mixed_count or mixed.get("maximum_scored_items") != expected_mixed_maximum or mixed.get("completion_fraction") != 0.8:
            errors.append("$.mixed_practice: minimum must cover every label-family pair once, maximum must add a bounded label-balanced extension, and completion fraction must be 0.8")
        items = mixed.get("ordered_exercises")
        if not isinstance(items, list) or len(items) != expected_mixed_count:
            errors.append("$.mixed_practice.ordered_exercises: must contain every label-family pair once")
        else:
            for index, item in enumerate(items):
                gate = item.get("family") if isinstance(item, dict) else None
                if gate not in expected_gates:
                    errors.append(f"$.mixed_practice.ordered_exercises[{index}].family: invalid")
                    continue
                stripped = {k: v for k, v in item.items() if k != "family"}
                identifier = exercise(stripped, f"$.mixed_practice.ordered_exercises[{index}]", gate)
                if identifier is not None:
                    mixed_ids.append(identifier)
    recap = value.get("recap")
    recap_ids: list[str] = []
    if not isinstance(recap, list) or len(recap) != len(labels):
        errors.append("$.recap: must contain one bare-label check per frontier label")
    else:
        for index, item in enumerate(recap):
            identifier = exercise(item, f"$.recap[{index}]", "W_question")
            if identifier is not None:
                recap_ids.append(identifier)
    expected_execution: list[dict[str, Any]] = []
    for gate in expected_gates:
        expected_execution.append({"phase": "presentation", "exercise_ids": [presentation_ids.get(gate)]})
        expected_execution.append({"phase": gate, "exercise_ids": controlled_ids.get(gate, [])})
    expected_execution.extend((
        {"phase": "mixed", "exercise_ids": mixed_ids},
        {"phase": "recap", "exercise_ids": recap_ids},
    ))
    if value.get("execution_sequence") != expected_execution:
        errors.append("$.execution_sequence: must exactly interleave each local model and gate, then mixed and recap")

    rules = value.get("gate_rules")
    if not isinstance(rules, dict):
        errors.append("$.gate_rules: must be an object")
    else:
        exact_keys(rules, {"required_cold_items_per_gate", "gate_acquisition_fraction", "independent_success_rule", "advance_rule", "train_more_trigger", "post_train_more_rule"}, "$.gate_rules", errors)
        if rules.get("required_cold_items_per_gate") != len(labels) or rules.get("gate_acquisition_fraction") != 0.75:
            errors.append("$.gate_rules: must require one cold item per frontier label and preserve the 0.75 acquisition fraction")
        for key in ("independent_success_rule", "advance_rule", "train_more_trigger", "post_train_more_rule"):
            nonempty_string(rules.get(key), f"$.gate_rules.{key}", errors)
    if not isinstance(value.get("interventions"), dict):
        errors.append("$.interventions: must be an object")
    validate_bindings(value.get("input_bindings"), errors)
    return errors


def validate_language(value: dict[str, Any]) -> list[str]:
    if value.get("schema_version") == "ninereeds_lexical_language_progression_v1":
        return validate_lexical_language(value)
    errors: list[str] = []
    exact_keys(value, {
        "schema_version", "lesson_id", "attempt_id", "decision", "gate_order",
        "presentation", "presentation_bindings", "execution_sequence", "controlled_practice", "gate_rules", "mixed_practice", "recap",
        "interventions", "identity_safety", "alarm", "input_bindings",
    }, "$", errors)
    if value.get("schema_version") != "ninereeds_language_progression_v1":
        errors.append("$.schema_version: must equal ninereeds_language_progression_v1")
    for key in ("lesson_id", "attempt_id"):
        nonempty_string(value.get(key), f"$.{key}", errors)
    decision = value.get("decision")
    if decision not in {"pass", "alarm"}:
        errors.append("$.decision: must be pass or alarm")
    if decision == "pass" and value.get("alarm") is not None:
        errors.append("$.alarm: pass requires null")
    if decision == "alarm" and not isinstance(value.get("alarm"), dict):
        errors.append("$.alarm: alarm decision requires an object")
    expected_order = [
        "presentation:greeting", "presentation:self_identification", "presentation:affirmative", "affirmative",
        "presentation:negative", "negative", "presentation:W_question", "W_question",
        "presentation:OR_question", "OR_question", "presentation:reciprocity", "reciprocity",
        "mixed", "picture_book", "comprehension", "recap",
    ]
    if value.get("gate_order") != expected_order:
        errors.append("$.gate_order: must preserve the complete frozen order")

    presentation = value.get("presentation")
    presentation_ids: set[str] = set()
    presentation_gates: set[str] = set()
    if not isinstance(presentation, list) or len(presentation) != 7:
        errors.append("$.presentation: L000 requires exactly seven isolated models")
    else:
        for index, item in enumerate(presentation):
            where = f"$.presentation[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{where}: must be an object")
                continue
            exact_keys(item, {"id", "gate", "participants", "visual_requirement", "dialogue", "teaching_claims"}, where, errors)
            identifier = item.get("id")
            nonempty_string(identifier, f"{where}.id", errors)
            if isinstance(identifier, str):
                if identifier in presentation_ids:
                    errors.append(f"{where}.id: duplicate")
                presentation_ids.add(identifier)
            gate = item.get("gate")
            if gate not in {"greeting", "self_identification", "affirmative", "negative", "W_question", "OR_question", "reciprocity"}:
                errors.append(f"{where}.gate: invalid")
            elif isinstance(gate, str):
                presentation_gates.add(gate)
            string_array(item.get("participants"), f"{where}.participants", errors)
            nonempty_string(item.get("visual_requirement"), f"{where}.visual_requirement", errors)
            string_array(item.get("teaching_claims"), f"{where}.teaching_claims", errors)
            dialogue = item.get("dialogue")
            if not isinstance(dialogue, list) or not dialogue:
                errors.append(f"{where}.dialogue: must be a non-empty array")
            else:
                dialogue_texts: list[str] = []
                for turn_index, turn in enumerate(dialogue):
                    turn_where = f"{where}.dialogue[{turn_index}]"
                    if not isinstance(turn, dict):
                        errors.append(f"{turn_where}: must be an object")
                        continue
                    exact_keys(turn, {"speaker", "text"}, turn_where, errors)
                    nonempty_string(turn.get("speaker"), f"{turn_where}.speaker", errors)
                    nonempty_string(turn.get("text"), f"{turn_where}.text", errors)
                    if isinstance(turn.get("text"), str):
                        dialogue_texts.append(turn["text"])
                if gate == "negative" and any(
                    re.search(r"No, I'm not (?:Taro|Emma|Bob|Errol|Ninereeds)\.\s+I'm ", text)
                    for text in dialogue_texts
                ):
                    errors.append(f"{where}.dialogue: early negative presentation must not append an affirmative correction")
                if gate == "reciprocity" and not {
                    "Nice to meet you.", "Nice to meet you, too."
                } <= set(dialogue_texts):
                    errors.append(f"{where}.dialogue: reciprocity presentation must model both turns explicitly")
    required_presentation = {"greeting", "self_identification", "affirmative", "negative", "W_question", "OR_question", "reciprocity"}
    if not required_presentation <= presentation_gates:
        errors.append("$.presentation: must cover greeting, self_identification, affirmative, negative, W_question, OR_question, and reciprocity")
    expected_bindings = {
        "affirmative": ["presentation-greeting", "presentation-self-identification", "presentation-affirmative"],
        "negative": ["presentation-negative"],
        "W_question": ["presentation-W-question"],
        "OR_question": ["presentation-OR-question"],
        "reciprocity": ["presentation-reciprocity"],
    }
    if value.get("presentation_bindings") != expected_bindings:
        errors.append("$.presentation_bindings: every tested gate must be led immediately by its exact local presentation")
    controlled_value = value.get("controlled_practice")
    expected_execution: list[dict[str, Any]] = []
    if isinstance(controlled_value, dict):
        for gate in ("affirmative", "negative", "W_question", "OR_question", "reciprocity"):
            expected_execution.append({"phase": "presentation", "exercise_ids": expected_bindings[gate]})
            pool = controlled_value.get(gate)
            expected_execution.append({
                "phase": gate,
                "exercise_ids": [item.get("id") for item in pool if isinstance(item, dict)] if isinstance(pool, list) else [],
            })
    mixed_value = value.get("mixed_practice")
    expected_execution.append({
        "phase": "mixed",
        "exercise_ids": mixed_value.get("ordered_exercise_ids", []) if isinstance(mixed_value, dict) else [],
    })
    recap_value = value.get("recap")
    expected_execution.append({
        "phase": "recap",
        "exercise_ids": [item.get("id") for item in recap_value if isinstance(item, dict)] if isinstance(recap_value, list) else [],
    })
    if value.get("execution_sequence") != expected_execution:
        errors.append("$.execution_sequence: must exactly interleave each local presentation with its controlled gate, then mixed practice and recap")
    if isinstance(presentation, list):
        actual_presentation_order = [item.get("gate") for item in presentation if isinstance(item, dict)]
        expected_presentation_order = ["greeting", "self_identification", "affirmative", "negative", "W_question", "OR_question", "reciprocity"]
        if actual_presentation_order != expected_presentation_order:
            errors.append("$.presentation: must preserve isolated greeting, self-identification, affirmative, negative, W, OR, reciprocity order")
        expected_dialogues = {
            "greeting": [("Taro", "Hello!"), ("Ninereeds", "Hello!")],
            "self_identification": [
                ("Taro", "I'm Taro."),
                ("Ninereeds", "I'm Ninereeds."),
                ("Emma", "I'm Emma."),
                ("Bob", "I'm Bob."),
                ("Taro", "I'm Taro."),
                ("Errol", "I'm Errol."),
            ],
            "affirmative": [("Taro", "Are you Ninereeds?"), ("Ninereeds", "Yes, I'm Ninereeds.")],
            "negative": [("Taro", "Are you Taro?"), ("Ninereeds", "No, I'm not Taro.")],
            "W_question": [("Taro", "Who are you?"), ("Ninereeds", "I'm Ninereeds.")],
            "OR_question": [("Taro", "Are you Taro or Ninereeds?"), ("Ninereeds", "I'm Ninereeds.")],
            "reciprocity": [("Taro", "Nice to meet you."), ("Ninereeds", "Nice to meet you, too.")],
        }
        for index, item in enumerate(presentation):
            if not isinstance(item, dict) or item.get("gate") not in expected_dialogues:
                continue
            actual_dialogue = [
                (turn.get("speaker"), turn.get("text"))
                for turn in item.get("dialogue", [])
                if isinstance(turn, dict)
            ]
            if actual_dialogue != expected_dialogues[item["gate"]]:
                errors.append(f"$.presentation[{index}].dialogue: must match the isolated model and ground every participant before scored practice")

    exercise_keys = {
        "id", "teacher_speaker", "teacher_opening", "target_prompt", "expected_target_answers",
        "teacher_closing", "expected_closing_answers", "visual_participants", "visual_requirement",
        "semantic_invariants", "response_mode", "speaker_identity", "evidence_use",
        "target_language_required",
    }
    exercise_ids: set[str] = set()
    exercise_gate: dict[str, str] = {}

    def validate_language_exercise(exercise: Any, where: str, gate: str) -> None:
        if not isinstance(exercise, dict):
            errors.append(f"{where}: must be an object")
            return
        exact_keys(exercise, exercise_keys, where, errors)
        for key in ("id", "teacher_speaker", "teacher_opening", "target_prompt", "visual_requirement"):
            nonempty_string(exercise.get(key), f"{where}.{key}", errors)
        if exercise.get("teacher_closing") is not None:
            errors.append(f"{where}.teacher_closing: controlled gates must end after the isolated target response")
        for key in ("expected_target_answers", "visual_participants", "semantic_invariants"):
            string_array(exercise.get(key), f"{where}.{key}", errors)
        string_array(
            exercise.get("expected_closing_answers"),
            f"{where}.expected_closing_answers",
            errors,
            nonempty=False,
        )
        identifier = exercise.get("id")
        if isinstance(identifier, str):
            if identifier in exercise_ids:
                errors.append(f"{where}.id: duplicate")
            exercise_ids.add(identifier)
            exercise_gate[identifier] = gate
        if exercise.get("response_mode") != "learner_self" or exercise.get("speaker_identity") != "Ninereeds" or exercise.get("evidence_use") != "learner_identity_and_language":
            errors.append(f"{where}: every scored language exercise must be Ninereeds learner-self evidence")
        if exercise.get("target_language_required") is not True:
            errors.append(f"{where}.target_language_required: must be true")
        answers = exercise.get("expected_target_answers")
        if isinstance(answers, list) and any(
            isinstance(answer, str) and re.search(r"\bI(?:'m| am)\s+(?:Taro|Emma|Bob|Errol)\b", answer)
            for answer in answers
        ):
            errors.append(f"{where}.expected_target_answers: first-person scored identity must remain Ninereeds")
        if exercise.get("expected_closing_answers") != []:
            errors.append(f"{where}.expected_closing_answers: controlled gates must not append a second response operation")
        prompt = exercise.get("target_prompt")
        if gate == "affirmative" and (prompt != "Are you Ninereeds?" or answers != ["Yes, I'm Ninereeds."]):
            errors.append(f"{where}: affirmative contract is incorrect")
        elif gate == "negative" and (
            not isinstance(prompt, str) or re.fullmatch(r"Are you (Taro|Emma|Bob|Errol)\?", prompt) is None
            or not isinstance(answers, list) or len(answers) != 1
            or re.fullmatch(r"No, I'm not (Taro|Emma|Bob|Errol)\.", answers[0]) is None
        ):
            errors.append(f"{where}: negative contract is incorrect")
        elif gate == "W_question" and (prompt != "Who are you?" or answers != ["I'm Ninereeds."]):
            errors.append(f"{where}: W-question contract is incorrect")
        elif gate == "OR_question" and (
            not isinstance(prompt, str) or re.fullmatch(r"Are you (Taro|Emma|Bob|Errol) or Ninereeds\?", prompt) is None
            or answers != ["I'm Ninereeds."]
        ):
            errors.append(f"{where}: OR-question contract is incorrect")
        elif gate == "reciprocity" and (prompt != "Nice to meet you." or answers != ["Nice to meet you, too."]):
            errors.append(f"{where}: reciprocity contract is incorrect")

    controlled = value.get("controlled_practice")
    controlled_ids: list[str] = []
    if not isinstance(controlled, dict):
        errors.append("$.controlled_practice: must be an object")
    else:
        exact_keys(controlled, {"affirmative", "negative", "W_question", "OR_question", "reciprocity"}, "$.controlled_practice", errors)
        for gate in ("affirmative", "negative", "W_question", "OR_question", "reciprocity"):
            pool = controlled.get(gate)
            if not isinstance(pool, list) or len(pool) != 4:
                errors.append(f"$.controlled_practice.{gate}: L000 requires exactly four exercises")
                continue
            for index, exercise in enumerate(pool):
                validate_language_exercise(exercise, f"$.controlled_practice.{gate}[{index}]", gate)
                if isinstance(exercise, dict) and isinstance(exercise.get("id"), str):
                    controlled_ids.append(exercise["id"])

    gate_rules = value.get("gate_rules")
    if not isinstance(gate_rules, dict):
        errors.append("$.gate_rules: must be an object")
    else:
        exact_keys(gate_rules, {
            "required_cold_items_per_gate", "maximum_scored_attempts_per_base_item",
            "gate_acquisition_fraction", "operational_advance_after_budget",
            "independent_success_rule", "advance_rule", "overall_mastery_rule", "train_more_trigger",
            "post_train_more_rule",
        }, "$.gate_rules", errors)
        if gate_rules.get("required_cold_items_per_gate") != 4:
            errors.append("$.gate_rules.required_cold_items_per_gate: must equal 4")
        if gate_rules.get("maximum_scored_attempts_per_base_item") != 2:
            errors.append("$.gate_rules.maximum_scored_attempts_per_base_item: must equal 2")
        if gate_rules.get("gate_acquisition_fraction") != 0.75:
            errors.append("$.gate_rules.gate_acquisition_fraction: must equal 0.75")
        if gate_rules.get("operational_advance_after_budget") is not True:
            errors.append("$.gate_rules.operational_advance_after_budget: must be true")
        for key in ("independent_success_rule", "advance_rule", "overall_mastery_rule", "train_more_trigger", "post_train_more_rule"):
            nonempty_string(gate_rules.get(key), f"$.gate_rules.{key}", errors)

    mixed = value.get("mixed_practice")
    if not isinstance(mixed, dict):
        errors.append("$.mixed_practice: must be an object")
    else:
        exact_keys(mixed, {"seed", "ordered_exercise_ids", "minimum_scored_items", "maximum_scored_items", "completion_fraction", "semantic_and_language_scores_separate"}, "$.mixed_practice", errors)
        nonempty_string(mixed.get("seed"), "$.mixed_practice.seed", errors)
        order = mixed.get("ordered_exercise_ids")
        if not isinstance(order, list) or len(order) != 20 or len(set(order)) != 20 or set(order) != set(controlled_ids):
            errors.append("$.mixed_practice.ordered_exercise_ids: must contain every controlled exercise exactly once")
        if mixed.get("minimum_scored_items") != 16 or mixed.get("maximum_scored_items") != 20 or mixed.get("completion_fraction") != 0.8:
            errors.append("$.mixed_practice: must preserve the 16/20 and 0.8 bounds")
        if mixed.get("semantic_and_language_scores_separate") is not True:
            errors.append("$.mixed_practice.semantic_and_language_scores_separate: must be true")

    recap = value.get("recap")
    if not isinstance(recap, list) or len(recap) < 5:
        errors.append("$.recap: must contain a complete closing retrieval")
    else:
        for index, exercise in enumerate(recap):
            if not isinstance(exercise, dict):
                errors.append(f"$.recap[{index}]: must be an object")
                continue
            gate = exercise.get("recap_gate")
            exact_keys(exercise, exercise_keys | {"recap_gate"}, f"$.recap[{index}]", errors)
            stripped = {k: v for k, v in exercise.items() if k != "recap_gate"}
            if gate not in {"affirmative", "negative", "W_question", "OR_question", "reciprocity"}:
                errors.append(f"$.recap[{index}].recap_gate: invalid")
            else:
                validate_language_exercise(stripped, f"$.recap[{index}]", gate)

    interventions = value.get("interventions")
    if not isinstance(interventions, dict):
        errors.append("$.interventions: must be an object")
    else:
        exact_keys(interventions, {"ordinary_correction_sequence", "train_more", "train_longer", "alarm_conditions"}, "$.interventions", errors)
        string_array(interventions.get("ordinary_correction_sequence"), "$.interventions.ordinary_correction_sequence", errors)
        string_array(interventions.get("alarm_conditions"), "$.interventions.alarm_conditions", errors)
        reserve_ids: list[str] = []
        train_more = interventions.get("train_more")
        if not isinstance(train_more, dict):
            errors.append("$.interventions.train_more: must be an object")
        else:
            exact_keys(train_more, {"decision_rule", "reserve_by_gate", "material_source", "maximum_release_per_gate", "return_rule"}, "$.interventions.train_more", errors)
            nonempty_string(train_more.get("decision_rule"), "$.interventions.train_more.decision_rule", errors)
            nonempty_string(train_more.get("return_rule"), "$.interventions.train_more.return_rule", errors)
            if train_more.get("maximum_release_per_gate") != 2:
                errors.append("$.interventions.train_more.maximum_release_per_gate: must equal 2")
            if train_more.get("material_source") != "preauthored_reserve_only":
                errors.append("$.interventions.train_more.material_source: live generation is forbidden")
            reserve = train_more.get("reserve_by_gate")
            if not isinstance(reserve, dict):
                errors.append("$.interventions.train_more.reserve_by_gate: must be an object")
            else:
                exact_keys(reserve, {"affirmative", "negative", "W_question", "OR_question", "reciprocity"}, "$.interventions.train_more.reserve_by_gate", errors)
                for gate in ("affirmative", "negative", "W_question", "OR_question", "reciprocity"):
                    pool = reserve.get(gate)
                    if not isinstance(pool, list) or len(pool) != 2:
                        errors.append(f"$.interventions.train_more.reserve_by_gate.{gate}: must contain exactly two pre-authored items")
                        continue
                    for index, exercise in enumerate(pool):
                        validate_language_exercise(exercise, f"$.interventions.train_more.reserve_by_gate.{gate}[{index}]", gate)
                        if isinstance(exercise, dict) and isinstance(exercise.get("id"), str):
                            reserve_ids.append(exercise["id"])
        train_longer = interventions.get("train_longer")
        if not isinstance(train_longer, dict):
            errors.append("$.interventions.train_longer: must be an object")
        else:
            exact_keys(train_longer, {"decision_rule", "additional_ordered_exercise_ids", "material_source", "maximum_additional_scored_items", "stop_rule"}, "$.interventions.train_longer", errors)
            nonempty_string(train_longer.get("decision_rule"), "$.interventions.train_longer.decision_rule", errors)
            nonempty_string(train_longer.get("stop_rule"), "$.interventions.train_longer.stop_rule", errors)
            additional = train_longer.get("additional_ordered_exercise_ids")
            known_ids = set(controlled_ids)
            if not isinstance(additional, list) or len(additional) != 8 or any(v not in known_ids for v in additional) or any(a == b for a, b in zip(additional, additional[1:])):
                errors.append("$.interventions.train_longer.additional_ordered_exercise_ids: must contain eight known items without immediate repeats")
            if train_longer.get("maximum_additional_scored_items") != 8:
                errors.append("$.interventions.train_longer.maximum_additional_scored_items: must equal 8")
            if train_longer.get("material_source") != "frozen_base_ids_only":
                errors.append("$.interventions.train_longer.material_source: must equal frozen_base_ids_only so TRAIN_LONGER cannot release TRAIN_MORE reserves")

    if value.get("identity_safety") != {
        "scored_speaker_identity": "Ninereeds",
        "non_ninereeds_first_person_is_modeled_only": True,
        "quoted_character_completion_forbidden": True,
    }:
        errors.append("$.identity_safety: must preserve L000 learner identity")
    validate_bindings(value.get("input_bindings"), errors)
    return errors


def validate_visual_plan(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    exact_keys(value, {
        "schema_version", "lesson_id", "attempt_id", "decision", "master_assets",
        "literal_crops", "usage_map", "pixel_acceptance_rules", "alarm_conditions",
        "alarm", "input_bindings",
    }, "$", errors)
    if value.get("schema_version") != "ninereeds_visual_plan_stage_v1":
        errors.append("$.schema_version: must equal ninereeds_visual_plan_stage_v1")
    for key in ("lesson_id", "attempt_id"):
        nonempty_string(value.get(key), f"$.{key}", errors)
    decision = value.get("decision")
    if decision not in {"pass", "alarm"}:
        errors.append("$.decision: must be pass or alarm")
    if decision == "pass" and value.get("alarm") is not None:
        errors.append("$.alarm: pass requires null")

    required_masters = {
        "portrait-taro", "portrait-emma", "portrait-errol", "portrait-ninereeds", "portrait-bob",
        "scene-emma-bob", "scene-taro-errol",
        "scene-taro-ninereeds", "scene-emma-ninereeds", "scene-bob-ninereeds", "scene-errol-ninereeds",
    }
    masters = value.get("master_assets")
    master_ids: set[str] = set()
    if not isinstance(masters, list):
        errors.append("$.master_assets: must be an array")
    else:
        for index, item in enumerate(masters):
            where = f"$.master_assets[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{where}: must be an object")
                continue
            exact_keys(item, {"asset_id", "operation", "purpose", "participants", "reference_bindings", "scene_inventory", "teaching_claims", "prompt", "forbidden"}, where, errors)
            identifier = item.get("asset_id")
            nonempty_string(identifier, f"{where}.asset_id", errors)
            if isinstance(identifier, str):
                if identifier in master_ids:
                    errors.append(f"{where}.asset_id: duplicate")
                master_ids.add(identifier)
            operation = item.get("operation")
            if operation not in {"reuse", "imagegen_generate"}:
                errors.append(f"{where}.operation: must be reuse or imagegen_generate")
            if item.get("purpose") not in {"portrait", "presentation_scene", "practice_scene", "picture_book_master"}:
                errors.append(f"{where}.purpose: invalid")
            for key in ("participants", "scene_inventory", "teaching_claims", "forbidden"):
                string_array(item.get(key), f"{where}.{key}", errors)
            refs = item.get("reference_bindings")
            if not isinstance(refs, list):
                errors.append(f"{where}.reference_bindings: must be an array")
            else:
                for ref_index, ref in enumerate(refs):
                    ref_where = f"{where}.reference_bindings[{ref_index}]"
                    if not isinstance(ref, dict):
                        errors.append(f"{ref_where}: must be an object")
                        continue
                    if set(ref) == {"entity", "planned_asset_id"}:
                        nonempty_string(ref.get("entity"), f"{ref_where}.entity", errors)
                        nonempty_string(ref.get("planned_asset_id"), f"{ref_where}.planned_asset_id", errors)
                        continue
                    exact_keys(ref, {"entity", "reference_id", "path", "sha256"}, ref_where, errors)
                    for key in ("entity", "reference_id", "path"):
                        nonempty_string(ref.get(key), f"{ref_where}.{key}", errors)
                    expected = ref.get("sha256")
                    raw_path = ref.get("path")
                    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
                        errors.append(f"{ref_where}.sha256: invalid")
                    elif isinstance(raw_path, str) and Path(raw_path).is_file() and digest(Path(raw_path)) != expected:
                        errors.append(f"{ref_where}.sha256: does not match file")
            if operation == "imagegen_generate":
                nonempty_string(item.get("prompt"), f"{where}.prompt", errors)
            elif item.get("prompt") is not None:
                errors.append(f"{where}.prompt: reuse must use null")
    if value.get("lesson_id") == "L000" and master_ids != required_masters:
        errors.append(f"$.master_assets: L000 requires exact closed inventory {sorted(required_masters)}")

    crops = value.get("literal_crops")
    crop_ids: set[str] = set()
    if not isinstance(crops, list):
        errors.append("$.literal_crops: must be an array")
    else:
        for index, item in enumerate(crops):
            where = f"$.literal_crops[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{where}: must be an object")
                continue
            exact_keys(item, {"asset_id", "parent_asset_id", "crop_intent", "teaching_claims", "crop_xywh"}, where, errors)
            for key in ("asset_id", "parent_asset_id", "crop_intent"):
                nonempty_string(item.get(key), f"{where}.{key}", errors)
            if isinstance(item.get("asset_id"), str):
                if item["asset_id"] in crop_ids or item["asset_id"] in master_ids:
                    errors.append(f"{where}.asset_id: duplicate")
                crop_ids.add(item["asset_id"])
            if item.get("parent_asset_id") not in master_ids:
                errors.append(f"{where}.parent_asset_id: must cite a master")
            string_array(item.get("teaching_claims"), f"{where}.teaching_claims", errors)
            if item.get("crop_xywh") is not None:
                errors.append(f"{where}.crop_xywh: planning stage must leave coordinates null until pixels exist")

    usage = value.get("usage_map")
    used_assets: set[str] = set()
    component_ids: set[str] = set()
    if not isinstance(usage, list) or not usage:
        errors.append("$.usage_map: must be a non-empty array")
    else:
        for index, item in enumerate(usage):
            where = f"$.usage_map[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{where}: must be an object")
                continue
            exact_keys(item, {"lesson_component_id", "asset_ids"}, where, errors)
            identifier = item.get("lesson_component_id")
            nonempty_string(identifier, f"{where}.lesson_component_id", errors)
            if isinstance(identifier, str):
                if identifier in component_ids:
                    errors.append(f"{where}.lesson_component_id: duplicate")
                component_ids.add(identifier)
            asset_ids = item.get("asset_ids")
            if not isinstance(asset_ids, list) or not asset_ids or any(v not in master_ids | crop_ids for v in asset_ids):
                errors.append(f"{where}.asset_ids: must cite one or more planned assets")
            elif isinstance(asset_ids, list):
                used_assets.update(asset_ids)
    required_components = {
        "presentation-greeting", "presentation-self-identification", "presentation-affirmative",
        "presentation-negative", "presentation-W-question", "presentation-OR-question",
        "presentation-reciprocity", "practice-taro", "practice-emma", "practice-bob",
        "practice-errol", "page-01", "page-02", "page-03", "page-04", "page-05",
        "page-06", "page-07", "page-08", "nc-01-page04-next-scene",
        "nc-02-page05-previous-scene",
    }
    if value.get("lesson_id") == "L000" and not required_components <= component_ids:
        errors.append("$.usage_map: missing required L000 presentation, practice, story, or comprehension component")
    if master_ids and not master_ids <= used_assets:
        errors.append("$.usage_map: every master must be used")

    if value.get("lesson_id") == "L000" and isinstance(usage, list):
        usage_assets = {
            item.get("lesson_component_id"): set(item.get("asset_ids", []))
            for item in usage if isinstance(item, dict) and isinstance(item.get("lesson_component_id"), str)
        }
        bindings = value.get("input_bindings")
        language_bindings = [
            item for item in bindings or []
            if isinstance(item, dict) and item.get("role") == "repaired_language"
        ]
        if len(language_bindings) != 1:
            errors.append("$.input_bindings: L000 repaired visual plan requires exactly one repaired_language binding")
        else:
            raw_path = language_bindings[0].get("path")
            if isinstance(raw_path, str) and Path(raw_path).is_file():
                language = load(Path(raw_path))
                portrait = {
                    "Taro": "portrait-taro", "Emma": "portrait-emma", "Bob": "portrait-bob",
                    "Errol": "portrait-errol", "Ninereeds": "portrait-ninereeds",
                }
                scene = {
                    "Taro": "scene-taro-ninereeds", "Emma": "scene-emma-ninereeds",
                    "Bob": "scene-bob-ninereeds", "Errol": "scene-errol-ninereeds",
                }

                def require_exercise_binding(exercise: Any, component_id: str) -> None:
                    if not isinstance(exercise, dict):
                        return
                    teacher = exercise.get("teacher_speaker")
                    if teacher not in scene:
                        return
                    required = {scene[teacher], portrait[teacher], portrait["Ninereeds"]}
                    prompt = exercise.get("target_prompt", "")
                    if isinstance(prompt, str):
                        for name in re.findall(r"\b(?:Taro|Emma|Bob|Errol|Ninereeds)\b", prompt):
                            required.add(portrait[name])
                    actual = usage_assets.get(component_id)
                    if actual is None:
                        errors.append(f"$.usage_map: missing exact exercise component {component_id}")
                    elif not required <= actual:
                        errors.append(f"$.usage_map[{component_id}]: missing required relational operands {sorted(required - actual)}")

                controlled = language.get("controlled_practice", {})
                if isinstance(controlled, dict):
                    for pool in controlled.values():
                        if not isinstance(pool, list):
                            continue
                        for exercise in pool:
                            if isinstance(exercise, dict) and isinstance(exercise.get("id"), str):
                                require_exercise_binding(exercise, exercise["id"])
                                require_exercise_binding(exercise, f"mixed-{exercise['id']}")
                interventions = language.get("interventions", {})
                reserve_by_gate = interventions.get("train_more", {}).get("reserve_by_gate", {}) if isinstance(interventions, dict) else {}
                if isinstance(reserve_by_gate, dict):
                    for pool in reserve_by_gate.values():
                        if isinstance(pool, list):
                            for exercise in pool:
                                if isinstance(exercise, dict) and isinstance(exercise.get("id"), str):
                                    require_exercise_binding(exercise, exercise["id"])
                for exercise in language.get("recap", []):
                    if isinstance(exercise, dict) and isinstance(exercise.get("id"), str):
                        require_exercise_binding(exercise, exercise["id"])

                expected_self_assets = {
                    "scene-taro-ninereeds", "scene-emma-bob", "scene-taro-errol",
                    "portrait-taro", "portrait-ninereeds", "portrait-emma",
                    "portrait-bob", "portrait-errol",
                }
                actual_self_assets = usage_assets.get("presentation-self-identification")
                if actual_self_assets is not None and actual_self_assets != expected_self_assets:
                    errors.append("$.usage_map[presentation-self-identification]: must bind exactly the three modeled pairs and five participant representations")

    string_array(value.get("pixel_acceptance_rules"), "$.pixel_acceptance_rules", errors)
    string_array(value.get("alarm_conditions"), "$.alarm_conditions", errors)
    validate_bindings(value.get("input_bindings"), errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("thesis", "kernel", "pages", "comprehension", "language", "visual_plan", "story"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        value = load(args.input)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    validators = {
        "thesis": validate_thesis,
        "kernel": validate_kernel,
        "pages": validate_pages,
        "comprehension": validate_comprehension,
        "language": validate_language,
        "visual_plan": validate_visual_plan,
        "story": validate_story,
    }
    errors = validators[args.stage](value)
    if errors:
        print("validation failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"valid {args.stage} stage: {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
