#!/usr/bin/env python3
"""Measure how M5 training changed each widened M4 half relative to canonical M3."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator

import torch

from analyze_campaign35_m4_merge import Geometry, load, merged_halves_vs_joint, tensor_group


def tensor_items(value: Any, prefix: str = "") -> Iterator[tuple[str, torch.Tensor]]:
    if isinstance(value, torch.Tensor):
        yield prefix, value
    elif isinstance(value, dict):
        for key in sorted(value):
            yield from tensor_items(value[key], f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from tensor_items(item, f"{prefix}.{index}" if prefix else str(index))


def compatible_geometry(left: Any, right: Any) -> dict[str, Any]:
    left_items, right_items = dict(tensor_items(left)), dict(tensor_items(right))
    shared = sorted(
        key for key in left_items.keys() & right_items.keys()
        if left_items[key].shape == right_items[key].shape
    )
    groups: dict[str, Geometry] = {}
    for path in shared:
        group = tensor_group(path)
        groups.setdefault(group, Geometry()).add(left_items[path], right_items[path])
    return {
        "shared_compatible_tensors": len(shared),
        "left_only_or_incompatible": sorted(left_items.keys() - set(shared)),
        "right_only_or_incompatible": sorted(right_items.keys() - set(shared)),
        "groups": {name: metric.report() for name, metric in sorted(groups.items())},
    }


def half_healing(m4: dict[str, Any], m5: dict[str, Any], m3: dict[str, Any]) -> dict[str, Any]:
    before, after = merged_halves_vs_joint(m4, m3), merged_halves_vs_joint(m5, m3)
    report: dict[str, Any] = {}
    for group in sorted(before):
        report[group] = {}
        for half in sorted(before[group]):
            initial, final = before[group][half], after[group][half]
            report[group][half] = {
                "m4_vs_m3": initial,
                "m5_vs_m3": final,
                "difference_rms_change": round(final["difference_rms"] - initial["difference_rms"], 9),
                "relative_l2_change": round(final["relative_l2_to_left"] - initial["relative_l2_to_left"], 9),
                "cosine_change": round(final["cosine"] - initial["cosine"], 9),
                "moved_toward_m3_by_difference_rms": final["difference_rms"] < initial["difference_rms"],
            }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m3", type=Path, required=True)
    parser.add_argument("--m4", type=Path, required=True)
    parser.add_argument("--m5", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    m3, m4, m5 = (load(path) for path in (args.m3, args.m4, args.m5))
    if m4["core_config"] != m5["core_config"]:
        raise ValueError("M4 and M5 core configurations differ")
    report = {
        "schema_version": "ninereeds_campaign35_m5_checkpoint_healing_v1",
        "inputs": {"m3": str(args.m3), "m4": str(args.m4), "m5": str(args.m5)},
        "architecture": {
            "m3_multiplier": m3["core_config"]["mlp_internal_dim_multiplier"],
            "m4_multiplier": m4["core_config"]["mlp_internal_dim_multiplier"],
            "m5_multiplier": m5["core_config"]["mlp_internal_dim_multiplier"],
            "m4_optimizer_present": m4.get("optimizer_state") is not None,
            "m5_optimizer_present": m5.get("optimizer_state") is not None,
        },
        "m4_to_m5_compatible_geometry": compatible_geometry(m4["trainable_state"], m5["trainable_state"]),
        "m4_to_m5_visual_geometry": compatible_geometry(m4.get("visual_state", {}), m5.get("visual_state", {})),
        "halves_relative_to_m3": half_healing(m4, m5, m3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "groups": sorted(report["halves_relative_to_m3"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
