from __future__ import annotations

from pathlib import Path

import pytest

from mission_hub.campaign_contract import expected_evaluation_context, validate_campaign_contract
from mission_hub.config import load_config_bundle
from mission_hub.errors import SafetyError
from mission_hub.jsonutil import canonical_json
from mission_hub.store import MissionHubStore, utc_now
from training.pipeline.cortex.evaluation import compare_evaluations


REPO = Path(__file__).resolve().parents[1]


def contract(mode: str) -> dict:
    return {
        "schema_version": "ninereeds_campaign_contract_v1",
        "mode": mode,
        "development_stage": "early language formation",
        "purpose": "Collect evidence about the declared learning purpose.",
        "success_criteria": ["The declared evidence question is answered."],
        "failure_criteria": ["Required chat or MRI evidence is missing."],
        "expected_regressions": ["Temporary behavioral regression."],
        "branches": ["branch-1", "branch-2"] if mode == "evolutionary" else [],
        "merge_sources": ["symbols", "language"] if mode == "merge" else [],
        "target_capabilities": ["new capability"] if mode == "advancement" else [],
        "bootstrap_milestones": ["Produces word sequences with sentence-like structure."] if mode == "bootstrap" else [],
        "hypothesis": "Different learning trajectories reveal different recovery behavior." if mode in {"experimental", "evolutionary", "merge"} else "",
        "observations_sought": ["Chat behavior and MRI changes."] if mode in {"experimental", "evolutionary", "merge"} else [],
    }


def evaluation(mode: str, *, regressed: bool) -> tuple[dict, dict]:
    score = 0.2 if regressed else 0.9
    return ({
        "checkpoint_sha256": ("a" if regressed else "b") * 64,
        "summary": {
            "overall": {"score": score, "total": 10, "pathological": 5 if regressed else 0, "cross_prompt_collapse": regressed, "dominant_response_fraction": 0.8 if regressed else 0.1},
            "groups": {"capability": {"score": score}, "protected": {"score": score}},
            "concepts": {},
        },
        "scan": {"activation_health": {"dead_layers": [], "saturated_layers": []}},
    }, {})


def compare_for(mode: str, *, complete: bool = True) -> dict:
    bundle = load_config_bundle(REPO / "config/mission_hub")
    phase = {
        "bootstrap": "bootstrap_milestone",
        "advancement": "advancement_checkpoint",
        "experimental": "experimental_observation",
        "evolutionary": "evolutionary_branch",
        "merge": "post_merge",
    }[mode]
    branch = "branch-1" if mode == "evolutionary" else None
    context = expected_evaluation_context(
        contract(mode), bundle.campaign_modes, phase=phase, branch_id=branch,
        all_required_branches_complete=complete,
    )
    candidate, _ = evaluation(mode, regressed=True)
    parent, _ = evaluation(mode, regressed=False)
    raw = {"vectors": {name: [[1.0, 0.0]] for name in ("ingress", "core", "intentions")}}
    return compare_evaluations(
        candidate, raw, parent, raw,
        candidate_checkpoint="candidate.pt", parent_checkpoint="parent.pt",
        target_concept=None, evaluation_context=context,
    )


def test_campaign_contract_requires_declared_success_and_failure() -> None:
    bundle = load_config_bundle(REPO / "config/mission_hub")
    value = contract("experimental")
    value["success_criteria"] = []
    with pytest.raises(SafetyError, match="success and failure"):
        validate_campaign_contract(value, bundle.campaign_modes)


def test_bootstrap_regression_is_milestone_evidence_not_rejection() -> None:
    certificate = compare_for("bootstrap")
    assert certificate["status"] == "milestone_observed"
    assert certificate["blocking_reasons"] == []
    assert certificate["diagnostic_findings"]
    assert certificate["failure_modes"] == []
    assert certificate["reasons"] == []


