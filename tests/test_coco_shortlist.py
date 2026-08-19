import json
import sqlite3
from pathlib import Path

from image_registry.coco_shortlist import discover


def test_discovers_caption_and_excludes_prior_coco_image(tmp_path: Path) -> None:
    db_path = tmp_path / "coco.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE image(image_id INT,file_name TEXT,coco_url TEXT,flickr_url TEXT,width INT,height INT,split TEXT,license_id INT,license_name TEXT,license_url TEXT);
            CREATE VIRTUAL TABLE caption_search USING fts5(image_id UNINDEXED,caption_id UNINDEXED,caption,tokenize='porter unicode61');
            INSERT INTO image VALUES (1,'1.jpg','http://example/1.jpg',NULL,640,480,'train2017',4,'Attribution','https://license');
            INSERT INTO image VALUES (2,'2.jpg','http://example/2.jpg',NULL,640,480,'train2017',4,'Attribution','https://license');
            INSERT INTO caption_search VALUES (1,11,'A dog is under a table.');
            INSERT INTO caption_search VALUES (2,12,'A dog is under a table.');
            """
        )
    needs = tmp_path / "needs.jsonl"
    needs.write_text(json.dumps({
        "item_id": "one", "concept": "dog", "exact_teaching_claim": "A dog is under a table.",
        "metadata_queries": [{"tier": "concrete", "terms": ["dog", "under", "table"]}],
    }) + "\n", encoding="utf-8")
    prior = tmp_path / "prior"
    prior.mkdir()
    (prior / "accepted.jsonl").write_text(json.dumps({
        "item_id": "other", "source_metadata": {"coco_id": 1},
    }) + "\n", encoding="utf-8")
    candidates, unmatched = discover(db_path, needs, exclude_verification_dirs=[prior])
    assert not unmatched
    assert candidates[0]["source_image_id"] == "2"
    assert candidates[0]["source_metadata"]["original_url"].startswith("https://")


def test_excludes_rejected_source_and_returns_multiple_candidates(tmp_path: Path) -> None:
    db_path = tmp_path / "coco.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE image(image_id INT,file_name TEXT,coco_url TEXT,flickr_url TEXT,width INT,height INT,split TEXT,license_id INT,license_name TEXT,license_url TEXT);
            CREATE VIRTUAL TABLE caption_search USING fts5(image_id UNINDEXED,caption_id UNINDEXED,caption,tokenize='porter unicode61');
            INSERT INTO image VALUES (1,'1.jpg','http://example/1.jpg',NULL,640,480,'train2017',4,'Attribution','https://license');
            INSERT INTO image VALUES (2,'2.jpg','http://example/2.jpg',NULL,640,480,'train2017',4,'Attribution','https://license');
            INSERT INTO image VALUES (3,'3.jpg','http://example/3.jpg',NULL,640,480,'train2017',4,'Attribution','https://license');
            INSERT INTO caption_search VALUES (1,11,'A dog is under a table.');
            INSERT INTO caption_search VALUES (2,12,'A dog is under a table.');
            INSERT INTO caption_search VALUES (3,13,'A dog is under a table.');
            """
        )
    needs = tmp_path / "needs.jsonl"
    needs.write_text(json.dumps({
        "item_id": "one", "concept": "dog", "exact_teaching_claim": "A dog is under a table.",
        "metadata_queries": [{"tier": "concrete", "terms": ["dog", "under", "table"]}],
    }) + "\n", encoding="utf-8")
    prior = tmp_path / "prior"
    prior.mkdir()
    (prior / "rejected.jsonl").write_text(json.dumps({
        "item_id": "one", "source": "coco_2017", "source_image_id": "1",
    }) + "\n", encoding="utf-8")
    candidates, unmatched = discover(
        db_path, needs, exclude_verification_dirs=[prior], candidates_per_item=2,
    )
    assert not unmatched
    assert [row["source_image_id"] for row in candidates] == ["2", "3"]
    assert [row["candidate_rank"] for row in candidates] == [1, 2]
