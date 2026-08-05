"""Validation and authority gates for visual asset dispositions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


COMMISSION_STATUSES = {"fulfilled", "partially_fulfilled", "failed"}
ASSET_STATUSES = {"usable", "review", "unusable"}


class DispositionError(ValueError):
    pass


def validate_disposition(value: dict[str, Any]) -> None:
    required = {
        "schema_version",
        "asset_sha256",
        "display_filename",
        "review_status",
        "commission_status",
        "asset_status",
        "actual_facts",
        "potential_uses",
        "failure_reason",
        "evidence",
        "assistant",
        "sol_review",
    }
    if set(value) != required or value.get("schema_version") != "ninereeds_visual_asset_disposition_v1":
        raise DispositionError("invalid disposition fields or schema")
    if value["commission_status"] not in COMMISSION_STATUSES:
        raise DispositionError("invalid commission_status")
    if value["asset_status"] not in ASSET_STATUSES:
        raise DispositionError("invalid asset_status")
    if value["review_status"] not in {"assistant_proposal", "sol_verified"}:
        raise DispositionError("invalid review_status")
    if value["review_status"] == "assistant_proposal":
        if value["asset_status"] != "review" or value["sol_review"] is not None:
            raise DispositionError("assistant proposals must remain review pending Sol")
    else:
        review = value["sol_review"]
        if not isinstance(review, dict) or review.get("reviewer") != "sol":
            raise DispositionError("Sol-verified records require a Sol review")
    if value["commission_status"] == "fulfilled" and value["failure_reason"] is not None:
        raise DispositionError("fulfilled commissions cannot have a failure_reason")
    if value["commission_status"] != "fulfilled" and not value["failure_reason"]:
        raise DispositionError("non-fulfilled commissions require a failure_reason")
    facts = value["actual_facts"]
    if not isinstance(facts, list) or any(
        not isinstance(fact, dict)
        or set(fact) != {"fact", "evidence_keys"}
        or not isinstance(fact["fact"], str)
        or not fact["fact"].strip()
        or not isinstance(fact["evidence_keys"], list)
        or not fact["evidence_keys"]
        for fact in facts
    ):
        raise DispositionError("invalid actual_facts")
    uses = value["potential_uses"]
    if not isinstance(uses, list):
        raise DispositionError("invalid potential_uses")
    for use in uses:
        indexes = use.get("evidence_facts") if isinstance(use, dict) else None
        if not isinstance(indexes, list) or any(
            not isinstance(index, int) or isinstance(index, bool) or index < 0 or index >= len(facts)
            for index in indexes
        ):
            raise DispositionError("potential use references an invalid fact")


def finalize_by_sol(
    proposal: dict[str, Any],
    *,
    asset_status: str,
    accepted_use_indexes: list[int],
    verified_evidence_keys: list[str],
    reason: str,
) -> dict[str, Any]:
    """Create a final record without changing the original commission outcome."""
    validate_disposition(proposal)
    if asset_status not in ASSET_STATUSES or asset_status == "review":
        raise DispositionError("Sol must finalize as usable or unusable")
    uses = proposal["potential_uses"]
    if any(index < 0 or index >= len(uses) for index in accepted_use_indexes):
        raise DispositionError("accepted use index is out of range")
    if asset_status == "usable" and not accepted_use_indexes:
        raise DispositionError("usable assets require at least one accepted use")
    if asset_status == "unusable" and accepted_use_indexes:
        raise DispositionError("unusable assets cannot retain accepted uses")
    result = deepcopy(proposal)
    result["review_status"] = "sol_verified"
    result["asset_status"] = asset_status
    result["sol_review"] = {
        "reviewer": "sol",
        "accepted_use_indexes": accepted_use_indexes,
        "verified_evidence_keys": verified_evidence_keys,
        "reason": reason,
    }
    validate_disposition(result)
    return result
