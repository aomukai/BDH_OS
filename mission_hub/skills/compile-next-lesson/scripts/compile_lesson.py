#!/usr/bin/env python3
"""Validate and freeze a Ninereeds lesson contract without dispatching work."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lesson_assembly import canonical_bytes as selection_canonical_bytes
from lesson_assembly import select_next, select_next_preparation


COMPILER_VERSION = "ninereeds_lesson_compiler_v3"
REPO_ROOT = Path(__file__).resolve().parents[4]
LESSON_ID = re.compile(r"^lesson-[a-z0-9][a-z0-9-]*-v[0-9]+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PHASE_KEYS = ("affirmative", "negative", "W_question", "OR_question")


def controlled_phase_keys(lesson: dict[str, Any]) -> tuple[str, ...]:
    assembly = lesson.get("assembly")
    if (
        lesson.get("schema_version") == "ninereeds_lesson_contract_v3"
        and isinstance(assembly, dict)
        and assembly.get("conducted_entry_id") == "L000"
    ):
        return PHASE_KEYS + ("reciprocity",)
    return PHASE_KEYS
REHEARSAL_READY = {
    "full_rehearsal_passed",
    "pattern_rehearsal_passed",
    "qualified_no_rehearsal_due",
    "regression_spot_check_passed",
}


class DuplicateKeyError(ValueError):
    pass


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    except (OSError, json.JSONDecodeError, DuplicateKeyError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("lesson input must be one JSON object")
    return value


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


def resolve_repo_path(raw: str) -> Path:
    candidate = Path(raw)
    path = candidate if candidate.is_absolute() else REPO_ROOT / candidate
    path = path.resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {raw}") from exc
    return path


def require_keys(value: dict[str, Any], keys: set[str], where: str, errors: list[str]) -> None:
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    errors.extend(f"{where}: missing {key}" for key in missing)
    errors.extend(f"{where}: unknown key {key}" for key in extra)


def require_string(value: Any, where: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where}: must be a non-empty string")


def walk_strings(value: Any, where: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, str):
        found.append((where, value))
    elif isinstance(value, dict):
        for key, child in value.items():
            found.extend(walk_strings(child, f"{where}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(walk_strings(child, f"{where}[{index}]"))
    return found


def validate_exercise(
    exercise: Any,
    where: str,
    errors: list[str],
    *,
    require_response_contract: bool = False,
) -> set[str]:
    if not isinstance(exercise, dict):
        errors.append(f"{where}: must be an object")
        return set()
    keys = {"id", "teacher_text", "expected_answers", "invariants", "asset_ids", "target_language_required"}
    if require_response_contract:
        keys |= {"response_mode", "speaker_identity", "evidence_use"}
    optional_keys = {
        "teacher_turns", "teacher_speaker", "speaker_asset_ids",
        "nonverbal_control", "evidence_turn_ids", "scoring_role",
    } if require_response_contract else set()
    missing = sorted(keys - set(exercise))
    extra = sorted(set(exercise) - keys - optional_keys)
    errors.extend(f"{where}: missing {key}" for key in missing)
    errors.extend(f"{where}: unknown key {key}" for key in extra)
    for key in ("id", "teacher_text"):
        require_string(exercise.get(key), f"{where}.{key}", errors)
    if isinstance(exercise.get("teacher_text"), str) and exercise["teacher_text"] != exercise["teacher_text"].strip():
        errors.append(f"{where}.teacher_text: must not contain leading or trailing whitespace")
    for key in ("expected_answers", "invariants", "asset_ids"):
        items = exercise.get(key)
        if not isinstance(items, list):
            errors.append(f"{where}.{key}: must be an array")
        elif (
            key != "asset_ids"
            and not items
            and not (
                key == "expected_answers"
                and require_response_contract
                and exercise.get("response_mode") == "model_only"
            )
        ):
            errors.append(f"{where}.{key}: must not be empty")
        elif any(not isinstance(item, str) or not item for item in items):
            errors.append(f"{where}.{key}: items must be non-empty strings")
    if not isinstance(exercise.get("target_language_required"), bool):
        errors.append(f"{where}.target_language_required: must be boolean")
    scoring_role = exercise.get("scoring_role")
    if scoring_role is not None and scoring_role not in {"unscored_interface_check", "unscored_parallel_retest"}:
        errors.append(f"{where}.scoring_role: invalid")
    if require_response_contract:
        response_mode = exercise.get("response_mode")
        evidence_use = exercise.get("evidence_use")
        speaker_identity = exercise.get("speaker_identity")
        if response_mode not in {
            "model_only", "learner_self", "quoted_character_completion", "nonverbal_selection",
            "lexical_selection", "bare_label", "story_sequence_selection",
        }:
            errors.append(f"{where}.response_mode: invalid response mode")
        if evidence_use not in {
            "presentation_only", "learner_identity_and_language", "quoted_dialogue_only",
            "concept_only_nonverbal", "learner_label_and_concept",
        }:
            errors.append(f"{where}.evidence_use: invalid evidence use")
        if response_mode == "model_only":
            if speaker_identity is not None:
                errors.append(f"{where}.speaker_identity: model_only must be null")
            if evidence_use != "presentation_only":
                errors.append(f"{where}.evidence_use: model_only requires presentation_only")
            if exercise.get("target_language_required") is not False:
                errors.append(f"{where}.target_language_required: model_only must be false")
            if exercise.get("expected_answers") != []:
                errors.append(f"{where}.expected_answers: model_only must use an empty array")
            if exercise.get("teacher_text") != "MODEL_TURNS":
                errors.append(f"{where}.teacher_text: model_only must equal MODEL_TURNS; learner-facing language lives in teacher_turns")
            turns = exercise.get("teacher_turns")
            if not isinstance(turns, list) or not turns:
                errors.append(f"{where}.teacher_turns: model_only requires a non-empty turn array")
            else:
                for turn_index, turn in enumerate(turns):
                    turn_where = f"{where}.teacher_turns[{turn_index}]"
                    if not isinstance(turn, dict):
                        errors.append(f"{turn_where}: must be an object")
                        continue
                    require_keys(turn, {"speaker", "text", "asset_ids"}, turn_where, errors)
                    require_string(turn.get("speaker"), f"{turn_where}.speaker", errors)
                    require_string(turn.get("text"), f"{turn_where}.text", errors)
                    turn_assets = turn.get("asset_ids")
                    if not isinstance(turn_assets, list) or not turn_assets or any(not isinstance(item, str) or not item for item in turn_assets):
                        errors.append(f"{turn_where}.asset_ids: must be a non-empty string array")
                    else:
                        if not set(turn_assets) <= set(exercise.get("asset_ids", [])):
                            errors.append(f"{turn_where}.asset_ids: must be a subset of exercise asset_ids")
                        if any(item.startswith(("scene-", "portrait-")) for item in exercise.get("asset_ids", []) if isinstance(item, str)):
                            scene_assets = [item for item in turn_assets if item.startswith("scene-")]
                            portrait_assets = [item for item in turn_assets if item.startswith("portrait-")]
                            if len(scene_assets) != 1:
                                errors.append(f"{turn_where}.asset_ids: each modeled turn requires exactly one full relational scene")
                            speaker = turn.get("speaker")
                            if isinstance(speaker, str) and speaker not in {"caption", "model"}:
                                expected_portrait = f"portrait-{speaker.lower()}"
                                if portrait_assets != [expected_portrait]:
                                    errors.append(f"{turn_where}.asset_ids: must contain only the current speaker portrait {expected_portrait}")
                            elif portrait_assets:
                                errors.append(f"{turn_where}.asset_ids: caption/model turn must not show a speaker portrait")
        elif response_mode == "learner_self":
            if speaker_identity != "Ninereeds":
                errors.append(f"{where}.speaker_identity: learner_self must equal Ninereeds")
            if evidence_use != "learner_identity_and_language":
                errors.append(f"{where}.evidence_use: learner_self requires learner_identity_and_language")
            require_string(exercise.get("teacher_speaker"), f"{where}.teacher_speaker", errors)
            speaker_assets = exercise.get("speaker_asset_ids")
            if not isinstance(speaker_assets, list) or not speaker_assets or any(not isinstance(item, str) or not item for item in speaker_assets):
                errors.append(f"{where}.speaker_asset_ids: learner_self requires a non-empty speaker-binding asset array")
            elif not set(speaker_assets) <= set(exercise.get("asset_ids", [])):
                errors.append(f"{where}.speaker_asset_ids: must be a subset of exercise asset_ids")
            elif isinstance(exercise.get("teacher_speaker"), str) and any(
                item.startswith(("scene-", "portrait-"))
                for item in exercise.get("asset_ids", [])
                if isinstance(item, str)
            ):
                expected_portrait = f"portrait-{exercise['teacher_speaker'].lower()}"
                if speaker_assets != [expected_portrait]:
                    errors.append(f"{where}.speaker_asset_ids: must contain only the current teacher portrait {expected_portrait}")
            if (
                isinstance(exercise.get("asset_ids"), list)
                and any(item.startswith(("scene-", "portrait-")) for item in exercise["asset_ids"] if isinstance(item, str))
                and not any(item.startswith("scene-") for item in exercise["asset_ids"] if isinstance(item, str))
            ):
                errors.append(f"{where}.asset_ids: learner exchange requires a full relational scene")
        elif response_mode == "quoted_character_completion":
            if not isinstance(speaker_identity, str) or not speaker_identity or speaker_identity == "Ninereeds":
                errors.append(f"{where}.speaker_identity: quoted completion requires an explicit non-Ninereeds speaker")
            if evidence_use != "quoted_dialogue_only":
                errors.append(f"{where}.evidence_use: quoted completion can only supply quoted_dialogue_only evidence")
        elif response_mode == "nonverbal_selection":
            if speaker_identity is not None:
                errors.append(f"{where}.speaker_identity: nonverbal selection must be null")
            if evidence_use != "concept_only_nonverbal":
                errors.append(f"{where}.evidence_use: nonverbal selection can only supply concept_only_nonverbal evidence")
            evidence_turn_ids = exercise.get("evidence_turn_ids")
            if where.startswith("$.picture_book.comprehension") and (
                not isinstance(evidence_turn_ids, list)
                or not evidence_turn_ids
                or any(not isinstance(item, str) or not item for item in evidence_turn_ids)
            ):
                errors.append(f"{where}.evidence_turn_ids: nonverbal story attribution requires a non-empty string array")
            control = exercise.get("nonverbal_control")
            if not isinstance(control, dict):
                errors.append(f"{where}.nonverbal_control: nonverbal selection requires an explicit control")
            else:
                control_keys = {"machine_action", "spoken_text", "semantic_task", "demonstrations", "options"}
                if control.get("machine_action") == "SHOW_SCENE_SELECT_PHONE_IDENTITY":
                    control_keys |= {"scored_context_asset_ids", "scored_action_sequence"}
                if control.get("machine_action") == "REPLAY_TURN_SELECT_SPEAKER":
                    control_keys |= {"scored_turn_ids", "scored_action_sequence"}
                require_keys(control, control_keys, f"{where}.nonverbal_control", errors)
                allowed_machine_tasks = {
                    "REPLAY_TURN_SELECT_SPEAKER": "select_portrait_of_speaker_of_replayed_turn",
                    "SHOW_SCENE_SELECT_PHONE_IDENTITY": "select_after_scene_that_preserves_phone_identity_across_shown_handoff",
                    "SHOW_PAGE_SELECT_NEXT_SCENE": "select_scene_of_next_story_page",
                    "SHOW_PAGE_SELECT_PREVIOUS_SCENE": "select_scene_of_previous_story_page",
                }
                if control.get("machine_action") not in allowed_machine_tasks:
                    errors.append(f"{where}.nonverbal_control.machine_action: invalid closed story-selection action")
                if control.get("spoken_text") is not None:
                    errors.append(f"{where}.nonverbal_control.spoken_text: must be null")
                if control.get("semantic_task") != allowed_machine_tasks.get(control.get("machine_action")):
                    errors.append(f"{where}.nonverbal_control.semantic_task: must match the exact closed machine action")
                if control.get("machine_action") == "SHOW_SCENE_SELECT_PHONE_IDENTITY":
                    expected_contexts = ["scene-taro-ninereeds", "scene-taro-hands-phone-to-emma"]
                    if control.get("scored_context_asset_ids") != expected_contexts:
                        errors.append(
                            f"{where}.nonverbal_control.scored_context_asset_ids: "
                            "must show the frozen before and during hand-off sequence"
                        )
                    expected_actions = [
                        "SHOW_BEFORE_CONTEXT",
                        "SHOW_DURING_CONTEXT",
                        "SHOW_AFTER_OPTIONS",
                        "RECORD_SELECTION",
                    ]
                    if control.get("scored_action_sequence") != expected_actions:
                        errors.append(
                            f"{where}.nonverbal_control.scored_action_sequence: "
                            "must show before and during contexts before the two after-scene options and recording"
                        )
                if control.get("machine_action") == "REPLAY_TURN_SELECT_SPEAKER":
                    if control.get("scored_turn_ids") != exercise.get("evidence_turn_ids"):
                        errors.append(
                            f"{where}.nonverbal_control.scored_turn_ids: "
                            "must equal the frozen evidence turn IDs"
                        )
                    if control.get("scored_action_sequence") != [
                        "REPLAY_BOUND_TURN", "SHOW_OPTIONS", "RECORD_SELECTION"
                    ]:
                        errors.append(
                            f"{where}.nonverbal_control.scored_action_sequence: "
                            "must replay the bound turn, show both options, and record the selection"
                        )
                demonstrations = control.get("demonstrations")
                if not isinstance(demonstrations, list) or len(demonstrations) < 2:
                    errors.append(f"{where}.nonverbal_control.demonstrations: must contain at least two worked control examples")
                else:
                    for demo_index, demo in enumerate(demonstrations):
                        demo_where = f"{where}.nonverbal_control.demonstrations[{demo_index}]"
                        if not isinstance(demo, dict):
                            errors.append(f"{demo_where}: must be an object")
                            continue
                        demo_keys = {"turn_id", "replay_text", "correct_option_asset_id", "feedback_action"}
                        if where.startswith("$.picture_book.comprehension"):
                            demo_keys |= {"context_asset_id", "shown_option_asset_ids", "action_sequence"}
                        require_keys(demo, demo_keys, demo_where, errors)
                        for key in ("turn_id", "replay_text", "correct_option_asset_id"):
                            require_string(demo.get(key), f"{demo_where}.{key}", errors)
                        if demo.get("feedback_action") != "SHOW_CORRECT_OPTION":
                            errors.append(f"{demo_where}.feedback_action: must equal SHOW_CORRECT_OPTION")
                        if demo.get("correct_option_asset_id") not in exercise.get("asset_ids", []):
                            errors.append(f"{demo_where}.correct_option_asset_id: must be declared in exercise asset_ids")
                        if where.startswith("$.picture_book.comprehension"):
                            if demo.get("context_asset_id") not in exercise.get("asset_ids", []):
                                errors.append(f"{demo_where}.context_asset_id: must be declared in exercise asset_ids")
                            option_asset_ids = [
                                option.get("asset_id") for option in control.get("options", [])
                                if isinstance(option, dict)
                            ] if isinstance(control.get("options"), list) else []
                            shown_option_asset_ids = demo.get("shown_option_asset_ids")
                            if control.get("machine_action") == "SHOW_SCENE_SELECT_PHONE_IDENTITY":
                                if (
                                    not isinstance(shown_option_asset_ids, list)
                                    or len(shown_option_asset_ids) != 2
                                    or demo.get("correct_option_asset_id") not in shown_option_asset_ids
                                    or any(asset_id not in exercise.get("asset_ids", []) for asset_id in shown_option_asset_ids)
                                ):
                                    errors.append(f"{demo_where}.shown_option_asset_ids: must show two declared demonstration scenes including the correct scene")
                            elif shown_option_asset_ids != option_asset_ids:
                                errors.append(f"{demo_where}.shown_option_asset_ids: must show the complete frozen option pair")
                            expected_demo_actions = (
                                ["SHOW_CONTEXT", "SHOW_OPTIONS", "SHOW_CORRECT_OPTION"]
                                if control.get("machine_action") == "SHOW_SCENE_SELECT_PHONE_IDENTITY"
                                else ["REPLAY_TURN", "SHOW_OPTIONS", "SHOW_CORRECT_OPTION"]
                            )
                            if demo.get("action_sequence") != expected_demo_actions:
                                errors.append(f"{demo_where}.action_sequence: must expose context/replay, both options, and the correct-option action")
                options = control.get("options")
                option_ids: set[str] = set()
                if not isinstance(options, list) or len(options) < 2:
                    errors.append(f"{where}.nonverbal_control.options: must contain at least two options")
                else:
                    for option_index, option in enumerate(options):
                        option_where = f"{where}.nonverbal_control.options[{option_index}]"
                        if not isinstance(option, dict):
                            errors.append(f"{option_where}: must be an object")
                            continue
                        require_keys(option, {"id", "asset_id", "visual_entity"}, option_where, errors)
                        for key in ("id", "asset_id", "visual_entity"):
                            require_string(option.get(key), f"{option_where}.{key}", errors)
                        if isinstance(option.get("id"), str):
                            if option["id"] in option_ids:
                                errors.append(f"{option_where}.id: duplicate")
                            option_ids.add(option["id"])
                        if option.get("asset_id") not in exercise.get("asset_ids", []):
                            errors.append(f"{option_where}.asset_id: must be declared in exercise asset_ids")
                        if (
                            control.get("machine_action") in {
                                "SHOW_PAGE_SELECT_NEXT_SCENE", "SHOW_PAGE_SELECT_PREVIOUS_SCENE",
                                "SHOW_SCENE_SELECT_PHONE_IDENTITY",
                            }
                            and option.get("visual_entity") != option.get("asset_id")
                        ):
                            errors.append(f"{option_where}.visual_entity: scene-selection options must preserve the exact scene asset identity")
                    if control.get("machine_action") in {"SHOW_PAGE_SELECT_NEXT_SCENE", "SHOW_PAGE_SELECT_PREVIOUS_SCENE", "SHOW_SCENE_SELECT_PHONE_IDENTITY"}:
                        option_assets = {
                            option.get("asset_id") for option in options if isinstance(option, dict)
                        }
                        expected_scene_options = (
                            {"scene-emma-ninereeds", "scene-emma-errol"}
                            if control.get("machine_action") == "SHOW_SCENE_SELECT_PHONE_IDENTITY"
                            else {"scene-taro-ninereeds", "scene-emma-ninereeds"}
                        )
                        if option_assets != expected_scene_options:
                            errors.append(f"{where}.nonverbal_control.options: must contain exactly the two frozen story scenes")
                answers = exercise.get("expected_answers")
                if isinstance(answers, list) and not set(answers) <= option_ids:
                    errors.append(f"{where}.expected_answers: must cite defined nonverbal option IDs")
        elif response_mode == "lexical_selection":
            if speaker_identity is not None:
                errors.append(f"{where}.speaker_identity: lexical_selection must be null")
            if evidence_use != "concept_only_nonverbal":
                errors.append(f"{where}.evidence_use: lexical_selection requires concept_only_nonverbal")
            if exercise.get("teacher_text") != "MACHINE_CONTROL":
                errors.append(f"{where}.teacher_text: silent lexical selection must equal MACHINE_CONTROL")
            if exercise.get("target_language_required") is not False:
                errors.append(f"{where}.target_language_required: lexical selection must be false")
            control = exercise.get("nonverbal_control")
            licensed = {
                "SHOW_LABEL_SELECT_MATCHING_IMAGE": "select_image_matching_displayed_bare_label",
                "SHOW_MISMATCH_SELECT_REPLACEMENT": "select_bare_label_replacing_visible_mismatch",
                "SHOW_IMAGE_SELECT_ONE_OF_TWO_LABELS": "select_bare_label_matching_displayed_image",
                "SHOW_STORY_PAGE_SELECT_ACTIVE_OBJECT_LABEL": "select_label_for_object_moved_in_story_scene",
                "CHECK_UNDERSTANDING": "confirm_machine_control_before_scored_use",
            }
            option_ids: set[str] = set()
            if not isinstance(control, dict):
                errors.append(f"{where}.nonverbal_control: lexical selection requires an explicit frozen control")
            else:
                action = control.get("machine_action")
                control_keys = {"machine_action", "spoken_text", "semantic_task", "demonstrations", "options"}
                if action == "SHOW_MISMATCH_SELECT_REPLACEMENT":
                    control_keys.add("displayed_mismatch_label")
                if action == "SHOW_STORY_PAGE_SELECT_ACTIVE_OBJECT_LABEL":
                    control_keys.add("anchor_asset_id")
                if scoring_role == "unscored_interface_check":
                    control_keys.add("action_sequence")
                require_keys(control, control_keys, f"{where}.nonverbal_control", errors)
                if action not in licensed:
                    errors.append(f"{where}.nonverbal_control.machine_action: invalid lexical-selection action")
                if scoring_role == "unscored_interface_check" and action not in licensed:
                    errors.append(f"{where}.nonverbal_control.machine_action: unscored interface checks must use the exact licensed interface")
                if control.get("spoken_text") is not None:
                    errors.append(f"{where}.nonverbal_control.spoken_text: must be null")
                if control.get("semantic_task") != licensed.get(action):
                    errors.append(f"{where}.nonverbal_control.semantic_task: must match machine_action")
                if control.get("demonstrations") != []:
                    errors.append(f"{where}.nonverbal_control.demonstrations: local presentation supplies the worked model, so scored items must use []")
                if action == "SHOW_MISMATCH_SELECT_REPLACEMENT":
                    mismatch = control.get("displayed_mismatch_label")
                    require_string(mismatch, f"{where}.nonverbal_control.displayed_mismatch_label", errors)
                    if mismatch in exercise.get("expected_answers", []):
                        errors.append(f"{where}.nonverbal_control.displayed_mismatch_label: must differ from the correct replacement")
                if action == "SHOW_STORY_PAGE_SELECT_ACTIVE_OBJECT_LABEL" and control.get("anchor_asset_id") not in exercise.get("asset_ids", []):
                    errors.append(f"{where}.nonverbal_control.anchor_asset_id: must cite the sole story-page asset")
                options = control.get("options")
                expected_option_count = 2
                story_label_options_valid = (
                    action == "SHOW_STORY_PAGE_SELECT_ACTIVE_OBJECT_LABEL"
                    and isinstance(options, list)
                    and len(options) >= 4
                    and len(options) % 4 == 0
                )
                if not isinstance(options, list) or (
                    action == "SHOW_STORY_PAGE_SELECT_ACTIVE_OBJECT_LABEL" and not story_label_options_valid
                ) or (
                    action != "SHOW_STORY_PAGE_SELECT_ACTIVE_OBJECT_LABEL" and len(options) != expected_option_count
                ):
                    requirement = "exactly 4 closed options or another complete four-label multiple" if action == "SHOW_STORY_PAGE_SELECT_ACTIVE_OBJECT_LABEL" else f"exactly {expected_option_count} closed options"
                    errors.append(f"{where}.nonverbal_control.options: must contain {requirement}")
                else:
                    for option_index, option in enumerate(options):
                        option_where = f"{where}.nonverbal_control.options[{option_index}]"
                        if not isinstance(option, dict):
                            errors.append(f"{option_where}: must be an object")
                            continue
                        require_keys(option, {"id", "display_kind", "display_value", "asset_id"}, option_where, errors)
                        option_id = option.get("id")
                        require_string(option_id, f"{option_where}.id", errors)
                        if isinstance(option_id, str):
                            if option_id in option_ids:
                                errors.append(f"{option_where}.id: duplicate")
                            option_ids.add(option_id)
                        kind = option.get("display_kind")
                        if kind == "image":
                            if option.get("display_value") is not None:
                                errors.append(f"{option_where}.display_value: image option must use null")
                            if option.get("asset_id") not in exercise.get("asset_ids", []):
                                errors.append(f"{option_where}.asset_id: image option must cite an exercise asset")
                        elif kind == "label":
                            require_string(option.get("display_value"), f"{option_where}.display_value", errors)
                            if option.get("asset_id") is not None:
                                errors.append(f"{option_where}.asset_id: label option must use null")
                        else:
                            errors.append(f"{option_where}.display_kind: must be image or label")
            answers = exercise.get("expected_answers")
            if isinstance(answers, list) and (len(answers) != 1 or not set(answers) <= option_ids):
                errors.append(f"{where}.expected_answers: must name exactly one closed option")
        elif response_mode == "bare_label":
            if speaker_identity != "Ninereeds":
                errors.append(f"{where}.speaker_identity: bare_label must equal Ninereeds")
            if evidence_use != "learner_label_and_concept":
                errors.append(f"{where}.evidence_use: bare_label requires learner_label_and_concept")
            if exercise.get("teacher_text") != "MACHINE_CONTROL":
                errors.append(f"{where}.teacher_text: silent bare-label retrieval must equal MACHINE_CONTROL")
            if exercise.get("target_language_required") is not True:
                errors.append(f"{where}.target_language_required: bare_label must be true")
            control = exercise.get("nonverbal_control")
            if not isinstance(control, dict):
                errors.append(f"{where}.nonverbal_control: bare_label requires an explicit frozen control")
            else:
                require_keys(control, {"machine_action", "spoken_text", "semantic_task", "demonstrations", "options"}, f"{where}.nonverbal_control", errors)
                if control.get("machine_action") != "SHOW_IMAGE_RECORD_BARE_LABEL":
                    errors.append(f"{where}.nonverbal_control.machine_action: must equal SHOW_IMAGE_RECORD_BARE_LABEL")
                if control.get("spoken_text") is not None:
                    errors.append(f"{where}.nonverbal_control.spoken_text: must be null")
                if control.get("semantic_task") != "record_bare_label_for_shown_image":
                    errors.append(f"{where}.nonverbal_control.semantic_task: must equal record_bare_label_for_shown_image")
                if control.get("demonstrations") != [] or control.get("options") != []:
                    errors.append(f"{where}.nonverbal_control: open retrieval uses no demonstrations or options in the scored item")
        elif response_mode == "story_sequence_selection":
            if speaker_identity is not None:
                errors.append(f"{where}.speaker_identity: story_sequence_selection must be null")
            if evidence_use != "concept_only_nonverbal":
                errors.append(f"{where}.evidence_use: story_sequence_selection requires concept_only_nonverbal")
            if exercise.get("teacher_text") != "MACHINE_CONTROL":
                errors.append(f"{where}.teacher_text: silent story sequence selection must equal MACHINE_CONTROL")
            if exercise.get("target_language_required") is not False:
                errors.append(f"{where}.target_language_required: story sequence selection must be false")
            control = exercise.get("nonverbal_control")
            licensed = {
                "SHOW_PAGE_SELECT_NEXT_SCENE": "select_scene_of_next_story_page",
                "SHOW_PAGE_SELECT_PREVIOUS_SCENE": "select_scene_of_previous_story_page",
            }
            option_ids: set[str] = set()
            if not isinstance(control, dict):
                errors.append(f"{where}.nonverbal_control: story sequence selection requires an explicit control")
            else:
                require_keys(control, {"machine_action", "spoken_text", "semantic_task", "anchor_asset_id", "demonstrations", "options"}, f"{where}.nonverbal_control", errors)
                action = control.get("machine_action")
                if action not in licensed:
                    errors.append(f"{where}.nonverbal_control.machine_action: invalid story-sequence action")
                if control.get("spoken_text") is not None:
                    errors.append(f"{where}.nonverbal_control.spoken_text: must be null")
                if control.get("semantic_task") != licensed.get(action):
                    errors.append(f"{where}.nonverbal_control.semantic_task: must match machine_action")
                if control.get("anchor_asset_id") not in exercise.get("asset_ids", []):
                    errors.append(f"{where}.nonverbal_control.anchor_asset_id: must cite an exercise asset")
                demos = control.get("demonstrations")
                if not isinstance(demos, list) or (demos and len(demos) < 2):
                    errors.append(f"{where}.nonverbal_control.demonstrations: must be empty when a separate interface tutorial is bound, or contain at least two worked examples")
                elif demos:
                    for demo_index, demo in enumerate(demos):
                        demo_where = f"{where}.nonverbal_control.demonstrations[{demo_index}]"
                        if not isinstance(demo, dict):
                            errors.append(f"{demo_where}: must be an object")
                            continue
                        require_keys(demo, {"anchor_asset_id", "option_asset_ids", "expected_asset_id", "feedback_action"}, demo_where, errors)
                        if demo.get("anchor_asset_id") not in exercise.get("asset_ids", []):
                            errors.append(f"{demo_where}.anchor_asset_id: must cite an exercise asset")
                        demo_options = demo.get("option_asset_ids")
                        if not isinstance(demo_options, list) or len(demo_options) != 2 or len(set(demo_options)) != 2 or any(v not in exercise.get("asset_ids", []) for v in demo_options):
                            errors.append(f"{demo_where}.option_asset_ids: must contain two distinct exercise assets")
                        if demo.get("expected_asset_id") not in (demo_options if isinstance(demo_options, list) else []):
                            errors.append(f"{demo_where}.expected_asset_id: must name one demonstration option")
                        if demo.get("feedback_action") != "SHOW_CORRECT_OPTION":
                            errors.append(f"{demo_where}.feedback_action: must equal SHOW_CORRECT_OPTION")
                options = control.get("options")
                if not isinstance(options, list) or len(options) != 2:
                    errors.append(f"{where}.nonverbal_control.options: must contain exactly two scored scene options")
                else:
                    for option_index, option in enumerate(options):
                        option_where = f"{where}.nonverbal_control.options[{option_index}]"
                        if not isinstance(option, dict):
                            errors.append(f"{option_where}: must be an object")
                            continue
                        require_keys(option, {"id", "asset_id", "visual_entity"}, option_where, errors)
                        option_id = option.get("id")
                        require_string(option_id, f"{option_where}.id", errors)
                        if isinstance(option_id, str):
                            if option_id in option_ids:
                                errors.append(f"{option_where}.id: duplicate")
                            option_ids.add(option_id)
                        if option.get("asset_id") not in exercise.get("asset_ids", []):
                            errors.append(f"{option_where}.asset_id: must cite an exercise asset")
                        if option.get("visual_entity") != option.get("asset_id"):
                            errors.append(f"{option_where}.visual_entity: must preserve exact scene asset identity")
            answers = exercise.get("expected_answers")
            if isinstance(answers, list) and (len(answers) != 1 or not set(answers) <= option_ids):
                errors.append(f"{where}.expected_answers: must name exactly one scored option")
        elif exercise.get("nonverbal_control") is not None:
            errors.append(f"{where}.nonverbal_control: only nonverbal_selection may define a control")
    return set(exercise.get("asset_ids", [])) if isinstance(exercise.get("asset_ids"), list) else set()


def validate_bound_file(raw_path: Any, expected: Any, where: str, stage: str, errors: list[str]) -> None:
    if stage != "freeze":
        return
    require_string(raw_path, f"{where}.path", errors)
    if not isinstance(expected, str) or SHA256.fullmatch(expected) is None:
        errors.append(f"{where}.sha256: must be lowercase SHA-256")
        return
    if not isinstance(raw_path, str) or not raw_path:
        return
    try:
        path = resolve_repo_path(raw_path)
        if not path.is_file():
            errors.append(f"{where}.path: file does not exist")
        elif digest_path(path) != expected:
            errors.append(f"{where}.sha256: does not match file")
    except ValueError as exc:
        errors.append(f"{where}.path: {exc}")


def validate_v3_assembly(lesson: dict[str, Any], stage: str, declared_assets: dict[str, dict[str, Any]], errors: list[str]) -> None:
    assembly = lesson.get("assembly")
    if not isinstance(assembly, dict):
        errors.append("$.assembly: must be an object")
    else:
        keys = {"mode", "selection_packet_path", "selection_packet_sha256", "conducted_entry_id", "conducted_sequence_number"}
        require_keys(assembly, keys, "$.assembly", errors)
        if assembly.get("mode") != "handhold":
            errors.append("$.assembly.mode: must equal handhold until autonomous commissioning")
        require_string(assembly.get("conducted_entry_id"), "$.assembly.conducted_entry_id", errors)
        number = assembly.get("conducted_sequence_number")
        if not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= 666:
            errors.append("$.assembly.conducted_sequence_number: must be in 1..666")
        validate_bound_file(assembly.get("selection_packet_path"), assembly.get("selection_packet_sha256"), "$.assembly.selection_packet", stage, errors)
        if stage == "freeze" and isinstance(assembly.get("selection_packet_path"), str):
            try:
                packet = load_json(resolve_repo_path(assembly["selection_packet_path"]))
            except ValueError as exc:
                errors.append(f"$.assembly.selection_packet: {exc}")
            else:
                sequence = packet.get("sequence")
                entry = packet.get("selected_entry")
                if packet.get("schema_version") != "ninereeds_lesson_selection_v1" or not isinstance(sequence, dict) or not isinstance(entry, dict):
                    errors.append("$.assembly.selection_packet: invalid selection packet contract")
                else:
                    if sequence.get("entry_id") != assembly.get("conducted_entry_id") or sequence.get("sequence_number") != assembly.get("conducted_sequence_number"):
                        errors.append("$.assembly: conducted entry does not match selection packet")
                    expected_topic = entry.get("topic") if sequence.get("entry_kind") == "acquisition" else entry.get("topic_point_recombination", {}).get("varied_topic")
                    expected_point = entry.get("point") if sequence.get("entry_kind") == "acquisition" else entry.get("topic_point_recombination", {}).get("retrieved_point")
                    scope_override = None
                    for binding in lesson.get("source_bindings", []):
                        if isinstance(binding, dict) and binding.get("role") == "material_scope":
                            try:
                                candidate = load_json(resolve_repo_path(binding.get("path")))
                            except (TypeError, ValueError):
                                candidate = None
                            if (
                                isinstance(candidate, dict)
                                and candidate.get("schema_version") == "ninereeds_material_scope_decision_v1"
                                and candidate.get("decision") == "accepted_by_human"
                                and candidate.get("lesson_id") == assembly.get("conducted_entry_id")
                                and candidate.get("curriculum_topic") == expected_topic
                                and candidate.get("curriculum_point") == expected_point
                            ):
                                scope_override = candidate
                            break
                    allowed_topic = expected_topic
                    allowed_point = expected_point
                    if scope_override is not None:
                        allowed_topic = scope_override.get("authoring_topic")
                        tested = scope_override.get("language_boundary", {}).get("tested_language")
                        if isinstance(tested, list) and tested and all(isinstance(item, str) and item for item in tested):
                            allowed_point = "Activate the labels " + ", ".join(tested)
                    if lesson.get("topic") != allowed_topic:
                        errors.append("$.topic: does not match selected conducted entry or accepted material scope")
                    if isinstance(lesson.get("point"), dict) and lesson["point"].get("claim") != allowed_point:
                        errors.append("$.point.claim: does not match selected conducted entry or accepted material scope")
                    expected_prerequisites = (
                        entry.get("prerequisite_lessons", [])
                        if sequence.get("entry_kind") == "acquisition"
                        else [*entry.get("prerequisite_acquisition_lessons", []), *entry.get("prerequisite_rehearsal_lessons", [])]
                    )
                    actual_prerequisites = [item.get("id") for item in lesson.get("prerequisites", []) if isinstance(item, dict)]
                    if actual_prerequisites != [item for item in expected_prerequisites if item in actual_prerequisites]:
                        errors.append("$.prerequisites: must preserve curriculum order and may contain only evidenced learner prerequisites")
                    # Every new handhold entry is a complete dual-use visual lesson. The v6
                    # picture_book field remains provenance about the old planning decision;
                    # it no longer controls omission for acquisition or rehearsal.
                    if lesson.get("variant") != "picture_book":
                        errors.append("$.variant: every new handhold conducted entry must use picture_book")

    authoring = lesson.get("authoring")
    if not isinstance(authoring, dict):
        errors.append("$.authoring: must be an object")
    else:
        keys = {"actor", "prompt_path", "prompt_sha256", "receipt_path", "receipt_sha256"}
        require_keys(authoring, keys, "$.authoring", errors)
        if authoring.get("actor") != "luna":
            errors.append("$.authoring.actor: must equal luna")
        validate_bound_file(authoring.get("prompt_path"), authoring.get("prompt_sha256"), "$.authoring.prompt", stage, errors)
        validate_bound_file(authoring.get("receipt_path"), authoring.get("receipt_sha256"), "$.authoring.receipt", stage, errors)

    review = lesson.get("independent_review")
    if not isinstance(review, dict):
        errors.append("$.independent_review: must be an object")
    else:
        keys = {"required", "reviewer_role", "decision", "rubric_id", "receipt_path", "receipt_sha256", "findings"}
        require_keys(review, keys, "$.independent_review", errors)
        if review.get("required") is not True or review.get("reviewer_role") != "sol":
            errors.append("$.independent_review: handhold lessons require an independent Sol review")
        if review.get("decision") not in {"pending", "revise", "pass"}:
            errors.append("$.independent_review.decision: must be pending, revise, or pass")
        if stage == "freeze" and review.get("decision") != "pass":
            errors.append("$.independent_review.decision: must equal pass to freeze")
        require_string(review.get("rubric_id"), "$.independent_review.rubric_id", errors)
        if not isinstance(review.get("findings"), list) or any(not isinstance(v, str) or not v for v in review.get("findings", [])):
            errors.append("$.independent_review.findings: must be a string array")
        validate_bound_file(review.get("receipt_path"), review.get("receipt_sha256"), "$.independent_review.receipt", stage, errors)

    plan = lesson.get("visual_plan")
    if not isinstance(plan, dict):
        errors.append("$.visual_plan: must be an object")
        return
    require_keys(plan, {"lesson_asset_root", "flux_max_attempts", "operations"}, "$.visual_plan", errors)
    require_string(plan.get("lesson_asset_root"), "$.visual_plan.lesson_asset_root", errors)
    if isinstance(assembly, dict) and isinstance(assembly.get("conducted_entry_id"), str):
        expected_root = f"training_data/grounded_stories/assets/lessons/{assembly['conducted_entry_id']}"
        if plan.get("lesson_asset_root") != expected_root:
            errors.append(f"$.visual_plan.lesson_asset_root: must equal {expected_root}")
    max_attempts = plan.get("flux_max_attempts")
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or not 1 <= max_attempts <= 4:
        errors.append("$.visual_plan.flux_max_attempts: must be in 1..4")
    operations = plan.get("operations")
    if not isinstance(operations, list):
        errors.append("$.visual_plan.operations: must be an array")
        return
    operation_ids: set[str] = set()
    output_ids: set[str] = set()
    allowed_types = {"reuse", "literal_crop", "highlight", "flux_generate", "flux_edit", "imagegen_generate", "imagegen_fallback"}
    for index, operation in enumerate(operations):
        where = f"$.visual_plan.operations[{index}]"
        if not isinstance(operation, dict):
            errors.append(f"{where}: must be an object")
            continue
        keys = {
            "id", "type", "status", "teaching_claims", "parent_asset_id", "output_asset_id",
            "prompt", "attempts", "crop_xywh", "receipt_path", "receipt_sha256", "verification",
        }
        require_keys(operation, keys, where, errors)
        identifier = operation.get("id")
        require_string(identifier, f"{where}.id", errors)
        if isinstance(identifier, str):
            if identifier in operation_ids:
                errors.append(f"{where}.id: duplicate operation id")
            operation_ids.add(identifier)
        kind = operation.get("type")
        if kind not in allowed_types:
            errors.append(f"{where}.type: invalid visual operation")
        if operation.get("status") not in {"planned", "commissioned", "accepted", "rejected", "blocked"}:
            errors.append(f"{where}.status: invalid status")
        claims = operation.get("teaching_claims")
        if not isinstance(claims, list) or not claims or any(not isinstance(v, str) or not v for v in claims):
            errors.append(f"{where}.teaching_claims: must be a non-empty string array")
        output_id = operation.get("output_asset_id")
        require_string(output_id, f"{where}.output_asset_id", errors)
        if isinstance(output_id, str):
            if output_id in output_ids:
                errors.append(f"{where}.output_asset_id: duplicate output")
            output_ids.add(output_id)
            if output_id not in declared_assets:
                errors.append(f"{where}.output_asset_id: asset is not declared")
        attempts = operation.get("attempts")
        if not isinstance(attempts, list) or any(not isinstance(v, str) or not v for v in attempts):
            errors.append(f"{where}.attempts: must be a string array")
        if kind in {"flux_generate", "flux_edit"} and isinstance(attempts, list) and isinstance(max_attempts, int) and len(attempts) > max_attempts:
            errors.append(f"{where}.attempts: exceeds frozen Flux attempt budget")
        if kind in {"flux_generate", "flux_edit", "imagegen_generate", "imagegen_fallback"}:
            require_string(operation.get("prompt"), f"{where}.prompt", errors)
        elif operation.get("prompt") is not None:
            errors.append(f"{where}.prompt: deterministic operations cannot have a generative prompt")
        if kind in {"literal_crop", "highlight", "flux_edit"}:
            require_string(operation.get("parent_asset_id"), f"{where}.parent_asset_id", errors)
            if operation.get("parent_asset_id") not in declared_assets:
                errors.append(f"{where}.parent_asset_id: parent asset is not declared")
        if kind == "literal_crop":
            crop = operation.get("crop_xywh")
            if not isinstance(crop, list) or len(crop) != 4 or any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in crop) or (isinstance(crop, list) and len(crop) == 4 and (crop[2] < 1 or crop[3] < 1)):
                errors.append(f"{where}.crop_xywh: must be [x,y,width,height] with positive size")
        elif operation.get("crop_xywh") is not None:
            errors.append(f"{where}.crop_xywh: only literal_crop may define coordinates")
        if kind == "imagegen_fallback" and (not isinstance(attempts, list) or not attempts):
            errors.append(f"{where}.attempts: ImageGen fallback requires recorded prior attempts")
        if isinstance(output_id, str) and output_id in declared_assets:
            asset = declared_assets[output_id]
            expected_sources = {
                "reuse": {"registry", "external", "reuse"},
                "literal_crop": {"deterministic_crop"},
                "highlight": {"highlight"},
                "flux_generate": {"flux_generation"},
                "flux_edit": {"flux_edit"},
                "imagegen_generate": {"imagegen_generate", "openai_imagegen"},
                "imagegen_fallback": {"imagegen_fallback", "openai_imagegen"},
            }
            if kind in expected_sources and asset.get("source") not in expected_sources[kind]:
                errors.append(f"{where}.type: does not match output asset source")
            if kind == "literal_crop" and (
                asset.get("parent_asset_id") != operation.get("parent_asset_id")
                or asset.get("crop_xywh") != operation.get("crop_xywh")
            ):
                errors.append(f"{where}: crop parent/coordinates do not match output asset")
        if stage == "freeze":
            if operation.get("status") != "accepted":
                errors.append(f"{where}.status: must be accepted to freeze")
            validate_bound_file(operation.get("receipt_path"), operation.get("receipt_sha256"), f"{where}.receipt", stage, errors)
        verification = operation.get("verification")
        if not isinstance(verification, dict):
            errors.append(f"{where}.verification: must be an object")
            continue
        verification_keys = {"reviewer_role", "decision", "claim_results", "rejection_reasons", "receipt_path", "receipt_sha256"}
        require_keys(verification, verification_keys, f"{where}.verification", errors)
        if verification.get("reviewer_role") not in {"luna", "sol", "human"}:
            errors.append(f"{where}.verification.reviewer_role: invalid reviewer")
        if verification.get("decision") not in {"pending", "accepted", "rejected"}:
            errors.append(f"{where}.verification.decision: invalid decision")
        results = verification.get("claim_results")
        if not isinstance(results, list) or any(not isinstance(v, dict) or set(v) != {"claim", "passed", "evidence"} for v in results):
            errors.append(f"{where}.verification.claim_results: invalid claim-result array")
        elif stage == "freeze":
            result_claims = [v.get("claim") for v in results]
            if result_claims != claims or any(v.get("passed") is not True or not isinstance(v.get("evidence"), str) or not v["evidence"] for v in results):
                errors.append(f"{where}.verification.claim_results: every exact teaching claim must pass with evidence")
        reasons = verification.get("rejection_reasons")
        if not isinstance(reasons, list) or any(not isinstance(v, str) or not v for v in reasons):
            errors.append(f"{where}.verification.rejection_reasons: must be a string array")
        if stage == "freeze":
            if verification.get("decision") != "accepted" or reasons:
                errors.append(f"{where}.verification: must be accepted without rejection reasons to freeze")
            validate_bound_file(verification.get("receipt_path"), verification.get("receipt_sha256"), f"{where}.verification.receipt", stage, errors)

    if isinstance(assembly, dict) and assembly.get("conducted_entry_id") == "L000":
        portrait = {
            "Taro": "portrait-taro", "Emma": "portrait-emma", "Bob": "portrait-bob",
            "Errol": "portrait-errol", "Ninereeds": "portrait-ninereeds",
        }
        scene = {
            "Taro": "scene-taro-ninereeds", "Emma": "scene-emma-ninereeds",
            "Bob": "scene-bob-ninereeds", "Errol": "scene-errol-ninereeds",
        }

        def validate_truth_assets(exercise: Any, where: str) -> None:
            if not isinstance(exercise, dict) or exercise.get("response_mode") != "learner_self":
                return
            teacher = exercise.get("teacher_speaker")
            if teacher not in scene:
                errors.append(f"{where}.teacher_speaker: L000 learner-self exercise requires a known teacher speaker")
                return
            required = {scene[teacher], portrait[teacher], portrait["Ninereeds"]}
            teacher_text = exercise.get("teacher_text", "")
            if isinstance(teacher_text, str):
                for name in re.findall(r"\b(?:Taro|Emma|Bob|Errol|Ninereeds)\b", teacher_text):
                    required.add(portrait[name])
            actual = set(exercise.get("asset_ids", [])) if isinstance(exercise.get("asset_ids"), list) else set()
            missing = sorted(required - actual)
            if missing:
                errors.append(f"{where}.asset_ids: missing required relational operands {missing}")

        phases = lesson.get("phases", {})
        if isinstance(phases, dict):
            presentation = phases.get("presentation", [])
            self_models = [
                item for item in presentation
                if isinstance(item, dict) and item.get("id") == "presentation-self-identification"
            ] if isinstance(presentation, list) else []
            expected_self_turn_assets = [
                {"scene-taro-ninereeds", "portrait-taro"},
                {"scene-taro-ninereeds", "portrait-ninereeds"},
                {"scene-emma-bob", "portrait-emma"},
                {"scene-emma-bob", "portrait-bob"},
                {"scene-taro-errol", "portrait-taro"},
                {"scene-taro-errol", "portrait-errol"},
            ]
            if len(self_models) != 1:
                errors.append("$.phases.presentation: L000 requires exactly one participant-grounding self-identification model")
            else:
                turns = self_models[0].get("teacher_turns", [])
                if not isinstance(turns, list) or len(turns) != len(expected_self_turn_assets):
                    errors.append("$.phases.presentation[presentation-self-identification].teacher_turns: must contain the six frozen participant-grounding turns")
                else:
                    for index, (turn, expected_assets) in enumerate(zip(turns, expected_self_turn_assets)):
                        actual_assets = set(turn.get("asset_ids", [])) if isinstance(turn, dict) and isinstance(turn.get("asset_ids"), list) else set()
                        if actual_assets != expected_assets:
                            errors.append(f"$.phases.presentation[presentation-self-identification].teacher_turns[{index}].asset_ids: must equal {sorted(expected_assets)}")
            controlled = phases.get("controlled_practice", {})
            if isinstance(controlled, dict):
                for gate, pool in controlled.items():
                    if isinstance(pool, list):
                        for index, exercise in enumerate(pool):
                            validate_truth_assets(exercise, f"$.phases.controlled_practice.{gate}[{index}]")
            for pool_name in ("mixed_practice", "transfer"):
                pool = phases.get(pool_name)
                if isinstance(pool, list):
                    for index, exercise in enumerate(pool):
                        validate_truth_assets(exercise, f"$.phases.{pool_name}[{index}]")
        adaptive = lesson.get("adaptive", {})
        reserve = adaptive.get("train_more", {}).get("reserve_exercises", []) if isinstance(adaptive, dict) else []
        if isinstance(reserve, list):
            for index, exercise in enumerate(reserve):
                validate_truth_assets(exercise, f"$.adaptive.train_more.reserve_exercises[{index}]")
        picture_book = lesson.get("picture_book", {})
        comprehension = picture_book.get("comprehension", []) if isinstance(picture_book, dict) else []
        if isinstance(comprehension, list):
            for index, exercise in enumerate(comprehension):
                validate_truth_assets(exercise, f"$.picture_book.comprehension[{index}]")
    if stage == "freeze" and output_ids != set(declared_assets):
        errors.append("$.visual_plan.operations: every declared asset must have exactly one visual operation")


def validate_lesson(lesson: dict[str, Any], stage: str) -> list[str]:
    errors: list[str] = []
    schema_version = lesson.get("schema_version")
    top_keys = {
        "schema_version", "lesson_id", "status", "variant", "target_language", "topic",
        "point", "selection", "prerequisites", "source_bindings", "world",
        "language_boundary", "phases", "picture_book", "assets", "adaptive", "rehearsal",
    }
    if schema_version == "ninereeds_lesson_contract_v3":
        top_keys |= {"assembly", "authoring", "independent_review", "visual_plan", "vocabulary_plan"}
    require_keys(lesson, top_keys, "$", errors)
    if schema_version not in {"ninereeds_lesson_contract_v2", "ninereeds_lesson_contract_v3"}:
        errors.append("$.schema_version: must equal ninereeds_lesson_contract_v2 or ninereeds_lesson_contract_v3")
    if not isinstance(lesson.get("lesson_id"), str) or LESSON_ID.fullmatch(lesson["lesson_id"]) is None:
        errors.append("$.lesson_id: must match lesson-<slug>-v<number>")
    if lesson.get("status") != "draft":
        errors.append("$.status: compiler input must be draft")
    if lesson.get("variant") not in {"dialogue_only", "picture_book"}:
        errors.append("$.variant: must be dialogue_only or picture_book")
    for key in ("target_language", "topic"):
        require_string(lesson.get(key), f"$.{key}", errors)

    point = lesson.get("point")
    if not isinstance(point, dict):
        errors.append("$.point: must be an object")
    else:
        require_keys(point, {"id", "claim", "novelty_kind"}, "$.point", errors)
        for key in ("id", "claim", "novelty_kind"):
            require_string(point.get(key), f"$.point.{key}", errors)

    selection = lesson.get("selection")
    if not isinstance(selection, dict):
        errors.append("$.selection: must be an object")
    else:
        keys = {"learner_state_artifact_id", "known_closure_artifact_id", "rationale", "predicted_dosage"}
        require_keys(selection, keys, "$.selection", errors)
        for key in keys:
            require_string(selection.get(key), f"$.selection.{key}", errors)

    prerequisites = lesson.get("prerequisites")
    if not isinstance(prerequisites, list):
        errors.append("$.prerequisites: must be an array")
    else:
        for index, item in enumerate(prerequisites):
            where = f"$.prerequisites[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{where}: must be an object")
                continue
            require_keys(item, {"id", "evidence_artifact_id"}, where, errors)
            require_string(item.get("id"), f"{where}.id", errors)
            require_string(item.get("evidence_artifact_id"), f"{where}.evidence_artifact_id", errors)

    source_bindings = lesson.get("source_bindings")
    if not isinstance(source_bindings, list) or not source_bindings:
        errors.append("$.source_bindings: must be a non-empty array")
    else:
        roles: set[str] = set()
        for index, item in enumerate(source_bindings):
            where = f"$.source_bindings[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{where}: must be an object")
                continue
            require_keys(item, {"role", "path", "sha256"}, where, errors)
            role, raw_path, expected = item.get("role"), item.get("path"), item.get("sha256")
            require_string(role, f"{where}.role", errors)
            require_string(raw_path, f"{where}.path", errors)
            if role in roles:
                errors.append(f"{where}.role: duplicate role {role}")
            roles.add(role)
            if not isinstance(expected, str) or SHA256.fullmatch(expected) is None:
                errors.append(f"{where}.sha256: must be lowercase SHA-256")
            if stage == "freeze" and isinstance(raw_path, str):
                try:
                    path = resolve_repo_path(raw_path)
                    if not path.is_file():
                        errors.append(f"{where}.path: file does not exist")
                    elif isinstance(expected, str) and digest_path(path) != expected:
                        errors.append(f"{where}.sha256: does not match file")
                except ValueError as exc:
                    errors.append(f"{where}.path: {exc}")
        required_roles = {"learner_state", "known_closure", "teaching_methodology", "world_bible", "identity_policy", "instructor_qualification"}
        if schema_version == "ninereeds_lesson_contract_v3":
            required_roles.add("lesson_format")
        missing_roles = sorted(required_roles - roles)
        errors.extend(f"$.source_bindings: missing role {role}" for role in missing_roles)

    world = lesson.get("world")
    if not isinstance(world, dict):
        errors.append("$.world: must be an object")
    else:
        require_keys(world, {"recurring_entities", "new_entries", "extras_policy"}, "$.world", errors)
        if world.get("extras_policy") != "unnamed_nonrecurring_no_persistent_history":
            errors.append("$.world.extras_policy: must preserve the canonical extras policy")
        for list_key in ("recurring_entities", "new_entries"):
            entries = world.get(list_key)
            if not isinstance(entries, list):
                errors.append(f"$.world.{list_key}: must be an array")
                continue
            for index, item in enumerate(entries):
                where = f"$.world.{list_key}[{index}]"
                if not isinstance(item, dict):
                    errors.append(f"{where}: must be an object")
                    continue
                keys = {"id", "introduced_in", "available_from", "canonical_reference_ids"}
                require_keys(item, keys, where, errors)
                for key in ("id", "introduced_in", "available_from"):
                    require_string(item.get(key), f"{where}.{key}", errors)
                refs = item.get("canonical_reference_ids")
                if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref for ref in refs):
                    errors.append(f"{where}.canonical_reference_ids: must be an array of strings")

    language = lesson.get("language_boundary")
    if not isinstance(language, dict):
        errors.append("$.language_boundary: must be an object")
    else:
        keys = {"permitted_rescue_languages", "correct_meaning_wrong_language", "off_topic_response", "role_diversion_response"}
        require_keys(language, keys, "$.language_boundary", errors)
        rescue = language.get("permitted_rescue_languages")
        if not isinstance(rescue, list) or any(not isinstance(item, str) or not item for item in rescue):
            errors.append("$.language_boundary.permitted_rescue_languages: must be an array of strings")
        if language.get("correct_meaning_wrong_language") != "concept_may_be_understood_target_production_not_demonstrated":
            errors.append("$.language_boundary.correct_meaning_wrong_language: invalid policy")
        for key in ("off_topic_response", "role_diversion_response"):
            require_string(language.get(key), f"$.language_boundary.{key}", errors)

    phases = lesson.get("phases")
    lesson_phase_keys = controlled_phase_keys(lesson)
    used_asset_ids: set[str] = set()
    exercise_ids: set[str] = set()
    if not isinstance(phases, dict):
        errors.append("$.phases: must be an object")
    else:
        phase_keys = {"presentation", "controlled_practice", "mixed_practice", "transfer"}
        if schema_version == "ninereeds_lesson_contract_v3":
            phase_keys |= {"presentation_bindings", "execution_sequence"}
        require_keys(phases, phase_keys, "$.phases", errors)
        pools: list[tuple[str, Any]] = [("presentation", phases.get("presentation"))]
        controlled = phases.get("controlled_practice")
        if not isinstance(controlled, dict):
            errors.append("$.phases.controlled_practice: must be an object")
        else:
            require_keys(controlled, set(lesson_phase_keys), "$.phases.controlled_practice", errors)
            pools.extend((f"controlled_practice.{key}", controlled.get(key)) for key in lesson_phase_keys)
        if schema_version == "ninereeds_lesson_contract_v3":
            bindings = phases.get("presentation_bindings")
            presentation = phases.get("presentation")
            presentation_ids = [
                item.get("id") for item in presentation
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ] if isinstance(presentation, list) else []
            if not isinstance(bindings, dict):
                errors.append("$.phases.presentation_bindings: must be an object")
            else:
                require_keys(bindings, set(lesson_phase_keys), "$.phases.presentation_bindings", errors)
                bound_ids: list[str] = []
                for gate in lesson_phase_keys:
                    ids = bindings.get(gate)
                    where = f"$.phases.presentation_bindings.{gate}"
                    if not isinstance(ids, list) or not ids or any(not isinstance(item, str) or not item for item in ids):
                        errors.append(f"{where}: must be a non-empty array of presentation IDs")
                        continue
                    bound_ids.extend(ids)
                    unknown = [item for item in ids if item not in presentation_ids]
                    if unknown:
                        errors.append(f"{where}: unknown presentation IDs {unknown}")
                if len(bound_ids) != len(set(bound_ids)):
                    errors.append("$.phases.presentation_bindings: a presentation may lead into only one controlled gate")
                if bound_ids != presentation_ids:
                    errors.append("$.phases.presentation_bindings: flattened gate order must equal the presentation array exactly")
                expected_sequence: list[dict[str, Any]] = []
                for gate in lesson_phase_keys:
                    expected_sequence.append({"phase": "presentation", "exercise_ids": bindings.get(gate)})
                    expected_sequence.append({
                        "phase": gate,
                        "exercise_ids": [
                            item.get("id") for item in controlled.get(gate, [])
                            if isinstance(item, dict) and isinstance(item.get("id"), str)
                        ] if isinstance(controlled, dict) else [],
                    })
                expected_sequence.append({
                    "phase": "mixed_practice",
                    "exercise_ids": [
                        item.get("id") for item in phases.get("mixed_practice", [])
                        if isinstance(item, dict) and isinstance(item.get("id"), str)
                    ] if isinstance(phases.get("mixed_practice"), list) else [],
                })
                expected_sequence.append({
                    "phase": "picture_book",
                    "exercise_ids": [
                        item.get("id") for item in lesson.get("picture_book", {}).get("pages", [])
                        if isinstance(item, dict) and isinstance(item.get("id"), str)
                    ] if isinstance(lesson.get("picture_book"), dict) else [],
                })
                book_comprehension = [
                    item for item in lesson.get("picture_book", {}).get("comprehension", [])
                    if isinstance(item, dict)
                ] if isinstance(lesson.get("picture_book"), dict) else []
                story_comprehension = [
                    item for item in book_comprehension
                    if item.get("evidence_use") != "learner_label_and_concept"
                ]
                story_transfer = [
                    item for item in book_comprehension
                    if item.get("evidence_use") == "learner_label_and_concept"
                ]
                expected_sequence.append({
                    "phase": "comprehension",
                    "exercise_ids": [item["id"] for item in story_comprehension if isinstance(item.get("id"), str)],
                })
                if story_transfer:
                    expected_sequence.append({
                        "phase": "transfer",
                        "exercise_ids": [item["id"] for item in story_transfer if isinstance(item.get("id"), str)],
                    })
                closing_phase = "closing_recap" if lesson.get("point", {}).get("novelty_kind") == "lexical_set" else "transfer"
                expected_sequence.append({
                    "phase": closing_phase,
                    "exercise_ids": [
                        item.get("id") for item in phases.get("transfer", [])
                        if isinstance(item, dict) and isinstance(item.get("id"), str)
                    ] if isinstance(phases.get("transfer"), list) else [],
                })
                if phases.get("execution_sequence") != expected_sequence:
                    errors.append("$.phases.execution_sequence: must exactly interleave every local model with its controlled gate, then mixed practice, story, comprehension, and the explicit closing phase")
        pools.extend((("mixed_practice", phases.get("mixed_practice")), ("transfer", phases.get("transfer"))))
        for pool_name, pool in pools:
            where = f"$.phases.{pool_name}"
            if not isinstance(pool, list):
                errors.append(f"{where}: must be an array")
                continue
            if pool_name != "transfer" and not pool:
                errors.append(f"{where}: must not be empty")
            for index, exercise in enumerate(pool):
                used_asset_ids |= validate_exercise(
                    exercise,
                    f"{where}[{index}]",
                    errors,
                    require_response_contract=schema_version == "ninereeds_lesson_contract_v3",
                )
                if isinstance(exercise, dict) and isinstance(exercise.get("id"), str):
                    if exercise["id"] in exercise_ids:
                        errors.append(f"{where}[{index}].id: duplicate exercise id {exercise['id']}")
                    exercise_ids.add(exercise["id"])
                if schema_version == "ninereeds_lesson_contract_v3" and isinstance(exercise, dict):
                    mode = exercise.get("response_mode")
                    is_unscored_interface_check = exercise.get("scoring_role") == "unscored_interface_check"
                    if pool_name == "presentation" and mode != "model_only" and not is_unscored_interface_check:
                        errors.append(f"{where}[{index}].response_mode: presentation must be model_only or an explicit unscored interface check")
                    elif pool_name != "presentation" and mode == "model_only":
                        errors.append(f"{where}[{index}].response_mode: model_only is presentation-only")

    if schema_version == "ninereeds_lesson_contract_v3":
        if lesson.get("variant") != "picture_book":
            errors.append("$.variant: v3 handhold lessons must use the complete picture_book format")
        if isinstance(phases, dict):
            presentation = phases.get("presentation")
            if isinstance(presentation, list) and presentation and not any(
                isinstance(exercise, dict) and exercise.get("asset_ids")
                for exercise in presentation
            ):
                errors.append("$.phases.presentation: complete lessons require reviewed visual grounding")
        plan = lesson.get("vocabulary_plan")
        if not isinstance(plan, dict):
            errors.append("$.vocabulary_plan: must be an object")
        else:
            plan_keys = {
                "selection_basis", "default_tested_item_count", "selected_tested_item_count",
                "set_size", "sets", "rationale", "structural_exception",
            }
            require_keys(plan, plan_keys, "$.vocabulary_plan", errors)
            if plan.get("selection_basis") != "point_coherence_stage_and_budget":
                errors.append("$.vocabulary_plan.selection_basis: invalid selection basis")
            if plan.get("default_tested_item_count") != 16:
                errors.append("$.vocabulary_plan.default_tested_item_count: must record the 16-item planning default")
            if plan.get("set_size") != 4:
                errors.append("$.vocabulary_plan.set_size: every lexical set must contain four tested words")
            require_string(plan.get("rationale"), "$.vocabulary_plan.rationale", errors)
            selected = plan.get("selected_tested_item_count")
            if not isinstance(selected, int) or isinstance(selected, bool) or selected < 0 or selected % 4:
                errors.append("$.vocabulary_plan.selected_tested_item_count: must be a non-negative multiple of four")
            sets = plan.get("sets")
            all_items: list[str] = []
            if not isinstance(sets, list):
                errors.append("$.vocabulary_plan.sets: must be an array")
            else:
                set_ids: set[str] = set()
                for index, item_set in enumerate(sets):
                    where = f"$.vocabulary_plan.sets[{index}]"
                    if not isinstance(item_set, dict):
                        errors.append(f"{where}: must be an object")
                        continue
                    require_keys(item_set, {"id", "item_ids"}, where, errors)
                    set_id = item_set.get("id")
                    require_string(set_id, f"{where}.id", errors)
                    if isinstance(set_id, str) and set_id in set_ids:
                        errors.append(f"{where}.id: duplicate set id")
                    if isinstance(set_id, str):
                        set_ids.add(set_id)
                    items = item_set.get("item_ids")
                    if not isinstance(items, list) or len(items) != 4 or len(set(items)) != 4 or any(not isinstance(v, str) or not v for v in items):
                        errors.append(f"{where}.item_ids: must contain exactly four unique tested words")
                    else:
                        all_items.extend(items)
            if len(all_items) != len(set(all_items)):
                errors.append("$.vocabulary_plan.sets: tested words must be unique across sets")
            if isinstance(selected, int) and not isinstance(selected, bool) and selected != len(all_items):
                errors.append("$.vocabulary_plan.selected_tested_item_count: must equal the words in all selected sets")
            structural_exception = plan.get("structural_exception")
            if all_items:
                if structural_exception is not None:
                    errors.append("$.vocabulary_plan.structural_exception: lexical lessons must use complete 4x4 sets")
                if isinstance(phases, dict):
                    controlled = phases.get("controlled_practice")
                    if isinstance(controlled, dict):
                        for family in lesson_phase_keys:
                            pool = controlled.get(family)
                            if isinstance(pool, list) and len(pool) != len(all_items):
                                errors.append(f"$.phases.controlled_practice.{family}: must contain one cell per tested word across the selected 4x4 sets")
                    presentation = phases.get("presentation")
                    if isinstance(presentation, list):
                        presented_words = {
                            turn.get("text")
                            for model in presentation if isinstance(model, dict)
                            for turn in model.get("teacher_turns", []) if isinstance(turn, dict)
                            if isinstance(turn.get("text"), str)
                        }
                        if not set(all_items) <= presented_words:
                            errors.append("$.phases.presentation: must present every selected tested word")
            elif not isinstance(structural_exception, str) or not structural_exception.strip():
                errors.append("$.vocabulary_plan.structural_exception: non-lexical lessons require a deliberate exception rationale")

    picture_book = lesson.get("picture_book")
    if lesson.get("variant") == "dialogue_only":
        if picture_book is not None:
            errors.append("$.picture_book: must be null for dialogue_only")
    elif not isinstance(picture_book, dict):
        errors.append("$.picture_book: must be an object for picture_book")
    else:
        picture_book_keys = {"instructional_kernel", "pages", "comprehension"}
        if schema_version == "ninereeds_lesson_contract_v3":
            picture_book_keys |= {"story_arc", "world_grounding", "identity_safety"}
        require_keys(picture_book, picture_book_keys, "$.picture_book", errors)
        require_string(picture_book.get("instructional_kernel"), "$.picture_book.instructional_kernel", errors)
        if schema_version == "ninereeds_lesson_contract_v3":
            story_arc = picture_book.get("story_arc")
            if not isinstance(story_arc, dict):
                errors.append("$.picture_book.story_arc: must be an object")
            else:
                story_keys = {
                    "initial_state_or_goal", "meaningful_development",
                    "resolution_or_stopping_state", "continuity_bindings", "coherence_test",
                }
                require_keys(story_arc, story_keys, "$.picture_book.story_arc", errors)
                for key in story_keys - {"continuity_bindings"}:
                    require_string(story_arc.get(key), f"$.picture_book.story_arc.{key}", errors)
                bindings = story_arc.get("continuity_bindings")
                if not isinstance(bindings, list) or not bindings or any(not isinstance(v, str) or not v for v in bindings):
                    errors.append("$.picture_book.story_arc.continuity_bindings: must be a non-empty string array")
            world_grounding = picture_book.get("world_grounding")
            if not isinstance(world_grounding, dict):
                errors.append("$.picture_book.world_grounding: must be an object")
            else:
                grounding_keys = {
                    "selected_world_objective", "scored_world_claims",
                    "visual_safety_metadata", "forbidden_novelties",
                }
                require_keys(world_grounding, grounding_keys, "$.picture_book.world_grounding", errors)
                require_string(world_grounding.get("selected_world_objective"), "$.picture_book.world_grounding.selected_world_objective", errors)
                for key in grounding_keys - {"selected_world_objective"}:
                    values = world_grounding.get(key)
                    if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
                        errors.append(f"$.picture_book.world_grounding.{key}: must be a string array")
            identity_safety = picture_book.get("identity_safety")
            expected_identity_safety = {
                "first_person_default_identity": "Ninereeds",
                "l000_non_ninereeds_scored_first_person_forbidden": True,
                "quoted_character_completion_evidence": "never_self_identity_or_independent_first_person",
            }
            if identity_safety != expected_identity_safety:
                errors.append("$.picture_book.identity_safety: must preserve the frozen first-person evidence boundary")
        pages = picture_book.get("pages")
        story_turn_ids: set[str] = set()
        story_turn_texts: dict[str, str] = {}
        if not isinstance(pages, list) or not pages:
            errors.append("$.picture_book.pages: must be a non-empty array")
        else:
            page_ids: set[str] = set()
            for index, page in enumerate(pages):
                where = f"$.picture_book.pages[{index}]"
                if not isinstance(page, dict):
                    errors.append(f"{where}: must be an object")
                    continue
                page_keys = {"id", "asset_id", "caption", "scene_facts"}
                if schema_version == "ninereeds_lesson_contract_v3":
                    page_keys.add("dialogue_turns")
                require_keys(page, page_keys, where, errors)
                for key in ("id", "asset_id", "caption"):
                    require_string(page.get(key), f"{where}.{key}", errors)
                if page.get("id") in page_ids:
                    errors.append(f"{where}.id: duplicate page id")
                page_ids.add(page.get("id"))
                if isinstance(page.get("asset_id"), str):
                    used_asset_ids.add(page["asset_id"])
                facts = page.get("scene_facts")
                if not isinstance(facts, list) or not facts or any(not isinstance(f, str) or not f for f in facts):
                    errors.append(f"{where}.scene_facts: must be a non-empty string array")
                turns = page.get("dialogue_turns")
                if schema_version == "ninereeds_lesson_contract_v3" and (not isinstance(turns, list) or not turns):
                    errors.append(f"{where}.dialogue_turns: must be a non-empty array")
                elif isinstance(turns, list):
                    page_turn_ids: set[str] = set()
                    for turn_index, turn in enumerate(turns):
                        turn_where = f"{where}.dialogue_turns[{turn_index}]"
                        if not isinstance(turn, dict):
                            errors.append(f"{turn_where}: must be an object")
                            continue
                        require_keys(turn, {"id", "speaker", "text", "asset_ids", "responds_to"}, turn_where, errors)
                        for key in ("id", "speaker", "text"):
                            require_string(turn.get(key), f"{turn_where}.{key}", errors)
                        turn_id = turn.get("id")
                        if isinstance(turn_id, str):
                            if turn_id in page_turn_ids:
                                errors.append(f"{turn_where}.id: duplicate")
                            page_turn_ids.add(turn_id)
                            if turn_id in story_turn_ids:
                                errors.append(f"{turn_where}.id: duplicate story turn id")
                            story_turn_ids.add(turn_id)
                            if isinstance(turn.get("text"), str):
                                story_turn_texts[turn_id] = turn["text"]
                        turn_assets = turn.get("asset_ids")
                        if not isinstance(turn_assets, list) or not turn_assets or any(not isinstance(item, str) or not item for item in turn_assets):
                            errors.append(f"{turn_where}.asset_ids: must be a non-empty string array")
                        else:
                            used_asset_ids.update(turn_assets)
                        responds_to = turn.get("responds_to")
                        if responds_to is not None and responds_to not in page_turn_ids:
                            errors.append(f"{turn_where}.responds_to: must cite an earlier turn on the page")
        comprehension = picture_book.get("comprehension")
        if not isinstance(comprehension, list) or not comprehension:
            errors.append("$.picture_book.comprehension: must be a non-empty array")
        else:
            for index, exercise in enumerate(comprehension):
                used_asset_ids |= validate_exercise(
                    exercise,
                    f"$.picture_book.comprehension[{index}]",
                    errors,
                    require_response_contract=schema_version == "ninereeds_lesson_contract_v3",
                )
                if isinstance(exercise, dict) and isinstance(exercise.get("evidence_turn_ids"), list):
                    unknown_turns = sorted(set(exercise["evidence_turn_ids"]) - story_turn_ids)
                    errors.extend(
                        f"$.picture_book.comprehension[{index}].evidence_turn_ids: unknown story turn {turn_id}"
                        for turn_id in unknown_turns
                    )
                if (
                    isinstance(exercise, dict)
                    and exercise.get("response_mode") == "nonverbal_selection"
                    and isinstance(exercise.get("nonverbal_control"), dict)
                ):
                    nonverbal_control = exercise["nonverbal_control"]
                    demonstrations = nonverbal_control.get("demonstrations", [])
                    if isinstance(demonstrations, list):
                        for demo_index, demo in enumerate(demonstrations):
                            if not isinstance(demo, dict):
                                continue
                            if nonverbal_control.get("machine_action") == "SHOW_SCENE_SELECT_PHONE_IDENTITY":
                                continue
                            turn_id = demo.get("turn_id")
                            if turn_id not in story_turn_texts:
                                errors.append(f"$.picture_book.comprehension[{index}].nonverbal_control.demonstrations[{demo_index}].turn_id: unknown story turn")
                            elif demo.get("replay_text") != story_turn_texts[turn_id]:
                                errors.append(f"$.picture_book.comprehension[{index}].nonverbal_control.demonstrations[{demo_index}].replay_text: must exactly equal the bound story turn")

        if (
            schema_version == "ninereeds_lesson_contract_v3"
            and isinstance(lesson.get("assembly"), dict)
            and lesson["assembly"].get("conducted_entry_id") == "L000"
        ):
            exercise_pools: list[Any] = []
            if isinstance(phases, dict):
                exercise_pools.extend(phases.get("presentation", []))
                controlled = phases.get("controlled_practice")
                if isinstance(controlled, dict):
                    for family in lesson_phase_keys:
                        exercise_pools.extend(controlled.get(family, []))
                exercise_pools.extend(phases.get("mixed_practice", []))
                exercise_pools.extend(phases.get("transfer", []))
            if isinstance(comprehension, list):
                exercise_pools.extend(comprehension)
            for exercise in exercise_pools:
                if not isinstance(exercise, dict):
                    continue
                answers = exercise.get("expected_answers", [])
                if exercise.get("response_mode") == "quoted_character_completion":
                    errors.append(f"exercise {exercise.get('id')}: L000 forbids scored quoted-character completion")
                if isinstance(answers, list) and any(
                    isinstance(answer, str)
                    and re.search(r"\bI(?:'m| am)\s+(?:Taro|Emma|Bob|Errol)\b", answer)
                    for answer in answers
                ):
                    errors.append(f"exercise {exercise.get('id')}: L000 scored first-person identity must remain Ninereeds")

    assets = lesson.get("assets")
    declared_assets: dict[str, dict[str, Any]] = {}
    if not isinstance(assets, list):
        errors.append("$.assets: must be an array")
    else:
        for index, asset in enumerate(assets):
            where = f"$.assets[{index}]"
            if not isinstance(asset, dict):
                errors.append(f"{where}: must be an object")
                continue
            keys = {"id", "purpose", "status", "source", "path", "sha256", "review_receipt_id", "parent_asset_id", "crop_xywh", "canonical_reference_ids", "attempted_sources", "escalation_reason"}
            require_keys(asset, keys, where, errors)
            asset_id = asset.get("id")
            require_string(asset_id, f"{where}.id", errors)
            require_string(asset.get("purpose"), f"{where}.purpose", errors)
            if isinstance(asset_id, str):
                if asset_id in declared_assets:
                    errors.append(f"{where}.id: duplicate asset id {asset_id}")
                declared_assets[asset_id] = asset
            if asset.get("status") not in {"needed", "commissioned_pending", "reviewed_usable"}:
                errors.append(f"{where}.status: invalid status")
            if asset.get("source") not in {
                "registry", "external", "reuse", "highlight", "flux_edit", "flux_generation",
                "openai_imagegen", "imagegen_generate", "imagegen_fallback", "deterministic_crop", "deterministic_composite",
            }:
                errors.append(f"{where}.source: invalid source")
            for key in ("canonical_reference_ids", "attempted_sources"):
                if not isinstance(asset.get(key), list) or any(not isinstance(item, str) or not item for item in asset.get(key, [])):
                    errors.append(f"{where}.{key}: must be an array of strings")
            if asset.get("source") == "deterministic_crop":
                require_string(asset.get("parent_asset_id"), f"{where}.parent_asset_id", errors)
                box = asset.get("crop_xywh")
                if not isinstance(box, list) or len(box) != 4 or any(not isinstance(n, int) or n < 0 for n in box):
                    errors.append(f"{where}.crop_xywh: must contain four non-negative integers")
            elif asset.get("crop_xywh") is not None:
                errors.append(f"{where}.crop_xywh: only deterministic crops may define a crop box")
            if asset.get("source") in {"openai_imagegen", "imagegen_fallback"}:
                if (
                    not asset.get("canonical_reference_ids")
                    and "flux_generation" not in asset.get("attempted_sources", [])
                    and "flux_edit" not in asset.get("attempted_sources", [])
                ):
                    errors.append(f"{where}.attempted_sources: ImageGen requires a recorded Flux attempt")
                require_string(asset.get("escalation_reason"), f"{where}.escalation_reason", errors)
            if stage == "freeze":
                if asset.get("status") != "reviewed_usable":
                    errors.append(f"{where}.status: must be reviewed_usable to freeze")
                for key in ("path", "review_receipt_id"):
                    require_string(asset.get(key), f"{where}.{key}", errors)
                expected = asset.get("sha256")
                if not isinstance(expected, str) or SHA256.fullmatch(expected) is None:
                    errors.append(f"{where}.sha256: must be lowercase SHA-256")
                if isinstance(asset.get("path"), str):
                    try:
                        path = resolve_repo_path(asset["path"])
                        if not path.is_file():
                            errors.append(f"{where}.path: file does not exist")
                        elif isinstance(expected, str) and digest_path(path) != expected:
                            errors.append(f"{where}.sha256: does not match file")
                    except ValueError as exc:
                        errors.append(f"{where}.path: {exc}")
        unknown = sorted(used_asset_ids - set(declared_assets))
        errors.extend(f"asset reference is not declared: {item}" for item in unknown)
        for asset_id, asset in declared_assets.items():
            parent = asset.get("parent_asset_id")
            if parent is not None and parent not in declared_assets:
                errors.append(f"asset {asset_id}: parent asset {parent} is not declared")

    if schema_version == "ninereeds_lesson_contract_v3":
        validate_v3_assembly(lesson, stage, declared_assets, errors)

    adaptive = lesson.get("adaptive")
    if not isinstance(adaptive, dict):
        errors.append("$.adaptive: must be an object")
    else:
        keys = {
            "presentation_replay_after_failures", "maximum_teacher_turns",
            "mixed_practice_cap", "controller_actions",
            "marker_intervention",
        }
        is_l000_v3 = (
            schema_version == "ninereeds_lesson_contract_v3"
            and isinstance(lesson.get("assembly"), dict)
            and lesson["assembly"].get("conducted_entry_id") == "L000"
        )
        if schema_version == "ninereeds_lesson_contract_v3":
            keys |= {
                "present_again", "train_more", "train_longer", "mixed_execution",
                "replay_lesson", "finish", "alarm",
            }
            if "controller_transition_table" in adaptive:
                keys.add("controller_transition_table")
            if "runtime_contract" in adaptive:
                keys.add("runtime_contract")
        if is_l000_v3:
            keys |= {
                "maximum_teacher_turns_scope", "base_teacher_turn_count", "phase_terminal_rules",
                "budget_exhaustion", "overall_mastery", "teacher_turn_accounting", "completion_thresholds",
            }
        elif "runtime_contract" not in adaptive:
            keys.add("completion_fraction")
        require_keys(adaptive, keys, "$.adaptive", errors)
        for key in ("presentation_replay_after_failures", "maximum_teacher_turns", "mixed_practice_cap"):
            if not isinstance(adaptive.get(key), int) or adaptive[key] < 1:
                errors.append(f"$.adaptive.{key}: must be a positive integer")
        if is_l000_v3:
            if adaptive.get("maximum_teacher_turns_scope") != "full_lesson_execution_including_all_released_adaptations_and_one_replay":
                errors.append("$.adaptive.maximum_teacher_turns_scope: must bind the global cap to the full execution including released adaptations and one replay")
            phases = lesson.get("phases", {})
            presentation_turns = sum(
                len(item.get("teacher_turns", []))
                for item in phases.get("presentation", [])
                if isinstance(item, dict) and isinstance(item.get("teacher_turns"), list)
            ) if isinstance(phases, dict) else 0
            controlled_turns = sum(
                len(pool) for pool in phases.get("controlled_practice", {}).values() if isinstance(pool, list)
            ) if isinstance(phases, dict) and isinstance(phases.get("controlled_practice"), dict) else 0
            mixed_turns = len(phases.get("mixed_practice", [])) if isinstance(phases, dict) and isinstance(phases.get("mixed_practice"), list) else 0
            recap_turns = len(phases.get("transfer", [])) if isinstance(phases, dict) and isinstance(phases.get("transfer"), list) else 0
            picture_book = lesson.get("picture_book", {})
            story_turns = sum(
                len(page.get("dialogue_turns", []))
                for page in picture_book.get("pages", [])
                if isinstance(page, dict) and isinstance(page.get("dialogue_turns"), list)
            ) if isinstance(picture_book, dict) else 0
            comprehension_items = picture_book.get("comprehension", []) if isinstance(picture_book, dict) and isinstance(picture_book.get("comprehension"), list) else []
            comprehension_turns = sum(
                len(item.get("nonverbal_control", {}).get("scored_action_sequence", []))
                if isinstance(item, dict)
                and isinstance(item.get("nonverbal_control"), dict)
                and isinstance(item["nonverbal_control"].get("scored_action_sequence"), list)
                else 1
                for item in comprehension_items
            )
            comprehension_demonstrations = sum(
                len(item.get("nonverbal_control", {}).get("demonstrations", []))
                for item in picture_book.get("comprehension", [])
                if isinstance(item, dict)
                and isinstance(item.get("nonverbal_control"), dict)
                and isinstance(item["nonverbal_control"].get("demonstrations"), list)
            ) if isinstance(picture_book, dict) and isinstance(picture_book.get("comprehension"), list) else 0
            comprehension_demo_turns = comprehension_demonstrations * 3
            expected_base_turns = presentation_turns + controlled_turns + mixed_turns + story_turns + comprehension_turns + comprehension_demo_turns + recap_turns
            maximum_adaptive_additions = 28
            expected_global_cap = expected_base_turns * 2 + maximum_adaptive_additions
            if adaptive.get("base_teacher_turn_count") != expected_base_turns:
                errors.append(f"$.adaptive.base_teacher_turn_count: must equal the executable base-path count {expected_base_turns}")
            if adaptive.get("maximum_teacher_turns") != expected_global_cap:
                errors.append(f"$.adaptive.maximum_teacher_turns: must equal two base paths plus 28 maximal adaptive turns ({expected_global_cap})")
            terminal_rules = adaptive.get("phase_terminal_rules")
            required_terminal_phases = {
                "affirmative", "negative", "W_question", "OR_question", "reciprocity",
                "mixed_practice", "picture_book", "comprehension", "transfer",
            }
            if not isinstance(terminal_rules, dict) or set(terminal_rules) != required_terminal_phases:
                errors.append("$.adaptive.phase_terminal_rules: must define exactly the five controlled gates, mixed_practice, picture_book, comprehension, and transfer")
            else:
                for phase_name, rule in terminal_rules.items():
                    where = f"$.adaptive.phase_terminal_rules.{phase_name}"
                    if not isinstance(rule, dict):
                        errors.append(f"{where}: must be an object")
                        continue
                    require_keys(rule, {"success", "failure", "stop"}, where, errors)
                    for key in ("success", "failure", "stop"):
                        require_string(rule.get(key), f"{where}.{key}", errors)
                controlled_rule = {
                    "success": "success_after_at_least_3_of_4_base_correct_or_2_consecutive_released_reserve_correct",
                    "failure": "failure_after_fewer_than_3_of_4_base_correct_and_2_released_reserves_exhausted_without_2_consecutive_correct",
                    "stop": "stop_after_4_base_and_at_most_2_released_reserves_or_any_alarm",
                }
                expected_terminal_rules = {
                    "affirmative": controlled_rule,
                    "negative": controlled_rule,
                    "W_question": controlled_rule,
                    "OR_question": controlled_rule,
                    "reciprocity": controlled_rule,
                    "mixed_practice": {
                        "success": "success_after_exactly_20_scored_items_with_at_least_16_correct",
                        "failure": "failure_after_exactly_20_scored_items_with_fewer_than_16_correct",
                        "stop": "stop_after_exactly_20_scored_items_or_any_alarm",
                    },
                    "picture_book": {
                        "success": f"success_after_all_{len(picture_book.get('pages', []))}_pages_and_{story_turns}_story_turns_emitted_once_in_order",
                        "failure": "failure_on_missing_out_of_order_or_asset_contradictory_page_or_turn",
                        "stop": "stop_after_page_08_or_any_alarm",
                    },
                    "comprehension": {
                        "success": "success_after_2_of_2_narrative_selections_correct_and_direct_application_recorded",
                        "failure": "failure_after_both_narrative_selections_and_direct_application_are_recorded_without_success",
                        "stop": "stop_after_exactly_3_checks_or_any_alarm",
                    },
                    "transfer": {
                        "success": "success_after_at_least_4_of_5_transfer_items_correct",
                        "failure": "failure_after_fewer_than_4_of_5_transfer_items_correct",
                        "stop": "stop_after_exactly_5_transfer_items_or_any_alarm",
                    },
                }
                if terminal_rules != expected_terminal_rules:
                    errors.append("$.adaptive.phase_terminal_rules: must equal the frozen executable count-and-stop contract")
            budget_exhaustion = adaptive.get("budget_exhaustion")
            expected_budget_exhaustion = {
                "trigger": f"next_teacher_turn_would_exceed_{expected_global_cap}",
                "outcome": "defer_and_revisit",
                "behavior": f"permit_turn_{expected_global_cap}_then_terminate_current_path_recompute_mastery_and_apply_FINISH_or_defer_before_any_further_emission",
            }
            if budget_exhaustion != expected_budget_exhaustion:
                errors.append("$.adaptive.budget_exhaustion: must equal the frozen global-cap terminal transition")
            expected_turn_accounting = {
                "unit": "one_emitted_teacher_language_turn_or_machine_control_action_equals_one_teacher_turn",
                "simultaneous_asset_display": "does_not_add_turn_when_bound_to_the_same_emission",
                "base_path_breakdown": {
                    "presentation_teacher_turns": presentation_turns,
                    "controlled_scored_prompts": controlled_turns,
                    "mixed_scored_prompts": mixed_turns,
                    "picture_book_dialogue_turns": story_turns,
                    "comprehension_demonstration_replays": comprehension_demonstrations,
                    "comprehension_demonstration_option_displays": comprehension_demonstrations,
                    "comprehension_demonstration_feedback_actions": comprehension_demonstrations,
                    "comprehension_scored_control_actions": comprehension_turns,
                    "transfer_scored_prompts": recap_turns,
                    "total": expected_base_turns,
                },
                "adaptive_additions": {
                    "present_again": "count_each_replayed_presentation_teacher_turn",
                    "train_more": "count_each_released_reserve_prompt",
                    "train_longer": "count_each_released_base_prompt",
                    "replay_lesson": "count_each_base_path_emission_under_the_same_rules",
                },
                "counter_update": f"increment_before_each_emission_and_apply_budget_exhaustion_instead_of_emitting_when_the_next_increment_would_exceed_{expected_global_cap}",
            }
            if adaptive.get("teacher_turn_accounting") != expected_turn_accounting:
                errors.append("$.adaptive.teacher_turn_accounting: must equal the frozen all-emission accounting contract")
            expected_overall_mastery = {
                "controlled_gate_successes_required": 5,
                "mixed_minimum_successes": 16,
                "mixed_denominator": 20,
                "picture_book_terminal_required": "success",
                "narrative_comprehension_successes_required": 2,
                "direct_application_success_required": True,
                "transfer_minimum_successes": 4,
                "transfer_denominator": 5,
                "aggregate_rule": "all_conditions_required",
            }
            if adaptive.get("overall_mastery") != expected_overall_mastery:
                errors.append("$.adaptive.overall_mastery: must equal the frozen all-phases aggregate predicate")
            expected_completion_thresholds = {
                "controlled_gate": "3_of_4_base_or_2_consecutive_released_reserve",
                "mixed_practice": "16_of_20",
                "picture_book": "all_9_pages_and_18_dialogue_turns_in_order",
                "comprehension": "2_of_2_narrative_selections_and_1_direct_application_recorded",
                "transfer": "4_of_5_transfer_items",
            }
            if adaptive.get("completion_thresholds") != expected_completion_thresholds:
                errors.append("$.adaptive.completion_thresholds: must equal the phase-scoped terminal thresholds")
            if "completion_fraction" in adaptive:
                errors.append("$.adaptive.completion_fraction: ambiguous global fraction is forbidden for L000")
        elif "runtime_contract" in adaptive:
            runtime_contract = adaptive.get("runtime_contract")
            if not isinstance(runtime_contract, dict):
                errors.append("$.adaptive.runtime_contract: must be an object")
            else:
                accounting = runtime_contract.get("budgets")
                if not isinstance(accounting, dict) or accounting.get("teacher_cap") != adaptive.get("maximum_teacher_turns"):
                    errors.append("$.adaptive.runtime_contract.turn_accounting: maximum_teacher_turns must match the global controller cap")
                alarm_contract = runtime_contract.get("alarm")
                if not isinstance(alarm_contract, dict) or alarm_contract.get("absorbing_state") != "alarm_frozen":
                    errors.append("$.adaptive.runtime_contract.alarm_contract: must define the absorbing alarm_frozen state")
                registry = runtime_contract.get("interface_registry")
                presentation_checks = [
                    item for item in lesson.get("phases", {}).get("presentation", [])
                    if isinstance(item, dict) and item.get("scoring_role") == "unscored_interface_check"
                ]
                if not isinstance(registry, list) or len(registry) != len(presentation_checks):
                    errors.append("$.adaptive.runtime_contract.interface_registry: must map every emitted interface check exactly once")
                else:
                    for emitted, registered in zip(presentation_checks, registry):
                        control = emitted.get("nonverbal_control", {})
                        operands = registered.get("operands", {}) if isinstance(registered, dict) else {}
                        expected_option_ids = [
                            option.get("id") for option in control.get("options", []) if isinstance(option, dict)
                        ]
                        actual_option_ids = operands.get("option_ids", operands.get("options", []))
                        checks = (
                            isinstance(registered, dict)
                            and registered.get("exercise_id") == emitted.get("id")
                            and registered.get("asset_ids") == emitted.get("asset_ids")
                            and registered.get("response_mode") == emitted.get("response_mode")
                            and registered.get("machine_action") == control.get("machine_action")
                            and registered.get("action_sequence", []) == control.get("action_sequence", [])
                            and actual_option_ids == expected_option_ids
                            and operands.get("correct_answer") == (emitted.get("expected_answers") or [None])[0]
                        )
                        if control.get("displayed_mismatch_label") is not None:
                            checks = checks and operands.get("displayed_mismatch_label") == control.get("displayed_mismatch_label")
                        if not checks:
                            errors.append(f"$.adaptive.runtime_contract.interface_registry.{emitted.get('id')}: contradicts the emitted check")
                budgets = runtime_contract.get("budgets")
                if isinstance(budgets, dict):
                    phases_for_count = lesson.get("phases", {})
                    story_for_count = lesson.get("picture_book", {})
                    presentation_label_turns = sum(len(item.get("teacher_turns", [])) for item in phases_for_count.get("presentation", []) if isinstance(item, dict))
                    interface_turns = len(presentation_checks)
                    controlled_turns = sum(len(pool) for pool in phases_for_count.get("controlled_practice", {}).values())
                    mixed_turns = len(phases_for_count.get("mixed_practice", []))
                    story_turns = sum(len(page.get("dialogue_turns", [])) for page in story_for_count.get("pages", []) if isinstance(page, dict))
                    comprehension_turns = len(story_for_count.get("comprehension", []))
                    recap_turns = len(phases_for_count.get("transfer", []))
                    expected_base = presentation_label_turns + interface_turns + controlled_turns + mixed_turns + story_turns + comprehension_turns + recap_turns
                    expected_adaptive = (
                        2 * adaptive.get("present_again", {}).get("maximum_total_uses", 0)
                        + len(adaptive.get("train_more", {}).get("reserve_exercises", []))
                        + adaptive.get("train_longer", {}).get("max_additional_items", 0)
                        + presentation_label_turns + interface_turns
                    )
                    if budgets.get("base") != expected_base or budgets.get("maximum_adaptive_additions") != expected_adaptive or budgets.get("replay") != expected_base:
                        errors.append(f"$.adaptive.runtime_contract.budgets: must account {expected_base} base + {expected_adaptive} maximal adaptations + {expected_base} replay")
                    for cap in ("teacher_cap", "student_cap", "tool_cap"):
                        if budgets.get(cap) != expected_base + expected_adaptive + expected_base:
                            errors.append(f"$.adaptive.runtime_contract.budgets.{cap}: must equal {expected_base + expected_adaptive + expected_base}")
        else:
            fraction = adaptive.get("completion_fraction")
            if not isinstance(fraction, (int, float)) or isinstance(fraction, bool) or not 0 < fraction <= 1:
                errors.append("$.adaptive.completion_fraction: must be greater than 0 and at most 1")
        allowed_actions = {
            "CONTINUE", "PRESENT_AGAIN", "USE_MARKERS", "TRAIN_MORE",
            "TRAIN_LONGER", "REPLAY_LESSON", "BACKTRACK", "ALARM", "FINISH",
        }
        actions = adaptive.get("controller_actions")
        if not isinstance(actions, list) or not actions or not set(actions).issubset(allowed_actions):
            errors.append("$.adaptive.controller_actions: contains invalid actions")
        marker = adaptive.get("marker_intervention")
        if not isinstance(marker, dict):
            errors.append("$.adaptive.marker_intervention: must be an object")
        else:
            marker_keys = {
                "action", "enabled", "role_delimiters", "focus_delimiter", "levels",
                "scheduled_presentation_fraction", "immediate_retest",
                "expected_student_output", "fade_after_consecutive_unmarked_successes",
                "fade_after_distinct_scenes", "max_scored_mixed_prompts",
                "max_unchanged_failure_episodes", "terminal_outcome",
            }
            require_keys(marker, marker_keys, "$.adaptive.marker_intervention", errors)
            if marker.get("action") != "USE_MARKERS":
                errors.append("$.adaptive.marker_intervention.action: must equal USE_MARKERS")
            lexical_bootstrap = (
                isinstance(lesson.get("point"), dict)
                and lesson["point"].get("novelty_kind") == "lexical_set"
            )
            if is_l000_v3 or lexical_bootstrap:
                if marker.get("enabled") is not False:
                    errors.append("$.adaptive.marker_intervention.enabled: identity and lexical-bootstrap lessons must disable irrelevant live marker construction")
                if isinstance(actions, list) and "USE_MARKERS" in actions:
                    errors.append("$.adaptive.controller_actions: disabled marker intervention forbids USE_MARKERS")
            else:
                if marker.get("enabled") is not True:
                    errors.append("$.adaptive.marker_intervention.enabled: must be true")
                if isinstance(actions, list) and "USE_MARKERS" not in actions:
                    errors.append("$.adaptive.controller_actions: enabled marker intervention requires USE_MARKERS")
            expected_roles = {
                "subject": ["(", ")"], "predicate": ["*", "*"],
                "recipient": ["[", "]"], "object": ["{", "}"],
                "possessor": ["<", ">"],
            }
            if marker.get("role_delimiters") != expected_roles:
                errors.append("$.adaptive.marker_intervention.role_delimiters: marker meanings must remain frozen")
            if marker.get("focus_delimiter") != ["+", "+"]:
                errors.append("$.adaptive.marker_intervention.focus_delimiter: must equal ['+', '+']")
            expected_levels = ["none", "constituent_only", "full_role_map", "frontier_focus"]
            if marker.get("levels") != expected_levels:
                errors.append("$.adaptive.marker_intervention.levels: must preserve the ordered support levels")
            fraction = marker.get("scheduled_presentation_fraction")
            if not isinstance(fraction, (int, float)) or isinstance(fraction, bool) or not 0 <= fraction <= 1:
                errors.append("$.adaptive.marker_intervention.scheduled_presentation_fraction: must be between 0 and 1")
            if marker.get("immediate_retest") != "unmarked":
                errors.append("$.adaptive.marker_intervention.immediate_retest: must equal unmarked")
            if marker.get("expected_student_output") != "unmarked":
                errors.append("$.adaptive.marker_intervention.expected_student_output: must equal unmarked")
            for key in (
                "fade_after_consecutive_unmarked_successes", "fade_after_distinct_scenes",
                "max_scored_mixed_prompts", "max_unchanged_failure_episodes",
            ):
                if not isinstance(marker.get(key), int) or isinstance(marker.get(key), bool) or marker[key] < 1:
                    errors.append(f"$.adaptive.marker_intervention.{key}: must be a positive integer")
            marker_cap = marker.get("max_scored_mixed_prompts")
            mixed_cap = adaptive.get("mixed_practice_cap")
            if isinstance(marker_cap, int) and not isinstance(marker_cap, bool) and isinstance(mixed_cap, int) and not isinstance(mixed_cap, bool) and marker_cap > mixed_cap:
                errors.append("$.adaptive.marker_intervention.max_scored_mixed_prompts: exceeds mixed-practice cap")
            if marker.get("terminal_outcome") != "defer_and_revisit":
                errors.append("$.adaptive.marker_intervention.terminal_outcome: must equal defer_and_revisit")
        if schema_version == "ninereeds_lesson_contract_v3":
            present_again = adaptive.get("present_again")
            if not isinstance(present_again, dict):
                errors.append("$.adaptive.present_again: must be an object")
            else:
                present_again_keys = {"action", "source", "presentation_ids", "release_rule", "maximum_total_uses", "return_rule", "exhaustion"}
                if is_l000_v3:
                    present_again_keys.add("dispatch_table")
                lexical_bootstrap = lesson.get("point", {}).get("novelty_kind") == "lexical_set"
                hardened_lexical = lexical_bootstrap and "controller_transition_table" in adaptive
                if hardened_lexical:
                    present_again_keys |= {"dispatch_table", "retest_exercises"}
                require_keys(present_again, present_again_keys, "$.adaptive.present_again", errors)
                if present_again.get("action") != "PRESENT_AGAIN" or present_again.get("source") != "frozen_presentation_ids_only":
                    errors.append("$.adaptive.present_again: must bind PRESENT_AGAIN to frozen_presentation_ids_only")
                presentation_ids = present_again.get("presentation_ids")
                if not isinstance(presentation_ids, list) or not presentation_ids or any(item not in exercise_ids for item in presentation_ids):
                    errors.append("$.adaptive.present_again.presentation_ids: every ID must resolve to a frozen presentation exercise")
                for key in ("release_rule", "return_rule"):
                    require_string(present_again.get(key), f"$.adaptive.present_again.{key}", errors)
                if not isinstance(present_again.get("maximum_total_uses"), int) or isinstance(present_again.get("maximum_total_uses"), bool) or present_again["maximum_total_uses"] < 1:
                    errors.append("$.adaptive.present_again.maximum_total_uses: must be a positive integer")
                if present_again.get("exhaustion") != "defer_and_revisit":
                    errors.append("$.adaptive.present_again.exhaustion: must equal defer_and_revisit")
                if hardened_lexical:
                    retests = present_again.get("retest_exercises")
                    retest_ids: set[str] = set()
                    if not isinstance(retests, list) or not retests:
                        errors.append("$.adaptive.present_again.retest_exercises: must be a non-empty array")
                    else:
                        for index, retest in enumerate(retests):
                            retest_where = f"$.adaptive.present_again.retest_exercises[{index}]"
                            retest_assets = validate_exercise(retest, retest_where, errors, require_response_contract=True)
                            unknown_retest_assets = sorted(retest_assets - set(declared_assets))
                            errors.extend(f"{retest_where}: asset reference is not declared: {item}" for item in unknown_retest_assets)
                            if isinstance(retest, dict) and isinstance(retest.get("id"), str):
                                retest_ids.add(retest["id"])
                            if isinstance(retest, dict) and retest.get("scoring_role") != "unscored_parallel_retest":
                                errors.append(f"{retest_where}.scoring_role: must equal unscored_parallel_retest")
                    dispatch = present_again.get("dispatch_table")
                    controlled = phases.get("controlled_practice", {}) if isinstance(phases, dict) else {}
                    base_items = [item for pool in controlled.values() for item in pool if isinstance(item, dict)] if isinstance(controlled, dict) else []
                    base_ids = {item.get("id") for item in base_items if isinstance(item.get("id"), str)}
                    if not isinstance(dispatch, dict) or set(dispatch) != base_ids:
                        errors.append("$.adaptive.present_again.dispatch_table: must map every and only controlled base item")
                    else:
                        for base in base_items:
                            mapping = dispatch[base["id"]]
                            if not isinstance(mapping, dict) or set(mapping) != {"gate", "target_label", "presentation_id", "worked_item_label", "cold_retest_exercise_id"}:
                                errors.append(f"$.adaptive.present_again.dispatch_table.{base['id']}: invalid mapping")
                                continue
                            vocabulary_labels = {
                                label
                                for vocabulary_set in lesson.get("vocabulary_plan", {}).get("sets", [])
                                if isinstance(vocabulary_set, dict)
                                for label in vocabulary_set.get("item_ids", [])
                                if isinstance(label, str)
                            }
                            if (
                                mapping.get("presentation_id") not in presentation_ids
                                or mapping.get("target_label") not in vocabulary_labels
                                or mapping.get("worked_item_label") != mapping.get("target_label")
                            ):
                                errors.append(f"$.adaptive.present_again.dispatch_table.{base['id']}: presentation/target mapping is not frozen")
                            if mapping.get("cold_retest_exercise_id") not in retest_ids:
                                errors.append(f"$.adaptive.present_again.dispatch_table.{base['id']}.cold_retest_exercise_id: unknown")
                if is_l000_v3:
                    expected_dispatch = {
                        "affirmative": {"presentation_id": "presentation-affirmative", "cold_retest_exercise_id": "aff-04"},
                        "negative": {"presentation_id": "presentation-negative", "cold_retest_exercise_id": "neg-04"},
                        "W_question": {"presentation_id": "presentation-W-question", "cold_retest_exercise_id": "who-04"},
                        "OR_question": {"presentation_id": "presentation-OR-question", "cold_retest_exercise_id": "or-04"},
                        "reciprocity": {"presentation_id": "presentation-reciprocity", "cold_retest_exercise_id": "recip-04"},
                    }
                    if present_again.get("dispatch_table") != expected_dispatch:
                        errors.append("$.adaptive.present_again.dispatch_table: must equal the frozen gate-to-presentation-and-cold-retest map")
                    bindings = phases.get("presentation_bindings", {}) if isinstance(phases, dict) else {}
                    if isinstance(bindings, dict):
                        for gate, mapping in expected_dispatch.items():
                            ids = bindings.get(gate)
                            if isinstance(ids, list) and ids and ids[-1] != mapping["presentation_id"]:
                                errors.append(f"$.phases.presentation_bindings.{gate}: final local model must equal the PRESENT_AGAIN presentation_id")
                    if present_again.get("release_rule") != "after_the_first_3_base_items_in_a_gate_are_incorrect_dispatch_that_gates_exact_mapping_if_its_single_use_remains":
                        errors.append("$.adaptive.present_again.release_rule: must mechanically bind the failure trigger and dispatch mapping")
                    if present_again.get("return_rule") != "emit_the_mapped_presentation_once_then_administer_the_mapped_fourth_base_item_unmarked_as_that_gates_final_base_item":
                        errors.append("$.adaptive.present_again.return_rule: must mechanically bind the mapped unmarked cold retest")
                    if present_again.get("maximum_total_uses") != 5:
                        errors.append("$.adaptive.present_again.maximum_total_uses: L000 permits at most one exact dispatch per controlled gate")
                if isinstance(actions, list) and "PRESENT_AGAIN" not in actions:
                    errors.append("$.adaptive.controller_actions: present_again contract requires PRESENT_AGAIN")
            defined_reserve_ids: list[str] = []
            train_more = adaptive.get("train_more")
            if not isinstance(train_more, dict):
                errors.append("$.adaptive.train_more: must be an object")
            else:
                train_more_keys = {"action", "source", "reserve_ids", "reserve_exercises", "release_rule", "max_items_per_gate", "exhaustion"}
                lexical_bootstrap = lesson.get("point", {}).get("novelty_kind") == "lexical_set"
                if lexical_bootstrap:
                    train_more_keys.add("gate_execution")
                if "runtime_contract" in adaptive:
                    train_more_keys |= {"selection_rule", "score_rule"}
                require_keys(train_more, train_more_keys, "$.adaptive.train_more", errors)
                if train_more.get("action") != "TRAIN_MORE":
                    errors.append("$.adaptive.train_more.action: must equal TRAIN_MORE")
                if train_more.get("source") != "preauthored_reserve_only":
                    errors.append("$.adaptive.train_more.source: must equal preauthored_reserve_only")
                reserve_ids = train_more.get("reserve_ids")
                if not isinstance(reserve_ids, list) or not reserve_ids or len(reserve_ids) != len(set(reserve_ids)) or any(not isinstance(item, str) or not item for item in reserve_ids):
                    errors.append("$.adaptive.train_more.reserve_ids: must be a non-empty unique string array")
                reserve_exercises = train_more.get("reserve_exercises")
                if not isinstance(reserve_exercises, list) or not reserve_exercises:
                    errors.append("$.adaptive.train_more.reserve_exercises: must contain the frozen reserve exercise objects")
                else:
                    for reserve_index, reserve_exercise in enumerate(reserve_exercises):
                        reserve_where = f"$.adaptive.train_more.reserve_exercises[{reserve_index}]"
                        reserve_assets = validate_exercise(
                            reserve_exercise,
                            reserve_where,
                            errors,
                            require_response_contract=True,
                        )
                        unknown_reserve_assets = sorted(reserve_assets - set(declared_assets))
                        errors.extend(f"{reserve_where}: asset reference is not declared: {item}" for item in unknown_reserve_assets)
                        if isinstance(reserve_exercise, dict) and isinstance(reserve_exercise.get("id"), str):
                            defined_reserve_ids.append(reserve_exercise["id"])
                if isinstance(reserve_ids, list) and reserve_ids != defined_reserve_ids:
                    errors.append("$.adaptive.train_more.reserve_ids: must match reserve_exercises in order")
                require_string(train_more.get("release_rule"), "$.adaptive.train_more.release_rule", errors)
                if is_l000_v3 and train_more.get("release_rule") != "after_a_gate_records_fewer_than_3_of_4_base_correct_release_reserve_1_then_release_reserve_2_unconditionally_in_frozen_gate_order_and_record_success_only_if_both_are_correct_otherwise_failure":
                    errors.append("$.adaptive.train_more.release_rule: must release both frozen reserves and terminate every base-failure branch")
                if not isinstance(train_more.get("max_items_per_gate"), int) or isinstance(train_more.get("max_items_per_gate"), bool) or train_more["max_items_per_gate"] < 1:
                    errors.append("$.adaptive.train_more.max_items_per_gate: must be a positive integer")
                if train_more.get("exhaustion") != "defer_and_revisit":
                    errors.append("$.adaptive.train_more.exhaustion: must equal defer_and_revisit")
                if lexical_bootstrap:
                    gate_execution = train_more.get("gate_execution")
                    expected_gates = {"affirmative", "negative", "W_question", "OR_question"}
                    if not isinstance(gate_execution, dict) or set(gate_execution) != expected_gates:
                        errors.append("$.adaptive.train_more.gate_execution: must define exactly the four lexical gates")
                    else:
                        controlled = phases.get("controlled_practice", {}) if isinstance(phases, dict) else {}
                        for gate in expected_gates:
                            rule = gate_execution[gate]
                            rule_where = f"$.adaptive.train_more.gate_execution.{gate}"
                            rule_keys = {"base_exercise_ids", "base_pass_minimum_correct", "base_denominator", "reserve_exercise_ids", "reserve_release_trigger", "post_reserve_pass_rule", "terminal_on_pass", "terminal_on_reserve_failure_or_exhaustion", "terminal_on_alarm"}
                            if not isinstance(rule, dict):
                                errors.append(f"{rule_where}: must be an object")
                                continue
                            require_keys(rule, rule_keys, rule_where, errors)
                            expected_base = [item.get("id") for item in controlled.get(gate, [])] if isinstance(controlled, dict) else []
                            if rule.get("base_exercise_ids") != expected_base:
                                errors.append(f"{rule_where}.base_exercise_ids: must equal the frozen controlled-gate order")
                            expected_denominator = len(expected_base)
                            expected_minimum = math.ceil(0.75 * expected_denominator)
                            if rule.get("base_pass_minimum_correct") != expected_minimum or rule.get("base_denominator") != expected_denominator:
                                errors.append(f"{rule_where}: base threshold must equal 75 percent of the frozen gate")
                            expected_reserve_count = expected_denominator if "controller_transition_table" in adaptive else max(2, expected_denominator // 2)
                            if not isinstance(rule.get("reserve_exercise_ids"), list) or len(rule["reserve_exercise_ids"]) != expected_reserve_count or not set(rule["reserve_exercise_ids"]) <= set(reserve_ids or []):
                                errors.append(f"{rule_where}.reserve_exercise_ids: must bind the label-balanced frozen reserve set")
                            expected_trigger = (
                                f"base_correct_below_{expected_minimum}_then_filter_to_incorrect_base_labels"
                                if "runtime_contract" in adaptive
                                else f"base_correct_below_{expected_minimum}"
                            )
                            expected_literals = {
                                "reserve_release_trigger": expected_trigger,
                                "post_reserve_pass_rule": "both_released_reserves_correct" if expected_reserve_count == 2 else "all_released_reserves_correct",
                                "terminal_on_pass": "continue",
                                "terminal_on_reserve_failure_or_exhaustion": "defer_and_revisit",
                                "terminal_on_alarm": "freeze",
                            }
                            for key, value in expected_literals.items():
                                if rule.get(key) != value:
                                    errors.append(f"{rule_where}.{key}: must equal {value}")
                if isinstance(actions, list) and "TRAIN_MORE" not in actions:
                    errors.append("$.adaptive.controller_actions: train_more contract requires TRAIN_MORE")
            train_longer = adaptive.get("train_longer")
            if not isinstance(train_longer, dict):
                errors.append("$.adaptive.train_longer: must be an object")
            else:
                train_longer_keys = {"action", "source", "eligible_item_ids", "ordered_item_ids", "ordering_rule", "max_additional_items", "no_immediate_duplicate", "stop_rule", "exhaustion"}
                lexical_bootstrap = lesson.get("point", {}).get("novelty_kind") == "lexical_set"
                hardened_lexical = lexical_bootstrap and "controller_transition_table" in adaptive
                if hardened_lexical:
                    train_longer_keys |= {"denominator", "minimum_successes", "release_predicate", "terminal_on_success", "terminal_on_failure", "extension_event_ids", "extension_source_map", "identity_rule"}
                if is_l000_v3:
                    train_longer_keys |= {"release_predicate", "maximum_total_uses", "accounting_state", "action_precedence"}
                require_keys(train_longer, train_longer_keys, "$.adaptive.train_longer", errors)
                if train_longer.get("action") != "TRAIN_LONGER":
                    errors.append("$.adaptive.train_longer.action: must equal TRAIN_LONGER")
                expected_train_longer_source = "frozen_base_ids_only" if is_l000_v3 else "frozen_ids_only"
                if train_longer.get("source") != expected_train_longer_source:
                    errors.append(f"$.adaptive.train_longer.source: must equal {expected_train_longer_source}")
                eligible_ids = train_longer.get("eligible_item_ids")
                if not isinstance(eligible_ids, list) or not eligible_ids or len(eligible_ids) != len(set(eligible_ids)) or any(not isinstance(item, str) or not item for item in eligible_ids):
                    errors.append("$.adaptive.train_longer.eligible_item_ids: must be a non-empty unique string array")
                ordered_ids = train_longer.get("ordered_item_ids")
                if not isinstance(ordered_ids, list) or not ordered_ids or any(not isinstance(item, str) or not item for item in ordered_ids):
                    errors.append("$.adaptive.train_longer.ordered_item_ids: must be a non-empty string array")
                else:
                    known_runtime_ids = exercise_ids | set(defined_reserve_ids)
                    if any(item not in known_runtime_ids for item in ordered_ids):
                        errors.append("$.adaptive.train_longer.ordered_item_ids: every ID must resolve to a base or frozen reserve exercise")
                    if any(left == right for left, right in zip(ordered_ids, ordered_ids[1:])):
                        errors.append("$.adaptive.train_longer.ordered_item_ids: immediate duplicates are forbidden")
                    if isinstance(eligible_ids, list) and eligible_ids != ordered_ids:
                        errors.append("$.adaptive.train_longer.eligible_item_ids: must equal the executable ordered_item_ids")
                    if is_l000_v3:
                        expected_base_order = [
                            "aff-01", "recip-02", "neg-02", "who-03",
                            "or-04", "recip-04", "neg-04", "who-01",
                        ]
                        if ordered_ids != expected_base_order:
                            errors.append("$.adaptive.train_longer.ordered_item_ids: L000 must use the frozen base-only order")
                require_string(train_longer.get("ordering_rule"), "$.adaptive.train_longer.ordering_rule", errors)
                if not isinstance(train_longer.get("max_additional_items"), int) or isinstance(train_longer.get("max_additional_items"), bool) or train_longer["max_additional_items"] < 1:
                    errors.append("$.adaptive.train_longer.max_additional_items: must be a positive integer")
                if train_longer.get("no_immediate_duplicate") is not True:
                    errors.append("$.adaptive.train_longer.no_immediate_duplicate: must be true")
                require_string(train_longer.get("stop_rule"), "$.adaptive.train_longer.stop_rule", errors)
                if train_longer.get("exhaustion") != "defer_and_revisit":
                    errors.append("$.adaptive.train_longer.exhaustion: must equal defer_and_revisit")
                if hardened_lexical:
                    if train_longer.get("denominator") != len(ordered_ids or []) or train_longer.get("max_additional_items") != len(ordered_ids or []):
                        errors.append("$.adaptive.train_longer: denominator and maximum must equal the frozen ordered pool")
                    minimum = train_longer.get("minimum_successes")
                    if not isinstance(minimum, int) or isinstance(minimum, bool) or not 1 <= minimum <= len(ordered_ids or []):
                        errors.append("$.adaptive.train_longer.minimum_successes: must be within the frozen denominator")
                    require_string(train_longer.get("release_predicate"), "$.adaptive.train_longer.release_predicate", errors)
                    if train_longer.get("terminal_on_success") != "mark_mixed_remediated_then_continue_to_picture_book" or train_longer.get("terminal_on_failure") != "defer_and_revisit":
                        errors.append("$.adaptive.train_longer: terminal outcomes must explicitly advance remediated success or defer failure")
                    extension_ids = train_longer.get("extension_event_ids")
                    source_map = train_longer.get("extension_source_map")
                    if not isinstance(extension_ids, list) or len(extension_ids) != len(ordered_ids or []) or len(set(extension_ids)) != len(extension_ids):
                        errors.append("$.adaptive.train_longer.extension_event_ids: must be distinct and parallel to ordered_item_ids")
                    elif not isinstance(source_map, dict) or list(source_map) != extension_ids or list(source_map.values()) != ordered_ids:
                        errors.append("$.adaptive.train_longer.extension_source_map: must bind every distinct event to the frozen source order")
                    require_string(train_longer.get("identity_rule"), "$.adaptive.train_longer.identity_rule", errors)
                if is_l000_v3:
                    expected_train_longer_control = {
                        "release_predicate": "first_execution_mixed_terminal_and_mixed_successes_fewer_than_16_and_no_alarm_and_train_longer_count_0_and_remaining_global_turn_budget_at_least_8",
                        "maximum_total_uses": 1,
                        "accounting_state": "increment_train_longer_count_once_on_release_and_add_each_emitted_item_to_teacher_turn_count_and_train_longer_record",
                        "action_precedence": "PRESENT_AGAIN_then_TRAIN_MORE_within_controlled_gates_then_TRAIN_LONGER_after_initial_mixed_then_REPLAY_LESSON_after_first_execution_terminal",
                        "stop_rule": "emit_and_score_all_8_ordered_items_then_success_at_7_of_8_or_defer_and_revisit_below_7_of_8_no_early_stop",
                    }
                    for key, expected in expected_train_longer_control.items():
                        if train_longer.get(key) != expected:
                            errors.append(f"$.adaptive.train_longer.{key}: must equal the frozen deterministic release and precedence contract")
                if isinstance(actions, list) and "TRAIN_LONGER" not in actions:
                    errors.append("$.adaptive.controller_actions: train_longer contract requires TRAIN_LONGER")
            mixed_execution = adaptive.get("mixed_execution")
            if not isinstance(mixed_execution, dict):
                errors.append("$.adaptive.mixed_execution: must be an object")
            else:
                require_keys(mixed_execution, {"ordered_item_ids", "denominator", "minimum_successes", "maximum_items", "stop_rule"}, "$.adaptive.mixed_execution", errors)
                mixed_ids = [
                    item.get("id") for item in phases.get("mixed_practice", [])
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                ] if isinstance(phases, dict) else []
                if mixed_execution.get("ordered_item_ids") != mixed_ids:
                    errors.append("$.adaptive.mixed_execution.ordered_item_ids: must equal phases.mixed_practice order")
                denominator = mixed_execution.get("denominator")
                maximum_items = mixed_execution.get("maximum_items")
                minimum_successes = mixed_execution.get("minimum_successes")
                if denominator != len(mixed_ids) or maximum_items != len(mixed_ids):
                    errors.append("$.adaptive.mixed_execution: denominator and maximum_items must equal the frozen mixed pool length")
                if not isinstance(minimum_successes, int) or isinstance(minimum_successes, bool) or not 1 <= minimum_successes <= len(mixed_ids):
                    errors.append("$.adaptive.mixed_execution.minimum_successes: must be within the frozen mixed denominator")
                if adaptive.get("mixed_practice_cap") != len(mixed_ids):
                    errors.append("$.adaptive.mixed_practice_cap: must equal the frozen mixed pool length")
                require_string(mixed_execution.get("stop_rule"), "$.adaptive.mixed_execution.stop_rule", errors)
            replay = adaptive.get("replay_lesson")
            if not isinstance(replay, dict):
                errors.append("$.adaptive.replay_lesson: must be an object")
            else:
                replay_keys = {"action", "release_rule", "maximum_replays", "stop_rule", "exhaustion"}
                if is_l000_v3:
                    replay_keys |= {"release_predicate", "replay_scope", "record_reset_rule", "outcome_aggregation", "post_replay_disposition"}
                require_keys(replay, replay_keys, "$.adaptive.replay_lesson", errors)
                if replay.get("action") != "REPLAY_LESSON":
                    errors.append("$.adaptive.replay_lesson.action: must equal REPLAY_LESSON")
                for key in ("release_rule", "stop_rule"):
                    require_string(replay.get(key), f"$.adaptive.replay_lesson.{key}", errors)
                if not isinstance(replay.get("maximum_replays"), int) or isinstance(replay.get("maximum_replays"), bool) or replay["maximum_replays"] < 1:
                    errors.append("$.adaptive.replay_lesson.maximum_replays: must be a positive integer")
                if replay.get("exhaustion") != "defer_and_revisit":
                    errors.append("$.adaptive.replay_lesson.exhaustion: must equal defer_and_revisit")
                if is_l000_v3:
                    expected_replay_predicate = f"first_execution_terminal_and_no_alarm_and_overall_mastery_false_and_replay_count_0_and_remaining_global_turn_budget_at_least_{expected_base_turns}"
                    if replay.get("release_predicate") != expected_replay_predicate:
                        errors.append("$.adaptive.replay_lesson.release_predicate: must equal the frozen aggregate-and-budget predicate")
                    if replay.get("release_rule") != "release_only_when_release_predicate_true":
                        errors.append("$.adaptive.replay_lesson.release_rule: must be mechanically bound to release_predicate")
                    if replay.get("replay_scope") != f"frozen_{expected_base_turns}_turn_base_path_only_no_additional_adaptations":
                        errors.append("$.adaptive.replay_lesson.replay_scope: must freeze replay to the fully accounted base path")
                    expected_replay_outcomes = {
                        "record_reset_rule": "retain_first_execution_log_but_reset_all_controlled_gate_mixed_practice_picture_book_comprehension_transfer_and_overall_mastery_counters_for_replay_scoring",
                        "outcome_aggregation": "when_replay_occurs_terminal_decision_uses_replay_records_only_and_first_execution_records_remain_report_context_only",
                        "post_replay_disposition": f"after_replay_base_path_terminates_including_on_turn_{expected_global_cap}_recompute_overall_mastery_from_replay_records_then_FINISH_if_true_else_defer_and_revisit_no_second_replay",
                    }
                    for key, expected in expected_replay_outcomes.items():
                        if replay.get(key) != expected:
                            errors.append(f"$.adaptive.replay_lesson.{key}: must equal the frozen replay reset and outcome contract")
                if isinstance(actions, list) and "REPLAY_LESSON" not in actions:
                    errors.append("$.adaptive.controller_actions: replay_lesson contract requires REPLAY_LESSON")
            finish = adaptive.get("finish")
            if not isinstance(finish, dict):
                errors.append("$.adaptive.finish: must be an object")
            else:
                require_keys(finish, {"action", "eligibility", "behavior"}, "$.adaptive.finish", errors)
                if finish.get("action") != "FINISH":
                    errors.append("$.adaptive.finish.action: must equal FINISH")
                require_string(finish.get("eligibility"), "$.adaptive.finish.eligibility", errors)
                if finish.get("behavior") != "close_lesson_write_report_no_further_prompts":
                    errors.append("$.adaptive.finish.behavior: must close, report, and emit no further prompts")
                if isinstance(actions, list) and "FINISH" not in actions:
                    errors.append("$.adaptive.controller_actions: finish contract requires FINISH")
            alarm = adaptive.get("alarm")
            if not isinstance(alarm, dict):
                errors.append("$.adaptive.alarm: must be an object")
            else:
                require_keys(alarm, {"action", "triggers", "behavior"}, "$.adaptive.alarm", errors)
                expected_alarm_action = "ALARM" if "controller_transition_table" in adaptive else "ALARM_FREEZE"
                if alarm.get("action") != expected_alarm_action:
                    errors.append(f"$.adaptive.alarm.action: must equal {expected_alarm_action}")
                triggers = alarm.get("triggers")
                if not isinstance(triggers, list) or not triggers or any(not isinstance(item, str) or not item for item in triggers):
                    errors.append("$.adaptive.alarm.triggers: must be a non-empty string array")
                if alarm.get("behavior") != "freeze_immediately_preserve_log_no_further_teacher_turns":
                    errors.append("$.adaptive.alarm.behavior: must freeze immediately and preserve the log")
            if "controller_transition_table" in adaptive:
                transition_table = adaptive.get("controller_transition_table")
                if not isinstance(transition_table, dict) or not transition_table:
                    errors.append("$.adaptive.controller_transition_table: must be a non-empty deterministic transition map")
                elif transition_table.get("frozen+any_action") != "forbidden" or transition_table.get("any_non_frozen_state+ALARM") != "frozen_no_further_teacher_turns_preserve_log":
                    errors.append("$.adaptive.controller_transition_table: must make ALARM terminal and the frozen state absorbing")

    rehearsal = lesson.get("rehearsal")
    if not isinstance(rehearsal, dict):
        errors.append("$.rehearsal: must be an object")
    else:
        keys = {"pattern_id", "decision", "reason", "qualification_record_path", "qualification_record_sha256", "evidence_artifact_ids"}
        require_keys(rehearsal, keys, "$.rehearsal", errors)
        for key in ("pattern_id", "reason"):
            require_string(rehearsal.get(key), f"$.rehearsal.{key}", errors)
        decision = rehearsal.get("decision")
        if decision not in REHEARSAL_READY | {"required_pending"}:
            errors.append("$.rehearsal.decision: invalid decision")
        evidence = rehearsal.get("evidence_artifact_ids")
        if not isinstance(evidence, list) or any(not isinstance(item, str) or not item for item in evidence):
            errors.append("$.rehearsal.evidence_artifact_ids: must be an array of strings")
        if stage == "freeze":
            if decision not in REHEARSAL_READY:
                errors.append("$.rehearsal.decision: rehearsal or qualification remains pending")
            for key in ("qualification_record_path", "qualification_record_sha256"):
                require_string(rehearsal.get(key), f"$.rehearsal.{key}", errors)
            raw_path, expected = rehearsal.get("qualification_record_path"), rehearsal.get("qualification_record_sha256")
            if not isinstance(expected, str) or SHA256.fullmatch(expected) is None:
                errors.append("$.rehearsal.qualification_record_sha256: must be lowercase SHA-256")
            if isinstance(raw_path, str):
                try:
                    path = resolve_repo_path(raw_path)
                    if not path.is_file():
                        errors.append("$.rehearsal.qualification_record_path: file does not exist")
                    elif isinstance(expected, str) and digest_path(path) != expected:
                        errors.append("$.rehearsal.qualification_record_sha256: does not match file")
                except ValueError as exc:
                    errors.append(f"$.rehearsal.qualification_record_path: {exc}")

    for where, text in walk_strings(lesson):
        if "TODO" in text or "<replace" in text:
            errors.append(f"{where}: unresolved template placeholder")
        if re.search(r"\betc\.?\b", text, flags=re.IGNORECASE):
            errors.append(f"{where}: open-ended 'etc.' is forbidden; use a closed list")
    return errors


def render_markdown(lesson: dict[str, Any], lesson_sha: str) -> str:
    controlled = lesson["phases"]["controlled_practice"]
    counts = ", ".join(f"{key}={len(controlled[key])}" for key in controlled_phase_keys(lesson))
    lines = [
        f"# {lesson['lesson_id']}",
        "",
        f"- Variant: `{lesson['variant']}`",
        f"- Target language: `{lesson['target_language']}`",
        f"- Topic: {lesson['topic']}",
        f"- Point: `{lesson['point']['id']}` — {lesson['point']['claim']}",
        f"- Practice: {counts}; mixed={len(lesson['phases']['mixed_practice'])}; transfer={len(lesson['phases']['transfer'])}",
        f"- Assets: {len(lesson['assets'])}",
        f"- Rehearsal decision: `{lesson['rehearsal']['decision']}`",
        f"- Lesson SHA-256: `{lesson_sha}`",
        "",
        "This projection is for review. `lesson.json` is the immutable machine artifact.",
        "",
    ]
    return "\n".join(lines)


def compile_lesson(input_path: Path, output_dir: Path) -> None:
    lesson = load_json(input_path)
    errors = validate_lesson(lesson, "freeze")
    if errors:
        raise ValueError("lesson cannot freeze:\n" + "\n".join(f"- {item}" for item in errors))
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    frozen = json.loads(json.dumps(lesson))
    frozen["status"] = "frozen"
    lesson_bytes = canonical_bytes(frozen)
    lesson_sha = digest_bytes(lesson_bytes)
    source_hashes = {item["role"]: item["sha256"] for item in frozen["source_bindings"]}
    asset_hashes = {item["id"]: item["sha256"] for item in frozen["assets"]}
    manifest = {
        "schema_version": "ninereeds_compiled_lesson_manifest_v1",
        "compiler_version": COMPILER_VERSION,
        "lesson_id": frozen["lesson_id"],
        "variant": frozen["variant"],
        "lesson_sha256": lesson_sha,
        "source_hashes": source_hashes,
        "asset_hashes": asset_hashes,
        "qualification_record_sha256": frozen["rehearsal"]["qualification_record_sha256"],
    }
    if frozen.get("schema_version") == "ninereeds_lesson_contract_v3":
        manifest["conducted_sequence"] = {
            "entry_id": frozen["assembly"]["conducted_entry_id"],
            "sequence_number": frozen["assembly"]["conducted_sequence_number"],
            "selection_packet_sha256": frozen["assembly"]["selection_packet_sha256"],
        }
        manifest["authoring_receipt_sha256"] = frozen["authoring"]["receipt_sha256"]
        manifest["independent_review_receipt_sha256"] = frozen["independent_review"]["receipt_sha256"]
        manifest["visual_operations"] = [
            {
                "id": item["id"],
                "type": item["type"],
                "output_asset_id": item["output_asset_id"],
                "receipt_sha256": item["receipt_sha256"],
                "verification_receipt_sha256": item["verification"]["receipt_sha256"],
                "crop_xywh": item["crop_xywh"],
                "prompt_sha256": digest_bytes(item["prompt"].encode("utf-8")) if item["prompt"] else None,
            }
            for item in frozen["visual_plan"]["operations"]
        ]
    (output_dir / "lesson.json").write_bytes(lesson_bytes)
    (output_dir / "manifest.json").write_bytes(canonical_bytes(manifest))
    (output_dir / "lesson.md").write_text(render_markdown(frozen, lesson_sha), encoding="utf-8")


def promote_rehearsed_lesson(
    input_path: Path,
    rehearsal_manifest_path: Path,
    canonical_report_path: Path,
    qualification_record_path: Path,
    output_path: Path,
    visual_review_receipt_path: Path | None = None,
) -> None:
    """Create a freeze-ready lesson without mutating the hash-bound rehearsed source."""
    if output_path.exists():
        raise ValueError(f"refusing to overwrite promoted lesson: {output_path}")
    lesson = load_json(input_path)
    lesson_sha = digest_path(input_path)
    manifest = load_json(rehearsal_manifest_path)
    report = load_json(canonical_report_path)
    qualification = load_json(qualification_record_path)
    if manifest.get("schema_version") != "ninereeds_lesson_rehearsal_manifest_v1":
        raise ValueError("rehearsal manifest schema is invalid")
    if manifest.get("terminal_status") != "passed" or manifest.get("lesson_sha256") != lesson_sha:
        raise ValueError("promotion requires a passing rehearsal manifest for the exact lesson bytes")
    if report.get("schema_version") != "ninereeds_canonical_lesson_outcome_report_v1":
        raise ValueError("canonical report schema is invalid")
    report_lesson = report.get("lesson")
    if (
        report.get("outcome") != "passed"
        or not isinstance(report_lesson, dict)
        or report_lesson.get("sha256") != lesson_sha
        or report.get("run_id") != manifest.get("rehearsal_id")
    ):
        raise ValueError("canonical report must pass and bind the exact lesson and rehearsal")
    if qualification.get("schema_version") != "ninereeds_instructor_qualification_state_v1":
        raise ValueError("qualification record schema is invalid")
    try:
        qualification_relative = str(qualification_record_path.resolve().relative_to(REPO_ROOT))
    except ValueError as exc:
        raise ValueError("qualification record must live inside the repository") from exc

    promoted = json.loads(json.dumps(lesson))
    if promoted.get("schema_version") == "ninereeds_lesson_contract_v3":
        bindings = promoted.get("source_bindings", [])
        qualification_binding = next(
            (item for item in bindings if isinstance(item, dict) and item.get("role") == "instructor_qualification_state"),
            None,
        )
        if qualification_binding is not None:
            qualification_binding["path"] = qualification_relative
            qualification_binding["sha256"] = digest_path(qualification_record_path)
        if visual_review_receipt_path is None:
            raise ValueError("v3 promotion requires a visual review receipt")
        try:
            visual_review_relative = str(visual_review_receipt_path.resolve().relative_to(REPO_ROOT))
        except ValueError as exc:
            raise ValueError("visual review receipt must live inside the repository") from exc
        visual_review = load_json(visual_review_receipt_path)
        if (
            visual_review.get("schema_version") != "ninereeds_pixel_review_receipt_v1"
            or visual_review.get("lesson_id") != promoted.get("assembly", {}).get("conducted_entry_id")
            or visual_review.get("decision") != "accepted"
        ):
            raise ValueError("visual review receipt is not an accepted receipt for this lesson")
        visual_review_sha = digest_path(visual_review_receipt_path)
        bindings = [item for item in bindings if not (isinstance(item, dict) and item.get("role") == "pixel_review")]
        bindings.append({"role": "pixel_review", "path": visual_review_relative, "sha256": visual_review_sha})
        promoted["source_bindings"] = bindings
        review_id = f"pixel-review-sha256:{visual_review_sha}"
        for asset in promoted.get("assets", []):
            if isinstance(asset, dict):
                asset["review_receipt_id"] = review_id
        creation_bindings = {
            item.get("role"): item
            for item in bindings
            if isinstance(item, dict) and item.get("role") in {"image_bank_selection", "picture_book_imagegen"}
        }
        for operation in promoted.get("visual_plan", {}).get("operations", []):
            if not isinstance(operation, dict):
                continue
            output_id = operation.get("output_asset_id")
            asset = next((item for item in promoted.get("assets", []) if item.get("id") == output_id), None)
            role = "picture_book_imagegen" if isinstance(asset, dict) and "/picture_book_" in asset.get("path", "") else "image_bank_selection"
            creation = creation_bindings.get(role)
            if not isinstance(creation, dict):
                raise ValueError(f"missing {role} source binding for visual operation {operation.get('id')}")
            operation["receipt_path"] = creation["path"]
            operation["receipt_sha256"] = creation["sha256"]
            verification = operation.get("verification")
            if isinstance(verification, dict):
                verification["receipt_path"] = visual_review_relative
                verification["receipt_sha256"] = visual_review_sha
    promoted["rehearsal"] = {
        "pattern_id": lesson["rehearsal"]["pattern_id"],
        "decision": "full_rehearsal_passed",
        "reason": (
            f"Static review and full rehearsal {manifest['rehearsal_id']} passed; "
            f"canonical outcome {report['report_id']} is independently reviewed."
        ),
        "qualification_record_path": qualification_relative,
        "qualification_record_sha256": digest_path(qualification_record_path),
        "evidence_artifact_ids": [
            f"rehearsal-manifest-sha256:{digest_path(rehearsal_manifest_path)}",
            f"canonical-report:{report['report_id']}",
        ],
    }
    errors = validate_lesson(promoted, "freeze")
    if errors:
        raise ValueError("promoted lesson cannot freeze:\n" + "\n".join(f"- {item}" for item in errors))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_bytes(promoted))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--input", type=Path, required=True)
    validate_parser.add_argument("--stage", choices=("draft", "freeze"), default="draft")
    select_parser = subparsers.add_parser("select-next")
    select_parser.add_argument("--curriculum", type=Path, required=True)
    select_parser.add_argument("--rehearsal-layer", type=Path, required=True)
    select_parser.add_argument("--cursor", type=Path, required=True)
    select_parser.add_argument("--known-closure", type=Path, required=True)
    select_parser.add_argument("--output", type=Path, required=True)
    prepare_parser = subparsers.add_parser("select-next-preparation")
    prepare_parser.add_argument("--curriculum", type=Path, required=True)
    prepare_parser.add_argument("--rehearsal-layer", type=Path, required=True)
    prepare_parser.add_argument("--preparation-cursor", type=Path, required=True)
    prepare_parser.add_argument("--learner-cursor", type=Path, required=True)
    prepare_parser.add_argument("--known-closure", type=Path, required=True)
    prepare_parser.add_argument("--output", type=Path, required=True)
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("--input", type=Path, required=True)
    compile_parser.add_argument("--output-dir", type=Path, required=True)
    promote_parser = subparsers.add_parser("promote-rehearsed")
    promote_parser.add_argument("--input", type=Path, required=True)
    promote_parser.add_argument("--rehearsal-manifest", type=Path, required=True)
    promote_parser.add_argument("--canonical-report", type=Path, required=True)
    promote_parser.add_argument("--qualification-record", type=Path, required=True)
    promote_parser.add_argument("--visual-review-receipt", type=Path)
    promote_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "select-next":
            selected = select_next(
                curriculum_path=args.curriculum,
                rehearsal_path=args.rehearsal_layer,
                cursor_path=args.cursor,
                closure_path=args.known_closure,
            )
            if args.output.exists():
                raise ValueError(f"refusing to overwrite selection packet: {args.output}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(selection_canonical_bytes(selected))
            print(
                f"selected {selected['sequence']['entry_id']} at conducted position "
                f"{selected['sequence']['sequence_number']}/666 into {args.output}"
            )
            return 0
        if args.command == "select-next-preparation":
            selected = select_next_preparation(
                curriculum_path=args.curriculum,
                rehearsal_path=args.rehearsal_layer,
                preparation_cursor_path=args.preparation_cursor,
                learner_cursor_path=args.learner_cursor,
                closure_path=args.known_closure,
            )
            if args.output.exists():
                raise ValueError(f"refusing to overwrite selection packet: {args.output}")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(selection_canonical_bytes(selected))
            print(
                f"selected {selected['sequence']['entry_id']} for preparation at position "
                f"{selected['sequence']['sequence_number']}/666 into {args.output}"
            )
            return 0
        if args.command == "validate":
            lesson = load_json(args.input)
            errors = validate_lesson(lesson, args.stage)
            if errors:
                print("validation failed", file=sys.stderr)
                for error in errors:
                    print(f"- {error}", file=sys.stderr)
                return 1
            print(f"valid {args.stage} lesson: {lesson['lesson_id']}")
            return 0
        if args.command == "promote-rehearsed":
            promote_rehearsed_lesson(
                input_path=args.input,
                rehearsal_manifest_path=args.rehearsal_manifest,
                canonical_report_path=args.canonical_report,
                qualification_record_path=args.qualification_record,
                output_path=args.output,
                visual_review_receipt_path=args.visual_review_receipt,
            )
            print(f"promoted rehearsed lesson into {args.output}")
            return 0
        compile_lesson(args.input, args.output_dir)
        print(f"compiled lesson into {args.output_dir}")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
