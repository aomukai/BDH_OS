import hashlib
import json
from pathlib import Path

from image_registry.cli import connect
from image_registry.material_gap_analysis import main


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_recurring_gap_analysis_partitions_have_and_need(tmp_path: Path) -> None:
    material = tmp_path / "material"
    visual = material / "visual-batches" / "batch.jsonl"
    rows = [
        {
            "canonical_caption": "dog", "concept": "dog", "concept_id": "dog",
            "example_index": 1, "item_id": "c0001-e1", "ordinal": 1,
            "prompt": "Visual interpretation: dog is here. One coherent scene, no text.",
        },
        {
            "canonical_caption": "unicorn", "concept": "unicorn", "concept_id": "unicorn",
            "example_index": 1, "item_id": "c0002-e1", "ordinal": 2,
            "prompt": "Visual interpretation: unicorn is here. One coherent scene, no text.",
        },
    ]
    _jsonl(visual, rows)
    _jsonl(material / "curriculum.jsonl", [
        {"concept": "dog", "concept_id": "dog", "ordinal": 1},
        {"concept": "unicorn", "concept_id": "unicorn", "ordinal": 2},
    ])
    (material / "manifest.json").write_text(json.dumps({"batches": [{
        "batch_id": "batch", "visual_path": "visual-batches/batch.jsonl",
        "visual_sha256": hashlib.sha256(visual.read_bytes()).hexdigest(),
    }]}), encoding="utf-8")

    mission = tmp_path / "mission.json"
    mission.write_text(json.dumps({"campaign": {"id": "campaign-test"}}), encoding="utf-8")
    audit = tmp_path / "audit"
    (audit / "batches").mkdir(parents=True)
    (audit / "summary.json").write_text(json.dumps({"status": "ready_for_sol_review"}), encoding="utf-8")

    image = tmp_path / "dog.jpg"
    image.write_bytes(b"test-image")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    db_path = tmp_path / "registry.sqlite3"
    with connect(db_path) as db:
        cursor = db.execute(
            """INSERT INTO asset(source,source_id,split,local_path,sha256,width,height,status)
               VALUES ('test','dog-1','train',?,?,640,480,'reviewed_usable')""",
            (str(image), digest),
        )
        db.execute(
            "INSERT INTO text_record(asset_id,kind,text,author) VALUES (?,'reviewed_caption','dog in a park','test')",
            (cursor.lastrowid,),
        )
        db.execute(
            "INSERT INTO text_search(asset_id,kind,text) VALUES (?,'reviewed_caption','dog in a park')",
            (cursor.lastrowid,),
        )
        db.commit()
        dog_asset_id = cursor.lastrowid

    _jsonl(audit / "batches" / "batch.jsonl", [
        {"ordinal": 1, "status": "ready_for_sol_fit_review", "candidates": [{"asset_id": dog_asset_id}]},
        {"ordinal": 2, "status": "needs_sol_query_expansion", "candidates": []},
    ])

    output = tmp_path / "output"
    assert main([
        "--db", str(db_path), "--material-root", str(material),
        "--mission", str(mission), "--audit", str(audit), "--output", str(output),
        "--expected-items", "2", "--expected-concepts", "2",
    ]) == 0

    selections = [json.loads(line) for line in (output / "selection_proposal.jsonl").read_text().splitlines()]
    wishlist = [json.loads(line) for line in (output / "wishlist.jsonl").read_text().splitlines()]
    assert [row["item_id"] for row in selections] == ["c0001-e1"]
    assert selections[0]["verification_status"] == "pending_luna_pixel_verification"
    assert wishlist[0]["item_ids"] == ["c0002-e1"]
    assert wishlist[0]["preferred_next_action"] == "external_acquisition"
    assert json.loads((output / "validation_report.json").read_text())["status"] == "passed"
