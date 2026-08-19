import json
import sqlite3
import zipfile
from pathlib import Path

from image_registry.coco_index import build_index


def test_builds_caption_index_with_license(tmp_path: Path) -> None:
    archive = tmp_path / "annotations.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for split, image_id in (("train2017", 1), ("val2017", 2)):
            document = {
                "licenses": [{"id": 4, "name": "Attribution", "url": "https://license"}],
                "images": [{"id": image_id, "file_name": f"{image_id}.jpg",
                            "coco_url": f"https://example/{image_id}.jpg", "flickr_url": None,
                            "width": 640, "height": 480, "license": 4}],
                "annotations": [{"id": image_id + 10, "image_id": image_id,
                                 "caption": "A dog is under a table."}],
            }
            output.writestr(f"annotations/captions_{split}.json", json.dumps(document))
    manifest = build_index(archive, tmp_path / "coco.sqlite3")
    assert manifest["images"] == 2
    assert manifest["captions"] == 2
    with sqlite3.connect(tmp_path / "coco.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM caption_search WHERE caption_search MATCH 'dog AND table'").fetchone()[0] == 2
        assert db.execute("SELECT license_url FROM image LIMIT 1").fetchone()[0] == "https://license"
