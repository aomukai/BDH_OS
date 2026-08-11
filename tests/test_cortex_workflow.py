from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.configured_campaign import ConfiguredCortexCampaign
from mission_hub.cortex_workflow import CortexWorkflowCoordinator
from mission_hub.errors import SafetyError
from mission_hub.jsonutil import canonical_json
from mission_hub.store import MissionHubStore


REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "config/mission_hub/campaigns/campaign33-play-recovery-v1.json"


def test_retired_checkpoint_replay_requires_completed_evaluation_and_successor() -> None:
    jobs = {
        "s00:evaluate": {"status": "succeeded"},
        "s01:train": {"status": "succeeded"},
    }
    assert CortexWorkflowCoordinator._retired_checkpoint_replay_allowed(jobs, 0)
    jobs["s01:train"]["status"] = "running"
    assert not CortexWorkflowCoordinator._retired_checkpoint_replay_allowed(jobs, 0)
    jobs["s01:train"]["status"] = "succeeded"
    jobs["s00:evaluate"]["status"] = "failed"
    assert not CortexWorkflowCoordinator._retired_checkpoint_replay_allowed(jobs, 0)


def test_workflow_artifact_replay_can_read_retired_ledger_evidence(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    snapshot_id = store.activate_config(bundle, actor="test")
    deployment_id = store.register_deployment({
        "machine_id": "trainbox", "role": "trainbox", "release_id": "release-test",
        "source_sha256": "1" * 64, "environment_sha256": "2" * 64,
        "config_snapshot_id": snapshot_id,
    }, actor="test", activate=True)
    job = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="retired-ledger-evidence", created_by="test",
        requested_machine_id="trainbox", approved=True,
    )
    digest = "a" * 64
    output = canonical_json({
        "artifacts": [{"kind": "checkpoint", "sha256": digest, "byte_size": 7}],
    })
    with store.transaction() as db:
        db.execute("UPDATE jobs SET status='succeeded' WHERE id=?", (job["id"],))
        db.execute(
            """INSERT INTO runs
               (id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,
                lease_expires_at,started_at,heartbeat_at,finished_at,
                output_json,output_sha256)
               VALUES('run-retired',?,1,'trainbox',?,'succeeded',?,'now','now','now','now',?,?)""",
            (job["id"], deployment_id, "c" * 64, output, "b" * 64),
        )
        db.execute(
            """INSERT INTO artifacts
               (id,kind,producing_run_id,sha256,byte_size,lifecycle,manifest_json,created_at)
               VALUES('artifact-retired','checkpoint','run-retired',?,7,'deleted','{}','now')""",
            (digest,),
        )
    with pytest.raises(SafetyError, match="unavailable output artifact"):
        store.workflow_job_artifacts(job["id"])
    _, artifacts, _ = store.workflow_job_artifacts(
        job["id"], allow_retired_declarations=True,
    )
    assert [(item["id"], item["lifecycle"]) for item in artifacts] == [
        ("artifact-retired", "deleted"),
    ]
    assert snapshot_id


