import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from mission_hub.research_wiki import lint, page_metadata
from mission_hub.research.source_inventory import build_census, candidate_paths


ROOT = Path(__file__).resolve().parents[1]


def test_commissioned_research_wiki_lints_cleanly() -> None:
    result = lint(ROOT)
    assert result["errors"] == []
    assert result["ok"] is True
    assert result["source_count"] == 11
    assert result["page_count"] == 10
    assert result["planning_step_count"] == 10
    assert result["source_candidate_count"] >= 88


def test_wiki_metadata_is_machine_readable() -> None:
    metadata = page_metadata(ROOT / "mission_hub" / "wiki" / "index.md")
    assert metadata["page_id"] == "wiki-index"
    assert metadata["page_type"] == "index"


def _schema(name: str) -> dict:
    path = ROOT / "mission_hub" / "research" / "schemas" / name
    value = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(value)
    return value


def test_positive_question_answer_requires_evidence_and_boundary() -> None:
    validator = Draft202012Validator(_schema("question-review.schema.json"))
    value = {
        "schema_version": "ninereeds_question_review_v1",
        "question_id": "rq-0041-03",
        "epistemic_answer": "yes_supported",
        "explanation": "The preregistered transfer threshold was met.",
        "artifact_ids": [],
        "applicability_boundary": None,
        "confidence": "high",
        "lifecycle_disposition": "retire_answered",
        "successor_questions": [],
    }
    with pytest.raises(ValidationError):
        validator.validate(value)
    value["artifact_ids"] = ["art-evaluation"]
    value["applicability_boundary"] = "Unseen objects under the registered prompt family."
    validator.validate(value)


def test_not_tested_is_a_valid_complete_answer_without_artifacts() -> None:
    Draft202012Validator(_schema("question-review.schema.json")).validate({
        "schema_version": "ninereeds_question_review_v1",
        "question_id": "rq-0041-03",
        "epistemic_answer": "not_tested",
        "explanation": "No persistence evaluation artifact was produced.",
        "artifact_ids": [],
        "applicability_boundary": None,
        "confidence": "not_applicable",
        "lifecycle_disposition": "repeat_with_better_evidence",
        "successor_questions": [],
    })


def test_librarian_findings_contract_forbids_answering_questions() -> None:
    validator = Draft202012Validator(_schema("campaign-findings.schema.json"))
    finding = {
        "schema_version": "ninereeds_campaign_findings_v1",
        "campaign_id": "campaign-0041",
        "campaign_contract_hash": "a" * 64,
        "closure_status": "completed",
        "artifacts": [],
        "observations": [],
        "operational_anomalies": [],
        "question_evidence_index": [],
        "librarian_answered_research_questions": False,
    }
    validator.validate(finding)
    finding["librarian_answered_research_questions"] = True
    with pytest.raises(ValidationError):
        validator.validate(finding)


def test_transition_example_uses_valid_question_dispositions() -> None:
    example = json.loads((
        ROOT / "mission_hub" / "research" / "examples" /
        "campaign-transition-example.json"
    ).read_text(encoding="utf-8"))
    validator = Draft202012Validator(_schema("question-review.schema.json"))
    assert example["example_only"] is True
    for review in example["question_reviews"]:
        validator.validate(review)


def test_campaign_goals_preregister_question_boundaries_and_controls() -> None:
    Draft202012Validator(_schema("campaign-goals.schema.json")).validate({
        "schema_version": "ninereeds_campaign_goals_v1",
        "campaign_id": "campaign-0042",
        "predecessor_campaign_id": "campaign-0041",
        "mission": "Map transfer after four controlled examples.",
        "goals": ["Separate trained-form change from unseen-object transfer."],
        "goal_selection_rationale": "Campaign 41 conflated several meanings of learning.",
        "research_purpose": "boundary_mapping",
        "execution_design": "controlled_ablation",
        "questions": [{
            "question_id": "rq-0042-01",
            "question": "Do four examples transfer to unseen objects?",
            "origin_question_ids": ["rq-0041-03"],
            "scope": "The registered object family and prompt forms.",
            "yes_criterion": "The preregistered held-out threshold is met.",
            "no_criterion": "Performance remains at the preregistered baseline.",
            "required_observations": ["Held-out object evaluation."],
            "expected_artifact_roles": ["behavioral_evaluation"],
        }],
        "controls": ["Matched zero-example baseline."],
        "seeds": [42001, 42002],
        "stopping_rules": ["Stop if the campaign artifact contract is violated."],
        "retained_capability_checks": ["Run protected identity and language probes."],
        "authorization_status": "proposed_not_authorized",
    })


