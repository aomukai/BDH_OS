from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import os

import pytest

from mission_hub.campaign35_workflow import Campaign35Coordinator
from mission_hub.config import load_config_bundle
from mission_hub.configured_campaign35 import CAMPAIGN_ID, ConfiguredCampaign35
from mission_hub.errors import SafetyError
from mission_hub.store import MissionHubStore


REPO = Path(__file__).resolve().parents[1]
MATERIAL = REPO / "config/mission_hub/campaign_material/campaign35"


def rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_campaign35_uses_latest_explicit_workflow_attempt_per_batch() -> None:
    def workflow(workflow_id: str, plan_id: str, created_at: str, status: str):
        return {
            "id": workflow_id, "created_at": created_at, "status": status,
            "specification": {"plan": {"plan_id": plan_id}},
        }

    selected = Campaign35Coordinator._latest_visual_attempts([
        workflow("old-failed", "batch-a", "2026-01-01T00:00:00Z", "failed"),
        workflow("other", "batch-b", "2026-01-01T00:00:01Z", "succeeded"),
        workflow("successor", "batch-a", "2026-01-01T00:00:02Z", "active"),
    ])

    assert [(item["specification"]["plan"]["plan_id"], item["id"]) for item in selected] == [
        ("batch-a", "successor"), ("batch-b", "other"),
    ]


def test_campaign35_uses_successful_m4_evaluation_for_authorized_repair() -> None:
    def evaluation(key: str, status: str, checkpoint: str, created_at: str):
        return {
            "id": f"job-{key}", "job_type": "model.evaluate", "status": status,
            "created_at": created_at,
            "input_json": json.dumps({
                "candidate_artifact_id": checkpoint,
                "evaluation_context": {
                    "branch_id": "m4-merged", "branch_complete": True,
                },
            }),
        }

    jobs = {
        "campaign35:m4:evaluate:v1": evaluation(
            "v1", "failed", "art-original", "2026-08-16T16:37:54Z",
        ),
        "campaign35:m4:evaluate:v2": evaluation(
            "v2", "succeeded", "art-repaired", "2026-08-16T16:45:26Z",
        ),
    }

    selected = Campaign35Coordinator._successful_m4_evaluation(jobs, "art-repaired")

    assert selected["id"] == "job-v2"
    assert Campaign35Coordinator._successful_m4_evaluation(jobs, "art-original") is None


