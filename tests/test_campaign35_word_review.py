from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from image_benchmark.campaign35_word_worker import collect_unique_target_words, parse_response, prompt_for_asset
from image_benchmark.luna_usability_worker import sync_unusable_queue
from image_registry.cli import connect
from image_registry.campaign35_word_review import initialize_queue


def _build_db(db_path: sqlite3.PathLike[str]) -> sqlite3.Connection:
    db = connect(db_path)
    for source_id in ("A", "B"):
        digest = hashlib.sha256(source_id.encode("utf-8")).hexdigest()
        db.execute(
            """INSERT INTO asset(source, source_id, split, local_path, sha256, status)
               VALUES ('test', ?, 'validation', ?, ?, 'reviewed_usable')""",
            (source_id, f"/images/{source_id}.jpg", digest),
        )
    db.commit()
    return db


def _binding(slot_id: str, asset_id: int, word: str, sequence_position: int) -> dict:
    return {
        "slot_id": slot_id,
        "asset_id": asset_id,
        "word": word,
        "concept": f"{word}-concept",
        "ordinal": 1,
        "exposure_index": 1,
        "sequence_position": sequence_position,
        "source_caption": "caption",
        "candidate_tier": "primary",
    }


def test_initialize_queue_requires_immutable_unique_assets_and_shared_slots(tmp_path):
    with _build_db(tmp_path / "registry.sqlite3") as db:
        result = initialize_queue(
            db,
            "campaign35-word-review-v1",
            [_binding("s-01", 1, "cat", 2), _binding("s-02", 1, "cat", 1)],
            selection_name="campaign35-word-review-v1-sel",
        )
        assert result["slot_bindings"] == 2
        assert result["items"] == 1
        assert result["bindings_created"] is True
        assert db.execute(
            "SELECT COUNT(*) FROM campaign35_word_review_slot_binding WHERE queue_name=?",
            ("campaign35-word-review-v1",),
        ).fetchone()[0] == 2
        assert db.execute(
            "SELECT COUNT(*) FROM selection WHERE name=?",
            ("campaign35-word-review-v1-sel",),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT COUNT(*) FROM review_queue WHERE queue_name=?",
            ("campaign35-word-review-v1",),
        ).fetchone()[0] == 1


def test_prompt_groups_unique_targets_per_asset():
    bindings = [
        {"slot_id": "s1", "word": "Dog", "asset_id": 1, "sequence_position": 3},
        {"slot_id": "s2", "word": "cat", "asset_id": 1, "sequence_position": 1},
        {"slot_id": "s3", "word": "dog", "asset_id": 1, "sequence_position": 2},
    ]
    prompt = prompt_for_asset(bindings)
    assert "- cat" in prompt
    assert "- dog" in prompt
    assert prompt.count("- cat") == 1
    assert prompt.count("- dog") == 1
    assert collect_unique_target_words(bindings) == ["cat", "dog"]


def test_exact_target_coverage_is_validated_and_reported():
    response = {
        "admission": "usable",
        "visible_text": False,
        "watermark": False,
        "quality_flags": [],
        "literal_caption": "A cat and dog.",
        "targets": [
            {"word": "dog", "visible": True, "evidence": "A dog is visible."},
            {"word": "cat", "visible": False, "evidence": "No cat."},
        ],
        "uncertainties": [],
    }
    parsed, errors = parse_response(json.dumps(response), ["cat", "dog"])
    assert parsed == response
    assert errors == []
    _, missing = parse_response(json.dumps({**response, "targets": [{"word": "cat", "visible": True, "evidence": "x"}]}), ["cat", "dog"])
    assert any(err.startswith("targets:missing:") for err in missing)
    _, extra = parse_response(json.dumps({**response, "targets": [
        {"word": "cat", "visible": True, "evidence": "x"},
        {"word": "dog", "visible": True, "evidence": "x"},
        {"word": "horse", "visible": False, "evidence": "x"},
    ]}), ["cat", "dog"])
    assert any(err.startswith("targets:extra:") for err in extra)
    _, empty_caption = parse_response(json.dumps({**response, "literal_caption": "  "}), ["cat", "dog"])
    assert "literal_caption:empty" in empty_caption


def test_initialize_queue_rerun_matches_or_rejects_on_mismatch(tmp_path):
    with _build_db(tmp_path / "registry.sqlite3") as db:
        first = initialize_queue(
            db,
            "campaign35-word-review-v2",
            [_binding("s-01", 1, "cat", 1), _binding("s-02", 2, "dog", 2)],
            selection_name="campaign35-word-review-v2-sel",
        )
        second = initialize_queue(
            db,
            "campaign35-word-review-v2",
            [_binding("s-01", 1, "cat", 1), _binding("s-02", 2, "dog", 2)],
            selection_name="campaign35-word-review-v2-sel",
        )
        assert first["selection_created"]
        assert not second["selection_created"]
        assert not second["queue_created"]
        assert not second["bindings_created"]

        with pytest.raises(ValueError, match="immutable"):
            initialize_queue(
                db,
                "campaign35-word-review-v2",
                [_binding("s-01", 1, "bird", 1), _binding("s-02", 2, "dog", 2)],
                selection_name="campaign35-word-review-v2-sel",
            )


def test_usability_escalation_includes_usable_records_with_uncertainties(tmp_path):
    with _build_db(tmp_path / "registry.sqlite3") as db:
        initialize_queue(
            db,
            "semantic",
            [_binding("s-01", 1, "cat", 1), _binding("s-02", 2, "dog", 2)],
        )
        records = [
            {"parsed": {"admission": "usable", "uncertainties": ["blur"]}},
            {"parsed": {"admission": "usable", "uncertainties": []}},
        ]
        for asset_id, record in enumerate(records, 1):
            db.execute(
                "UPDATE review_queue SET status='completed',result_json=? WHERE queue_name='semantic' AND asset_id=?",
                (json.dumps(record), asset_id),
            )
        db.commit()
        assert sync_unusable_queue(db, "semantic", "usability") == 1
        assert db.execute(
            "SELECT asset_id FROM review_queue WHERE queue_name='usability'"
        ).fetchone()[0] == 1
