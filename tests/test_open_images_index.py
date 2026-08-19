import csv
import sqlite3
from pathlib import Path

from image_registry.open_images_index import build_index


def _csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_builds_deduplicated_annotation_index(tmp_path: Path) -> None:
    metadata = tmp_path / "metadata"
    _csv(metadata / "classes_boxable.csv", ["LabelName", "DisplayName"], [
        {"LabelName": "/dog", "DisplayName": "Dog"},
        {"LabelName": "/table", "DisplayName": "Table"},
    ])
    box_fields = [
        "ImageID", "LabelName", "IsOccluded", "IsTruncated", "IsGroupOf", "IsDepiction",
    ]
    _csv(metadata / "boxes.csv", box_fields, [
        {"ImageID": "a", "LabelName": "/dog", "IsOccluded": "0", "IsTruncated": "0", "IsGroupOf": "0", "IsDepiction": "0"},
        {"ImageID": "a", "LabelName": "/dog", "IsOccluded": "1", "IsTruncated": "0", "IsGroupOf": "0", "IsDepiction": "0"},
        {"ImageID": "a", "LabelName": "/table", "IsOccluded": "0", "IsTruncated": "0", "IsGroupOf": "0", "IsDepiction": "0"},
    ])
    relation_fields = ["ImageID", "LabelName1", "LabelName2", "RelationshipLabel"]
    relation = {"ImageID": "a", "LabelName1": "/dog", "LabelName2": "/table", "RelationshipLabel": "under"}
    _csv(metadata / "relationships.csv", relation_fields, [relation, relation])

    manifest = build_index(metadata, tmp_path / "index.sqlite3", batch_size=1)

    assert manifest["object_image_rows"] == 2
    assert manifest["object_images"] == 1
    assert manifest["relationship_source_rows"] == 2
    assert manifest["relationship_rows"] == 1
    with sqlite3.connect(tmp_path / "index.sqlite3") as db:
        assert db.execute(
            "SELECT instances, clean_instances FROM object_image WHERE label='Dog'"
        ).fetchone() == (2, 1)
        assert db.execute("SELECT subject, predicate, object FROM relation").fetchone() == (
            "Dog", "under", "Table",
        )