def test_campaign35_visual_recovery_restarts_only_authorized_frontiers(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    metadata = {"campaign35_execution": {
        "status": "running", "batches": [{"batch_id": "a"}, {"batch_id": "b"}, {"batch_id": "c"}],
    }}
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES(?, 'Campaign 35', 'active', ?, 'test', ?, 'now', 'now')""",
            (CAMPAIGN_ID, config_id, json.dumps(metadata)),
        )

    def specification(batch: str, seed: int) -> dict:
        return {
            "campaign_id": CAMPAIGN_ID,
            "plan": {
                "plan_id": f"campaign35-{batch}-visual-v1",
                "items": [{
                    "item_id": f"item-{batch}", "prompt": "fixed prompt",
                    "canonical_caption": "fixed caption", "seeds": [seed],
                    "width": 512, "height": 512, "steps": 4, "guidance_scale": 3.5,
                }],
                "authority": {"exact_material": True},
            },
            "experience_events": [{"type": "observe_image", "concept": "fixed"}],
            "limits": {"max_pack_items": 1, "max_candidates_per_item": 1},
        }

    stopped = store.create_visual_workflow(bundle, specification("a", 35_000_001), actor="test")
    blocked = store.create_job(
        bundle, job_type="visual.plan_exact",
        input_payload={"input_artifact_ids": [], "specification": stopped["specification"]["plan"], "limits": stopped["specification"]["limits"]},
        idempotency_key="test:campaign35:blocked-plan", created_by="test",
        campaign_id=CAMPAIGN_ID, requested_machine_id="mission-hub", approved=True,
    )
    store.link_visual_workflow_job(stopped["id"], "plan", blocked["id"], actor="test")
    with store.transaction() as db:
        db.execute("UPDATE jobs SET status='blocked' WHERE id=?", (blocked["id"],))
        store._event(db, "job", blocked["id"], "job.queue_age_exceeded", "test", {})
    store.finish_visual_workflow(stopped["id"], "failed", actor="test", reason="plan:blocked")

    incremental = store.create_visual_workflow(bundle, specification("c", 35_000_003), actor="test")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO artifacts(id,kind,sha256,byte_size,lifecycle,manifest_json,created_at)
               VALUES('art-preserved-plan','visual_plan',?,1,'candidate','{}','now')""",
            ("a" * 64,),
        )
    blocked_candidate = store.create_job(
        bundle, job_type="visual.generate",
        input_payload={
            "input_artifact_ids": ["art-preserved-plan"],
            "specification": {
                "workflow_id": incremental["id"],
                "selection": {"ordinal": 3, "item_id": "item-c", "seed": 35_000_003},
            },
            "limits": incremental["specification"]["limits"],
        },
        idempotency_key="test:campaign35:blocked-candidate", created_by="test",
        campaign_id=CAMPAIGN_ID, requested_machine_id="trainbox", approved=True,
    )
    store.link_visual_workflow_job(incremental["id"], "generate/0003", blocked_candidate["id"], actor="test")
    with store.transaction() as db:
        db.execute("UPDATE jobs SET status='blocked' WHERE id=?", (blocked_candidate["id"],))
        store._event(db, "job", blocked_candidate["id"], "job.queue_age_exceeded", "test", {})
    store.finish_visual_workflow(incremental["id"], "failed", actor="test", reason="generate/0003:blocked")

    rejected = store.create_visual_workflow(bundle, specification("b", 35_000_002), actor="test")
    store.finish_visual_workflow(
        rejected["id"], "failed", actor="test",
        reason="independent review found no usable candidate",
    )

    result = ConfiguredCampaign35(store, bundle, REPO).recover_visual_batches(
        actor="test:on-call", authorization_reference="operator-thread:test",
        expected_exact_restarts=2, expected_seed_replacements=1,
    )

    assert result["exact_restarts"] == 2
    assert result["seed_replacements"] == 1
    latest = Campaign35Coordinator._latest_visual_attempts([
        store.visual_workflow(row["id"])
        for row in store.list_rows("visual_workflows", limit=10)
    ])
    by_plan = {item["specification"]["plan"]["plan_id"]: item for item in latest}
    exact = by_plan["campaign35-a-visual-v1"]
    replacement = by_plan["campaign35-b-visual-v1"]
    assert exact["specification"] == stopped["specification"]
    assert replacement["specification"]["plan"]["items"][0] == {
        **rejected["specification"]["plan"]["items"][0], "seeds": [135_000_002],
    }
    events = store.list_rows("events", limit=100)
    authorized = [item for item in events if item["event_type"] == "visual_workflow.authorized_successor"]
    assert len(authorized) == 3
    assert {json.loads(item["payload_json"])["mode"] for item in authorized} == {
        "exact_restart", "replacement_seeds",
    }


