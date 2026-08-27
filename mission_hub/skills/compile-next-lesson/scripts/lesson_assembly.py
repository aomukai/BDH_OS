#!/usr/bin/env python3
"""Deterministic handhold-mode selection for the frozen v6 conducted sequence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SELECTION_VERSION = "ninereeds_lesson_selection_v1"
CURSOR_VERSION = "ninereeds_lesson_cursor_v1"
PREPARATION_CURSOR_VERSION = "ninereeds_lesson_preparation_cursor_v1"
CLOSURE_VERSION = "ninereeds_known_closure_v1"
ACQUISITION_COUNT = 396
REHEARSAL_COUNT = 270
CONDUCTED_COUNT = 666
ELIGIBLE_STATES = {
    "controlled_practice_completed",
    "mixed_practice_completed",
    "transferred",
    "retained",
    "stable",
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def digest_path(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected one JSON object")
    return value


def _require_exact_keys(value: dict[str, Any], keys: set[str], where: str) -> None:
    missing = sorted(keys - set(value))
    extra = sorted(set(value) - keys)
    if missing or extra:
        detail = [*(f"missing {item}" for item in missing), *(f"unknown {item}" for item in extra)]
        raise ValueError(f"{where}: " + "; ".join(detail))


def build_conducted_sequence(curriculum: dict[str, Any], rehearsal: dict[str, Any]) -> list[dict[str, Any]]:
    lessons = curriculum.get("lessons")
    scheduled = rehearsal.get("scheduled_rehearsals")
    if not isinstance(lessons, list) or len(lessons) != ACQUISITION_COUNT:
        raise ValueError(f"curriculum must contain exactly {ACQUISITION_COUNT} acquisition lessons")
    if not isinstance(scheduled, list) or len(scheduled) != REHEARSAL_COUNT:
        raise ValueError(f"rehearsal layer must contain exactly {REHEARSAL_COUNT} scheduled entries")

    sequence: list[dict[str, Any]] = []
    for index, lesson in enumerate(lessons):
        expected_id = f"L{index:03d}"
        if not isinstance(lesson, dict) or lesson.get("lesson_id") != expected_id:
            raise ValueError(f"acquisition sequence position {index + 1} must be {expected_id}")
        sequence.append({
            "sequence_number": index + 1,
            "entry_id": expected_id,
            "entry_kind": "acquisition",
            "entry": lesson,
        })

    for index, item in enumerate(scheduled, start=1):
        expected_id = f"R{index:03d}"
        expected_sequence = ACQUISITION_COUNT + index
        if not isinstance(item, dict) or item.get("rehearsal_id") != expected_id:
            raise ValueError(f"rehearsal sequence position {expected_sequence} must be {expected_id}")
        if item.get("conducted_sequence_number") != expected_sequence:
            raise ValueError(f"{expected_id}: conducted_sequence_number must be {expected_sequence}")
        sequence.append({
            "sequence_number": expected_sequence,
            "entry_id": expected_id,
            "entry_kind": "rehearsal",
            "entry": item,
        })

    if len(sequence) != CONDUCTED_COUNT:
        raise ValueError(f"conducted sequence must contain exactly {CONDUCTED_COUNT} entries")
    return sequence


def _completion_records(closure: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = closure.get("lesson_evidence")
    if not isinstance(records, list):
        raise ValueError("known closure lesson_evidence must be an array")
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            raise ValueError(f"known closure lesson_evidence[{index}] must be an object")
        _require_exact_keys(item, {"lesson_id", "state", "evidence_artifact_ids"}, f"lesson_evidence[{index}]")
        lesson_id = item.get("lesson_id")
        evidence = item.get("evidence_artifact_ids")
        if not isinstance(lesson_id, str) or not lesson_id:
            raise ValueError(f"lesson_evidence[{index}].lesson_id must be a non-empty string")
        if lesson_id in result:
            raise ValueError(f"duplicate lesson evidence: {lesson_id}")
        if item.get("state") not in ELIGIBLE_STATES:
            raise ValueError(f"{lesson_id}: state is not prerequisite-eligible")
        if not isinstance(evidence, list) or not evidence or any(not isinstance(v, str) or not v for v in evidence):
            raise ValueError(f"{lesson_id}: evidence_artifact_ids must be a non-empty string array")
        result[lesson_id] = item
    return result


def select_next(
    *,
    curriculum_path: Path,
    rehearsal_path: Path,
    cursor_path: Path,
    closure_path: Path,
) -> dict[str, Any]:
    curriculum = load_object(curriculum_path)
    rehearsal = load_object(rehearsal_path)
    cursor = load_object(cursor_path)
    closure = load_object(closure_path)
    sequence = build_conducted_sequence(curriculum, rehearsal)

    if cursor.get("schema_version") != CURSOR_VERSION:
        raise ValueError(f"cursor schema_version must equal {CURSOR_VERSION}")
    _require_exact_keys(cursor, {
        "schema_version", "mode", "curriculum_sha256", "rehearsal_layer_sha256",
        "completed_entry_ids", "next_sequence_number", "learner_state_artifact_id",
        "learner_state_path", "learner_state_sha256", "known_closure_artifact_id",
        "known_closure_path", "known_closure_sha256",
    }, "cursor")
    if cursor.get("mode") != "handhold":
        raise ValueError("cursor.mode must be handhold until the autonomous pipeline is commissioned")
    expected_hashes = {
        "curriculum_sha256": digest_path(curriculum_path),
        "rehearsal_layer_sha256": digest_path(rehearsal_path),
        "known_closure_sha256": digest_path(closure_path),
    }
    for key, expected in expected_hashes.items():
        if cursor.get(key) != expected:
            raise ValueError(f"cursor.{key} does not match the selected bytes")
    closure_bound_path = Path(cursor.get("known_closure_path", ""))
    if not closure_bound_path.is_absolute():
        closure_bound_path = cursor_path.parent / closure_bound_path
    if closure_bound_path.resolve() != closure_path.resolve():
        raise ValueError("cursor known-closure path does not identify the selected closure file")
    learner_path = Path(cursor.get("learner_state_path", ""))
    if not learner_path.is_absolute():
        learner_path = cursor_path.parent / learner_path
    if not learner_path.is_file() or cursor.get("learner_state_sha256") != digest_path(learner_path):
        raise ValueError("cursor learner-state path/hash does not resolve")

    completed = cursor.get("completed_entry_ids")
    next_number = cursor.get("next_sequence_number")
    if not isinstance(completed, list) or any(not isinstance(item, str) for item in completed):
        raise ValueError("cursor.completed_entry_ids must be a string array")
    if not isinstance(next_number, int) or isinstance(next_number, bool) or not 1 <= next_number <= CONDUCTED_COUNT + 1:
        raise ValueError(f"cursor.next_sequence_number must be in 1..{CONDUCTED_COUNT + 1}")
    expected_prefix = [item["entry_id"] for item in sequence[: next_number - 1]]
    if completed != expected_prefix:
        raise ValueError("cursor completion history is not the exact frozen conducted-sequence prefix")
    if next_number == CONDUCTED_COUNT + 1:
        raise ValueError("the frozen 666-entry conducted sequence is complete")

    if closure.get("schema_version") != CLOSURE_VERSION:
        raise ValueError(f"known closure schema_version must equal {CLOSURE_VERSION}")
    _require_exact_keys(closure, {"schema_version", "learner_state_artifact_id", "lesson_evidence", "eligible_vocabulary"}, "known closure")
    if closure.get("learner_state_artifact_id") != cursor.get("learner_state_artifact_id"):
        raise ValueError("known closure and cursor do not bind the same learner-state artifact")
    evidence = _completion_records(closure)

    selected = sequence[next_number - 1]
    entry = selected["entry"]
    prerequisite_ids = (
        entry.get("prerequisite_lessons", [])
        if selected["entry_kind"] == "acquisition"
        else [*entry.get("prerequisite_acquisition_lessons", []), *entry.get("prerequisite_rehearsal_lessons", [])]
    )
    missing = [item for item in prerequisite_ids if item not in completed or item not in evidence]
    if missing:
        raise ValueError("next entry has unresolved prerequisite evidence: " + ", ".join(missing))

    vocabulary = closure.get("eligible_vocabulary")
    if not isinstance(vocabulary, list):
        raise ValueError("known closure eligible_vocabulary must be an array")
    eligible_vocabulary: list[dict[str, Any]] = []
    seen_vocabulary: set[str] = set()
    for index, item in enumerate(vocabulary):
        if not isinstance(item, dict):
            raise ValueError(f"eligible_vocabulary[{index}] must be an object")
        _require_exact_keys(item, {"id", "surface", "evidence_lesson_ids", "evidence_artifact_ids"}, f"eligible_vocabulary[{index}]")
        identifier = item.get("id")
        lesson_ids = item.get("evidence_lesson_ids")
        artifacts = item.get("evidence_artifact_ids")
        if not isinstance(identifier, str) or not identifier or identifier in seen_vocabulary:
            raise ValueError(f"eligible_vocabulary[{index}].id must be non-empty and unique")
        seen_vocabulary.add(identifier)
        if not isinstance(item.get("surface"), str) or not item["surface"]:
            raise ValueError(f"eligible_vocabulary[{index}].surface must be non-empty")
        if not isinstance(lesson_ids, list) or not lesson_ids or any(v not in evidence or v not in completed for v in lesson_ids):
            raise ValueError(f"eligible_vocabulary[{index}] cites unavailable lesson evidence")
        if not isinstance(artifacts, list) or not artifacts or any(not isinstance(v, str) or not v for v in artifacts):
            raise ValueError(f"eligible_vocabulary[{index}].evidence_artifact_ids must be non-empty")
        eligible_vocabulary.append(item)

    return {
        "schema_version": SELECTION_VERSION,
        "mode": "handhold",
        "sequence": {
            "planned_total": CONDUCTED_COUNT,
            "sequence_number": selected["sequence_number"],
            "entry_id": selected["entry_id"],
            "entry_kind": selected["entry_kind"],
            "curriculum_sha256": expected_hashes["curriculum_sha256"],
            "rehearsal_layer_sha256": expected_hashes["rehearsal_layer_sha256"],
            "cursor_sha256": digest_path(cursor_path),
        },
        "learner_evidence": {
            "learner_state_artifact_id": cursor["learner_state_artifact_id"],
            "learner_state_sha256": cursor["learner_state_sha256"],
            "known_closure_artifact_id": cursor["known_closure_artifact_id"],
            "known_closure_sha256": expected_hashes["known_closure_sha256"],
        },
        "selected_entry": entry,
        "prerequisite_receipts": [evidence[item] for item in prerequisite_ids],
        "eligible_vocabulary": eligible_vocabulary,
        "authoring": {
            "actor": "luna",
            "authority": "Create the bounded complete lesson script inside the selected Point, prerequisites, chronology, and visual claims.",
            "forbidden": [
                "change the conducted entry or principal Point",
                "treat incidental exposure as prerequisite evidence",
                "approve pixels or waive a failed visual claim",
                "dispatch training",
            ],
        },
        "independent_review": {
            "required": True,
            "reviewer_role": "sol",
            "graduation_policy": "undecided",
            "handhold_rule": "Every compiled lesson requires explicit Sol review until an evidence-bearing graduation policy is approved.",
        },
    }


def select_next_preparation(
    *,
    curriculum_path: Path,
    rehearsal_path: Path,
    preparation_cursor_path: Path,
    learner_cursor_path: Path,
    closure_path: Path,
) -> dict[str, Any]:
    """Select the next artifact to build without advancing or falsifying learner state."""
    curriculum = load_object(curriculum_path)
    rehearsal = load_object(rehearsal_path)
    preparation = load_object(preparation_cursor_path)
    sequence = build_conducted_sequence(curriculum, rehearsal)
    _require_exact_keys(preparation, {
        "schema_version", "mode", "curriculum_sha256", "rehearsal_layer_sha256",
        "prepared_entries", "next_sequence_number", "learner_cursor_path",
        "learner_cursor_sha256", "known_closure_path", "known_closure_sha256",
    }, "preparation cursor")
    if preparation.get("schema_version") != PREPARATION_CURSOR_VERSION:
        raise ValueError(f"preparation cursor schema_version must equal {PREPARATION_CURSOR_VERSION}")
    if preparation.get("mode") != "handhold_preparation":
        raise ValueError("preparation cursor.mode must equal handhold_preparation")
    expected_hashes = {
        "curriculum_sha256": digest_path(curriculum_path),
        "rehearsal_layer_sha256": digest_path(rehearsal_path),
        "learner_cursor_sha256": digest_path(learner_cursor_path),
        "known_closure_sha256": digest_path(closure_path),
    }
    for key, expected in expected_hashes.items():
        if preparation.get(key) != expected:
            raise ValueError(f"preparation cursor.{key} does not match the selected bytes")

    for key, selected_path in (
        ("learner_cursor_path", learner_cursor_path),
        ("known_closure_path", closure_path),
    ):
        raw = Path(preparation.get(key, ""))
        resolved = raw if raw.is_absolute() else preparation_cursor_path.parent / raw
        if resolved.resolve() != selected_path.resolve():
            raise ValueError(f"preparation cursor.{key} does not identify the selected file")

    # Reuse the strict conducted-cursor validator. Its selected entry is intentionally ignored:
    # preparation may run ahead, but the learner evidence remains where conduct left it.
    learner_selection = select_next(
        curriculum_path=curriculum_path,
        rehearsal_path=rehearsal_path,
        cursor_path=learner_cursor_path,
        closure_path=closure_path,
    )
    prepared = preparation.get("prepared_entries")
    next_number = preparation.get("next_sequence_number")
    if not isinstance(prepared, list) or any(not isinstance(item, dict) for item in prepared):
        raise ValueError("preparation cursor.prepared_entries must be an object array")
    if not isinstance(next_number, int) or isinstance(next_number, bool) or not 1 <= next_number <= CONDUCTED_COUNT + 1:
        raise ValueError(f"preparation cursor.next_sequence_number must be in 1..{CONDUCTED_COUNT + 1}")

    expected_ids = [item["entry_id"] for item in sequence[: next_number - 1]]
    actual_ids: list[str] = []
    receipts: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(prepared):
        _require_exact_keys(item, {"entry_id", "compiled_manifest_path", "compiled_manifest_sha256"}, f"prepared_entries[{index}]")
        entry_id = item.get("entry_id")
        manifest_raw = Path(item.get("compiled_manifest_path", ""))
        manifest_path = manifest_raw if manifest_raw.is_absolute() else preparation_cursor_path.parent / manifest_raw
        if not isinstance(entry_id, str) or not entry_id:
            raise ValueError(f"prepared_entries[{index}].entry_id must be non-empty")
        if not manifest_path.is_file() or item.get("compiled_manifest_sha256") != digest_path(manifest_path):
            raise ValueError(f"prepared_entries[{index}] compiled manifest path/hash does not resolve")
        manifest = load_object(manifest_path)
        if manifest.get("conducted_sequence", {}).get("entry_id") != entry_id:
            raise ValueError(f"prepared_entries[{index}] manifest does not bind {entry_id}")
        actual_ids.append(entry_id)
        receipts[entry_id] = {
            "lesson_id": entry_id,
            "state": "compiled_ready_not_conducted",
            "evidence_artifact_ids": [item["compiled_manifest_sha256"]],
            "compiled_manifest_path": str(manifest_path.resolve()),
            "compiled_manifest_sha256": item["compiled_manifest_sha256"],
            "compiled_lesson_sha256": manifest.get("lesson_sha256"),
        }
    if actual_ids != expected_ids:
        raise ValueError("preparation history is not the exact frozen conducted-sequence prefix")
    if next_number == CONDUCTED_COUNT + 1:
        raise ValueError("the frozen 666-entry preparation sequence is complete")

    selected = sequence[next_number - 1]
    entry = selected["entry"]
    prerequisite_ids = (
        entry.get("prerequisite_lessons", [])
        if selected["entry_kind"] == "acquisition"
        else [*entry.get("prerequisite_acquisition_lessons", []), *entry.get("prerequisite_rehearsal_lessons", [])]
    )
    missing_prepared = [item for item in prerequisite_ids if item not in receipts]
    if missing_prepared:
        raise ValueError("next preparation entry has unprepared prerequisites: " + ", ".join(missing_prepared))
    established = {item["surface"] for item in learner_selection["eligible_vocabulary"]}
    required_language = entry.get("required_established_language", []) if selected["entry_kind"] == "acquisition" else []
    missing_language = [item for item in required_language if item not in established]
    if missing_language:
        raise ValueError(
            "next preparation entry requires language absent from actual learner closure: "
            + ", ".join(missing_language)
        )

    return {
        "schema_version": SELECTION_VERSION,
        "mode": "handhold_preparation",
        "selection_basis": "compiled_preparation_prefix_with_actual_learner_closure_unchanged",
        "sequence": {
            "planned_total": CONDUCTED_COUNT,
            "sequence_number": selected["sequence_number"],
            "entry_id": selected["entry_id"],
            "entry_kind": selected["entry_kind"],
            "curriculum_sha256": expected_hashes["curriculum_sha256"],
            "rehearsal_layer_sha256": expected_hashes["rehearsal_layer_sha256"],
            "cursor_sha256": digest_path(preparation_cursor_path),
        },
        "learner_evidence": learner_selection["learner_evidence"],
        "learner_conduct_position": learner_selection["sequence"],
        "selected_entry": entry,
        "prerequisite_receipts": [receipts[item] for item in prerequisite_ids],
        "eligible_vocabulary": learner_selection["eligible_vocabulary"],
        "authoring": {
            "actor": "luna",
            "authority": "Create the bounded complete lesson script for later conduct without treating prepared prerequisites as learned.",
            "forbidden": [
                "change the conducted entry or principal Point",
                "claim a prepared lesson was conducted or learned",
                "use language absent from actual learner closure unless it is the selected frontier",
                "dispatch training",
            ],
        },
        "independent_review": {
            "required": True,
            "reviewer_role": "sol",
            "graduation_policy": "undecided",
            "handhold_rule": "Every compiled lesson requires explicit Sol review until an evidence-bearing graduation policy is approved.",
        },
    }
