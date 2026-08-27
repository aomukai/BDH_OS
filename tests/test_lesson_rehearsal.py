from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "mission_hub" / "skills" / "compile-next-lesson" / "scripts" / "rehearse_lesson.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("ninereeds_lesson_rehearsal", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lesson(root: Path, *, variant: str) -> dict:
    source = ROOT / "tests" / "test_lesson_compiler.py"
    spec = importlib.util.spec_from_file_location("lesson_compiler_test_fixtures", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._lesson(root, variant=variant)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _spec(tmp_path: Path, *, variant: str = "dialogue_only") -> tuple[Path, dict]:
    lesson = _lesson(tmp_path, variant=variant)
    lesson_path = _write(tmp_path / "lesson.json", lesson)
    teaching = ROOT / "mission_hub" / "wiki" / "teaching.md"
    value = {
        "schema_version": "ninereeds_lesson_rehearsal_spec_v1",
        "rehearsal_id": "rehearsal-fixture-001",
        "lesson_path": lesson_path.name,
        "lesson_sha256": _sha(lesson_path),
        "scenario_id": "ordinary-correct",
        "random_seed": 7,
        "luna": {"role": "luna_teacher", "model_id": "luna-fixture", "reasoning_effort": "medium", "prompt_sha256": "1" * 64},
        "luna_reporter": {"role": "luna_post_lesson_analyst", "model_id": "luna-fixture", "reasoning_effort": "xhigh", "prompt_sha256": "5" * 64},
        "sol": {"role": "sol_learner_simulator", "model_id": "sol-fixture", "reasoning_effort": "high", "prompt_sha256": "2" * 64},
        "verifier": {
            "role": "sol_independent_reviewer",
            "reviewer_id": "sol-review-session-fixture",
            "model_id": "sol-fixture",
            "prompt_sha256": "3" * 64,
            "rubric_sha256": "4" * 64,
            "context_policy": "fresh_context_anonymized_actors_lesson_level_script_log_and_wiki",
        },
        "effort_escalation": {
            "target_role": "lesson_conductor",
            "ladder": ["medium", "high", "xhigh", "max"],
            "attempt_index": 0,
            "current_effort": "medium",
            "max_failure_outcome": "terminal_model_capability_failure",
        },
        "review_wiki_bindings": [{"role": "teaching_methodology", "path": str(teaching), "sha256": _sha(teaching)}],
        "learner_profile": {
            "conducted_sequence_number": 1,
            "learner_state_artifact_id": "learner-state-fixture",
            "learner_state_path": "learner_state.json",
            "learner_state_sha256": _sha(tmp_path / "learner_state.json"),
            "known_closure_path": "known_closure.json",
            "known_closure_sha256": _sha(tmp_path / "known_closure.json"),
            "stage_description": "At the first lesson boundary with no later curriculum knowledge.",
            "epistemic_baseline": {
                "approximate_parameters_billion": 1.2,
                "prior_image_exposures": 30000,
                "prior_word_form_exposures": 3000,
                "grounding_at_lesson_zero": "none",
                "system_at_lesson_zero": "none",
                "grammar_at_lesson_zero": "none",
                "context_at_lesson_zero": "none",
                "model_initialization": "random_1_2b_parameters",
                "encoder_training_effect": "can_read_siglip2_and_lfm_encoder_vectors_not_bankable_semantics",
                "prior_learning_treatment": "untrusted_bonus_never_prerequisite_without_deliberate_evidence",
                "exposure_implication": "no_meaning_or_knowledge_without_deliberate_grounded_evidence",
            },
            "simulation_mode": "calibrated_estimate",
            "hidden_behavior_profile": "Respond correctly to the first prompt, then ask for clarification if focus is ambiguous.",
        },
        "required_phases": ["presentation"],
        "allowed_tools": ["SHOW_ASSET", "SHOW_CROP", "SHOW_HIGHLIGHT", "REPLAY_PRESENTATION", "USE_MARKERS", "ASK_BOUNDED_CLARIFICATION", "CHECK_UNDERSTANDING", "TRAIN_MORE", "TRAIN_LONGER", "ALARM"],
        "teacher_language_policy": {
            "known_forms": ["Hello!", "Are you Ninereeds?"],
            "frontier_forms": ["I'm Ninereeds."],
            "instruction_phrases": ["Look.", "Your turn."],
            "rescue_phrases": ["I will show it again."],
            "comprehension_check_required": True,
            "unlicensed_language_action": "ALARM",
        },
        "budgets": {"max_teacher_turns": 4, "max_student_turns": 4, "max_tool_calls": 4},
        "parent_run_manifest_path": None,
        "parent_run_manifest_sha256": None,
        "repair_receipt_path": None,
        "repair_receipt_sha256": None,
    }
    return _write(tmp_path / "rehearsal-spec.json", value), value


def _teacher_event(
    *,
    action: str = "present",
    unlicensed: list[str] | None = None,
    phase: str = "presentation",
    exercise_id: str = "presentation-01",
) -> dict:
    return {
        "event_type": "teacher_turn",
        "actor": "luna",
        "phase": phase,
        "exercise_id": exercise_id,
        "payload": {
            "action": action,
            "delivery_mode": "spoken",
            "text": "Are you Ninereeds?",
            "script_ref": f"{exercise_id}/teacher_turn_1",
            "claim_ids": [],
            "language_receipt": {
                "known_forms": ["Are you Ninereeds?"],
                "frontier_forms": [],
                "instruction_phrases": [],
                "rescue_phrases": [],
                "unlicensed_forms": unlicensed or [],
            },
        },
    }


def _student_event() -> dict:
    return {
        "event_type": "student_turn",
        "actor": "sol",
        "phase": "presentation",
        "exercise_id": "presentation-01",
        "payload": {
            "text": "Hello!",
            "behavior_tag": "correct",
            "simulator_basis": "hidden_profile_and_known_closure",
        },
    }


def test_brokered_exchange_enforces_role_separation(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, _ = _spec(tmp_path)
    run = tmp_path / "run-brokered"
    harness.init_run(spec_path, run)
    teacher_path = tmp_path / "teacher-events.json"
    student_path = tmp_path / "student-events.json"
    teacher_path.write_text(json.dumps([_teacher_event()]), encoding="utf-8")
    student_path.write_text(json.dumps([_student_event()]), encoding="utf-8")
    harness.append_exchange(run, teacher_path, student_path)
    state = json.loads((run / "state.json").read_text())
    assert state["teacher_turns"] == 1
    assert state["student_turns"] == 1
    assert state["expected_actor"] == "luna"


def test_brokered_exchange_rejects_teacher_authored_student_turn(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, _ = _spec(tmp_path)
    run = tmp_path / "run-brokered-role-error"
    harness.init_run(spec_path, run)
    teacher_path = tmp_path / "teacher-events-bad.json"
    student_path = tmp_path / "student-events.json"
    teacher_path.write_text(json.dumps([_teacher_event(), _student_event()]), encoding="utf-8")
    student_path.write_text(json.dumps([_student_event()]), encoding="utf-8")
    with pytest.raises(ValueError, match="teacher exchange may contain only Luna"):
        harness.append_exchange(run, teacher_path, student_path)
    assert json.loads((run / "state.json").read_text())["last_sequence"] == 1


def test_brokered_exchange_rejects_invalid_block_atomically(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, _ = _spec(tmp_path)
    run = tmp_path / "run-brokered-atomic"
    harness.init_run(spec_path, run)
    second_teacher = _teacher_event()
    invalid_tool = _tool_event("SHOW_ASSET", {"asset_id": "not-a-licensed-asset"})
    teacher_path = tmp_path / "teacher-events-invalid-block.json"
    student_path = tmp_path / "student-events-two.json"
    teacher_path.write_text(json.dumps([_teacher_event(), invalid_tool, second_teacher]), encoding="utf-8")
    student_path.write_text(json.dumps([_student_event(), _student_event()]), encoding="utf-8")
    with pytest.raises(ValueError, match="rejected atomically"):
        harness.append_exchange(run, teacher_path, student_path)
    state = json.loads((run / "state.json").read_text())
    assert state["status"] == "alarm_frozen"
    assert state["last_sequence"] == 2
    assert state["teacher_turns"] == 0
    assert state["student_turns"] == 0
    assert state["tool_calls"] == 0


def test_present_again_allows_only_dispatched_presentation_rewind(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, spec = _spec(tmp_path)
    lesson_path = tmp_path / spec["lesson_path"]
    lesson = json.loads(lesson_path.read_text())
    lesson["adaptive"]["present_again"] = {
        "dispatch_table": {
            "affirmative-01": {
                "gate": "affirmative",
                "presentation_id": "presentation-01",
                "cold_retest_exercise_id": "affirmative-01-cold-retest",
            }
        },
        "retest_exercises": [
            {**lesson["phases"]["controlled_practice"]["affirmative"][0], "id": "affirmative-01-cold-retest"}
        ],
    }
    lesson_path.write_text(json.dumps(lesson), encoding="utf-8")
    spec["lesson_sha256"] = _sha(lesson_path)
    spec["required_phases"] = ["presentation", "affirmative"]
    spec["allowed_tools"].append("PRESENT_AGAIN")
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    run = tmp_path / "run-present-again-rewind"
    harness.init_run(spec_path, run)
    harness.append_interaction(run, _write(tmp_path / "presentation-teacher.json", _teacher_event()))
    harness.append_interaction(run, _write(tmp_path / "presentation-student.json", _student_event()))
    initial_teacher = _teacher_event(phase="affirmative", exercise_id="affirmative-01")
    initial_student = _student_event()
    initial_student["phase"] = "affirmative"
    initial_student["exercise_id"] = "affirmative-01"
    harness.append_interaction(run, _write(tmp_path / "initial-teacher.json", initial_teacher))
    harness.append_interaction(run, _write(tmp_path / "initial-student.json", initial_student))
    dispatch = _tool_event("PRESENT_AGAIN", {
        "gate": "affirmative",
        "presentation_id": "presentation-01",
        "cold_retest_exercise_id": "affirmative-01-cold-retest",
    })
    dispatch["phase"] = "affirmative"
    dispatch["exercise_id"] = "affirmative-01"
    harness.append_interaction(run, _write(tmp_path / "present-again.json", dispatch))
    harness.append_interaction(run, _write(tmp_path / "rewind-teacher.json", _teacher_event()))
    harness.append_interaction(run, _write(tmp_path / "rewind-student.json", _student_event()))
    cold_teacher = _teacher_event(phase="affirmative", exercise_id="affirmative-01-cold-retest")
    cold_student = _student_event()
    cold_student["phase"] = "affirmative"
    cold_student["exercise_id"] = "affirmative-01-cold-retest"
    harness.append_interaction(run, _write(tmp_path / "cold-teacher.json", cold_teacher))
    harness.append_interaction(run, _write(tmp_path / "cold-student.json", cold_student))
    state = json.loads((run / "state.json").read_text())
    assert state["status"] == "active"
    assert state["present_again_dispatch"] is None


def test_teacher_artifact_rejects_duplicate_exact_script_ref(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, _ = _spec(tmp_path)
    run = tmp_path / "run-duplicate-teacher-ref"
    harness.init_run(spec_path, run)
    artifact = tmp_path / "duplicate-teacher-artifact.json"
    artifact.write_text(json.dumps([_teacher_event(), _teacher_event()]), encoding="utf-8")
    with pytest.raises(ValueError, match="already emitted"):
        harness.lint_teacher_artifact(run, artifact)
    assert json.loads((run / "state.json").read_text())["status"] == "active"


def test_teacher_artifact_keeps_scored_work_item_atomic(tmp_path: Path) -> None:
    harness = _load_harness()
    lesson = _lesson(tmp_path, variant="dialogue_only")
    first = _teacher_event(phase="affirmative", exercise_id="affirmative-01")
    second = _teacher_event(phase="negative", exercise_id="negative-01")
    with pytest.raises(ValueError, match="at most one scored exercise"):
        harness.validate_teacher_artifact_granularity([first, second], lesson)

    # A multi-turn model plus its unscored interface check remains one safe block.
    lesson["phases"]["presentation"][0]["expected_answers"] = []
    harness.validate_teacher_artifact_granularity([_teacher_event(), _teacher_event()], lesson)


def test_l001_presentation_requires_exact_frozen_turn_binding() -> None:
    harness = _load_harness()
    lesson_path = ROOT / "output" / "lessons" / "L001-handhold-attempt-002" / "stages" / "08-rehearsal" / "lesson-static-approved-002.json"
    lesson = json.loads(lesson_path.read_text(encoding="utf-8"))
    state = {"emitted_teacher_script_refs": [], "present_again_dispatch": None}
    event = {
        "event_type": "teacher_turn",
        "actor": "luna",
        "phase": "presentation",
        "exercise_id": "l001-p1-affirmative-model",
        "payload": {
            "action": "present",
            "delivery_mode": "machine_control",
            "text": "WORKED_affirmative",
            "script_ref": "l001-p1-affirmative-model",
            "claim_ids": [],
            "language_receipt": {
                "known_forms": [], "frontier_forms": [], "instruction_phrases": [],
                "rescue_phrases": [], "unlicensed_forms": [],
            },
        },
    }
    with pytest.raises(ValueError, match="exact frozen exercise"):
        harness.validate_teacher_script_binding(event, state, lesson)
    event["payload"].update({
        "delivery_mode": "spoken",
        "text": "cup",
        "script_ref": "l001-p1-affirmative-model/teacher_turn_1",
    })
    harness.validate_teacher_script_binding(event, state, lesson)


def test_teacher_artifact_lint_is_non_mutating_and_checks_receipts(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, _ = _spec(tmp_path)
    run = tmp_path / "run-teacher-lint"
    harness.init_run(spec_path, run)
    valid_path = tmp_path / "valid-teacher-artifact.json"
    valid_path.write_text(json.dumps([_teacher_event()]), encoding="utf-8")
    harness.lint_teacher_artifact(run, valid_path)
    assert json.loads((run / "state.json").read_text())["last_sequence"] == 1
    invalid = _teacher_event()
    invalid["payload"]["language_receipt"]["known_forms"] = ["Hello."]
    invalid_path = tmp_path / "invalid-teacher-artifact.json"
    invalid_path.write_text(json.dumps([invalid]), encoding="utf-8")
    with pytest.raises(ValueError, match="outside the frozen policy"):
        harness.lint_teacher_artifact(run, invalid_path)
    assert json.loads((run / "state.json").read_text())["status"] == "active"


def test_lesson_index_uses_execution_sequence_phase_for_closing_recap(tmp_path: Path) -> None:
    harness = _load_harness()
    lesson = _lesson(tmp_path, variant="dialogue_only")
    recap = {
        "id": "closing-recap-01",
        "asset_ids": [],
        "teacher_text": "MACHINE_CONTROL",
    }
    lesson["phases"]["transfer"] = [recap]
    lesson["phases"]["execution_sequence"] = [
        {"phase": "closing_recap", "exercise_ids": ["closing-recap-01"]}
    ]

    exercises, _, _, _ = harness.lesson_index(lesson)

    assert exercises["closing-recap-01"] == "closing_recap"


def _tool_event(tool: str, arguments: dict | None = None) -> dict:
    return {
        "event_type": "tool_call",
        "actor": "luna",
        "phase": "presentation",
        "exercise_id": "presentation-01",
        "payload": {"tool": tool, "arguments": arguments or {}, "reason": "The protocol requires this action."},
    }


def test_train_more_has_bounded_payload(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, spec = _spec(tmp_path)
    lesson_path = tmp_path / spec["lesson_path"]
    lesson = json.loads(lesson_path.read_text())
    lesson["adaptive"]["train_more"] = {"reserve_exercises": [{"id": "aff-r01"}]}
    lesson_path.write_text(json.dumps(lesson), encoding="utf-8")
    spec["lesson_sha256"] = _sha(lesson_path)
    spec["required_phases"] = ["presentation", "affirmative"]
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    run = tmp_path / "run-interventions"
    harness.init_run(spec_path, run)
    train_more = _tool_event("TRAIN_MORE", {
        "gate": "affirmative",
        "reserve_exercise_id": "aff-r01",
        "decision_basis": "The learner failed a new valid example after presentation.",
    })
    train_more["phase"] = "affirmative"
    train_more["exercise_id"] = "affirmative-01"
    event_path = _write(tmp_path / "train-more.json", train_more)
    harness.append_interaction(run, event_path)
    state = json.loads((run / "state.json").read_text())
    assert state["current_phase"] is None
    assert state["current_exercise_id"] is None
    assert json.loads((run / "state.json").read_text())["tool_calls"] == 1


def test_train_longer_requires_a_bounded_varied_mixed_loop(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, spec = _spec(tmp_path)
    lesson_path = tmp_path / spec["lesson_path"]
    lesson = json.loads(lesson_path.read_text())
    mixed_template = lesson["phases"]["mixed_practice"][0]
    lesson["phases"]["mixed_practice"] = [
        {**mixed_template, "id": f"mixed-{index:02d}"} for index in range(1, 5)
    ]
    lesson["adaptive"]["train_longer"] = {
        "ordered_item_ids": ["mixed-01", "mixed-03", "mixed-02", "mixed-04"]
    }
    lesson_path.write_text(json.dumps(lesson), encoding="utf-8")
    spec["lesson_sha256"] = _sha(lesson_path)
    spec["required_phases"] = ["presentation", "mixed_practice"]
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    run = tmp_path / "run-train-longer"
    harness.init_run(spec_path, run)
    event = {
        "event_type": "tool_call",
        "actor": "luna",
        "phase": "mixed_practice",
        "exercise_id": "mixed-01",
        "payload": {
            "tool": "TRAIN_LONGER",
            "arguments": {
                "exercise_ids": ["mixed-01", "mixed-03", "mixed-02", "mixed-04"],
                "ordering": "frozen_order",
                "stop_after": 4,
                "decision_basis": "Mixed performance remains unstable without a presentation failure.",
            },
            "reason": "Extend varied mixed practice within the frozen cap.",
        },
    }
    harness.append_interaction(run, _write(tmp_path / "train-longer.json", event))
    assert json.loads((run / "state.json").read_text())["tool_calls"] == 1


def _passing_verdict(packet: Path) -> dict:
    return {
        "schema_version": "ninereeds_lesson_rehearsal_verdict_v1",
        "verifier_id": "sol-review-session-fixture",
        "review_packet_sha256": _sha(packet),
        "decision": "pass",
        "report_disposition": "luna_verified",
        "report_corrections": [],
        "dimensions": {
            "lesson_plan_waterproof": True,
            "point_topic_integrity": True,
            "material_scope_judgment": True,
            "structural_completeness": True,
            "picture_book_application": True,
            "luna_routine": True,
            "intervention_judgment": True,
            "teacher_self_assessment_calibration": True,
            "teacher_language_closure": True,
            "developmental_stage_fidelity": True,
            "protocol_integrity": True,
            "visual_grounding": True,
            "learner_simulation_fidelity": True,
        },
        "failures": [],
        "notes": [],
    }


def _failed_verdict(packet: Path, event_sequence: int) -> dict:
    return {
        "schema_version": "ninereeds_lesson_rehearsal_verdict_v1",
        "verifier_id": "sol-review-session-fixture",
        "review_packet_sha256": _sha(packet),
        "decision": "fail",
        "report_disposition": "luna_verified",
        "report_corrections": [],
        "dimensions": {
            "lesson_plan_waterproof": False,
            "point_topic_integrity": True,
            "material_scope_judgment": True,
            "structural_completeness": True,
            "picture_book_application": True,
            "luna_routine": True,
            "intervention_judgment": True,
            "teacher_self_assessment_calibration": True,
            "teacher_language_closure": True,
            "developmental_stage_fidelity": True,
            "protocol_integrity": False,
            "visual_grounding": False,
            "learner_simulation_fidelity": True,
        },
        "failures": [{
            "category": "visual_material",
            "code": "missing_literal_crop",
            "event_sequence": event_sequence,
            "severity": "major",
            "explanation": "The requested focus crop was not prepared.",
            "repair_target": "Add and verify a literal_crop operation to the lesson.",
        }],
        "notes": ["The teacher correctly stopped instead of improvising pixels."],
    }


def _luna_report(run: Path, lesson_sha256: str, rehearsal_id: str = "rehearsal-fixture-001") -> dict:
    return {
        "schema_version": "ninereeds_luna_post_lesson_report_v1",
        "rehearsal_id": rehearsal_id,
        "lesson_sha256": lesson_sha256,
        "author_role": "luna_post_lesson_analyst",
        "overall_assessment": "indeterminate",
        "phase_assessment": [],
        "learner_capability_hypotheses": [],
        "remaining_difficulties": [],
        "uncertainties": ["This minimal fixture does not establish a durable capability."],
        "intervention_assessment": [],
        "teacher_self_critique": ["A longer trace would be needed for a capability claim."],
        "alarm_assessment": "No positive capability conclusion is warranted from the fixture alone.",
        "proposed_closure_changes": [],
        "next_lesson_implications": ["Retain the previous closure until independent review."],
        "rehearsal_nonadvancement": "hypotheses_only_no_learner_state_advance",
    }


def test_rehearsal_happy_path_is_logged_reviewed_and_anonymized(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, _ = _spec(tmp_path)
    run = tmp_path / "run"
    harness.init_run(spec_path, run)
    for name, event in (
        ("teacher", _teacher_event()),
        ("check", _tool_event("CHECK_UNDERSTANDING")),
        ("student", _student_event()),
    ):
        harness.append_interaction(run, _write(tmp_path / f"{name}.json", event))
    state = json.loads((run / "state.json").read_text())
    harness.make_reporter_packet(run)
    reporter_packet = (run / "reporter-packet.json").read_text(encoding="utf-8")
    assert '"hidden_behavior_profile"' not in reporter_packet
    assert "luna-fixture" not in reporter_packet
    assert "sol-fixture" not in reporter_packet
    assert "student_simulator_hidden_behavior_profile" in reporter_packet
    report_path = _write(tmp_path / "luna-report.json", _luna_report(run, state["lesson_sha256"]))
    harness.record_luna_report(run, report_path)
    harness.make_review_packet(run)
    packet_path = run / "review-packet.json"
    rendered = packet_path.read_text(encoding="utf-8")
    assert "luna-fixture" not in rendered
    assert "sol-fixture" not in rendered
    assert "hidden_behavior_profile" not in rendered
    assert "teaching_methodology" in rendered
    harness.finalize(run, _write(tmp_path / "verdict.json", _passing_verdict(packet_path)))
    assert harness.verify_run(run)["status"] == "passed"
    manifest = run / "manifest.json"
    suite_spec = _write(tmp_path / "suite.json", {
        "schema_version": "ninereeds_lesson_rehearsal_suite_v1",
        "suite_id": "suite-fixture-001",
        "lesson_sha256": json.loads(manifest.read_text())["lesson_sha256"],
        "required_scenarios": ["ordinary-correct"],
        "runs": [{"scenario_id": "ordinary-correct", "manifest_path": str(manifest), "manifest_sha256": _sha(manifest)}],
        "pass_rule": "all_required_scenarios_pass",
    })
    suite_receipt = tmp_path / "suite-receipt.json"
    harness.assemble_suite(suite_spec, suite_receipt)
    assert json.loads(suite_receipt.read_text())["status"] == "passed"


def test_successful_teaching_can_require_sol_report_reconstruction(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, _ = _spec(tmp_path)
    run = tmp_path / "run-report-fallback"
    harness.init_run(spec_path, run)
    for name, event in (
        ("teacher", _teacher_event()),
        ("check", _tool_event("CHECK_UNDERSTANDING")),
        ("student", _student_event()),
    ):
        harness.append_interaction(run, _write(tmp_path / f"fallback-{name}.json", event))
    state = json.loads((run / "state.json").read_text())
    harness.record_luna_report(run, _write(tmp_path / "fallback-report.json", _luna_report(run, state["lesson_sha256"])))
    harness.make_review_packet(run)
    verdict = _passing_verdict(run / "review-packet.json")
    verdict["dimensions"]["teacher_self_assessment_calibration"] = False
    verdict["report_disposition"] = "sol_reconstruction_required"
    verdict["report_corrections"] = ["Separate prompted repetition from independent capability."]
    harness.finalize(run, _write(tmp_path / "fallback-verdict.json", verdict))
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["terminal_status"] == "passed"
    assert manifest["report_disposition"] == "sol_reconstruction_required"


@pytest.mark.parametrize(
    "event",
    [
        _teacher_event(action="freestyle_new_lesson"),
        _teacher_event(unlicensed=["metalinguistic explanation Ninereeds does not know"]),
    ],
)
def test_freestyle_or_unlicensed_teacher_language_alarm_freezes(tmp_path: Path, event: dict) -> None:
    harness = _load_harness()
    spec_path, _ = _spec(tmp_path)
    run = tmp_path / "run"
    harness.init_run(spec_path, run)
    with pytest.raises(ValueError, match="alarm-froze"):
        harness.append_interaction(run, _write(tmp_path / "bad-event.json", event))
    assert json.loads((run / "state.json").read_text())["status"] == "alarm_frozen"
    with pytest.raises(ValueError, match="terminal"):
        harness.append_interaction(run, _write(tmp_path / "later.json", _teacher_event()))


def test_missing_crop_alarm_is_diagnosed_and_repair_rerun_is_linked(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, spec = _spec(tmp_path, variant="picture_book")
    run = tmp_path / "run"
    harness.init_run(spec_path, run)
    bad_crop = _tool_event("SHOW_CROP", {"asset_id": "page-01"})
    with pytest.raises(ValueError, match="alarm-froze"):
        harness.append_interaction(run, _write(tmp_path / "crop.json", bad_crop))
    state = json.loads((run / "state.json").read_text())
    report_path = _write(tmp_path / "luna-alarm-report.json", _luna_report(run, state["lesson_sha256"]))
    harness.record_luna_report(run, report_path)
    harness.make_review_packet(run)
    state = json.loads((run / "state.json").read_text())
    harness.finalize(run, _write(tmp_path / "failed-verdict.json", _failed_verdict(run / "review-packet.json", state["alarm_sequence"])))
    manifest = run / "manifest.json"
    repaired_lesson_value = json.loads((tmp_path / "lesson.json").read_text())
    repaired_lesson_value["selection"]["rationale"] += " A literal crop was added after rehearsal diagnosis."
    repaired_lesson = _write(tmp_path / "lesson-repaired.json", repaired_lesson_value)
    repair = _write(tmp_path / "repair.json", {
        "schema_version": "ninereeds_lesson_rehearsal_repair_receipt_v1",
        "parent_manifest_sha256": _sha(manifest),
        "failure_codes": ["missing_literal_crop"],
        "root_causes": ["visual_material"],
        "changed_artifacts": [{"path": repaired_lesson.name, "before_sha256": spec["lesson_sha256"], "after_sha256": _sha(repaired_lesson)}],
        "repair_rationale": "Bind the changed lesson bytes to the diagnosed visual-material failure.",
        "approved_by": "operator-fixture",
    })
    rerun_spec = json.loads(spec_path.read_text())
    rerun_spec["rehearsal_id"] = "rehearsal-fixture-002"
    rerun_spec["lesson_path"] = repaired_lesson.name
    rerun_spec["lesson_sha256"] = _sha(repaired_lesson)
    rerun_spec["parent_run_manifest_path"] = str(manifest)
    rerun_spec["parent_run_manifest_sha256"] = _sha(manifest)
    rerun_spec["repair_receipt_path"] = str(repair)
    rerun_spec["repair_receipt_sha256"] = _sha(repair)
    rerun_path = _write(tmp_path / "rerun-spec.json", rerun_spec)
    harness.init_run(rerun_path, tmp_path / "rerun")
    frozen = json.loads((tmp_path / "rerun" / "spec.json").read_text())
    assert frozen["parent_run_manifest_sha256"] == _sha(manifest)


def test_event_log_tampering_is_detected(tmp_path: Path) -> None:
    harness = _load_harness()
    spec_path, _ = _spec(tmp_path)
    run = tmp_path / "run"
    harness.init_run(spec_path, run)
    events = run / "events.jsonl"
    events.write_text(events.read_text().replace("run_started", "run_changed"), encoding="utf-8")
    with pytest.raises(ValueError, match="event chain mismatch"):
        harness.verify_run(run)


def test_machine_control_license_covers_demo_and_scored_action_sequences() -> None:
    harness = _load_harness()
    control = {
        "machine_action": "SELECT_VISUAL",
        "scored_action_sequence": ["SHOW_CONTEXT", "RECORD_SELECTION"],
        "demonstrations": [{
            "replay_text": "VISUAL_DEMONSTRATION_ONLY",
            "feedback_action": "SHOW_CORRECT_OPTION",
            "action_sequence": ["SHOW_DEMO_CONTEXT", "SHOW_OPTIONS"],
        }],
    }
    assert harness.licensed_machine_texts(control) == {
        "SELECT_VISUAL",
        "SHOW_CONTEXT",
        "RECORD_SELECTION",
        "VISUAL_DEMONSTRATION_ONLY",
        "SHOW_CORRECT_OPTION",
        "SHOW_DEMO_CONTEXT",
        "SHOW_OPTIONS",
    }
