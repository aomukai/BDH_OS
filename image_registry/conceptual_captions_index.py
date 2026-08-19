"""Download and index Conceptual Captions labeled metadata without image pixels."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


DATASET_ID = "google-research-datasets/conceptual_captions"
PARQUET_ENDPOINT = "https://datasets-server.huggingface.co/parquet"
USER_AGENT = "Ninereeds-conceptual-captions-index/1.0"


def request_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def labeled_manifest() -> list[dict[str, Any]]:
    url = PARQUET_ENDPOINT + "?" + urllib.parse.urlencode({"dataset": DATASET_ID})
    payload = request_json(url)
    rows = [
        row for row in payload.get("parquet_files", [])
        if row.get("config") == "labeled" and row.get("split") == "train"
    ]
    if not rows:
        raise RuntimeError("Hugging Face returned no labeled Conceptual Captions parquet files")
    return rows


def download_file(url: str, destination: Path, expected_size: int, *, retries: int = 8) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    if destination.is_file() and destination.stat().st_size == expected_size:
        return
    if destination.exists():
        raise ValueError(f"completed file has unexpected size: {destination}")
    for attempt in range(retries):
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {"User-Agent": USER_AGENT}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response:
                if offset and response.status != 206:
                    partial.unlink()
                    offset = 0
                mode = "ab" if offset else "wb"
                with partial.open(mode) as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
            if partial.stat().st_size == expected_size:
                partial.replace(destination)
                return
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            pass
        if attempt + 1 < retries:
            time.sleep(min(2 ** attempt, 30))
    actual = partial.stat().st_size if partial.exists() else 0
    raise RuntimeError(f"metadata download incomplete: {destination.name}: {actual}/{expected_size}")


def download(root: Path) -> dict[str, Any]:
    manifest = labeled_manifest()
    for row in manifest:
        download_file(row["url"], root / row["filename"], int(row["size"]))
    receipt = {
        "schema_version": "ninereeds_conceptual_captions_metadata_download_v1",
        "dataset_id": DATASET_ID, "config": "labeled", "split": "train",
        "files": [{"filename": row["filename"], "size": row["size"], "url": row["url"]} for row in manifest],
        "total_bytes": sum(int(row["size"]) for row in manifest),
        "status": "metadata_download_complete_no_pixels_downloaded",
    }
    (root / "download-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
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
            labels_json TEXT NOT NULL,
            confidence_scores_json TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE image_search USING fts5(caption,labels,content='image',content_rowid='id');
    """)
    inserted = 0
    for file_record in receipt["files"]:
        path = root / file_record["filename"]
        parquet_file = parquet.ParquetFile(path)
        row_offset = 0
        for batch in parquet_file.iter_batches(
            batch_size=20_000,
            columns=["image_url", "caption", "labels", "confidence_scores"],
        ):
            columns = batch.to_pydict()
            values = []
            search = []
            for index, url in enumerate(columns["image_url"]):
                caption = str(columns["caption"][index] or "")
                labels = [str(value) for value in (columns["labels"][index] or [])]
                scores = columns["confidence_scores"][index] or []
                source_id = f"{file_record['filename']}:{row_offset + index}"
                values.append((source_id, str(url), caption, json.dumps(labels), json.dumps(scores)))
            db.executemany(
                "INSERT INTO image(source_id,image_url,caption,labels_json,confidence_scores_json) VALUES (?,?,?,?,?)",
                values,
            )
            first_id = inserted + 1
            for index, values_row in enumerate(values):
                search.append((first_id + index, values_row[2], " ".join(json.loads(values_row[3]))))
            db.executemany("INSERT INTO image_search(rowid,caption,labels) VALUES (?,?,?)", search)
            inserted += len(values)
            row_offset += len(values)
            db.commit()
    db.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", [
        ("schema_version", "ninereeds_conceptual_captions_index_v1"),
        ("dataset_id", DATASET_ID), ("config", "labeled"), ("rows", str(inserted)),
    ])
    db.execute("INSERT INTO image_search(image_search) VALUES ('optimize')")
    db.commit()
    db.close()
    temporary.replace(database)
    summary = {
        "schema_version": "ninereeds_conceptual_captions_index_v1",
        "dataset_id": DATASET_ID, "rows": inserted, "database": str(database),
        "status": "searchable_metadata_index_complete_no_pixels_downloaded",
    }
    (root / "index-summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return summary


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _fts(word: str) -> str:
    terms = re.findall(r"[^\W_]+", word.casefold(), flags=re.UNICODE)
    if not terms:
        raise ValueError(f"cannot search empty word: {word!r}")
    return " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)


def shortlist(
    database: Path, registry_db: Path, needs_path: Path, existing_paths: list[Path],
    output: Path, *, overfetch_factor: float = 2.0, search_multiplier: int = 12,
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
        str(row[0]) for row in registry.execute("SELECT original_url FROM asset WHERE original_url IS NOT NULL")
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
        needed = sum(max(0, target_per_slot - existing_per_slot.get(slot["slot_id"], 0)) for slot in slots)
        if not needed:
            continue
        matches = index.execute(
            """SELECT i.*,bm25(image_search,2.0,1.0) score
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
                    unresolved.append({**slot, "reason": "insufficient_unused_conceptual_caption_matches"})
                    break
                row = available[cursor]
                cursor += 1
                used_urls.add(row["image_url"])
                candidates.append({
                    **slot,
                    "candidate_rank_for_slot": existing_per_slot.get(slot["slot_id"], 0) + candidate_index + 1,
                    "source": "conceptual_captions_labeled", "split": "train",
                    "source_image_id": row["source_id"], "caption": row["caption"],
                    "retrieval_evidence": {
                        "kind": "conceptual_captions_caption_or_label_word_match",
                        "matched_caption": row["caption"], "labels": json.loads(row["labels_json"]),
                        "confidence_scores": json.loads(row["confidence_scores_json"]),
                        "fts_score": row["score"], "annotation_language": "en",
                    },
                    "source_metadata": {
                        "original_url": row["image_url"],
                        "landing_url": "https://huggingface.co/datasets/google-research-datasets/conceptual_captions",
                        "license_url": "https://huggingface.co/datasets/google-research-datasets/conceptual_captions#licensing-information",
                        "official_dataset_version": "Conceptual Captions labeled; HF revision 0bb028f274446e0b102c1253d087a98eeb4519a3",
                    },
                    "status": "metadata_candidate_not_downloaded_or_pixel_verified",
                })
    index.close()
    candidates.sort(key=lambda row: (row["sequence_position"], row["candidate_rank_for_slot"]))
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("candidates", candidates), ("unresolved", unresolved)):
        (output / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8",
        )
    summary = {
        "schema_version": "ninereeds_conceptual_captions_shortlist_v1",
        "residual_slots": len(needs), "existing_wave_candidates": len(existing_candidates),
        "metadata_candidates": len(candidates),
        "wave_candidate_total": len(existing_candidates) + len(candidates),
        "wave_target": math.ceil(len(needs) * overfetch_factor),
        "overfetch_factor": overfetch_factor,
        "matched_words": len({row["word"] for row in candidates}),
        "unresolved_candidate_positions": len(unresolved),
        "status": "metadata_only_requires_download_and_pixel_verification",
    }
    (output / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
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
            args.database, args.registry_db, args.needs, args.existing_candidates,
            args.output, overfetch_factor=args.overfetch_factor,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
