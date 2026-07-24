#!/usr/bin/env python3
"""Load a Cortex checkpoint and verify its resumable optimizer state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from cortex.student import build_student
from training.optim import FactoredAdamW


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--ingress-device", default="cuda:0")
    parser.add_argument("--core-device", default="cuda:1")
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    student, parent_kind, optimizer_state = build_student(
        args.checkpoint,
        frozen_dtype=torch.bfloat16,
        local_files_only=args.local_files_only,
    )
    partition = student.place(
        ingress_device=torch.device(args.ingress_device),
        core_device=torch.device(args.core_device),
        trainable_dtype=torch.bfloat16,
    )
    optimizer = FactoredAdamW(student.trainable_parameters(), lr=1e-3)
    if optimizer_state is None:
        raise RuntimeError("checkpoint has no resumable optimizer state")
    optimizer.load_state_dict(optimizer_state)
    floating_dtypes = sorted(
        {
            str(value.dtype)
            for state in optimizer.state.values()
            for value in state.values()
            if isinstance(value, torch.Tensor) and value.is_floating_point()
        }
    )
    if floating_dtypes != ["torch.float32"]:
        raise RuntimeError(f"optimizer state is not uniformly fp32: {floating_dtypes}")
    print(
        json.dumps(
            {
                "checkpoint": str(args.checkpoint),
                "parent_kind": parent_kind,
                "optimizer_policy": optimizer.policy(),
                "optimizer_state_bytes": optimizer.state_bytes(),
                "optimizer_floating_dtypes": floating_dtypes,
                "ownership": student.ownership_report(),
                "partition": partition,
                "allocated_vram_bytes": {
                    str(index): torch.cuda.memory_allocated(index)
                    for index in range(torch.cuda.device_count())
                },
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
