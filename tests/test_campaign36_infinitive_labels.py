from __future__ import annotations

import argparse
import json

import pytest

from image_registry.campaign36_infinitive_labels import publish


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def source_rows():
    rows = []
    for ordinal, concept_id, word, pos, sense in (
        (1, "paint", "paint", "noun", "colored liquid"),
        (2, "paint_2", "paint", "verb", "apply colored liquid"),
    ):
        for index in range(1, 11):
            rows.append({
                "ordinal": ordinal,
                "concept_id": concept_id,
                "word": word,
                "part_of_speech": pos,
                "teaching_sense": sense,
                "slot_id": f"c{ordinal:04d}-i{index:02d}",
                "sha256": f"{ordinal:02d}{index:02d}",
                "schema_version": "source",
            })
    return rows


def decisions():
    return [
        {
            "ordinal": 1,
            "concept_id": "paint",
            "original_word": "paint",
            "decision": "not_verb",
            "verified_part_of_speech": "noun",
            "proposed_display_label": "paint",
            "confidence": "high",
            "rationale": "material noun",
            "image_fit_count": 10,
            "image_mismatch_count": 0,
            "image_mismatch_slots": [],
            "image_contract_assessment": "pass",
        },
        {
            "ordinal": 2,
            "concept_id": "paint_2",
            "original_word": "paint",
            "decision": "verified_verb",
            "verified_part_of_speech": "verb",
            "proposed_display_label": "to paint",
            "confidence": "high",
            "rationale": "application action",
            "image_fit_count": 9,
            "image_mismatch_count": 1,
            "image_mismatch_slots": ["c0002-i03"],
            "image_contract_assessment": "partial",
        },
    ]


def args(tmp_path, manifest, ledger):
    return argparse.Namespace(
        manifest=manifest,
        decisions=ledger,
        output=tmp_path / "out",
        images_per_contract=10,
        expected_rows=20,
        expected_contracts=2,
    )


def test_publish_distinguishes_noun_and_verb(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    write_jsonl(manifest, source_rows())
    write_jsonl(ledger, decisions())

    report = publish(args(tmp_path, manifest, ledger))
    output = [
        json.loads(line)
        for line in (tmp_path / "out" / "teaching-contracts.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [row["word"] for row in output] == ["paint", "to paint"]
    assert output[1]["lemma"] == "paint"
    assert report["unique_display_labels"] == 2
    assert report["display_label_collision_groups"] == 0
    assert report["label_migration_complete"] is True
    assert report["training_ready"] is False


def test_rejects_nonverb_label_change(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    ledger = tmp_path / "ledger.jsonl"
    write_jsonl(manifest, source_rows())
    bad = decisions()
    bad[0]["proposed_display_label"] = "a paint"
    write_jsonl(ledger, bad)

    from image_registry.campaign36_infinitive_labels import (
        contracts_by_ordinal,
        validated_decisions,
    )

    with pytest.raises(ValueError, match="non-verb decision changes the label"):
        validated_decisions(ledger, contracts_by_ordinal(source_rows()))


def test_derives_missing_ordinal_from_slot_id():
    from image_registry.campaign36_infinitive_labels import row_ordinal

    assert row_ordinal({"slot_id": "c0626-i07"}) == 626
    with pytest.raises(ValueError, match="disagrees"):
        row_ordinal({"ordinal": 625, "slot_id": "c0626-i07"})
