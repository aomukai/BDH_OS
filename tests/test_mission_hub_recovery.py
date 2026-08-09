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


def test_verified_recovery_retry_dispatches_before_unrelated_higher_priority_work(tmp_path: Path):
    store, bundle, library, config_id, _ = ready(tmp_path)
    (library / "failed.md").write_text("failed work\n", encoding="utf-8")
    (library / "ordinary.md").write_text("ordinary work\n", encoding="utf-8")
    repaired_job, _ = fail_corpus(store, bundle)
    incident, _ = start_repair(store, bundle, repaired_job["id"])
    ordinary = store.create_job(
        bundle, job_type="corpus.build",
        input_payload={
            "corpus_name": "ordinary", "source_paths": ["ordinary.md"],
            "normalization": "utf8_lf", "record_format": "ninereeds_document_v1",
        },
        idempotency_key="ordinary-higher-priority", created_by="test",
        requested_machine_id="mission-hub", approved=True,
    )
    with store.transaction() as db:
        db.execute("UPDATE jobs SET priority=999 WHERE id=?", (ordinary["id"],))

    RecoveryCoordinator(
        store, bundle, SuccessfulRepairDriver(store, bundle, config_id, tmp_path),
    ).tick(actor="test:on-call")
    deployment = store.active_deployment("mission-hub")
    envelope = MissionHubService(store, bundle).lease_envelope(
        machine_id="mission-hub", deployment_id=deployment["id"], actor="test",
    )

    assert envelope["job"]["id"] == repaired_job["id"]
    assert RecoveryManager(store, bundle).get(incident["id"])["state"] == "verifying"


def test_transient_provider_or_transport_failure_retries_without_source_mutation(tmp_path: Path):
    store, bundle, library, config_id, deployment_id = ready(tmp_path)
    bundle.jobs["corpus.build"]["max_attempts"] = 2
    (library / "source.md").write_text("retry material\n", encoding="utf-8")
    job, failed = fail_corpus(store, bundle, code="transport_unavailable", failure_class="operational_transient")
    manager = RecoveryManager(store, bundle)
    incident = manager.incident_for_job(job["id"])
    incident = manager.get(incident["id"])
    assert incident["state"] == "monitoring"
    assert store.list_rows("jobs", limit=1)[0]["status"] == "queued"
    successful = run_retried_corpus(store, bundle)
    assert RecoveryCoordinator(store, bundle).tick(actor="test") == 1
    recovered = RecoveryManager(store, bundle).get(incident["id"])
    assert recovered["state"] == "recovered"
    assert not any(action["kind"] == "source_patch" for action in recovered["attempts"][0]["actions"])
    assert store.active_deployment("mission-hub")["id"] == deployment_id


def test_retryable_malformed_output_is_monitored_and_closes_after_success(tmp_path: Path):
    store, bundle, library, _, deployment_id = ready(tmp_path)
    bundle.jobs["corpus.build"]["max_attempts"] = 2
    bundle.jobs["corpus.build"]["retry_policy"] = "classified"
    bundle.retry_policies["classified"]["backoff_seconds"] = [0]
    (library / "source.md").write_text("retry malformed output\n", encoding="utf-8")
    job, _ = fail_corpus(
        store, bundle, code="structured_response_invalid",
        failure_class="repairable_output",
    )
    manager = RecoveryManager(store, bundle)
    incident = manager.incident_for_job(job["id"])
    incident = manager.get(incident["id"])

    assert incident["state"] == "monitoring"
    assert incident["attempts"][0]["strategy"] == "deterministic_retry"
    assert not any(action["kind"] == "source_patch" for action in incident["attempts"][0]["actions"])
    successful = run_retried_corpus(store, bundle)
    assert RecoveryCoordinator(store, bundle).tick(actor="test:verify") == 1
    recovered = RecoveryManager(store, bundle).get(incident["id"])
    assert recovered["state"] == "recovered"
    assert recovered["verification"]["successful_run_id"] == successful["run"]["id"]
    assert store.active_deployment("mission-hub")["id"] == deployment_id


def test_cancelled_configured_retry_closes_with_machine_readable_blocker(tmp_path: Path):
    store, bundle, library, _, _ = ready(tmp_path)
    bundle.jobs["corpus.build"]["max_attempts"] = 2
    (library / "source.md").write_text("cancel retry\n", encoding="utf-8")
    job, _ = fail_corpus(
        store, bundle, code="transport_unavailable",
        failure_class="operational_transient",
    )
    incident = RecoveryManager(store, bundle).incident_for_job(job["id"])
    store.cancel_job(
        job["id"], reason="authorized deployment boundary cancelled the stale retry", actor="test:operator",
    )

    assert RecoveryCoordinator(store, bundle).tick(actor="test:verify") == 1
    closed = RecoveryManager(store, bundle).get(incident["id"])
    assert closed["state"] == "blocked"
    assert closed["blocker_code"] == "operator_cancelled"
    assert closed["attempts"][0]["state"] == "failed"
    assert closed["attempts"][0]["actions"][-1]["kind"] == "health_check"


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


