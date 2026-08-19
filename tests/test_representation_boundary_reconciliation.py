import pytest

from image_registry.representation_boundary_reconciliation import reconcile


def test_reconciles_audited_single_and_gemma_non_single() -> None:
    needs = [{"item_id": "a"}, {"item_id": "b"}]
    proposal = [
        {"item_id": "a", "representation_class": "single_image"},
        {"item_id": "b", "representation_class": "image_sequence"},
    ]
    audit = [{"item_id": "a", "representation_class": "image_plus_context"}]
    single, dispositions, summary = reconcile(needs, proposal, audit)
    assert not single
    assert [row["representation_class"] for row in dispositions] == [
        "image_plus_context", "image_sequence",
    ]
    assert summary["input_residual_items"] == 2


def test_requires_audit_of_every_proposed_single() -> None:
    with pytest.raises(ValueError, match="every proposed single"):
        reconcile(
            [{"item_id": "a"}], [{"item_id": "a", "representation_class": "single_image"}], [],
        )
