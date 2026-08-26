from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from image_benchmark.campaign35_word_worker import collect_target_senses, collect_unique_target_words, parse_response, prompt_for_asset
from image_benchmark.luna_usability_worker import sync_unusable_queue
from image_benchmark.luna_campaign_word_worker import coalesce_sense_targets
from image_registry.cli import connect
from image_registry.campaign35_word_review import initialize_queue
from image_benchmark.luna_terminal_semantic_worker import (
    PROMPT_VERSION,
    project_completed_fallbacks,
    sync_terminal_failures,
)


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
        {"slot_id": "s1", "word": "Dog", "asset_id": 1, "sequence_position": 3, "teaching_sense": "a domestic canine"},
        {"slot_id": "s2", "word": "cat", "asset_id": 1, "sequence_position": 1, "teaching_sense": "a domestic feline"},
        {"slot_id": "s3", "word": "dog", "asset_id": 1, "sequence_position": 2, "teaching_sense": "a domestic canine"},
    ]
    prompt = prompt_for_asset(bindings)
    assert "- cat — REQUIRED SENSE: a domestic feline" in prompt
    assert "- dog — REQUIRED SENSE: a domestic canine" in prompt
    assert prompt.count("REQUIRED SENSE: a domestic feline") == 1
    assert prompt.count("REQUIRED SENSE: a domestic canine") == 1
    assert collect_unique_target_words(bindings) == ["cat", "dog"]
    assert collect_target_senses(bindings) == {
        "cat": ["a domestic feline"], "dog": ["a domestic canine"],
    }


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


def test_luna_per_sense_rows_coalesce_to_one_surface_term():
    result = coalesce_sense_targets([
        {"word": "credit (financial)", "visible": True, "evidence": "A credit card is visible."},
        {"word": "credit (academic)", "visible": False, "evidence": "No coursework is shown."},
    ], ["credit"])
    assert result == [{
        "word": "credit", "visible": True,
        "evidence": "A credit card is visible.; No coursework is shown.",
    }]


def test_luna_surface_lemma_maps_to_one_disambiguated_contract_only():
    assert coalesce_sense_targets([
        {"word": "sole", "visible": True, "evidence": "The sole is visible."},
    ], ["sole (of foot)"]) == [{
        "word": "sole (of foot)", "visible": True,
        "evidence": "The sole is visible.",
    }]

    # A bare lemma cannot safely choose between two simultaneous senses.
    ambiguous = {"word": "bank", "visible": True, "evidence": "A bank is visible."}
    assert coalesce_sense_targets(
        [ambiguous], ["bank (river)", "bank (financial)"],
    ) == [ambiguous]


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


def test_terminal_semantic_fallback_preserves_failure_and_projects_exact_result(tmp_path):
    with _build_db(tmp_path / "registry.sqlite3") as db:
        initialize_queue(
            db, "semantic", [_binding("s-01", 1, "cat", 1)],
        )
        db.execute(
            "UPDATE review_queue SET status='failed' WHERE queue_name='semantic' AND asset_id=1"
        )
        db.commit()
        assert sync_terminal_failures(db, "semantic", "semantic-luna-fallback") == 1
        record = {
            "prompt_version": PROMPT_VERSION,
            "backend": "codex-luna-terminal-fallback",
            "parsed": {
                "admission": "usable", "visible_text": False, "watermark": False,
                "quality_flags": [], "literal_caption": "A cat.",
                "targets": [{"word": "cat", "visible": True, "evidence": "A cat."}],
                "uncertainties": [],
            },
            "schema_errors": [],
        }
        db.execute(
            """UPDATE review_queue SET status='completed',completed_at='2026-01-01T00:00:00Z',
                      result_json=? WHERE queue_name='semantic-luna-fallback' AND asset_id=1""",
            (json.dumps(record),),
        )
        db.commit()
        assert project_completed_fallbacks(db, "semantic", "semantic-luna-fallback") == 1
        projected = db.execute(
            "SELECT status,result_json FROM review_queue WHERE queue_name='semantic' AND asset_id=1"
        ).fetchone()
        assert projected["status"] == "completed"
        assert json.loads(projected["result_json"])["backend"] == "codex-luna-terminal-fallback"
        assert sync_terminal_failures(db, "semantic", "semantic-luna-fallback") == 0
