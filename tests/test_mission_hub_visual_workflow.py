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
        machines={"control-test": {"enabled": True, "role": "mission_hub"}},
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


def test_visual_workflow_selects_usable_alternatives_in_declared_order() -> None:
    workflow = {
        "specification": {
            "plan": {
                "items": [
                    {"item_id": "dog", "seeds": [3501, 3502]},
                    {"item_id": "cat", "seeds": [3503]},
                ],
            },
            "limits": {"max_pack_items": 1},
        },
    }
    candidates = [
        {"id": "candidate-cat", "sha256": "c" * 64, "manifest": {"item_id": "cat", "seed": 3503}},
        {"id": "candidate-dog-2", "sha256": "b" * 64, "manifest": {"item_id": "dog", "seed": 3502}},
        {"id": "candidate-dog-1", "sha256": "a" * 64, "manifest": {"item_id": "dog", "seed": 3501}},
    ]
    reviews = [
        {"id": "review-cat", "manifest": {"asset_sha256": "c" * 64, "asset_status": "usable"}},
        {"id": "review-dog-2", "manifest": {"asset_sha256": "b" * 64, "asset_status": "usable"}},
        {"id": "review-dog-1", "manifest": {"asset_sha256": "a" * 64, "asset_status": "unusable"}},
    ]

    selected_candidates, selected_reviews = VisualWorkflowCoordinator._selected_usable_candidates(
        workflow, candidates, reviews,
    )

    assert [item["id"] for item in selected_candidates] == ["candidate-dog-2"]
    assert [item["id"] for item in selected_reviews] == ["review-dog-2"]


def test_visual_workflow_allows_no_selection_when_every_alternative_is_rejected() -> None:
    workflow = {
        "specification": {
            "plan": {"items": [{"item_id": "dog", "seeds": [3501]}]},
            "limits": {"max_pack_items": 1},
        },
    }
    candidates = [
        {"id": "candidate", "sha256": "a" * 64, "manifest": {"item_id": "dog", "seed": 3501}},
    ]
    reviews = [
        {"id": "review", "manifest": {"asset_sha256": "a" * 64, "asset_status": "unusable"}},
    ]

    assert VisualWorkflowCoordinator._selected_usable_candidates(workflow, candidates, reviews) == ([], [])


def test_visual_workflow_selects_from_one_batch_review_without_repeating_artifact() -> None:
    workflow = {
        "specification": {
            "plan": {"items": [{"item_id": "dog", "seeds": [3501, 3502]}]},
            "limits": {"max_pack_items": 2},
        },
    }
    candidates = [
        {"id": "candidate-1", "sha256": "a" * 64, "manifest": {"item_id": "dog", "seed": 3501}},
        {"id": "candidate-2", "sha256": "b" * 64, "manifest": {"item_id": "dog", "seed": 3502}},
    ]
    review = {
        "id": "review-batch", "manifest": {
            "reviewer": "sol", "items": [
                {"asset_sha256": "a" * 64, "result": {"asset_sha256": "a" * 64, "asset_status": "usable"}},
                {"asset_sha256": "b" * 64, "result": {"asset_sha256": "b" * 64, "asset_status": "usable"}},
            ],
        },
    }

    selected_candidates, selected_reviews = VisualWorkflowCoordinator._selected_usable_candidates(
        workflow, candidates, [review],
    )

    assert [item["id"] for item in selected_candidates] == ["candidate-1", "candidate-2"]
    assert [item["id"] for item in selected_reviews] == ["review-batch"]


def test_failed_visual_workflow_can_reconcile_only_preserved_successful_jobs_while_paused(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    job = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="visual-reconcile-job", created_by="test",
        requested_machine_id="mission-hub", approved=True,
    )
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES('campaign-visual','Visual','active',?,'test','{}','now','now')""",
            (config_id,),
        )
        db.execute(
            """INSERT INTO visual_workflows
               (id,campaign_id,status,specification_json,config_snapshot_id,created_by,created_at,updated_at)
               VALUES('visual-failed','campaign-visual','failed','{}',?,'test','now','now')""",
            (config_id,),
        )
        db.execute("UPDATE jobs SET status='succeeded' WHERE id=?", (job["id"],))
        db.execute(
            "INSERT INTO visual_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES('visual-failed','plan',?,'now')",
            (job["id"],),
        )

    reopened = store.reopen_visual_workflow_after_coordinator_repair(
        "visual-failed", actor="test", reason="selection semantics repaired",
    )

    assert reopened["status"] == "active"
    event = next(
        item for item in store.list_rows("events")
        if item["event_type"] == "visual_workflow.reopened_after_coordinator_repair"
    )
    assert json.loads(event["payload_json"])["preserved_job_count"] == 1


def test_never_run_exact_visual_plan_can_be_audited_into_active_config(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES('campaign-visual-reauth','Visual','active',?,'test','{}','now','now')""",
            (config_id,),
        )
        db.execute(
            """INSERT INTO config_snapshots(id,sha256,state,payload_json,created_at,actor)
               SELECT 'cfg-old-visual',printf('%064d',8),'superseded',payload_json,created_at,'test'
               FROM config_snapshots WHERE id=?""",
            (config_id,),
        )
    payload = {"input_artifact_ids": [], "specification": {"fixed": True}, "limits": {}}
    job = store.create_job(
        bundle, job_type="visual.plan_exact", input_payload=payload,
        idempotency_key="visual-reauth-plan", created_by="test",
        campaign_id="campaign-visual-reauth", requested_machine_id="mission-hub", approved=True,
    )
    specification = {
        "campaign_id": "campaign-visual-reauth",
        "plan": {"authority": {"exact_material": True}},
    }
    with store.transaction() as db:
        db.execute(
            """INSERT INTO visual_workflows
               (id,campaign_id,status,specification_json,config_snapshot_id,created_by,created_at,updated_at)
               VALUES('visual-reauth','campaign-visual-reauth','active',?,'cfg-old-visual','test','now','now')""",
            (json.dumps(specification),),
        )
        db.execute(
            "UPDATE jobs SET config_snapshot_id='cfg-old-visual' WHERE id=?", (job["id"],),
        )
        db.execute(
            "INSERT INTO visual_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES('visual-reauth','plan',?,'now')",
            (job["id"],),
        )

    result = store.reauthorize_queued_visual_workflows(
        bundle, campaign_id="campaign-visual-reauth",
        reason="The active config changes only the repaired text completion bound.", actor="operator",
    )

    assert result["reauthorized_workflow_ids"] == ["visual-reauth"]
    workflow = store.visual_workflow("visual-reauth")
    assert workflow["config_snapshot_id"] == config_id
    assert workflow["jobs"][0]["config_snapshot_id"] == config_id
    events = {row["event_type"] for row in store.list_rows("events", limit=100)}
    assert "job.config_reauthorized_before_first_run" in events
    assert "visual_workflow.config_reauthorized_before_first_run" in events


