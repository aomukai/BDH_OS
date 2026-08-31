#!/usr/bin/env python3
"""Run the bounded Campaign 36C Stage-3 executed-subgraph learning lab."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
from pathlib import Path
from typing import Any

import torch

from campaign36c import (
    LearningLabConfig,
    merge_learning_lab_results,
    run_learning_laboratory,
    write_learning_lab_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify that useful executed routes learn while inactive tissue, "
            "unknown outcomes, retained knowledge, and rare routes remain bounded."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--rotary-pairs", type=int, default=2)
    parser.add_argument("--sequence-length", type=int, default=16)
    parser.add_argument("--training-examples", type=int, default=12)
    parser.add_argument("--evaluation-examples", type=int, default=6)
    parser.add_argument("--training-steps", type=int, default=64)
    parser.add_argument("--black-swan-steps", type=int, default=32)
    parser.add_argument("--common-replay-steps", type=int, default=16)
    parser.add_argument("--disconnected-cells", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument(
        "--minimum-heldout-improvement-fraction", type=float, default=0.01
    )
    parser.add_argument("--seed", type=int, default=36_300)
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
    return run_learning_laboratory(
        LearningLabConfig(**specification["config"]),
        device=specification["device"],
        dtype=getattr(torch, specification["dtype"]),
    )


def main() -> None:
    args = parse_args()
    devices = resolve_devices(args.device, args.devices)
    if any(torch.device(value).type == "cpu" for value in devices) and args.dtype != "float32":
        raise ValueError("the Stage-3 CPU lab requires float32")
    config = LearningLabConfig(
        width=args.width,
        rotary_pairs=args.rotary_pairs,
        sequence_length=args.sequence_length,
        training_examples=args.training_examples,
        evaluation_examples=args.evaluation_examples,
        training_steps=args.training_steps,
        black_swan_steps=args.black_swan_steps,
        common_replay_steps=args.common_replay_steps,
        disconnected_cells=args.disconnected_cells,
        learning_rate=args.learning_rate,
        minimum_heldout_improvement_fraction=(
            args.minimum_heldout_improvement_fraction
        ),
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
        result = merge_learning_lab_results(reports)
    write_learning_lab_result(args.output, result)
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
