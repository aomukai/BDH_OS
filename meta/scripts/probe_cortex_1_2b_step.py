#!/usr/bin/env python3
"""Run one non-persistent full Cortex forward/backward/optimizer step."""

from __future__ import annotations

import json

import torch

from cortex.student import build_student
from training.optim import FactoredAdamW


def main() -> int:
    student, _ = build_student(
        None,
        frozen_dtype=torch.bfloat16,
        local_files_only=True,
    )
    partition = student.place(
        ingress_device=torch.device("cuda:0"),
        core_device=torch.device("cuda:1"),
        trainable_dtype=torch.bfloat16,
    )
    parameters = list(student.trainable_parameters())
    optimizer = FactoredAdamW(parameters, lr=1e-3, momentum=True)
    student.train()
    loss = student.response_loss(
        ["The word is cedar."],
        ["Cedar is a word."],
    )
    loss.backward()
    ownership = student.ownership_report()
    optimizer.step()
    report = {
        "schema_version": "ninereeds_cortex_1_2b_step_probe_v1",
        "loss": float(loss.detach().cpu()),
        "optimizer": optimizer.policy(),
        "optimizer_state_bytes": optimizer.state_bytes(),
        "ownership": ownership,
        "partition": partition,
        "peak_vram_bytes": {
            str(index): torch.cuda.max_memory_allocated(index)
            for index in range(torch.cuda.device_count())
        },
    }
    report["pass"] = (
        torch.isfinite(loss).item()
        and ownership["mbert_parameters_with_gradients"] == 0
        and ownership["lfm_parameters_with_gradients"] == 0
        and optimizer.state_bytes() > 0
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
