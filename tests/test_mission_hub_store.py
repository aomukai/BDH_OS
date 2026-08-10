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
    store.request_pipeline_state("running", actor="test")
    store.apply_pipeline_state(actor="test-daemon")
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


def test_queue_age_does_not_expire_before_job_becomes_available(tmp_path: Path) -> None:
    bundle, store, config_id = initialized(tmp_path, commissioned_bundle())
    deployment_id, _ = active_deployment(store, config_id)
    job = store.create_job(
        bundle,
        job_type="system.healthcheck",
        input_payload={},
        idempotency_key="future-job",
        created_by="test",
        requested_machine_id="trainbox",
        available_at="2099-01-01T00:00:00Z",
    )
    with store.transaction() as db:
        db.execute(
            "UPDATE jobs SET created_at='2000-01-01T00:00:00Z',updated_at='2000-01-01T00:00:00Z' WHERE id=?",
            (job["id"],),
        )

    assert store.lease_next(
        bundle, machine_id="trainbox", deployment_id=deployment_id, actor="agent",
    ) is None
    with store._connect() as db:
        status = db.execute("SELECT status FROM jobs WHERE id=?", (job["id"],)).fetchone()[0]
    assert status == "queued"


def test_on_call_job_leases_before_equal_priority_ordinary_work(tmp_path: Path) -> None:
    bundle, store, config_id = initialized(tmp_path)
    manifest = {
        "machine_id": "mission-hub", "role": "mission_hub", "release_id": "test-release",
        "source_sha256": "1" * 64, "environment_sha256": "2" * 64,
        "config_snapshot_id": config_id,
    }
    deployment_id = store.register_deployment(manifest, actor="test", activate=True)
    store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="ordinary-equal-priority", created_by="test",
        requested_machine_id="mission-hub", approved=True,
    )
    on_call = store.create_job(
        bundle, job_type="operations.respond",
        input_payload={
            "thread_id": "thread-test", "message_id": "message-test",
            "subject": "Operational notice", "body": "A failure needs assessment.",
            "context_messages": [{
                "id": "message-test", "sender": "mission_hub",
                "body": "A failure needs assessment.", "created_at": "2026-01-01T00:00:00Z",
            }],
            "context_truncated": False,
        },
        idempotency_key="on-call-priority", created_by="test",
        requested_machine_id="mission-hub", approved=True,
    )

    leased, _ = store.lease_next(
        bundle, machine_id="mission-hub", deployment_id=deployment_id, actor="agent",
    )

    assert leased["id"] == on_call["id"]


