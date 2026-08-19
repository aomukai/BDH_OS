import json
from pathlib import Path

from image_registry.campaign35_material import compile_audit
from image_registry.cli import connect


def _materials(root: Path) -> Path:
    root.mkdir()
    (root / "visual.jsonl").write_text("\n".join((
        json.dumps({
            "canonical_caption": "under", "concept": "under", "concept_id": "under",
            "example_index": 1, "item_id": "c0001-e1", "ordinal": 1,
            "prompt": "Visual interpretation: A dog is under a table. One coherent scene, no text.",
        }),
        json.dumps({
            "canonical_caption": "under", "concept": "under", "concept_id": "under",
            "example_index": 2, "item_id": "c0001-e2", "ordinal": 1,
            "prompt": "Visual interpretation: A cat is under a tree. One coherent scene, no text.",
        }),
    )) + "\n", encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({
        "batches": [{"batch_id": "c0001-c0025", "visual_path": "visual.jsonl"}],
    }), encoding="utf-8")
    return root


def _asset(db, source_id: str, caption: str, status: str) -> None:
    cursor = db.execute(
        """INSERT INTO asset(source,source_id,split,local_path,sha256,width,height,status)
           VALUES ('test',?,'train',?, ?,640,480,?)""",
        (source_id, f"/images/{source_id}.jpg", source_id.rjust(64, "0")[-64:], status),
    )
    db.execute(
        "INSERT INTO text_search(asset_id,kind,text) VALUES (?,'caption',?)",
        (cursor.lastrowid, caption),
    )


def test_campaign35_audit_is_read_only_and_sharded_for_sol(tmp_path: Path) -> None:
    db_path = tmp_path / "registry.sqlite3"
    with connect(db_path) as db:
        _asset(db, "1", "dog under table", "reviewed_usable")
        _asset(db, "2", "cat under tree", "mechanically_valid")
        db.execute("""CREATE TABLE review_queue(
            queue_name TEXT, asset_id INTEGER, ordinal INTEGER, status TEXT,
            current_attempt_id INTEGER, completed_at TEXT, result_json TEXT)""")
        db.execute("INSERT INTO review_queue VALUES ('visual-corpus-review-v1',1,0,'pending',NULL,NULL,NULL)")
        db.commit()

    output = tmp_path / "audit"
    summary = compile_audit(
        db_path, _materials(tmp_path / "material"), output,
        candidate_multiplier=1, minimum_candidates=1,
    )
    assert summary["required_images"] == 2
    assert summary["exact_query_upper_bound_covered"] == 1
    assert summary["status"] == "preview_only_registry_still_processing"
    unit = json.loads((output / "batches/c0001-c0025.jsonl").read_text())
    assert unit["status"] == "needs_sol_query_expansion"
    assert [item["asset_id"] for item in unit["candidates"]] == [1]
    assert unit["sol_instruction"].endswith("Do not commission Flux.")
    with connect(db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM selection").fetchone()[0] == 0


def test_permanent_benchmark_queue_does_not_block_registry_freeze(tmp_path: Path) -> None:
    db_path = tmp_path / "registry.sqlite3"
    with connect(db_path) as db:
        _asset(db, "1", "dog under table", "reviewed_usable")
        db.execute("""CREATE TABLE review_queue(
            queue_name TEXT, asset_id INTEGER, ordinal INTEGER, status TEXT,
            current_attempt_id INTEGER, completed_at TEXT, result_json TEXT)""")
        db.execute("INSERT INTO review_queue VALUES ('benchmark-100-review-v1',1,0,'pending',NULL,NULL,NULL)")
        db.commit()

    summary = compile_audit(
        db_path, _materials(tmp_path / "material"), tmp_path / "audit",
        candidate_multiplier=1, minimum_candidates=1,
    )

    assert summary["status"] == "ready_for_sol_review"
    assert summary["registry"]["unfinished_review_items"] == 0
