import json
from pathlib import Path

from image_registry.cli import connect
from image_registry.open_images_claim_proposal import build


def test_selects_first_reviewed_candidate_and_reports_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "registry.sqlite3"
    candidates = tmp_path / "candidates.jsonl"
    rows = []
    for item, source, rank in (("one", "bad", 1), ("one", "good", 2), ("two", "bad-two", 1)):
        rows.append({
            "item_id": item, "source_image_id": source, "candidate_rank": rank,
            "concept": "dog", "exact_teaching_claim": "A dog is visible.",
            "retrieval_evidence": {"kind": "exact_concept_object_annotation"},
            "source_metadata": {"license_url": "CC"},
        })
    candidates.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    with connect(db_path) as db:
        for source, status in (("bad", "reviewed_unusable"), ("good", "reviewed_usable"), ("bad-two", "reviewed_unusable")):
            db.execute(
                """INSERT INTO asset(source,source_id,split,local_path,sha256,status)
                   VALUES ('open_images_v7',?,'train',?,? ,?)""",
                (source, f"/{source}.jpg", source * 8, status),
            )
        db.commit()
        proposals, unresolved = build(db, candidates)
    assert proposals[0]["source_image_id"] == "good"
    assert proposals[0]["verification_status"] == "pending_luna_pixel_verification"
    assert unresolved[0]["item_id"] == "two"

    prior = tmp_path / "prior"
    prior.mkdir()
    for name, values in (
        ("accepted", [{"item_id": "two", "asset_id": 99}]),
        ("rejected", [{"item_id": "one", "asset_id": proposals[0]["asset_id"]}]),
        ("uncertain", []),
    ):
        (prior / f"{name}.jsonl").write_text(
            "".join(json.dumps(value) + "\n" for value in values), encoding="utf-8",
        )
    with connect(db_path) as db:
        second, second_unresolved = build(db, candidates, [prior])
    assert not second
    assert second_unresolved[0]["item_id"] == "one"
