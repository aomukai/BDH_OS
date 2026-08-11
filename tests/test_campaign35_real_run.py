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


def test_campaign35_material_is_exactly_batched_and_ordered() -> None:
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


def test_sparse_neuron_merge_concatenates_core_and_averages_shared_bridges(tmp_path: Path) -> None:
    torch = pytest.importorskip("torch")
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
        document = {
            "schema_version": "ninereeds_cortex_checkpoint_v2",
            "core_config": config, "cortex_config": {}, "parent": "scratch",
            "trainable_state": {
                "core": {
                    "encoder.0": torch.full((2, 3, 6), value),
                    "encoder_v.0": torch.full((2, 3, 6), value),
                    "decoder.0": torch.full((12, 3), value),
                    "embed.weight": torch.full((8, 3), value),
                },
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
    assert torch.all(merged["trainable_state"]["ingress_projector"]["weight"] == 2)
    assert merged["visual_state"] == checkpoint(3.0, visual=True)["visual_state"]
    receipt = json.loads(report.read_text(encoding="utf-8"))
    assert receipt["optimizer_policy"] == "discard_source_optimizer_state"