def test_campaign35_queue_expiry_requeues_same_visual_job_immediately(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    metadata = {"campaign35_execution": {
        "status": "running", "batches": [{"batch_id": "a"}],
    }}
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES(?, 'Campaign 35', 'active', ?, 'test', ?, 'now', 'now')""",
            (CAMPAIGN_ID, config_id, json.dumps(metadata)),
        )
    specification = {
        "campaign_id": CAMPAIGN_ID,
        "plan": {
            "plan_id": "campaign35-a-visual-v1",
            "items": [{
                "item_id": "item-a", "prompt": "fixed prompt",
                "canonical_caption": "fixed caption", "seeds": [35_000_001],
                "width": 512, "height": 512, "steps": 4, "guidance_scale": 3.5,
            }],
            "authority": {"exact_material": True},
        },
        "experience_events": [{"type": "observe_image", "concept": "fixed"}],
        "limits": {"max_pack_items": 1, "max_candidates_per_item": 1},
    }
    workflow = store.create_visual_workflow(bundle, specification, actor="test")
    job = store.create_job(
        bundle, job_type="visual.plan_exact",
        input_payload={
            "input_artifact_ids": [], "specification": specification["plan"],
            "limits": specification["limits"],
        },
        idempotency_key="campaign35-queue-expired", created_by="test",
        campaign_id=CAMPAIGN_ID, requested_machine_id="mission-hub", approved=True,
    )
    store.link_visual_workflow_job(workflow["id"], "plan", job["id"], actor="test")
    with store.transaction() as db:
        db.execute("UPDATE jobs SET status='blocked' WHERE id=?", (job["id"],))
        store._event(db, "job", job["id"], "job.queue_age_exceeded", "test", {})
    store.finish_visual_workflow(workflow["id"], "failed", actor="test", reason="plan:blocked")

    result = ConfiguredCampaign35(
        store, bundle, REPO,
    ).resume_queue_expired_visual_frontiers(
        actor="test:on-call", reason="Active workflow frontiers no longer expire.",
        expected_count=1,
    )

    assert result["recovered_count"] == 1
    recovered = store.visual_workflow(workflow["id"])
    assert recovered["status"] == "active"
    assert recovered["jobs"][0]["id"] == job["id"]
    assert recovered["jobs"][0]["status"] == "queued"
    assert recovered["jobs"][0]["available_at"] is None
    evidence = result["recoveries"][0]
    assert evidence["retry_delay_seconds"] == 0
    assert evidence["job_id"] == job["id"]


def test_campaign35_candidate_recommission_stops_at_bounded_attempt_budget(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    with store.transaction() as db:
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES(?, 'Campaign 35', 'active', ?, 'test', '{}', 'now', 'now')""",
            (CAMPAIGN_ID, config_id),
        )
    specification = {
        "campaign_id": CAMPAIGN_ID,
        "plan": {
            "plan_id": "campaign35-bounded-visual-v1",
            "items": [{
                "item_id": "bounded-item", "prompt": "fixed prompt",
                "canonical_caption": "fixed caption", "seeds": [35_000_001],
                "width": 512, "height": 512, "steps": 4, "guidance_scale": 3.5,
            }],
            "authority": {"exact_material": True},
        },
        "experience_events": [{"type": "observe_image", "concept": "fixed"}],
        "limits": {"max_pack_items": 1, "max_candidates_per_item": 1},
    }
    configured = ConfiguredCampaign35(store, bundle, REPO)
    current = store.create_visual_workflow(bundle, specification, actor="test")

    for attempt in range(4):
        store.finish_visual_workflow(
            current["id"], "failed", actor="test",
            reason="independent review found no usable candidate",
        )
        successor = configured.recommission_visual_workflow(
            current["id"], actor="test",
            authority_reference=f"automatic-candidate-retry:{current['id']}",
            candidate_attempt_budget=4,
        )
        if attempt < 3:
            assert successor is not None
            current = store.visual_workflow(successor["successor_workflow_id"])
        else:
            assert successor is None

    assert len(store.list_rows("visual_workflows", limit=10)) == 4


def test_campaign35_legacy_m1_material_is_exactly_batched_and_ordered() -> None:
    # This immutable source bundle produced the completed M1.  Its obsolete
    # sentence-matched visual rows are deliberately *not* the replacement
    # 25,000-event visual curriculum; the coordinator's frozen-curriculum gate
    # prevents them from being used for M2.
    manifest = json.loads((MATERIAL / "manifest.json").read_text(encoding="utf-8"))
    curriculum = rows(MATERIAL / "curriculum.jsonl")
    text = rows(MATERIAL / "text-lessons.jsonl")
    visual = rows(MATERIAL / "visual-items.jsonl")
    assert len(curriculum) == 2500
    assert [item["ordinal"] for item in curriculum] == list(range(1, 2501))
    assert len(text) == len(visual) == 7891
    assert manifest["batch_count"] == 100
    assert sum(item["text_examples"] for item in manifest["batches"]) == 7891
    assert sum(item["visual_items"] for item in manifest["batches"]) == 7891
    assert max(item["visual_items"] for item in manifest["batches"]) <= 128
    assert [(item["ordinal"], item["example_index"]) for item in text] == [
        (item["ordinal"], item["example_index"]) for item in visual
    ]
    # Only the first exposure declares each dependency-list entry; later
    # exposures retain lesson_concept without duplicating a taught concept.
    declared = [item["concept"] for item in text if "concept" in item]
    assert declared == [item["concept"] for item in curriculum]
    identity = [item for item in text if item["concept_id"] == "identity"]
    assert any(item["completion"] == "I am Ninereeds. I am a mind. I learn." for item in identity)
    assert all("I have no mind" not in item["completion"] for item in identity)
    assert all("[Ninereeds]" not in item["completion"] for item in text)
    assert max(len(item["completion"].encode("utf-8")) for item in text) <= 512


