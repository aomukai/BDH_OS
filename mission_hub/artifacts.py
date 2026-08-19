"""Content-addressed artifact bytes shared by Mission Hub and the trainbox agent."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from typing import BinaryIO, Any

from .errors import SafetyError


def sha256_file(path: Path, *, chunk_bytes: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_bytes):
            digest.update(chunk)
    return digest.hexdigest()


class ArtifactFiles:
    def __init__(self, bundle: Any, machine_id: str):
        self.bundle = bundle
        self.machine = bundle.machines[machine_id]
        self.root = Path(self.machine["state_root"]).resolve() / "artifacts" / "objects"
        self.chunk_bytes = bundle.base["artifacts"]["transfer_chunk_bytes"]
        self.max_bytes = bundle.base["artifacts"]["max_transfer_bytes"]

    def object_path(self, sha256: str) -> Path:
        self._validate_sha256(sha256)
        return self.root / sha256[:2] / sha256

    def ingest(self, source: Path | str) -> tuple[Path, str, int]:
        source_path = Path(source).resolve()
        self._require_allowed(source_path)
        if not source_path.is_file():
            raise SafetyError(f"artifact source is not a file: {source_path}")
        size = source_path.stat().st_size
        self._require_size(size)
        digest = sha256_file(source_path, chunk_bytes=self.chunk_bytes)
        destination = self.object_path(digest)
        if destination.exists():
            self.verify(destination, digest, size)
            return destination, digest, size
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".ingest-", dir=destination.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            with source_path.open("rb") as handle:
                shutil.copyfileobj(handle, temporary, length=self.chunk_bytes)
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            self.verify(temporary_path, digest, size)
            os.chmod(temporary_path, 0o440)
            os.replace(temporary_path, destination)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        return destination, digest, size

    def receive(self, stream: BinaryIO, *, sha256: str, byte_size: int) -> Path:
        self._validate_sha256(sha256)
        self._require_size(byte_size)
        destination = self.object_path(sha256)
        if destination.exists():
            self.verify(destination, sha256, byte_size)
            digest = hashlib.sha256()
            remaining = byte_size
            while remaining:
                chunk = stream.read(min(self.chunk_bytes, remaining))
                if not chunk:
                    break
                digest.update(chunk)
                remaining -= len(chunk)
            if remaining or stream.read(1) or digest.hexdigest() != sha256:
                raise SafetyError("artifact retransmission does not match the existing object")
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        remaining = byte_size
        with tempfile.NamedTemporaryFile(prefix=".receive-", dir=destination.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            while remaining:
                chunk = stream.read(min(self.chunk_bytes, remaining))
                if not chunk:
                    break
                temporary.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            if remaining or stream.read(1):
                raise SafetyError("artifact transfer size does not match its declaration")
            if digest.hexdigest() != sha256:
                raise SafetyError("artifact transfer content hash mismatch")
            os.chmod(temporary_path, 0o440)
            os.replace(temporary_path, destination)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        return destination

    def verified_source(self, uri: Path | str, *, sha256: str, byte_size: int) -> Path:
        path = Path(uri).resolve()
        self._require_allowed(path)
        self.verify(path, sha256, byte_size)
        return path

    def verify(self, path: Path, sha256: str, byte_size: int) -> None:
        if not path.is_file() or path.stat().st_size != byte_size:
            raise SafetyError(f"artifact bytes do not match declared size: {path}")
        if sha256_file(path, chunk_bytes=self.chunk_bytes) != sha256:
            raise SafetyError(f"artifact bytes do not match declared hash: {path}")

    def _require_allowed(self, path: Path) -> None:
        roots = [Path(self.machine["state_root"]).resolve(), *(Path(value).resolve() for value in self.machine["artifact_roots"])]
        if not any(path == root or root in path.parents for root in roots):
            raise SafetyError(f"artifact path is outside configured roots: {path}")

    def _require_size(self, byte_size: int) -> None:
        if not isinstance(byte_size, int) or isinstance(byte_size, bool) or byte_size < 0 or byte_size > self.max_bytes:
            raise SafetyError(f"artifact size exceeds configured transfer limit: {byte_size}")

    @staticmethod
    def _validate_sha256(value: str) -> None:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise SafetyError("artifact transfer requires a lowercase SHA-256")
