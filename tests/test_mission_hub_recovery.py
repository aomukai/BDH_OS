from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from mission_hub.config import bundle_from_snapshot, load_config_bundle
from mission_hub.agent import TrainboxAgent
from mission_hub.operations_workflow import OperationalResponseCoordinator
from mission_hub.recovery import RecoveryCoordinator, RecoveryManager
from mission_hub.repair_driver import BoundedCodexRepairDriver
from mission_hub.service import MissionHubService
from mission_hub.store import MissionHubStore
from mission_hub.protocol import build_result_envelope


REPO = Path(__file__).resolve().parents[1]


def ready(tmp_path: Path, *, max_repair_attempts: int = 2):
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    state = tmp_path / "state"
    library = tmp_path / "training_data"
    library.mkdir()
    bundle.base["hub"]["state_root"] = str(state)
    bundle.failure_logging["root"] = str(state / "critical-failures")
    bundle.contracts["training_library_root"] = str(library)
    bundle.machines["mission-hub"]["state_root"] = str(state)
    bundle.machines["mission-hub"]["artifact_roots"] = [str(library)]
    bundle.machines["mission-hub"]["release_install_root"] = str(state / "releases")
    bundle.machines["mission-hub"]["active_release_link"] = str(state / "releases" / "current")
    bundle.recovery["max_repair_attempts"] = max_repair_attempts
    bundle.retry_policies["infrastructure_only"]["max_repair_attempts"] = max_repair_attempts
    bundle.retry_policies["infrastructure_only"]["backoff_seconds"] = [0, 0]
    bundle.jobs["corpus.build"]["max_attempts"] = 1
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    failed_deployment_id = store.register_deployment({
        "machine_id": "mission-hub", "role": "mission_hub", "release_id": "release-broken",
        "source_sha256": "1" * 64, "environment_sha256": "2" * 64,
        "config_snapshot_id": config_id,
    }, actor="test", activate=True)
    store.request_pipeline_state("running", actor="test")
    store.apply_pipeline_state(actor="test")
    return store, bundle, library, config_id, failed_deployment_id


def fail_corpus(store: MissionHubStore, bundle, *, code="artifact_contract_invalid", failure_class="deterministic_specification", campaign_id=None):
    job = store.create_job(
        bundle, job_type="corpus.build",
        input_payload={"corpus_name": "recovery", "source_paths": ["source.md"], "normalization": "utf8_lf", "record_format": "ninereeds_document_v1"},
        idempotency_key="recovery-corpus", created_by="test", requested_machine_id="mission-hub", approved=True,
        campaign_id=campaign_id,
    )
    service = MissionHubService(store, bundle)
    deployment = store.active_deployment("mission-hub")
    envelope = service.lease_envelope(machine_id="mission-hub", deployment_id=deployment["id"], actor="test")
    assert envelope is not None
    store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="test")
    service.record_failure(
        envelope, failure_class=failure_class, code=code,
        message="controlled producer emitted zero required artifacts", actor="test",
    )
    return job, envelope


def run_retried_corpus(store: MissionHubStore, bundle):
    service = MissionHubService(store, bundle)
    deployment = store.active_deployment("mission-hub")
    envelope = service.lease_envelope(machine_id="mission-hub", deployment_id=deployment["id"], actor="test")
    assert envelope is not None
    store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="test")
    assert service.execute_and_record("mission-hub", envelope, actor="test") == "succeeded"
    return envelope


