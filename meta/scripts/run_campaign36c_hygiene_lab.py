#!/usr/bin/env python3
"""Run the Campaign 36C Stage-7 senescence and hygiene laboratory."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
from pathlib import Path
from typing import Any

import torch

from campaign36c import (
    HygieneLabConfig,
    merge_hygiene_lab_results,
    run_hygiene_laboratory,
    write_hygiene_lab_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify rooted vitality, mark-and-sweep quarantine, same-UID "
            "revival, and authorized storage-pressure purge."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--rotary-pairs", type=int, default=2)
    parser.add_argument("--sequence-length", type=int, default=16)
    parser.add_argument("--page-capacity", type=int, default=2)
    parser.add_argument("--senescence-interval", type=int, default=2)
    parser.add_argument("--minimum-senescence-sweeps", type=int, default=1)
    parser.add_argument("--maximum-revival-candidates", type=int, default=2)
    parser.add_argument("--minimum-revival-similarity", type=float, default=0.80)
    parser.add_argument(
        "--minimum-revival-improvement-fraction", type=float, default=0.05
    )
    parser.add_argument("--maximum-revival-regression", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=36_700)
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
    return run_hygiene_laboratory(
        HygieneLabConfig(**specification["config"]),
        device=specification["device"],
        dtype=getattr(torch, specification["dtype"]),
        scratch_root=specification["scratch_root"],
    )


def main() -> None:
    args = parse_args()
    devices = resolve_devices(args.device, args.devices)
    if any(torch.device(value).type == "cpu" for value in devices) and args.dtype != "float32":
        raise ValueError("the Stage-7 CPU lab requires float32")
    config = HygieneLabConfig(
        width=args.width,
        rotary_pairs=args.rotary_pairs,
        sequence_length=args.sequence_length,
        page_capacity=args.page_capacity,
        senescence_interval=args.senescence_interval,
        minimum_senescence_sweeps=args.minimum_senescence_sweeps,
        maximum_revival_candidates=args.maximum_revival_candidates,
        minimum_revival_similarity=args.minimum_revival_similarity,
        minimum_revival_improvement_fraction=(
            args.minimum_revival_improvement_fraction
        ),
        maximum_revival_regression=args.maximum_revival_regression,
        seed=args.seed,
    )
    config.validate()
    scratch_root = args.scratch_root or args.output.parent / "stage7-scratch"
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
        result = merge_hygiene_lab_results(reports)
    write_hygiene_lab_result(args.output, result)
    print(json.dumps({
        "output": str(args.output),
        "execution": result["execution"],
        "selection": result["selection"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
