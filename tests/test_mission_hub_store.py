from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from mission_hub.agent import TrainboxAgent
from mission_hub.config import load_config_bundle
from mission_hub.errors import ConflictError, SafetyError
from mission_hub.service import MissionHubService
from mission_hub.store import MissionHubStore


REPO = Path(__file__).resolve().parents[1]


def commissioned_bundle():
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.machines["trainbox"]["maintenance_mode"] = False
    return bundle


def initialized(tmp_path: Path, bundle=None):
    bundle = bundle or load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    return bundle, store, config_id


def active_deployment(store: MissionHubStore, config_id: str) -> tuple[str, dict]:
    manifest = {
        "schema_version": "ninereeds_deployment_manifest_v1",
        "machine_id": "trainbox",
        "role": "trainbox",
        "release_id": "test-release",
        "source_sha256": "1" * 64,
        "environment_sha256": "2" * 64,
        "config_snapshot_id": config_id,
    }
    deployment_id = store.register_deployment(manifest, actor="test", activate=True)
    return deployment_id, {"id": deployment_id, **manifest}


def test_only_safe_healthcheck_is_creatable_by_default(tmp_path: Path) -> None:
    bundle, store, _ = initialized(tmp_path)
    health = store.create_job(
        bundle,
        job_type="system.healthcheck",
        input_payload={"include_disk": False, "include_gpu": False, "include_release": True},
        idempotency_key="health-1",
        created_by="test",
        requested_machine_id="trainbox",
    )
    assert health["status"] == "queued"
    with pytest.raises(SafetyError, match="disabled"):
        store.create_job(
            bundle,
            job_type="model.train",
            input_payload={},
            idempotency_key="train-1",
            created_by="test",
        )


def test_idempotency_key_cannot_change_work(tmp_path: Path) -> None:
    bundle, store, _ = initialized(tmp_path)
    first = store.create_job(
        bundle,
        job_type="system.healthcheck",
        input_payload={},
        idempotency_key="same",
        created_by="test",
    )
    second = store.create_job(
        bundle,
        job_type="system.healthcheck",
        input_payload={},
        idempotency_key="same",
        created_by="test",
    )
    assert second["id"] == first["id"]
    with pytest.raises(ConflictError):
        store.create_job(
            bundle,
            job_type="system.healthcheck",
            input_payload={"include_disk": False},
            idempotency_key="same",
            created_by="test",
        )


def test_trainbox_maintenance_mode_refuses_leases(tmp_path: Path) -> None:
    bundle, store, config_id = initialized(tmp_path)
    deployment_id, _ = active_deployment(store, config_id)
    store.create_job(
        bundle,
        job_type="system.healthcheck",
        input_payload={},
        idempotency_key="health-maintenance",
        created_by="test",
    )
    with pytest.raises(SafetyError, match="maintenance"):
        store.lease_next(bundle, machine_id="trainbox", deployment_id=deployment_id, actor="agent")


def test_end_to_end_safe_job_has_one_authoritative_lifecycle(tmp_path: Path) -> None:
    bundle, store, config_id = initialized(tmp_path, commissioned_bundle())
    deployment_id, deployment = active_deployment(store, config_id)
    job = store.create_job(
        bundle,
        job_type="system.healthcheck",
        input_payload={"include_disk": False, "include_gpu": False, "include_release": True},
        idempotency_key="health-e2e",
        created_by="operator",
        requested_machine_id="trainbox",
    )
    service = MissionHubService(store, bundle)
    envelope = service.lease_envelope(machine_id="trainbox", deployment_id=deployment_id, actor="dispatcher")
    assert envelope is not None
    store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="agent")
    result = TrainboxAgent(bundle, machine_id="trainbox", deployment=deployment).execute(envelope)
    assert "token" not in str(result)
    service.accept_result(envelope, result, actor="agent")
    assert store.list_rows("jobs", limit=1)[0]["status"] == "succeeded"
    assert store.list_rows("runs", limit=1)[0]["status"] == "succeeded"
    integrity = store.integrity_report()
    assert integrity == {
        "sqlite_integrity": "ok",
        "foreign_key_errors": [],
        "event_chain_ok": True,
        "event_count": 7,
    }


