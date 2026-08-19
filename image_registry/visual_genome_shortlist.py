"""Search Visual Genome captions conservatively for unresolved teaching claims."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "with",
}


def _dedupe_terms(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if len(value) < 2:
            continue
        if any(
            min(len(value), len(existing)) >= 4
            and (value.startswith(existing) or existing.startswith(value))
            for existing in result
        ):
            continue
        if value not in result:
            result.append(value)
    return result


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _terms(query: dict[str, Any]) -> list[str]:
    values = query.get("terms") or re.findall(r"[a-z0-9]+", str(query.get("query", "")).lower())
    return _dedupe_terms([
        value for raw in values
        if (value := "".join(re.findall(r"[a-z0-9]+", str(raw).lower())))
        and value not in STOPWORDS
    ])


def _fts(terms: list[str]) -> str:
    return " AND ".join(f'"{term}"' for term in terms)


def discover(
    index_db: Path, needs_path: Path, *, candidates_per_item: int = 3,
    search_limit: int = 40, minimum_content_terms: int = 2,
    unanchored_minimum_terms: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    db = sqlite3.connect(f"file:{index_db.resolve()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    used_images: set[int] = set()
    candidates: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for need in _load(needs_path):
        selected: list[tuple[sqlite3.Row, dict[str, Any], list[str]]] = []
        queries = sorted(
            need.get("metadata_queries", []),
            key=lambda query: (-len(_terms(query)), int(query.get("priority", 99))),
        )
        concept_terms = _dedupe_terms([
            term for term in re.findall(r"[a-z0-9]+", re.sub(r"\s+\d+$", "", need["concept"].lower()))
            if term not in STOPWORDS
        ])
        query_specs: list[tuple[dict[str, Any], list[str], str]] = []
        for query in queries:
            base_terms = _terms(query)
            anchored = _dedupe_terms(concept_terms + base_terms)
            if len(anchored) >= minimum_content_terms:
                query_specs.append((query, anchored, "concept_anchored"))
            if set(concept_terms).issubset(base_terms):
                continue
            if len(base_terms) >= unanchored_minimum_terms:
                query_specs.append((query, base_terms, "high_specificity_unanchored"))
        for query, terms, strategy in query_specs:
            if len(terms) < minimum_content_terms:
                continue
            rows = db.execute(
                """SELECT r.image_id,r.region_id,r.phrase,bm25(region_search) AS score,
                          i.url,i.width,i.height,i.coco_id,i.flickr_id
                     FROM region_search r JOIN image i ON i.image_id=r.image_id
                    WHERE region_search MATCH ?
                    ORDER BY score,r.image_id LIMIT ?""",
                (_fts(terms), search_limit),
            ).fetchall()
            for row in rows:
                if row["image_id"] in used_images or any(
                    previous[0]["image_id"] == row["image_id"] for previous in selected
                ):
                    continue
                selected.append((row, query, terms))
                if len(selected) >= candidates_per_item:
                    break
            if len(selected) >= candidates_per_item:
                break
        if not selected:
            unmatched.append({
                "item_id": need["item_id"], "concept": need["concept"],
                "exact_teaching_claim": need["exact_teaching_claim"],
                "reason": "no_visual_genome_region_description_match",
                "next_route": "another_dataset_or_representation_reassessment",
            })
            continue
        for rank, (row, query, terms) in enumerate(selected, 1):
            used_images.add(row["image_id"])
            candidates.append({
                "schema_version": "ninereeds_visual_genome_candidate_v1",
                "item_id": need["item_id"], "concept": need["concept"],
                "exact_teaching_claim": need["exact_teaching_claim"],
                "source": "visual_genome_v1_2", "split": "all",
                "source_image_id": str(row["image_id"]), "candidate_rank": rank,
                "retrieval_evidence": {
                    "kind": "region_description_fts_match",
                    "matched_region_id": row["region_id"],
                    "matched_phrase": row["phrase"],
                    "matched_terms": terms,
                    "query_tier": query.get("tier"),
                    "retrieval_strategy": strategy,
                    "fts_score": row["score"],
                },
                "source_metadata": {
                    "original_url": row["url"], "landing_url": "https://visualgenome.org/",
                    "license_url": "https://visualgenome.org/terms.html",
                    "width": row["width"], "height": row["height"],
                    "coco_id": row["coco_id"], "flickr_id": row["flickr_id"],
                    "official_dataset_version": "Visual Genome 1.2",
                },
                "status": "metadata_candidate_not_pixel_verified",
            })
    db.close()
    return candidates, unmatched


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-db", type=Path, required=True)
    parser.add_argument("--needs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidates-per-item", type=int, default=3)
    parser.add_argument("--search-limit", type=int, default=40)
    parser.add_argument("--minimum-content-terms", type=int, default=2)
    parser.add_argument("--unanchored-minimum-terms", type=int, default=3)
    args = parser.parse_args(list(argv) if argv is not None else None)
    candidates, unmatched = discover(
        args.index_db, args.needs, candidates_per_item=args.candidates_per_item,
        search_limit=args.search_limit, minimum_content_terms=args.minimum_content_terms,
        unanchored_minimum_terms=args.unanchored_minimum_terms,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    _write(args.output / "candidates.jsonl", candidates)
    _write(args.output / "unmatched.jsonl", unmatched)
    summary = {
        "schema_version": "ninereeds_visual_genome_shortlist_summary_v1",
        "needs": len(_load(args.needs)),
        "matched_items": len({row["item_id"] for row in candidates}),
        "candidate_images": len(candidates), "unmatched_items": len(unmatched),
        "status": "metadata_shortlist_requires_pixel_download_and_review",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