def test_prerequisite_work_examples_are_schema_valid_and_non_authorizing() -> None:
    examples = json.loads((
        ROOT / "mission_hub" / "research" / "examples" /
        "prerequisite-work-examples.json"
    ).read_text(encoding="utf-8"))
    validator = Draft202012Validator(_schema("prerequisite-work.schema.json"))
    assert examples["example_only"] is True
    for request in examples["requests"]:
        validator.validate(request)
        assert request["authorization_status"] == "proposed_not_authorized"
        assert request["followup"] == "return_to_sol_for_replanning"


def test_mutable_library_source_must_be_frozen_before_prerequisite_execution() -> None:
    request = json.loads((
        ROOT / "mission_hub" / "research" / "examples" /
        "prerequisite-work-examples.json"
    ).read_text(encoding="utf-8"))["requests"][1]
    request["source_inputs"][0]["freeze_before_execution"] = False
    with pytest.raises(ValidationError):
        Draft202012Validator(_schema("prerequisite-work.schema.json")).validate(request)


def test_source_maintenance_examples_are_atomic_and_schema_valid() -> None:
    example = json.loads((
        ROOT / "mission_hub" / "research" / "examples" /
        "source-maintenance-example.json"
    ).read_text(encoding="utf-8"))
    validator = Draft202012Validator(_schema("source-claim.schema.json"))
    assert example["example_only"] is True
    for claim in example["claims"]:
        validator.validate(claim)


def test_source_census_covers_current_and_archived_document_surfaces() -> None:
    paths = {path.relative_to(ROOT).as_posix() for path in candidate_paths(ROOT)}
    assert "docs/ninereeds_training_modes.md" in paths
    assert "handoff/README.md" in paths
    assert "archive/docs/ninereeds_cks_curriculum.md" in paths
    assert "archive/workstation/cleanup-2026-08-06/docs/grounded_story_picturebooks.md" in paths
    assert "archive/workstation/cleanup-2026-08-06/training/harness/intervention_registry.md" in paths
    assert "archive/training_harness_design_pre_2026-05-23.md" in paths
    census = build_census(ROOT)
    assert census["candidate_count"] == len(paths)
    assert census["unique_byte_count"] <= census["candidate_count"]
    assert all(item["intake_disposition"] == "needs_identity_or_scope_review" for item in census["candidates"])


def test_source_triage_partitions_the_entire_census() -> None:
    census = json.loads((
        ROOT / "mission_hub" / "research" / "intake" / "source-census.json"
    ).read_text(encoding="utf-8"))
    triage = json.loads((
        ROOT / "mission_hub" / "research" / "intake" / "source-triage.json"
    ).read_text(encoding="utf-8"))
    census_paths = {item["path"] for item in census["candidates"]}
    triage_paths = [path for batch in triage["batches"] for path in batch["paths"]]
    assert len(triage_paths) == len(set(triage_paths))
    assert set(triage_paths) == census_paths


def test_current_intervention_catalogue_preserves_modern_training_distinctions() -> None:
    catalogue = json.loads((
        ROOT / "mission_hub" / "research" / "intervention-catalogue.json"
    ).read_text(encoding="utf-8"))
    interventions = {item["id"]: item for item in catalogue["interventions"]}
    assert "complete varied presentation-practice-production cycles" in interventions["increase_exposure_depth"]["modern_rule"]
    assert "prerequisites and a complete instructional cycle" in interventions["increase_curriculum_breadth"]["modern_rule"]
    assert "merge_and_heal" in interventions
    assert "branch_and_specialize" in interventions


def test_teacher_handoff_example_is_bounded_and_returns_script_control() -> None:
    example = json.loads((
        ROOT / "mission_hub" / "research" / "examples" /
        "teacher-handoff-example.json"
    ).read_text(encoding="utf-8"))
    Draft202012Validator(_schema("teacher-handoff.schema.json")).validate(example["handoff"])
    assert example["handoff"]["result"]["return_control"] == "deterministic_script"
    assert example["handoff"]["result"]["verifier_required"] is True
