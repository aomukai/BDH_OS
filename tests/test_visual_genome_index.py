import json
import sqlite3
import zipfile
from pathlib import Path

from image_registry.visual_genome_index import build_index


def _zip(path: Path, member: str, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, json.dumps(value))


def test_builds_visual_genome_index(tmp_path: Path) -> None:
    root = tmp_path / "metadata"
    _zip(root / "image_data.json.zip", "image_data.json", [
        {"image_id": 1, "url": "https://example/1.jpg", "width": 640, "height": 480,
         "coco_id": None, "flickr_id": None},
    ])
    _zip(root / "region_descriptions.json.zip", "region_descriptions.json", [
        {"regions": [{"image_id": 1, "region_id": 2, "phrase": "A dog is under a table."}]},
    ])
    _zip(root / "relationships.json.zip", "relationships.json", [
        {"image_id": 1, "relationships": [{
            "relationship_id": 3, "predicate": "UNDER",
            "subject": {"name": "dog"}, "object": {"names": ["table"]},
        }]},
    ])
    manifest = build_index(root, tmp_path / "index.sqlite3", batch_size=1)
    assert manifest["images"] == 1
    assert manifest["region_descriptions"] == 1
    assert manifest["relationships_distinct"] == 1
    with sqlite3.connect(tmp_path / "index.sqlite3") as db:
        assert db.execute(
            "SELECT image_id FROM region_search WHERE region_search MATCH 'dog AND under AND table'"
        ).fetchone()[0] == 1
        assert db.execute("SELECT subject,predicate,object FROM relationship").fetchone() == (
            "dog", "under", "table",
        )
