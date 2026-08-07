"""Restricted stdin/stdout boundary for a deployed trainbox agent."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import site
import sys
import threading

from .agent import TrainboxAgent
from .config import load_config_bundle
from .errors import MissionHubError, RemoteJobError, SafetyError
from .artifacts import ArtifactFiles, sha256_file
from .jsonutil import canonical_json, content_hash
from .release import verify_release


def _connection_watchdog(stop: threading.Event, interval_seconds: int) -> None:
    """Keep SSH active and terminate the agent if its result channel vanishes."""
    while not stop.wait(interval_seconds):
        try:
            sys.stdout.write("\n")
            sys.stdout.flush()
        except (BrokenPipeError, OSError):
            os.kill(os.getpid(), signal.SIGTERM)
            return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--machine-id", required=True)
    parser.add_argument("--deployment-manifest", required=True)
    parser.add_argument("command", choices=["ping", "execute", "artifact-put", "artifact-get", "artifact-delete", "build-inventory"])
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
        if args.command == "build-inventory":
            if len(args.artifact_arguments) != 3:
                raise MissionHubError("build-inventory requires exactly 3 arguments")
            config_sha256, deployment_id, scan_mode = args.artifact_arguments
            if scan_mode not in {"threshold", "force"}:
                raise MissionHubError("build inventory scan mode must be threshold or force")
            if config_sha256 != bundle.sha256 or deployment_id != deployment.get("id"):
                raise MissionHubError("build inventory configuration or deployment mismatch")
            roots = [Path(value).resolve(strict=False) for value in bundle.retention["build_roots"]]
            machine = bundle.machines[args.machine_id]
            allowed = [
                Path(machine["state_root"]).resolve(strict=False),
                *(Path(value).resolve(strict=False) for value in machine["artifact_roots"]),
            ]
            if any(not any(root == boundary or boundary in root.parents for boundary in allowed) for root in roots):
                raise SafetyError("retention build root is outside the commissioned artifact boundary")
            usage = shutil.disk_usage(roots[0])
            used_fraction = (usage.total - usage.free) / usage.total
            triggered = scan_mode == "force" or (
                used_fraction >= bundle.retention["proposal_used_fraction"]
                or usage.free < bundle.retention["minimum_free_bytes"]
            )
            files = []
            suffixes = set(bundle.retention["build_file_suffixes"])
            if triggered:
                for root in roots:
                    if not root.is_dir():
                        continue
                    for path in sorted(root.rglob("*")):
                        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in suffixes:
                            continue
                        resolved = path.resolve(strict=True)
                        if not (resolved == root or root in resolved.parents):
                            raise SafetyError("retention inventory escaped its declared build root")
                        files.append({
                            "uri": str(resolved), "sha256": sha256_file(resolved),
                            "byte_size": resolved.stat().st_size,
                        })
            print(canonical_json({
                "ok": True, "machine_id": args.machine_id,
                "config_sha256": bundle.sha256, "deployment_id": deployment.get("id"),
                "triggered": triggered, "used_fraction": used_fraction,
                "free_bytes": usage.free, "total_bytes": usage.total,
                "scan_mode": scan_mode, "build_roots": [str(root) for root in roots], "files": files,
            }))
            return 0
        if args.command in {"artifact-put", "artifact-get", "artifact-delete"}:
            expected_arguments = {"artifact-put": 6, "artifact-get": 7, "artifact-delete": 8}[args.command]
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
            if args.command == "artifact-delete":
                plan_sha256, uri = remainder
                if len(plan_sha256) != 64 or any(character not in "0123456789abcdef" for character in plan_sha256):
                    raise MissionHubError("artifact deletion requires an exact retention-plan SHA-256")
                path = files.verified_source(uri, sha256=digest, byte_size=byte_size)
                path.unlink()
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                print(canonical_json({
                    "ok": True, "artifact_id": artifact_id, "kind": kind,
                    "sha256": digest, "byte_size": byte_size, "uri": str(path),
                    "plan_sha256": plan_sha256, "config_sha256": bundle.sha256,
                    "deployment_id": deployment.get("id"), "deleted": True,
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
        watchdog_stop = threading.Event()
        watchdog = threading.Thread(
            target=_connection_watchdog,
            args=(watchdog_stop, max(1, min(bundle.base["scheduler"]["heartbeat_seconds"], 10))),
            name="mission-hub-connection-watchdog", daemon=True,
        )
        watchdog.start()
        try:
            result = TrainboxAgent(bundle, machine_id=args.machine_id, deployment=deployment).execute(envelope)
        finally:
            watchdog_stop.set()
            watchdog.join(timeout=1)
        print(canonical_json(result))
        return 0
    except Exception as exc:
        target = sys.stderr if getattr(args, "command", None) == "artifact-get" else sys.stdout
        if isinstance(exc, RemoteJobError):
            failure_class, failure_code = exc.failure_class, exc.code
        elif isinstance(exc, SafetyError):
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
