from __future__ import annotations

import hashlib
import json
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


class InventoryDispatcher(DeletingDispatcher):
    def __init__(self, files):
        self.files = files

    def build_inventory(self, machine_id, deployment, *, force=False):
        return {
            "ok": True, "machine_id": machine_id, "deployment_id": deployment["id"],
            "triggered": force, "used_fraction": 0.5,
            "free_bytes": 40 * 1024 ** 3, "total_bytes": 100 * 1024 ** 3,
            "files": self.files if force else [],
        }


def setup_retention(tmp_path: Path):
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.base["hub"]["state_root"] = str(tmp_path / "hub-state")
    for machine_id in ("mission-hub", "trainbox"):
        root = tmp_path / machine_id
        bundle.machines[machine_id]["state_root"] = str(root / "state")
        bundle.machines[machine_id]["artifact_roots"] = [str(root)]
    bundle.retention["build_roots"] = [str(tmp_path / "trainbox")]
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


def campaign_metadata() -> dict:
    return {"campaign_contract": {
        "schema_version": "ninereeds_campaign_contract_v1", "mode": "advancement",
        "development_stage": "storage preflight fixture",
        "purpose": "Prove cleanup and capacity before campaign work.",
        "success_criteria": ["Capacity is proven."],
        "failure_criteria": ["Capacity is insufficient."],
        "expected_regressions": [], "branches": [], "merge_sources": [],
        "target_capabilities": ["storage preflight"], "bootstrap_milestones": [],
        "hypothesis": "", "observations_sought": [],
    }}


def test_protection_registry_excludes_pins_from_exact_cleanup_plan(tmp_path: Path) -> None:
    bundle, store = setup_retention(tmp_path)
    keeper = checkpoint(store, bundle, tmp_path, "keeper")
    disposable = checkpoint(store, bundle, tmp_path, "disposable")
    pin = store.protect_artifact(
        keeper["id"], protection_key="operator-pin", reason="Known-good baseline",
        actor="test", source="operator",
    )

    plan = store.retention_inventory(machine_id="trainbox", roots=bundle.retention["build_roots"])

    assert [item["id"] for item in plan["protected"]] == [keeper["id"]]
    assert [item["id"] for item in plan["eligible"]] == [disposable["id"]]
    assert plan["plan_sha256"] == content_hash({key: value for key, value in plan.items() if key != "plan_sha256"})
    store.release_artifact_protection(pin["id"], actor="test")
    assert len(store.retention_inventory(machine_id="trainbox")["eligible"]) == 2


def test_exact_path_pin_excludes_runtime_weight_from_cleanup(tmp_path: Path) -> None:
    bundle, store = setup_retention(tmp_path)
    runtime = checkpoint(store, bundle, tmp_path, "runtime-projector")
    store.protect_path(
        "trainbox", runtime["uri"], protection_key="active-runtime",
        reason="Campaign runtime fixture", actor="test", source="operator",
    )

    plan = store.retention_inventory(
        machine_id="trainbox", roots=bundle.retention["build_roots"],
    )

    assert [item["id"] for item in plan["protected"]] == [runtime["id"]]
    assert plan["eligible"] == []


def test_active_campaign_protects_only_current_lineage_heads_and_explicit_metadata(tmp_path: Path) -> None:
    bundle, store = setup_retention(tmp_path)
    root = checkpoint(store, bundle, tmp_path, "root")
    first = checkpoint(store, bundle, tmp_path, "first")
    second = checkpoint(store, bundle, tmp_path, "second")
    branch = checkpoint(store, bundle, tmp_path, "branch")
    config_id = store.active_config()["id"]
    metadata = {**campaign_metadata(), "starting_checkpoint_artifact_id": root["id"]}
    store.create_campaign(
        campaign_id="campaign-active", name="active", objective="lineage",
        metadata=metadata, state="active", actor="test",
    )
    now = "2026-01-01T00:00:00.000000Z"
    with store.transaction() as db:
        for index, (session_id, parent, output) in enumerate((
            ("session-1", root["id"], first["id"]),
            ("session-2", first["id"], second["id"]),
            ("session-branch", root["id"], branch["id"]),
        )):
            job_id = f"job-lineage-{index}"
            db.execute(
                """INSERT INTO jobs
                   (id,idempotency_key,job_type,job_version,status,config_snapshot_id,
                    campaign_id,requested_machine_id,input_json,input_sha256,priority,
                    approval_policy,approved_by,approved_at,created_by,created_at,updated_at)
                   VALUES(?,?,'model.train',1,'succeeded',?,'campaign-active','trainbox',
                          '{}',?,1,'operator','test',?,'test',?,?)""",
                (job_id, job_id, config_id, str(index) * 64, now, now, now),
            )
            db.execute(
                """INSERT INTO training_session_plans
                   (id,campaign_id,session_id,job_id,parent_checkpoint_artifact_id,
                    subject_artifact_id,validation_artifact_id,ordered_concepts_json,
                    parent_knowledge_sha256,plan_sha256,status,created_at,completed_at,
                    output_checkpoint_artifact_id)
                   VALUES(?, 'campaign-active', ?, ?, ?, ?, ?, '[]', ?, ?,
                          'completed', ?, ?, ?)""",
                (
                    f"plan-{index}", session_id, job_id, parent, root["id"], root["id"],
                    chr(97 + index) * 64, chr(100 + index) * 64, now, now, output,
                ),
            )

    result = store.reconcile_retention_protections(bundle, actor="test")
    plan = store.retention_inventory(
        machine_id="trainbox", roots=bundle.retention["build_roots"],
    )

    assert result["artifact_protections"] == 3
    assert {item["id"] for item in plan["protected"]} == {
        root["id"], second["id"], branch["id"],
    }
    assert [item["id"] for item in plan["eligible"]] == [first["id"]]


