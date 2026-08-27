from __future__ import annotations

import hashlib
import importlib.util
import json
import copy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "mission_hub" / "skills" / "compile-next-lesson" / "scripts" / "compile_lesson.py"
STAGE_VALIDATOR = ROOT / "mission_hub" / "skills" / "compile-next-lesson" / "scripts" / "validate_builder_stage.py"


def _load_compiler():
    spec = importlib.util.spec_from_file_location("ninereeds_lesson_compiler", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_stage_validator():
    spec = importlib.util.spec_from_file_location("ninereeds_builder_stage_validator", STAGE_VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exercise(identifier: str, asset_ids: list[str] | None = None) -> dict:
    return {
        "id": identifier,
        "teacher_text": "Are you Ninereeds?",
        "expected_answers": ["Yes, I am Ninereeds."],
        "invariants": ["speaker identifies as Ninereeds"],
        "asset_ids": asset_ids or [],
        "target_language_required": True,
    }


def _lesson(root: Path, *, variant: str) -> dict:
    bindings = []
    for role in (
        "learner_state",
        "known_closure",
        "teaching_methodology",
        "world_bible",
        "identity_policy",
        "instructor_qualification",
    ):
        path = root / f"{role}.json"
        path.write_text(json.dumps({"role": role}), encoding="utf-8")
        bindings.append({"role": role, "path": path.name, "sha256": _sha(path)})
    qualification = root / "instructor_qualification.json"
    practice = {
        key: [_exercise(f"{key}-01")]
        for key in ("affirmative", "negative", "W_question", "OR_question")
    }
    lesson = {
        "schema_version": "ninereeds_lesson_contract_v2",
        "lesson_id": "lesson-greeting-v1",
        "status": "draft",
        "variant": variant,
        "target_language": "English",
        "topic": "Greeting and self-introduction",
        "point": {"id": "self_identification", "claim": "Say one's own name", "novelty_kind": "communicative_act"},
        "selection": {
            "learner_state_artifact_id": "learner-state-001",
            "known_closure_artifact_id": "known-closure-001",
            "rationale": "The learner needs a stable first self-introduction.",
            "predicted_dosage": "One presentation and one item per controlled form before mixed practice.",
        },
        "prerequisites": [],
        "source_bindings": bindings,
        "world": {
            "recurring_entities": [],
            "new_entries": [],
            "extras_policy": "unnamed_nonrecurring_no_persistent_history",
        },
        "language_boundary": {
            "permitted_rescue_languages": [],
            "correct_meaning_wrong_language": "concept_may_be_understood_target_production_not_demonstrated",
            "off_topic_response": "Acknowledge briefly and return to the pending turn.",
            "role_diversion_response": "Keep the Instructor role and return to the lesson.",
        },
        "phases": {
            "presentation": [_exercise("presentation-01")],
            "controlled_practice": practice,
            "mixed_practice": [_exercise("mixed-01")],
            "transfer": [],
        },
        "picture_book": None,
        "assets": [],
        "adaptive": {
            "presentation_replay_after_failures": 3,
            "maximum_teacher_turns": 4,
            "mixed_practice_cap": 16,
            "completion_fraction": 0.75,
            "controller_actions": ["CONTINUE", "PRESENT_AGAIN", "USE_MARKERS", "FINISH"],
            "marker_intervention": {
                "action": "USE_MARKERS",
                "enabled": True,
                "role_delimiters": {
                    "subject": ["(", ")"],
                    "predicate": ["*", "*"],
                    "recipient": ["[", "]"],
                    "object": ["{", "}"],
                    "possessor": ["<", ">"],
                },
                "focus_delimiter": ["+", "+"],
                "levels": ["none", "constituent_only", "full_role_map", "frontier_focus"],
                "scheduled_presentation_fraction": 0.25,
                "immediate_retest": "unmarked",
                "expected_student_output": "unmarked",
                "fade_after_consecutive_unmarked_successes": 3,
                "fade_after_distinct_scenes": 2,
                "max_scored_mixed_prompts": 16,
                "max_unchanged_failure_episodes": 2,
                "terminal_outcome": "defer_and_revisit",
            },
        },
        "rehearsal": {
            "pattern_id": f"{variant}-v1",
            "decision": "full_rehearsal_passed",
            "reason": "Five consecutive mandatory suites passed.",
            "qualification_record_path": qualification.name,
            "qualification_record_sha256": _sha(qualification),
            "evidence_artifact_ids": ["rehearsal-suite-001"],
        },
    }
    if variant == "picture_book":
        image = root / "page-01.png"
        image.write_bytes(b"fixture image bytes")
        asset = {
            "id": "page-01",
            "purpose": "Reviewed master scene",
            "status": "reviewed_usable",
            "source": "flux_generation",
            "path": image.name,
            "sha256": _sha(image),
            "review_receipt_id": "review-page-01",
            "parent_asset_id": None,
            "crop_xywh": None,
            "canonical_reference_ids": [],
            "attempted_sources": ["registry"],
            "escalation_reason": "",
        }
        lesson["assets"] = [asset]
        lesson["picture_book"] = {
            "instructional_kernel": "Ninereeds uses the established greeting in a first meeting.",
            "pages": [{"id": "story-page-01", "asset_id": "page-01", "caption": "Hello!", "scene_facts": ["two characters greet"]}],
            "comprehension": [_exercise("comprehension-01", ["page-01"])],
        }
    return lesson


def test_compiles_dialogue_only_lesson(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _lesson(tmp_path, variant="dialogue_only")
    assert compiler.validate_lesson(lesson, "freeze") == []
    source = tmp_path / "draft.json"
    source.write_text(json.dumps(lesson), encoding="utf-8")
    output = tmp_path / "compiled"
    compiler.compile_lesson(source, output)
    frozen = json.loads((output / "lesson.json").read_text(encoding="utf-8"))
    assert frozen["status"] == "frozen"
    assert sorted(path.name for path in output.iterdir()) == ["lesson.json", "lesson.md", "manifest.json"]


def test_compiles_picture_book_lesson(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _lesson(tmp_path, variant="picture_book")
    assert compiler.validate_lesson(lesson, "freeze") == []


def test_promotes_exact_passed_rehearsal_without_mutating_source(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _lesson(tmp_path, variant="dialogue_only")
    lesson["rehearsal"]["decision"] = "required_pending"
    qualification = tmp_path / "qualification-state.json"
    qualification.write_text(json.dumps({
        "schema_version": "ninereeds_instructor_qualification_state_v1",
        "patterns": {},
    }), encoding="utf-8")
    lesson["rehearsal"]["qualification_record_path"] = qualification.name
    lesson["rehearsal"]["qualification_record_sha256"] = _sha(qualification)
    source = tmp_path / "rehearsed-source.json"
    source.write_text(json.dumps(lesson), encoding="utf-8")
    manifest = tmp_path / "run-manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": "ninereeds_lesson_rehearsal_manifest_v1",
        "rehearsal_id": "fixture-run-001",
        "terminal_status": "passed",
        "lesson_sha256": _sha(source),
    }), encoding="utf-8")
    report = tmp_path / "canonical-report.json"
    report.write_text(json.dumps({
        "schema_version": "ninereeds_canonical_lesson_outcome_report_v1",
        "report_id": "fixture-report-001",
        "run_id": "fixture-run-001",
        "outcome": "passed",
        "lesson": {"path": str(source), "sha256": _sha(source)},
    }), encoding="utf-8")
    output = tmp_path / "promoted.json"

    compiler.promote_rehearsed_lesson(source, manifest, report, qualification, output)

    assert json.loads(source.read_text())["rehearsal"]["decision"] == "required_pending"
    promoted = json.loads(output.read_text())
    assert promoted["rehearsal"]["decision"] == "full_rehearsal_passed"
    assert promoted["rehearsal"]["qualification_record_sha256"] == _sha(qualification)


def test_rejects_imagegen_without_flux_attempt(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _lesson(tmp_path, variant="picture_book")
    lesson["assets"][0]["source"] = "openai_imagegen"
    lesson["assets"][0]["attempted_sources"] = ["registry"]
    lesson["assets"][0]["escalation_reason"] = "Flux was not attempted."
    errors = compiler.validate_lesson(lesson, "freeze")
    assert any("ImageGen requires a recorded Flux attempt" in error for error in errors)


def test_rejects_unreviewed_asset_and_pending_rehearsal(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _lesson(tmp_path, variant="picture_book")
    lesson["assets"][0]["status"] = "commissioned_pending"
    lesson["rehearsal"]["decision"] = "required_pending"
    errors = compiler.validate_lesson(lesson, "freeze")
    assert any("must be reviewed_usable" in error for error in errors)
    assert any("rehearsal or qualification remains pending" in error for error in errors)


def test_rejects_marker_drift_or_marked_mastery_response(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _lesson(tmp_path, variant="dialogue_only")
    lesson["adaptive"]["marker_intervention"]["role_delimiters"]["subject"] = ["[", "]"]
    lesson["adaptive"]["marker_intervention"]["expected_student_output"] = "marked"
    errors = compiler.validate_lesson(lesson, "freeze")
    assert any("marker meanings must remain frozen" in error for error in errors)
    assert any("expected_student_output: must equal unmarked" in error for error in errors)


def test_rejects_enabled_marker_intervention_without_action(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _lesson(tmp_path, variant="dialogue_only")
    lesson["adaptive"]["controller_actions"].remove("USE_MARKERS")
    errors = compiler.validate_lesson(lesson, "freeze")
    assert any("requires USE_MARKERS" in error for error in errors)


def _selection_inputs(tmp_path: Path, *, next_sequence_number: int = 2) -> tuple[Path, Path]:
    learner = tmp_path / "learner-state.json"
    learner.write_text(json.dumps({"learner": "dry-run", "mode": "handhold"}), encoding="utf-8")
    closure = tmp_path / "known-closure.json"
    closure.write_text(json.dumps({
        "schema_version": "ninereeds_known_closure_v1",
        "learner_state_artifact_id": "learner-state-dry-run",
        "lesson_evidence": [{
            "lesson_id": "L000",
            "state": "mixed_practice_completed",
            "evidence_artifact_ids": ["evidence-L000"],
        }],
        "eligible_vocabulary": [{
            "id": "hello",
            "surface": "Hello!",
            "evidence_lesson_ids": ["L000"],
            "evidence_artifact_ids": ["evidence-L000"],
        }],
    }), encoding="utf-8")
    curriculum = ROOT / "docs" / "curriculum_v6_sol" / "curriculum_v6.json"
    rehearsal = ROOT / "docs" / "curriculum_v6_sol" / "rehearsal_layer_v6.json"
    cursor = tmp_path / "cursor.json"
    cursor.write_text(json.dumps({
        "schema_version": "ninereeds_lesson_cursor_v1",
        "mode": "handhold",
        "curriculum_sha256": _sha(curriculum),
        "rehearsal_layer_sha256": _sha(rehearsal),
        "completed_entry_ids": ["L000"] if next_sequence_number == 2 else [],
        "next_sequence_number": next_sequence_number,
        "learner_state_artifact_id": "learner-state-dry-run",
        "learner_state_path": learner.name,
        "learner_state_sha256": _sha(learner),
        "known_closure_artifact_id": "known-closure-dry-run",
        "known_closure_path": closure.name,
        "known_closure_sha256": _sha(closure),
    }), encoding="utf-8")
    return cursor, closure


def test_selects_exact_next_v6_entry_with_prerequisite_receipt(tmp_path: Path) -> None:
    compiler = _load_compiler()
    cursor, closure = _selection_inputs(tmp_path)
    selected = compiler.select_next(
        curriculum_path=ROOT / "docs" / "curriculum_v6_sol" / "curriculum_v6.json",
        rehearsal_path=ROOT / "docs" / "curriculum_v6_sol" / "rehearsal_layer_v6.json",
        cursor_path=cursor,
        closure_path=closure,
    )
    assert selected["sequence"] == {
        "planned_total": 666,
        "sequence_number": 2,
        "entry_id": "L001",
        "entry_kind": "acquisition",
        "curriculum_sha256": _sha(ROOT / "docs" / "curriculum_v6_sol" / "curriculum_v6.json"),
        "rehearsal_layer_sha256": _sha(ROOT / "docs" / "curriculum_v6_sol" / "rehearsal_layer_v6.json"),
        "cursor_sha256": _sha(cursor),
    }
    assert selected["prerequisite_receipts"][0]["lesson_id"] == "L000"
    assert selected["authoring"]["actor"] == "luna"
    assert selected["independent_review"]["required"] is True


def test_rejects_cursor_that_skips_frozen_sequence_prefix(tmp_path: Path) -> None:
    compiler = _load_compiler()
    cursor, closure = _selection_inputs(tmp_path)
    payload = json.loads(cursor.read_text(encoding="utf-8"))
    payload["completed_entry_ids"] = []
    cursor.write_text(json.dumps(payload), encoding="utf-8")
    try:
        compiler.select_next(
            curriculum_path=ROOT / "docs" / "curriculum_v6_sol" / "curriculum_v6.json",
            rehearsal_path=ROOT / "docs" / "curriculum_v6_sol" / "rehearsal_layer_v6.json",
            cursor_path=cursor,
            closure_path=closure,
        )
    except ValueError as exc:
        assert "exact frozen conducted-sequence prefix" in str(exc)
    else:
        raise AssertionError("skipped cursor must fail closed")


def test_preparation_selection_runs_ahead_without_advancing_learner_state(tmp_path: Path) -> None:
    compiler = _load_compiler()
    def write(name: str, value: dict) -> Path:
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path
    curriculum = ROOT / "docs" / "curriculum_v6_sol" / "curriculum_v6.json"
    rehearsal = ROOT / "docs" / "curriculum_v6_sol" / "rehearsal_layer_v6.json"
    learner = write("learner.json", {"state": "before-L000"})
    closure = write("closure.json", {
        "schema_version": "ninereeds_known_closure_v1",
        "learner_state_artifact_id": "learner-before-L000",
        "lesson_evidence": [],
        "eligible_vocabulary": [],
    })
    learner_cursor = write("learner-cursor.json", {
        "schema_version": "ninereeds_lesson_cursor_v1",
        "mode": "handhold",
        "curriculum_sha256": _sha(curriculum),
        "rehearsal_layer_sha256": _sha(rehearsal),
        "completed_entry_ids": [],
        "next_sequence_number": 1,
        "learner_state_artifact_id": "learner-before-L000",
        "learner_state_path": learner.name,
        "learner_state_sha256": _sha(learner),
        "known_closure_artifact_id": "closure-before-L000",
        "known_closure_path": closure.name,
        "known_closure_sha256": _sha(closure),
    })
    compiled_manifest = write("L000-manifest.json", {
        "conducted_sequence": {"entry_id": "L000"},
        "lesson_sha256": "a" * 64,
    })
    preparation_cursor = write("preparation-cursor.json", {
        "schema_version": "ninereeds_lesson_preparation_cursor_v1",
        "mode": "handhold_preparation",
        "curriculum_sha256": _sha(curriculum),
        "rehearsal_layer_sha256": _sha(rehearsal),
        "prepared_entries": [{
            "entry_id": "L000",
            "compiled_manifest_path": compiled_manifest.name,
            "compiled_manifest_sha256": _sha(compiled_manifest),
        }],
        "next_sequence_number": 2,
        "learner_cursor_path": learner_cursor.name,
        "learner_cursor_sha256": _sha(learner_cursor),
        "known_closure_path": closure.name,
        "known_closure_sha256": _sha(closure),
    })
    selected = compiler.select_next_preparation(
        curriculum_path=curriculum,
        rehearsal_path=rehearsal,
        preparation_cursor_path=preparation_cursor,
        learner_cursor_path=learner_cursor,
        closure_path=closure,
    )
    assert selected["sequence"]["entry_id"] == "L001"
    assert selected["learner_conduct_position"]["entry_id"] == "L000"
    assert selected["eligible_vocabulary"] == []
    assert selected["prerequisite_receipts"][0]["state"] == "compiled_ready_not_conducted"


def _upgrade_v3(root: Path, lesson: dict) -> dict:
    files = {}
    for name in ("selection-packet", "luna-prompt", "luna-receipt", "sol-review"):
        path = root / f"{name}.json"
        path.write_text(json.dumps({"kind": name, "mode": "handhold"}), encoding="utf-8")
        files[name] = path
    files["selection-packet"].write_text(json.dumps({
        "schema_version": "ninereeds_lesson_selection_v1",
        "sequence": {"entry_id": "L001", "entry_kind": "acquisition", "sequence_number": 2},
        "selected_entry": {
            "topic": lesson["topic"],
            "point": lesson["point"]["claim"],
            "prerequisite_lessons": [item["id"] for item in lesson["prerequisites"]],
            "picture_book": {"status": "required" if lesson["variant"] == "picture_book" else "no"},
        },
    }), encoding="utf-8")
    lesson["schema_version"] = "ninereeds_lesson_contract_v3"
    original_presentation = lesson["phases"]["presentation"][0]
    lesson["phases"]["presentation"] = []
    lesson["phases"]["presentation_bindings"] = {}
    for gate in ("affirmative", "negative", "W_question", "OR_question"):
        model = copy.deepcopy(original_presentation)
        model["id"] = f"presentation-{gate}"
        lesson["phases"]["presentation"].append(model)
        lesson["phases"]["presentation_bindings"][gate] = [model["id"]]
    lesson_format = root / "lesson-format.json"
    lesson_format.write_text(json.dumps({"policy": "complete dual-use visual lesson"}), encoding="utf-8")
    lesson["source_bindings"].append({
        "role": "lesson_format",
        "path": lesson_format.name,
        "sha256": _sha(lesson_format),
    })
    pools = [lesson["phases"]["presentation"], lesson["phases"]["mixed_practice"], lesson["phases"]["transfer"]]
    pools.extend(lesson["phases"]["controlled_practice"].values())
    if isinstance(lesson.get("picture_book"), dict):
        pools.append(lesson["picture_book"]["comprehension"])
    for pool in pools:
        for exercise in pool:
            if isinstance(lesson.get("picture_book"), dict) and not exercise["asset_ids"]:
                exercise["asset_ids"] = ["page-01"]
            exercise.update({
                "response_mode": "learner_self",
                "speaker_identity": "Ninereeds",
                "evidence_use": "learner_identity_and_language",
                "teacher_speaker": "Taro",
                "speaker_asset_ids": exercise["asset_ids"],
            })
    for exercise in lesson["phases"]["presentation"]:
        exercise.pop("teacher_speaker", None)
        exercise.pop("speaker_asset_ids", None)
        exercise.update({
            "expected_answers": [],
            "teacher_text": "MODEL_TURNS",
            "target_language_required": False,
            "response_mode": "model_only",
            "speaker_identity": None,
            "evidence_use": "presentation_only",
            "teacher_turns": [{
                "speaker": "Taro",
                "text": "Hello!",
                "asset_ids": ["page-01"] if isinstance(lesson.get("picture_book"), dict) else [],
            }],
        })
    if isinstance(lesson.get("picture_book"), dict):
        lesson["picture_book"]["pages"][0]["dialogue_turns"] = [{
            "id": "p01-t01",
            "speaker": "Taro",
            "text": "Hello!",
            "asset_ids": ["page-01"],
            "responds_to": None,
        }]
        lesson["picture_book"].update({
            "story_arc": {
                "initial_state_or_goal": "Ninereeds participates in one greeting exchange.",
                "meaningful_development": "The partner asks for and receives Ninereeds's identity.",
                "resolution_or_stopping_state": "The same exchange closes reciprocally.",
                "continuity_bindings": ["same partner", "same interaction"],
                "coherence_test": "Removing the identity response breaks the exchange before its reciprocal close.",
            },
            "world_grounding": {
                "selected_world_objective": "A greeting exchange preserves stable participant names.",
                "scored_world_claims": ["Ninereeds keeps the same name through the exchange."],
                "visual_safety_metadata": [],
                "forbidden_novelties": ["new biography"],
            },
            "identity_safety": {
                "first_person_default_identity": "Ninereeds",
                "l000_non_ninereeds_scored_first_person_forbidden": True,
                "quoted_character_completion_evidence": "never_self_identity_or_independent_first_person",
            },
        })
    lesson["vocabulary_plan"] = {
        "selection_basis": "point_coherence_stage_and_budget",
        "default_tested_item_count": 16,
        "selected_tested_item_count": 0,
        "set_size": 4,
        "sets": [],
        "rationale": "This fixture exercises a non-lexical self-identification Point.",
        "structural_exception": "Non-lexical communicative-act fixture; no tested referent set.",
    }
    lesson["assembly"] = {
        "mode": "handhold",
        "selection_packet_path": files["selection-packet"].name,
        "selection_packet_sha256": _sha(files["selection-packet"]),
        "conducted_entry_id": "L001",
        "conducted_sequence_number": 2,
    }
    lesson["authoring"] = {
        "actor": "luna",
        "prompt_path": files["luna-prompt"].name,
        "prompt_sha256": _sha(files["luna-prompt"]),
        "receipt_path": files["luna-receipt"].name,
        "receipt_sha256": _sha(files["luna-receipt"]),
    }
    lesson["independent_review"] = {
        "required": True,
        "reviewer_role": "sol",
        "decision": "pass",
        "rubric_id": "sol-lesson-assembly-review-v1",
        "receipt_path": files["sol-review"].name,
        "receipt_sha256": _sha(files["sol-review"]),
        "findings": [],
    }
    lesson["visual_plan"] = {
        "lesson_asset_root": "training_data/grounded_stories/assets/lessons/L001",
        "flux_max_attempts": 3,
        "operations": [],
    }
    lesson["adaptive"]["train_more"] = {
        "action": "TRAIN_MORE",
        "source": "preauthored_reserve_only",
        "reserve_ids": ["reserve-01"],
        "reserve_exercises": [{
            **lesson["phases"]["mixed_practice"][0],
            "id": "reserve-01",
        }],
        "release_rule": "Release one frozen reserve after a diagnosed gate-specific failure.",
        "max_items_per_gate": 1,
        "exhaustion": "defer_and_revisit",
    }
    lesson["adaptive"]["train_longer"] = {
        "action": "TRAIN_LONGER",
        "source": "frozen_ids_only",
        "eligible_item_ids": ["mixed-01"],
        "ordered_item_ids": ["mixed-01"],
        "ordering_rule": "Cycle frozen mixed IDs without an immediate duplicate.",
        "max_additional_items": 1,
        "no_immediate_duplicate": True,
        "stop_rule": "Stop after one added item or explicit stop.",
        "exhaustion": "defer_and_revisit",
    }
    lesson["adaptive"]["present_again"] = {
        "action": "PRESENT_AGAIN",
        "source": "frozen_presentation_ids_only",
        "presentation_ids": [exercise["id"] for exercise in lesson["phases"]["presentation"]],
        "release_rule": "Release after a diagnosed presentation-linked failure.",
        "maximum_total_uses": 1,
        "return_rule": "Return to one unmarked retest.",
        "exhaustion": "defer_and_revisit",
    }
    lesson["adaptive"]["mixed_practice_cap"] = 1
    lesson["adaptive"]["marker_intervention"]["max_scored_mixed_prompts"] = 1
    lesson["adaptive"]["mixed_execution"] = {
        "ordered_item_ids": ["mixed-01"],
        "denominator": 1,
        "minimum_successes": 1,
        "maximum_items": 1,
        "stop_rule": "Stop after the one frozen item.",
    }
    lesson["adaptive"]["replay_lesson"] = {
        "action": "REPLAY_LESSON",
        "release_rule": "Release once after the bounded lesson terminates below threshold.",
        "maximum_replays": 1,
        "stop_rule": "Stop after the one replay or earlier alarm.",
        "exhaustion": "defer_and_revisit",
    }
    lesson["adaptive"]["finish"] = {
        "action": "FINISH",
        "eligibility": "All frozen paths have terminated and no alarm is active.",
        "behavior": "close_lesson_write_report_no_further_prompts",
    }
    lesson["adaptive"]["alarm"] = {
        "action": "ALARM_FREEZE",
        "triggers": ["asset mismatch", "identity contradiction"],
        "behavior": "freeze_immediately_preserve_log_no_further_teacher_turns",
    }
    for action in ("TRAIN_MORE", "TRAIN_LONGER", "REPLAY_LESSON"):
        if action not in lesson["adaptive"]["controller_actions"]:
            lesson["adaptive"]["controller_actions"].append(action)
    execution_sequence = []
    for gate in ("affirmative", "negative", "W_question", "OR_question"):
        execution_sequence.append({"phase": "presentation", "exercise_ids": lesson["phases"]["presentation_bindings"][gate]})
        execution_sequence.append({"phase": gate, "exercise_ids": [item["id"] for item in lesson["phases"]["controlled_practice"][gate]]})
    book = lesson.get("picture_book") if isinstance(lesson.get("picture_book"), dict) else {"pages": [], "comprehension": []}
    execution_sequence.extend([
        {"phase": "mixed_practice", "exercise_ids": [item["id"] for item in lesson["phases"]["mixed_practice"]]},
        {"phase": "picture_book", "exercise_ids": [item["id"] for item in book["pages"]]},
        {"phase": "comprehension", "exercise_ids": [item["id"] for item in book["comprehension"]]},
        {"phase": "transfer", "exercise_ids": [item["id"] for item in lesson["phases"]["transfer"]]},
    ])
    lesson["phases"]["execution_sequence"] = execution_sequence
    return lesson


def test_v3_rejects_dialogue_only_even_when_legacy_v6_flag_says_no(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _upgrade_v3(tmp_path, _lesson(tmp_path, variant="dialogue_only"))
    errors = compiler.validate_lesson(lesson, "freeze")
    assert any("must use the complete picture_book format" in error for error in errors)


def test_v3_freeze_binds_luna_authoring_and_sol_review(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _upgrade_v3(tmp_path, _lesson(tmp_path, variant="picture_book"))
    lesson["phases"]["presentation"][0]["asset_ids"] = ["page-01"]
    lesson["visual_plan"]["operations"] = [_visual_operation(tmp_path)]
    assert compiler.validate_lesson(lesson, "freeze") == []
    source = tmp_path / "draft-v3.json"
    source.write_text(json.dumps(lesson), encoding="utf-8")
    output = tmp_path / "compiled-v3"
    compiler.compile_lesson(source, output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["conducted_sequence"]["entry_id"] == "L001"
    assert manifest["authoring_receipt_sha256"] == lesson["authoring"]["receipt_sha256"]
    assert manifest["independent_review_receipt_sha256"] == lesson["independent_review"]["receipt_sha256"]


def test_v3_freeze_rejects_pending_sol_review(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _upgrade_v3(tmp_path, _lesson(tmp_path, variant="picture_book"))
    lesson["phases"]["presentation"][0]["asset_ids"] = ["page-01"]
    lesson["visual_plan"]["operations"] = [_visual_operation(tmp_path)]
    lesson["independent_review"]["decision"] = "pending"
    errors = compiler.validate_lesson(lesson, "freeze")
    assert any("must equal pass to freeze" in error for error in errors)


def test_v3_presentation_is_modeled_without_fake_learner_response(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _upgrade_v3(tmp_path, _lesson(tmp_path, variant="picture_book"))
    lesson["phases"]["presentation"][0].update({
        "expected_answers": ["Yes, I'm Ninereeds."],
        "target_language_required": True,
        "response_mode": "learner_self",
        "speaker_identity": "Ninereeds",
        "evidence_use": "learner_identity_and_language",
    })
    errors = compiler.validate_lesson(lesson, "draft")
    assert any("presentation must be model_only" in error for error in errors)


def test_v3_requires_every_controlled_gate_to_have_a_local_presentation(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _upgrade_v3(tmp_path, _lesson(tmp_path, variant="picture_book"))
    lesson["phases"]["presentation_bindings"]["negative"] = []
    errors = compiler.validate_lesson(lesson, "draft")
    assert any("presentation_bindings.negative: must be a non-empty array" in error for error in errors)


def test_v3_rejects_front_loaded_presentation_order_disconnected_from_gates(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _upgrade_v3(tmp_path, _lesson(tmp_path, variant="picture_book"))
    bindings = lesson["phases"]["presentation_bindings"]
    bindings["affirmative"], bindings["negative"] = bindings["negative"], bindings["affirmative"]
    errors = compiler.validate_lesson(lesson, "draft")
    assert any("flattened gate order must equal the presentation array exactly" in error for error in errors)


def _visual_operation(root: Path, *, kind: str = "flux_generate") -> dict:
    operation_receipt = root / "visual-operation-receipt.json"
    verification_receipt = root / "pixel-verification-receipt.json"
    operation_receipt.write_text(json.dumps({"provider": "fixture", "accepted": True}), encoding="utf-8")
    verification_receipt.write_text(json.dumps({"claim": "two characters greet", "passed": True}), encoding="utf-8")
    return {
        "id": "visual-op-page-01",
        "type": kind,
        "status": "accepted",
        "teaching_claims": ["two characters greet"],
        "parent_asset_id": None,
        "output_asset_id": "page-01",
        "prompt": "Educational scene: two characters greet." if kind == "flux_generate" else None,
        "attempts": ["flux-attempt-001"] if kind == "flux_generate" else [],
        "crop_xywh": None,
        "receipt_path": operation_receipt.name,
        "receipt_sha256": _sha(operation_receipt),
        "verification": {
            "reviewer_role": "luna",
            "decision": "accepted",
            "claim_results": [{"claim": "two characters greet", "passed": True, "evidence": "Both figures are visible facing one another."}],
            "rejection_reasons": [],
            "receipt_path": verification_receipt.name,
            "receipt_sha256": _sha(verification_receipt),
        },
    }


def test_v3_visual_operation_freezes_exact_prompt_and_pixel_evidence(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _upgrade_v3(tmp_path, _lesson(tmp_path, variant="picture_book"))
    lesson["phases"]["presentation"][0]["asset_ids"] = ["page-01"]
    operation = _visual_operation(tmp_path)
    lesson["visual_plan"]["operations"] = [operation]
    assert compiler.validate_lesson(lesson, "freeze") == []


def test_v3_never_accepts_generative_work_as_literal_crop(tmp_path: Path) -> None:
    compiler = _load_compiler()
    compiler.REPO_ROOT = tmp_path
    lesson = _upgrade_v3(tmp_path, _lesson(tmp_path, variant="picture_book"))
    lesson["phases"]["presentation"][0]["asset_ids"] = ["page-01"]
    operation = _visual_operation(tmp_path, kind="literal_crop")
    operation["parent_asset_id"] = "page-01"
    operation["prompt"] = "Move the subjects closer together."
    operation["crop_xywh"] = [0, 0, 0, 64]
    lesson["visual_plan"]["operations"] = [operation]
    errors = compiler.validate_lesson(lesson, "freeze")
    assert any("deterministic operations cannot have a generative prompt" in error for error in errors)
    assert any("positive size" in error for error in errors)


def test_l001_phased_lexical_assembly_validates_as_draft() -> None:
    compiler = _load_compiler()
    lesson_path = ROOT / "output/lessons/L001-handhold-attempt-002/stages/06-assembly/lesson-draft-luna-phased-006.json"
    lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
    assert compiler.validate_lesson(lesson, "draft") == []


def test_lexical_negative_requires_frozen_displayed_mismatch() -> None:
    compiler = _load_compiler()
    lesson_path = ROOT / "output/lessons/L001-handhold-attempt-001/stages/06-assembly/lesson-draft-luna-phased-003.json"
    lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
    lesson["phases"]["controlled_practice"]["negative"][0]["nonverbal_control"].pop("displayed_mismatch_label")
    errors = compiler.validate_lesson(lesson, "draft")
    assert any("displayed_mismatch_label" in error for error in errors)


def test_lexical_gate_execution_binds_two_reserves() -> None:
    compiler = _load_compiler()
    lesson_path = ROOT / "output/lessons/L001-handhold-attempt-001/stages/06-assembly/lesson-draft-luna-phased-003.json"
    lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
    lesson["adaptive"]["train_more"]["gate_execution"]["affirmative"]["reserve_exercise_ids"] = []
    errors = compiler.validate_lesson(lesson, "draft")
    assert any("reserve_exercise_ids" in error for error in errors)


def test_story_active_object_check_must_use_all_frontier_labels() -> None:
    compiler = _load_compiler()
    lesson_path = ROOT / "output/lessons/L001-handhold-attempt-001/stages/06-assembly/lesson-draft-luna-phased-003.json"
    lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
    lesson["picture_book"]["comprehension"][0]["nonverbal_control"]["options"].pop()
    errors = compiler.validate_lesson(lesson, "draft")
    assert any("exactly 4 closed options" in error for error in errors)


def test_lexical_selection_rejects_answer_outside_closed_options() -> None:
    compiler = _load_compiler()
    lesson_path = ROOT / "output/lessons/L001-handhold-attempt-001/stages/06-assembly/lesson-draft-luna-phased-002.json"
    lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
    lesson["phases"]["controlled_practice"]["affirmative"][0]["expected_answers"] = ["not-a-visible-option"]
    errors = compiler.validate_lesson(lesson, "draft")
    assert any("must name exactly one closed option" in error for error in errors)


def test_lexical_story_comprehension_rejects_nonadjacent_answer() -> None:
    validator = _load_stage_validator()
    stage_path = ROOT / "output/lessons/L001-handhold-attempt-001/stages/04-comprehension/story-comprehension-luna-medium-001.json"
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    stage["narrative_comprehension_checks"][0]["expected_option_ids"] = ["next-distractor-p05"]
    errors = validator.validate_comprehension(stage)
    assert any("actual adjacent page" in error for error in errors)
