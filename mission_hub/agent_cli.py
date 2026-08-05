"""Restricted stdin/stdout boundary for a deployed trainbox agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import site
import sys

from .agent import TrainboxAgent
from .config import load_config_bundle
from .errors import MissionHubError, SafetyError
from .artifacts import ArtifactFiles
from .jsonutil import canonical_json, content_hash
from .release import verify_release


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--machine-id", required=True)
    parser.add_argument("--deployment-manifest", required=True)
    parser.add_argument("command", choices=["ping", "execute", "artifact-put", "artifact-get"])
    parser.add_argument("artifact_arguments", nargs="*")
    args = parser.parse_args()
    try:
        bundle = load_config_bundle(args.config)
        deployment = json.loads(Path(args.deployment_manifest).read_text(encoding="utf-8"))
        deployment.setdefault("release_root", str(Path(args.deployment_manifest).resolve().parent))
        verification = verify_release(deployment, deployment["release_root"])
        for site_path in deployment.get("environment", {}).get("python_site_paths", []):
            site.addsitedir(site_path)
        if args.command == "ping":
            print(canonical_json({"ok": True, "machine_id": args.machine_id, "deployment_id": deployment.get("id"), "config_sha256": bundle.sha256, **verification}))
            return 0
        if args.command in {"artifact-put", "artifact-get"}:
            expected_arguments = 6 if args.command == "artifact-put" else 7
            if len(args.artifact_arguments) != expected_arguments:
                raise MissionHubError(f"{args.command} requires exactly {expected_arguments} arguments")
            artifact_id, kind, digest, size_text, config_sha256, deployment_id, *remainder = args.artifact_arguments
            if config_sha256 != bundle.sha256 or deployment_id != deployment.get("id"):
                raise MissionHubError("artifact command configuration or deployment mismatch")
            expected_id = f"art-{content_hash({'kind': kind, 'sha256': digest})[:16]}"
            if artifact_id != expected_id:
                raise MissionHubError("artifact command identity mismatch")
            byte_size = int(size_text)
            files = ArtifactFiles(bundle, args.machine_id)
            if args.command == "artifact-put":
                path = files.receive(sys.stdin.buffer, sha256=digest, byte_size=byte_size)
                print(canonical_json({
                    "ok": True, "artifact_id": artifact_id, "kind": kind,
                    "sha256": digest, "byte_size": byte_size, "uri": str(path),
                    "config_sha256": bundle.sha256, "deployment_id": deployment.get("id"),
                }))
                return 0
            path = files.verified_source(remainder[0], sha256=digest, byte_size=byte_size)
            with path.open("rb") as handle:
                shutil.copyfileobj(handle, sys.stdout.buffer, length=files.chunk_bytes)
            return 0
        limit = bundle.base["protocol"]["max_envelope_bytes"]
        raw = sys.stdin.buffer.read(limit + 1)
        if len(raw) > limit:
            raise MissionHubError("request exceeds configured envelope limit")
        envelope = json.loads(raw)
        result = TrainboxAgent(bundle, machine_id=args.machine_id, deployment=deployment).execute(envelope)
        print(canonical_json(result))
        return 0
    except Exception as exc:
        target = sys.stderr if getattr(args, "command", None) == "artifact-get" else sys.stdout
        if isinstance(exc, SafetyError):
            failure_class, failure_code = "safety_policy", "safety_policy_refused"
        elif isinstance(exc, OSError):
            failure_class, failure_code = "operational_transient", "resource_temporarily_unavailable"
        elif isinstance(exc, (MissionHubError, ValueError, json.JSONDecodeError)):
            failure_class, failure_code = "deterministic_specification", "job_spec_invalid"
        else:
            failure_class, failure_code = "deterministic_specification", "unexpected_internal_error"
        print(canonical_json({
            "ok": False, "error": type(exc).__name__, "message": str(exc),
            "failure_class": failure_class, "failure_code": failure_code,
        }), file=target)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
