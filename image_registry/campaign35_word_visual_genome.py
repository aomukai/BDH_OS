"""Shortlist Visual Genome region captions for Campaign 35 word-image gaps."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _fts(word: str) -> str:
    terms = re.findall(r"[^\W_]+", word.casefold(), flags=re.UNICODE)
    if not terms:
        raise ValueError(f"cannot search empty word: {word!r}")
    return " AND ".join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)


def discover(
    index_db: Path, registry_db: Path, needs: list[dict], excluded: set[str],
    excluded_coco_ids: set[int],
) -> tuple[list[dict], list[dict]]:
    db = sqlite3.connect(f"file:{index_db.resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    registry = sqlite3.connect(f"file:{registry_db.resolve()}?mode=ro", uri=True)
    existing = {
        str(row[0]) for row in registry.execute(
            "SELECT source_id FROM asset WHERE source='visual_genome_v1_2'"
        )
    }
    excluded_coco_ids |= {
        int(row[0]) for row in registry.execute(
            "SELECT source_id FROM asset WHERE source='coco_2017' AND source_id GLOB '[0-9]*'"
        )
    }
    registry.close()
    used = set(excluded) | existing
    by_word: dict[str, list[dict]] = {}
    for need in needs:
        by_word.setdefault(need["word"], []).append(need)
    candidates, unresolved = [], []
    for word, slots in by_word.items():
        rows = db.execute(
            """SELECT r.image_id,r.region_id,r.phrase,bm25(region_search) AS score,
                      i.url,i.width,i.height,i.coco_id,i.flickr_id
               FROM region_search r JOIN image i ON i.image_id=r.image_id
               WHERE region_search MATCH ? ORDER BY score,r.image_id LIMIT ?""",
            (_fts(word), max(len(slots) * 8, 80)),
        ).fetchall()
        available = []
        seen = set()
        for row in rows:
            image_id = str(row["image_id"])
            if image_id in used or image_id in seen or (
                row["coco_id"] is not None and int(row["coco_id"]) in excluded_coco_ids
            ):
                continue
            seen.add(image_id)
            available.append(row)
        for slot, row in zip(slots, available):
            image_id = str(row["image_id"])
            used.add(image_id)
            candidates.append({
                **slot,
                "source": "visual_genome_v1_2", "split": "v1.2",
                "source_image_id": image_id, "caption": row["phrase"],
                "retrieval_evidence": {
                    "kind": "visual_genome_region_caption_word_match",
                    "region_id": row["region_id"], "matched_caption": row["phrase"],
                    "fts_score": row["score"],
                },
                "source_metadata": {
                    "original_url": row["url"].replace("http://", "https://", 1),
                    "width": row["width"], "height": row["height"],
                    "coco_id": row["coco_id"], "flickr_id": row["flickr_id"],
                    "landing_url": "https://homes.cs.washington.edu/~ranjay/visualgenome/",
                    "official_dataset_version": "Visual Genome 1.2",
                },
                "status": "metadata_candidate_not_downloaded_or_pixel_verified",
            })
        unresolved.extend({**slot, "reason": "no_unused_visual_genome_region_word_match"} for slot in slots[len(available):])
    db.close()
    candidates.sort(key=lambda row: row["sequence_position"])
    unresolved.sort(key=lambda row: row["sequence_position"])
    return candidates, unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-db", type=Path, required=True)
    parser.add_argument("--registry-db", type=Path, required=True)
    parser.add_argument("--needs", type=Path, required=True)
    parser.add_argument("--exclude-candidates", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prior = _load(args.exclude_candidates) if args.exclude_candidates else []
    excluded = {
        row["source_image_id"] for row in prior
        if row.get("source") == "visual_genome_v1_2"
    }
    excluded_coco_ids = {
        int(row["source_image_id"]) for row in prior
        if row.get("source") == "coco_2017"
    }
    candidates, unresolved = discover(
        args.index_db, args.registry_db, _load(args.needs), excluded,
        excluded_coco_ids,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("candidates", candidates), ("unresolved", unresolved)):
        (args.output / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8",
        )
    summary = {
        "schema_version": "ninereeds_campaign35_word_visual_genome_shortlist_v1",
        "requested_slots": len(candidates) + len(unresolved),
        "metadata_candidates": len(candidates), "unresolved_slots": len(unresolved),
        "matched_words": len({row["word"] for row in candidates}),
        "status": "metadata_only_requires_download_registry_review_and_pixel_verification",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
