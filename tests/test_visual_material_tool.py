import json
from pathlib import Path

import pytest

from image_registry.cli import connect
from image_registry.material_tool import fulfil_request, load_request


ROOT = Path(__file__).resolve().parents[1]


def _request(required_count: int = 2) -> dict:
    return {
        "schema_version": "ninereeds_visual_material_request_v1",
        "request_id": "material-test-under",
        "purpose": "Test material retrieval.",
        "teaching_claim": "The subject is under the object.",
        "target_concepts": ["under"],
        "candidate_queries": [
            {"tier": "exact", "fts_query": "dog AND under AND table", "rationale": "Exact."},
            {"tier": "semantic_equivalent", "fts_query": "under", "rationale": "Equivalent."},
        ],
        "required_count": required_count,
        "allowed_sources": [],
        "exclude_selections": ["protected-eval"],
        "intended_partition": "training",
        "fallback_order": ["registry_only", "minimal_flux_edit", "custom_flux_generation"],
        "acceptance_criteria": ["Relation is unambiguous."],
    }


def _asset(db, source_id: str, text: str, status: str = "reviewed_usable") -> int:
    cursor = db.execute(
        """INSERT INTO asset(source, source_id, split, local_path, sha256, width, height, status)
           VALUES ('test', ?, 'test', ?, ?, 640, 480, ?)""",
        (source_id, f"/images/{source_id}.jpg", source_id.rjust(64, "0")[-64:], status),
    )
    asset_id = cursor.lastrowid
    db.execute(
        "INSERT INTO text_record(asset_id, kind, text, author) VALUES (?, 'caption', ?, 'test')",
        (asset_id, text),
    )
    db.execute(
        "INSERT INTO text_search(asset_id, kind, text) VALUES (?, 'caption', ?)",
        (asset_id, text),
    )
    return asset_id


def test_material_request_example_is_schema_valid() -> None:
    request = load_request(
        ROOT / "mission_hub" / "research" / "examples" / "visual-material-request-example.json"
    )
    assert request["request_id"] == "material-under-training-v1"


def test_fulfilment_uses_only_reviewed_assets_and_respects_exclusions(tmp_path: Path) -> None:
    with connect(tmp_path / "registry.sqlite3") as db:
        exact = _asset(db, "1", "dog under table")
        equivalent = _asset(db, "2", "cat under tree")
        unreviewed = _asset(db, "3", "dog under table", "mechanically_valid")
        protected = _asset(db, "4", "dog under table")
        db.execute("INSERT INTO selection VALUES ('protected-eval', ?, 'eval', 0)", (protected,))
        db.commit()
        manifest = fulfil_request(db, _request(), "lesson-under-v1")
        assert manifest["status"] == "fulfilled_from_registry"
        assert [item["asset_id"] for item in manifest["assets"]] == [exact, equivalent]
        assert unreviewed not in {item["asset_id"] for item in manifest["assets"]}
        assert protected not in {item["asset_id"] for item in manifest["assets"]}
        assert manifest["commissioning_request"] is None
        rows = db.execute(
            "SELECT asset_id, stratum FROM selection WHERE name='lesson-under-v1' ORDER BY ordinal"
        ).fetchall()
        assert [tuple(row) for row in rows] == [(exact, "exact"), (equivalent, "semantic_equivalent")]


def test_residual_gap_is_structured_and_never_dispatches_generation(tmp_path: Path) -> None:
    with connect(tmp_path / "registry.sqlite3") as db:
        _asset(db, "1", "dog under table")
        db.commit()
        manifest = fulfil_request(db, _request(required_count=3), "lesson-under-gap")
        assert manifest["status"] == "residual_gap"
        assert manifest["selected_count"] == 1
        assert manifest["missing_count"] == 2
        gap = manifest["commissioning_request"]
        assert gap["authorization_status"] == "proposed_not_authorized"
        assert gap["generation_dispatched"] is False
        assert gap["fallback_order"] == ["minimal_flux_edit", "custom_flux_generation"]


def test_material_selection_is_immutable(tmp_path: Path) -> None:
    with connect(tmp_path / "registry.sqlite3") as db:
        _asset(db, "1", "dog under table")
        db.commit()
        fulfil_request(db, _request(required_count=1), "lesson-under-v1")
        with pytest.raises(ValueError, match="immutable"):
            fulfil_request(db, _request(required_count=1), "lesson-under-v1")
