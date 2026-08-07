from __future__ import annotations

from pathlib import Path

from mission_hub.config import load_config_bundle
from mission_hub.configured_gate_credit import ConfiguredGateCreditCampaign
from mission_hub.jsonutil import canonical_json
from mission_hub.store import MissionHubStore, utc_now


REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "config/mission_hub/campaigns/campaign34-gate-credit-v1.json"


def test_campaign34_reconciles_one_control_and_one_observed_workflow(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    state_root = tmp_path / "state"
    bundle.machines["mission-hub"]["state_root"] = str(state_root)
    bundle.machines["mission-hub"]["artifact_roots"] = [str(state_root), str(REPO)]
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO artifacts
               (id,kind,sha256,byte_size,lifecycle,manifest_json,created_at)
               VALUES('art-20c96f701d529b15','checkpoint',?,7265446143,'candidate',?,?)""",
            (
                "5ef4f84ad5796d05622e0d2b962b9c240736875fc8c8a432a8c924f3728b82e7",
                canonical_json({"architecture": "cortex"}), utc_now(),
            ),
        )
    configured = ConfiguredGateCreditCampaign(
        store, bundle, repo_root=REPO, specification_path=SPEC,
    )
    result = configured.reconcile(
        actor="test", authorize_branches=["gate-credit-control", "gate-credit-observed"],
    )

    assert result["parent_artifact_id"] == "art-20c96f701d529b15"
    assert len(result["workflows"]) == 2
    specifications = [workflow["specification"] for workflow in result["workflows"]]
    assert {item["branch_id"] for item in specifications} == {
        "gate-credit-control", "gate-credit-observed",
    }
    diagnostic_states = {
        item["branch_id"]: item["sessions"][0]["parameters"]["gate_credit_diagnostics"]["enabled"]
        for item in specifications
    }
    assert diagnostic_states == {
        "gate-credit-control": False, "gate-credit-observed": True,
    }
    paired = [
        {key: value for key, value in item["sessions"][0]["parameters"].items() if key != "gate_credit_diagnostics"}
        for item in specifications
    ]
    assert paired[0] == paired[1]
    assert specifications[0]["sessions"][0]["corpus_artifact_id"] == specifications[1]["sessions"][0]["corpus_artifact_id"]

