#!/usr/bin/env python3
"""Run the bounded Campaign 36C Stage-1 standalone-cell experiment."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
from pathlib import Path
from typing import Any

import torch

from campaign36c import (
    CellLabConfig,
    CellOptimizerConfig,
    load_latent_task,
    merge_cell_lab_results,
    run_cell_laboratory,
    synthetic_latent_task,
    write_lab_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sweep independent BDH rotary-pair cell cohorts. Without "
            "--latent-bundle the result is mechanical smoke evidence only."
        )
    )
    parser.add_argument("--latent-bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--pair-counts",
        type=int,
        nargs="+",
        default=[1, 2, 4, 8, 16, 32],
    )
    parser.add_argument("--training-steps", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=3e-3)
    parser.add_argument("--benchmark-warmup", type=int, default=3)
    parser.add_argument("--benchmark-iterations", type=int, default=10)
    parser.add_argument("--residual-scale", type=float, default=0.25)
    parser.add_argument("--mechanical-tolerance", type=float)
    parser.add_argument("--minimum-improvement-fraction", type=float, default=0.01)
    parser.add_argument("--seed", type=int, default=36_003)
    devices = parser.add_mutually_exclusive_group()
    devices.add_argument("--device")
    devices.add_argument("--devices", nargs="+")
    parser.add_argument(
        "--dtype",
        choices=("float32", "bfloat16"),
        default="float32",
    )
    parser.add_argument("--synthetic-width", type=int, default=512)
    parser.add_argument("--synthetic-sequence-length", type=int, default=16)
    parser.add_argument("--synthetic-training-examples", type=int, default=16)
    parser.add_argument("--synthetic-evaluation-examples", type=int, default=8)
    parser.add_argument("--synthetic-teacher-pairs", type=int, default=8)
    return parser.parse_args()


def resolve_devices(device: str | None, devices: list[str] | None) -> list[str]:
    requested = devices or ([device] if device is not None else ["auto"])
    if requested != ["auto"]:
        return [str(torch.device(value)) for value in requested]
    if not torch.cuda.is_available():
        return ["cpu"]
    return [f"cuda:{index}" for index in range(torch.cuda.device_count())]


def _run_shard(specification: dict[str, Any]) -> dict[str, Any]:
    dtype = getattr(torch, specification["dtype"])
    latent_bundle = specification["latent_bundle"]
    task = (
        load_latent_task(Path(latent_bundle))
        if latent_bundle is not None
        else synthetic_latent_task(**specification["synthetic"])
    )
    return run_cell_laboratory(
        task,
        config=CellLabConfig(**specification["lab_config"]),
        optimizer_config=CellOptimizerConfig(**specification["optimizer_config"]),
        device=specification["device"],
        dtype=dtype,
    )


def main() -> None:
    args = parse_args()
    devices = resolve_devices(args.device, args.devices)
    dtype = torch.float32 if args.dtype == "float32" else torch.bfloat16
    if any(torch.device(device).type == "cpu" for device in devices) and dtype == torch.bfloat16:
        raise ValueError("the Stage-1 CPU lab requires float32")
    lab_config = CellLabConfig(
        pair_counts=tuple(args.pair_counts),
        training_steps=args.training_steps,
        benchmark_warmup=args.benchmark_warmup,
        benchmark_iterations=args.benchmark_iterations,
        residual_scale=args.residual_scale,
        seed=args.seed,
        mechanical_tolerance=(
            args.mechanical_tolerance
            if args.mechanical_tolerance is not None
            else 0.02
            if dtype == torch.bfloat16
            else 1e-5
        ),
        minimum_improvement_fraction=args.minimum_improvement_fraction,
    )
    optimizer_config = CellOptimizerConfig(learning_rate=args.learning_rate)
    pair_shards = [tuple(args.pair_counts[index::len(devices)]) for index in range(len(devices))]
    specifications = []
    for device, pair_counts in zip(devices, pair_shards, strict=True):
        if not pair_counts:
            continue
        shard_config = CellLabConfig(
            **{
                **lab_config.__dict__,
                "pair_counts": pair_counts,
            }
        )
        specifications.append({
            "device": device,
            "dtype": args.dtype,
            "latent_bundle": (
                None if args.latent_bundle is None else str(args.latent_bundle)
            ),
            "synthetic": {
                "width": args.synthetic_width,
                "sequence_length": args.synthetic_sequence_length,
                "training_examples": args.synthetic_training_examples,
                "evaluation_examples": args.synthetic_evaluation_examples,
                "teacher_pairs": args.synthetic_teacher_pairs,
                "residual_scale": args.residual_scale,
                "seed": args.seed,
            },
            "lab_config": shard_config.__dict__,
            "optimizer_config": optimizer_config.__dict__,
        })
    if len(specifications) == 1:
        result = _run_shard(specifications[0])
    else:
        context = multiprocessing.get_context("spawn")
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=len(specifications),
            mp_context=context,
        ) as executor:
            shards = list(executor.map(_run_shard, specifications))
        result = merge_cell_lab_results(shards, config=lab_config)
    write_lab_result(args.output, result)
    print(json.dumps({
        "output": str(args.output),
        "selection": result["selection"],
        "device": result["execution"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