def test_campaign35_visual_joint_and_healing_share_images_but_not_targets() -> None:
    coordinator = object.__new__(Campaign35Coordinator)
    coordinator.campaign_id = "campaign-35-multimodal-foundation-v1"
    execution = {"evaluation_suite_artifact_id": "art-0000000000000001"}
    inputs = [{
        "batch": {
            "batch_id": "c0001-c0025",
            "ordered_concepts": [{"concept": "dog", "depends_on": []}],
        },
        "features": {"id": "art-0000000000000002"},
        "experience": {
            "id": "art-0000000000000003",
            "manifest": {"events": [
                {"type": "observe_image", "concept": "dog", "word": "dog", "ordinal": 1, "example_index": 1, "asset_sha256": "1" * 64},
                {"type": "hear_or_read_text", "concept": "dog", "ordinal": 1, "example_index": 1, "text": "A brown dog runs through green grass."},
                {"type": "observe_image", "concept": "dog", "word": "dog", "ordinal": 1, "example_index": 2, "asset_sha256": "2" * 64},
                {"type": "hear_or_read_text", "concept": "dog", "ordinal": 1, "example_index": 2, "text": "A white dog sleeps beside a chair."},
            ]},
        },
    }]
    m2 = coordinator._multimodal_workflow(
        execution, inputs, "art-0000000000000004", "m2-images", "visual",
    )
    m3 = coordinator._multimodal_workflow(
        execution, inputs, "art-0000000000000004", "m3-words-and-images", "joint",
    )
    m5 = coordinator._replay_multimodal_workflow(
        execution,
        {"specification": m3},
        {
            "session_count": 1,
            "event_count": 2,
            "visual_event_count": 2,
            "text_event_count": 0,
        },
        "art-0000000000000005",
        "m5-healed",
    )
    assert m2["evaluation_policy"] == "none"
    assert [event["completion"] for event in m2["sessions"][0]["events"]] == ["dog", "dog"]
    assert [event["type"] for event in m3["sessions"][0]["events"]] == ["visual", "visual"]
    assert [event["completion"] for event in m3["sessions"][0]["events"]] == [
        "A brown dog runs through green grass.",
        "A white dog sleeps beside a chair.",
    ]
    assert m5["sessions"][0]["events"] == m3["sessions"][0]["events"]
    assert m5["sessions"][0]["id"] == f"m5-replay-{m3['sessions'][0]['id']}"
    assert [
        {**session, "id": m3["sessions"][index]["id"]}
        for index, session in enumerate(m5["sessions"])
    ] == m3["sessions"]
    assert m5["starting_checkpoint_artifact_id"] == "art-0000000000000005"


def test_campaign35_m5_rejects_a_successful_m3_restart_continuation() -> None:
    coordinator = object.__new__(Campaign35Coordinator)
    coordinator.campaign_id = "campaign-35-multimodal-foundation-v1"
    execution = {"evaluation_suite_artifact_id": "art-0000000000000001"}
    continuation = {
        "branch_id": "m3-words-and-images",
        "training_job_type": "model.multimodal_train",
        "multimodal_mode": "joint",
        "sessions": [
            {"id": f"m3-joint-v3-{index:02d}", "events": []}
            for index in range(8, 51)
        ],
    }

    with pytest.raises(SafetyError, match="partial M3 ledger"):
        coordinator._replay_multimodal_workflow(
            execution,
            {"specification": continuation},
            {
                "session_count": 51,
                "event_count": 22_288,
                "visual_event_count": 14_397,
                "text_event_count": 7_891,
            },
            "art-0000000000000005",
            "m5-healed",
        )


