"""Produce a secret-free runtime environment attestation on the target host."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import sys
import site
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def environment_attestation(site_paths: list[str] | None = None) -> dict[str, Any]:
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
        "schema_version": "ninereeds_environment_attestation_v1",
        "hostname": socket.gethostname(),
        "python_executable": sys.executable,
        "python_executable_resolved": str(executable),
        "python_executable_sha256": _sha256(executable),
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": packages,
        "python_site_paths": site_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-path", action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(environment_attestation(args.site_path), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
