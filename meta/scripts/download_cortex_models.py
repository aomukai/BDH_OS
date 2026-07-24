#!/usr/bin/env python3
"""Download and verify the canonical frozen cortex checkpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from huggingface_hub import snapshot_download

MODELS = {
    "mbert": "google-bert/bert-base-multilingual-cased",
    "lfm": "LiquidAI/LFM2.5-230M",
}

# Preserve only native PyTorch/safetensors assets. In particular, mBERT also
# publishes multi-gigabyte TensorFlow, Flax, and legacy PyTorch copies that are
# not needed when the canonical safetensors file is present.
ALLOW_PATTERNS = [
    "*.json",
    "*.jinja",
    "*.md",
    "*.txt",
    "*.safetensors",
    "LICENSE*",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["all", *MODELS], default="all")
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    names = MODELS if args.model == "all" else {args.model: MODELS[args.model]}
    resolved: dict[str, dict[str, str]] = {}
    for name, model_id in names.items():
        path = snapshot_download(
            repo_id=model_id,
            cache_dir=str(args.cache_dir) if args.cache_dir else None,
            local_files_only=args.local_files_only,
            allow_patterns=ALLOW_PATTERNS,
        )
        resolved[name] = {"model_id": model_id, "snapshot_path": path}
    print(json.dumps(resolved, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
