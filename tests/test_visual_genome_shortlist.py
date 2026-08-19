import json
import sqlite3
from pathlib import Path

from image_registry.visual_genome_shortlist import _dedupe_terms, discover


def test_deduplicates_inflection_and_stem_as_one_signal() -> None:
    assert _dedupe_terms(["ensuring", "ensur", "flow"]) == ["ensuring", "flow"]


def test_prefers_specific_multi_term_query(tmp_path: Path) -> None:
    db_path = tmp_path / "vg.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE image(image_id INTEGER PRIMARY KEY,url TEXT,width INT,height INT,coco_id INT,flickr_id INT);
            CREATE VIRTUAL TABLE region_search USING fts5(image_id UNINDEXED,region_id UNINDEXED,phrase,tokenize='porter unicode61');
            INSERT INTO image VALUES (1,'https://example/1.jpg',640,480,NULL,NULL);
            INSERT INTO image VALUES (2,'https://example/2.jpg',640,480,NULL,NULL);
            INSERT INTO region_search VALUES (1,1,'A ruler sits on a desk.');
            INSERT INTO region_search VALUES (2,2,'A ruler measures length.');
            """
        )
    need = {
        "item_id": "one", "concept": "ruler", "exact_teaching_claim": "A ruler measures length.",
        "metadata_queries": [
            {"priority": 1, "tier": "exact", "terms": ["ruler"]},
            {"priority": 3, "tier": "concrete", "terms": ["measure", "length"]},
        ],
    }
    needs = tmp_path / "needs.jsonl"
    needs.write_text(json.dumps(need) + "\n", encoding="utf-8")
    candidates, unmatched = discover(db_path, needs, candidates_per_item=1)
    assert not unmatched
    assert candidates[0]["source_image_id"] == "2"
    assert candidates[0]["retrieval_evidence"]["query_tier"] == "concrete"
