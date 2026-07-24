from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .msm_trainer import MsmTrainer, TrainerError


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute one deterministic MSM trainer session.")
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise TrainerError("trainer request must be an object")
        if set(request) not in (
            {"script", "mode", "checkpoint_path", "inference"},
            {"script", "mode", "checkpoint_path", "inference", "shadow_transcript"},
        ):
            raise TrainerError("trainer request fields do not match the v1 contract")
        result, artifact_hashes = MsmTrainer(repo_root=args.repo).run(**request)
    except (OSError, json.JSONDecodeError, TrainerError, RuntimeError) as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 2
    print(
        json.dumps(
            {"ok": True, "result": result, "artifact_hashes": artifact_hashes},
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
