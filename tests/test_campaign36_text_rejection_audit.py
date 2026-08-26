from image_registry.campaign36_text_rejection_audit import semantic_pass, text_related


def test_text_related_reasons_are_narrow():
    assert text_related("visible_text")
    assert text_related("quality:Visible writing on the packet")
    assert not text_related("quality:malformed hand")


def test_semantic_pass_requires_every_target_and_no_uncertainty():
    result = {
        "admission": "usable", "watermark": False, "uncertainties": [],
        "targets": [{"concept_id": "yeast", "verdict": "present"}],
    }
    assert semantic_pass(result)
    result["uncertainties"] = ["maybe"]
    assert not semantic_pass(result)