def test_commissioned_training_still_requires_its_complete_contract(tmp_path: Path) -> None:
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
    with pytest.raises(ValueError, match="missing required"):
        store.create_job(
            bundle,
            job_type="model.train",
            input_payload={},
            idempotency_key="train-1",
            created_by="test",
        )
    with pytest.raises(SafetyError, match="disabled"):
        store.create_job(
            bundle, job_type="executor.generate", input_payload={},
            idempotency_key="generate-1", created_by="test",
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


def test_metered_provider_jobs_reserve_budget_transactionally(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.base["safety"]["live_execution"] = True
    bundle.jobs["visual.plan"]["enabled"] = True
    bundle.prompts["visual-plan-v1"]["enabled"] = True
    bundle.routes["visual-planning"]["enabled"] = True
    bundle.routes["visual-planning"]["ordered_model_ids"] = ["deepseek-v4-flash-official"]
    for model_id in bundle.routes["visual-planning"]["ordered_model_ids"]:
        bundle.models[model_id]["enabled"] = True
        bundle.providers[bundle.models[model_id]["provider"]]["enabled"] = True
    bundle.budget.update({
        "external_calls_enabled": True, "monthly_limit": 3.0, "weekly_limit": 3.0,
        "per_run_approval_above": 10.0, "emergency_reserve": 0.0, "hard_stop_fraction": 1.0,
    })
    _, store, _ = initialized(tmp_path, bundle)
    payload = {"input_artifact_ids": [], "specification": {"goal": "red ball"}, "limits": {}}
    first = store.create_job(bundle, job_type="visual.plan", input_payload=payload, idempotency_key="visual-budget-1", created_by="test")
    assert first["status"] == "awaiting_approval"
    with pytest.raises(SafetyError, match="budget hard stop"):
        store.create_job(bundle, job_type="visual.plan", input_payload=payload, idempotency_key="visual-budget-2", created_by="test")


def test_zero_external_budget_values_mean_unlimited(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.base["safety"]["live_execution"] = True
    bundle.jobs["visual.plan"]["enabled"] = True
    bundle.prompts["visual-plan-v1"]["enabled"] = True
    route = bundle.routes["visual-planning"]
    route.update({"enabled": True, "ordered_model_ids": ["deepseek-v4-flash-0731-openrouter"], "max_cost_usd": 0.0})
    bundle.models["deepseek-v4-flash-0731-openrouter"]["enabled"] = True
    bundle.providers["openrouter"]["enabled"] = True
    bundle.budget.update({
        "external_calls_enabled": True, "monthly_limit": 0.0, "weekly_limit": 0.0,
        "per_run_approval_above": 0.0, "emergency_reserve": 0.0,
    })
    _, store, _ = initialized(tmp_path, bundle)
    job = store.create_job(
        bundle, job_type="visual.plan",
        input_payload={"input_artifact_ids": [], "specification": {"goal": "red ball"}, "limits": {}},
        idempotency_key="unlimited-external", created_by="test",
    )
    assert job["status"] == "awaiting_approval"  # the job's explicit approval policy, not a cost threshold
    with store._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM budget_reservations").fetchone()[0] == 0


def test_trainbox_maintenance_mode_refuses_leases(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.machines["trainbox"]["maintenance_mode"] = True
    bundle, store, config_id = initialized(tmp_path, bundle)
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


def test_paused_pipeline_cannot_issue_a_new_lease(tmp_path: Path) -> None:
    bundle, store, config_id = initialized(tmp_path, commissioned_bundle())
    deployment_id, _ = active_deployment(store, config_id)
    store.create_job(bundle, job_type="system.healthcheck", input_payload={}, idempotency_key="pause-before-lease", created_by="test")
    store.request_pipeline_state("paused", actor="operator")
    assert store.lease_next(bundle, machine_id="trainbox", deployment_id=deployment_id, actor="agent") is None
    store.request_pipeline_state("running", actor="operator")
    store.apply_pipeline_state(actor="test-daemon")
    assert store.lease_next(bundle, machine_id="trainbox", deployment_id=deployment_id, actor="agent") is not None


def test_superseded_config_job_is_neither_leased_nor_reported_as_next(tmp_path: Path) -> None:
    bundle, store, config_id = initialized(tmp_path, commissioned_bundle())
    deployment_id, _ = active_deployment(store, config_id)
    stale = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="stale-config-job", created_by="test",
        requested_machine_id="trainbox",
    )
    current = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={"include_gpu": True},
        idempotency_key="current-config-job", created_by="test",
        requested_machine_id="trainbox",
    )
    with store.transaction() as db:
        db.execute(
            """INSERT INTO config_snapshots(id,sha256,state,payload_json,created_at,actor)
               SELECT 'cfg-superseded-test',printf('%064d',7),'superseded',payload_json,created_at,'test'
               FROM config_snapshots WHERE id=?""",
            (config_id,),
        )
        db.execute(
            "UPDATE jobs SET config_snapshot_id='cfg-superseded-test' WHERE id=?",
            (stale["id"],),
        )

    assert store.next_queued_job()["id"] == current["id"]
    leased, _ = store.lease_next(
        bundle, machine_id="trainbox", deployment_id=deployment_id, actor="agent",
    )
    assert leased["id"] == current["id"]


def test_latest_terminal_job_uses_completion_transition_not_creation_order(tmp_path: Path) -> None:
    bundle, store, _ = initialized(tmp_path)
    completed = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="completed-before-newer-queue", created_by="test",
    )
    store.create_job(
        bundle, job_type="system.healthcheck", input_payload={"include_gpu": True},
        idempotency_key="newer-still-queued", created_by="test",
    )
    with store.transaction() as db:
        db.execute(
            "UPDATE jobs SET status='succeeded',updated_at='2099-01-02T03:04:05Z' WHERE id=?",
            (completed["id"],),
        )

    assert store.latest_terminal_job()["id"] == completed["id"]


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
        "event_count": 9,
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
        input_payload={
            "corpus_artifact_id": corpus_id,
            "expected_rows": 1,
            "identity_scope": "excluded",
            "ordered_concepts": [{"concept": "test", "depends_on": []}],
        },
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
