from __future__ import annotations

from pathlib import Path

from mission_hub.config import load_config_bundle
from mission_hub.configured_campaign import ConfiguredCortexCampaign
from mission_hub.jsonutil import canonical_json
from mission_hub.store import MissionHubStore, utc_now


REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "config/mission_hub/campaigns/campaign33-play-recovery-v1.json"


def test_campaign33_configuration_reconciles_exact_artifacts_and_baseline_knowledge(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config/mission_hub")
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
               VALUES('art-ba5e1e0000000000','checkpoint',?,7265464584,'candidate',?,?)""",
            (
                "76c1ba33c935a61557caf39a4886669f4833458671d4e909dc40adb96b2b81a9",
                canonical_json({"certification_scope": "byte_identity_only"}), utc_now(),
            ),
        )
    configured = ConfiguredCortexCampaign(
        store, bundle, repo_root=REPO, specification_path=SPEC,
    )
    result = configured.reconcile(actor="test")
    assert result["baseline_artifact_id"] == "art-ba5e1e0000000000"
    assert len(result["corpora"]["play-word-evolution-0501-2000-v1-play-003"]) == 12
    assert len(store.checkpoint_knowledge("art-ba5e1e0000000000")) == 500
    campaign = next(
        row for row in store.list_rows("campaigns", limit=10)
        if row["id"] == "campaign-33-play-recovery-recommissioned-v1"
    )
    assert campaign["state"] == "active"
    assert result["workflows"] == []

    repeated = configured.reconcile(actor="test")
    assert repeated["campaign_id"] == result["campaign_id"]
    assert len(store.checkpoint_knowledge("art-ba5e1e0000000000")) == 500

    branch = "play-word-evolution-0501-2000-v1-play-003"
    authorized = configured.reconcile(actor="test", authorize_branches=[branch])
    authorized_again = configured.reconcile(actor="test", authorize_branches=[branch])
    assert authorized_again["workflows"][0]["id"] == authorized["workflows"][0]["id"]
    assert len(store.list_rows("cortex_workflows", limit=10)) == 1