class SuccessfulRepairDriver:
    def __init__(self, store: MissionHubStore, bundle, config_id: str, root: Path):
        self.store, self.bundle, self.config_id, self.root = store, bundle, config_id, root

    def _evidence_file(self, name: str, body: bytes):
        path = self.root / "state" / "recovery-evidence" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return str(path), hashlib.sha256(body).hexdigest(), len(body)

    def repair(self, context):
        patch_uri, patch_sha, patch_bytes = self._evidence_file("repair.patch", b"controlled producer adapter fix\n")
        targeted_uri, targeted_sha, targeted_bytes = self._evidence_file("targeted.log", b"2 passed\n")
        regression_uri, regression_sha, regression_bytes = self._evidence_file("regression.log", b"160 passed\n")
        deployment_id = self.store.register_deployment({
            "machine_id": "mission-hub", "role": "mission_hub", "release_id": "release-repaired",
            "source_sha256": "3" * 64, "environment_sha256": "2" * 64,
            "config_snapshot_id": self.config_id,
        }, actor="test:repair-driver", activate=True)
        return {
            "succeeded": True, "summary": "producer adapter repaired and validated",
            "actions": [
                {"kind": "source_patch", "status": "succeeded", "evidence": {
                    "changed_files": ["mission_hub/handlers/contracts.py"], "patch_sha256": patch_sha,
                    "patch_uri": patch_uri, "patch_bytes": patch_bytes,
                }},
                {"kind": "tests", "status": "succeeded", "evidence": {
                    "scope": "targeted", "command": ["python3", "-m", "pytest", "-q", "tests/test_mission_hub_recovery.py"],
                    "exit_code": 0, "passed": True, "transcript_uri": targeted_uri,
                    "transcript_sha256": targeted_sha, "transcript_bytes": targeted_bytes,
                }},
                {"kind": "tests", "status": "succeeded", "evidence": {
                    "scope": "regression", "command": ["python3", "-m", "pytest", "-q"],
                    "exit_code": 0, "passed": True, "transcript_uri": regression_uri,
                    "transcript_sha256": regression_sha, "transcript_bytes": regression_bytes,
                }},
                {"kind": "deployment", "status": "succeeded", "evidence": {
                    "before_deployment_id": context["failed_deployment"]["id"],
                    "after_deployment_id": deployment_id, "active": True,
                    "source_sha256": "3" * 64, "release_id": "release-repaired",
                }},
            ],
        }


class FailingRepairDriver:
    def repair(self, context):
        return {"succeeded": False, "failure_code": "targeted_tests_failed", "summary": "targeted test exposed a bad first patch", "actions": []}


def start_repair(store, bundle, job_id: str):
    manager = RecoveryManager(store, bundle)
    incident = manager.incident_for_job(job_id)
    assert incident is not None
    store.request_pipeline_state("paused", actor="test:on-call")
    attempt = manager.start_attempt(incident["id"], "controlled_repair", actor="test:on-call")
    return incident, attempt


def test_deterministic_producer_defect_repairs_deploys_retries_and_recovers_after_restart(tmp_path: Path):
    store, bundle, library, config_id, _ = ready(tmp_path)
    (library / "source.md").write_text("immutable material\n", encoding="utf-8")
    job, failed = fail_corpus(store, bundle)
    incident, attempt = start_repair(store, bundle, job["id"])

    # A fresh store/coordinator instance has no conversational state.
    restarted_store = MissionHubStore(store.path)
    coordinator = RecoveryCoordinator(
        restarted_store, bundle, SuccessfulRepairDriver(restarted_store, bundle, config_id, tmp_path),
    )
    assert coordinator.tick(actor="test:on-call") == 1
    queued = restarted_store.list_rows("jobs", limit=1)[0]
    assert queued["status"] == "queued"
    assert queued["operator_restart_count"] == 1

    successful = run_retried_corpus(restarted_store, bundle)
    assert RecoveryCoordinator(restarted_store, bundle).tick(actor="test:verify") == 1
    recovered = RecoveryManager(restarted_store, bundle).get(incident["id"])
    assert recovered["state"] == "recovered"
    assert recovered["verification"]["successful_run_id"] == successful["run"]["id"]
    kinds = [action["kind"] for action in recovered["attempts"][0]["actions"]]
    assert kinds == ["evidence_preserved", "source_patch", "tests", "tests", "deployment", "job_retry", "artifact_validation", "health_check"]
    assert recovered["operational_thread_id"]
    with restarted_store._connect() as db:
        projection = db.execute(
            "SELECT body FROM thread_messages WHERE thread_id=? ORDER BY created_at DESC LIMIT 1",
            (recovered["operational_thread_id"],),
        ).fetchone()[0]
    assert "Recovery verified from authoritative action records" in projection
    assert successful["run"]["id"] in projection
    assert restarted_store.integrity_report()["event_chain_ok"] is True


