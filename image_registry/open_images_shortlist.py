"""Create a conservative Open Images pixel shortlist from external material needs."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable


RELATION_PHRASES = (
    "holding hands", "talk on phone", "inside of", "interacts with",
    "skateboard", "snowboard", "highfive", "handshake", "holds", "wears",
    "surf", "hang", "drink", "on", "ride", "dance", "catch", "eat", "cut",
    "contain", "kiss", "under", "hug", "throw", "hits", "kick", "ski",
    "plays", "read",
)


def _normal(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _concept(value: str) -> str:
    return re.sub(r"\s+\d+$", "", _normal(value))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _mentioned_labels(claim: str, labels: dict[str, str]) -> list[str]:
    normal_claim = f" {_normal(claim)} "
    found = [
        (normal_claim.index(f" {normal} "), display)
        for normal, display in labels.items()
        if f" {normal} " in normal_claim
    ]
    return [display for _, display in sorted(found)]


def _relation_candidates(
    db: sqlite3.Connection, labels: list[str], predicate: str, limit: int,
) -> list[sqlite3.Row]:
    if len(labels) < 2:
        return []
    placeholders = ",".join("?" for _ in labels)
    return db.execute(
        f"""SELECT image_id, subject, predicate, object
              FROM relation
             WHERE predicate = ? AND subject IN ({placeholders}) AND object IN ({placeholders})
             ORDER BY image_id LIMIT ?""",
        (predicate, *labels, *labels, limit),
    ).fetchall()


def discover(
    index_db: Path, needs_path: Path, *, candidates_per_item: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    db = sqlite3.connect(f"file:{index_db.resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    labels = {
        _normal(row[0]): row[0]
        for row in db.execute("SELECT DISTINCT label FROM object_image")
    }
    used_images: set[str] = set()
    candidates: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for need in _load_jsonl(needs_path):
        claim = need["exact_teaching_claim"]
        concept_label = labels.get(_concept(need["concept"]))
        mentioned = _mentioned_labels(claim, labels)
        predicate = next(
            (phrase for phrase in RELATION_PHRASES if f" {phrase} " in f" {_normal(claim)} "),
            None,
        )
        rows: list[sqlite3.Row] = []
        evidence_kind = ""
        if predicate:
            rows = _relation_candidates(db, mentioned, predicate, candidates_per_item * 10)
            evidence_kind = "explicit_relationship_annotation"
        if not rows and concept_label:
            rows = db.execute(
                """SELECT image_id, label, instances, clean_instances
                     FROM object_image
                    WHERE label = ? AND clean_instances > 0
                    ORDER BY CASE WHEN clean_instances = 1 AND instances = 1 THEN 0 ELSE 1 END,
                             clean_instances, instances, image_id
                    LIMIT ?""",
                (concept_label, candidates_per_item * 10),
            ).fetchall()
            evidence_kind = "exact_concept_object_annotation"
        selected = [row for row in rows if row["image_id"] not in used_images][:candidates_per_item]
        if not selected:
            unmatched.append({
                "item_id": need["item_id"],
                "concept": need["concept"],
                "exact_teaching_claim": claim,
                "reason": "no_unused_high_evidence_open_images_annotation_match",
                "next_route": "caption_rich_metadata_or_representation_reassessment",
            })
            continue
        for rank, row in enumerate(selected, 1):
            image_id = row["image_id"]
            used_images.add(image_id)
            annotation = dict(row)
            candidates.append({
                "schema_version": "ninereeds_open_images_candidate_v1",
                "item_id": need["item_id"],
                "concept": need["concept"],
                "exact_teaching_claim": claim,
                "source": "open_images_v7",
                "split": "train",
                "source_image_id": image_id,
                "candidate_rank": rank,
                "retrieval_evidence": {
                    "kind": evidence_kind,
                    "matched_annotation": annotation,
                },
                "status": "metadata_candidate_not_pixel_verified",
            })
    db.close()
    return candidates, unmatched


def hydrate(candidates: list[dict[str, Any]], image_metadata: Path) -> None:
    by_id: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        by_id.setdefault(row["source_image_id"], []).append(row)
    remaining = set(by_id)
    with image_metadata.open(newline="", encoding="utf-8") as handle:
        for source in csv.DictReader(handle):
            image_id = source["ImageID"]
            if image_id not in remaining:
                continue
            fields = {
                "original_url": source["OriginalURL"],
                "landing_url": source["OriginalLandingURL"],
                "thumbnail_url": source["Thumbnail300KURL"],
                "license_url": source["License"],
                "author": source["Author"],
                "title": source["Title"],
                "declared_bytes": int(source["OriginalSize"] or 0),
                "declared_md5": source["OriginalMD5"],
                "rotation": source["Rotation"],
            }
            for candidate in by_id[image_id]:
                candidate["source_metadata"] = fields
            remaining.remove(image_id)
            if not remaining:
                break
    if remaining:
        raise ValueError(f"missing image metadata for {len(remaining)} shortlisted IDs")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-db", type=Path, required=True)
    parser.add_argument("--needs", type=Path, required=True)
    parser.add_argument("--image-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidates-per-item", type=int, default=3)
    args = parser.parse_args(list(argv) if argv is not None else None)
    candidates, unmatched = discover(
        args.index_db, args.needs, candidates_per_item=args.candidates_per_item,
    )
    hydrate(candidates, args.image_metadata)
    args.output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output / "candidates.jsonl", candidates)
    _write_jsonl(args.output / "unmatched.jsonl", unmatched)
    summary = {
        "schema_version": "ninereeds_open_images_shortlist_summary_v1",
        "needs": len(_load_jsonl(args.needs)),
        "matched_items": len({row["item_id"] for row in candidates}),
        "candidate_images": len(candidates),
        "unmatched_items": len(unmatched),
        "status": "metadata_shortlist_requires_pixel_download_and_luna_gate",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
