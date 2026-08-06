from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from mission_hub.config import load_config_bundle
from mission_hub.configured_campaign import ConfiguredCortexCampaign
from mission_hub.jsonutil import canonical_json
from mission_hub.store import MissionHubStore


REPO = Path(__file__).resolve().parents[1]
SPEC = REPO / "config/mission_hub/campaigns/campaign33-play-recovery-v1.json"


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
    assert recovered["jobs"][0]["id"] == "job-retry"
    assert recovered["jobs"][0]["status"] == "queued"
