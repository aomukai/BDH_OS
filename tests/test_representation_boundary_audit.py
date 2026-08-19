import pytest

from image_registry.representation_boundary_audit import validate


def test_boundary_schema_consistency() -> None:
    assert validate({
        "verdict": "confirm_single_image", "representation_class": "single_image",
        "reason": "Directly visible.", "visible_criterion": "one dog",
    })["verdict"] == "confirm_single_image"
    with pytest.raises(ValueError, match="must choose another"):
        validate({
            "verdict": "reclassify", "representation_class": "single_image",
            "reason": "No.", "visible_criterion": "none",
        })
