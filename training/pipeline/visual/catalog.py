from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ASSET_SCHEMA = "ninereeds_visual_asset_v1"
HASH_PATTERN = frozenset("0123456789abcdef")


class CatalogError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AssetCatalog:
    """Content-addressed images with a SQLite index and grep-friendly JSONL export."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.objects = self.root / "objects"
        self.catalog_path = self.root / "catalog.sqlite3"
        self.jsonl_path = self.root / "catalog.jsonl"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.objects.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.catalog_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS assets (
                    asset_sha256 TEXT PRIMARY KEY,
                    family_id TEXT NOT NULL,
                    split TEXT NOT NULL,
                    display_filename TEXT NOT NULL,
                    description TEXT NOT NULL,
                    record_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS asset_revisions (
                    asset_sha256 TEXT NOT NULL,
                    revised_at TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    PRIMARY KEY (asset_sha256, revised_at, record_json)
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS asset_search USING fts5(
                    asset_sha256 UNINDEXED,
                    display_filename,
                    description,
                    search_terms,
                    facts,
                    claims
                );
                """
            )

    def import_bytes(
        self,
        data: bytes,
        record: dict[str, Any],
        *,
        export_jsonl: bool = True,
    ) -> dict[str, Any]:
        digest = hashlib.sha256(data).hexdigest()
        width, height, media_type = self._inspect_image(data)
        value = dict(record)
        value.update(
            {
                "schema_version": ASSET_SCHEMA,
                "asset_sha256": digest,
                "object_path": f"objects/{digest}",
                "byte_size": len(data),
                "width": width,
                "height": height,
                "media_type": media_type,
                "created_at": value.get("created_at") or utc_now(),
            }
        )
        self.validate_record(value)
        object_path = self.objects / digest
        if object_path.exists():
            if hashlib.sha256(object_path.read_bytes()).hexdigest() != digest:
                raise CatalogError(f"object hash mismatch: {object_path}")
        else:
            self._write_bytes_atomic(object_path, data)
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
        search = self._search_columns(value)
        with self._connect() as connection:
            parent = value["lineage"]["parent_sha256"]
            if parent is not None:
                parent_row = connection.execute(
                    "SELECT family_id, split FROM assets WHERE asset_sha256 = ?", (parent,)
                ).fetchone()
                if parent_row is None:
                    raise CatalogError(f"lineage parent is not catalogued: {parent}")
                if parent_row["family_id"] != value["family_id"] or parent_row["split"] != value["split"]:
                    raise CatalogError("derived assets must retain the parent family and split")
            existing = connection.execute(
                "SELECT record_json FROM assets WHERE asset_sha256 = ?", (digest,)
            ).fetchone()
            if existing is not None and existing["record_json"] != encoded:
                raise CatalogError(f"asset already has different metadata: {digest}")
            if existing is None:
                connection.execute(
                    "INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        digest,
                        value["family_id"],
                        value["split"],
                        value["display_filename"],
                        value["description"]["text"],
                        encoded,
                    ),
                )
                connection.execute(
                    "INSERT INTO asset_search VALUES (?, ?, ?, ?, ?, ?)",
                    (digest, *search),
                )
        if export_jsonl:
            self.export_jsonl()
        return value

    def revise_annotations(
        self,
        asset_sha256: str,
        *,
        description: dict[str, Any],
        search_terms: list[str],
        facts: list[dict[str, Any]],
        claims: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Replace annotations while retaining a complete revision trail."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM assets WHERE asset_sha256 = ?", (asset_sha256,)
            ).fetchone()
            if row is None:
                raise CatalogError(f"unknown visual asset: {asset_sha256}")
            previous = json.loads(row["record_json"])
            revised = dict(previous)
            revised.update(
                {
                    "description": description,
                    "search_terms": search_terms,
                    "facts": facts,
                    "claims": claims,
                }
            )
            self.validate_record(revised)
            encoded = json.dumps(revised, ensure_ascii=False, sort_keys=True)
            if encoded == row["record_json"]:
                return revised
            connection.execute(
                "INSERT INTO asset_revisions VALUES (?, ?, ?)",
                (asset_sha256, utc_now(), row["record_json"]),
            )
            connection.execute(
                "UPDATE assets SET description = ?, record_json = ? WHERE asset_sha256 = ?",
                (description["text"], encoded, asset_sha256),
            )
            connection.execute(
                "DELETE FROM asset_search WHERE asset_sha256 = ?", (asset_sha256,)
            )
            connection.execute(
                "INSERT INTO asset_search VALUES (?, ?, ?, ?, ?, ?)",
                (asset_sha256, *self._search_columns(revised)),
            )
        self.export_jsonl()
        return revised

    def records(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT record_json FROM assets ORDER BY asset_sha256"
            ).fetchall()
        return [json.loads(row["record_json"]) for row in rows]

    def search(self, query: str, *, split: str | None = None) -> list[dict[str, Any]]:
        if not query.strip():
            raise CatalogError("search query must not be empty")
        sql = (
            "SELECT a.record_json FROM asset_search s JOIN assets a USING(asset_sha256) "
            "WHERE asset_search MATCH ?"
        )
        parameters: list[str] = [query]
        if split is not None:
            sql += " AND a.split = ?"
            parameters.append(split)
        sql += " ORDER BY bm25(asset_search), a.asset_sha256"
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [json.loads(row["record_json"]) for row in rows]

    def export_jsonl(self) -> Path:
        payload = b"".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8") + b"\n"
            for record in self.records()
        )
        self._write_bytes_atomic(self.jsonl_path, payload)
        return self.jsonl_path

    @staticmethod
    def validate_record(value: dict[str, Any]) -> None:
        required = {
            "schema_version", "asset_sha256", "display_filename", "object_path",
            "media_type", "byte_size", "width", "height", "family_id", "split",
            "description", "search_terms", "facts", "claims", "source", "lineage",
            "created_at",
        }
        if set(value) != required or value.get("schema_version") != ASSET_SCHEMA:
            raise CatalogError("asset record has invalid fields or schema")
        digest = value["asset_sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or set(digest) - HASH_PATTERN:
            raise CatalogError("asset_sha256 must be lowercase SHA-256")
        if value["object_path"] != f"objects/{digest}":
            raise CatalogError("object_path must be derived from asset_sha256")
        if value["split"] not in {"train", "validation", "test", "qualification", "unassigned"}:
            raise CatalogError("invalid asset split")
        if not isinstance(value["description"], dict) or not value["description"].get("text"):
            raise CatalogError("asset requires a non-empty description")
        parent = value["lineage"].get("parent_sha256")
        if parent is not None and (len(parent) != 64 or set(parent) - HASH_PATTERN):
            raise CatalogError("invalid lineage parent_sha256")
        for key in ("display_filename", "family_id", "created_at"):
            if not isinstance(value[key], str) or not value[key]:
                raise CatalogError(f"{key} must be a non-empty string")
        for key in ("search_terms", "facts", "claims"):
            if not isinstance(value[key], list):
                raise CatalogError(f"{key} must be a list")

    @staticmethod
    def _inspect_image(data: bytes) -> tuple[int, int, str]:
        try:
            from PIL import Image
        except ImportError as exc:
            raise CatalogError("Pillow is required to inspect visual assets") from exc
        try:
            with Image.open(io.BytesIO(data)) as image:
                image.verify()
                width, height = image.size
                media_type = Image.MIME.get(image.format or "")
        except (OSError, ValueError) as exc:
            raise CatalogError(f"invalid image: {exc}") from exc
        if not media_type or media_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise CatalogError("unsupported image format")
        return width, height, media_type

    @staticmethod
    def _search_columns(value: dict[str, Any]) -> tuple[str, str, str, str, str]:
        return (
            value["display_filename"],
            value["description"]["text"],
            "\n".join(value["search_terms"]),
            "\n".join(fact["text"] for fact in value["facts"]),
            "\n".join(claim["text"] for claim in value["claims"]),
        )

    @staticmethod
    def _write_bytes_atomic(path: Path, payload: bytes) -> None:
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