def test_sol_on_call_repairs_have_no_numeric_attempt_ceiling(tmp_path: Path):
    store, bundle, library, _, _ = ready(tmp_path, max_repair_attempts=2)
    (library / "source.md").write_text("iterative repair\n", encoding="utf-8")
    job, _ = fail_corpus(store, bundle)
    manager = RecoveryManager(store, bundle)
    incident = manager.incident_for_job(job["id"])
    assert incident is not None
    assert incident["state"] == "classified"
    assert incident["repair_budget"] == 0

    for ordinal in range(1, 5):
        attempt = manager.start_attempt(
            incident["id"], f"diagnostic_iteration_{ordinal}", actor="test:sol-on-call",
        )
        assert attempt["ordinal"] == ordinal
        RecoveryCoordinator(store, bundle, FailingRepairDriver()).tick(actor="test:sol-on-call")
        current = manager.get(incident["id"])
        assert current["state"] == "classified"
        assert current["blocker_code"] is None
        assert current["attempts"][-1]["state"] == "failed"

    started = next(
        row for row in store.list_rows("events", limit=100)
        if row["event_type"] == "recovery.attempt_started"
    )
    payload = json.loads(started["payload_json"])
    assert payload["consumes_budget"] is False
    assert payload["repair_attempt_limit"] is None


def test_external_verified_repair_can_reenter_budget_exhausted_incident(tmp_path: Path):
    store, bundle, library, _, _ = ready(tmp_path, max_repair_attempts=1)
    (library / "source.md").write_text("external repair\n", encoding="utf-8")
    job, _ = fail_corpus(store, bundle)
    incident, _ = start_repair(store, bundle, job["id"])
    RecoveryCoordinator(store, bundle, FailingRepairDriver()).tick(actor="test:on-call")
    # Historical incidents created by older releases may still carry a
    # terminal budget-exhausted state. Preserve their explicit operator
    # re-entry path even though new Sol-managed incidents never enter it.
    with store.transaction() as db:
        db.execute(
            """UPDATE recovery_incidents SET state='escalated',repair_budget=1,
               blocker_code='repair_budget_exhausted',blocker_detail='legacy attempt ceiling',
               closed_at=updated_at WHERE id=?""",
            (incident["id"],),
        )
    exhausted = RecoveryManager(store, bundle).get(incident["id"])
    assert exhausted["state"] == "escalated"
    assert exhausted["blocker_code"] == "repair_budget_exhausted"

    external = RecoveryManager(store, bundle).start_external_repair(
        incident["id"], "operator_verified_patch",
        authorization_reference="change-request:test-42", actor="test:operator",
    )

    reopened = RecoveryManager(store, bundle).get(incident["id"])
    assert external["ordinal"] == 2
    assert external["state"] == "planned"
    assert reopened["state"] == "repairing"
    assert reopened["repair_budget"] == 1
    assert [attempt["state"] for attempt in reopened["attempts"]] == ["failed", "planned"]
    event = next(
        row for row in store.list_rows("events", limit=100)
        if row["event_type"] == "recovery.external_repair_started"
    )
    assert json.loads(event["payload_json"])["autonomous_budget_extended"] is False


def test_bounded_repair_uses_current_noninteractive_codex_cli_contract(tmp_path: Path):
    store, bundle, _, _, _ = ready(tmp_path)
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        Path(command[command.index("--output-last-message") + 1]).write_text("done\n", encoding="utf-8")
        return __import__("subprocess").CompletedProcess(command, 0, stdout="", stderr="")

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    request = tmp_path / "request.json"
    request.write_text("{}\n", encoding="utf-8")
    driver = BoundedCodexRepairDriver(store, bundle, runner=runner, repo_root=REPO)
    log = driver._invoke_codex(worktree, request, "rat-cli-contract")

    assert log.is_file()
    final_path = Path(commands[0][commands[0].index("--output-last-message") + 1])
    assert worktree not in final_path.parents
    assert final_path.name == "codex-final.txt"
    assert commands[0][1] == "exec"
    assert "--approve-for-me" in commands[0]
    assert "--ask-for-approval" not in commands[0]
    assert "--sandbox" not in commands[0]


