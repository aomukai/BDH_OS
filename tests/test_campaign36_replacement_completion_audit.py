import argparse
import json

from image_registry.campaign36_replacement_completion_audit import audit
from image_registry.campaign36_replacement_generation_queue import connect, sync


def write_jsonl(path, values):
    path.write_text("".join(json.dumps(row) + "\n" for row in values), encoding="utf-8")


def test_completion_audit_publishes_manifest_only_after_every_invariant_passes(tmp_path):
    db_path = tmp_path / "registry.sqlite3"
    requirements = tmp_path / "requirements.jsonl"
    retained = tmp_path / "retained.jsonl"
    replacements = tmp_path / "replacements.jsonl"
    replacement_map = tmp_path / "replacement-map.jsonl"
    reconciliation = tmp_path / "summary.json"
    report = tmp_path / "audit.json"
    manifest = tmp_path / "final.jsonl"

    requirement_rows = []
    retained_rows = []
    replacement_rows = []
    for ordinal, word in ((1, "cat"), (2, "dog")):
        for exposure in range(1, 11):
            slot = f"c{ordinal:04d}-i{exposure:02d}"
            requirement_rows.append({"slot_id": slot, "word": word, "concept_id": word})
            image = tmp_path / f"{word}-{exposure}.png"
            image.write_bytes(f"{word}-{exposure}".encode())
            row = {
                "slot_id": slot,
                "word": word,
                "concept_id": word,
                "sha256": f"{ordinal:02d}{exposure:02d}",
                "local_path": str(image),
                "status": "reviewed_usable",
                "watermark": False,
                "disposition": "accepted",
            }
            (retained_rows if word == "cat" else replacement_rows).append(row)
    write_jsonl(requirements, requirement_rows)
    write_jsonl(retained, retained_rows)
    write_jsonl(replacements, replacement_rows)
    write_jsonl(
        replacement_map,
        [{"new_word": "dog", "new_concept_id": "dog", "new_teaching_sense": "a dog", "ordinal": 2}],
    )
    reconciliation.write_text(
        json.dumps(
            {
                "semantic_unfinished_claims": 0,
                "cascade_unfinished_claims": 0,
                "residual_images": 0,
                "selected_slots": 10,
            }
        ),
        encoding="utf-8",
    )
    with connect(db_path) as db:
        sync(
            db,
            replacement_map=replacement_map,
            selected_assets=replacements,
            reviews_complete=True,
        )
        db.execute(
            """CREATE TABLE review_queue(
                   queue_name TEXT NOT NULL,status TEXT NOT NULL,result_json TEXT
               )"""
        )
        db.execute(
            """CREATE TABLE campaign35_word_review_slot_binding(
                   queue_name TEXT NOT NULL,teaching_sense TEXT
               )"""
        )
        provenance = json.dumps({"prompt_version": "campaign35-word-review-v2-exact-sense"})
        db.executemany(
            "INSERT INTO review_queue(queue_name,status,result_json) VALUES (?,'completed',?)",
            [
                ("campaign36-visual-vocab-replacements-metadata-v1-semantic", provenance),
                ("campaign36-visual-vocab-replacements-local-v1-semantic", provenance),
            ],
        )
        db.executemany(
            """INSERT INTO campaign35_word_review_slot_binding(queue_name,teaching_sense)
               VALUES (?,?)""",
            [
                ("campaign36-visual-vocab-replacements-metadata-v1-semantic", "a dog"),
                ("campaign36-visual-vocab-replacements-local-v1-semantic", "a dog"),
            ],
        )
        db.commit()

    args = argparse.Namespace(
        db=db_path,
        requirements=requirements,
        retained=retained,
        replacements=replacements,
        reconciliation_summary=reconciliation,
        output=report,
        final_manifest=manifest,
        images_per_word=10,
        reuse_cap=4,
        verify_content_hashes=False,
    )
    result = audit(args)
    assert result["complete"] is True
    assert result["combined_assets"] == 20
    assert result["max_image_reuse"] == 1
    assert manifest.is_file()
    assert len(manifest.read_text(encoding="utf-8").splitlines()) == 20

    replacement_rows[0]["disposition"] = "rejected_watermark"
    write_jsonl(replacements, replacement_rows)
    result = audit(args)
    assert result["complete"] is False
    assert any("accepted disposition" in error for error in result["errors"])


def test_completion_audit_keeps_homonymous_concepts_separate(tmp_path):
    """Two concepts may intentionally share one surface word and still get 10 each."""
    db_path = tmp_path / "registry.sqlite3"
    requirements = tmp_path / "requirements.jsonl"
    retained = tmp_path / "retained.jsonl"
    replacements = tmp_path / "replacements.jsonl"
    replacement_map = tmp_path / "replacement-map.jsonl"
    reconciliation = tmp_path / "summary.json"
    report = tmp_path / "audit.json"
    manifest = tmp_path / "final.jsonl"

    requirement_rows = []
    retained_rows = []
    replacement_rows = []
    for ordinal, concept_id in ((1, "nail"), (2, "nail_2")):
        for exposure in range(1, 11):
            slot = f"c{ordinal:04d}-i{exposure:02d}"
            requirement_rows.append({"slot_id": slot, "word": "nail", "concept_id": concept_id})
            image = tmp_path / f"{concept_id}-{exposure}.png"
            image.write_bytes(f"{concept_id}-{exposure}".encode())
            row = {
                "slot_id": slot,
                "word": "nail",
                "concept_id": concept_id,
                "sha256": f"{ordinal:02d}{exposure:02d}",
                "local_path": str(image),
                "disposition": "accepted",
            }
            (retained_rows if ordinal == 1 else replacement_rows).append(row)
    write_jsonl(requirements, requirement_rows)
    write_jsonl(retained, retained_rows)
    write_jsonl(replacements, replacement_rows)
    write_jsonl(
        replacement_map,
        [{"new_word": "nail", "new_concept_id": "nail_2", "new_teaching_sense": "finger nail", "ordinal": 2}],
    )
    reconciliation.write_text(json.dumps({
        "semantic_unfinished_claims": 0,
        "cascade_unfinished_claims": 0,
        "residual_images": 0,
        "selected_slots": 10,
    }))
    with connect(db_path) as db:
        sync(db, replacement_map=replacement_map, selected_assets=replacements, reviews_complete=True)
        db.execute("CREATE TABLE review_queue(queue_name TEXT,status TEXT,result_json TEXT)")
        db.execute("CREATE TABLE campaign35_word_review_slot_binding(queue_name TEXT,teaching_sense TEXT)")
        provenance = json.dumps({"prompt_version": "campaign35-word-review-v2-exact-sense"})
        for pool in ("metadata", "local"):
            queue = f"campaign36-visual-vocab-replacements-{pool}-v1-semantic"
            db.execute("INSERT INTO review_queue VALUES (?,'completed',?)", (queue, provenance))
            db.execute("INSERT INTO campaign35_word_review_slot_binding VALUES (?,?)", (queue, "nail sense"))
        db.commit()

    result = audit(argparse.Namespace(
        db=db_path,
        requirements=requirements,
        retained=retained,
        replacements=replacements,
        reconciliation_summary=reconciliation,
        output=report,
        final_manifest=manifest,
        images_per_word=10,
        reuse_cap=4,
        verify_content_hashes=False,
    ))
    assert result["complete"] is True
    assert result["words"] == 2
    assert result["teaching_contracts"] == 2
    assert result["unique_surface_words"] == 1
