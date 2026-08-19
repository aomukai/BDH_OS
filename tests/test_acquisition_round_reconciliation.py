import json
from pathlib import Path

from image_registry.acquisition_round_reconciliation import reconcile


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_reconciles_multiple_external_passes(tmp_path: Path) -> None:
    _write(tmp_path / "protected.jsonl", [{"item_id": "p", "asset_id": 1}])
    _write(tmp_path / "external.jsonl", [
        {"item_id": "a", "status": "pending"}, {"item_id": "b", "status": "pending"},
    ])
    _write(tmp_path / "decisions.jsonl", [
        {"item_id": "p", "representation_class": "single_image"},
        {"item_id": "a", "representation_class": "single_image"},
        {"item_id": "b", "representation_class": "single_image"},
        {"item_id": "t", "representation_class": "text_only"},
    ])
    for number, buckets in enumerate((
        {"accepted": [], "rejected": [("a", 2)], "uncertain": []},
        {"accepted": [("a", 3)], "rejected": [("b", 4)], "uncertain": []},
    ), 1):
        root = tmp_path / f"v{number}"
        _write(root / "unfinished.jsonl", [])
        for name, values in buckets.items():
            _write(root / f"{name}.jsonl", [
                {"item_id": item, "asset_id": asset, "source_image_id": str(asset),
                 "luna_result": {"verdict": name[:-2] if name.endswith("ed") else name,
                                 "reason": name, "disqualifiers": []}}
                for item, asset in values
            ])
    summary = reconcile(
        protected_path=tmp_path / "protected.jsonl", external_path=tmp_path / "external.jsonl",
        decisions_path=tmp_path / "decisions.jsonl",
        verification_dirs=[tmp_path / "v1", tmp_path / "v2"], output=tmp_path / "out",
        expected_curriculum_items=4,
    )
    assert summary["new_external_accepts"] == 1
    assert summary["protected_selections"] == 2
    assert summary["external_metadata_needs"] == 1
    remaining = json.loads((tmp_path / "out/external_metadata_needs.jsonl").read_text())
    assert len(remaining["acquisition_attempts"]) == 1
