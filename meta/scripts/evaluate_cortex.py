#!/usr/bin/env python3
"""Deterministically evaluate and quarantine one Cortex checkpoint candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from training.pipeline.cortex.evaluation import run_candidate_evaluation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--target-concept")
    parser.add_argument("--ingress-device", default="cuda:0")
    parser.add_argument("--core-device", default="cuda:1")
    parser.add_argument("--max-new-tokens", type=int, default=48)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_candidate_evaluation(
        candidate_checkpoint=args.candidate,
        parent_checkpoint=args.parent,
        suite_path=args.suite,
        campaign_id=args.campaign_id,
        target_concept=args.target_concept,
        ingress_device=args.ingress_device,
        core_device=args.core_device,
        max_new_tokens=args.max_new_tokens,
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
