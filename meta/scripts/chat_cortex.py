#!/usr/bin/env python3
"""Generate one deterministic, checkpoint-pinned Ninereeds chat response."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import torch

from cortex.student import build_student


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--ingress-device", default="cuda:0")
    parser.add_argument("--core-device", default="cuda:1")
    parser.add_argument("--max-new-tokens", type=int, required=True)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_new_tokens <= 4096:
        parser.error("max-new-tokens must be between 1 and 4096")

    prompt = args.prompt.read_text(encoding="utf-8")
    if not prompt or len(prompt.encode("utf-8")) > 256 * 1024:
        parser.error("prompt must contain 1-262144 UTF-8 bytes")
    started = time.time()
    student, parent_kind, _ = build_student(
        args.checkpoint, frozen_dtype=torch.bfloat16,
        local_files_only=args.local_files_only,
    )
    student.place(
        ingress_device=torch.device(args.ingress_device),
        core_device=torch.device(args.core_device),
        trainable_dtype=torch.bfloat16,
    )
    output = student.generate_text([prompt], max_new_tokens=args.max_new_tokens)[0]
    print(json.dumps({
        "schema_version": "ninereeds_checkpoint_chat_v1",
        "response": output,
        "parent_kind": parent_kind,
        "max_new_tokens": args.max_new_tokens,
        "do_sample": False,
        "duration_seconds": round(time.time() - started, 3),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
