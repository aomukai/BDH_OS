"""Build a compact caption index from official COCO 2017 annotations."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any, Iterable


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def build_index(archive_path: Path, output_db: Path) -> dict[str, Any]:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(output_db, timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS image(
            image_id INTEGER PRIMARY KEY,file_name TEXT NOT NULL,coco_url TEXT NOT NULL,
            flickr_url TEXT,width INTEGER NOT NULL,height INTEGER NOT NULL,split TEXT NOT NULL,
            license_id INTEGER NOT NULL,license_name TEXT,license_url TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS caption_search USING fts5(
            image_id UNINDEXED,caption_id UNINDEXED,caption,tokenize='porter unicode61'
        );
        """
    )
    db.executescript("DELETE FROM metadata; DELETE FROM image; DELETE FROM caption_search;")
    image_count = caption_count = 0
    with zipfile.ZipFile(archive_path) as archive:
        for split in ("train2017", "val2017"):
            member = f"annotations/captions_{split}.json"
            document = json.loads(archive.read(member))
            licenses = {row["id"]: row for row in document["licenses"]}
            db.executemany(
                "INSERT INTO image VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    (row["id"], row["file_name"], row["coco_url"], row.get("flickr_url"),
                     row["width"], row["height"], split, row["license"],
                     licenses.get(row["license"], {}).get("name"),
                     licenses.get(row["license"], {}).get("url"))
                    for row in document["images"]
                ),
            )
            db.executemany(
                "INSERT INTO caption_search VALUES (?,?,?)",
                ((row["image_id"], row["id"], row["caption"]) for row in document["annotations"]),
            )
            image_count += len(document["images"])
            caption_count += len(document["annotations"])
            db.commit()
    manifest = {
        "schema_version": "ninereeds_coco_caption_index_v1",
        "images": image_count, "captions": caption_count,
        "input": {"bytes": archive_path.stat().st_size, "sha256": _sha(archive_path)},
    }
    db.executemany(
        "INSERT INTO metadata VALUES (?,?)",
        ((key, json.dumps(value, sort_keys=True)) for key, value in manifest.items()),
    )
    db.commit()
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    db.close()
    if integrity != "ok":
        raise RuntimeError(f"COCO index integrity check failed: {integrity}")
    return manifest


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-db", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(json.dumps(build_index(args.archive, args.output_db), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