def test_verified_repaired_visual_frontier_can_follow_active_config(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES('campaign-visual-repair','Visual','active',?,'test','{}','now','now')""",
            (config_id,),
        )
        db.execute(
            """INSERT INTO config_snapshots(id,sha256,state,payload_json,created_at,actor)
               SELECT 'cfg-old-repair',printf('%064d',7),'superseded',payload_json,created_at,'test'
               FROM config_snapshots WHERE id=?""",
            (config_id,),
        )
    payload = {"input_artifact_ids": [], "specification": {"fixed": True}, "limits": {}}
    job = store.create_job(
        bundle, job_type="visual.plan_exact", input_payload=payload,
        idempotency_key="visual-repair-plan", created_by="test",
        campaign_id="campaign-visual-repair", requested_machine_id="mission-hub", approved=True,
    )
    specification = {
        "campaign_id": "campaign-visual-repair",
        "plan": {"authority": {"exact_material": True}},
    }
    with store.transaction() as db:
        db.execute(
            """INSERT INTO deployments
               (id,machine_id,role,release_id,source_sha256,environment_sha256,
                config_snapshot_id,status,manifest_json,created_at)
               VALUES('dep-old','mission-hub','mission-hub','release-old',?,?,?,
                      'retired','{}','now')""",
            ("3" * 64, "4" * 64, config_id),
        )
        db.execute(
            """INSERT INTO visual_workflows
               (id,campaign_id,status,specification_json,config_snapshot_id,created_by,created_at,updated_at)
               VALUES('visual-repair','campaign-visual-repair','active',?,'cfg-old-repair','test','now','now')""",
            (json.dumps(specification),),
        )
        db.execute("UPDATE jobs SET config_snapshot_id='cfg-old-repair' WHERE id=?", (job["id"],))
        db.execute(
            "INSERT INTO visual_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES('visual-repair','plan',?,'now')",
            (job["id"],),
        )
        db.execute(
            """INSERT INTO runs
               (id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,
                lease_expires_at,started_at,finished_at,failure_class,failure_code,failure_json)
               VALUES('run-visual-repair',?,1,'mission-hub','dep-old','failed',?,'now','now','now',
                      'repairable_output','output_schema_invalid','{}')""",
            (job["id"], "1" * 64),
        )
        db.execute(
            """INSERT INTO recovery_incidents
               (id,failed_run_id,job_id,campaign_id,state,category,failure_class,failure_code,
                repair_allowed,repair_budget,attempts_started,created_at,updated_at)
               VALUES('inc-visual-repair','run-visual-repair',?,'campaign-visual-repair','verifying',
                      'contract','repairable_output','output_schema_invalid',1,2,1,'now','now')""",
            (job["id"],),
        )
        db.execute(
            """INSERT INTO recovery_attempts(id,incident_id,ordinal,state,strategy,started_at)
               VALUES('rat-visual-repair','inc-visual-repair',1,'verifying','bounded_software_repair','now')"""
        )
        db.execute(
            """INSERT INTO recovery_actions
               (id,attempt_id,sequence,kind,status,evidence_json,evidence_sha256,recorded_at)
               VALUES('rac-visual-repair','rat-visual-repair',1,'job_retry','succeeded','{}',?,'now')""",
            ("2" * 64,),
        )

    result = store.reauthorize_queued_visual_workflows(
        bundle, campaign_id="campaign-visual-repair",
        reason="The repaired frontier must use the active compatible contract.", actor="operator",
    )

    assert result["reauthorized_workflow_ids"] == ["visual-repair"]
    workflow = store.visual_workflow("visual-repair")
    assert workflow["config_snapshot_id"] == config_id
    assert workflow["jobs"][0]["config_snapshot_id"] == config_id
    events = {row["event_type"] for row in store.list_rows("events", limit=100)}
    assert "job.config_reauthorized_after_verified_repair" in events
    assert "visual_workflow.config_reauthorized_after_verified_repair" in events


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
