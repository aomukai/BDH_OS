#!/usr/bin/env python3
"""Read-only structural validator for the Ninereeds v6 curriculum artifacts.

This program does not validate pedagogical quality, factual truth, visual
quality, learner readiness, or instructor qualification.  It never writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


ALLOWED_PHASES = [
    "P0_BOOTSTRAP",
    "P1_REFERENCE",
    "P2_ACTION_SOCIAL",
    "P3_OPERATORS",
    "P4_ONTOLOGY_EPISTEMIC",
    "P5_NATURAL_QUANTITATIVE_WORLD",
    "P6_SOCIAL_TECHNICAL_WORLD",
    "P7_FORMAL_BRIDGE",
]
ALLOWED_NOVELTIES = {
    "LEXICAL_SET",
    "LEXICAL_ITEM",
    "CONSTRUCTION",
    "RESPONSE_FORM",
    "DISCOURSE_OPERATION",
    "WORLD_RELATION",
    "STAGED_EXCEPTION",
}
ALLOWED_CHRONOLOGY = {
    "canonical_event",
    "canonical_state_reuse",
    "noncanonical_instructional",
}
ALLOWED_BOOK = {"required", "optional", "no"}


def load_json(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing file: {path.name}")
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {path.name}: {exc}")
    return None


def check(condition: bool, message: str, errors: list[str]):
    if not condition:
        errors.append(message)


def validate(directory: Path):
    errors: list[str] = []
    warnings: list[str] = []
    check_results: dict[str, dict] = {}

    curriculum = load_json(directory / "curriculum_v6.json", errors)
    accounting = load_json(directory / "source_accounting_v6.json", errors)
    rehearsal = load_json(directory / "rehearsal_layer_v6.json", errors)
    if not all([curriculum, accounting, rehearsal]):
        return {
            "status": "FAIL",
            "scope": "structural validation only; no mechanical pedagogical-quality claim",
            "errors": errors,
            "warnings": warnings,
            "checks": check_results,
        }

    lessons = curriculum.get("lessons")
    check(isinstance(lessons, list) and lessons, "curriculum lessons must be a nonempty list", errors)
    if not isinstance(lessons, list) or not lessons:
        lessons = []
    lesson_ids = [row.get("lesson_id") for row in lessons]
    expected_lesson_ids = [f"L{i:03d}" for i in range(len(lessons))]
    check(lesson_ids == expected_lesson_ids, "acquisition lesson IDs are not consecutive from L000", errors)
    check(len(lesson_ids) == len(set(lesson_ids)), "duplicate acquisition lesson identifier", errors)
    lesson_index = {lid: i for i, lid in enumerate(lesson_ids)}
    lesson_by_id = {row.get("lesson_id"): row for row in lessons}
    key_values = [row.get("curriculum_key") for row in lessons]
    check(len(key_values) == len(set(key_values)), "duplicate curriculum_key", errors)
    check(
        curriculum.get("metadata", {}).get("acquisition_lesson_count") == len(lessons),
        "metadata acquisition_lesson_count does not match lessons",
        errors,
    )
    check_results["identifier_uniqueness"] = {
        "status": "PASS" if lesson_ids == expected_lesson_ids and len(lesson_ids) == len(set(lesson_ids)) else "FAIL",
        "acquisition_ids_checked": len(lesson_ids),
    }

    required_fields = {
        "lesson_id",
        "phase",
        "topic",
        "point",
        "world_objective",
        "principal_novelty",
        "frontier_language",
        "required_established_language",
        "prerequisite_lessons",
        "grounding_modes",
        "picture_book",
        "characters",
        "locations",
        "chronology_constraints",
        "evaluation_targets",
        "source_provenance",
        "intended_later_rehearsal_targets",
    }
    event_ids = []
    phase_order = {phase: i for i, phase in enumerate(ALLOWED_PHASES)}
    last_phase = -1
    first_ontology_id = None
    bob_occurrences = []
    frontier_exceptions = []
    for i, lesson in enumerate(lessons):
        lid = lesson.get("lesson_id", f"row-{i}")
        missing = sorted(required_fields - set(lesson))
        check(not missing, f"{lid} missing required fields: {missing}", errors)
        phase = lesson.get("phase")
        check(phase in phase_order, f"{lid} has unknown phase {phase!r}", errors)
        if phase in phase_order:
            check(phase_order[phase] >= last_phase, f"{lid} moves backward in phase order", errors)
            last_phase = max(last_phase, phase_order[phase])
        check(isinstance(lesson.get("topic"), str) and lesson.get("topic", "").strip(), f"{lid} has empty TOPIC", errors)
        check(isinstance(lesson.get("point"), str) and lesson.get("point", "").strip(), f"{lid} has empty POINT", errors)
        check(isinstance(lesson.get("world_objective"), str) and lesson.get("world_objective", "").strip(), f"{lid} has empty world objective", errors)

        novelty = lesson.get("principal_novelty", {})
        novelty_type = novelty.get("type")
        check(novelty_type in ALLOWED_NOVELTIES, f"{lid} has invalid novelty type {novelty_type!r}", errors)
        check(bool(novelty.get("principal_axis")), f"{lid} lacks one principal novelty axis", errors)
        frontier = lesson.get("frontier_language")
        check(isinstance(frontier, list) and frontier, f"{lid} frontier_language must be nonempty for acquisition", errors)
        if not isinstance(frontier, list):
            frontier = []
        check(all(isinstance(x, str) and x.strip() for x in frontier), f"{lid} has an empty/non-string frontier entry", errors)
        if len(frontier) > 4:
            note = lesson.get("compiler_notes", "").lower()
            allowed = lid == "L000" or (
                len(frontier) == 5
                and ("five" in note or "5" in note)
                and any(term in note for term in ["evaluat", "waiver", "split"])
            )
            check(allowed, f"{lid} exceeds four frontier entries without a declared counted exception", errors)
            if allowed:
                frontier_exceptions.append(lid)
        counts = novelty.get("actual_counts", {})
        check(counts.get("new_forms") == len(frontier), f"{lid} actual new_forms does not match frontier entries", errors)
        if novelty_type == "CONSTRUCTION":
            check(counts.get("new_constructions") == len(frontier), f"{lid} construction count does not match frontier", errors)
        if novelty_type == "RESPONSE_FORM":
            check(counts.get("new_response_forms") == len(frontier), f"{lid} response-form count does not match frontier", errors)
        if novelty_type == "DISCOURSE_OPERATION":
            check(counts.get("new_discourse_operations") == len(frontier), f"{lid} discourse-operation count does not match frontier", errors)

        required_language = lesson.get("required_established_language")
        check(isinstance(required_language, list), f"{lid} required_established_language must be a list", errors)
        prerequisites = lesson.get("prerequisite_lessons")
        check(isinstance(prerequisites, list), f"{lid} prerequisite_lessons must be a list", errors)
        if isinstance(prerequisites, list):
            check(len(prerequisites) == len(set(prerequisites)), f"{lid} has duplicate prerequisites", errors)
            for dependency in prerequisites:
                check(dependency in lesson_index, f"{lid} references missing prerequisite {dependency}", errors)
                if dependency in lesson_index:
                    check(lesson_index[dependency] < i, f"{lid} prerequisite {dependency} is not earlier", errors)

        check(isinstance(lesson.get("grounding_modes"), list) and lesson.get("grounding_modes"), f"{lid} lacks grounding modes", errors)
        picture = lesson.get("picture_book", {})
        check(picture.get("status") in ALLOWED_BOOK, f"{lid} has invalid picture-book status", errors)
        check(isinstance(picture.get("rationale"), str) and picture.get("rationale", "").strip(), f"{lid} lacks picture-book rationale", errors)
        check(isinstance(lesson.get("characters"), list) and lesson.get("characters"), f"{lid} lacks character declaration", errors)
        check(isinstance(lesson.get("locations"), list) and lesson.get("locations"), f"{lid} lacks location declaration", errors)
        if "Bob" in lesson.get("characters", []):
            bob_occurrences.append(lid)

        chronology = lesson.get("chronology_constraints", {})
        mode = chronology.get("mode")
        check(mode in ALLOWED_CHRONOLOGY, f"{lid} has invalid chronology mode {mode!r}", errors)
        check(isinstance(chronology.get("constraints"), list) and chronology.get("constraints"), f"{lid} lacks chronology constraints", errors)
        if mode == "canonical_event":
            event_id = chronology.get("event_id")
            check(isinstance(event_id, str) and event_id, f"{lid} canonical event lacks event_id", errors)
            if event_id:
                event_ids.append(event_id)
        else:
            check(chronology.get("event_id") is None, f"{lid} non-event chronology has event_id", errors)
        if mode == "noncanonical_instructional":
            check(not chronology.get("state_updates"), f"{lid} noncanonical instruction updates canonical state", errors)

        check(isinstance(lesson.get("evaluation_targets"), list) and len(lesson.get("evaluation_targets", [])) >= 3, f"{lid} lacks sufficient evaluation targets", errors)
        if lesson.get("curriculum_key") == "ontology_labels":
            first_ontology_id = lid

        world_and_frontier = " ".join([lesson.get("world_objective", ""), *frontier]).lower()
        forbidden_patterns = [
            "ninereeds is an ai",
            "ninereeds is a machine",
            "ninereeds is a model",
            "ninereeds is an llm",
            "ninereeds is conscious",
            "ninereeds is sentient",
        ]
        for pattern in forbidden_patterns:
            check(pattern not in world_and_frontier, f"{lid} contains forbidden Ninereeds classification: {pattern}", errors)

    check(len(event_ids) == len(set(event_ids)), "duplicate canonical event_id", errors)
    check(bob_occurrences == ["L000"], f"Bob must appear only in L000 characters, found {bob_occurrences}", errors)
    check(first_ontology_id is not None, "missing ontology_labels lesson", errors)
    check(
        curriculum.get("metadata", {}).get("first_explicit_ontology_lesson") == first_ontology_id,
        "metadata first explicit ontology ID does not match ontology_labels",
        errors,
    )
    if lessons:
        l000 = lessons[0]
        check(l000.get("phase") == "P0_BOOTSTRAP", "L000 is not in bootstrap phase", errors)
        check(l000.get("principal_novelty", {}).get("type") == "STAGED_EXCEPTION", "L000 is not staged exception", errors)
        check(l000.get("picture_book", {}).get("status") == "no", "L000 must have no picture book", errors)
        check("Bob" in l000.get("characters", []), "L000 must preserve Bob source appearance", errors)
        for lesson in lessons[1:]:
            check(lesson.get("principal_novelty", {}).get("type") != "STAGED_EXCEPTION", f"{lesson.get('lesson_id')} is an unauthorized staged exception", errors)
    primitive = next((row for row in lessons if row.get("curriculum_key") == "errol_data_travel"), None)
    check(primitive is not None, "missing intentional Errol data-travel lesson", errors)
    if primitive:
        check("Errol travels by data transfer." in primitive.get("frontier_language", []), "Errol data-travel primitive is not preserved verbatim", errors)
    check_results["dependency_frontier_chronology"] = {
        "status": "PASS" if not errors else "FAIL",
        "lessons_checked": len(lessons),
        "canonical_events_checked": len(event_ids),
        "declared_frontier_exceptions": frontier_exceptions,
        "bob_character_occurrences": bob_occurrences,
        "first_explicit_ontology_lesson": first_ontology_id,
    }

    records = accounting.get("records")
    check(isinstance(records, list), "source accounting records must be a list", errors)
    if not isinstance(records, list):
        records = []
    source_ids = [row.get("source_id") for row in records]
    expected_sources = [f"C{i:03d}" for i in range(1, 241)]
    check(len(records) == 240, "source accounting must contain exactly 240 records", errors)
    check(source_ids == expected_sources, "source records are not exactly C001-C240 in order", errors)
    check(len(source_ids) == len(set(source_ids)), "duplicate source accounting record", errors)
    check(accounting.get("record_count") == len(records), "source record_count mismatch", errors)
    allowed_dispositions = {"active", "consolidated", "deferred", "excluded"}
    recorded_map = {}
    for row in records:
        sid = row.get("source_id", "unknown")
        check(row.get("disposition") in allowed_dispositions, f"{sid} has invalid disposition", errors)
        resulting = row.get("resulting_lesson_ids")
        check(isinstance(resulting, list), f"{sid} resulting_lesson_ids must be a list", errors)
        if not isinstance(resulting, list):
            resulting = []
        if row.get("disposition") in {"active", "consolidated"}:
            check(bool(resulting), f"{sid} active/consolidated record has no lesson IDs", errors)
        if row.get("disposition") in {"deferred", "excluded"}:
            check(not resulting, f"{sid} deferred/excluded record has acquisition lesson IDs", errors)
        for lid in resulting:
            check(lid in lesson_by_id, f"{sid} maps to missing lesson {lid}", errors)
        check(isinstance(row.get("rationale"), str) and len(row.get("rationale", "")) > 40, f"{sid} lacks evidence-based rationale", errors)
        check(isinstance(row.get("evidence"), list), f"{sid} lacks evidence records", errors)
        recorded_map[sid] = resulting
    provenance_map = defaultdict(list)
    for lesson in lessons:
        for source in lesson.get("source_provenance", []):
            if isinstance(source, str) and source.startswith("C") and source[1:].isdigit():
                provenance_map[source].append(lesson["lesson_id"])
    for sid in expected_sources:
        check(recorded_map.get(sid, []) == provenance_map.get(sid, []), f"{sid} accounting is not bidirectional with lesson provenance", errors)
    check_results["source_accounting"] = {
        "status": "PASS" if source_ids == expected_sources and all(recorded_map.get(sid) == provenance_map.get(sid) for sid in expected_sources) else "FAIL",
        "records_checked": len(records),
        "disposition_counts": dict(Counter(row.get("disposition") for row in records)),
    }

    scheduled = rehearsal.get("scheduled_rehearsals")
    check(isinstance(scheduled, list) and scheduled, "scheduled rehearsals must be a nonempty list", errors)
    if not isinstance(scheduled, list):
        scheduled = []
    rehearsal_ids = [row.get("rehearsal_id") for row in scheduled]
    expected_rids = [f"R{i:03d}" for i in range(1, len(scheduled) + 1)]
    check(rehearsal_ids == expected_rids, "rehearsal IDs are not consecutive from R001", errors)
    check(len(rehearsal_ids) == len(set(rehearsal_ids)), "duplicate rehearsal identifier", errors)
    rehearsal_index = {rid: i for i, rid in enumerate(rehearsal_ids)}
    rehearsal_by_id = {row.get("rehearsal_id"): row for row in scheduled}
    cold_coverage = Counter()
    for i, row in enumerate(scheduled):
        rid = row.get("rehearsal_id", f"r-row-{i}")
        check(row.get("layer") == "REHEARSAL_TRANSFER", f"{rid} has wrong layer", errors)
        check(row.get("frontier_language") == [], f"{rid} introduces frontier language", errors)
        check(row.get("new_world_facts") == [], f"{rid} introduces world facts", errors)
        acquisitions = row.get("prerequisite_acquisition_lessons")
        check(isinstance(acquisitions, list) and acquisitions, f"{rid} lacks acquisition prerequisites", errors)
        if not isinstance(acquisitions, list):
            acquisitions = []
        for lid in acquisitions:
            check(lid in lesson_by_id, f"{rid} references missing acquisition {lid}", errors)
        prior_rehearsals = row.get("prerequisite_rehearsal_lessons")
        check(isinstance(prior_rehearsals, list), f"{rid} rehearsal prerequisites must be a list", errors)
        if isinstance(prior_rehearsals, list):
            for prior in prior_rehearsals:
                check(prior in rehearsal_index, f"{rid} references missing rehearsal {prior}", errors)
                if prior in rehearsal_index:
                    check(rehearsal_index[prior] < i, f"{rid} references non-earlier rehearsal {prior}", errors)
        expected_after = lesson_ids[-1] if i == 0 and lesson_ids else f"R{i:03d}"
        check(row.get("scheduled_after") == expected_after, f"{rid} scheduled_after is not immediate preceding layer item", errors)
        recombination = row.get("topic_point_recombination", {})
        point_source = recombination.get("point_source_lesson")
        topic_source = recombination.get("topic_source_lesson")
        check(point_source in acquisitions, f"{rid} point source is not an acquisition prerequisite", errors)
        check(topic_source in acquisitions, f"{rid} topic source is not an acquisition prerequisite", errors)
        check(isinstance(recombination.get("task"), str) and recombination.get("task", "").strip(), f"{rid} lacks concrete recombination task", errors)
        check(bool(recombination.get("compatibility_basis")), f"{rid} lacks compatibility basis", errors)
        cold = row.get("cold_retrieval_targets")
        check(isinstance(cold, list) and cold, f"{rid} lacks cold retrieval targets", errors)
        if not isinstance(cold, list):
            cold = []
        for lid in cold:
            check(lid in acquisitions, f"{rid} cold target {lid} not listed as prerequisite", errors)
            if lid in lesson_by_id:
                cold_coverage[lid] += 1
        spacing = row.get("spacing_purpose")
        check(isinstance(spacing, list) and spacing, f"{rid} lacks spacing records", errors)
        if isinstance(spacing, list):
            spacing_targets = [item.get("acquisition_lesson") for item in spacing]
            check(spacing_targets == cold, f"{rid} spacing records do not match cold targets", errors)
            for item in spacing:
                check(isinstance(item.get("conducted_opportunity_gap"), int) and item.get("conducted_opportunity_gap", 0) > 0, f"{rid} has nonpositive spacing gap", errors)
                prior = item.get("prior_rehearsal")
                if prior is not None:
                    check(prior in rehearsal_index and rehearsal_index[prior] < i, f"{rid} spacing points to non-earlier rehearsal {prior}", errors)
        check(isinstance(row.get("interference_set"), list) and row.get("interference_set"), f"{rid} lacks interference set", errors)
        check(bool(row.get("grounding_mode")), f"{rid} lacks grounding mode", errors)
        check(isinstance(row.get("response_expectations"), list) and len(row.get("response_expectations", [])) >= 3, f"{rid} lacks response expectations", errors)
        check(isinstance(row.get("evaluation_objective"), str) and row.get("evaluation_objective", "").strip(), f"{rid} lacks evaluation objective", errors)
        chrono = row.get("chronology_constraints", {})
        check(chrono.get("mode") == "rehearsal_only", f"{rid} does not declare rehearsal-only chronology", errors)
        check(chrono.get("creates_canonical_event") is False, f"{rid} creates a canonical event", errors)

    check(set(cold_coverage) == set(lesson_ids), "cold rehearsal coverage does not include every acquisition", errors)
    if lesson_ids:
        check(min(cold_coverage.values(), default=0) >= 2, "an acquisition has fewer than two cold retrievals", errors)
    for lesson in lessons:
        lid = lesson["lesson_id"]
        intents = lesson.get("intended_later_rehearsal_targets")
        check(isinstance(intents, list) and len(intents) >= 2, f"{lid} lacks two intended later rehearsal links", errors)
        if isinstance(intents, list):
            for rid in intents:
                check(rid in rehearsal_by_id, f"{lid} links missing rehearsal {rid}", errors)
                if rid in rehearsal_by_id:
                    check(lid in rehearsal_by_id[rid].get("prerequisite_acquisition_lessons", []), f"{lid}→{rid} link is not reciprocal", errors)
    for row in scheduled:
        rid = row["rehearsal_id"]
        for lid in row.get("prerequisite_acquisition_lessons", []):
            if lid in lesson_by_id:
                check(rid in lesson_by_id[lid].get("intended_later_rehearsal_targets", []), f"{rid}→{lid} link is not reciprocal", errors)

    gates = rehearsal.get("conditional_diagnostic_remedial_gates")
    check(isinstance(gates, list), "conditional gates must be a list", errors)
    if not isinstance(gates, list):
        gates = []
    gate_ids = [gate.get("gate_id") for gate in gates]
    check(len(gate_ids) == len(set(gate_ids)), "duplicate conditional gate ID", errors)
    for gate in gates:
        gid = gate.get("gate_id", "unknown-gate")
        check(gate.get("conditional_not_precommitted") is True, f"{gid} is not marked conditional", errors)
        check(gate.get("scheduled_lesson_count") == 0, f"{gid} incorrectly adds scheduled lessons", errors)
        check(gate.get("evaluate_after") in rehearsal_index, f"{gid} evaluates after missing rehearsal", errors)
        lesson_range = gate.get("acquisition_range")
        check(isinstance(lesson_range, list) and len(lesson_range) == 2, f"{gid} has invalid acquisition range", errors)
        if isinstance(lesson_range, list) and len(lesson_range) == 2:
            check(all(x in lesson_index for x in lesson_range), f"{gid} range contains missing lesson", errors)
            if all(x in lesson_index for x in lesson_range):
                check(lesson_index[lesson_range[0]] <= lesson_index[lesson_range[1]], f"{gid} range is reversed", errors)
    check(
        rehearsal.get("metadata", {}).get("scheduled_rehearsal_count") == len(scheduled),
        "rehearsal metadata count mismatch",
        errors,
    )
    check(
        rehearsal.get("metadata", {}).get("planned_conducted_total") == len(lessons) + len(scheduled),
        "planned conducted total mismatch",
        errors,
    )
    check_results["acquisition_rehearsal_separation"] = {
        "status": "PASS" if all(row.get("frontier_language") == [] and row.get("new_world_facts") == [] for row in scheduled) else "FAIL",
        "rehearsals_checked": len(scheduled),
        "conditional_gates_checked": len(gates),
        "cold_coverage_minimum": min(cold_coverage.values(), default=0),
        "cold_coverage_maximum": max(cold_coverage.values(), default=0),
    }

    actual_phase_counts = Counter(row.get("phase") for row in lessons)
    check(
        curriculum.get("metadata", {}).get("phase_counts") == {phase: actual_phase_counts.get(phase, 0) for phase in ALLOWED_PHASES},
        "phase_counts metadata mismatch",
        errors,
    )
    actual_book_counts = Counter(row.get("picture_book", {}).get("status") for row in lessons)
    expected_books = {status: actual_book_counts.get(status, 0) for status in ["required", "optional", "no"]}
    check(curriculum.get("metadata", {}).get("picture_book_counts") == expected_books, "picture_book_counts metadata mismatch", errors)
    check_results["referential_integrity"] = {
        "status": "PASS" if not any("reciprocal" in error or "missing" in error for error in errors) else "FAIL",
        "acquisition_to_rehearsal_links_checked": sum(len(row.get("intended_later_rehearsal_targets", [])) for row in lessons),
        "picture_book_counts": expected_books,
        "phase_counts": dict(actual_phase_counts),
    }

    warnings.extend(
        [
            "Surface-language semantic closure is declared but cannot be proven by string matching; a qualified compiler must inspect authored lesson text.",
            "Chronology declarations and event-ID uniqueness are checked, but world-bible factual consistency and visual continuity require human review.",
            "TOPIC/POINT pairing fields and curated compatibility rationales are present, but pedagogical teachability is not mechanically validated.",
            "Source accounting is checked bidirectionally for structure; disposition quality and rationale adequacy require independent adversarial review.",
        ]
    )
    status = "FAIL" if errors else "PASS"
    return {
        "status": status,
        "scope": "structural validation only; no mechanical pedagogical-quality claim",
        "summary": {
            "acquisition_lessons": len(lessons),
            "scheduled_rehearsals": len(scheduled),
            "conditional_gates": len(gates),
            "source_records": len(records),
            "canonical_events": len(event_ids),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "checks": check_results,
        "errors": errors,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit one JSON object")
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = validate(args.directory.resolve())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['status']}: {result['summary']['error_count']} errors, {result['summary']['warning_count']} limitations")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"NOTE: {warning}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