def test_operator_can_reopen_retention_block_with_available_frontier(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    snapshot_id = store.activate_config(bundle, actor="test")
    deployment_id = store.register_deployment({
        "machine_id": "trainbox", "role": "trainbox", "release_id": "release-test",
        "source_sha256": "1" * 64, "environment_sha256": "2" * 64,
        "config_snapshot_id": snapshot_id,
    }, actor="test", activate=True)
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES('campaign-retention','Retention','active',?,'test','{}','now','now')""",
            (snapshot_id,),
        )
        db.execute(
            """INSERT INTO cortex_workflows
               (id,campaign_id,status,specification_json,config_snapshot_id,
                authorized_by,created_at,updated_at)
               VALUES('workflow-retention','campaign-retention','blocked',?,?,'test','old','old')""",
            (canonical_json({
                "branch_id": "branch-retention",
                "sessions": [{"id": "one"}, {"id": "two"}],
            }), snapshot_id),
        )
    stage_jobs = {}
    for stage in ("s00:train", "s00:evaluate", "s01:train"):
        job = store.create_job(
            bundle, job_type="system.healthcheck", input_payload={},
            idempotency_key=f"retention-{stage}", created_by="test",
            campaign_id="campaign-retention", requested_machine_id="trainbox", approved=True,
        )
        stage_jobs[stage] = job["id"]
        with store.transaction() as db:
            db.execute("UPDATE jobs SET status='succeeded' WHERE id=?", (job["id"],))
            db.execute(
                "INSERT INTO cortex_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES('workflow-retention',?,?,?)",
                (stage, job["id"], stage),
            )
    with store.transaction() as db:
        for index, stage in enumerate(("s00:train", "s01:train")):
            digest = str(index + 1) * 64
            run_id = f"run-retention-{index}"
            artifact_id = f"artifact-retention-{index}"
            output = canonical_json({
                "artifacts": [{"kind": "checkpoint", "sha256": digest, "byte_size": 7}],
            })
            db.execute(
                """INSERT INTO runs
                   (id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,
                    lease_expires_at,started_at,heartbeat_at,finished_at,
                    output_json,output_sha256)
                   VALUES(?,?,1,'trainbox',?,'succeeded',?,'now','now','now','now',?,?)""",
                (run_id, stage_jobs[stage], deployment_id, "e" * 64, output, "f" * 64),
            )
            db.execute(
                """INSERT INTO artifacts
                   (id,kind,producing_run_id,sha256,byte_size,lifecycle,manifest_json,created_at)
                   VALUES(?,'checkpoint',?,?,7,?,'{}','now')""",
                (artifact_id, run_id, digest, "deleted" if index == 0 else "candidate"),
            )
            if index == 1:
                db.execute(
                    """INSERT INTO artifact_locations
                       (artifact_id,machine_id,uri,observed_at,available)
                       VALUES(?,'trainbox','/runtime/frontier.pt','now',1)""",
                    (artifact_id,),
                )
        store._event(
            db, "cortex_workflow", "workflow-retention", "cortex_workflow.blocked", "daemon",
            {"reason": "SafetyError: successful run declares an unavailable output artifact"},
        )

    reopened = store.reopen_cortex_workflow_after_retention_repair(
        "workflow-retention", actor="operator",
        reason="Retired intermediates are now replayed only behind a completed successor.",
    )
    assert reopened["status"] == "active"
    event = next(
        row for row in store.list_rows("events", limit=100)
        if row["event_type"] == "cortex_workflow.reopened_after_retention_repair"
    )
    evidence = json.loads(event["payload_json"])
    assert evidence["retired_checkpoint_count"] == 1
    assert evidence["frontier_checkpoint_artifact_id"] == "artifact-retention-1"


def test_successful_workflow_completion_pauses_for_operator(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    snapshot_id = store.activate_config(bundle, actor="test")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES('campaign','Campaign','active',?,'Complete one branch.','{}','now','now')""",
            (snapshot_id,),
        )
        db.execute(
            """INSERT INTO cortex_workflows
               (id,campaign_id,status,specification_json,config_snapshot_id,authorized_by,created_at,updated_at)
               VALUES('workflow','campaign','active',? ,?,'test','now','now')""",
            (canonical_json({"branch_id": "branch", "sessions": []}), snapshot_id),
        )
    store.request_pipeline_state("running", actor="operator")
    store.apply_pipeline_state(actor="daemon")

    store.finish_cortex_workflow(
        "workflow", "succeeded", actor="daemon", pause_pipeline=True,
    )

    control = store.pipeline_control()
    assert control["desired_state"] == "paused"
    assert control["effective_state"] == "paused"
    events = store.list_rows("events")
    pause = next(item for item in events if item["event_type"] == "pipeline.paused_requested")
    assert json.loads(pause["payload_json"])["workflow_id"] == "workflow"


