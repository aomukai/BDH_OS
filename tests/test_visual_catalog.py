from __future__ import annotations

import io

import pytest
Image = pytest.importorskip("PIL.Image")

from training.pipeline.visual.catalog import AssetCatalog, CatalogError


def _jpeg() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 24), (120, 70, 30)).save(output, format="JPEG")
    return output.getvalue()


def _record() -> dict:
    return {
        "display_filename": "dog_202607312305.jpg",
        "family_id": "oxford:dachshund:001",
        "split": "train",
        "description": {
            "text": "A young brown dachshund lies in grass in front of a barn, playing with a red ball.",
            "status": "human_verified",
            "author": "operator",
            "model_id": None,
            "model_revision": None,
        },
        "search_terms": ["dog", "brown", "dachshund", "grass", "barn", "red ball", "in front of"],
        "facts": [{"text": "the dog is in front of a barn", "status": "human_verified", "confidence": 1.0, "evidence": "visible"}],
        "claims": [{"text": "a dog", "status": "accepted", "verified_by": ["operator"]}],
        "source": {"kind": "dataset", "dataset": "Oxford-IIIT Pet", "item_id": "dog-1", "license": "CC-BY-SA-4.0", "attribution": "Oxford-IIIT Pet"},
        "lineage": {"parent_sha256": None, "model_id": None, "model_revision": None, "prompt": None, "seed": None, "intended_delta": None},
    }


def test_catalog_is_content_addressed_searchable_and_grep_friendly(tmp_path) -> None:
    catalog = AssetCatalog(tmp_path)
    record = catalog.import_bytes(_jpeg(), _record())

    assert (tmp_path / record["object_path"]).is_file()
    assert catalog.search('"in front of"')[0]["asset_sha256"] == record["asset_sha256"]
    assert "red ball" in catalog.jsonl_path.read_text(encoding="utf-8")


def test_same_pixels_cannot_silently_change_metadata(tmp_path) -> None:
    catalog = AssetCatalog(tmp_path)
    catalog.import_bytes(_jpeg(), _record())
    changed = _record()
    changed["split"] = "test"

    with pytest.raises(CatalogError, match="different metadata"):
        catalog.import_bytes(_jpeg(), changed)


def test_annotation_revisions_are_searchable_and_preserve_history(tmp_path) -> None:
    catalog = AssetCatalog(tmp_path)
    record = catalog.import_bytes(_jpeg(), _record())
    revised = catalog.revise_annotations(
        record["asset_sha256"],
        description={**record["description"], "text": "A brown dog beside a doghouse."},
        search_terms=["brown dog", "doghouse", "beside"],
        facts=record["facts"],
        claims=record["claims"],
    )

    assert catalog.search("doghouse")[0]["description"] == revised["description"]
    with catalog._connect() as connection:
        assert connection.execute("SELECT count(*) FROM asset_revisions").fetchone()[0] == 1
