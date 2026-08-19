import csv
import json
import sqlite3
from pathlib import Path

from image_registry.open_images_shortlist import discover, hydrate


def test_discovers_relationship_then_exact_object_and_hydrates(tmp_path: Path) -> None:
    db_path = tmp_path / "index.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE object_image(label TEXT, image_id TEXT, instances INT, clean_instances INT);
            CREATE TABLE relation(subject TEXT, predicate TEXT, object TEXT, image_id TEXT);
            INSERT INTO object_image VALUES ('Dog', 'object-image', 1, 1);
            INSERT INTO object_image VALUES ('Dog', 'crowded-image', 20, 20);
            INSERT INTO object_image VALUES ('Dog', 'relation-image', 1, 1);
            INSERT INTO object_image VALUES ('Table', 'relation-image', 1, 1);
            INSERT INTO relation VALUES ('Dog', 'under', 'Table', 'relation-image');
            """
        )
    needs = tmp_path / "needs.jsonl"
    rows = [
        {"item_id": "one", "concept": "under", "exact_teaching_claim": "A dog is under a table."},
        {"item_id": "two", "concept": "dog 2", "exact_teaching_claim": "A dog is an animal."},
    ]
    needs.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    candidates, unmatched = discover(db_path, needs, candidates_per_item=1)

    assert not unmatched
    assert candidates[0]["source_image_id"] == "relation-image"
    assert candidates[0]["retrieval_evidence"]["kind"] == "explicit_relationship_annotation"
    assert candidates[1]["source_image_id"] == "object-image"

    metadata = tmp_path / "image_metadata.csv"
    fields = [
        "ImageID", "OriginalURL", "OriginalLandingURL", "Thumbnail300KURL", "License",
        "Author", "Title", "OriginalSize", "OriginalMD5", "Rotation",
    ]
    with metadata.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for image_id in ("relation-image", "object-image"):
            writer.writerow({
                "ImageID": image_id, "OriginalURL": f"https://example/{image_id}",
                "OriginalLandingURL": "https://example/landing", "Thumbnail300KURL": "https://example/thumb",
                "License": "CC", "Author": "A", "Title": "T", "OriginalSize": "12",
                "OriginalMD5": "md5", "Rotation": "0",
            })
    hydrate(candidates, metadata)
    assert candidates[0]["source_metadata"]["declared_bytes"] == 12