def test_only_final_workflow_checkpoint_can_complete_an_evolutionary_branch() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE artifacts(id TEXT PRIMARY KEY,kind TEXT,producing_run_id TEXT);
        CREATE TABLE runs(id TEXT PRIMARY KEY,job_id TEXT,status TEXT);
        CREATE TABLE cortex_workflows(id TEXT PRIMARY KEY,status TEXT,specification_json TEXT);
        CREATE TABLE cortex_workflow_jobs(workflow_id TEXT,stage_key TEXT,job_id TEXT);
        CREATE TABLE jobs(id TEXT PRIMARY KEY,status TEXT);
        """
    )
    specification = json.dumps({
        "branch_id": "branch-3",
        "sessions": [{"id": "one"}, {"id": "two"}],
    })
    db.execute("INSERT INTO cortex_workflows VALUES('workflow','active',?)", (specification,))
    for index in range(2):
        job_id = f"train-{index}"
        run_id = f"run-{index}"
        artifact_id = f"candidate-{index}"
        db.execute("INSERT INTO jobs VALUES(?,'succeeded')", (job_id,))
        db.execute("INSERT INTO runs VALUES(?,?,'succeeded')", (run_id, job_id))
        db.execute("INSERT INTO artifacts VALUES(?,'checkpoint',?)", (artifact_id, run_id))
        db.execute(
            "INSERT INTO cortex_workflow_jobs VALUES('workflow',?,?)",
            (f"s{index:02d}:train", job_id),
        )

    assert not MissionHubStore._candidate_completes_cortex_branch(
        db, "candidate-0", "branch-3",
    )
    assert not MissionHubStore._candidate_completes_cortex_branch(
        db, "candidate-1", "branch-3",
    )

    db.execute("INSERT INTO jobs VALUES('eval-0','succeeded')")
    db.execute(
        "INSERT INTO cortex_workflow_jobs VALUES('workflow','s00:evaluate','eval-0')"
    )
    assert MissionHubStore._candidate_completes_cortex_branch(
        db, "candidate-1", "branch-3",
    )
    assert not MissionHubStore._candidate_completes_cortex_branch(
        db, "candidate-1", "branch-4",
    )


def test_failed_predecessor_evaluation_cannot_complete_branch() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE artifacts(id TEXT PRIMARY KEY,kind TEXT,producing_run_id TEXT);
        CREATE TABLE runs(id TEXT PRIMARY KEY,job_id TEXT,status TEXT);
        CREATE TABLE cortex_workflows(id TEXT PRIMARY KEY,status TEXT,specification_json TEXT);
        CREATE TABLE cortex_workflow_jobs(workflow_id TEXT,stage_key TEXT,job_id TEXT);
        CREATE TABLE jobs(id TEXT PRIMARY KEY,status TEXT);
        INSERT INTO cortex_workflows VALUES(
          'workflow','active','{"branch_id":"branch-3","sessions":[{"id":"one"},{"id":"two"}]}'
        );
        INSERT INTO jobs VALUES('train-1','succeeded');
        INSERT INTO jobs VALUES('eval-0','failed');
        INSERT INTO runs VALUES('run-1','train-1','succeeded');
        INSERT INTO artifacts VALUES('candidate-1','checkpoint','run-1');
        INSERT INTO cortex_workflow_jobs VALUES('workflow','s01:train','train-1');
        INSERT INTO cortex_workflow_jobs VALUES('workflow','s00:evaluate','eval-0');
        """
    )
    assert not MissionHubStore._candidate_completes_cortex_branch(
        db, "candidate-1", "branch-3",
    )


