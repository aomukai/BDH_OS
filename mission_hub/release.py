"""Target-side verification of an extracted role release."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .errors import ProtocolError
from .jsonutil import content_hash


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_release(deployment: dict[str, Any], release_root: Path | str) -> dict[str, Any]:
    root = Path(release_root).resolve()
    source = deployment.get("source")
    environment = deployment.get("environment")
    if not isinstance(source, dict) or not isinstance(environment, dict):
        raise ProtocolError("deployment manifest lacks source or environment attestation")
    source_hash = source.get("source_sha256")
    source_body = {key: value for key, value in source.items() if key != "source_sha256"}
    if source_hash != content_hash(source_body) or deployment.get("source_sha256") != source_hash:
        raise ProtocolError("deployment source manifest hash mismatch")
    environment_hash = content_hash(environment)
    if deployment.get("environment_sha256") != environment_hash:
        raise ProtocolError("deployment environment attestation hash mismatch")
    expected_release_id = f"release-{source_hash[:12]}-{environment_hash[:12]}"
    if deployment.get("release_id") != expected_release_id:
        raise ProtocolError("deployment release ID mismatch")
    verified = 0
    for entry in source.get("files", []):
        relative = Path(entry["path"])
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ProtocolError(f"release manifest path escapes root: {relative}") from exc
        if not path.is_file() or path.stat().st_size != entry["byte_size"] or _sha256(path) != entry["sha256"]:
            raise ProtocolError(f"release file verification failed: {relative}")
        verified += 1
    return {"release_id": expected_release_id, "source_sha256": source_hash, "environment_sha256": environment_hash, "verified_files": verified}
