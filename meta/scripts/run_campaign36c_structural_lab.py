#!/usr/bin/env python3
"""Run the Campaign 36C Stage-6 packing, fusion, rigidity, and fission lab."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
from pathlib import Path
from typing import Any

import torch

from campaign36c import (
    StructuralLabConfig,
    merge_structural_lab_results,
    run_structural_laboratory,
    write_structural_lab_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify co-access packing, reversible pairwise fusion, UID/trust "
            "continuity, explicit rigidity, and seam-gated early fission."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--rotary-pairs", type=int, default=2)
    parser.add_argument("--sequence-length", type=int, default=16)
    parser.add_argument("--benchmark-warmup", type=int, default=3)
    parser.add_argument("--benchmark-iterations", type=int, default=20)
    parser.add_argument("--page-capacity", type=int, default=2)
    parser.add_argument("--maximum-composite-leaves", type=int, default=2)
    parser.add_argument("--behavior-tolerance", type=float)
    parser.add_argument("--maximum-seam-regression", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=36_600)
    devices = parser.add_mutually_exclusive_group()
    devices.add_argument("--device")
    devices.add_argument("--devices", nargs="+")
    parser.add_argument("--dtype", choices=("float32", "bfloat16"), default="float32")
    return parser.parse_args()


def resolve_devices(device: str | None, devices: list[str] | None) -> list[str]:
    requested = devices or ([device] if device is not None else ["auto"])
    if requested != ["auto"]:
        return [str(torch.device(value)) for value in requested]
    if not torch.cuda.is_available():
        return ["cpu"]
    return [f"cuda:{index}" for index in range(torch.cuda.device_count())]


def _run(specification: dict[str, Any]) -> dict[str, Any]:
    return run_structural_laboratory(
        StructuralLabConfig(**specification["config"]),
        device=specification["device"],
        dtype=getattr(torch, specification["dtype"]),
        scratch_root=specification["scratch_root"],
    )


def main() -> None:
    args = parse_args()
    devices = resolve_devices(args.device, args.devices)
    if any(torch.device(value).type == "cpu" for value in devices) and args.dtype != "float32":
        raise ValueError("the Stage-6 CPU lab requires float32")
    tolerance = args.behavior_tolerance
    if tolerance is None:
        tolerance = 0.02 if args.dtype == "bfloat16" else 1e-5
    config = StructuralLabConfig(
        width=args.width,
        rotary_pairs=args.rotary_pairs,
        sequence_length=args.sequence_length,
        benchmark_warmup=args.benchmark_warmup,
        benchmark_iterations=args.benchmark_iterations,
        page_capacity=args.page_capacity,
        maximum_composite_leaves=args.maximum_composite_leaves,
        behavior_tolerance=tolerance,
        maximum_seam_regression=args.maximum_seam_regression,
        seed=args.seed,
    )
    config.validate()
    scratch_root = args.scratch_root or args.output.parent / "stage6-scratch"
    specifications = [
        {
            "config": config.__dict__,
            "device": device,
            "dtype": args.dtype,
            "scratch_root": str(scratch_root),
        }
        for device in devices
    ]
    if len(specifications) == 1:
        result = _run(specifications[0])
    else:
        context = multiprocessing.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=len(specifications), mp_context=context
        ) as executor:
            reports = list(executor.map(_run, specifications))
        result = merge_structural_lab_results(reports)
    write_structural_lab_result(args.output, result)
    print(json.dumps({
        "output": str(args.output),
        "execution": result["execution"],
        "selection": result["selection"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