def test_experimental_regression_is_evidence_not_rejection() -> None:
    certificate = compare_for("experimental")
    assert certificate["status"] == "evidence_collected"
    assert certificate["recommended_parent_checkpoint"] is None


def test_evolutionary_branch_cannot_be_ranked_early() -> None:
    certificate = compare_for("evolutionary", complete=False)
    assert certificate["status"] == "comparison_pending"
    assert "wait for every declared branch" in certificate["recommended_next_action"]
    assert certificate["failure_modes"] == []
    assert certificate["reasons"] == []
    assert any("observed target gain" in item for item in certificate["diagnostic_findings"])


def test_advancement_keeps_parent_candidate_guard() -> None:
    certificate = compare_for("advancement")
    assert certificate["status"] == "rejected"
    assert certificate["recommended_parent_checkpoint"] == "parent.pt"
    assert "target_nontransfer" in certificate["failure_modes"]


def test_merge_uses_composition_and_interference_review() -> None:
    certificate = compare_for("merge")
    assert certificate["status"] == "merge_review_ready"
    assert "composition" in certificate["recommended_next_action"]


def test_new_campaign_cannot_exist_without_purpose_contract(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config/mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    with pytest.raises(SafetyError, match="complete versioned"):
        store.create_campaign(
            campaign_id="missing-contract", name="missing", objective="missing",
            metadata={}, actor="test",
        )


def test_manual_evolutionary_evaluation_cannot_claim_branch_completion(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config/mission_hub")
    bundle.base["safety"]["live_execution"] = True
    bundle.jobs["model.evaluate"]["enabled"] = True
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    campaign_contract = contract("evolutionary")
    store.create_campaign(
        campaign_id="evolution-test", name="evolution", objective="compare branches",
        metadata={"campaign_contract": campaign_contract}, state="active", actor="test",
    )
    with store.transaction() as db:
        for artifact_id, kind, digest in (
            ("art-aaaaaaaaaaaaaaaa", "checkpoint", "a" * 64),
            ("art-bbbbbbbbbbbbbbbb", "checkpoint", "b" * 64),
            ("art-cccccccccccccccc", "evaluation_suite", "c" * 64),
        ):
            db.execute(
                "INSERT INTO artifacts(id,kind,sha256,byte_size,lifecycle,manifest_json,created_at) VALUES(?,?,?,?, 'candidate',?,?)",
                (artifact_id, kind, digest, 1, canonical_json({}), utc_now()),
            )

    def payload(branch_id: str, all_complete: bool, *, branch_complete: bool = False) -> dict:
        return {
            "candidate_artifact_id": "art-aaaaaaaaaaaaaaaa",
            "parent_artifact_id": "art-bbbbbbbbbbbbbbbb",
            "suite_artifact_id": "art-cccccccccccccccc",
            "evaluation_context": expected_evaluation_context(
                campaign_contract, bundle.campaign_modes, phase="evolutionary_branch",
                branch_id=branch_id, branch_complete=branch_complete,
                all_required_branches_complete=all_complete,
            ),
            "parameters": {"ingress_device": "cpu", "core_device": "cpu", "max_new_tokens": 16},
        }

    first = store.create_job(
        bundle, job_type="model.evaluate", input_payload=payload("branch-1", False),
        idempotency_key="branch-1", created_by="test", campaign_id="evolution-test", approved=True,
    )
    with store.transaction() as db:
        db.execute("UPDATE jobs SET status='succeeded' WHERE id=?", (first["id"],))
    second = store.create_job(
        bundle, job_type="model.evaluate", input_payload=payload("branch-2", False),
        idempotency_key="branch-2", created_by="test", campaign_id="evolution-test", approved=True,
    )
    assert second["status"] == "queued"
    with pytest.raises(SafetyError, match="does not exactly match"):
        store.create_job(
            bundle, job_type="model.evaluate",
            input_payload=payload("branch-2", True, branch_complete=True),
            idempotency_key="branch-2-false-claim", created_by="test",
            campaign_id="evolution-test", approved=True,
        )
