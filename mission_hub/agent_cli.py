"""Restricted stdin/stdout boundary for a deployed trainbox agent."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import site
import sys
import threading
import tarfile
import tempfile
from urllib.parse import urlsplit

from .agent import TrainboxAgent
from .config import load_config_bundle
from .errors import ArtifactContractError, MissionHubError, RemoteJobError, SafetyError
from .artifacts import ArtifactFiles, sha256_file
from .jsonutil import canonical_json, content_hash
from .gpu_lock import (
    GPU_JOB_TYPES, GPU_MINIMUM_FREE_MEMORY_MIB, GPU_PREFLIGHT_JOB_TYPES,
    GPU_PREFLIGHT_TIMEOUT_SECONDS, GPU_REQUIRED_DEVICE_INDICES,
    gpu_resource, require_gpu_capacity,
)
from .release import verify_release


def _bounded_failed_run_evidence(bundle, machine_id: str, envelope: object) -> dict | None:
    """Return a bounded in-memory bundle of remote run diagnostics.

    Failure evidence must cross the same authenticated response channel as the
    failure itself.  Relying on a machine-local path leaves Mission Hub and its
    authorized recovery actor unable to inspect the causal log.
    """
    if not isinstance(envelope, dict):
        return None
    run = envelope.get("run")
    if not isinstance(run, dict) or not isinstance(run.get("id"), str):
        return None
    root = (Path(bundle.machines[machine_id]["state_root"]).resolve() / "runs" / run["id"]).resolve()
    state_root = Path(bundle.machines[machine_id]["state_root"]).resolve()
    if state_root not in root.parents or not root.is_dir():
        return None
    maximum = min(int(bundle.base["protocol"]["max_envelope_bytes"]) // 2, 1024 * 1024)
    files = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in {".json", ".log", ".txt"}:
            continue
        resolved = path.resolve()
        if root not in resolved.parents:
            continue
        data = resolved.read_bytes()
        if total + len(data) > maximum:
            continue
        files.append({
            "path": str(resolved.relative_to(root)),
            "sha256": hashlib.sha256(data).hexdigest(),
            "byte_size": len(data),
            "content_base64": base64.b64encode(data).decode("ascii"),
        })
        total += len(data)
        if len(files) >= 32:
            break
    if not files:
        return None
    payload = canonical_json({
        "schema_version": "ninereeds_failed_run_evidence_v1",
        "machine_id": machine_id,
        "job_id": envelope.get("job", {}).get("id"),
        "run_id": run["id"],
        "files": files,
    }).encode("utf-8")
    return {
        "kind": "failed_output_evidence",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_size": len(payload),
        "payload_base64": base64.b64encode(payload).decode("ascii"),
        "manifest": {
            "schema_version": "ninereeds_failed_run_evidence_v1",
            "machine_id": machine_id,
            "job_id": envelope.get("job", {}).get("id"),
            "run_id": run["id"],
            "file_count": len(files),
        },
    }


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
    parser.add_argument("command", choices=["ping", "execute", "artifact-put", "artifact-get", "artifact-delete", "build-inventory", "release-install", "release-activate", "vision-api", "vision-api-cleanup", "vision-token-set"])
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
        if args.command == "vision-token-set":
            if args.artifact_arguments:
                raise MissionHubError("vision-token-set accepts its token only on stdin")
            token = sys.stdin.read(129).strip()
            if len(token) != 64 or any(character not in "0123456789abcdef" for character in token):
                raise SafetyError("vision API token must be exactly 64 lowercase hexadecimal characters")
            state_root = Path(bundle.machines[args.machine_id]["state_root"])
            state_root.mkdir(parents=True, exist_ok=True)
            token_path = state_root / "vision-api.token"
            temporary = token_path.with_name(f".{token_path.name}.{os.getpid()}")
            temporary.write_text(token + "\n", encoding="utf-8")
            temporary.chmod(0o600)
            os.replace(temporary, token_path)
            print(canonical_json({"ok": True, "token_installed": True, "path": str(token_path)}))
            return 0
        if args.command == "vision-api-cleanup":
            if args.artifact_arguments:
                raise MissionHubError("vision-api-cleanup accepts no arguments")
            stopped = 0
            for candidate in Path("/proc").iterdir():
                if not candidate.name.isdigit() or int(candidate.name) == os.getpid():
                    continue
                try:
                    command = (candidate / "cmdline").read_bytes().replace(b"\0", b" ")
                    owner = (candidate / "status").read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if b"meta.scripts.vision_api" not in command or f"Uid:\t{os.getuid()}\t" not in owner:
                    continue
                os.kill(int(candidate.name), signal.SIGTERM)
                stopped += 1
            print(canonical_json({"ok": True, "stopped": stopped}))
            return 0
        if args.command == "vision-api":
            if args.artifact_arguments:
                raise MissionHubError("vision-api accepts no arguments")
            provider = bundle.providers["trainbox-vision-api"]
            endpoint = urlsplit(provider["endpoint"])
            if endpoint.scheme != "http" or not endpoint.hostname or not endpoint.port:
                raise SafetyError("trainbox vision API endpoint must declare an explicit private HTTP host and port")
            auxiliary = {
                item["id"]: item for item in deployment.get("environment", {}).get("auxiliary_python_executables", [])
            }
            executable = auxiliary.get("vision", {}).get("python_executable")
            if not executable:
                raise SafetyError("the deployed vision interpreter is not attested")
            token_path = Path(bundle.machines[args.machine_id]["state_root"]) / "vision-api.token"
            release_root = Path(deployment["release_root"])
            os.chdir(release_root)
            os.execv(executable, [
                executable, "-m", "meta.scripts.vision_api", "--config", str(release_root / "config/mission_hub"),
                "--bind", endpoint.hostname, "--port", str(endpoint.port), "--token-file", str(token_path),
                "--ssh-watchdog",
            ])
        if args.command == "release-install":
            if len(args.artifact_arguments) != 5:
                raise MissionHubError("release-install requires exactly 5 arguments")
            release_id, archive_sha, size_text, config_sha, deployment_id = args.artifact_arguments
            if len(config_sha) != 64 or len(archive_sha) != 64:
                raise MissionHubError("release install configuration or archive identity is malformed")
            byte_size = int(size_text)
            if byte_size < 1 or byte_size > bundle.base["artifacts"]["max_transfer_bytes"]:
                raise SafetyError("release archive exceeds configured transfer bounds")
            install_root = Path(bundle.machines[args.machine_id]["release_install_root"]).resolve()
            install_root.mkdir(parents=True, exist_ok=True)
            destination = install_root / release_id
            if destination.exists():
                candidate = json.loads((destination / "RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
                candidate_bundle = load_config_bundle(destination / "config" / "mission_hub")
                if (
                    candidate_bundle.sha256 != config_sha
                    or candidate.get("config_snapshot_id") != f"cfg-{config_sha[:16]}"
                    or candidate.get("id") != deployment_id
                    or verify_release(candidate, destination)["release_id"] != release_id
                ):
                    raise SafetyError("existing release directory has a different identity")
                print(canonical_json({"ok": True, "installed": True, "idempotent": True, "deployment_id": deployment_id, "release_id": release_id, "config_sha256": config_sha, "install_root": str(destination)}))
                return 0
            archive_path: Path | None = None
            extracted: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(prefix=".release-", dir=install_root, delete=False) as temporary:
                    archive_path = Path(temporary.name)
                    digest = hashlib.sha256()
                    remaining = byte_size
                    while remaining:
                        chunk = sys.stdin.buffer.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise MissionHubError("release archive ended before its declared size")
                        temporary.write(chunk)
                        digest.update(chunk)
                        remaining -= len(chunk)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                extracted = Path(tempfile.mkdtemp(prefix=".extract-", dir=install_root))
                if digest.hexdigest() != archive_sha or sys.stdin.buffer.read(1):
                    raise MissionHubError("release archive bytes do not match their declaration")
                with tarfile.open(archive_path, mode="r:gz") as archive:
                    for member in archive.getmembers():
                        relative = Path(member.name)
                        if relative.is_absolute() or ".." in relative.parts or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                            raise SafetyError("release archive contains an unsafe member")
                    archive.extractall(extracted, filter="data")
                candidate = json.loads((extracted / "RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
                candidate.setdefault("release_root", str(extracted))
                candidate_bundle = load_config_bundle(extracted / "config" / "mission_hub")
                candidate_install_root = Path(
                    candidate_bundle.machines[args.machine_id]["release_install_root"]
                ).resolve()
                if (
                    candidate_bundle.sha256 != config_sha
                    or candidate_install_root != install_root
                    or candidate.get("id") != deployment_id
                    or candidate.get("config_snapshot_id") != f"cfg-{config_sha[:16]}"
                ):
                    raise SafetyError("release manifest deployment or configuration identity mismatch")
                if verify_release(candidate, extracted)["release_id"] != release_id:
                    raise SafetyError("release manifest does not match the requested release")
                os.replace(extracted, destination)
            finally:
                if archive_path is not None:
                    archive_path.unlink(missing_ok=True)
                if extracted is not None and extracted.exists():
                    shutil.rmtree(extracted)
            print(canonical_json({"ok": True, "installed": True, "idempotent": False, "deployment_id": deployment_id, "release_id": release_id, "config_sha256": config_sha, "install_root": str(destination)}))
            return 0
        if args.command == "release-activate":
            if len(args.artifact_arguments) != 3:
                raise MissionHubError("release-activate requires exactly 3 arguments")
            deployment_id, release_id, config_sha = args.artifact_arguments
            machine = bundle.machines[args.machine_id]
            destination = Path(machine["release_install_root"]).resolve() / release_id
            candidate = json.loads((destination / "RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
            candidate.setdefault("release_root", str(destination))
            candidate_bundle = load_config_bundle(destination / "config" / "mission_hub")
            candidate_machine = candidate_bundle.machines[args.machine_id]
            if (
                candidate_bundle.sha256 != config_sha
                or candidate.get("config_snapshot_id") != f"cfg-{config_sha[:16]}"
                or Path(candidate_machine["release_install_root"]).resolve() != Path(machine["release_install_root"]).resolve()
                or candidate.get("id") != deployment_id
                or verify_release(candidate, destination)["release_id"] != release_id
            ):
                raise SafetyError("installed release does not match activation request")
            active_link = Path(candidate_machine["active_release_link"])
            active_link.parent.mkdir(parents=True, exist_ok=True)
            if active_link.exists() and not active_link.is_symlink():
                raise SafetyError("active release pointer is not a managed symbolic link")
            temporary_link = active_link.with_name(f".{active_link.name}.{os.getpid()}")
            temporary_link.unlink(missing_ok=True)
            temporary_link.symlink_to(destination)
            os.replace(temporary_link, active_link)
            print(canonical_json({"ok": True, "activated": True, "deployment_id": deployment_id, "release_id": release_id, "config_sha256": config_sha, "active_release": str(destination)}))
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
            job_type = envelope.get("job", {}).get("type") if isinstance(envelope, dict) else None
            if job_type in GPU_JOB_TYPES:
                with gpu_resource(bundle.machines[args.machine_id]["state_root"], wait=True):
                    if job_type in GPU_PREFLIGHT_JOB_TYPES:
                        require_gpu_capacity(
                            GPU_REQUIRED_DEVICE_INDICES,
                            GPU_MINIMUM_FREE_MEMORY_MIB,
                            timeout_seconds=GPU_PREFLIGHT_TIMEOUT_SECONDS,
                        )
                    result = TrainboxAgent(bundle, machine_id=args.machine_id, deployment=deployment).execute(envelope)
            else:
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
        elif isinstance(exc, ArtifactContractError):
            failure_class, failure_code = "deterministic_specification", "artifact_contract_invalid"
        elif isinstance(exc, SafetyError):
            failure_class, failure_code = "safety_policy", "safety_policy_refused"
        elif isinstance(exc, OSError):
            failure_class, failure_code = "operational_transient", "resource_temporarily_unavailable"
        elif isinstance(exc, (MissionHubError, ValueError, json.JSONDecodeError)):
            failure_class, failure_code = "deterministic_specification", "job_spec_invalid"
        else:
            failure_class, failure_code = "deterministic_specification", "unexpected_internal_error"
        response = {
            "ok": False, "error": type(exc).__name__, "message": str(exc),
            "failure_class": failure_class, "failure_code": failure_code,
        }
        try:
            evidence = _bounded_failed_run_evidence(bundle, args.machine_id, locals().get("envelope"))
        except Exception:
            evidence = None
        if evidence is not None:
            response["failure_evidence"] = evidence
        print(canonical_json(response), file=target)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
