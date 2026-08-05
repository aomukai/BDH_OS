import pytest

from training.pipeline.visual.disposition import (
    DispositionError,
    finalize_by_sol,
    validate_disposition,
)


def proposed_record() -> dict:
    return {
        "schema_version": "ninereeds_visual_asset_disposition_v1",
        "asset_sha256": "a" * 64,
        "display_filename": "three_red_balls.png",
        "review_status": "assistant_proposal",
        "commission_status": "partially_fulfilled",
        "asset_status": "review",
        "actual_facts": [
            {"fact": "three red balls are visible", "evidence_keys": ["mechanical.red_count"]},
            {"fact": "a dog is present", "evidence_keys": ["vision.secondary.dog_present"]},
        ],
        "potential_uses": [
            {
                "teaching_goal": "three red balls",
                "kind": "cardinality_label",
                "requires_assets": [],
                "constraints": [],
                "evidence_facts": [0],
            }
        ],
        "failure_reason": "Requested two red balls; observed three.",
        "evidence": {"mechanical.red_count": 3},
        "assistant": {"model": "deepseek-v4-flash", "role": "proposal_only"},
        "sol_review": None,
    }


def test_sol_can_salvage_without_rewriting_commission_history() -> None:
    proposal = proposed_record()
    result = finalize_by_sol(
        proposal,
        asset_status="usable",
        accepted_use_indexes=[0],
        verified_evidence_keys=["mechanical.red_count", "vision.secondary.dog_present"],
        reason="Pixels verify one dog and exactly three red balls.",
    )

    assert result["commission_status"] == "partially_fulfilled"
    assert result["asset_status"] == "usable"
    assert result["review_status"] == "sol_verified"


def test_assistant_cannot_mark_asset_usable() -> None:
    proposal = proposed_record()
    proposal["asset_status"] = "usable"
    with pytest.raises(DispositionError, match="pending Sol"):
        validate_disposition(proposal)