def test_only_configured_transient_failure_is_retried(tmp_path: Path) -> None:
    bundle = commissioned_bundle()
    bundle.jobs["system.healthcheck"]["max_attempts"] = 3
    bundle.jobs["system.healthcheck"]["retry_policy"] = "infrastructure_only"
    bundle, store, config_id = initialized(tmp_path, bundle)
    deployment_id, _ = active_deployment(store, config_id)
    store.create_job(
        bundle,
        job_type="system.healthcheck",
        input_payload={},
        idempotency_key="retry-health",
        created_by="test",
    )
    leased, token = store.lease_next(bundle, machine_id="trainbox", deployment_id=deployment_id, actor="agent")
    store.finish_run(
        bundle,
        leased["run_id"],
        token,
        status="failed",
        output=None,
        failure={"class": "operational_transient", "code": "transport_unavailable"},
        actor="agent",
    )
    job = store.list_rows("jobs", limit=1)[0]
    assert job["status"] == "queued"
    assert job["available_at"] is not None


def test_non_retryable_specification_failure_stops(tmp_path: Path) -> None:
    bundle = commissioned_bundle()
    bundle.jobs["system.healthcheck"]["max_attempts"] = 3
    bundle.jobs["system.healthcheck"]["retry_policy"] = "infrastructure_only"
    bundle, store, config_id = initialized(tmp_path, bundle)
    deployment_id, _ = active_deployment(store, config_id)
    store.create_job(bundle, job_type="system.healthcheck", input_payload={}, idempotency_key="bad-spec", created_by="test")
    leased, token = store.lease_next(bundle, machine_id="trainbox", deployment_id=deployment_id, actor="agent")
    store.finish_run(
        bundle,
        leased["run_id"],
        token,
        status="failed",
        output=None,
        failure={"class": "deterministic_specification", "code": "job_spec_invalid"},
        actor="agent",
    )
    assert store.list_rows("jobs", limit=1)[0]["status"] == "failed"


def test_artifact_references_are_resolved_and_outputs_commit_atomically(tmp_path: Path) -> None:
    bundle = commissioned_bundle()
    definition = bundle.jobs["corpus.validate"]
    definition["enabled"] = True
    bundle, store, config_id = initialized(tmp_path, bundle)
    deployment_id, _ = active_deployment(store, config_id)
    corpus_id = store.register_artifact(
        bundle,
        kind="corpus",
        sha256="a" * 64,
        byte_size=12,
        lifecycle="legacy",
        manifest={"source": "test"},
        producing_run_id=None,
        machine_id="trainbox",
        uri="/home/aomukai/.local/share/ninereeds/trainbox-agent/artifacts/test.jsonl",
        actor="test",
    )
    store.create_job(
        bundle,
        job_type="corpus.validate",
        input_payload={"corpus_artifact_id": corpus_id},
        idempotency_key="validate-artifact",
        created_by="test",
        requested_machine_id="trainbox",
    )
    leased, token = store.lease_next(bundle, machine_id="trainbox", deployment_id=deployment_id, actor="agent")
    resolved = store.resolve_artifacts(definition, {"corpus_artifact_id": corpus_id}, machine_id="trainbox")
    assert resolved[0]["id"] == corpus_id
    store.start_run(leased["run_id"], token, actor="agent")
    store.finish_run(
        bundle,
        leased["run_id"],
        token,
        status="succeeded",
        output={
            "status": "succeeded",
            "artifacts": [
                {
                    "kind": "validation_report",
                    "sha256": "b" * 64,
                    "byte_size": 20,
                    "uri": f"/home/aomukai/.local/share/ninereeds/trainbox-agent/runs/{leased['run_id']}/report.json",
                    "lifecycle": "candidate",
                    "manifest": {"corpus_artifact_id": corpus_id},
                }
            ],
            "metrics": {},
            "failure": None,
        },
        failure=None,
        actor="agent",
    )
    artifacts = store.list_rows("artifacts", limit=10)
    assert {row["kind"] for row in artifacts} == {"corpus", "validation_report"}
