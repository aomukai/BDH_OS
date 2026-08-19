import json
from pathlib import Path

from image_registry.cli import connect
from image_registry.open_images_shortlist_registry import admit


def test_admits_shortlist_without_resetting_existing_review(tmp_path: Path) -> None:
    db_path = tmp_path / "registry.sqlite3"
    shortlist = tmp_path / "shortlist.jsonl"
    candidate = {
        "source_image_id": "image-a", "split": "train",
        "source_metadata": {
            "original_url": "https://example/original", "landing_url": "https://example/landing",
            "thumbnail_url": "https://example/thumb", "license_url": "CC", "author": "A",
            "title": "T", "declared_bytes": 10, "declared_md5": "md5", "rotation": "0.0",
        },
        "retrieval_evidence": {
            "kind": "exact_concept_object_annotation",
            "matched_annotation": {"label": "Dog"},
        },
    }
    shortlist.write_text(json.dumps(candidate) + "\n", encoding="utf-8")
    with connect(db_path) as db:
        db.execute(
            """INSERT INTO asset(source,source_id,split,status)
               VALUES ('open_images_v7','image-a','train','reviewed_usable')"""
        )
        db.commit()
        assert admit(db, shortlist, "shortlist") == {
            "selection": "shortlist", "assets": 1, "created": True,
        }
        assert db.execute("SELECT status FROM asset").fetchone()[0] == "reviewed_usable"
        assert db.execute("SELECT name FROM label").fetchone()[0] == "Dog"
        assert admit(db, shortlist, "shortlist")["created"] is False
