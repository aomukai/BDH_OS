"""Content-addressed preservation and lossless legacy record import."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from .errors import EvidenceError
from .jsonutil import canonical_json, content_hash


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class EvidenceArchive:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.blobs = self.root / "blobs" / "sha256"
        self.manifests = self.root / "manifests"
        self.records = self.root / "records"

    def capture(self, source: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        source_path = Path(source["path"]).expanduser()
        if not source_path.exists():
            if source["required"]:
                raise EvidenceError(f"required evidence source does not exist: {source_path}")
            files: list[Path] = []
        elif source_path.is_file():
            files = [source_path]
        elif source_path.is_dir():
            files = [path for path in sorted(source_path.rglob("*")) if path.is_file() and not path.is_symlink()]
        else:
            raise EvidenceError(f"unsupported evidence source type: {source_path}")

        suffixes = set(source["include_suffixes"])
        excluded = set(source["exclude_names"])
        entries: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        for path in files:
            relative = path.name if source_path.is_file() else path.relative_to(source_path).as_posix()
            if any(part in excluded for part in Path(relative).parts):
                continue
            if suffixes and path.suffix not in suffixes:
                continue
            stat = path.stat()
            if source["hash_content"]:
                sha256 = _file_sha256(path)
                hash_kind = "content_sha256"
            else:
                sha256 = content_hash({"path": relative, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns})
                hash_kind = "metadata_sha256"
            blob_uri = None
            if source["copy_bytes"]:
                blob_path = self._copy_blob(path, sha256)
                blob_uri = blob_path.relative_to(self.root).as_posix()
            entry = {
                "path": relative,
                "byte_size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "mode": stat.st_mode & 0o777,
                "hash_kind": hash_kind,
                "sha256": sha256,
                "blob_uri": blob_uri,
            }
            entries.append(entry)
            if source["import_json"] and path.suffix == ".json" and stat.st_size <= source["max_import_bytes"]:
                record = self._json_record(path, relative, source["source_kind"], sha256)
                if record is not None:
                    records.append(record)

        captured_at = _utc_now()
        manifest_body = {
            "schema_version": "ninereeds_evidence_manifest_v1",
            "source_id": source["id"],
            "machine_id": source["machine_id"],
            "source_kind": source["source_kind"],
            "source_uri": str(source_path),
            "captured_at": captured_at,
            "copy_bytes": source["copy_bytes"],
            "hash_content": source["hash_content"],
            "files": entries,
        }
        manifest_body["snapshot_sha256"] = content_hash(manifest_body)
        self._write_manifest(manifest_body)
        self._write_records(manifest_body["snapshot_sha256"], records)
        return manifest_body, records

    def verify(self, manifest: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        supplied = manifest.get("snapshot_sha256")
        body = {key: value for key, value in manifest.items() if key != "snapshot_sha256"}
        if supplied != content_hash(body):
            errors.append("manifest hash mismatch")
        for entry in manifest.get("files", []):
            blob_uri = entry.get("blob_uri")
            if blob_uri:
                blob = self.root / blob_uri
                if not blob.is_file():
                    errors.append(f"missing blob: {blob}")
                elif _file_sha256(blob) != entry["sha256"]:
                    errors.append(f"blob hash mismatch: {blob}")
        return errors

    def load_capture(self, snapshot_sha256: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        manifest_path = self.manifests / f"{snapshot_sha256}.json"
        records_path = self.records / f"{snapshot_sha256}.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            records = json.loads(records_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EvidenceError(f"cannot load evidence capture {snapshot_sha256}: {exc}") from exc
        if not isinstance(manifest, dict) or not isinstance(records, list):
            raise EvidenceError("evidence capture has invalid manifest or record shape")
        errors = self.verify(manifest)
        if errors:
            raise EvidenceError("; ".join(errors))
        return manifest, records

    def _copy_blob(self, source: Path, sha256: str) -> Path:
        target = self.blobs / sha256[:2] / sha256
        if target.exists():
            if target.stat().st_size != source.stat().st_size:
                raise EvidenceError(f"content-addressed blob size conflict: {target}")
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix="evidence-", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
        try:
            shutil.copyfile(source, temporary)
            if _file_sha256(temporary) != sha256:
                raise EvidenceError(f"evidence copy verification failed: {source}")
            os.chmod(temporary, 0o440)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def _write_manifest(self, manifest: dict[str, Any]) -> Path:
        self.manifests.mkdir(parents=True, exist_ok=True)
        target = self.manifests / f"{manifest['snapshot_sha256']}.json"
        encoded = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        if target.exists():
            if target.read_bytes() != encoded:
                raise EvidenceError(f"manifest collision: {target}")
            return target
        with tempfile.NamedTemporaryFile(prefix="manifest-", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
        try:
            os.chmod(temporary, 0o440)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def _write_records(self, snapshot_sha256: str, records: list[dict[str, Any]]) -> Path:
        self.records.mkdir(parents=True, exist_ok=True)
        target = self.records / f"{snapshot_sha256}.json"
        encoded = (json.dumps(records, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
        if target.exists():
            if target.read_bytes() != encoded:
                raise EvidenceError(f"record export collision: {target}")
            return target
        with tempfile.NamedTemporaryFile(prefix="records-", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
        try:
            os.chmod(temporary, 0o440)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    @staticmethod
    def _json_record(path: Path, relative: str, source_kind: str, sha256: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        parent = Path(relative).parent.name
        record_kind = parent.rstrip("s") if parent in {"plans", "receipts", "reports", "claims"} else source_kind
        if isinstance(payload, dict):
            legacy_id = next(
                (str(payload[key]) for key in ("id", "plan_id", "receipt_id", "report_id", "campaign_id", "schema_version") if payload.get(key)),
                relative,
            )
        else:
            legacy_id = relative
        return {
            "record_kind": record_kind,
            "legacy_id": legacy_id,
            "sha256": sha256,
            "payload": payload,
            "source_path": relative,
        }