def test_bounded_repair_reads_git_paths_without_dropping_first_character(tmp_path: Path):
    driver = BoundedCodexRepairDriver.__new__(BoundedCodexRepairDriver)
    outputs = {
        "diff": b"mission_hub/handlers/visual_provider.py\0tests/test_visual.py\0",
        "ls-files": b"mission_hub/new_helper.py\0",
    }
    driver._git_bytes = lambda _root, command, *_args: outputs[command]

    assert driver._changed_files(tmp_path) == [
        "mission_hub/handlers/visual_provider.py",
        "mission_hub/new_helper.py",
        "tests/test_visual.py",
    ]


def test_bounded_repair_copies_archived_regression_fixture_then_removes_it(tmp_path: Path):
    repository = tmp_path / "repository"
    worktree = tmp_path / "worktree"
    files = [
        Path("archive/workstation/evaluation.json"),
        Path("archive/workstation/baseline.json"),
    ]
    directory = Path("training_data/campaign/material")
    campaigns = repository / "config/mission_hub/campaigns"
    campaigns.mkdir(parents=True)
    (campaigns / "campaign.json").write_text(
        json.dumps({"inputs": [*(str(value) for value in files), str(directory)]}) + "\n",
        encoding="utf-8",
    )
    for relative in files:
        source = repository / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f'{{"fixture": "{relative.name}"}}\n', encoding="utf-8")
    material = repository / directory / "material.jsonl"
    material.parent.mkdir(parents=True)
    material.write_text('{"material": true}\n', encoding="utf-8")
    worktree.mkdir()
    driver = BoundedCodexRepairDriver.__new__(BoundedCodexRepairDriver)
    driver.repo_root = repository

    with driver._regression_fixtures(worktree):
        for relative in files:
            target = worktree / relative
            source = repository / relative
            assert target.read_bytes() == source.read_bytes()
            target.write_text('{"mutated": true}\n', encoding="utf-8")
            assert source.read_text(encoding="utf-8") == f'{{"fixture": "{relative.name}"}}\n'
        copied_material = worktree / directory / "material.jsonl"
        assert copied_material.read_bytes() == material.read_bytes()
        copied_material.write_text('{"mutated": true}\n', encoding="utf-8")
        assert material.read_text(encoding="utf-8") == '{"material": true}\n'

    assert not (worktree / "archive").exists()
    assert not (worktree / "training_data").exists()


def test_failed_successor_returns_same_incident_to_unbounded_on_call_repair(tmp_path: Path):
    store, bundle, library, config_id, _ = ready(tmp_path, max_repair_attempts=2)
    (library / "source.md").write_text("successor validation\n", encoding="utf-8")
    job, _ = fail_corpus(store, bundle)
    incident, _ = start_repair(store, bundle, job["id"])
    RecoveryCoordinator(
        store, bundle, SuccessfulRepairDriver(store, bundle, config_id, tmp_path),
    ).tick(actor="test:on-call")

    service = MissionHubService(store, bundle)
    deployment = store.active_deployment("mission-hub")
    envelope = service.lease_envelope(machine_id="mission-hub", deployment_id=deployment["id"], actor="test")
    store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="test")
    service.record_failure(
        envelope, failure_class="repairable_output", code="output_schema_invalid",
        message="first repaired producer still emitted an unexpected log", actor="test",
    )

    after = RecoveryManager(store, bundle).get(incident["id"])
    assert after["state"] == "classified"
    assert after["attempts"][0]["state"] == "failed"
    assert after["attempts"][0]["failure_code"] == "output_schema_invalid"
    assert after["attempts"][0]["actions"][-1]["kind"] == "health_check"
    assert after["attempts"][0]["actions"][-1]["status"] == "failed"
    next_attempt = RecoveryManager(store, bundle).start_attempt(
        incident["id"], "diagnose_failed_successor", actor="test:sol-on-call",
    )
    assert next_attempt["ordinal"] == 2
    with store._connect() as db:
        assert db.execute(
            "SELECT COUNT(*) FROM recovery_incidents WHERE job_id=?", (job["id"],),
        ).fetchone()[0] == 1


def test_repaired_retry_moves_stale_placement_to_current_executor_role(tmp_path: Path):
    store, bundle, library, config_id, _ = ready(tmp_path)
    (library / "source.md").write_text("placement repair\n", encoding="utf-8")
    job, _ = fail_corpus(store, bundle)
    with store.transaction() as db:
        db.execute("UPDATE jobs SET requested_machine_id='trainbox' WHERE id=?", (job["id"],))
    incident, _ = start_repair(store, bundle, job["id"])

    RecoveryCoordinator(
        store, bundle, SuccessfulRepairDriver(store, bundle, config_id, tmp_path),
    ).tick(actor="test:on-call")

    repaired = next(item for item in store.list_rows("jobs", limit=10) if item["id"] == job["id"])
    assert repaired["status"] == "queued"
    assert repaired["requested_machine_id"] == "mission-hub"
    assert RecoveryManager(store, bundle).get(incident["id"])["state"] == "verifying"


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
