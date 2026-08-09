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
from meta.scripts.visual_runtime import selected_generation_items


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


def test_new_visual_workflow_fans_out_one_immutable_candidate_job_at_a_time() -> None:
    coordinator = VisualWorkflowCoordinator.__new__(VisualWorkflowCoordinator)
    workflow = {
        "id": "visual-incremental", "campaign_id": "campaign-test",
        "specification": {
            "plan": {"items": [
                {"item_id": "dog", "seeds": [11, 12]},
                {"item_id": "cat", "seeds": [13]},
            ]},
            "limits": {"max_pack_items": 3, "max_candidates_per_item": 2},
            "experience_events": [{"type": "observe_image"}],
        },
    }
    plan = ({"id": "job-plan"}, [{"id": "art-plan", "kind": "visual_plan"}], "2026-08-09T00:00:00Z")
    captured = {}

    def next_job(workflow, key, job_type, artifact_ids, predecessor, actor, *, specification=None):
        captured.update({
            "key": key, "job_type": job_type, "artifact_ids": artifact_ids,
            "specification": specification,
        })
        return {"status": "queued", "stage": key, "job_id": "job-generate-0"}

    coordinator._next = next_job
    result = coordinator._advance_incremental(workflow, {}, plan, actor="test")

    assert result["job_id"] == "job-generate-0"
    assert captured == {
        "key": "generate/0000", "job_type": "visual.generate",
        "artifact_ids": ["art-plan"],
        "specification": {
            "workflow_id": "visual-incremental",
            "selection": {"ordinal": 0, "item_id": "dog", "seed": 11},
        },
    }
    assert VisualWorkflowCoordinator._candidate_units(workflow) == [
        {"ordinal": 0, "item_id": "dog", "seed": 11},
        {"ordinal": 1, "item_id": "dog", "seed": 12},
        {"ordinal": 2, "item_id": "cat", "seed": 13},
    ]


def test_visual_candidate_fanout_resumes_after_restart_without_repeating_success() -> None:
    coordinator = VisualWorkflowCoordinator.__new__(VisualWorkflowCoordinator)
    workflow = {
        "id": "visual-restarted", "campaign_id": "campaign-test",
        "specification": {
            "plan": {"items": [{"item_id": "dog", "seeds": [11, 12]}]},
            "limits": {"max_pack_items": 2, "max_candidates_per_item": 2},
            "experience_events": [{"type": "observe_image"}],
        },
    }
    plan = ({"id": "job-plan"}, [{"id": "art-plan", "kind": "visual_plan"}], "2026-08-09T00:00:00Z")
    completed = (
        {"id": "job-generate-0"},
        [
            {"id": "candidate-0", "kind": "visual_candidate"},
            {"id": "report-0", "kind": "visual_generation_report"},
        ],
        "2026-08-09T00:10:00Z",
    )
    coordinator.store = SimpleNamespace(workflow_job_artifacts=lambda job_id: completed)
    captured = {}
    coordinator._next = lambda workflow, key, job_type, artifact_ids, predecessor, actor, **kwargs: captured.update(
        {"key": key, "job_type": job_type, "specification": kwargs["specification"]},
    ) or {"status": "queued", "stage": key, "job_id": "job-generate-1"}

    result = coordinator._advance_incremental(
        workflow, {"generate/0000": {"id": "job-generate-0", "status": "succeeded"}},
        plan, actor="test:restart",
    )

    assert result["job_id"] == "job-generate-1"
    assert captured["key"] == "generate/0001"
    assert captured["specification"]["selection"] == {"ordinal": 1, "item_id": "dog", "seed": 12}


def test_preserved_batch_generation_resumes_at_first_per_candidate_inspection() -> None:
    coordinator = VisualWorkflowCoordinator.__new__(VisualWorkflowCoordinator)
    workflow = {
        "id": "visual-migrated", "campaign_id": "campaign-test",
        "specification": {
            "plan": {"items": [{"item_id": "dog", "seeds": [11]}]},
            "limits": {"max_pack_items": 1, "max_candidates_per_item": 1},
            "experience_events": [{"type": "observe_image"}],
        },
    }
    plan = ({"id": "job-plan"}, [{"id": "art-plan", "kind": "visual_plan"}], "2026-08-09T00:00:00Z")
    generated = (
        {"id": "job-generate"},
        [
            {"id": "candidate", "kind": "visual_candidate", "manifest": {"item_id": "dog", "seed": 11}},
            {"id": "generation-report", "kind": "visual_generation_report", "manifest": {}},
        ],
        "2026-08-09T00:10:00Z",
    )
    captured = {}
    coordinator._next = lambda workflow, key, job_type, artifact_ids, predecessor, actor, **kwargs: captured.update(
        {"key": key, "job_type": job_type, "artifact_ids": artifact_ids},
    ) or {"status": "queued", "stage": key}

    result = coordinator._advance_incremental(
        workflow, {}, plan, actor="test", preserved_generation=generated,
    )

    assert result["stage"] == "inspect/0000"
    assert captured == {
        "key": "inspect/0000", "job_type": "visual.inspect",
        "artifact_ids": ["candidate", "generation-report"],
    }


