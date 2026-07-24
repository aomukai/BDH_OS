#!/usr/bin/env python3
"""Instantiate the complete frozen-cortex 1.2B topology without training."""

from __future__ import annotations

import json

import torch

from cortex.student import build_student


def main() -> int:
    torch.cuda.reset_peak_memory_stats(0)
    torch.cuda.reset_peak_memory_stats(1)
    student, parent_kind = build_student(
        None,
        frozen_dtype=torch.bfloat16,
        local_files_only=True,
    )
    partition = student.place(
        ingress_device=torch.device("cuda:0"),
        core_device=torch.device("cuda:1"),
        trainable_dtype=torch.bfloat16,
    )
    trainable = sum(
        parameter.numel() for parameter in student.parameters() if parameter.requires_grad
    )
    report = {
        "schema_version": "ninereeds_cortex_1_2b_allocation_probe_v1",
        "parent_kind": parent_kind,
        "core_parameters": sum(parameter.numel() for parameter in student.core.parameters()),
        "trainable_parameters": trainable,
        "partition": partition,
        "allocated_vram_bytes": {
            str(index): torch.cuda.memory_allocated(index)
            for index in range(torch.cuda.device_count())
        },
        "peak_vram_bytes": {
            str(index): torch.cuda.max_memory_allocated(index)
            for index in range(torch.cuda.device_count())
        },
    }
    report["pass"] = (
        report["core_parameters"] >= 1_200_000_000
        and partition["layer_devices"][:6] == ["cuda:0"] * 6
        and partition["layer_devices"][6:] == ["cuda:1"] * 6
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
