import csv
from pathlib import Path

from image_registry.cli import connect, import_open_images, select_candidates


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_import_and_deterministic_selection(tmp_path: Path) -> None:
    meta = tmp_path / "metadata"
    meta.mkdir()
    _write_csv(meta / "classes_boxable.csv", ["LabelName", "DisplayName"], [
        {"LabelName": "/cat", "DisplayName": "Cat"},
        {"LabelName": "/ball", "DisplayName": "Ball"},
    ])
    (meta / "attribute_names.csv").write_text("/red,Red\n", encoding="utf-8")
    assets = []
    labels = []
    boxes = []
    relations = []
    for index in range(40):
        image_id = f"{index:016x}"
        assets.append({
            "ImageID": image_id, "Subset": "validation", "OriginalURL": "https://example/image",
            "OriginalLandingURL": "https://example/page", "License": "CC-BY",
            "AuthorProfileURL": "", "Author": "tester", "Title": f"image {index}",
            "OriginalSize": 100, "OriginalMD5": "md5", "Thumbnail300KURL": "", "Rotation": "",
        })
        for name in ("/cat", "/ball", "/red", f"term-{index}"):
            labels.append({"ImageID": image_id, "Source": "verification", "LabelName": name, "Confidence": 1})
        for box_index in range(2):
            boxes.append({
                "ImageID": image_id, "Source": "xclick", "LabelName": "/ball", "Confidence": 1,
                "XMin": 0.1, "XMax": 0.2, "YMin": 0.1, "YMax": 0.2,
                "IsOccluded": 0, "IsTruncated": 0, "IsGroupOf": 0,
                "IsDepiction": 0, "IsInside": 0,
            })
        for predicate in ("at", "holds"):
            relations.append({
                "ImageID": image_id, "LabelName1": "/cat", "LabelName2": "/ball",
                "XMin1": 0, "XMax1": 1, "YMin1": 0, "YMax1": 1,
                "XMin2": 0, "XMax2": 1, "YMin2": 0, "YMax2": 1,
                "RelationshipLabel": predicate,
            })
    _write_csv(meta / "image_metadata.csv", list(assets[0]), assets)
    _write_csv(meta / "image_labels.csv", list(labels[0]), labels)
    _write_csv(meta / "boxes.csv", list(boxes[0]), boxes)
    _write_csv(meta / "relationships.csv", list(relations[0]), relations)

    with connect(tmp_path / "registry.sqlite3") as db:
        import_open_images(db, meta)
        assert db.execute("SELECT COUNT(*) FROM asset").fetchone()[0] == 40
        assert db.execute("SELECT COUNT(*) FROM relationship").fetchone()[0] == 80
        import_open_images(db, meta)
        assert db.execute("SELECT COUNT(*) FROM relationship").fetchone()[0] == 80
        assert db.execute("SELECT COUNT(*) FROM object_box").fetchone()[0] == 80
        select_candidates(db, "sample", 20, 9)
        first = db.execute("SELECT asset_id, stratum FROM selection ORDER BY ordinal").fetchall()
        select_candidates(db, "sample", 20, 9)
        second = db.execute("SELECT asset_id, stratum FROM selection ORDER BY ordinal").fetchall()
        assert [tuple(row) for row in first] == [tuple(row) for row in second]
        assert len(second) == 20