def test_transient_provider_or_transport_failure_retries_without_source_mutation(tmp_path: Path):
    store, bundle, library, config_id, deployment_id = ready(tmp_path)
    bundle.jobs["corpus.build"]["max_attempts"] = 2
    (library / "source.md").write_text("retry material\n", encoding="utf-8")
    job, failed = fail_corpus(store, bundle, code="transport_unavailable", failure_class="operational_transient")
    incident = RecoveryManager(store, bundle).incident_for_job(job["id"])
    assert incident["state"] == "monitoring"
    assert store.list_rows("jobs", limit=1)[0]["status"] == "queued"
    successful = run_retried_corpus(store, bundle)
    assert RecoveryCoordinator(store, bundle).tick(actor="test") == 1
    recovered = RecoveryManager(store, bundle).get(incident["id"])
    assert recovered["state"] == "recovered"
    assert not any(action["kind"] == "source_patch" for action in recovered["attempts"][0]["actions"])
    assert store.active_deployment("mission-hub")["id"] == deployment_id


def test_failed_first_repair_is_preserved_and_second_attempt_can_recover(tmp_path: Path):
    store, bundle, library, config_id, _ = ready(tmp_path, max_repair_attempts=2)
    (library / "source.md").write_text("retry repair\n", encoding="utf-8")
    job, _ = fail_corpus(store, bundle)
    incident, first = start_repair(store, bundle, job["id"])
    RecoveryCoordinator(store, bundle, FailingRepairDriver()).tick(actor="test:on-call")
    after_first = RecoveryManager(store, bundle).get(incident["id"])
    assert after_first["state"] == "classified"
    assert after_first["attempts"][0]["state"] == "failed"
    second = RecoveryManager(store, bundle).start_attempt(incident["id"], "second_patch", actor="test:on-call")
    RecoveryCoordinator(store, bundle, SuccessfulRepairDriver(store, bundle, config_id, tmp_path)).tick(actor="test:on-call")
    run_retried_corpus(store, bundle)
    RecoveryCoordinator(store, bundle).tick(actor="test:verify")
    recovered = RecoveryManager(store, bundle).get(incident["id"])
    assert recovered["state"] == "recovered"
    assert [attempt["state"] for attempt in recovered["attempts"]] == ["failed", "succeeded"]


