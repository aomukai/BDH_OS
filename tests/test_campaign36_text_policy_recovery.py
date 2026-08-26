from pathlib import Path

from image_registry.campaign36_text_policy_recovery import semantic_clean


def clean_decision():
    return {
        "failure_reasons": ["visible_text"],
        "luna_result": {
            "admission": "usable",
            "visible_text": True,
            "watermark": False,
            "quality_flags": [],
            "uncertainties": [],
            "targets": [{"concept_id": "yeast", "verdict": "present"}],
        },
    }


def test_semantic_clean_accepts_retired_outer_veto_only():
    assert semantic_clean(clean_decision())


def test_semantic_clean_rejects_spelling_or_other_quality_concern():
    row = clean_decision()
    row["failure_reasons"] = ["visible_text", "quality:malformed spelling"]
    row["luna_result"]["quality_flags"] = ["malformed spelling"]
    assert not semantic_clean(row)


def test_semantic_clean_rejects_uncertainty():
    row = clean_decision()
    row["luna_result"]["uncertainties"] = ["label partly occluded"]
    assert not semantic_clean(row)
