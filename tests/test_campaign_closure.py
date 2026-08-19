from __future__ import annotations

from pathlib import Path
import hashlib

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.jsonutil import canonical_json
from mission_hub.store import MissionHubStore, utc_now
from mission_hub.errors import SafetyError


REPO = Path(__file__).resolve().parents[1]


def test_campaign_closure_requires_and_binds_nonranking_review(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    now = utc_now()
    contract = {
        "schema_version": "ninereeds_campaign_contract_v1",
        "mode": "evolutionary",
        "development_stage": "test stage",
        "purpose": "Compare two fully evidenced test branches.",
        "success_criteria": ["Both terminal evaluations exist."],
        "failure_criteria": ["A terminal evaluation is missing."],
        "expected_regressions": [],
        "branches": ["branch-a", "branch-b"],
        "merge_sources": [], "target_capabilities": [], "bootstrap_milestones": [],
        "hypothesis": "The branches may differ.",
        "observations_sought": ["Terminal behavior and MRI."],
    }
    with store.transaction() as db:
        for suffix, branch in (("aaaaaaaaaaaaaaaa", "branch-a"), ("bbbbbbbbbbbbbbbb", "branch-b")):
            db.execute(
                "INSERT INTO artifacts(id,kind,sha256,byte_size,lifecycle,manifest_json,created_at) VALUES(?, 'evaluation_report', ?, 1, 'observed', ?, ?)",
                (f"art-{suffix}", suffix * 4, canonical_json({"branch_id": branch}), now),
            )
        db.execute(
            "INSERT INTO artifacts(id,kind,sha256,byte_size,lifecycle,manifest_json,created_at) VALUES('art-cccccccccccccccc','campaign_review',?,1,'observed',?,?)",
            ("c" * 64, canonical_json({
                "campaign_id": "closure-test", "evaluation_basis": ["behavioral_chat", "mri_activation"],
                "loss_role": "telemetry_only", "automatic_winner_selected": False,
                "architecture_knowledge": {
                    "canonical_path": "docs/ninereeds_architecture_knowledge.md",
                    "ledger_sha256": hashlib.sha256((REPO / "docs/ninereeds_architecture_knowledge.md").read_bytes()).hexdigest(),
                    "disposition": "no_new_findings", "entry_ids": [],
                    "reason": "This synthetic closure test produced no observations about Ninereeds.",
                },
            }), now),
        )
        db.execute(
            "INSERT INTO artifacts(id,kind,sha256,byte_size,lifecycle,manifest_json,created_at) VALUES('art-dddddddddddddddd','campaign_review',?,1,'observed',?,?)",
            ("d" * 64, canonical_json({
                "campaign_id": "closure-test", "evaluation_basis": ["behavioral_chat", "mri_activation"],
                "loss_role": "telemetry_only", "automatic_winner_selected": False,
            }), now),
        )
    store.create_campaign(
        campaign_id="closure-test", name="Closure test", objective=contract["purpose"],
        metadata={
            "campaign_contract": contract,
            "completed_branch_evidence": {
                "branch-a": ["art-aaaaaaaaaaaaaaaa"],
                "branch-b": ["art-bbbbbbbbbbbbbbbb"],
            },
        }, state="active", actor="test",
    )

    with pytest.raises(SafetyError, match="architecture-knowledge disposition"):
        store.close_campaign(
            "closure-test", review_artifact_id="art-dddddddddddddddd", actor="test",
        )

    closed = store.close_campaign(
        "closure-test", review_artifact_id="art-cccccccccccccccc", actor="test",
    )

    assert closed["state"] == "closed"
    assert closed["metadata"]["final_review_artifact_id"] == "art-cccccccccccccccc"
    assert closed["metadata"]["closure_policy"]["automatic_winner_selected"] is False
    assert closed["metadata"]["architecture_knowledge"]["disposition"] == "no_new_findings"
