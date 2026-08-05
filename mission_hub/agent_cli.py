"""Restricted stdin/stdout boundary for a deployed trainbox agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .agent import TrainboxAgent
from .config import load_config_bundle
from .errors import MissionHubError
from .jsonutil import canonical_json
from .release import verify_release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--machine-id", required=True)
    parser.add_argument("--deployment-manifest", required=True)
    parser.add_argument("command", choices=["ping", "execute"])
    args = parser.parse_args()
    try:
        bundle = load_config_bundle(args.config)
        deployment = json.loads(Path(args.deployment_manifest).read_text(encoding="utf-8"))
        deployment.setdefault("release_root", str(Path(args.deployment_manifest).resolve().parent))
        verification = verify_release(deployment, deployment["release_root"])
        if args.command == "ping":
            print(canonical_json({"ok": True, "machine_id": args.machine_id, "deployment_id": deployment.get("id"), "config_sha256": bundle.sha256, **verification}))
            return 0
        limit = bundle.base["protocol"]["max_envelope_bytes"]
        raw = sys.stdin.buffer.read(limit + 1)
        if len(raw) > limit:
            raise MissionHubError("request exceeds configured envelope limit")
        envelope = json.loads(raw)
        result = TrainboxAgent(bundle, machine_id=args.machine_id, deployment=deployment).execute(envelope)
        print(canonical_json(result))
        return 0
    except (MissionHubError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(canonical_json({"ok": False, "error": type(exc).__name__, "message": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
