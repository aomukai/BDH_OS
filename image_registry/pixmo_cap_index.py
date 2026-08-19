"""Download and index PixMo-Cap metadata without downloading image pixels."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sqlite3
from typing import Any
import urllib.parse

from .conceptual_captions_index import download_file, request_json, _fts, _rows


DATASET_ID = "allenai/pixmo-cap"
DATASET_REVISION = "edce6390d9d5be6c8db0d863fbe62718c88988a4"
PARQUET_ENDPOINT = "https://datasets-server.huggingface.co/parquet"


def manifest() -> list[dict[str, Any]]:
    url = PARQUET_ENDPOINT + "?" + urllib.parse.urlencode({"dataset": DATASET_ID})
    payload = request_json(url)
    rows = [
        row for row in payload.get("parquet_files", [])
        if row.get("config") == "default" and row.get("split") == "train"
    ]
    if not rows:
        raise RuntimeError("Hugging Face returned no PixMo-Cap train parquet files")
    return rows


def download(root: Path) -> dict[str, Any]:
    files = manifest()
    for row in files:
        download_file(row["url"], root / row["filename"], int(row["size"]))
    receipt = {
        "schema_version": "ninereeds_pixmo_cap_metadata_download_v1",
        "dataset_id": DATASET_ID,
        "revision": DATASET_REVISION,
        "license": "odc-by-1.0",
        "config": "default",
        "split": "train",
        "files": [
            {"filename": row["filename"], "size": row["size"], "url": row["url"]}
            for row in files
        ],
        "total_bytes": sum(int(row["size"]) for row in files),
        "status": "metadata_download_complete_no_pixels_downloaded",
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "download-receipt.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


def build(root: Path, database: Path) -> dict[str, Any]:
    import pyarrow.parquet as parquet

    receipt = json.loads((root / "download-receipt.json").read_text(encoding="utf-8"))
    temporary = database.with_suffix(database.suffix + ".building")
    if temporary.exists():
        temporary.unlink()
    db = sqlite3.connect(temporary)
    db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE image(
            id INTEGER PRIMARY KEY,
            source_id TEXT NOT NULL UNIQUE,
            image_url TEXT NOT NULL,
            caption TEXT NOT NULL,
            transcripts_json TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE image_search USING fts5(caption);
    """)
    inserted = 0
    for file_record in receipt["files"]:
        parquet_file = parquet.ParquetFile(root / file_record["filename"])
        row_offset = 0
        for batch in parquet_file.iter_batches(
            batch_size=20_000, columns=["image_url", "caption", "transcripts"]
        ):
            columns = batch.to_pydict()
            values = []
            search = []
            for index, url in enumerate(columns["image_url"]):
                caption = str(columns["caption"][index] or "")
                source_id = f"{file_record['filename']}:{row_offset + index}"
                values.append((
                    source_id,
                    str(url),
                    caption,
                    json.dumps(columns["transcripts"][index] or [], ensure_ascii=False),
                ))
            db.executemany(
                "INSERT INTO image(source_id,image_url,caption,transcripts_json) VALUES (?,?,?,?)",
                values,
            )
            first_id = inserted + 1
            search.extend((first_id + index, row[2]) for index, row in enumerate(values))
            db.executemany("INSERT INTO image_search(rowid,caption) VALUES (?,?)", search)
            inserted += len(values)
            row_offset += len(values)
            db.commit()
    db.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", [
        ("schema_version", "ninereeds_pixmo_cap_index_v1"),
        ("dataset_id", DATASET_ID),
        ("revision", DATASET_REVISION),
        ("license", "odc-by-1.0"),
        ("rows", str(inserted)),
    ])
    db.execute("INSERT INTO image_search(image_search) VALUES ('optimize')")
    db.commit()
    db.close()
    temporary.replace(database)
    summary = {
        "schema_version": "ninereeds_pixmo_cap_index_v1",
        "dataset_id": DATASET_ID,
        "revision": DATASET_REVISION,
        "license": "odc-by-1.0",
        "rows": inserted,
        "database": str(database),
        "status": "searchable_metadata_index_complete_no_pixels_downloaded",
    }
    (root / "index-summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def shortlist(
    database: Path,
    registry_db: Path,
    needs_path: Path,
    existing_paths: list[Path],
    output: Path,
    *,
    overfetch_factor: float = 2.0,
    search_multiplier: int = 12,
) -> dict[str, Any]:
    needs = _rows(needs_path)
    existing_candidates = [row for path in existing_paths for row in _rows(path)]
    existing_per_slot: dict[str, int] = {}
    excluded_urls = set()
    for row in existing_candidates:
        existing_per_slot[row["slot_id"]] = existing_per_slot.get(row["slot_id"], 0) + 1
        url = (row.get("source_metadata") or {}).get("original_url")
        if url:
            excluded_urls.add(url)
    registry = sqlite3.connect(f"file:{registry_db.resolve()}?mode=ro", uri=True)
    excluded_urls.update(
        str(row[0]) for row in registry.execute(
            "SELECT original_url FROM asset WHERE original_url IS NOT NULL"
        )
    )
    registry.close()
    index = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    index.row_factory = sqlite3.Row
    by_word: dict[str, list[dict[str, Any]]] = {}
    for row in needs:
        by_word.setdefault(row["word"], []).append(row)
    candidates = []
    unresolved = []
    used_urls = set(excluded_urls)
    target_per_slot = max(1, int(math.ceil(overfetch_factor)))
    for word, slots in by_word.items():
        needed = sum(
            max(0, target_per_slot - existing_per_slot.get(slot["slot_id"], 0))
            for slot in slots
        )
        if not needed:
            continue
        matches = index.execute(
            """SELECT i.*,bm25(image_search,2.0) score
               FROM image_search s JOIN image i ON i.id=s.rowid
               WHERE image_search MATCH ? ORDER BY score,i.id LIMIT ?""",
            (_fts(word), max(needed * search_multiplier, 160)),
        ).fetchall()
        available = [row for row in matches if row["image_url"] not in used_urls]
        cursor = 0
        for slot in slots:
            count = max(0, target_per_slot - existing_per_slot.get(slot["slot_id"], 0))
            for candidate_index in range(count):
                if cursor >= len(available):
                    unresolved.append({
                        **slot, "reason": "insufficient_unused_pixmo_caption_matches"
                    })
                    break
                row = available[cursor]
                cursor += 1
                used_urls.add(row["image_url"])
                candidates.append({
                    **slot,
                    "candidate_rank_for_slot": existing_per_slot.get(slot["slot_id"], 0) + candidate_index + 1,
                    "source": "pixmo_cap",
                    "split": "train",
                    "source_image_id": row["source_id"],
                    "caption": row["caption"],
                    "retrieval_evidence": {
                        "kind": "pixmo_caption_word_match",
                        "matched_caption": row["caption"],
                        "transcripts": json.loads(row["transcripts_json"]),
                        "fts_score": row["score"],
                        "annotation_language": "en",
                    },
                    "source_metadata": {
                        "original_url": row["image_url"],
                        "landing_url": "https://huggingface.co/datasets/allenai/pixmo-cap",
                        "license_url": "https://opendatacommons.org/licenses/by/1-0/",
                        "official_dataset_version": f"PixMo-Cap; HF revision {DATASET_REVISION}",
                    },
                    "status": "metadata_candidate_not_downloaded_or_pixel_verified",
                })
    index.close()
    candidates.sort(key=lambda row: (row["sequence_position"], row["candidate_rank_for_slot"]))
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("candidates", candidates), ("unresolved", unresolved)):
        (output / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    summary = {
        "schema_version": "ninereeds_pixmo_cap_shortlist_v1",
        "residual_slots": len(needs),
        "existing_wave_candidates": len(existing_candidates),
        "metadata_candidates": len(candidates),
        "wave_candidate_total": len(existing_candidates) + len(candidates),
        "wave_target": math.ceil(len(needs) * overfetch_factor),
        "overfetch_factor": overfetch_factor,
        "matched_words": len({row["word"] for row in candidates}),
        "unresolved_candidate_positions": len(unresolved),
        "status": "metadata_only_requires_download_and_pixel_verification",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--root", type=Path, required=True)
    prepare.add_argument("--database", type=Path, required=True)
    short = sub.add_parser("shortlist")
    short.add_argument("--database", type=Path, required=True)
    short.add_argument("--registry-db", type=Path, required=True)
    short.add_argument("--needs", type=Path, required=True)
    short.add_argument("--existing-candidates", type=Path, action="append", default=[])
    short.add_argument("--output", type=Path, required=True)
    short.add_argument("--overfetch-factor", type=float, default=2.0)
    args = parser.parse_args()
    if args.command == "prepare":
        receipt = download(args.root)
        result = build(args.root, args.database)
        result["download"] = receipt
    else:
        result = shortlist(
            args.database,
            args.registry_db,
            args.needs,
            args.existing_candidates,
            args.output,
            overfetch_factor=args.overfetch_factor,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
