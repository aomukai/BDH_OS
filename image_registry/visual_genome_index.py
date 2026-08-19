"""Build a caption- and relationship-rich SQLite index for Visual Genome."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any, Iterable


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _json_from_zip(path: Path, member: str) -> Any:
    with zipfile.ZipFile(path) as archive, archive.open(member) as raw:
        return json.load(io.TextIOWrapper(raw, encoding="utf-8"))


def _name(value: dict[str, Any]) -> str:
    name = value.get("name")
    if name:
        return str(name).strip().lower()
    names = value.get("names") or []
    return str(names[0]).strip().lower() if names else ""


def build_index(metadata_dir: Path, output_db: Path, *, batch_size: int = 50_000) -> dict[str, Any]:
    image_path = metadata_dir / "image_data.json.zip"
    regions_path = metadata_dir / "region_descriptions.json.zip"
    relationships_path = metadata_dir / "relationships.json.zip"
    output_db.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(output_db, timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA temp_store=MEMORY")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS image(
            image_id INTEGER PRIMARY KEY, url TEXT NOT NULL, width INTEGER NOT NULL,
            height INTEGER NOT NULL, coco_id INTEGER, flickr_id INTEGER
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS region_search USING fts5(
            image_id UNINDEXED, region_id UNINDEXED, phrase,
            tokenize='porter unicode61'
        );
        CREATE TABLE IF NOT EXISTS relationship(
            image_id INTEGER NOT NULL, relationship_id INTEGER NOT NULL,
            subject TEXT NOT NULL, predicate TEXT NOT NULL, object TEXT NOT NULL,
            PRIMARY KEY(image_id, relationship_id)
        ) WITHOUT ROWID;
        CREATE INDEX IF NOT EXISTS relationship_spo
            ON relationship(subject, predicate, object, image_id);
        CREATE INDEX IF NOT EXISTS relationship_image ON relationship(image_id);
        """
    )
    db.executescript("DELETE FROM metadata; DELETE FROM image; DELETE FROM region_search; DELETE FROM relationship;")

    images = _json_from_zip(image_path, "image_data.json")
    db.executemany(
        "INSERT INTO image VALUES (?,?,?,?,?,?)",
        ((row["image_id"], row["url"], row["width"], row["height"], row.get("coco_id"), row.get("flickr_id")) for row in images),
    )
    image_count = len(images)
    del images
    db.commit()

    region_documents = _json_from_zip(regions_path, "region_descriptions.json")
    region_count = 0
    pending: list[tuple[int, int, str]] = []
    for document in region_documents:
        for region in document.get("regions", []):
            phrase = str(region.get("phrase", "")).strip()
            if phrase:
                pending.append((int(region["image_id"]), int(region["region_id"]), phrase))
            if len(pending) >= batch_size:
                db.executemany("INSERT INTO region_search VALUES (?,?,?)", pending)
                region_count += len(pending)
                pending.clear()
                db.commit()
    if pending:
        db.executemany("INSERT INTO region_search VALUES (?,?,?)", pending)
        region_count += len(pending)
        db.commit()
    del region_documents

    relationship_documents = _json_from_zip(relationships_path, "relationships.json")
    relationship_count = 0
    pending_relationships: list[tuple[int, int, str, str, str]] = []
    for document in relationship_documents:
        image_id = int(document["image_id"])
        for row in document.get("relationships", []):
            subject, object_ = _name(row.get("subject", {})), _name(row.get("object", {}))
            predicate = str(row.get("predicate", "")).strip().lower()
            if subject and predicate and object_:
                pending_relationships.append((
                    image_id, int(row["relationship_id"]), subject, predicate, object_,
                ))
            if len(pending_relationships) >= batch_size:
                db.executemany("INSERT OR IGNORE INTO relationship VALUES (?,?,?,?,?)", pending_relationships)
                relationship_count += len(pending_relationships)
                pending_relationships.clear()
                db.commit()
    if pending_relationships:
        db.executemany("INSERT OR IGNORE INTO relationship VALUES (?,?,?,?,?)", pending_relationships)
        relationship_count += len(pending_relationships)
        db.commit()
    del relationship_documents

    manifest = {
        "schema_version": "ninereeds_visual_genome_index_v1",
        "images": image_count,
        "region_descriptions": region_count,
        "relationships_ingested": relationship_count,
        "relationships_distinct": db.execute("SELECT count(*) FROM relationship").fetchone()[0],
        "inputs": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in (image_path, regions_path, relationships_path)
        },
    }
    db.executemany(
        "INSERT INTO metadata VALUES (?,?)",
        ((key, json.dumps(value, sort_keys=True)) for key, value in manifest.items()),
    )
    db.commit()
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    db.close()
    if integrity != "ok":
        raise RuntimeError(f"Visual Genome index integrity check failed: {integrity}")
    return manifest


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-dir", type=Path, required=True)
    parser.add_argument("--output-db", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(json.dumps(build_index(args.metadata_dir, args.output_db), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
