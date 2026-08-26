from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "mission_hub" / "skills" / "compile-next-lesson" / "scripts" / "compile_lesson.py"


def _load_compiler():
    spec = importlib.util.spec_from_file_location("ninereeds_lesson_compiler", SCRIPT)
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
