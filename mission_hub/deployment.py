"""Role-specific, content-addressed deployment manifests."""

from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import gzip
import io
from typing import Any

from .config import ConfigBundle
from .errors import ConfigError, SafetyError
from .jsonutil import content_hash


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, timeout=30, check=True
    )
    return completed.stdout.strip()


class DeploymentBuilder:
    def __init__(self, repo_root: Path | str, bundle: ConfigBundle):
        self.repo_root = Path(repo_root).resolve()
        self.bundle = bundle

    def source_manifest(self, deployment_role_id: str) -> dict[str, Any]:
        try:
            role = self.bundle.deployment_roles[deployment_role_id]
        except KeyError as exc:
            raise ConfigError(f"unknown deployment role: {deployment_role_id}") from exc
        files: list[dict[str, Any]] = []
        seen: set[str] = set()
        for root_name in role["include_roots"]:
            root = (self.repo_root / root_name).resolve()
            try:
                root.relative_to(self.repo_root)
            except ValueError as exc:
                raise ConfigError(f"deployment root escapes repository: {root_name}") from exc
            if not root.exists():
                raise ConfigError(f"deployment include root does not exist: {root_name}")
            candidates = [root] if root.is_file() else sorted(root.rglob("*")) if root.is_dir() else []
            for path in candidates:
                if not path.is_file() or path.is_symlink():
                    continue
                relative = path.relative_to(self.repo_root).as_posix()
                if relative in seen or any(fnmatch.fnmatch(relative, pattern) for pattern in role["exclude_globs"]):
                    continue
                seen.add(relative)
                files.append({"path": relative, "byte_size": path.stat().st_size, "sha256": _sha256_file(path)})
        present = {entry["path"] for entry in files}
        missing = sorted(set(role["required_paths"]) - present)
        if missing:
            raise ConfigError(f"deployment is missing required paths: {', '.join(missing)}")
        git_head = _git(self.repo_root, "rev-parse", "HEAD")
        git_branch = _git(self.repo_root, "branch", "--show-current")
        status = _git(
            self.repo_root,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            *role["include_roots"],
        )
        body = {
            "schema_version": "ninereeds_source_manifest_v1",
            "deployment_role_id": deployment_role_id,
            "role": role["role"],
            "git_head": git_head,
            "git_branch": git_branch,
            "git_status_sha256": hashlib.sha256(status.encode()).hexdigest(),
            "git_clean": not bool(status),
            "config_bundle_sha256": self.bundle.sha256,
            "files": sorted(files, key=lambda item: item["path"]),
        }
        body["source_sha256"] = content_hash(body)
        return body

    def deployment_manifest(
        self,
        deployment_role_id: str,
        *,
        machine_id: str,
        config_snapshot_id: str,
        environment: dict[str, Any],
        allow_dirty_candidate: bool = True,
    ) -> dict[str, Any]:
        source = self.source_manifest(deployment_role_id)
        if not source["git_clean"] and not allow_dirty_candidate:
            raise SafetyError("a dirty source tree cannot become an active deployment")
        machine = self.bundle.machines.get(machine_id)
        if machine is None or machine["role"] != source["role"]:
            raise ConfigError("machine role does not match deployment role")
        role = self.bundle.deployment_roles[deployment_role_id]
        if environment.get("hostname") != machine["hostname"]:
            raise ConfigError("environment attestation hostname does not match target machine")
        if environment.get("python_executable") != role["python_executable"]:
            raise ConfigError("environment attestation interpreter does not match deployment configuration")
        if environment.get("python_site_paths", []) != role["python_site_paths"]:
            raise ConfigError("environment attestation site paths do not match deployment configuration")
        auxiliary = {item.get("id"): item for item in environment.get("auxiliary_python_executables", [])}
        for declared in role["auxiliary_python_executables"]:
            attested = auxiliary.get(declared["id"])
            if not attested or attested.get("python_executable") != declared["path"]:
                raise ConfigError(f"auxiliary Python is not attested: {declared['id']}")
            missing = [name for name in declared["required_packages"] if not attested.get("packages", {}).get(name)]
            if missing:
                raise ConfigError(f"auxiliary Python {declared['id']} lacks packages: {', '.join(missing)}")
        model_paths = {item.get("id"): item for item in environment.get("required_model_paths", [])}
        for declared in role["required_model_paths"]:
            attested = model_paths.get(declared["id"])
            if not attested or any(attested.get(key) != declared[key] for key in ("path", "revision", "marker")):
                raise ConfigError(f"required model path is not attested: {declared['id']}")
            if attested.get("broken_symlinks") or not attested.get("marker_sha256") or attested.get("file_count", 0) < 1:
                raise ConfigError(f"required model snapshot is incomplete: {declared['id']}")
        if "cortex" in machine["capabilities"] and not environment.get("packages", {}).get("torch"):
            raise ConfigError("Cortex deployment environment has no attested Torch package")
        environment_sha = content_hash(environment)
        release_id = f"release-{source['source_sha256'][:12]}-{environment_sha[:12]}"
        return {
            "schema_version": "ninereeds_deployment_manifest_v1",
            "machine_id": machine_id,
            "role": source["role"],
            "release_id": release_id,
            "source_sha256": source["source_sha256"],
            "environment_sha256": environment_sha,
            "config_snapshot_id": config_snapshot_id,
            "source": source,
            "environment": environment,
        }

    def build_archive(self, deployment_manifest: dict[str, Any], output: Path | str) -> dict[str, Any]:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        source = deployment_manifest["source"]
        manifest_bytes = (json.dumps(deployment_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        with output_path.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                    self._add_bytes(archive, "RELEASE-MANIFEST.json", manifest_bytes, mode=0o440)
                    for entry in source["files"]:
                        path = self.repo_root / entry["path"]
                        info = archive.gettarinfo(str(path), arcname=entry["path"])
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        info.mtime = 0
                        info.mode = 0o440 if path.suffix in {".toml", ".json", ".md"} else 0o550 if path.suffix == ".py" else 0o440
                        with path.open("rb") as handle:
                            archive.addfile(info, handle)
        digest = _sha256_file(output_path)
        return {"path": str(output_path), "sha256": digest, "byte_size": output_path.stat().st_size, "release_id": deployment_manifest["release_id"]}

    @staticmethod
    def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes, *, mode: int) -> None:
        info = tarfile.TarInfo(name)
        info.size = len(payload)
        info.mode = mode
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = 0
        archive.addfile(info, io.BytesIO(payload))
