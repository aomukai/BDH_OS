import json
from pathlib import Path

from image_registry.cli import connect
from image_registry.coco_shortlist_registry import admit


def test_admits_coco_candidate_caption_and_license(tmp_path: Path) -> None:
    candidate = {
        "source_image_id": "1", "split": "train2017",
        "source_metadata": {
            "original_url": "https://images.cocodataset.org/train2017/1.jpg",
            "landing_url": "https://cocodataset.org/", "license_url": "https://license/",
            "license_id": 3, "license_name": "Example", "flickr_url": "http://flickr/1.jpg",
            "file_name": "1.jpg", "width": 640, "height": 480,
        },
        "retrieval_evidence": {"matched_caption_id": 2, "matched_caption": "A dog under a table."},
    }
    shortlist = tmp_path / "shortlist.jsonl"
    shortlist.write_text(json.dumps(candidate) + "\n", encoding="utf-8")
    with connect(tmp_path / "registry.sqlite3") as db:
        assert admit(db, shortlist, "coco")["created"] is True
        assert tuple(db.execute("SELECT source,status,license_url FROM asset").fetchone()) == (
            "coco_2017", "metadata_only", "https://license/",
        )
        assert db.execute("SELECT original_url FROM asset").fetchone()[0] == (
            "https://s3.amazonaws.com/images.cocodataset.org/train2017/1.jpg"
        )
        row = db.execute("SELECT text,payload_json FROM text_record").fetchone()
        assert row[0] == "A dog under a table."
        assert json.loads(row[1])["license_name"] == "Example"
        assert admit(db, shortlist, "coco")["created"] is False
