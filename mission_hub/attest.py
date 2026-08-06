"""Produce a secret-free runtime environment attestation on the target host."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import sys
import site
import subprocess
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _python_runtime(executable: str, required_packages: list[str]) -> dict[str, Any]:
    code = """import hashlib,importlib.metadata,json,pathlib,platform,sys
p=pathlib.Path(sys.executable).resolve(); h=hashlib.sha256(p.read_bytes()).hexdigest()
versions={}
for name in json.loads(sys.argv[1]):
    try: versions[name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: versions[name]=None
print(json.dumps({'python_executable':sys.executable,'python_executable_resolved':str(p),'python_executable_sha256':h,'python_version':platform.python_version(),'packages':versions},sort_keys=True))"""
    completed = subprocess.run(
        [executable, "-c", code, json.dumps(required_packages)], capture_output=True,
        text=True, timeout=30, check=True,
    )
    return json.loads(completed.stdout)


def _model_path(declaration: dict[str, str]) -> dict[str, Any]:
    path = Path(declaration["path"]).resolve()
    marker = path / declaration["marker"]
    if not path.is_dir() or path.name != declaration["revision"]:
        raise ValueError(f"required pinned model is unavailable: {declaration['id']}")
    try:
        marker.relative_to(path)
    except ValueError as exc:
        raise ValueError(f"model marker escapes snapshot: {declaration['id']}") from exc
    if not marker.is_file():
        raise ValueError(f"required model marker is unavailable: {declaration['id']}")
    broken_links = []
    file_count = 0
    byte_size = 0
    for item in path.rglob("*"):
        if item.is_symlink() and not item.exists():
            broken_links.append(item.relative_to(path).as_posix())
        elif item.is_file():
            file_count += 1
            byte_size += item.stat().st_size
    if broken_links:
        raise ValueError(f"required model has broken links: {declaration['id']}")
    return {
        **declaration, "resolved_path": str(path), "marker_sha256": _sha256(marker),
        "file_count": file_count, "byte_size": byte_size, "broken_symlinks": [],
    }


def environment_attestation(
    site_paths: list[str] | None = None,
    auxiliary_python_executables: list[dict[str, Any]] | None = None,
    required_model_paths: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    site_paths = site_paths or []
    for path in site_paths:
        site.addsitedir(path)
    executable = Path(sys.executable).resolve()
    packages = {}
    for name in ("torch", "transformers", "jsonschema", "safetensors"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "schema_version": "ninereeds_environment_attestation_v2",
        "hostname": socket.gethostname(),
        "python_executable": sys.executable,
        "python_executable_resolved": str(executable),
        "python_executable_sha256": _sha256(executable),
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": packages,
        "python_site_paths": site_paths,
        "auxiliary_python_executables": [
            {"id": runtime["id"], **_python_runtime(runtime["path"], runtime["required_packages"])}
            for runtime in (auxiliary_python_executables or [])
        ],
        "required_model_paths": [_model_path(item) for item in (required_model_paths or [])],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-path", action="append", default=[])
    parser.add_argument("--deployment-role-json")
    parser.add_argument("--deployment-role-json-text")
    parser.add_argument("--deployment-role-json-base64")
    args = parser.parse_args()
    if sum(bool(value) for value in (args.deployment_role_json, args.deployment_role_json_text, args.deployment_role_json_base64)) > 1:
        parser.error("choose only one deployment role input")
    if args.deployment_role_json:
        role = json.loads(Path(args.deployment_role_json).read_text())
    elif args.deployment_role_json_text:
        role = json.loads(args.deployment_role_json_text)
    elif args.deployment_role_json_base64:
        role = json.loads(base64.b64decode(args.deployment_role_json_base64, validate=True))
    else:
        role = {}
    declared_site_paths = role.get("python_site_paths", [])
    site_paths = args.site_path or declared_site_paths
    print(json.dumps(environment_attestation(
        site_paths,
        role.get("auxiliary_python_executables", []),
        role.get("required_model_paths", []),
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
