import json

from image_registry.huggingface_dataset_catalog import (
    initial_url, link_next, normalize_dataset, parse_declared_count, rank, score_dataset,
)


def test_link_next_parses_pagination_header():
    assert link_next('<https://example.test/next>; rel="next"') == "https://example.test/next"
    assert link_next(None) is None


def test_parse_declared_count_accepts_formatted_card_values():
    assert parse_declared_count("109,686") == 109686
    assert parse_declared_count("about 12 500 examples") == 12500
    assert parse_declared_count(None) == 0


def test_catalog_url_requires_image_and_datasets_library():
    url = initial_url("https://example.test/api", 100)
    assert "modality%3Aimage" in url
    assert "library%3Adatasets" in url
    assert "%2C" in url


def test_normalize_finds_image_caption_and_class_labels():
    row = normalize_dataset({
        "id": "example/world",
        "downloads": 100,
        "cardData": {
            "license": "cc-by-4.0",
            "language": ["de", "ja"],
            "task_categories": ["image-to-text"],
            "dataset_info": {
                "features": [
                    {"name": "image", "dtype": "image"},
                    {"name": "caption", "dtype": "string"},
                    {"name": "image_url", "dtype": "string"},
                    {"name": "label", "dtype": "classlabel", "names": ["dog", "cat"]},
                ],
                "splits": [{"name": "train", "num_examples": 20}],
            },
        },
    })
    assert row["image_fields"] == ["image"]
    assert row["metadata_fields"] == ["caption", "label"]
    assert row["pixel_locator_fields"] == ["image_url"]
    assert row["class_names"] == ["cat", "dog"]
    assert row["metadata_searchable_structure"] is True
    assert row["num_examples_declared"] == 20
    assert row["languages"] == ["de", "ja"]


def test_score_prefers_general_caption_data_over_ocr():
    base = {
        "dataset_id": "example/world", "private": False, "disabled": False,
        "gated": False, "licenses": ["cc-by-4.0"], "image_fields": ["image"],
        "metadata_fields": ["caption"], "class_names": [], "downloads": 1000,
        "likes": 10, "task_categories": ["image-to-text"],
        "metadata_searchable_structure": True, "pretty_name": "Everyday scenes",
        "tags": ["caption", "object"],
    }
    good, _, _ = score_dataset(base, {"dog": 10})
    bad, _, _ = score_dataset({**base, "dataset_id": "example/medical-ocr", "tags": ["ocr", "medical"]}, {"dog": 10})
    assert good > bad


def test_rank_writes_bounded_candidates(tmp_path):
    catalog = tmp_path / "catalog.jsonl"
    catalog.write_text(json.dumps({
        "dataset_id": "example/world", "private": False, "disabled": False,
        "gated": False, "licenses": ["cc-by-4.0"], "image_fields": ["image"],
        "metadata_fields": ["caption"], "class_names": ["dog"], "downloads": 100,
        "likes": 1, "task_categories": ["image-to-text"], "tags": ["caption"],
        "metadata_searchable_structure": True,
    }) + "\n", encoding="utf-8")
    needs = tmp_path / "needs.jsonl"
    needs.write_text(json.dumps({"word": "dog"}) + "\n", encoding="utf-8")
    output = tmp_path / "ranking"
    summary = rank(catalog, needs, output, limit=1)
    assert summary["ranked_candidates"] == 1
    candidate = json.loads((output / "candidates.jsonl").read_text())
    assert candidate["dataset_id"] == "example/world"
    assert candidate["declared_concept_hits"] == ["dog"]