def test_operator_can_retry_exact_failed_transport_stage_without_regeneration(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config/mission_hub")
    state = tmp_path / "state"
    bundle.machines["mission-hub"]["state_root"] = str(state)
    bundle.machines["mission-hub"]["artifact_roots"] = [str(state), str(REPO)]
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    snapshot_id = store.activate_config(bundle, actor="test")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO artifacts
               (id,kind,sha256,byte_size,lifecycle,manifest_json,created_at)
               VALUES('art-ba5e1e0000000000','checkpoint',?,7265464584,'candidate',?,'now')""",
            (
                "76c1ba33c935a61557caf39a4886669f4833458671d4e909dc40adb96b2b81a9",
                canonical_json({"certification_scope": "byte_identity_only"}),
            ),
        )
    configured = ConfiguredCortexCampaign(
        store, bundle, repo_root=REPO, specification_path=SPEC,
    )
    branch = "play-word-evolution-0501-2000-v1-play-003"
    workflow = configured.reconcile(actor="test", authorize_branches=[branch])["workflows"][0]
    deployment_id = store.register_deployment({
        "machine_id": "trainbox", "role": "trainbox", "release_id": "release-test",
        "source_sha256": "1" * 64, "environment_sha256": "2" * 64,
        "config_snapshot_id": snapshot_id,
    }, actor="test", activate=True)
    failure = {
        "class": "deterministic_specification", "code": "unexpected_internal_error",
        "message": "TimeoutExpired: Command '['ssh', '--', 'ninereeds-trainbox-agent', 'execute']' timed out after 60 seconds",
    }
    with store.transaction() as db:
        db.execute(
            """INSERT INTO jobs
               (id,idempotency_key,job_type,job_version,status,config_snapshot_id,campaign_id,
                requested_machine_id,input_json,input_sha256,priority,approval_policy,approved_by,
                approved_at,created_by,created_at,updated_at)
               VALUES('job-retry','retry-test','model.train',2,'failed',?,?,
                      'trainbox','{}',?,70,'operator','test','now','test','now','now')""",
            (snapshot_id, workflow["campaign_id"], "3" * 64),
        )
        db.execute(
            """INSERT INTO runs
               (id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,
                lease_expires_at,started_at,heartbeat_at,finished_at,failure_class,failure_code,failure_json)
               VALUES('run-retry','job-retry',1,'trainbox',?,'failed',?,'then','then','then','then',
                      'deterministic_specification','unexpected_internal_error',?)""",
            (deployment_id, "4" * 64, canonical_json(failure)),
        )
        db.execute(
            "INSERT INTO cortex_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES(?, 's00:train','job-retry','now')",
            (workflow["id"],),
        )
        db.execute("UPDATE cortex_workflows SET status='failed' WHERE id=?", (workflow["id"],))

    recovered = store.retry_failed_cortex_stage(
        bundle, workflow["id"], reason="Reviewed the 60-second transport timeout; remote process is stopped.", actor="operator",
    )

    assert recovered["status"] == "active"
    assert recovered["reauthorized_config_snapshot_id"] == snapshot_id
    assert recovered["jobs"][0]["id"] == "job-retry"
    assert recovered["jobs"][0]["status"] == "queued"


def test_untouched_cortex_frontier_can_be_audited_into_active_config(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config/mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES('campaign-frontier','Frontier','active',?,'test','{}','now','now')""",
            (config_id,),
        )
        db.execute(
            """INSERT INTO config_snapshots(id,sha256,state,payload_json,created_at,actor)
               SELECT 'cfg-old-frontier',printf('%064d',9),'superseded',payload_json,created_at,'test'
               FROM config_snapshots WHERE id=?""",
            (config_id,),
        )
        db.execute(
            """INSERT INTO cortex_workflows
               (id,campaign_id,status,specification_json,config_snapshot_id,authorized_by,created_at,updated_at)
               VALUES('cortex-frontier','campaign-frontier','active','{}','cfg-old-frontier','test','now','now')""",
        )
    job = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="cortex-frontier-job", created_by="test",
        campaign_id="campaign-frontier", requested_machine_id="trainbox", approved=True,
    )
    with store.transaction() as db:
        db.execute("UPDATE jobs SET config_snapshot_id='cfg-old-frontier' WHERE id=?", (job["id"],))
        db.execute(
            "INSERT INTO cortex_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES('cortex-frontier','s01:train',?,'now')",
            (job["id"],),
        )

    result = store.reauthorize_queued_cortex_stages(
        bundle, campaign_id="campaign-frontier",
        reason="Scheduler-only configuration repair at an idle frontier.", actor="operator",
    )

    assert result["reauthorized_job_ids"] == [job["id"]]
    workflow = store.cortex_workflow("cortex-frontier")
    assert workflow["reauthorized_config_snapshot_id"] == config_id
    assert workflow["jobs"][0]["config_snapshot_id"] == config_id
    events = {row["event_type"] for row in store.list_rows("events", limit=100)}
    assert "cortex_workflow.queued_frontier_reauthorized" in events


