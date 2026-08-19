import json
from pathlib import Path

import pytest

from image_registry.acquisition_reconciliation import reconcile


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_reconcile_requires_finished_gate(tmp_path: Path) -> None:
    verification = tmp_path / "verification"
    for name in ("accepted", "rejected", "uncertain"):
        _write(verification / f"{name}.jsonl", [])
    _write(verification / "unfinished.jsonl", [{"item_id": "c0001-e1"}])
    _write(tmp_path / "prior.jsonl", [])
    _write(tmp_path / "external.jsonl", [])
    _write(tmp_path / "decisions.jsonl", [])
    with pytest.raises(ValueError, match="unfinished"):
        reconcile(
            prior_accepted=tmp_path / "prior.jsonl", base_external=tmp_path / "external.jsonl",
            verification_dir=verification, decisions_path=tmp_path / "decisions.jsonl",
            output=tmp_path / "output",
        )


def test_reconcile_partitions_completed_gate(tmp_path: Path) -> None:
    verification = tmp_path / "verification"
    _write(verification / "accepted.jsonl", [{
        "item_id": "c0002-e1", "asset_id": "asset-new", "concept": "cat",
    }])
    _write(verification / "rejected.jsonl", [{
        "item_id": "c0003-e1", "asset_id": "asset-bad", "concept": "under",
        "exact_teaching_claim": "a cat under a table",
        "luna_result": {"reason": "The cat is beside the table.", "disqualifiers": ["wrong_relation"]},
    }])
    _write(verification / "uncertain.jsonl", [])
    _write(verification / "unfinished.jsonl", [])
    _write(tmp_path / "prior.jsonl", [{
        "item_id": "c0001-e1", "asset_id": "asset-prior", "concept": "dog",
    }])
    _write(tmp_path / "external.jsonl", [])
    _write(tmp_path / "decisions.jsonl", [
        {"item_id": "c0001-e1", "representation_class": "single_image"},
        {"item_id": "c0002-e1", "representation_class": "single_image"},
        {"item_id": "c0003-e1", "representation_class": "single_image"},
        {"item_id": "c0004-e1", "representation_class": "text_only"},
    ])

    summary = reconcile(
        prior_accepted=tmp_path / "prior.jsonl",
        base_external=tmp_path / "external.jsonl",
        verification_dir=verification,
        decisions_path=tmp_path / "decisions.jsonl",
        output=tmp_path / "output",
        expected_curriculum_items=4,
        expected_gate_items=2,
    )

    assert summary == {
        "schema_version": "ninereeds_acquisition_reconciliation_v1",
        "protected_selections": 2,
        "new_luna_accepts": 1,
        "new_luna_rejects": 1,
        "new_luna_uncertain": 0,
        "external_metadata_needs": 1,
        "non_single_or_nonvisual_dispositions": 1,
        "curriculum_items": 4,
        "status": "passed_incomplete_external_acquisition_pending",
    }
    external = [json.loads(line) for line in (tmp_path / "output/external_metadata_needs.jsonl").read_text().splitlines()]
    assert external[0]["item_id"] == "c0003-e1"
    assert external[0]["prior_excluded_asset_ids"] == ["asset-bad"]
    assert json.loads((tmp_path / "output/validation_report.json").read_text())["status"] == "passed"
