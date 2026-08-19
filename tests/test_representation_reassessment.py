import json

import pytest

from image_registry.representation_reassessment import make_batches, parse_document


def test_batches_keep_concept_siblings_together() -> None:
    needs = [
        {"item_id": "a1", "concept": "quarter", "exact_teaching_claim": "A quarter is round."},
        {"item_id": "a2", "concept": "quarter", "exact_teaching_claim": "A quarter buys things."},
        {"item_id": "b1", "concept": "dog", "exact_teaching_claim": "A dog is here."},
    ]
    batches = make_batches(needs, [], 2)
    assert [[row["item_id"] for row in batch] for batch in batches] == [["a1", "a2"], ["b1"]]
    assert batches[0][0]["sibling_claims_for_sense_disambiguation"] == [
        "A quarter is round.", "A quarter buys things.",
    ]


def test_parser_rejects_missing_or_open_ended_answers() -> None:
    valid = {"decisions": [{
        "item_id": "a", "representation_class": "single_image", "claim_quality": "valid",
        "confidence": "high", "reason": "Visible.", "visible_criterion": "a dog",
    }]}
    assert parse_document(json.dumps(valid), {"a"})[0]["item_id"] == "a"
    valid["decisions"][0]["representation_class"] = "something_else"
    with pytest.raises(ValueError, match="invalid representation"):
        parse_document(json.dumps(valid), {"a"})


def test_parser_normalizes_quality_label_in_wrong_field() -> None:
    document = {"decisions": [{
        "item_id": "a", "representation_class": "placeholder", "claim_quality": "valid",
        "confidence": "high", "reason": "Malformed placeholder.", "visible_criterion": "none",
    }]}
    row = parse_document(json.dumps(document), {"a"})[0]
    assert row["representation_class"] == "not_visually_teachable"
    assert row["claim_quality"] == "placeholder"
    assert row["normalization"] == "claim_quality_returned_in_representation_field"