def test_campaign_block_resolves_only_after_verified_successor_run(tmp_path: Path):
    store, bundle, library, config_id, _ = ready(tmp_path)
    (library / "source.md").write_text("campaign repair\n", encoding="utf-8")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns(id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES('campaign-recovery','Recovery','active',?,'prove unblocking','{}','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')""",
            (config_id,),
        )
    job, _ = fail_corpus(store, bundle, campaign_id="campaign-recovery")
    incident, _ = start_repair(store, bundle, job["id"])
    assert len(store.campaign_blocks("campaign-recovery", active_only=True)) == 1
    RecoveryCoordinator(store, bundle, SuccessfulRepairDriver(store, bundle, config_id, tmp_path)).tick(actor="test:on-call")
    # A queued repaired job is progress, but not yet proof that the campaign is healthy.
    assert len(store.campaign_blocks("campaign-recovery", active_only=True)) == 1
    run_retried_corpus(store, bundle)
    RecoveryCoordinator(store, bundle).tick(actor="test:verify")
    assert store.campaign_blocks("campaign-recovery", active_only=True) == []
    block = store.campaign_blocks("campaign-recovery")[0]
    assert block["state"] == "resolved"
    assert block["resolution"]["incident_id"] == incident["id"]


def test_false_repair_claim_cannot_retry_or_close_incident(tmp_path: Path):
    store, bundle, library, config_id, _ = ready(tmp_path)
    (library / "source.md").write_text("safe\n", encoding="utf-8")
    job, _ = fail_corpus(store, bundle)
    incident, attempt = start_repair(store, bundle, job["id"])
    with pytest.raises(Exception, match="patch evidence"):
        RecoveryManager(store, bundle).record_action(attempt["id"], "source_patch", "succeeded", {
            "changed_files": [], "patch_sha256": "a" * 64,
        }, actor="liar")
    result = OperationalResponseCoordinator(store, bundle)._act({
        "action": "retry_failed_job", "target_job_id": job["id"],
        "recovery_attempt_id": attempt["id"], "assessment": "fixed", "reasoning": "fixed",
    }, actor="liar")
    assert result["applied"] is False
    assert store.list_rows("jobs", limit=1)[0]["status"] == "failed"
    assert RecoveryManager(store, bundle).get(incident["id"])["state"] == "repairing"


def test_configuration_repair_requires_config_change_not_source_patch(tmp_path: Path):
    store, bundle, library, config_id, _ = ready(tmp_path)
    (library / "source.md").write_text("config\n", encoding="utf-8")
    job, _ = fail_corpus(store, bundle, code="configuration_invalid")
    incident, attempt = start_repair(store, bundle, job["id"])
    assert incident["category"] == "configuration"
    with pytest.raises(Exception, match="configuration_change"):
        RecoveryManager(store, bundle).require_ready_for_retry(attempt["id"])


def test_bad_configuration_rolls_back_known_good_roles_and_continues(tmp_path: Path):
    store, good_bundle, library, good_config_id, good_deployment_id = ready(tmp_path)
    (library / "source.md").write_text("config rollback\n", encoding="utf-8")
    store.register_deployment({
        "machine_id": "trainbox", "role": "trainbox", "release_id": "release-trainbox-good",
        "source_sha256": "5" * 64, "environment_sha256": "6" * 64,
        "config_snapshot_id": good_config_id,
    }, actor="test:good-config", activate=True)
    bad_bundle = replace(good_bundle, sha256="b" * 64)
    bad_config_id = store.activate_config(bad_bundle, actor="test:bad-config")
    bad_deployment_id = store.register_deployment({
        "machine_id": "mission-hub", "role": "mission_hub", "release_id": "release-bad-config",
        "source_sha256": "4" * 64, "environment_sha256": "2" * 64,
        "config_snapshot_id": bad_config_id,
    }, actor="test:bad-config", activate=True)
    job, _ = fail_corpus(store, bad_bundle, code="configuration_invalid")
    incident, attempt = start_repair(store, bad_bundle, job["id"])

    RecoveryCoordinator(
        store, bad_bundle, BoundedCodexRepairDriver(store, bad_bundle, repo_root=REPO),
    ).tick(actor="test:on-call")

    active = store.active_config()
    assert active["id"] == good_config_id
    assert store.active_deployment("mission-hub")["id"] == good_deployment_id
    restored_bundle = bundle_from_snapshot(REPO / "config" / "mission_hub", active["payload"])
    run_retried_corpus(store, restored_bundle)
    RecoveryCoordinator(store, restored_bundle).tick(actor="test:verify")
    recovered = RecoveryManager(store, restored_bundle).get(incident["id"])
    assert recovered["state"] == "recovered"
    assert any(action["kind"] == "configuration_change" for action in recovered["attempts"][0]["actions"])


@pytest.mark.parametrize("kinds", [[], ["corpus", "corpus"], ["log"], ["corpus", "corpus_manifest", "log"]])
def test_output_artifact_cardinality_and_type_fail_before_result_envelope(tmp_path: Path, kinds):
    store, bundle, library, config_id, _ = ready(tmp_path)
    declarations = [{"kind": kind} for kind in kinds]
    with pytest.raises((ValueError, TypeError), match="exactly one|unexpected"):
        TrainboxAgent._validate_output_artifacts(
            declarations, bundle.machines["mission-hub"], bundle.jobs["corpus.build"],
        )


def test_malformed_remote_success_is_preserved_as_immutable_failed_output(tmp_path: Path):
    store, bundle, library, config_id, _ = ready(tmp_path)
    (library / "source.md").write_text("evidence\n", encoding="utf-8")
    job = store.create_job(
        bundle, job_type="corpus.build",
        input_payload={"corpus_name": "bad-result", "source_paths": ["source.md"], "normalization": "utf8_lf", "record_format": "ninereeds_document_v1"},
        idempotency_key="bad-result", created_by="test", requested_machine_id="mission-hub", approved=True,
    )
    service = MissionHubService(store, bundle)
    deployment = store.active_deployment("mission-hub")
    envelope = service.lease_envelope(machine_id="mission-hub", deployment_id=deployment["id"], actor="test")
    store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="test")
    malformed = {"status": "succeeded", "artifacts": [], "metrics": {}, "failure": None}
    result = build_result_envelope(envelope, malformed)
    service.execute_envelope = lambda machine_id, selected: result

    assert service.execute_and_record("mission-hub", envelope, actor="test") == "failed"
    run = store.list_rows("runs", limit=1)[0]
    failure = json.loads(run["failure_json"])
    assert run["failure_code"] == "artifact_contract_invalid"
    artifact = store.artifact_at(failure["failed_output_artifact_id"], machine_id="mission-hub")
    assert artifact["kind"] == "failed_output_evidence"
    assert artifact["sha256"] == failure["failed_output_sha256"]
