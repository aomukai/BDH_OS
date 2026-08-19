"""Repeatable adversarial classification and crash-boundary simulations."""

from __future__ import annotations

import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from mission_hub.recovery import classify_failure
from mission_hub.recovery import RecoveryManager
from mission_hub.agent import TrainboxAgent
from mission_hub.service import MissionHubService
from mission_hub.store import MissionHubStore
from tests.test_mission_hub_store import active_deployment, commissioned_bundle, initialized
from tests.test_mission_hub_recovery import ready


FAULT_MATRIX = [
    ("provider unavailable", "provider_capability_unavailable", "capability_transient", False, "transient", "automatic_retry_or_fallback"),
    ("provider timeout", "provider_timeout", "capability_transient", False, "transient", "automatic_retry_or_fallback"),
    ("provider empty output", "provider_empty_output", "repairable_output", False, "software", "bounded_output_retry"),
    ("provider output truncation", "provider_output_truncated", "repairable_output", False, "software", "bounded_output_retry"),
    ("invalid structured response", "structured_response_invalid", "repairable_output", False, "software", "bounded_output_retry"),
    ("wrong artifact type", "artifact_contract_invalid", "deterministic_specification", True, "contract", "autonomous_repair"),
    ("zero required artifacts", "artifact_contract_invalid", "deterministic_specification", True, "contract", "autonomous_repair"),
    ("duplicate required artifacts", "artifact_contract_invalid", "deterministic_specification", True, "contract", "autonomous_repair"),
    ("corrupt artifact", "artifact_corrupt", "deterministic_specification", True, "contract", "autonomous_repair"),
    ("disk/write failure", "disk_write_failed", "operational_transient", False, "transient", "automatic_retry"),
    ("trainbox unreachable", "transport_unavailable", "operational_transient", False, "transient", "automatic_retry"),
    ("SSH interruption", "process_interrupted", "operational_transient", False, "transient", "automatic_retry"),
    ("stale deployment", "deployment_stale", "operational_transient", True, "infrastructure", "autonomous_repair"),
    ("configuration mismatch", "configuration_invalid", "deterministic_specification", True, "configuration", "known_good_rollback"),
    ("checkpoint mismatch", "checkpoint_mismatch", "deterministic_specification", True, "contract", "autonomous_repair"),
    ("process crash during execution", "lease_expired", "operational_transient", False, "transient", "automatic_retry"),
    ("process crash during artifact commit", "process_interrupted", "operational_transient", False, "transient", "atomic_rollback_retry"),
    ("process crash during state transition", "process_interrupted", "operational_transient", False, "transient", "atomic_rollback_retry"),
    ("dependency missing", "dependency_missing", "deterministic_specification", True, "software", "autonomous_repair"),
    ("test failure during repair", "unexpected_internal_error", "deterministic_specification", True, "software", "next_bounded_attempt"),
    ("runtime-invalid repair", "unexpected_internal_error", "deterministic_specification", True, "software", "next_bounded_attempt"),
    ("safety boundary", "safety_policy_refused", "safety_policy", True, "safety", "machine_blocker"),
]


def test_fault_matrix_has_machine_actionable_behavior_for_every_declared_fault():
    names = {row[0] for row in FAULT_MATRIX}
    assert {
        "provider unavailable", "provider timeout", "provider empty output", "provider output truncation",
        "invalid structured response", "wrong artifact type", "zero required artifacts",
        "duplicate required artifacts", "corrupt artifact", "disk/write failure", "trainbox unreachable",
        "SSH interruption", "stale deployment", "configuration mismatch", "checkpoint mismatch",
        "process crash during execution", "process crash during artifact commit",
        "process crash during state transition", "dependency missing", "test failure during repair",
        "runtime-invalid repair", "safety boundary",
    } <= names
    for name, code, failure_class, terminal, category, behavior in FAULT_MATRIX:
        actual_category, repair_allowed, blocker = classify_failure(failure_class, code, job_terminal=terminal)
        assert actual_category == category, name
        assert behavior
        if category == "safety":
            assert blocker == "safety_invariant_refused"


def test_crash_during_terminal_transition_rolls_back_all_partial_state(tmp_path: Path, monkeypatch):
    bundle, store, config_id = initialized(tmp_path, commissioned_bundle())
    deployment_id, _ = active_deployment(store, config_id)
    job = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={}, idempotency_key="crash-transition",
        created_by="test", requested_machine_id="trainbox",
    )
    service = MissionHubService(store, bundle)
    envelope = service.lease_envelope(machine_id="trainbox", deployment_id=deployment_id, actor="test")
    store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="test")
    original_event = store._event

    def crash_after_run_update(db, entity_type, entity_id, event_type, actor, payload):
        if event_type == "run.succeeded":
            raise RuntimeError("injected process crash during state transition")
        return original_event(db, entity_type, entity_id, event_type, actor, payload)

    monkeypatch.setattr(store, "_event", crash_after_run_update)
    with pytest.raises(RuntimeError, match="injected process crash"):
        store.finish_run(
            bundle, envelope["run"]["id"], envelope["lease"]["token"], status="succeeded",
            output={
                "status": "succeeded", "hostname": "test", "observed_at": "2026-01-01T00:00:00Z",
                "capabilities": [], "release": None, "disk": None, "gpu": None, "artifacts": [],
            }, failure=None, actor="test",
        )
    with store._connect() as db:
        run = db.execute("SELECT status,finished_at,output_json FROM runs WHERE id=?", (envelope["run"]["id"],)).fetchone()
        persisted_job = db.execute("SELECT status FROM jobs WHERE id=?", (job["id"],)).fetchone()
    assert tuple(run) == ("running", None, None)
    assert persisted_job[0] == "running"
    assert store.integrity_report()["event_chain_ok"] is True


