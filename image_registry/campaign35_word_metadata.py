"""Fill Campaign 35 word-image gaps from Localized Narratives metadata.

This stage downloads nothing.  It binds gap slots to caption-rich COCO or Open
Images IDs so pixels can be fetched, mechanically checked, registered, and
reviewed before admission.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3
from typing import Any


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _fts(word: str) -> str:
    terms = re.findall(r"[^\W_]+", word.casefold(), flags=re.UNICODE)
    if not terms:
        raise ValueError(f"cannot search empty word: {word!r}")
    return " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)


def discover(
    index_db: Path,
    coco_db: Path,
    registry_db: Path,
    wishlist_path: Path,
    *,
    search_multiplier: int = 8,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    gaps = _load(wishlist_path)
    index = sqlite3.connect(f"file:{index_db.resolve()}?mode=ro", uri=True)
    index.row_factory = sqlite3.Row
    coco = sqlite3.connect(f"file:{coco_db.resolve()}?mode=ro", uri=True)
    coco.row_factory = sqlite3.Row
    registry = sqlite3.connect(f"file:{registry_db.resolve()}?mode=ro", uri=True)
    registry.row_factory = sqlite3.Row
    existing = {
        (row["source"], str(row["source_id"]))
        for row in registry.execute("SELECT source,source_id FROM asset")
    }
    registry.close()
    by_word: dict[str, list[dict[str, Any]]] = {}
    for gap in gaps:
        by_word.setdefault(gap["word"], []).append(gap)
    candidates: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for word, slots in by_word.items():
        limit = max(len(slots) * search_multiplier, 80)
        rows = index.execute(
            """SELECT dataset_id,image_id,annotator_id,caption,
                      bm25(narrative_search) AS score
               FROM narrative_search WHERE narrative_search MATCH ?
               ORDER BY score,dataset_id,image_id LIMIT ?""",
            (_fts(word), limit),
        ).fetchall()
        available: list[sqlite3.Row] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            source = "open_images_v7" if row["dataset_id"] == "open_images" else "coco_2017"
            key = (source, str(row["image_id"]))
            if key in seen or key in existing:
                continue
            seen.add(key)
            available.append(row)
        for slot, row in zip(slots, available):
            source = "open_images_v7" if row["dataset_id"] == "open_images" else "coco_2017"
            if source == "coco_2017":
                metadata = coco.execute("SELECT * FROM image WHERE image_id=?", (int(row["image_id"]),)).fetchone()
                if metadata is None:
                    unresolved.append({**slot, "reason": "localized_narrative_coco_metadata_missing"})
                    continue
                source_metadata = {
                    "original_url": metadata["coco_url"].replace("http://", "https://", 1),
                    "flickr_url": metadata["flickr_url"], "file_name": metadata["file_name"],
                    "width": metadata["width"], "height": metadata["height"],
                    "license_id": metadata["license_id"], "license_name": metadata["license_name"],
                    "license_url": metadata["license_url"], "landing_url": "https://cocodataset.org/",
                    "official_dataset_version": "COCO 2017",
                }
                split = metadata["split"]
            else:
                source_metadata = {
                    "original_url": f"https://open-images-dataset.s3.amazonaws.com/train/{row['image_id']}.jpg",
                    "landing_url": "https://storage.googleapis.com/openimages/web/index.html",
                    "license_url": "https://creativecommons.org/licenses/by/2.0/",
                    "official_dataset_version": "Open Images V6/V7 train",
                }
                split = "train"
            candidates.append({
                **slot,
                "source": source,
                "split": split,
                "source_image_id": str(row["image_id"]),
                "caption": row["caption"],
                "retrieval_evidence": {
                    "kind": "localized_narrative_word_match",
                    "dataset_id": row["dataset_id"], "annotator_id": row["annotator_id"],
                    "matched_caption": row["caption"], "fts_score": row["score"],
                    "annotation_license": "CC BY 4.0",
                },
                "source_metadata": source_metadata,
                "status": "metadata_candidate_not_downloaded_or_pixel_verified",
            })
        if len(available) < len(slots):
            unresolved.extend({**slot, "reason": "no_unused_localized_narrative_word_match"} for slot in slots[len(available):])
    index.close()
    coco.close()
    candidates.sort(key=lambda row: row["sequence_position"])
    unresolved.sort(key=lambda row: row["sequence_position"])
    return candidates, unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-db", type=Path, required=True)
    parser.add_argument("--coco-db", type=Path, required=True)
    parser.add_argument("--registry-db", type=Path, required=True)
    parser.add_argument("--wishlist", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidates, unresolved = discover(args.index_db, args.coco_db, args.registry_db, args.wishlist)
    args.output.mkdir(parents=True, exist_ok=True)
    _write(args.output / "candidates.jsonl", candidates)
    _write(args.output / "unresolved.jsonl", unresolved)
    summary = {
        "schema_version": "ninereeds_campaign35_word_metadata_shortlist_v1",
        "requested_slots": len(candidates) + len(unresolved),
        "metadata_candidates": len(candidates),
        "unresolved_slots": len(unresolved),
        "matched_words": len({row["word"] for row in candidates}),
        "status": "metadata_only_requires_download_registry_review_and_pixel_verification",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
