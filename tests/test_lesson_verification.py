import hashlib
import json
from pathlib import Path

from image_benchmark.luna_lesson_worker import prompt_for
from image_registry.cli import connect
from image_registry.lesson_verification import export_results, initialize_queue, load_proposal


def _proposal(tmp_path: Path) -> tuple[Path, list[dict]]:
    image = tmp_path / "dog.jpg"
    image.write_bytes(b"dog image")
    row = {
        "item_id": "c0001-e1", "asset_id": 1, "path": str(image),
        "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "concept": "dog", "intended_teaching_claim": "A dog is here.",
        "query_tier": "exact", "verification_status": "pending_luna_pixel_verification",
    }
    path = tmp_path / "proposal.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return path, [row]


def test_lesson_queue_is_immutable_and_result_export_is_partitioned(tmp_path: Path) -> None:
    path, proposal = _proposal(tmp_path)
    with connect(tmp_path / "registry.sqlite3") as db:
        db.execute(
            """INSERT INTO asset(id,source,source_id,split,local_path,sha256,status)
               VALUES (1,'test','dog','train',?,?,'reviewed_usable')""",
            (proposal[0]["path"], proposal[0]["sha256"]),
        )
        db.commit()
        initialized = initialize_queue(
            db, load_proposal(path), selection_name="selection", queue_name="queue",
        )
        assert initialized["items"] == 1
        assert initialize_queue(
            db, load_proposal(path), selection_name="selection", queue_name="queue",
        )["queue_created"] is False
        db.execute(
            """UPDATE review_queue SET status='completed',completed_at=CURRENT_TIMESTAMP,result_json=?
               WHERE queue_name='queue'""",
            (json.dumps({"verdict": "accept", "claim_visibility": "direct"}),),
        )
        db.commit()
        summary = export_results(db, proposal, "queue", tmp_path / "results")
    assert summary == {
        "accepted": 1, "rejected": 0, "uncertain": 0, "unfinished": 0,
        "metadata_need_items": 0,
    }


def test_luna_prompt_requires_pixels_not_metadata(tmp_path: Path) -> None:
    _, proposal = _proposal(tmp_path)
    prompt = prompt_for(proposal[0])
    assert "A dog is here." in prompt
    assert "filename, metadata, captions" in prompt
    assert "wrong objects" in prompt
    assert "spelling “value”" in prompt


def test_load_proposal_accepts_acquisition_loop_exact_claim_field(tmp_path: Path) -> None:
    path, proposal = _proposal(tmp_path)
    row = proposal[0]
    row["exact_teaching_claim"] = row.pop("intended_teaching_claim")
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    loaded = load_proposal(path)

    assert loaded[0]["intended_teaching_claim"] == "A dog is here."
    assert loaded[0]["exact_teaching_claim"] == "A dog is here."


def test_export_combines_sol_residual_and_luna_rejection_for_metadata_search(tmp_path: Path) -> None:
    path, proposal = _proposal(tmp_path)
    wishlist = tmp_path / "wishlist.jsonl"
    wishlist.write_text(json.dumps({
        "concept": "cat", "item_ids": ["c0002-e1"],
        "teaching_needs": [{"item_id": "c0002-e1", "teaching_claim": "A cat is here."}],
        "gap_class": "genuine_material_gap", "acceptable_alternatives": ["kitten"],
    }) + "\n", encoding="utf-8")
    with connect(tmp_path / "registry.sqlite3") as db:
        db.execute(
            """INSERT INTO asset(id,source,source_id,split,local_path,sha256,status)
               VALUES (1,'test','dog','train',?,?,'reviewed_usable')""",
            (proposal[0]["path"], proposal[0]["sha256"]),
        )
        db.commit()
        initialize_queue(db, load_proposal(path), selection_name="selection", queue_name="queue")
        db.execute(
            """UPDATE review_queue SET status='completed',completed_at=CURRENT_TIMESTAMP,result_json=?
               WHERE queue_name='queue'""",
            (json.dumps({
                "verdict": "reject", "claim_visibility": "not_visible",
                "reason": "Only the word dog is visible.",
                "disqualifiers": ["overlaid_text_or_label", "claim_not_visible"],
            }),),
        )
        db.commit()
        summary = export_results(
            db, proposal, "queue", tmp_path / "results", base_wishlist=wishlist,
        )
    needs = [json.loads(line) for line in (tmp_path / "results/metadata_needs.jsonl").read_text().splitlines()]
    assert summary["metadata_need_items"] == 2
    assert [row["item_id"] for row in needs] == ["c0001-e1", "c0002-e1"]
    assert needs[0]["disqualifiers"] == ["overlaid_text_or_label", "claim_not_visible"]
    assert needs[1]["acceptable_alternatives"] == ["kitten"]
