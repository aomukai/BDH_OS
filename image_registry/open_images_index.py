"""Build a compact, annotation-first index for Open Images metadata.

The index deliberately excludes the multi-gigabyte image metadata table. Candidate
discovery works from human object and relationship annotations; URLs and license
fields are hydrated only for the bounded shortlist in a later pass.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator


SCHEMA_VERSION = "ninereeds_open_images_annotation_index_v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _classes(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {row["LabelName"]: row["DisplayName"] for row in csv.DictReader(handle)}


def _groups(rows: Iterable[dict[str, str]]) -> Iterator[tuple[str, list[dict[str, str]]]]:
    image_id: str | None = None
    group: list[dict[str, str]] = []
    for row in rows:
        if image_id is not None and row["ImageID"] != image_id:
            yield image_id, group
            group = []
        image_id = row["ImageID"]
        group.append(row)
    if image_id is not None:
        yield image_id, group


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=60)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA temp_store=MEMORY")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS object_image(
            label TEXT NOT NULL,
            image_id TEXT NOT NULL,
            instances INTEGER NOT NULL,
            clean_instances INTEGER NOT NULL,
            PRIMARY KEY(label, image_id)
        ) WITHOUT ROWID;
        CREATE INDEX IF NOT EXISTS object_image_by_image ON object_image(image_id, label);
        CREATE TABLE IF NOT EXISTS relation(
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            image_id TEXT NOT NULL,
            PRIMARY KEY(subject, predicate, object, image_id)
        ) WITHOUT ROWID;
        CREATE INDEX IF NOT EXISTS relation_by_image ON relation(image_id);
        """
    )
    return db


def build_index(metadata_dir: Path, output_db: Path, *, batch_size: int = 50_000) -> dict[str, Any]:
    classes_path = metadata_dir / "classes_boxable.csv"
    boxes_path = metadata_dir / "boxes.csv"
    relationships_path = metadata_dir / "relationships.csv"
    names = _classes(classes_path)
    db = _connect(output_db)
    db.execute("DELETE FROM object_image")
    db.execute("DELETE FROM relation")
    db.execute("DELETE FROM metadata")

    object_rows = 0
    object_images = 0
    pending: list[tuple[str, str, int, int]] = []
    with boxes_path.open(newline="", encoding="utf-8") as handle:
        for image_id, rows in _groups(csv.DictReader(handle)):
            counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
            for row in rows:
                label = names.get(row["LabelName"], row["LabelName"])
                counts[label][0] += 1
                if not any(int(row[field]) for field in ("IsOccluded", "IsTruncated", "IsGroupOf", "IsDepiction")):
                    counts[label][1] += 1
            pending.extend((label, image_id, count, clean) for label, (count, clean) in counts.items())
            object_images += 1
            if len(pending) >= batch_size:
                db.executemany("INSERT INTO object_image VALUES (?, ?, ?, ?)", pending)
                object_rows += len(pending)
                pending.clear()
                db.commit()
    if pending:
        db.executemany("INSERT INTO object_image VALUES (?, ?, ?, ?)", pending)
        object_rows += len(pending)
        db.commit()

    relation_source_rows = 0
    with relationships_path.open(newline="", encoding="utf-8") as handle:
        pending_relations: list[tuple[str, str, str, str]] = []
        for row in csv.DictReader(handle):
            pending_relations.append((
                names.get(row["LabelName1"], row["LabelName1"]),
                row["RelationshipLabel"].replace("_", " "),
                names.get(row["LabelName2"], row["LabelName2"]),
                row["ImageID"],
            ))
            relation_source_rows += 1
            if len(pending_relations) >= batch_size:
                db.executemany("INSERT OR IGNORE INTO relation VALUES (?, ?, ?, ?)", pending_relations)
                pending_relations.clear()
                db.commit()
        if pending_relations:
            db.executemany("INSERT OR IGNORE INTO relation VALUES (?, ?, ?, ?)", pending_relations)
            db.commit()

    relation_rows = db.execute("SELECT count(*) FROM relation").fetchone()[0]
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "object_image_rows": object_rows,
        "object_images": object_images,
        "relationship_source_rows": relation_source_rows,
        "relationship_rows": relation_rows,
        "inputs": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in (classes_path, boxes_path, relationships_path)
        },
    }
    db.executemany(
        "INSERT INTO metadata(key, value) VALUES (?, ?)",
        ((key, json.dumps(value, sort_keys=True)) for key, value in manifest.items()),
    )
    db.commit()
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    db.close()
    if integrity != "ok":
        raise RuntimeError(f"annotation index integrity check failed: {integrity}")
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
