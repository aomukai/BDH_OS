#!/usr/bin/env python3
"""Validate and freeze a Ninereeds lesson contract without dispatching work."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


COMPILER_VERSION = "ninereeds_lesson_compiler_v2"
REPO_ROOT = Path(__file__).resolve().parents[4]
LESSON_ID = re.compile(r"^lesson-[a-z0-9][a-z0-9-]*-v[0-9]+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PHASE_KEYS = ("affirmative", "negative", "W_question", "OR_question")
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


def validate_exercise(exercise: Any, where: str, errors: list[str]) -> set[str]:
    if not isinstance(exercise, dict):
        errors.append(f"{where}: must be an object")
        return set()
    keys = {"id", "teacher_text", "expected_answers", "invariants", "asset_ids", "target_language_required"}
    require_keys(exercise, keys, where, errors)
    for key in ("id", "teacher_text"):
        require_string(exercise.get(key), f"{where}.{key}", errors)
    for key in ("expected_answers", "invariants", "asset_ids"):
        items = exercise.get(key)
        if not isinstance(items, list):
            errors.append(f"{where}.{key}: must be an array")
        elif key != "asset_ids" and not items:
            errors.append(f"{where}.{key}: must not be empty")
        elif any(not isinstance(item, str) or not item for item in items):
            errors.append(f"{where}.{key}: items must be non-empty strings")
    if not isinstance(exercise.get("target_language_required"), bool):
        errors.append(f"{where}.target_language_required: must be boolean")
    return set(exercise.get("asset_ids", [])) if isinstance(exercise.get("asset_ids"), list) else set()


def validate_lesson(lesson: dict[str, Any], stage: str) -> list[str]:
    errors: list[str] = []
    top_keys = {
        "schema_version", "lesson_id", "status", "variant", "target_language", "topic",
        "point", "selection", "prerequisites", "source_bindings", "world",
        "language_boundary", "phases", "picture_book", "assets", "adaptive", "rehearsal",
    }
    require_keys(lesson, top_keys, "$", errors)
    if lesson.get("schema_version") != "ninereeds_lesson_contract_v2":
        errors.append("$.schema_version: must equal ninereeds_lesson_contract_v2")
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
    used_asset_ids: set[str] = set()
    exercise_ids: set[str] = set()
    if not isinstance(phases, dict):
        errors.append("$.phases: must be an object")
    else:
        require_keys(phases, {"presentation", "controlled_practice", "mixed_practice", "transfer"}, "$.phases", errors)
        pools: list[tuple[str, Any]] = [("presentation", phases.get("presentation"))]
        controlled = phases.get("controlled_practice")
        if not isinstance(controlled, dict):
            errors.append("$.phases.controlled_practice: must be an object")
        else:
            require_keys(controlled, set(PHASE_KEYS), "$.phases.controlled_practice", errors)
            pools.extend((f"controlled_practice.{key}", controlled.get(key)) for key in PHASE_KEYS)
        pools.extend((("mixed_practice", phases.get("mixed_practice")), ("transfer", phases.get("transfer"))))
        for pool_name, pool in pools:
            where = f"$.phases.{pool_name}"
            if not isinstance(pool, list):
                errors.append(f"{where}: must be an array")
                continue
            if pool_name != "transfer" and not pool:
                errors.append(f"{where}: must not be empty")
            for index, exercise in enumerate(pool):
                used_asset_ids |= validate_exercise(exercise, f"{where}[{index}]", errors)
                if isinstance(exercise, dict) and isinstance(exercise.get("id"), str):
                    if exercise["id"] in exercise_ids:
                        errors.append(f"{where}[{index}].id: duplicate exercise id {exercise['id']}")
                    exercise_ids.add(exercise["id"])

    picture_book = lesson.get("picture_book")
    if lesson.get("variant") == "dialogue_only":
        if picture_book is not None:
            errors.append("$.picture_book: must be null for dialogue_only")
    elif not isinstance(picture_book, dict):
        errors.append("$.picture_book: must be an object for picture_book")
    else:
        require_keys(picture_book, {"instructional_kernel", "pages", "comprehension"}, "$.picture_book", errors)
        require_string(picture_book.get("instructional_kernel"), "$.picture_book.instructional_kernel", errors)
        pages = picture_book.get("pages")
        if not isinstance(pages, list) or not pages:
            errors.append("$.picture_book.pages: must be a non-empty array")
        else:
            page_ids: set[str] = set()
            for index, page in enumerate(pages):
                where = f"$.picture_book.pages[{index}]"
                if not isinstance(page, dict):
                    errors.append(f"{where}: must be an object")
                    continue
                require_keys(page, {"id", "asset_id", "caption", "scene_facts"}, where, errors)
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
        comprehension = picture_book.get("comprehension")
        if not isinstance(comprehension, list) or not comprehension:
            errors.append("$.picture_book.comprehension: must be a non-empty array")
        else:
            for index, exercise in enumerate(comprehension):
                used_asset_ids |= validate_exercise(exercise, f"$.picture_book.comprehension[{index}]", errors)

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
            if asset.get("source") not in {"registry", "external", "flux_edit", "flux_generation", "openai_imagegen", "deterministic_crop"}:
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
            if asset.get("source") == "openai_imagegen":
                if "flux_generation" not in asset.get("attempted_sources", []) and "flux_edit" not in asset.get("attempted_sources", []):
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

    adaptive = lesson.get("adaptive")
    if not isinstance(adaptive, dict):
        errors.append("$.adaptive: must be an object")
    else:
        keys = {
            "presentation_replay_after_failures", "maximum_teacher_turns",
            "mixed_practice_cap", "completion_fraction", "controller_actions",
            "marker_intervention",
        }
        require_keys(adaptive, keys, "$.adaptive", errors)
        for key in ("presentation_replay_after_failures", "maximum_teacher_turns", "mixed_practice_cap"):
            if not isinstance(adaptive.get(key), int) or adaptive[key] < 1:
                errors.append(f"$.adaptive.{key}: must be a positive integer")
        fraction = adaptive.get("completion_fraction")
        if not isinstance(fraction, (int, float)) or isinstance(fraction, bool) or not 0 < fraction <= 1:
            errors.append("$.adaptive.completion_fraction: must be greater than 0 and at most 1")
        allowed_actions = {
            "CONTINUE", "PRESENT_AGAIN", "USE_MARKERS", "TRAIN_MORE",
            "TRAIN_LONGER", "REPLAY_LESSON", "BACKTRACK", "FINISH",
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
    counts = ", ".join(f"{key}={len(controlled[key])}" for key in PHASE_KEYS)
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
    (output_dir / "lesson.json").write_bytes(lesson_bytes)
    (output_dir / "manifest.json").write_bytes(canonical_bytes(manifest))
    (output_dir / "lesson.md").write_text(render_markdown(frozen, lesson_sha), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--input", type=Path, required=True)
    validate_parser.add_argument("--stage", choices=("draft", "freeze"), default="draft")
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("--input", type=Path, required=True)
    compile_parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
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
        compile_lesson(args.input, args.output_dir)
        print(f"compiled lesson into {args.output_dir}")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