def test_campaign35_m2_rejects_an_implicit_or_multiword_label() -> None:
    coordinator = object.__new__(Campaign35Coordinator)
    coordinator.campaign_id = "campaign-35-multimodal-foundation-v1"
    inputs = [{
        "batch": {"batch_id": "c0001-c0025", "ordered_concepts": [{"concept": "red apple", "depends_on": []}]},
        "features": {"id": "art-0000000000000002"},
        "experience": {
            "id": "art-0000000000000003",
            "manifest": {"events": [
                {"type": "observe_image", "concept": "red apple", "word": "red apple", "ordinal": 1, "example_index": 1, "asset_sha256": "1" * 64},
                {"type": "hear_or_read_text", "concept": "red apple", "ordinal": 1, "example_index": 1, "text": "A red apple."},
            ]},
        },
    }]
    with pytest.raises(SafetyError, match="explicit, non-empty one-word label"):
        coordinator._multimodal_workflow(
            {"evaluation_suite_artifact_id": "art-0000000000000001"},
            inputs,
            "art-0000000000000004",
            "m2-images",
            "visual",
        )


def test_sparse_neuron_merge_concatenates_core_and_averages_shared_bridges(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
    from bdh import BDH, BDHConfig

    config = {
        "n_layer": 1, "n_embd": 3, "dropout": 0.0, "n_head": 2,
        "mlp_internal_dim_multiplier": 4, "vocab_size": 8,
        "per_layer_weights": True, "architecture_variant": "bdh_v1",
        "activation_history_mix": 0.0, "activation_history_decay": 0.5,
        "activation_history_target": "x", "activation_history_max_mix": 0.5,
        "learned_activation_history": False, "attention_decay": None,
        "learned_attention_decay": False, "compute_ticks": 1,
        "adaptive_compute": False, "adaptive_min_ticks": 1,
        "adaptive_max_ticks": 1, "adaptive_logit_delta_threshold": 0.0,
    }
    def checkpoint(value: float, *, visual: bool):
        core_state = BDH(BDHConfig(**config)).state_dict()
        for key, tensor in core_state.items():
            if key != "attn.freqs" and tensor.is_floating_point():
                core_state[key] = torch.full_like(tensor, value)
        document = {
            "schema_version": "ninereeds_cortex_checkpoint_v2",
            "core_config": config, "cortex_config": {}, "parent": "scratch",
            "trainable_state": {
                "core": core_state,
                "ingress_projector": {"weight": torch.full((3, 3), value)},
                "intention": {"weight": torch.full((3, 3), value)},
                "expression_projector": {"weight": torch.full((3, 3), value)},
            },
            "optimizer_state": None, "metadata": {},
        }
        if visual:
            document["visual_state"] = {"schema_version": "visual", "config": {}, "resampler_state": {"weight": torch.ones(1)}}
        return document
    left, right = tmp_path / "left.pt", tmp_path / "right.pt"
    output, report = tmp_path / "merged.pt", tmp_path / "report.json"
    torch.save(checkpoint(1.0, visual=False), left); torch.save(checkpoint(3.0, visual=True), right)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(REPO) + os.pathsep + environment.get("PYTHONPATH", "")
    completed = subprocess.run([
        sys.executable, str(REPO / "meta/scripts/merge_cortex.py"),
        "--left", str(left), "--right", str(right), "--output", str(output), "--report", str(report),
    ], capture_output=True, text=True, check=False, env=environment)
    assert completed.returncode == 0, completed.stderr
    merged = torch.load(output, map_location="cpu", weights_only=True)
    assert merged["core_config"]["mlp_internal_dim_multiplier"] == 8
    assert merged["trainable_state"]["core"]["encoder.0"].shape == (2, 3, 12)
    assert merged["trainable_state"]["core"]["decoder.0"].shape == (24, 3)
    assert merged["trainable_state"]["core"]["attn.freqs"].shape == (1, 1, 1, 12)
    merged_core = BDH(BDHConfig(**merged["core_config"]))
    merged_core.load_state_dict(merged["trainable_state"]["core"], strict=True)
    assert torch.all(merged["trainable_state"]["ingress_projector"]["weight"] == 2)
    assert merged["visual_state"] == checkpoint(3.0, visual=True)["visual_state"]
    receipt = json.loads(report.read_text(encoding="utf-8"))
    assert receipt["optimizer_policy"] == "discard_source_optimizer_state"
