from __future__ import annotations

import hashlib
import json
from pathlib import Path

from mission_hub.chat_workflow import ChatCoordinator
from mission_hub.config import load_config_bundle
from mission_hub.jsonutil import canonical_json
from mission_hub.lab import LabStore
from mission_hub.store import MissionHubStore, utc_now


REPO = Path(__file__).resolve().parents[1]


def test_chat_coordinator_records_response_from_immutable_artifact(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    now = utc_now()
    checkpoint_id = "art-1234567890abcdef"
    with store.transaction() as db:
        db.execute(
            "INSERT INTO artifacts(id,kind,sha256,byte_size,lifecycle,manifest_json,created_at) VALUES(?,'checkpoint',?,1,'candidate','{}',?)",
            (checkpoint_id, "a" * 64, now),
        )
        db.execute(
            "INSERT INTO artifact_locations(artifact_id,machine_id,uri,observed_at,available) VALUES(?,'trainbox','/checkpoint.pt',?,1)",
            (checkpoint_id, now),
        )
    lab = LabStore(store, bundle)
    chat = lab.create_chat(checkpoint_id, "Test", actor="test")
    chat = lab.add_chat_message(chat["thread"]["id"], "Hello", actor="test")
    invocation = chat["invocations"][0]
    report = {
        "schema_version": "ninereeds_checkpoint_chat_v1",
        "invocation_id": invocation["id"], "response": "Hello from Ninereeds.",
    }
    report_path = tmp_path / "chat-report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    raw = report_path.read_bytes()
    run_id = "run-chat-test"
    artifact_id = "art-fedcba0987654321"
    with store.transaction() as db:
        config_id = db.execute(
            "SELECT id FROM config_snapshots ORDER BY created_at DESC LIMIT 1",
        ).fetchone()[0]
        db.execute(
            """INSERT INTO deployments
               (id,machine_id,role,release_id,source_sha256,environment_sha256,
                config_snapshot_id,status,manifest_json,created_at,activated_at)
               VALUES('dep-test','trainbox','trainbox','release-test',?,?,?,'active','{}',?,?)""",
            ("d" * 64, "e" * 64, config_id, now, now),
        )
        db.execute(
            """INSERT INTO runs
               (id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,
                lease_expires_at,started_at,heartbeat_at,finished_at)
               VALUES(?,?,1,'trainbox','dep-test','succeeded',?,?,?,?,?)""",
            (run_id, invocation["job_id"], "f" * 64, now, now, now, now),
        )
        db.execute(
            "UPDATE jobs SET status='succeeded',updated_at=? WHERE id=?",
            (now, invocation["job_id"]),
        )
        db.execute(
            "INSERT INTO artifacts(id,kind,sha256,byte_size,lifecycle,manifest_json,producing_run_id,created_at) VALUES(?,'chat_report',?,?,'candidate',?, ?,?)",
            (artifact_id, hashlib.sha256(raw).hexdigest(), len(raw), canonical_json({"invocation_id": invocation["id"]}), run_id, now),
        )
        db.execute(
            "INSERT INTO artifact_locations(artifact_id,machine_id,uri,observed_at,available) VALUES(?,'mission-hub',?,?,1)",
            (artifact_id, str(report_path), now),
        )

    assert ChatCoordinator(store, bundle).tick(actor="test") == 1
    completed = lab.chat(chat["thread"]["id"])
    assert completed["invocations"][0]["status"] == "succeeded"
    assert completed["messages"][-1]["role"] == "ninereeds"
    assert completed["messages"][-1]["body"] == "Hello from Ninereeds."
