#!/usr/bin/env python3
"""Freeze a bounded first visual pack from words in the foundation corpus."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from training.pipeline.visual.foundation import DEFAULT_CONCEPTS, build_plan, validate_plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", type=Path, default=Path("training/corpus_admin/kernel/kernel_full_words.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pack-id", default="foundation-objects-v1")
    parser.add_argument("--concept", action="append", dest="concepts")
    parser.add_argument("--images-per-concept", type=int, default=4)
    parser.add_argument("--seed", type=int, default=240801)
    args = parser.parse_args()
    plan = build_plan(
        words_path=args.words,
        pack_id=args.pack_id,
        concepts=args.concepts or list(DEFAULT_CONCEPTS),
        images_per_concept=args.images_per_concept,
        seed=args.seed,
    )
    validate_plan(plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent, delete=False) as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output.resolve()), **plan["scope"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
