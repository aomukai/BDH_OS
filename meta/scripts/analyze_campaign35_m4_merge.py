#!/usr/bin/env python3
"""Audit exact M4 merge inheritance and source-relative weight geometry."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import torch

from bdh import BDHConfig


def load(path: Path) -> dict[str, Any]:
    torch.serialization.add_safe_globals([BDHConfig])
    value = torch.load(path, map_location="cpu", weights_only=True)
    if value.get("schema_version") != "ninereeds_cortex_checkpoint_v2":
        raise ValueError(f"unsupported Cortex checkpoint: {path}")
    return value


def tensor_group(path: str) -> str:
    if path.startswith("core.encoder") or path.startswith("core.encoder_v"):
        return "core_encoder"
    if path.startswith("core.decoder"):
        return "core_decoder"
    if path == "core.attn.freqs":
        return "attention_frequencies"
    if path.startswith("core."):
        return "core_shared"
    return path.split(".", 1)[0]


class Geometry:
    def __init__(self) -> None:
        self.dot = self.left_sq = self.right_sq = self.diff_sq = 0.0
        self.count = 0

    def add(self, left: torch.Tensor, right: torch.Tensor) -> None:
        if left.shape != right.shape:
            raise ValueError(f"geometry shape mismatch: {left.shape} != {right.shape}")
        a, b = left.detach().float().reshape(-1), right.detach().float().reshape(-1)
        self.dot += float(torch.dot(a, b))
        self.left_sq += float(torch.dot(a, a))
        self.right_sq += float(torch.dot(b, b))
        delta = a - b
        self.diff_sq += float(torch.dot(delta, delta))
        self.count += a.numel()

    def report(self) -> dict[str, float | int]:
        denominator = math.sqrt(max(self.left_sq * self.right_sq, 0.0))
        return {
            "elements": self.count,
            "cosine": round(self.dot / denominator, 9) if denominator else 0.0,
            "left_rms": round(math.sqrt(self.left_sq / self.count), 9) if self.count else 0.0,
            "right_rms": round(math.sqrt(self.right_sq / self.count), 9) if self.count else 0.0,
            "difference_rms": round(math.sqrt(self.diff_sq / self.count), 9) if self.count else 0.0,
            "relative_l2_to_left": round(math.sqrt(self.diff_sq / self.left_sq), 9) if self.left_sq else 0.0,
        }


def state_items(checkpoint: dict[str, Any]):
    for component, state in checkpoint["trainable_state"].items():
        for key, tensor in state.items():
            yield f"{component}.{key}", tensor


def nested_equal(left: Any, right: Any) -> bool:
    if isinstance(left, torch.Tensor) and isinstance(right, torch.Tensor):
        return left.shape == right.shape and left.dtype == right.dtype and torch.equal(left, right)
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(nested_equal(left[key], right[key]) for key in left)
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return len(left) == len(right) and all(nested_equal(a, b) for a, b in zip(left, right))
    return left == right


def geometry(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    a, b = dict(state_items(left)), dict(state_items(right))
    if set(a) != set(b):
        raise ValueError("checkpoint trainable-state paths differ")
    groups: dict[str, Geometry] = {}
    for path in sorted(a):
        group = groups.setdefault(tensor_group(path), Geometry())
        group.add(a[path], b[path])
    return {name: value.report() for name, value in sorted(groups.items())}


def exact_merge_audit(left: dict[str, Any], right: dict[str, Any], merged: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    receipt: list[dict[str, Any]] = []
    for key, observed in merged["trainable_state"]["core"].items():
        a, b = left["trainable_state"]["core"][key], right["trainable_state"]["core"][key]
        base = key.rsplit(".", 1)[0] if left["core_config"]["per_layer_weights"] and key.rsplit(".", 1)[-1].isdigit() else key
        if base.startswith("encoder") or base == "attn.freqs":
            split = a.shape[-1]
            passed = observed.shape[-1] == split + b.shape[-1] and torch.equal(observed[..., :split], a) and torch.equal(observed[..., split:], b)
            policy = "left_then_right_last_axis"
        elif base.startswith("decoder"):
            split = a.shape[0]
            passed = observed.shape[0] == split + b.shape[0] and torch.equal(observed[:split], a) and torch.equal(observed[split:], b)
            policy = "left_then_right_first_axis"
        else:
            expected = ((a.float() + b.float()) / 2).to(a.dtype)
            passed = torch.equal(observed, expected)
            policy = "arithmetic_mean"
        receipt.append({"tensor": f"core.{key}", "policy": policy, "passed": passed})
        if not passed:
            failures.append(f"core.{key}")
    for component in ("ingress_projector", "intention", "expression_projector"):
        for key, observed in merged["trainable_state"][component].items():
            a, b = left["trainable_state"][component][key], right["trainable_state"][component][key]
            passed = torch.equal(observed, ((a.float() + b.float()) / 2).to(a.dtype))
            receipt.append({"tensor": f"{component}.{key}", "policy": "arithmetic_mean", "passed": passed})
            if not passed:
                failures.append(f"{component}.{key}")
    visual_equal = nested_equal(merged.get("visual_state"), right.get("visual_state"))
    return {
        "passed": not failures and visual_equal,
        "checked_tensors": len(receipt),
        "failed_tensors": failures,
        "visual_state_exactly_from_m2": visual_equal,
        "receipt": receipt,
    }


def merged_halves_vs_joint(merged: dict[str, Any], joint: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, dict[str, Geometry]] = {}
    for key, value in merged["trainable_state"]["core"].items():
        target = joint["trainable_state"]["core"][key]
        base = key.rsplit(".", 1)[0] if merged["core_config"]["per_layer_weights"] and key.rsplit(".", 1)[-1].isdigit() else key
        group = tensor_group(f"core.{key}")
        values = groups.setdefault(group, {"m1_half_vs_m3": Geometry(), "m2_half_vs_m3": Geometry()})
        if base.startswith("encoder") or base == "attn.freqs":
            split = target.shape[-1]
            values["m1_half_vs_m3"].add(value[..., :split], target)
            values["m2_half_vs_m3"].add(value[..., split:], target)
        elif base.startswith("decoder"):
            split = target.shape[0]
            values["m1_half_vs_m3"].add(value[:split], target)
            values["m2_half_vs_m3"].add(value[split:], target)
        else:
            values["m1_half_vs_m3"].add(value, target)
            values["m2_half_vs_m3"].add(value, target)
    return {
        group: {name: metric.report() for name, metric in comparisons.items()}
        for group, comparisons in sorted(groups.items())
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m1", type=Path, required=True)
    parser.add_argument("--m2", type=Path, required=True)
    parser.add_argument("--m3", type=Path, required=True)
    parser.add_argument("--m4", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    m1, m2, m3, m4 = (load(path) for path in (args.m1, args.m2, args.m3, args.m4))
    report = {
        "schema_version": "ninereeds_campaign35_m4_merge_diagnostic_v1",
        "inputs": {name: str(path) for name, path in (("m1", args.m1), ("m2", args.m2), ("m3", args.m3), ("m4", args.m4))},
        "architecture": {
            "source_multiplier": m1["core_config"]["mlp_internal_dim_multiplier"],
            "merged_multiplier": m4["core_config"]["mlp_internal_dim_multiplier"],
            "source_optimizer_present": {"m1": m1.get("optimizer_state") is not None, "m2": m2.get("optimizer_state") is not None, "m3": m3.get("optimizer_state") is not None},
            "m4_optimizer_present": m4.get("optimizer_state") is not None,
        },
        "exact_merge_audit": exact_merge_audit(m1, m2, m4),
        "source_geometry": {
            "m1_vs_m2": geometry(m1, m2),
            "m1_vs_m3": geometry(m1, m3),
            "m2_vs_m3": geometry(m2, m3),
        },
        "merged_halves_vs_m3": merged_halves_vs_joint(m4, m3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "exact_merge_passed": report["exact_merge_audit"]["passed"],
        "checked_tensors": report["exact_merge_audit"]["checked_tensors"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
