"""Immutable corpus construction and checkpoint byte certification contracts."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from ..artifacts import sha256_file
from ..errors import SafetyError
from ..jsonutil import canonical_json, content_hash


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _object_file(state_root: str, payload: bytes) -> tuple[Path, str, int]:
    digest = hashlib.sha256(payload).hexdigest()
    destination = Path(state_root).resolve() / "artifacts" / "objects" / digest[:2] / digest
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.stat().st_size != len(payload) or sha256_file(destination) != digest:
            raise SafetyError("existing content-addressed object does not match its name")
        return destination, digest, len(payload)
    descriptor, name = tempfile.mkstemp(prefix=".contract-", dir=destination.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o440)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination, digest, len(payload)


def _declaration(kind: str, path: Path, digest: str, size: int, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind, "sha256": digest, "byte_size": size, "uri": str(path),
        "lifecycle": "candidate", "manifest": manifest,
    }


class CorpusBuildHandler:
    """Build deterministic one-document-per-source JSONL from the editable library."""

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        limits = context["contract_limits"]
        library = Path(limits["training_library_root"]).resolve()
        requested = payload["source_paths"]
        if len(requested) > limits["corpus_max_source_files"]:
            raise SafetyError("corpus request exceeds the configured file-count bound")
        records: list[bytes] = []
        sources: list[dict[str, Any]] = []
        total = 0
        for relative in sorted(requested):
            relative_path = Path(relative)
            if relative_path.is_absolute() or ".." in relative_path.parts or "\\" in relative:
                raise SafetyError(f"corpus source must be a clean relative path: {relative}")
            candidate = library / relative_path
            path = candidate.resolve()
            if library not in path.parents or not path.is_file() or candidate.is_symlink():
                raise SafetyError(f"corpus source is unavailable or outside the training library: {relative}")
            raw = path.read_bytes()
            total += len(raw)
            if total > limits["corpus_max_source_bytes"]:
                raise SafetyError("corpus request exceeds the configured source-byte bound")
            try:
                text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
            except UnicodeDecodeError as exc:
                raise SafetyError(f"corpus source is not UTF-8: {relative}") from exc
            source_sha = hashlib.sha256(raw).hexdigest()
            record = {
                "schema_version": "ninereeds_document_v1",
                "id": content_hash({"source_path": relative_path.as_posix(), "source_sha256": source_sha}),
                "source_path": relative_path.as_posix(),
                "source_sha256": source_sha,
                "text": text,
            }
            records.append((canonical_json(record) + "\n").encode("utf-8"))
            sources.append({"path": relative_path.as_posix(), "sha256": source_sha, "byte_size": len(raw)})
        corpus_path, corpus_sha, corpus_bytes = _object_file(context["state_root"], b"".join(records))
        manifest = {
            "schema_version": "ninereeds_corpus_manifest_v1",
            "corpus_name": payload["corpus_name"],
            "normalization": payload["normalization"],
            "record_format": payload["record_format"],
            "source_library": str(library),
            "sources": sources,
            "source_manifest_sha256": content_hash(sources),
            "record_count": len(records),
            "corpus_sha256": corpus_sha,
            "corpus_bytes": corpus_bytes,
        }
        manifest_path, manifest_sha, manifest_bytes = _object_file(
            context["state_root"], (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        compact = {
            "schema_version": "ninereeds_corpus_artifact_v1", "corpus_name": payload["corpus_name"],
            "record_count": len(records), "source_manifest_sha256": manifest["source_manifest_sha256"],
            "manifest_sha256": manifest_sha,
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _declaration("corpus", corpus_path, corpus_sha, corpus_bytes, compact),
                _declaration("corpus_manifest", manifest_path, manifest_sha, manifest_bytes, compact),
            ],
            "metrics": {
                "source_files": len(sources), "source_bytes": total, "records": len(records),
                "corpus_sha256": corpus_sha, "manifest_sha256": manifest_sha,
            },
            "failure": None,
        }


class GeneratedCorpusAssembleHandler:
    """Fan in already-validated one-unit model outputs without another model call."""

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        artifact_ids = payload["input_artifact_ids"]
        unit_ids = payload["unit_ids"]
        if len(artifact_ids) != len(unit_ids):
            raise SafetyError("generated corpus assembly requires one artifact for every unit_id")
        available = {item["id"]: item for item in context["artifacts"]}
        roots = [Path(context["state_root"]).resolve(), *(Path(value).resolve() for value in context["artifact_roots"])]
        records: list[bytes] = []
        sources: list[dict[str, Any]] = []
        total = 0
        for ordinal, (unit_id, artifact_id) in enumerate(zip(unit_ids, artifact_ids, strict=True)):
            artifact = available.get(artifact_id)
            if artifact is None or artifact["kind"] != "generated_material":
                raise SafetyError(f"material unit {unit_id} does not name one generated_material artifact")
            path = Path(artifact["uri"]).resolve()
            if not path.is_file() or not any(path == root or root in path.parents for root in roots):
                raise SafetyError(f"generated material is unavailable or outside configured roots: {artifact_id}")
            raw = path.read_bytes()
            if len(raw) != artifact["byte_size"] or sha256_file(path) != artifact["sha256"]:
                raise SafetyError(f"generated material bytes do not match their declaration: {artifact_id}")
            try:
                material = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SafetyError(f"generated material is not canonical JSON: {artifact_id}") from exc
            record = {
                "schema_version": "ninereeds_generated_material_unit_v1",
                "ordinal": ordinal, "unit_id": unit_id,
                "source_artifact_id": artifact_id,
                "source_sha256": artifact["sha256"], "material": material,
            }
            encoded = (canonical_json(record) + "\n").encode("utf-8")
            records.append(encoded)
            total += len(raw)
            sources.append({
                "ordinal": ordinal, "unit_id": unit_id, "artifact_id": artifact_id,
                "sha256": artifact["sha256"], "byte_size": artifact["byte_size"],
            })
        corpus_path, corpus_sha, corpus_bytes = _object_file(context["state_root"], b"".join(records))
        manifest = {
            "schema_version": "ninereeds_generated_material_corpus_manifest_v1",
            "corpus_name": payload["corpus_name"], "record_count": len(records),
            "order_policy": "declared_unit_order", "sources": sources,
            "source_manifest_sha256": content_hash(sources),
            "corpus_sha256": corpus_sha, "corpus_bytes": corpus_bytes,
        }
        manifest_path, manifest_sha, manifest_bytes = _object_file(
            context["state_root"],
            (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
        compact = {
            "schema_version": "ninereeds_generated_material_corpus_v1",
            "corpus_name": payload["corpus_name"], "record_count": len(records),
            "source_manifest_sha256": manifest["source_manifest_sha256"],
            "manifest_sha256": manifest_sha,
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _declaration("corpus", corpus_path, corpus_sha, corpus_bytes, compact),
                _declaration("corpus_manifest", manifest_path, manifest_sha, manifest_bytes, compact),
            ],
            "metrics": {
                "source_files": len(sources), "source_bytes": total, "records": len(records),
                "corpus_sha256": corpus_sha, "manifest_sha256": manifest_sha,
            },
            "failure": None,
        }


class CheckpointCertifyHandler:
    """Certify immutable checkpoint bytes without deserializing untrusted pickle."""

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        limits = context["contract_limits"]
        candidate = Path(payload["checkpoint_path"])
        path = candidate.resolve()
        roots = [Path(value).resolve() for value in limits["checkpoint_roots"]]
        if not path.is_file() or candidate.is_symlink() or not any(root in path.parents for root in roots):
            raise SafetyError("checkpoint is unavailable or outside the certified checkpoint roots")
        size = path.stat().st_size
        if size < 1 or size > limits["checkpoint_max_bytes"]:
            raise SafetyError("checkpoint exceeds the configured certification bound")
        digest = sha256_file(path)
        manifest = {
            "schema_version": "ninereeds_checkpoint_manifest_v1",
            "certified_at": _now(),
            "certification_scope": "byte_identity_only",
            "checkpoint_sha256": digest,
            "checkpoint_bytes": size,
            "source_uri": str(path),
            "format_claim": payload["format"],
            "lineage_label": payload["lineage_label"],
            "parent_checkpoint_artifact_id": payload["parent_checkpoint_artifact_id"],
            "deserialized": False,
            "compatibility_certified": False,
        }
        manifest_path, manifest_sha, manifest_bytes = _object_file(
            context["state_root"], (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        compact = {
            "schema_version": "ninereeds_checkpoint_certification_v1",
            "lineage_label": payload["lineage_label"], "manifest_sha256": manifest_sha,
            "certification_scope": "byte_identity_only", "compatibility_certified": False,
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _declaration("checkpoint", path, digest, size, compact),
                _declaration("checkpoint_manifest", manifest_path, manifest_sha, manifest_bytes, compact),
            ],
            "metrics": {"checkpoint_bytes": size, "checkpoint_sha256": digest, "manifest_sha256": manifest_sha},
            "failure": None,
        }
