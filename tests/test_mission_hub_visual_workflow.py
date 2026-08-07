from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import hashlib
import json

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.errors import SafetyError
from mission_hub.store import MissionHubStore
from mission_hub.visual_workflow import VisualWorkflowCoordinator


REPO = Path(__file__).resolve().parents[1]


def test_visual_workflow_cannot_start_while_execution_is_locked(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    bundle.jobs["visual.generate"]["enabled"] = False
    store.activate_config(bundle, actor="test")
    with pytest.raises(SafetyError, match="complete visual workflow"):
        store.create_visual_workflow(
            bundle,
            {"campaign_id": "campaign-test", "plan": {"goal": "one object"}, "experience_events": [{"type": "page_turn"}], "limits": {}},
            actor="test",
        )


def test_visual_stage_pacing_is_anchored_to_predecessor_completion() -> None:
    coordinator = VisualWorkflowCoordinator.__new__(VisualWorkflowCoordinator)
    coordinator.bundle = SimpleNamespace(visual={"stage_cooldown_seconds": 900})
    captured = {}

    def create(workflow, key, job_type, artifact_ids, specification, available_at, actor):
        captured.update({"available_at": available_at, "key": key})
        return {"status": "queued", "stage": key}

    coordinator._create = create
    predecessor = ({}, [], "2026-08-06T01:02:03.000000Z")
    coordinator._next({"id": "visual-test"}, "generate", "visual.generate", [], predecessor, "test")
    assert captured == {"available_at": "2026-08-06T01:17:03.000000Z", "key": "generate"}


def test_exact_visual_workflow_authorizes_its_derived_stage() -> None:
    coordinator = VisualWorkflowCoordinator.__new__(VisualWorkflowCoordinator)
    coordinator.bundle = SimpleNamespace(
        jobs={"visual.review": {"executor_role": "mission_hub"}},
    )
    coordinator._place = lambda *args: None
    captured = {}

    class Store:
        def create_job(self, bundle, **kwargs):
            captured.update(kwargs)
            return {"id": "job-review", "status": "queued"}

        def link_visual_workflow_job(self, *args, **kwargs):
            return None

    coordinator.store = Store()
    result = coordinator._create(
        {"id": "visual-authorized", "campaign_id": "campaign-test", "specification": {"limits": {}}},
        "review:art-test", "visual.review", ["art-test"], {}, None, "mission-hub-daemon",
    )

    assert captured["approved"] is True
    assert result["status"] == "queued"


def test_workflow_resolves_content_deduplicated_output_from_new_run(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.base["hub"]["state_root"] = str(tmp_path / "state")
    for machine in bundle.machines.values():
        machine["state_root"] = str(tmp_path / machine["id"])
        machine["artifact_roots"] = [str(tmp_path)]
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO deployments
               (id,machine_id,role,release_id,source_sha256,environment_sha256,
                config_snapshot_id,status,manifest_json,created_at,activated_at)
               VALUES('dep-test','mission-hub','mission-hub','release-test',?,?,?,'active','{}',?,?)""",
            ("1" * 64, "2" * 64, config_id, "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z"),
        )
    jobs = [store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key=f"dedupe-{index}", created_by="test",
        requested_machine_id="mission-hub", approved=True,
    ) for index in (1, 2)]
    artifact_path = tmp_path / "mission-hub" / "same-plan.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text('{"plan":"same"}\n', encoding="utf-8")
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    declaration = {
        "kind": "visual_plan", "sha256": digest,
        "byte_size": artifact_path.stat().st_size,
    }
    for index, job in enumerate(jobs, 1):
        run_id = f"run-dedupe-{index}"
        with store.transaction() as db:
            db.execute(
                """INSERT INTO runs
                   (id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,
                    lease_expires_at,started_at,finished_at,output_json)
                   VALUES(?,?,1,'mission-hub','dep-test','succeeded',?,?,?,?,?)""",
                (run_id, job["id"], "3" * 64, "2026-08-01T01:00:00Z", "2026-08-01T00:00:00Z", "2026-08-01T00:00:01Z", json.dumps({"artifacts": [declaration]})),
            )
            db.execute("UPDATE jobs SET status='succeeded' WHERE id=?", (job["id"],))
        store.register_artifact(
            bundle, kind="visual_plan", sha256=digest,
            byte_size=artifact_path.stat().st_size, lifecycle="candidate",
            manifest={"plan": "same"}, producing_run_id=run_id,
            machine_id="mission-hub", uri=str(artifact_path), actor="test",
        )

    _, artifacts, _ = store.workflow_job_artifacts(jobs[1]["id"])
    assert [(item["kind"], item["sha256"]) for item in artifacts] == [("visual_plan", digest)]
