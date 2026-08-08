#!/usr/bin/env python3
"""Merge two compatible Cortex checkpoints by concatenating BDH sparse neurons."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

import torch

from bdh import BDHConfig
from cortex.student import CORTEX_CHECKPOINT_SCHEMA


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def load(path: Path) -> dict[str, Any]:
    torch.serialization.add_safe_globals([BDHConfig])
    value = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(value, dict) or value.get("schema_version") != CORTEX_CHECKPOINT_SCHEMA:
        raise ValueError(f"not a current Cortex checkpoint: {path}")
    return value


def average(a: dict[str, torch.Tensor], b: dict[str, torch.Tensor], name: str, receipt: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
    if set(a) != set(b):
        raise ValueError(f"{name} state keys differ")
    result = {}
    for key in sorted(a):
        if a[key].shape != b[key].shape or a[key].dtype != b[key].dtype:
            raise ValueError(f"{name}.{key} is incompatible")
        result[key] = ((a[key].float() + b[key].float()) / 2).to(a[key].dtype)
        receipt.append({"tensor": f"{name}.{key}", "policy": "arithmetic_mean", "shape": list(result[key].shape)})
    return result


def merge_core(a: dict[str, torch.Tensor], b: dict[str, torch.Tensor], per_layer: bool, receipt: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
    if set(a) != set(b):
        raise ValueError("core state keys differ")
    result = {}
    for key in sorted(a):
        left, right = a[key], b[key]
        if left.shape != right.shape or left.dtype != right.dtype:
            raise ValueError(f"core.{key} is incompatible")
        base = key.rsplit(".", 1)[0] if per_layer and key.rsplit(".", 1)[-1].isdigit() else key
        if base.startswith("encoder"):
            result[key] = torch.cat((left, right), dim=-1)
            policy = "concatenate_sparse_neuron_axis_last"
        elif base.startswith("decoder"):
            result[key] = torch.cat((left, right), dim=0)
            policy = "concatenate_sparse_neuron_axis_first"
        else:
            result[key] = ((left.float() + right.float()) / 2).to(left.dtype)
            policy = "arithmetic_mean"
        receipt.append({"tensor": f"core.{key}", "policy": policy, "shape": list(result[key].shape)})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    left, right = load(args.left), load(args.right)
    if left["core_config"] != right["core_config"] or left["cortex_config"] != right["cortex_config"]:
        raise ValueError("merge sources have different architecture configurations")
    config = dict(left["core_config"])
    old_multiplier = int(config["mlp_internal_dim_multiplier"])
    config["mlp_internal_dim_multiplier"] = old_multiplier * 2
    receipt: list[dict[str, Any]] = []
    state = {
        "core": merge_core(left["trainable_state"]["core"], right["trainable_state"]["core"], bool(config["per_layer_weights"]), receipt),
        "ingress_projector": average(left["trainable_state"]["ingress_projector"], right["trainable_state"]["ingress_projector"], "ingress_projector", receipt),
        "intention": average(left["trainable_state"]["intention"], right["trainable_state"]["intention"], "intention", receipt),
        "expression_projector": average(left["trainable_state"]["expression_projector"], right["trainable_state"]["expression_projector"], "expression_projector", receipt),
    }
    # M2 is the right-hand source by contract and owns the learned visual receptor bridge.
    if "visual_state" not in right:
        raise ValueError("right-hand image specialist has no visual state")
    document = {
        "schema_version": CORTEX_CHECKPOINT_SCHEMA,
        "core_config": config,
        "cortex_config": left["cortex_config"],
        "parent": {"left_sha256": digest(args.left), "right_sha256": digest(args.right)},
        "trainable_state": state,
        "visual_state": right["visual_state"],
        "optimizer_state": None,
        "metadata": {
            "schema_version": "ninereeds_sparse_neuron_merge_v1",
            "merge_policy": "concatenate_bdh_sparse_neurons_average_shared_bridges",
            "left_sha256": digest(args.left), "right_sha256": digest(args.right),
            "old_multiplier": old_multiplier, "new_multiplier": config["mlp_internal_dim_multiplier"],
            "optimizer_policy": "discard_source_optimizer_state",
            "visual_state_policy": "carry_right_image_specialist",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(document, args.output)
    report = {**document["metadata"], "output_sha256": digest(args.output), "tensor_receipt": receipt}
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
