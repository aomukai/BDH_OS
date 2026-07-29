#!/usr/bin/env python3
"""Download and record the pinned local visual-toolchain checkpoints."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download
from huggingface_hub.errors import GatedRepoError

from vision.model_registry import DEFAULT_VISUAL_MODELS, VISUAL_MODELS


def selected_models(model: str, include_9b: bool) -> tuple[str, ...]:
    if model != "all":
        return (model,)
    names = list(DEFAULT_VISUAL_MODELS)
    if include_9b:
        names.append("flux9b")
    return tuple(names)


def estimated_download_bytes(name: str) -> int:
    """Estimate retained bytes without downloading checkpoint data."""
    model = VISUAL_MODELS[name]
    info = HfApi().model_info(
        model.repo_id,
        revision=model.revision,
        files_metadata=True,
    )
    ignored_names = {
        pattern
        for pattern in model.ignore_patterns
        if "*" not in pattern and "?" not in pattern
    }
    return sum(
        sibling.size or 0
        for sibling in info.siblings
        if sibling.rfilename not in ignored_names
        and not (
            sibling.rfilename.endswith((".jpg", ".png"))
            and any(pattern in {"*.jpg", "*.png"} for pattern in model.ignore_patterns)
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["all", *VISUAL_MODELS], default="all")
    parser.add_argument(
        "--include-9b",
        action="store_true",
        help="also fetch gated FLUX 9B when --model=all",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(
            os.environ.get(
                "NINEREEDS_VISUAL_MODEL_CACHE",
                Path.home() / ".cache" / "huggingface",
            )
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("tmp/vision/model_manifest.json"),
    )
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    names = selected_models(args.model, args.include_9b)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(args.cache_dir).free

    estimates: dict[str, int | None] = {}
    for name in names:
        if args.local_files_only:
            estimates[name] = 0
            continue
        try:
            estimates[name] = estimated_download_bytes(name)
        except GatedRepoError:
            estimates[name] = None

    known_required = sum(value for value in estimates.values() if value is not None)
    if known_required > free_bytes:
        raise RuntimeError(
            f"known downloads require {known_required / 2**30:.1f} GiB but only "
            f"{free_bytes / 2**30:.1f} GiB is free in {args.cache_dir}"
        )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "cache_dir": str(args.cache_dir),
                    "free_gib": round(free_bytes / 2**30, 2),
                    "models": {
                        name: {
                            "repo_id": VISUAL_MODELS[name].repo_id,
                            "revision": VISUAL_MODELS[name].revision,
                            "estimated_gib": (
                                round(estimates[name] / 2**30, 2)
                                if estimates[name] is not None
                                else None
                            ),
                            "gated": VISUAL_MODELS[name].gated,
                        }
                        for name in names
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    resolved: dict[str, dict[str, str | bool]] = {}
    for name in names:
        model = VISUAL_MODELS[name]
        try:
            path = snapshot_download(
                repo_id=model.repo_id,
                revision=model.revision,
                cache_dir=str(args.cache_dir),
                local_files_only=args.local_files_only,
                ignore_patterns=list(model.ignore_patterns),
            )
        except GatedRepoError as exc:
            raise RuntimeError(
                f"{model.repo_id} is gated. Accept its license in a browser and "
                "authenticate this machine with `hf auth login`, then retry."
            ) from exc
        resolved[name] = {
            "repo_id": model.repo_id,
            "revision": model.revision,
            "snapshot_path": path,
            "role": model.role,
            "gated": model.gated,
        }

    previous_models: dict[str, dict[str, str | bool]] = {}
    if args.manifest.is_file():
        previous = json.loads(args.manifest.read_text(encoding="utf-8"))
        if previous.get("schema") == "ninereeds_visual_model_manifest_v1":
            previous_models = previous.get("models", {})
    previous_models.update(resolved)
    manifest = {
        "schema": "ninereeds_visual_model_manifest_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cache_dir": str(args.cache_dir.resolve()),
        "models": previous_models,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
