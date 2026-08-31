#!/usr/bin/env python3
"""Run the bounded Campaign 36C Stage-2 sparse-wave experiment."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
from pathlib import Path
from typing import Any

import torch

from campaign36c import (
    WaveLabConfig,
    merge_wave_lab_results,
    run_wave_laboratory,
    write_wave_lab_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify fixed-graph sparse waves, deterministic convergence, bounded "
            "recurrence, and capacity-independent active work."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--rotary-pairs", type=int, default=2)
    parser.add_argument("--sequence-length", type=int, default=16)
    parser.add_argument(
        "--disconnected-cell-counts",
        type=int,
        nargs="+",
        default=[0, 256, 4096],
    )
    parser.add_argument("--benchmark-warmup", type=int, default=5)
    parser.add_argument("--benchmark-iterations", type=int, default=25)
    parser.add_argument("--maximum-material-latency-ratio", type=float, default=3.0)
    parser.add_argument("--maximum-serviceable-p95-ms", type=float, default=5_000.0)
    parser.add_argument("--seed", type=int, default=36_200)
    devices = parser.add_mutually_exclusive_group()
    devices.add_argument("--device")
    devices.add_argument("--devices", nargs="+")
    parser.add_argument(
        "--dtype",
        choices=("float32", "bfloat16"),
        default="float32",
    )
    return parser.parse_args()


def resolve_devices(device: str | None, devices: list[str] | None) -> list[str]:
    requested = devices or ([device] if device is not None else ["auto"])
    if requested != ["auto"]:
        return [str(torch.device(value)) for value in requested]
    if not torch.cuda.is_available():
        return ["cpu"]
    return [f"cuda:{index}" for index in range(torch.cuda.device_count())]


def _run(specification: dict[str, Any]) -> dict[str, Any]:
    return run_wave_laboratory(
        WaveLabConfig(**specification["config"]),
        device=specification["device"],
        dtype=getattr(torch, specification["dtype"]),
    )


def main() -> None:
    args = parse_args()
    devices = resolve_devices(args.device, args.devices)
    if any(torch.device(value).type == "cpu" for value in devices) and args.dtype != "float32":
        raise ValueError("the Stage-2 CPU lab requires float32")
    config = WaveLabConfig(
        width=args.width,
        rotary_pairs=args.rotary_pairs,
        sequence_length=args.sequence_length,
        disconnected_cell_counts=tuple(args.disconnected_cell_counts),
        benchmark_warmup=args.benchmark_warmup,
        benchmark_iterations=args.benchmark_iterations,
        maximum_material_latency_ratio=args.maximum_material_latency_ratio,
        maximum_serviceable_p95_ms=args.maximum_serviceable_p95_ms,
        seed=args.seed,
    )
    config.validate()
    specifications = [
        {"config": config.__dict__, "device": device, "dtype": args.dtype}
        for device in devices
    ]
    if len(specifications) == 1:
        result = _run(specifications[0])
    else:
        context = multiprocessing.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=len(specifications),
            mp_context=context,
        ) as executor:
            reports = list(executor.map(_run, specifications))
        result = merge_wave_lab_results(reports)
    write_wave_lab_result(args.output, result)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "execution": result["execution"],
                "selection": result["selection"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
