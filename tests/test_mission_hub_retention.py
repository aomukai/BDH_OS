from __future__ import annotations

import hashlib
from pathlib import Path

from mission_hub.config import load_config_bundle
from mission_hub.jsonutil import content_hash
from mission_hub.retention import RETENTION_ACKNOWLEDGEMENT, RetentionManager
from mission_hub.store import MissionHubStore


REPO = Path(__file__).resolve().parents[1]


class DeletingDispatcher:
    def delete_artifact(self, machine_id, deployment, artifact, *, plan_sha256):
        Path(artifact["uri"]).unlink()
        return {
            "ok": True, "artifact_id": artifact["id"], "kind": artifact["kind"],
            "sha256": artifact["sha256"], "byte_size": artifact["byte_size"],
            "uri": artifact["uri"], "plan_sha256": plan_sha256,
            "config_sha256": "test", "deployment_id": deployment["id"],
            "deleted": True,
        }


def setup_retention(tmp_path: Path):
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.base["hub"]["state_root"] = str(tmp_path / "hub-state")
    for machine_id in ("mission-hub", "trainbox"):
        root = tmp_path / machine_id
        bundle.machines[machine_id]["state_root"] = str(root / "state")
        bundle.machines[machine_id]["artifact_roots"] = [str(root)]
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    store.register_deployment({
        "machine_id": "trainbox", "role": "trainbox", "release_id": "test",
        "source_sha256": "1" * 64, "environment_sha256": "2" * 64,
        "config_snapshot_id": config_id,
    }, actor="test", activate=True)
    return bundle, store


def checkpoint(store, bundle, tmp_path: Path, name: str) -> dict:
    path = tmp_path / "trainbox" / "runs" / name / "candidate.pt"
    path.parent.mkdir(parents=True)
    path.write_bytes(name.encode())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    artifact_id = store.register_artifact(
        bundle, kind="checkpoint", sha256=digest, byte_size=path.stat().st_size,
        lifecycle="candidate", manifest={"branch_id": name}, producing_run_id=None,
        machine_id="trainbox", uri=str(path), actor="test",
    )
    return store.artifact_at(artifact_id, machine_id="trainbox")


def test_protection_registry_excludes_pins_from_exact_cleanup_plan(tmp_path: Path) -> None:
    bundle, store = setup_retention(tmp_path)
    keeper = checkpoint(store, bundle, tmp_path, "keeper")
    disposable = checkpoint(store, bundle, tmp_path, "disposable")
    pin = store.protect_artifact(
        keeper["id"], protection_key="operator-pin", reason="Known-good baseline",
        actor="test", source="operator",
    )

    plan = store.retention_inventory(machine_id="trainbox")

    assert [item["id"] for item in plan["protected"]] == [keeper["id"]]
    assert [item["id"] for item in plan["eligible"]] == [disposable["id"]]
    assert plan["plan_sha256"] == content_hash({key: value for key, value in plan.items() if key != "plan_sha256"})
    store.release_artifact_protection(pin["id"], actor="test")
    assert len(store.retention_inventory(machine_id="trainbox")["eligible"]) == 2


def test_cleanup_deletes_only_exact_unprotected_location_and_preserves_metadata(tmp_path: Path) -> None:
    bundle, store = setup_retention(tmp_path)
    keeper = checkpoint(store, bundle, tmp_path, "keeper")
    disposable = checkpoint(store, bundle, tmp_path, "disposable")
    store.protect_artifact(
        keeper["id"], protection_key="operator-pin", reason="Known-good baseline",
        actor="test", source="operator",
    )
    plan = store.retention_inventory(machine_id="trainbox")
    result = RetentionManager(
        store, bundle, dispatcher=DeletingDispatcher(),
    ).apply(
        machine_id="trainbox", plan_sha256=plan["plan_sha256"],
        acknowledgement=RETENTION_ACKNOWLEDGEMENT, actor="test",
    )

    assert result["deleted"][0]["id"] == disposable["id"]
    assert Path(keeper["uri"]).is_file()
    assert not Path(disposable["uri"]).exists()
    rows = {row["id"]: row for row in store.list_rows("artifacts", limit=100)}
    assert rows[disposable["id"]]["lifecycle"] == "deleted"
    assert rows[keeper["id"]]["lifecycle"] == "protected"
    assert result["report_artifact_id"].startswith("art-")
