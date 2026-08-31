#!/usr/bin/env python3
"""Create the deterministic scratch checkpoint for Campaign 36B."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path

import torch

from amorphous.config import CellSubstrateConfig, GrowthPolicyConfig
from amorphous.student import (
    AMORPHOUS_CORTEX_ARCHITECTURE,
    build_amorphous_student,
    save_amorphous_cortex_checkpoint,
)
from cortex.siglip2 import (
    BoundedVisualResampler,
    Siglip2ProjectorConfig,
    VISUAL_PROJECTOR_SCHEMA,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=36002)
    parser.add_argument("--seed-cells", type=int, default=256)
    parser.add_argument("--cell-rank", type=int, default=16)
    parser.add_argument("--birth-cohort-size", type=int, default=4)
    parser.add_argument("--propagation-steps", type=int, default=2)
    parser.add_argument("--max-cells", type=int, default=65_536)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    if args.output.exists() or args.receipt.exists():
        raise FileExistsError("initialization outputs must not already exist")
    torch.manual_seed(args.seed)
    substrate_config = CellSubstrateConfig(
        rank=args.cell_rank,
        seed_cells=args.seed_cells,
        birth_cohort_size=args.birth_cohort_size,
        propagation_steps=args.propagation_steps,
        initialization_seed=args.seed,
        max_cells=args.max_cells,
    )
    growth_config = GrowthPolicyConfig()
    student, growth_controller, optimizer_state = build_amorphous_student(
        None,
        substrate_config=substrate_config,
        growth_config=growth_config,
        frozen_dtype=torch.bfloat16,
        local_files_only=args.local_files_only,
    )
    assert optimizer_state is None
    visual_config = Siglip2ProjectorConfig(cortex_width=substrate_config.width)
    visual_resampler = BoundedVisualResampler(visual_config)
    metadata = {
        "schema_version": "ninereeds_amorphous_initialization_v1",
        "campaign_track": "36B",
        "architecture": AMORPHOUS_CORTEX_ARCHITECTURE,
        "seed": args.seed,
        "substrate_config": dataclasses.asdict(substrate_config),
        "growth_config": dataclasses.asdict(growth_config),
        "anatomy": student.substrate.anatomy(),
        "training_events_consumed": 0,
        "bootstrap_manifest_sha256": (
            "e1d760e264717d05676076429a2e13e46cd05da6d8376169feaad579121ac2fb"
        ),
    }
    save_amorphous_cortex_checkpoint(
        args.output,
        student,
        growth_controller=growth_controller,
        parent="scratch",
        metadata=metadata,
        visual_state={
            "schema_version": VISUAL_PROJECTOR_SCHEMA,
            "config": dataclasses.asdict(visual_config),
            "resampler_state": visual_resampler.state_dict(),
        },
    )
    receipt = {
        **metadata,
        "checkpoint": str(args.output.resolve()),
        "checkpoint_sha256": sha256(args.output),
        "checkpoint_bytes": args.output.stat().st_size,
        "frozen_organs_embedded": False,
        "status": "initialized_not_trained",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
