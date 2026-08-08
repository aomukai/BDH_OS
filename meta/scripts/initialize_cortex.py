#!/usr/bin/env python3
"""Create one deterministic untrained Cortex root checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from cortex.config import CORTEX_ARCHITECTURE
from cortex.student import build_student, save_cortex_checkpoint


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    torch.manual_seed(args.seed)
    student, parent_kind, _ = build_student(
        None, frozen_dtype=torch.bfloat16, local_files_only=args.local_files_only,
    )
    metadata = {
        "schema_version": "ninereeds_neutral_root_v1",
        "architecture": CORTEX_ARCHITECTURE,
        "seed": args.seed,
        "parent_kind": parent_kind,
        "training_events": 0,
        "weight_updates": 0,
        "order_policy": "declared_only",
        "shuffle_allowed": False,
    }
    save_cortex_checkpoint(
        args.output, student, parent="scratch", metadata=metadata,
        optimizer_state=None,
    )
    args.report.write_text(json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
