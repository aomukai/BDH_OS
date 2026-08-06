from __future__ import annotations

import json
import sqlite3

from mission_hub.store import MissionHubStore


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
