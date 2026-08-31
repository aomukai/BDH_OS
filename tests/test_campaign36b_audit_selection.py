from __future__ import annotations

from meta.scripts.audit_campaign36b_anatomy import compare, event_identity


def test_event_identity_binds_order_and_asset() -> None:
    event = {"ordinal": 7, "asset_sha256": "a" * 64}
    first = event_identity("session", 0, event)
    assert first != event_identity("session", 1, event)
    assert first.endswith("|7|" + "a" * 64)


def test_ablation_comparison_uses_positive_delta_for_helpful_cohort() -> None:
    enabled = {
        "a": {"nll": 1.0, "exact": True},
        "b": {"nll": 2.0, "exact": False},
    }
    ablated = {
        "a": {"nll": 1.2, "exact": False},
        "b": {"nll": 2.1, "exact": False},
    }
    result = compare(enabled, ablated)
    assert result["median_delta_nll"] == 0.15000000000000002
    assert result["helpful_fraction"] == 1.0
    assert result["exact_lost_when_ablated"] == 1
