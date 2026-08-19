"""Search COCO 2017 captions for unresolved teaching claims with duplicate controls."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .visual_genome_shortlist import STOPWORDS, _dedupe_terms, _fts, _terms


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def discover(
    index_db: Path, needs_path: Path, *, exclude_verification_dirs: list[Path] | None = None,
    candidates_per_item: int = 1, search_limit: int = 40, minimum_content_terms: int = 2,
    unanchored_minimum_terms: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    excluded_coco_ids: set[int] = set()
    resolved_items: set[str] = set()
    for root in exclude_verification_dirs or []:
        for name in ("accepted.jsonl", "rejected.jsonl", "uncertain.jsonl"):
            for row in _load(root / name):
                if name == "accepted.jsonl":
                    resolved_items.add(row["item_id"])
                coco_id = (row.get("source_metadata") or {}).get("coco_id")
                if coco_id is not None:
                    excluded_coco_ids.add(int(coco_id))
                if row.get("source") == "coco_2017" and row.get("source_image_id"):
                    excluded_coco_ids.add(int(row["source_image_id"]))
    db = sqlite3.connect(f"file:{index_db.resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    used_images = set(excluded_coco_ids)
    candidates: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for need in _load(needs_path):
        if need["item_id"] in resolved_items:
            continue
        concept_terms = _dedupe_terms([
            term for term in re.findall(r"[a-z0-9]+", re.sub(r"\s+\d+$", "", need["concept"].lower()))
            if term not in STOPWORDS
        ])
        queries = sorted(
            need.get("metadata_queries", []),
            key=lambda query: (-len(_terms(query)), int(query.get("priority", 99))),
        )
        selected: list[tuple[sqlite3.Row, dict[str, Any], list[str], str]] = []
        for query in queries:
            base = _terms(query)
            anchored = _dedupe_terms(concept_terms + base)
            specs: list[tuple[list[str], str]] = []
            if len(anchored) >= minimum_content_terms:
                specs.append((anchored, "concept_anchored"))
            if not set(concept_terms).issubset(base) and len(base) >= unanchored_minimum_terms:
                specs.append((base, "high_specificity_unanchored"))
            for terms, strategy in specs:
                rows = db.execute(
                    """SELECT c.image_id,c.caption_id,c.caption,bm25(caption_search) score,
                              i.file_name,i.coco_url,i.flickr_url,i.width,i.height,i.split,
                              i.license_id,i.license_name,i.license_url
                         FROM caption_search c JOIN image i ON i.image_id=c.image_id
                        WHERE caption_search MATCH ? ORDER BY score,c.image_id LIMIT ?""",
                    (_fts(terms), search_limit),
                ).fetchall()
                for row in rows:
                    if row["image_id"] in used_images or any(
                        previous[0]["image_id"] == row["image_id"] for previous in selected
                    ):
                        continue
                    selected.append((row, query, terms, strategy))
                    if len(selected) >= candidates_per_item:
                        break
                if len(selected) >= candidates_per_item:
                    break
            if len(selected) >= candidates_per_item:
                break
        if not selected:
            unmatched.append({
                "item_id": need["item_id"], "concept": need["concept"],
                "exact_teaching_claim": need["exact_teaching_claim"],
                "reason": "no_coco_caption_match",
                "next_route": "another_dataset_or_representation_reassessment",
            })
            continue
        for rank, (row, query, terms, strategy) in enumerate(selected, 1):
            used_images.add(row["image_id"])
            url = row["coco_url"].replace("http://", "https://", 1)
            candidates.append({
                "schema_version": "ninereeds_coco_candidate_v1",
                "item_id": need["item_id"], "concept": need["concept"],
                "exact_teaching_claim": need["exact_teaching_claim"],
                "source": "coco_2017", "split": row["split"],
                "source_image_id": str(row["image_id"]), "candidate_rank": rank,
                "retrieval_evidence": {
                    "kind": "coco_caption_fts_match", "matched_caption_id": row["caption_id"],
                    "matched_caption": row["caption"], "matched_terms": terms,
                    "query_tier": query.get("tier"), "retrieval_strategy": strategy,
                    "fts_score": row["score"],
                },
                "source_metadata": {
                    "original_url": url, "landing_url": "https://cocodataset.org/",
                    "license_id": row["license_id"], "license_name": row["license_name"],
                    "license_url": row["license_url"], "width": row["width"],
                    "height": row["height"], "file_name": row["file_name"],
                    "flickr_url": row["flickr_url"], "official_dataset_version": "COCO 2017",
                },
                "status": "metadata_candidate_not_pixel_verified",
            })
    db.close()
    return candidates, unmatched


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-db", type=Path, required=True)
    parser.add_argument("--needs", type=Path, required=True)
    parser.add_argument("--exclude-verification-dir", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--search-limit", type=int, default=40)
    parser.add_argument("--candidates-per-item", type=int, default=1)
    parser.add_argument("--minimum-content-terms", type=int, default=2)
    parser.add_argument("--unanchored-minimum-terms", type=int, default=3)
    args = parser.parse_args(list(argv) if argv is not None else None)
    candidates, unmatched = discover(
        args.index_db, args.needs, exclude_verification_dirs=args.exclude_verification_dir,
        candidates_per_item=args.candidates_per_item, search_limit=args.search_limit,
        minimum_content_terms=args.minimum_content_terms,
        unanchored_minimum_terms=args.unanchored_minimum_terms,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("candidates", candidates), ("unmatched", unmatched)):
        (args.output / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    summary = {
        "schema_version": "ninereeds_coco_shortlist_summary_v1",
        "candidate_images": len(candidates),
        "matched_items": len({row["item_id"] for row in candidates}),
        "unmatched_items": len(unmatched),
        "status": "metadata_shortlist_requires_pixel_download_and_review",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
