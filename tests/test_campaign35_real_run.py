from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import os

import pytest

from mission_hub.campaign35_workflow import Campaign35Coordinator


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
