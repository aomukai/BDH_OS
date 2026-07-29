#!/usr/bin/env python3
"""Download and verify the canonical frozen cortex checkpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from huggingface_hub import snapshot_download

MODELS = {
    "encoder-230m": {
        "model_id": "LiquidAI/LFM2.5-Encoder-230M",
        "revision": "0b649ad0c684378b03d4d8304f7577a662ab89bc",
    },
    "encoder-350m": {
        "model_id": "LiquidAI/LFM2.5-Encoder-350M",
        "revision": "b886781f7c6f10ca9b7096e21b83e30a073c2f39",
    },
    "lfm": {
        "model_id": "LiquidAI/LFM2.5-230M",
        "revision": None,
    },
}

# Preserve the model configuration, pinned remote implementation, tokenizer,
# license, and canonical safetensors weights.
ALLOW_PATTERNS = [
    "*.py",
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
    for name, model in names.items():
        model_id = model["model_id"]
        revision = model["revision"]
        path = snapshot_download(
            repo_id=model_id,
            revision=revision,
            cache_dir=str(args.cache_dir) if args.cache_dir else None,
            local_files_only=args.local_files_only,
            allow_patterns=ALLOW_PATTERNS,
        )
        resolved[name] = {
            "model_id": model_id,
            "revision": revision or "main",
            "snapshot_path": path,
        }
    print(json.dumps(resolved, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
