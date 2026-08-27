import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from mission_hub.research_wiki import lint, page_metadata
from mission_hub.research.source_inventory import build_census, candidate_paths
from mission_hub.research_brief import build_briefing


ROOT = Path(__file__).resolve().parents[1]


def test_commissioned_research_wiki_lints_cleanly() -> None:
    result = lint(ROOT)
    assert result["errors"] == []
    assert result["ok"] is True
    assert result["source_count"] == 42
    assert result["page_count"] == 12
    assert result["planning_step_count"] == 10
    assert result["source_candidate_count"] >= 88


def test_between_campaign_experiment_catalogue_is_non_authorizing_and_ordered() -> None:
    catalogue = json.loads((
        ROOT / "mission_hub" / "research" /
        "experimental-campaign-catalogue.json"
    ).read_text(encoding="utf-8"))
    assert catalogue["status"] == "prepared_plans_not_authorized"
    assert not any(catalogue["authority"].values())
    experiments = {item["id"]: item for item in catalogue["experiments"]}
    assert set(experiments) == {
        "XR-RT-01", "XR-LR-00", "XR-GC-01", "XR-LR-01", "XR-PFC-00",
        "XR-PFC-01", "XR-RT-02", "XR-LR-02", "XR-LR-03", "XR-GC-02",
        "XR-AK-01",
    }
    assert experiments["XR-PFC-01"]["depends_on"] == ["XR-PFC-00"]
    assert experiments["XR-AK-01"]["depends_on"] == ["XR-RT-01"]


def test_wiki_metadata_is_machine_readable() -> None:
    metadata = page_metadata(ROOT / "mission_hub" / "wiki" / "index.md")
    assert metadata["page_id"] == "wiki-index"
    assert metadata["page_type"] == "index"


def test_operator_local_training_sources_are_explicit() -> None:
    registry = json.loads((
        ROOT / "mission_hub" / "research" / "sources.json"
    ).read_text(encoding="utf-8"))
    source = next(
        item for item in registry["sources"]
        if item["id"] == "src-grounded-story-world-v1"
    )
    assert source["availability"] == "operator_local"
    assert source["path"].startswith("training_data/")


def test_bdh_cq_evaluation_method_is_planning_visible_and_complete() -> None:
    methodology = json.loads((
        ROOT / "mission_hub" / "research" / "evaluation-methodology.json"
    ).read_text(encoding="utf-8"))
    assert methodology["source_method"] == "src-bdh-cq-paper"
    assert methodology["campaign_scope"] == "campaign_0036_and_later"
    assert {layer["id"] for layer in methodology["evaluation_layers"]} == {
        "coverage_profile", "strict_consistency", "controlled_ladder",
        "matched_support", "atomic_composition", "cue_and_contamination_controls",
        "effort_and_replication", "failure_structure",
    }
    assert methodology["campaign_design_contract"]["freeze_before_generation"] is True

    metadata = page_metadata(ROOT / "mission_hub" / "wiki" / "evaluation.md")
    assert metadata["page_type"] == "evaluation_methodology"
    assert "src-bdh-cq-paper" in metadata["source_ids"]

    procedure = json.loads((
        ROOT / "mission_hub" / "research" / "sol-planning-procedure.json"
    ).read_text(encoding="utf-8"))
    required_paths = {
        path
        for section in procedure["ordered_read_set"]
        for path in section.get("required_paths", [])
    }
    assert "mission_hub/wiki/evaluation.md" in required_paths
    assert "mission_hub/research/evaluation-methodology.json" in required_paths


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
    receipt = example["handoff"]["result"]["marker_receipt"]
    assert receipt["used"] is True
    assert receipt["level"] == "constituent_only"
    assert receipt["immediate_unmarked_retest_required"] is True


def test_teacher_handoff_rejects_marker_use_without_unmarked_retest() -> None:
    example = json.loads((
        ROOT / "mission_hub" / "research" / "examples" /
        "teacher-handoff-example.json"
    ).read_text(encoding="utf-8"))
    example["handoff"]["result"]["marker_receipt"]["immediate_unmarked_retest_required"] = False
    with pytest.raises(ValidationError):
        Draft202012Validator(_schema("teacher-handoff.schema.json")).validate(example["handoff"])


def test_sol_planning_decision_has_one_luna_and_lab_source() -> None:
    example = json.loads((
        ROOT / "mission_hub" / "research" / "examples" /
        "sol-planning-decision-example.json"
    ).read_text(encoding="utf-8"))
    Draft202012Validator(_schema("sol-planning-decision.schema.json")).validate(example["decision"])
    decision = example["decision"]
    assert decision["luna_handoff"]["decision_artifact_id"] in decision["lab_projection"]["evidence_links"]


def test_sol_briefing_compiles_exact_ordered_context_with_budget() -> None:
    briefing = build_briefing(
        ROOT,
        live_state=ROOT / "mission_hub" / "research" / "examples" / "campaign-transition-example.json",
    )
    assert briefing["status"] == "ready"
    assert briefing["total_content_bytes"] < 100_000
    groups = [item["group"] for item in briefing["documents"]]
    assert groups[0] == "orientation"
    assert groups[-1] == "live_state"
    assert "planning_form" in groups


def test_sol_briefing_refuses_context_budget_overrun() -> None:
    with pytest.raises(ValueError, match="byte budget"):
        build_briefing(ROOT, max_bytes=100)
