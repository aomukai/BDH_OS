"""Shortlist exact Open Images object-label matches for Campaign 35 word slots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3

from .open_images_shortlist import hydrate


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _normal(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def discover(index_db: Path, registry_db: Path, needs: list[dict], excluded: set[str]) -> tuple[list[dict], list[dict]]:
    db = sqlite3.connect(f"file:{index_db.resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    registry = sqlite3.connect(f"file:{registry_db.resolve()}?mode=ro", uri=True)
    existing = {
        str(row[0]) for row in registry.execute(
            "SELECT source_id FROM asset WHERE source='open_images_v7'"
        )
    }
    registry.close()
    labels = {_normal(row[0]): row[0] for row in db.execute("SELECT DISTINCT label FROM object_image")}
    used = set(excluded) | existing
    by_word: dict[str, list[dict]] = {}
    for need in needs:
        by_word.setdefault(need["word"], []).append(need)
    candidates, unresolved = [], []
    for word, slots in by_word.items():
        label = labels.get(_normal(word))
        if label is None:
            unresolved.extend({**slot, "reason": "no_exact_open_images_object_label"} for slot in slots)
            continue
        rows = db.execute(
            """SELECT image_id,label,instances,clean_instances FROM object_image
               WHERE label=? AND clean_instances>0
               ORDER BY CASE WHEN clean_instances=1 AND instances=1 THEN 0 ELSE 1 END,
                        clean_instances,instances,image_id LIMIT ?""",
            (label, max(len(slots) * 6, 60)),
        ).fetchall()
        available = [row for row in rows if row["image_id"] not in used]
        for slot, row in zip(slots, available):
            used.add(row["image_id"])
            candidates.append({
                **slot,
                "source": "open_images_v7", "split": "train",
                "source_image_id": row["image_id"],
                "caption": None,
                "retrieval_evidence": {
                    "kind": "exact_open_images_object_annotation",
                    "matched_annotation": dict(row),
                },
                "status": "metadata_candidate_not_downloaded_or_pixel_verified",
            })
        unresolved.extend({**slot, "reason": "no_unused_exact_open_images_object_match"} for slot in slots[len(available):])
    db.close()
    candidates.sort(key=lambda row: row["sequence_position"])
    unresolved.sort(key=lambda row: row["sequence_position"])
    return candidates, unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-db", type=Path, required=True)
    parser.add_argument("--image-metadata", type=Path, required=True)
    parser.add_argument("--registry-db", type=Path, required=True)
    parser.add_argument("--needs", type=Path, required=True)
    parser.add_argument("--exclude-candidates", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    excluded = {
        row["source_image_id"] for row in _load(args.exclude_candidates)
        if row.get("source") == "open_images_v7"
    } if args.exclude_candidates else set()
    candidates, unresolved = discover(args.index_db, args.registry_db, _load(args.needs), excluded)
    hydrate(candidates, args.image_metadata)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("candidates", candidates), ("unresolved", unresolved)):
        (args.output / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    summary = {
        "schema_version": "ninereeds_campaign35_word_open_images_shortlist_v1",
        "requested_slots": len(candidates) + len(unresolved),
        "metadata_candidates": len(candidates), "unresolved_slots": len(unresolved),
        "matched_words": len({row["word"] for row in candidates}),
        "status": "metadata_only_requires_download_caption_review_and_pixel_verification",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