def test_queue_expired_untouched_cortex_frontier_can_resume_exact_job(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES('campaign-expired','Expired','active',?,'test','{}','now','now')""",
            (config_id,),
        )
        db.execute(
            """INSERT INTO cortex_workflows
               (id,campaign_id,status,specification_json,config_snapshot_id,authorized_by,created_at,updated_at)
               VALUES('cortex-expired','campaign-expired','failed','{}',?,'test','old','old')""",
            (config_id,),
        )
    predecessor = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="cortex-expired-predecessor", created_by="test",
        campaign_id="campaign-expired", requested_machine_id="trainbox", approved=True,
    )
    frontier = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="cortex-expired-frontier", created_by="test",
        campaign_id="campaign-expired", requested_machine_id="trainbox", approved=True,
    )
    original_hash = frontier["input_sha256"]
    with store.transaction() as db:
        db.execute("UPDATE jobs SET status='succeeded' WHERE id=?", (predecessor["id"],))
        db.execute(
            "UPDATE jobs SET status='blocked',created_at='2000-01-01T00:00:00Z',updated_at='2000-01-01T00:00:00Z' WHERE id=?",
            (frontier["id"],),
        )
        db.execute(
            "INSERT INTO cortex_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES('cortex-expired','s00:train',?,'old')",
            (predecessor["id"],),
        )
        db.execute(
            "INSERT INTO cortex_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES('cortex-expired','s00:evaluate',?,'now')",
            (frontier["id"],),
        )
        store._event(db, "job", frontier["id"], "job.queue_age_exceeded", "daemon", {})
        store._event(
            db, "cortex_workflow", "cortex-expired", "cortex_workflow.failed", "daemon",
            {"reason": "s00:evaluate:blocked"},
        )

    recovered = store.recover_queue_expired_cortex_stage(
        bundle, frontier["id"], reason="Untouched evaluation expired after a config change.", actor="on-call",
    )

    assert recovered["status"] == "active"
    resumed = next(job for job in recovered["jobs"] if job["id"] == frontier["id"])
    assert resumed["status"] == "queued"
    assert resumed["config_snapshot_id"] == config_id
    assert resumed["input_sha256"] == original_hash
    with store._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM runs WHERE job_id=?", (frontier["id"],)).fetchone()[0] == 0
    events = {row["event_type"] for row in store.list_rows("events", limit=100)}
    assert "job.requeued_after_queue_age_recovery" in events
    assert "cortex_workflow.reopened_after_queue_age_recovery" in events


def test_operator_can_cleanly_restart_exact_workflow_after_contract_implementation_fault(
    tmp_path: Path,
) -> None:
    bundle = load_config_bundle(REPO / "config/mission_hub")
    state = tmp_path / "state"
    bundle.machines["mission-hub"]["state_root"] = str(state)
    bundle.machines["mission-hub"]["artifact_roots"] = [str(state), str(REPO)]
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    snapshot_id = store.activate_config(bundle, actor="test")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO artifacts
               (id,kind,sha256,byte_size,lifecycle,manifest_json,created_at)
               VALUES('art-ba5e1e0000000000','checkpoint',?,7265464584,'candidate',?,'now')""",
            (
                "76c1ba33c935a61557caf39a4886669f4833458671d4e909dc40adb96b2b81a9",
                canonical_json({"certification_scope": "byte_identity_only"}),
            ),
        )
    configured = ConfiguredCortexCampaign(
        store, bundle, repo_root=REPO, specification_path=SPEC,
    )
    branch = "play-word-evolution-0501-2000-v1-play-003"
    workflow = configured.reconcile(actor="test", authorize_branches=[branch])["workflows"][0]
    failed_deployment_id = store.register_deployment({
        "machine_id": "trainbox", "role": "trainbox", "release_id": "release-broken",
        "source_sha256": "1" * 64, "environment_sha256": "2" * 64,
        "config_snapshot_id": snapshot_id,
    }, actor="test", activate=True)
    failure = {
        "class": "deterministic_specification", "code": "unexpected_internal_error",
        "message": "Cortex training report does not match the commissioned session contract",
    }
    with store.transaction() as db:
        db.execute(
            """INSERT INTO jobs
               (id,idempotency_key,job_type,job_version,status,config_snapshot_id,campaign_id,
                requested_machine_id,input_json,input_sha256,priority,approval_policy,approved_by,
                approved_at,created_by,created_at,updated_at)
               VALUES('job-contract-fault','contract-fault','model.train',2,'failed',?,?
                      ,'trainbox','{}',?,70,'operator','test','now','test','now','now')""",
            (snapshot_id, workflow["campaign_id"], "3" * 64),
        )
        db.execute(
            """INSERT INTO runs
               (id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,
                lease_expires_at,started_at,heartbeat_at,finished_at,failure_class,failure_code,failure_json)
               VALUES('run-contract-fault','job-contract-fault',2,'trainbox',?,'failed',?
                      ,'then','then','then','then','deterministic_specification',
                       'unexpected_internal_error',?)""",
            (failed_deployment_id, "4" * 64, canonical_json(failure)),
        )
        db.execute(
            "INSERT INTO cortex_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES(?,'s00:train','job-contract-fault','now')",
            (workflow["id"],),
        )
        db.execute(
            """INSERT INTO training_session_plans
               (id,campaign_id,session_id,job_id,parent_checkpoint_artifact_id,
                subject_artifact_id,validation_artifact_id,ordered_concepts_json,
                parent_knowledge_sha256,plan_sha256,status,created_at)
               VALUES('session-plan-contract-fault',?,?,'job-contract-fault',
                      'art-ba5e1e0000000000','art-ba5e1e0000000000',
                      'art-ba5e1e0000000000','[]',?,?, 'admitted','now')""",
            (
                workflow["campaign_id"], workflow["specification"]["sessions"][0]["id"],
                "6" * 64, "7" * 64,
            ),
        )
        db.execute("UPDATE cortex_workflows SET status='failed' WHERE id=?", (workflow["id"],))
    replacement_deployment_id = store.register_deployment({
        "machine_id": "trainbox", "role": "trainbox", "release_id": "release-fixed",
        "source_sha256": "5" * 64, "environment_sha256": "2" * 64,
        "config_snapshot_id": snapshot_id,
    }, actor="test", activate=True)

    restarted = store.restart_failed_cortex_workflow(
        bundle, workflow["id"],
        reason="The structured train-scope report contract is fixed and tested.",
        actor="operator",
    )

    assert restarted["id"] != workflow["id"]
    assert restarted["status"] == "active"
    assert restarted["specification"] == workflow["specification"]
    assert len(restarted["jobs"]) == 1
    assert restarted["jobs"][0]["stage_key"] == "s00:train"
    assert restarted["jobs"][0]["status"] == "queued"
    with store._connect() as db:
        rebound = db.execute(
            "SELECT job_id,status FROM training_session_plans WHERE id='session-plan-contract-fault'",
        ).fetchone()
    assert rebound["job_id"] == restarted["jobs"][0]["id"]
    assert rebound["status"] == "admitted"
    assert store.cortex_workflow(workflow["id"])["status"] == "failed"
    assert store.active_deployment("trainbox")["id"] == replacement_deployment_id
    assert store.create_cortex_workflow(
        bundle, workflow["specification"], actor="operator",
    )["id"] == restarted["id"]
