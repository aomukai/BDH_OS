"""Admit a bounded Open Images shortlist to the registry without trusting it."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .cli import DEFAULT_DB, connect


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def admit(db: sqlite3.Connection, shortlist: Path, selection: str) -> dict[str, Any]:
    candidates = _rows(shortlist)
    source_ids = [row["source_image_id"] for row in candidates]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("shortlist repeats a source image")
    existing_selection = db.execute(
        "SELECT COUNT(*) FROM selection WHERE name=?", (selection,),
    ).fetchone()[0]
    if existing_selection:
        existing_ids = [
            row[0] for row in db.execute(
                """SELECT a.source_id FROM selection s JOIN asset a ON a.id=s.asset_id
                    WHERE s.name=? ORDER BY s.ordinal""", (selection,),
            )
        ]
        if existing_ids != source_ids:
            raise ValueError(f"immutable selection differs: {selection}")
        return {"selection": selection, "assets": len(source_ids), "created": False}

    for ordinal, candidate in enumerate(candidates):
        metadata = candidate["source_metadata"]
        rotation = metadata.get("rotation", "")
        db.execute(
            """INSERT INTO asset(
                   source,source_id,split,original_url,landing_url,thumbnail_url,
                   license_url,author,title,declared_bytes,declared_md5,rotation,status
               ) VALUES ('open_images_v7',?,?,?,?,?,?,?,?,?,?,?,'metadata_only')
               ON CONFLICT(source,source_id) DO UPDATE SET
                   original_url=excluded.original_url,landing_url=excluded.landing_url,
                   thumbnail_url=excluded.thumbnail_url,license_url=excluded.license_url,
                   author=excluded.author,title=excluded.title,
                   declared_bytes=excluded.declared_bytes,declared_md5=excluded.declared_md5,
                   rotation=excluded.rotation""",
            (
                candidate["source_image_id"], candidate["split"], metadata["original_url"],
                metadata["landing_url"], metadata["thumbnail_url"], metadata["license_url"],
                metadata["author"], metadata["title"], metadata["declared_bytes"],
                metadata["declared_md5"], int(float(rotation)) if rotation else None,
            ),
        )
        asset_id = db.execute(
            "SELECT id FROM asset WHERE source='open_images_v7' AND source_id=?",
            (candidate["source_image_id"],),
        ).fetchone()[0]
        evidence = candidate["retrieval_evidence"]
        annotation = evidence["matched_annotation"]
        if evidence["kind"] == "exact_concept_object_annotation":
            db.execute(
                "INSERT OR IGNORE INTO label VALUES (?, ?, 1, 'open_images_box')",
                (asset_id, annotation["label"]),
            )
        elif evidence["kind"] == "explicit_relationship_annotation":
            db.execute(
                """INSERT INTO relationship(asset_id,subject,predicate,object)
                   SELECT ?,?,?,? WHERE NOT EXISTS(
                       SELECT 1 FROM relationship
                        WHERE asset_id=? AND subject=? AND predicate=? AND object=?)""",
                (
                    asset_id, annotation["subject"], annotation["predicate"], annotation["object"],
                    asset_id, annotation["subject"], annotation["predicate"], annotation["object"],
                ),
            )
        db.execute(
            "INSERT INTO selection(name,asset_id,stratum,ordinal) VALUES (?,?,'external_metadata_candidate',?)",
            (selection, asset_id, ordinal),
        )
    db.commit()
    return {"selection": selection, "assets": len(source_ids), "created": True}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--shortlist", type=Path, required=True)
    parser.add_argument("--selection", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    with connect(args.db) as db:
        result = admit(db, args.shortlist, args.selection)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
