#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.pipeline.cortex.allowlist_wave import prepare_allowlist_wave


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare the next Ninereeds allowlist wave.")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--first-rank", type=int, default=501)
    parser.add_argument("--last-rank", type=int, default=2000)
    parser.add_argument("--wave-id", default="allowlist-0501-2000-v1")
    args = parser.parse_args()
    result = prepare_allowlist_wave(
        args.repo.resolve(),
        wave_id=args.wave_id,
        first_rank=args.first_rank,
        last_rank=args.last_rank,
    )
    print(json.dumps({key: result[key] for key in ("wave_id", "concept_count", "block_count", "manifest_path")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
