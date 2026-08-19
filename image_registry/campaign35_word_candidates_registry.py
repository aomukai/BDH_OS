"""Admit word-level metadata candidates to the registry for bounded download/review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .cli import DEFAULT_DB, connect


def _load(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    return rows


def admit(db, candidates: list[dict], selection: str) -> dict:
    unique: dict[tuple[str, str], dict] = {}
    bindings: dict[tuple[str, str], list[dict]] = {}
    for candidate in candidates:
        key = (candidate["source"], str(candidate["source_image_id"]))
        unique.setdefault(key, candidate)
        bindings.setdefault(key, []).append({
            "slot_id": candidate["slot_id"], "word": candidate["word"],
            "ordinal": candidate["ordinal"], "sequence_position": candidate["sequence_position"],
        })
    keys = sorted(unique)
    existing = [
        (row["source"], str(row["source_id"]))
        for row in db.execute(
            """SELECT a.source,a.source_id FROM selection s JOIN asset a ON a.id=s.asset_id
               WHERE s.name=? ORDER BY s.ordinal""", (selection,),
        )
    ]
    if existing:
        if existing != keys:
            raise ValueError(f"immutable selection differs: {selection}")
        return {"selection": selection, "assets": len(existing), "slot_bindings": len(candidates), "created": False}
    for selection_ordinal, key in enumerate(keys):
        candidate = unique[key]
        metadata = candidate["source_metadata"]
        source, source_id = key
        original_url = metadata["original_url"]
        if source == "coco_2017":
            original_url = "https://s3.amazonaws.com/images.cocodataset.org/" + f'{candidate["split"]}/{metadata["file_name"]}'
        db.execute(
            """INSERT INTO asset(
                   source,source_id,split,original_url,landing_url,license_url,
                   width,height,status
               ) VALUES (?,?,?,?,?,?,?,?, 'metadata_only')
               ON CONFLICT(source,source_id) DO UPDATE SET
                   original_url=excluded.original_url,landing_url=excluded.landing_url,
                   license_url=excluded.license_url,
                   width=COALESCE(excluded.width,asset.width),
                   height=COALESCE(excluded.height,asset.height)""",
            (
                source, source_id, candidate["split"], original_url,
                metadata.get("landing_url"), metadata.get("license_url"),
                metadata.get("width"), metadata.get("height"),
            ),
        )
        asset_id = db.execute(
            "SELECT id FROM asset WHERE source=? AND source_id=?", key,
        ).fetchone()[0]
        caption = candidate.get("caption")
        if caption:
            payload = {
                "retrieval_evidence": candidate["retrieval_evidence"],
                "campaign35_slot_bindings": bindings[key],
            }
            db.execute(
                "INSERT INTO text_record(asset_id,kind,text,author,payload_json) VALUES (?,'source_caption',?,'campaign35-word-metadata',?)",
                (asset_id, caption, json.dumps(payload, sort_keys=True)),
            )
            db.execute(
                "INSERT INTO text_search(asset_id,kind,text) VALUES (?,'source_caption',?)",
                (asset_id, caption),
            )
        db.execute(
            "INSERT INTO selection(name,asset_id,stratum,ordinal) VALUES (?,?,'campaign35_word_metadata_candidate',?)",
            (selection, asset_id, selection_ordinal),
        )
    db.commit()
    return {"selection": selection, "assets": len(keys), "slot_bindings": len(candidates), "created": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--candidates", type=Path, action="append", required=True)
    parser.add_argument("--selection", required=True)
    args = parser.parse_args()
    with connect(args.db) as db:
        result = admit(db, _load(args.candidates), args.selection)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
