import json

import pytest

from training.pipeline.visual.salvage import parse_salvage_response, sol_review_envelope


ASSET = "a" * 64


def proposal(bucket: str = "propose_use", uses=None) -> str:
    return json.dumps(
        [
            {
                "asset_sha256": ASSET,
                "bucket": bucket,
                "candidate_uses": uses
                if uses is not None
                else [
                    {
                        "kind": "cardinality_label",
                        "teaching_goal": "three red balls",
                        "evidence_keys": ["mechanical.red_ball_count"],
                        "paired_asset_sha256s": [],
                        "constraints": ["second visual judge confirms that all red regions are balls"],
                    }
                ],
                "reason": "Wrong for two, potentially useful for three.",
            }
        ]
    )


def test_salvage_is_a_proposal_not_an_acceptance() -> None:
    parsed = parse_salvage_response(proposal())
    envelope = sol_review_envelope(
        asset={"asset_sha256": ASSET},
        original_report={"commission_decision": "reject"},
        salvage_proposal=parsed[0],
    )

    assert parsed[0]["bucket"] == "propose_use"
    assert envelope["authority"]["deepseek_may_accept"] is False
    assert envelope["authority"]["original_commission_decision_is_immutable"] is True


def test_nonproposal_cannot_smuggle_candidate_uses() -> None:
    with pytest.raises(ValueError, match="only propose_use"):
        parse_salvage_response(proposal(bucket="discard"))
