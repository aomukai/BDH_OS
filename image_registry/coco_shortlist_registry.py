"""Admit a bounded COCO caption shortlist to the registry without trusting it."""

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
        raise ValueError("shortlist repeats a COCO image")
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
        evidence = candidate["retrieval_evidence"]
        # The vanity COCO image hostname currently presents an invalid TLS
        # certificate. Use the same official public bucket through Amazon's
        # valid path-style HTTPS endpoint. Preserve both source URLs below.
        original_url = (
            "https://s3.amazonaws.com/images.cocodataset.org/"
            f'{candidate["split"]}/{metadata["file_name"]}'
        )
        db.execute(
            """INSERT INTO asset(
                   source,source_id,split,original_url,landing_url,license_url,
                   author,title,width,height,status
               ) VALUES ('coco_2017',?,?,?,?,?,NULL,?,?,?,'metadata_only')
               ON CONFLICT(source,source_id) DO UPDATE SET
                   original_url=excluded.original_url,landing_url=excluded.landing_url,
                   license_url=excluded.license_url,width=excluded.width,height=excluded.height""",
            (
                candidate["source_image_id"], candidate["split"], original_url,
                metadata["landing_url"], metadata.get("license_url"),
                f'COCO caption {evidence["matched_caption_id"]}', metadata["width"],
                metadata["height"],
            ),
        )
        asset_id = db.execute(
            "SELECT id FROM asset WHERE source='coco_2017' AND source_id=?",
            (candidate["source_image_id"],),
        ).fetchone()[0]
        caption = evidence["matched_caption"]
        payload = dict(evidence)
        payload["license_id"] = metadata.get("license_id")
        payload["license_name"] = metadata.get("license_name")
        payload["flickr_url"] = metadata.get("flickr_url")
        payload["official_dataset_url"] = metadata.get("original_url")
        payload["acquisition_url"] = original_url
        db.execute(
            """INSERT INTO text_record(asset_id,kind,text,author,payload_json)
               VALUES (?,'source_caption',?,'coco',?)""",
            (asset_id, caption, json.dumps(payload, sort_keys=True)),
        )
        db.execute(
            "INSERT INTO text_search(asset_id,kind,text) VALUES (?,'source_caption',?)",
            (asset_id, caption),
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
