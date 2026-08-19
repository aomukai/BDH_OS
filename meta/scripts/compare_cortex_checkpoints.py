#!/usr/bin/env python3
"""Compare learned Cortex and optimizer state while ignoring run metadata."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
from typing import Any

import torch


def tensor_sha256(value: torch.Tensor) -> str:
    digest = hashlib.sha256()
    flat = value.detach().cpu().contiguous().view(torch.uint8).reshape(-1)
    chunk = 16 * 1024 * 1024
    for start in range(0, flat.numel(), chunk):
        digest.update(flat[start:start + chunk].numpy().tobytes())
    return digest.hexdigest()


def fingerprints(value: Any, path: str = "") -> dict[str, dict[str, Any]]:
    if isinstance(value, torch.Tensor):
        return {path: {
            "kind": "tensor", "shape": list(value.shape),
            "dtype": str(value.dtype), "sha256": tensor_sha256(value),
        }}
    if isinstance(value, dict):
        result: dict[str, dict[str, Any]] = {}
        for key in sorted(value, key=lambda item: str(item)):
            child = f"{path}.{key}" if path else str(key)
            result.update(fingerprints(value[key], child))
        return result
    if isinstance(value, (list, tuple)):
        result = {}
        for index, item in enumerate(value):
            result.update(fingerprints(item, f"{path}[{index}]"))
        return result
    return {path: {"kind": "value", "value": value}}


def checkpoint_fingerprints(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    value = torch.load(path, map_location="cpu", weights_only=True)
    if value.get("schema_version") != "ninereeds_cortex_checkpoint_v2":
        raise ValueError("unsupported Cortex checkpoint schema")
    identity = {
        "schema_version": value["schema_version"],
        "core_config": value["core_config"],
        "cortex_config": value["cortex_config"],
        "parent": value["parent"],
    }
    learned = fingerprints({
        "trainable_state": value["trainable_state"],
        "optimizer_state": value["optimizer_state"],
    })
    del value
    gc.collect()
    return identity, learned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--observed", type=Path, required=True)
    args = parser.parse_args()
    control_identity, control = checkpoint_fingerprints(args.control)
    observed_identity, observed = checkpoint_fingerprints(args.observed)
    paths = sorted(set(control) | set(observed))
    mismatches = [path for path in paths if control.get(path) != observed.get(path)]
    identity_equal = control_identity == observed_identity
    report = {
        "schema_version": "ninereeds_cortex_checkpoint_learned_state_comparison_v1",
        "comparison_scope": ["trainable_state", "optimizer_state"],
        "ignored_scope": ["metadata", "checkpoint_container_bytes"],
        "identity_equal": identity_equal,
        "learned_state_equal": not mismatches,
        "compared_leaf_count": len(paths),
        "mismatch_count": len(mismatches),
        "mismatch_paths": mismatches[:100],
        "control_identity": control_identity,
        "observed_identity": observed_identity,
    }
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if identity_equal and not mismatches else 2


if __name__ == "__main__":
    raise SystemExit(main())