def test_paused_migration_cancels_only_unstarted_legacy_frontier(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    jobs = [
        store.create_job(
            bundle, job_type="system.healthcheck", input_payload={},
            idempotency_key=f"legacy-{stage}", created_by="test",
            requested_machine_id="mission-hub", approved=True,
        )
        for stage in ("plan", "generate", "inspect")
    ]
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES('campaign-migrate','Visual','active',?,'test','{}','now','now')""",
            (config_id,),
        )
        db.execute(
            """INSERT INTO visual_workflows
               (id,campaign_id,status,specification_json,config_snapshot_id,created_by,created_at,updated_at)
               VALUES('visual-migrate','campaign-migrate','active','{}',?,'test','now','now')""",
            (config_id,),
        )
        for stage, job in zip(("plan", "generate", "inspect"), jobs, strict=True):
            db.execute(
                "INSERT INTO visual_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES('visual-migrate',?,?,?)",
                (stage, job["id"], f"now-{stage}"),
            )
        db.execute("UPDATE jobs SET status='succeeded' WHERE id IN (?,?)", (jobs[0]["id"], jobs[1]["id"]))

    result = store.migrate_legacy_visual_workflow_to_fanout("visual-migrate", actor="operator")

    assert result["cancelled_job_ids"] == [jobs[2]["id"]]
    workflow = store.visual_workflow("visual-migrate")
    assert {item["stage_key"]: item["status"] for item in workflow["jobs"]} == {
        "plan": "succeeded", "generate": "succeeded", "inspect": "cancelled",
    }
    assert store.visual_workflow_uses_preserved_generation_fanout("visual-migrate") is True


def test_runtime_selection_rejects_stale_or_copied_candidate_identity() -> None:
    items = [{"item_id": "dog", "prompt": "a dog", "seeds": [11, 12]}]
    assert selected_generation_items(
        items, {"ordinal": 1, "item_id": "dog", "seed": 12},
    ) == [{"item_id": "dog", "prompt": "a dog", "seeds": [12]}]
    with pytest.raises(ValueError, match="disagrees"):
        selected_generation_items(items, {"ordinal": 1, "item_id": "cat", "seed": 12})


def test_incremental_decision_receives_only_its_immutable_commission_item() -> None:
    workflow = {
        "specification": {"plan": {
            "plan_id": "plan-test", "canonical_text": ["A dog.", "A cat."],
            "items": [
                {"item_id": "dog", "canonical_caption": "A dog.", "seeds": [11]},
                {"item_id": "cat", "canonical_caption": "A cat.", "seeds": [12]},
            ],
        }},
    }

    subset = VisualWorkflowCoordinator._commission_for_unit(
        workflow, {"ordinal": 1, "item_id": "cat", "seed": 12},
    )

    assert subset == {
        "plan_id": "plan-test", "canonical_text": ["A cat."],
        "items": [{"item_id": "cat", "canonical_caption": "A cat.", "seeds": [12]}],
    }


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

    restart_job = store.create_job(
        bundle, job_type="visual.plan_exact", input_payload=payload,
        idempotency_key="visual-settings-restart-plan", created_by="test",
        campaign_id="campaign-visual-repair", requested_machine_id="mission-hub", approved=True,
    )
    with store.transaction() as db:
        db.execute(
            """INSERT INTO visual_workflows
               (id,campaign_id,status,specification_json,config_snapshot_id,created_by,created_at,updated_at)
               VALUES('visual-settings-restart','campaign-visual-repair','active',?,
                      'cfg-old-repair','test','now','now')""",
            (json.dumps(specification),),
        )
        db.execute(
            "UPDATE jobs SET config_snapshot_id='cfg-old-repair' WHERE id=?", (restart_job["id"],),
        )
        db.execute(
            """INSERT INTO visual_workflow_jobs(workflow_id,stage_key,job_id,created_at)
               VALUES('visual-settings-restart','plan',?,'now')""",
            (restart_job["id"],),
        )
        db.execute(
            """INSERT INTO runs
               (id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,
                lease_expires_at,started_at,finished_at)
               VALUES('run-settings-restart',?,1,'mission-hub','dep-old','cancelled',
                      ?,'now','now','now')""",
            (restart_job["id"], "5" * 64),
        )
        store._event(
            db, "job", restart_job["id"], "job.settings_restart_requested", "test", {},
        )

    restarted = store.reauthorize_queued_visual_workflows(
        bundle, campaign_id="campaign-visual-repair",
        reason="The authorized settings restart resumes under the active contract.", actor="operator",
    )

    assert restarted["reauthorized_workflow_ids"] == ["visual-settings-restart"]
    events = {row["event_type"] for row in store.list_rows("events", limit=200)}
    assert "job.config_reauthorized_after_settings_restart" in events
    assert "visual_workflow.config_reauthorized_after_settings_restart" in events


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