def test_crash_during_artifact_commit_preserves_bytes_but_rolls_back_authority(tmp_path: Path, monkeypatch):
    store, bundle, library, _, _ = ready(tmp_path)
    (library / "source.md").write_text("immutable source\n", encoding="utf-8")
    job = store.create_job(
        bundle, job_type="corpus.build",
        input_payload={
            "corpus_name": "crash-artifact", "source_paths": ["source.md"],
            "normalization": "utf8_lf", "record_format": "ninereeds_document_v1",
        },
        idempotency_key="crash-artifact-commit", created_by="test",
        requested_machine_id="mission-hub", approved=True,
    )
    service = MissionHubService(store, bundle)
    deployment = store.active_deployment("mission-hub")
    envelope = service.lease_envelope(
        machine_id="mission-hub", deployment_id=deployment["id"], actor="test",
    )
    store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="test")
    result = service.execute_envelope("mission-hub", envelope)
    output = result["output"]
    produced_paths = [Path(item["uri"]) for item in output["artifacts"]]
    original_event = store._event

    def crash_before_terminal_event(db, entity_type, entity_id, event_type, actor, payload):
        if event_type == "run.succeeded":
            raise RuntimeError("injected crash after artifact rows")
        return original_event(db, entity_type, entity_id, event_type, actor, payload)

    monkeypatch.setattr(store, "_event", crash_before_terminal_event)
    with pytest.raises(RuntimeError, match="injected crash after artifact rows"):
        store.finish_run(
            bundle, envelope["run"]["id"], envelope["lease"]["token"],
            status="succeeded", output=output, failure=None, actor="test",
        )

    with store._connect() as db:
        run = db.execute("SELECT status,output_json FROM runs WHERE id=?", (envelope["run"]["id"],)).fetchone()
        artifacts = db.execute("SELECT COUNT(*) FROM artifacts WHERE producing_run_id=?", (envelope["run"]["id"],)).fetchone()[0]
    assert tuple(run) == ("running", None)
    assert artifacts == 0
    assert produced_paths and all(path.is_file() for path in produced_paths)
    assert store.integrity_report()["event_chain_ok"] is True


def test_duplicate_result_delivery_cannot_create_a_second_terminal_transition(tmp_path: Path):
    bundle, store, config_id = initialized(tmp_path, commissioned_bundle())
    deployment_id, deployment = active_deployment(store, config_id)
    job = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={"include_gpu": False},
        idempotency_key="duplicate-result", created_by="test", requested_machine_id="trainbox",
    )
    service = MissionHubService(store, bundle)
    envelope = service.lease_envelope(machine_id="trainbox", deployment_id=deployment_id, actor="test")
    store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="test")
    result = TrainboxAgent(bundle, machine_id="trainbox", deployment=deployment).execute(envelope)
    service.accept_result(envelope, result, actor="test")
    event_count = store.integrity_report()["event_count"]
    with pytest.raises(Exception, match="already succeeded"):
        service.accept_result(envelope, result, actor="duplicate-delivery")
    assert store.integrity_report()["event_count"] == event_count
    assert store.list_rows("jobs", limit=1)[0]["status"] == "succeeded"


def test_fresh_store_after_interrupted_run_recovers_from_persisted_lease_only(tmp_path: Path):
    bundle = commissioned_bundle()
    bundle.base["scheduler"]["lease_seconds"] = 1
    bundle, store, config_id = initialized(tmp_path, bundle)
    deployment_id, _ = active_deployment(store, config_id)
    job = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={}, idempotency_key="worker-restart",
        created_by="test", requested_machine_id="trainbox",
    )
    service = MissionHubService(store, bundle)
    envelope = service.lease_envelope(machine_id="trainbox", deployment_id=deployment_id, actor="test")
    store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="test")
    with store.transaction() as db:
        db.execute("UPDATE runs SET lease_expires_at='2000-01-01T00:00:00Z' WHERE id=?", (envelope["run"]["id"],))

    restarted = MissionHubStore(store.path)
    assert restarted.expire_leases(bundle, actor="fresh-daemon") == 1
    assert restarted.list_rows("jobs", limit=1)[0]["status"] == "queued"
    assert restarted.list_rows("runs", limit=1)[0]["status"] == "expired"
    incident = RecoveryManager(restarted, bundle).incident_for_job(job["id"])
    assert incident is not None and incident["state"] == "monitoring"
    assert restarted.integrity_report()["event_chain_ok"] is True


def test_schema_16_restart_adds_incident_thread_link_without_losing_state(tmp_path: Path):
    store = MissionHubStore(tmp_path / "migration.sqlite3")
    store.initialize()
    with store._connect() as db:
        db.execute("ALTER TABLE recovery_incidents DROP COLUMN operational_thread_id")
        db.execute("UPDATE metadata SET value='16' WHERE key='schema_version'")

    MissionHubStore(store.path).initialize()

    with store._connect() as db:
        version = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0]
        columns = {row[1] for row in db.execute("PRAGMA table_info(recovery_incidents)")}
    assert version == "19"
    assert "operational_thread_id" in columns


def test_concurrent_startup_serializes_schema_migration(tmp_path: Path):
    store = MissionHubStore(tmp_path / "concurrent-migration.sqlite3")
    store.initialize()
    with store._connect() as db:
        for column in ("wait_check_count", "wait_reason", "next_check_at", "wait_started_at"):
            db.execute(f"ALTER TABLE operational_responses DROP COLUMN {column}")
        db.execute("UPDATE metadata SET value='18' WHERE key='schema_version'")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: MissionHubStore(store.path).initialize(), range(2)))

    assert results == [None, None]
    with store._connect() as db:
        assert db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] == "19"
