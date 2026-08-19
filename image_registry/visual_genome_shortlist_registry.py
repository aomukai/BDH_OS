"""Admit a bounded Visual Genome shortlist to the registry without trusting it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from .cli import DEFAULT_DB, connect


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def admit(db: Any, shortlist: Path, selection: str) -> dict[str, Any]:
    candidates = _load(shortlist)
    source_ids = [row["source_image_id"] for row in candidates]
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("shortlist repeats a Visual Genome image")
    existing = [
        row[0] for row in db.execute(
            """SELECT a.source_id FROM selection s JOIN asset a ON a.id=s.asset_id
                WHERE s.name=? ORDER BY s.ordinal""", (selection,),
        )
    ]
    if existing:
        if existing != source_ids:
            raise ValueError(f"immutable selection differs: {selection}")
        return {"selection": selection, "assets": len(existing), "created": False}
    for ordinal, candidate in enumerate(candidates):
        metadata = candidate["source_metadata"]
        db.execute(
            """INSERT INTO asset(
                   source,source_id,split,original_url,landing_url,license_url,
                   author,title,width,height,status
               ) VALUES ('visual_genome_v1_2',?,?,?,?,?,NULL,?,?,?,'metadata_only')
               ON CONFLICT(source,source_id) DO UPDATE SET
                   original_url=excluded.original_url,landing_url=excluded.landing_url,
                   license_url=excluded.license_url,width=excluded.width,height=excluded.height""",
            (
                candidate["source_image_id"], candidate["split"], metadata["original_url"],
                metadata["landing_url"], metadata.get("license_url"),
                f'Visual Genome region {candidate["retrieval_evidence"]["matched_region_id"]}',
                metadata["width"], metadata["height"],
            ),
        )
        asset_id = db.execute(
            "SELECT id FROM asset WHERE source='visual_genome_v1_2' AND source_id=?",
            (candidate["source_image_id"],),
        ).fetchone()[0]
        phrase = candidate["retrieval_evidence"]["matched_phrase"]
        db.execute(
            """INSERT INTO text_record(asset_id,kind,text,author,payload_json)
               VALUES (?,'source_region_description',?,'visual_genome',?)""",
            (asset_id, phrase, json.dumps(candidate["retrieval_evidence"], sort_keys=True)),
        )
        db.execute(
            "INSERT INTO text_search(asset_id,kind,text) VALUES (?,'source_region_description',?)",
            (asset_id, phrase),
        )
        db.execute(
            "INSERT INTO selection VALUES (?,?,'external_metadata_candidate',?)",
            (selection, asset_id, ordinal),
        )
    db.commit()
    return {"selection": selection, "assets": len(candidates), "created": True}


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
