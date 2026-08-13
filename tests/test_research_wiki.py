import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from mission_hub.research_wiki import lint, page_metadata


ROOT = Path(__file__).resolve().parents[1]


def test_commissioned_research_wiki_lints_cleanly() -> None:
    result = lint(ROOT)
    assert result["errors"] == []
    assert result["ok"] is True
    assert result["source_count"] == 5
    assert result["page_count"] == 9
    assert result["planning_step_count"] == 10


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