def test_event_driven_frontier_prune_deletes_superseded_parent_without_inventory_scan(tmp_path: Path) -> None:
    bundle, store = setup_retention(tmp_path)
    parent = checkpoint(store, bundle, tmp_path, "frontier-parent")
    successor = checkpoint(store, bundle, tmp_path, "frontier-successor")
    store.create_campaign(
        campaign_id="campaign-frontier", name="frontier", objective="rolling retention",
        metadata=campaign_metadata(), state="active", actor="test",
    )
    config_id = store.active_config()["id"]
    now = "2026-01-01T00:00:00.000000Z"
    with store.transaction() as db:
        db.execute(
            """INSERT INTO jobs
               (id,idempotency_key,job_type,job_version,status,config_snapshot_id,
                campaign_id,requested_machine_id,input_json,input_sha256,priority,
                approval_policy,approved_by,approved_at,created_by,created_at,updated_at)
               VALUES('job-frontier','job-frontier','model.train',1,'succeeded',?,
                      'campaign-frontier','trainbox','{}',?,1,'operator','test',?,
                      'test',?,?)""",
            (config_id, "f" * 64, now, now, now),
        )
        db.execute(
            """INSERT INTO training_session_plans
               (id,campaign_id,session_id,job_id,parent_checkpoint_artifact_id,
                subject_artifact_id,validation_artifact_id,ordered_concepts_json,
                parent_knowledge_sha256,plan_sha256,status,created_at,completed_at,
                output_checkpoint_artifact_id)
               VALUES('plan-frontier','campaign-frontier','session-frontier','job-frontier',
                      ?,?,?,'[]',?,?,'completed',?,?,?)""",
            (parent["id"], parent["id"], parent["id"], "a" * 64, "b" * 64,
             now, now, successor["id"]),
        )
        db.execute(
            "INSERT INTO metadata(key,value) VALUES('checkpoint_frontier_prune',?)",
            (json.dumps({"token": "prune-1", "superseded_parent_artifact_id": parent["id"]}),),
        )

    result = RetentionManager(
        store, bundle, dispatcher=DeletingDispatcher(),
    ).prune_checkpoint_frontier(machine_id="trainbox", actor="test")

    assert result["deleted_count"] == 1
    assert result["deleted_bytes"] == parent["byte_size"]
    assert not Path(parent["uri"]).exists()
    assert Path(successor["uri"]).is_file()
    assert store.checkpoint_frontier_prune_request() is None


def test_post_training_prune_waits_for_comparison_evaluation_ownership(tmp_path: Path) -> None:
    bundle, _ = setup_retention(tmp_path)

    class DeferredStore:
        @staticmethod
        def checkpoint_frontier_prune_request():
            return {"token": "deferred", "phase": "post_training", "job_id": "train"}

        @staticmethod
        def checkpoint_frontier_prune_ready(request):
            return False

        @staticmethod
        def pipeline_control():
            return {"live_runs": 0}

        def reconcile_retention_protections(self, *args, **kwargs):
            raise AssertionError("protection reconciliation ran before evaluation ownership")

    result = RetentionManager(
        DeferredStore(), bundle, dispatcher=DeletingDispatcher(),
    ).prune_checkpoint_frontier(machine_id="trainbox", actor="test")

    assert result["deferred"] is True
    assert result["deleted_count"] == 0


def test_automatic_retention_interval_uses_event_timestamp(tmp_path: Path) -> None:
    _, store = setup_retention(tmp_path)
    assert store.retention_auto_due(900) is True
    store.record_retention_auto_check({"checked": True}, actor="test")
    assert store.retention_auto_due(900) is False


def test_cleanup_deletes_only_exact_unprotected_location_and_preserves_metadata(tmp_path: Path) -> None:
    bundle, store = setup_retention(tmp_path)
    keeper = checkpoint(store, bundle, tmp_path, "keeper")
    disposable = checkpoint(store, bundle, tmp_path, "disposable")
    store.protect_artifact(
        keeper["id"], protection_key="operator-pin", reason="Known-good baseline",
        actor="test", source="operator",
    )
    plan = store.retention_inventory(machine_id="trainbox", roots=bundle.retention["build_roots"])
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


def test_campaign_preflight_cleans_unprotected_builds_and_proves_capacity(tmp_path: Path) -> None:
    bundle, store = setup_retention(tmp_path)
    keeper = checkpoint(store, bundle, tmp_path, "keeper")
    disposable = checkpoint(store, bundle, tmp_path, "disposable")
    store.protect_artifact(
        keeper["id"], protection_key="canonical-base", reason="Current best foundation",
        actor="test", source="operator",
    )
    files = [
        {"uri": item["uri"], "sha256": item["sha256"], "byte_size": item["byte_size"]}
        for item in (keeper, disposable)
    ]
    store.create_campaign(
        campaign_id="campaign-next", name="next", objective="capacity",
        metadata=campaign_metadata(), state="active", actor="test",
    )
    store.declare_campaign_storage(
        "campaign-next", required_free_bytes=35 * 1024 ** 3,
        estimated_build_count=5, actor="test",
    )

    result = RetentionManager(
        store, bundle, dispatcher=InventoryDispatcher(files),
    ).prepare_campaign(
        "campaign-next", required_free_bytes=35 * 1024 ** 3, actor="test",
    )

    assert result["prepared"] is True
    assert result["deleted_count"] == 1
    assert Path(keeper["uri"]).is_file()
    assert not Path(disposable["uri"]).exists()
    campaign = next(row for row in store.list_rows("campaigns") if row["id"] == "campaign-next")
    metadata = json.loads(campaign["metadata_json"])
    assert metadata["storage_preflight"]["status"] == "prepared"
