"""Search dense Localized Narratives captions for the audited still-image wishlist."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable

from .representation_reassessment import load_jsonl
from .visual_genome_shortlist import STOPWORDS, _dedupe_terms, _fts, _terms


def discover(
    index_db: Path, coco_db: Path, needs_path: Path, *, candidates_per_item: int = 2,
    search_limit: int = 60,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    db = sqlite3.connect(f"file:{index_db.resolve()}?mode=ro", uri=True); db.row_factory = sqlite3.Row
    coco = sqlite3.connect(f"file:{coco_db.resolve()}?mode=ro", uri=True); coco.row_factory = sqlite3.Row
    used: set[tuple[str, str]] = set()
    candidates, unmatched = [], []
    for need in load_jsonl(needs_path):
        concept_terms = _dedupe_terms([
            term for term in re.findall(r"[a-z0-9]+", re.sub(r"\s+\d+$", "", need["concept"].lower()))
            if term not in STOPWORDS
        ])
        selected = []
        queries = sorted(need.get("metadata_queries", []), key=lambda q: (-len(_terms(q)), int(q.get("priority", 99))))
        for query in queries:
            base = _terms(query); anchored = _dedupe_terms(concept_terms + base)
            specs = []
            if len(anchored) >= 2: specs.append((anchored, "concept_anchored"))
            if not set(concept_terms).issubset(base) and len(base) >= 3:
                specs.append((base, "high_specificity_unanchored"))
            for terms, strategy in specs:
                rows = db.execute(
                    """SELECT dataset_id,image_id,annotator_id,caption,bm25(narrative_search) score
                       FROM narrative_search WHERE narrative_search MATCH ?
                       ORDER BY score,dataset_id,image_id LIMIT ?""", (_fts(terms), search_limit),
                ).fetchall()
                for row in rows:
                    key = (row["dataset_id"], row["image_id"])
                    if key in used or any((x[0]["dataset_id"], x[0]["image_id"]) == key for x in selected):
                        continue
                    selected.append((row, query, terms, strategy))
                    if len(selected) >= candidates_per_item: break
                if len(selected) >= candidates_per_item: break
            if len(selected) >= candidates_per_item: break
        if not selected:
            unmatched.append({"item_id": need["item_id"], "concept": need["concept"],
                              "exact_teaching_claim": need["exact_teaching_claim"],
                              "reason": "no_localized_narrative_match"})
            continue
        for rank, (row, query, terms, strategy) in enumerate(selected, 1):
            used.add((row["dataset_id"], row["image_id"]))
            source = "open_images_v7" if row["dataset_id"] == "open_images" else "coco_2017"
            if source == "coco_2017":
                meta = coco.execute("SELECT * FROM image WHERE image_id=?", (int(row["image_id"]),)).fetchone()
                if meta is None: continue
                source_metadata = {
                    "file_name": meta["file_name"], "width": meta["width"], "height": meta["height"],
                    "original_url": meta["coco_url"].replace("http://", "https://", 1),
                    "flickr_url": meta["flickr_url"], "license_id": meta["license_id"],
                    "license_name": meta["license_name"], "license_url": meta["license_url"],
                    "landing_url": "https://cocodataset.org/", "official_dataset_version": "COCO 2017",
                }
                split = meta["split"]
            else:
                source_metadata = {
                    "original_url": f"https://open-images-dataset.s3.amazonaws.com/train/{row['image_id']}.jpg",
                    "landing_url": "https://storage.googleapis.com/openimages/web/index.html",
                    "license_url": "https://creativecommons.org/licenses/by/2.0/",
                    "official_dataset_version": "Open Images V6/V7 train",
                }
                split = "train"
            candidates.append({
                "schema_version": "ninereeds_localized_narratives_candidate_v1",
                "item_id": need["item_id"], "concept": need["concept"],
                "exact_teaching_claim": need["exact_teaching_claim"], "source": source,
                "split": split, "source_image_id": str(row["image_id"]), "candidate_rank": rank,
                "retrieval_evidence": {"kind": "localized_narrative_caption_fts_match",
                    "dataset_id": row["dataset_id"], "annotator_id": row["annotator_id"],
                    "matched_caption": row["caption"], "matched_terms": terms,
                    "query_tier": query.get("tier"), "retrieval_strategy": strategy,
                    "fts_score": row["score"], "annotation_license": "CC BY 4.0"},
                "source_metadata": source_metadata, "status": "metadata_candidate_not_pixel_verified",
            })
    db.close(); coco.close()
    return candidates, unmatched


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-db", type=Path, required=True); parser.add_argument("--coco-db", type=Path, required=True)
    parser.add_argument("--needs", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidates-per-item", type=int, default=2); parser.add_argument("--search-limit", type=int, default=60)
    args = parser.parse_args(list(argv) if argv is not None else None)
    candidates, unmatched = discover(args.index_db, args.coco_db, args.needs,
                                     candidates_per_item=args.candidates_per_item, search_limit=args.search_limit)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("candidates", candidates), ("unmatched", unmatched)):
        (args.output / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True)+"\n" for r in rows), encoding="utf-8")
    summary = {"candidate_images": len(candidates), "matched_items": len({r['item_id'] for r in candidates}),
               "unmatched_items": len(unmatched), "status": "metadata_shortlist_requires_pixel_review"}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
