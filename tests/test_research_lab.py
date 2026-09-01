from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from mission_hub.config import load_config_bundle
from mission_hub.jsonutil import content_hash
from mission_hub.lab import LabStore
from mission_hub.research_lab import (
    HEARTBEAT_SECONDS,
    ResearchLabCoordinator,
    commission_research_lab,
)
from mission_hub.store import MissionHubStore, utc_now


ROOT = Path(__file__).resolve().parents[1]


def ready(tmp_path: Path):
    bundle = load_config_bundle(ROOT / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    deployments = {}
    for machine_id, role in (("mission-hub", "mission_hub"), ("trainbox", "trainbox")):
        deployments[machine_id] = store.register_deployment({
            "machine_id": machine_id,
            "role": role,
            "release_id": f"test-{machine_id}",
            "source_sha256": "1" * 64,
            "environment_sha256": "2" * 64,
            "config_snapshot_id": config_id,
        }, actor="test", activate=True)
    return store, bundle, deployments


def controls() -> dict:
    return {
        "seed": 3_603_602,
        "learning_rate": 2e-4,
        "cell_learning_rate": 3e-3,
        "weight_decay": 0.0,
        "seed_ingress_cells": 8,
        "cell_rotary_pairs": 2,
        "initial_route_energy": 64.0,
        "branch_energy_floor": 0.10,
        "max_waves": 32,
        "max_total_activations": 256,
        "max_degree": 16,
        "max_fanout": 4,
        "minimum_observations": 6,
        "minimum_independent_lineages": 6,
        "minimum_source_families": 2,
        "minimum_residual_coherence": 0.80,
        "shadow_training_steps": 64,
        "shadow_learning_rate": 0.03,
    }


def decision(kind: str) -> dict:
    launch = kind == "launch_experiment"
    conclude = kind == "conclude_campaign"
    return {
        "status": "succeeded",
        "action": {
            "kind": kind,
            "experiment_title": "Complete-organ baseline" if launch else None,
            "hypothesis": "A short baseline establishes observable dynamics." if launch else None,
            "max_sessions": 1 if launch else None,
            "max_events_per_session": 10 if launch else None,
            "controls": controls() if launch else None,
            "campaign_report": "The campaign resolved its question." if conclude else None,
            "next_campaign_title": "Next mechanism" if conclude else None,
            "next_campaign_goal": "Isolate the next Mycelium mechanism." if conclude else None,
        },
        "message": {
            "launch_experiment": "I am launching the complete-organ baseline now.",
            "wait": "The baseline is still running, so I am leaving it alone and going back to sleep.",
            "inspect_state": "State is indeterminate; I will inspect again without launching duplicate work.",
            "conclude_campaign": "I am concluding this campaign and opening the next one.",
        }[kind],
        "rationale": "This is the only action permitted by authoritative state.",
        "updated_todo": {
            "focus": "Learn the baseline dynamics.",
            "current_hypothesis": "The baseline is measurable.",
            "next_questions": ["What changed?"],
            "constraints": ["Knowledge, not improvement."],
        },
        "artifacts": [],
    }


def succeed_job(
    store: MissionHubStore, deployments: dict[str, str], job_id: str, output: dict,
) -> str:
    with store.transaction() as db:
        job = db.execute(
            "SELECT requested_machine_id FROM jobs WHERE id=?", (job_id,),
        ).fetchone()
        machine_id = job["requested_machine_id"]
        run_id = f"run-{uuid.uuid4()}"
        now = utc_now()
        db.execute("UPDATE jobs SET status='succeeded',updated_at=? WHERE id=?", (now, job_id))
        db.execute(
            """INSERT INTO runs
               (id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,
                lease_expires_at,started_at,heartbeat_at,finished_at,output_json,output_sha256)
               VALUES(?,?,1,?,?,'succeeded',?,?,?,?,?,?,?)""",
            (
                run_id, job_id, machine_id, deployments[machine_id], "0" * 64,
                "2099-01-01T00:00:00Z", now, now, now,
                json.dumps(output, sort_keys=True), content_hash(output),
            ),
        )
    return run_id


def commission(store: MissionHubStore, bundle) -> dict:
    return commission_research_lab(
        store, bundle, campaign_number=36, title="Mycelium laboratory",
        goal="Map complete-organ learning and Mycelium control dynamics.", actor="test",
    )


def test_commission_creates_one_ordinary_numbered_campaign_and_twenty_minute_thread(
    tmp_path: Path,
) -> None:
    store, bundle, _ = ready(tmp_path)
    created = commission(store, bundle)

    with store._connect() as db:
        campaign = db.execute(
            "SELECT name,state,metadata_json FROM campaigns WHERE id=?", (created["campaign_id"],),
        ).fetchone()
        lab = db.execute("SELECT * FROM research_labs WHERE id=?", (created["id"],)).fetchone()
    thread = LabStore(store).thread(created["thread_id"], mark_read=False)

    assert campaign["name"] == "Campaign 36 — Mycelium laboratory"
    assert campaign["state"] == "active"
    assert json.loads(campaign["metadata_json"])["authority"]["improvement_is_not_required"] is True
    assert lab["campaign_number"] == 36
    assert lab["heartbeat_seconds"] == HEARTBEAT_SECONDS == 1200
    assert thread["messages"][0]["sender"] == "sol"
    assert "wake every 20 minutes" in thread["messages"][0]["body"]


def test_running_experiment_forces_wait_without_duplicate_launch(tmp_path: Path) -> None:
    store, bundle, deployments = ready(tmp_path)
    created = commission(store, bundle)
    coordinator = ResearchLabCoordinator(store, bundle)

    first = coordinator.tick(actor="test:sol")
    assert first[0]["allowed_actions"] == ["launch_experiment", "conclude_campaign"]
    with store._connect() as db:
        decision_job_id = db.execute(
            "SELECT decision_job_id FROM research_activations WHERE sequence=1"
        ).fetchone()[0]
    succeed_job(store, deployments, decision_job_id, decision("launch_experiment"))
    launched = coordinator.tick(actor="test:sol")
    assert launched[0]["action"] == "launch_experiment"

    with store.transaction() as db:
        db.execute(
            "UPDATE research_labs SET next_activation_at='2000-01-01T00:00:00Z' WHERE id=?",
            (created["id"],),
        )
    running = coordinator.tick(actor="test:sol")
    assert running[0]["allowed_actions"] == ["wait"]
    with store._connect() as db:
        rows = db.execute(
            "SELECT job_type,input_json FROM jobs ORDER BY created_at"
        ).fetchall()
        second_decision = db.execute(
            "SELECT decision_job_id FROM research_activations WHERE sequence=2"
        ).fetchone()[0]
    assert sum(row["job_type"] == "model.organism_bootstrap" for row in rows) == 1
    launch_payload = json.loads(next(
        row["input_json"] for row in rows if row["job_type"] == "model.organism_bootstrap"
    ))
    assert launch_payload["experiment_id"] == "experiment-36-1"
    assert launch_payload["max_events_per_session"] == 10

    succeed_job(store, deployments, second_decision, decision("wait"))
    waited = coordinator.tick(actor="test:sol")
    assert waited[0]["action"] == "wait"
    thread = LabStore(store).thread(created["thread_id"], mark_read=False)
    assert "still running" in thread["messages"][-1]["body"]
    with store._connect() as db:
        lab = db.execute("SELECT next_activation_at FROM research_labs WHERE id=?", (created["id"],)).fetchone()
    due = datetime.fromisoformat(lab["next_activation_at"].replace("Z", "+00:00"))
    assert 1190 <= (due - datetime.now(timezone.utc)).total_seconds() <= 1200


def test_idle_activation_cannot_apply_a_wait_decision(tmp_path: Path) -> None:
    store, bundle, deployments = ready(tmp_path)
    created = commission(store, bundle)
    coordinator = ResearchLabCoordinator(store, bundle)
    coordinator.tick(actor="test:sol")
    with store._connect() as db:
        job_id = db.execute("SELECT decision_job_id FROM research_activations").fetchone()[0]
    succeed_job(store, deployments, job_id, decision("wait"))

    result = coordinator.tick(actor="test:sol")

    assert result[0]["status"] == "failed"
    with store._connect() as db:
        activation = db.execute("SELECT status FROM research_activations").fetchone()
        launches = db.execute(
            "SELECT COUNT(*) FROM jobs WHERE job_type='model.organism_bootstrap'"
        ).fetchone()[0]
    assert activation["status"] == "failed"
    assert launches == 0
    thread = LabStore(store).thread(created["thread_id"], mark_read=False)
    assert "state-contract error" in thread["messages"][-1]["body"]
