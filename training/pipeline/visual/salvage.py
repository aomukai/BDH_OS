"""Bounded alternative-use proposals for failed visual commissions."""

from __future__ import annotations

import json
from typing import Any


SALVAGE_BUCKETS = {"propose_use", "discard", "needs_visual_recheck"}
USE_KINDS = {
    "cardinality_label",
    "comparative_series_member",
    "increment_or_decrement_pair",
    "count_question",
    "descriptive_sentence",
    "contrastive_negative",
}


def parse_salvage_response(text: str) -> list[dict[str, Any]]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = "\n".join(candidate.splitlines()[1:-1]).strip()
    value = json.loads(candidate)
    if not isinstance(value, list):
        raise ValueError("salvage response must be a JSON array")
    rows = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "asset_sha256",
            "bucket",
            "candidate_uses",
            "reason",
        }:
            raise ValueError("salvage response item does not match the v1 schema")
        asset = item["asset_sha256"]
        if not isinstance(asset, str) or len(asset) != 64:
            raise ValueError("invalid salvage asset_sha256")
        if item["bucket"] not in SALVAGE_BUCKETS:
            raise ValueError("invalid salvage bucket")
        reason = item["reason"]
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError("invalid salvage reason")
        uses = item["candidate_uses"]
        if not isinstance(uses, list) or len(uses) > 8:
            raise ValueError("candidate_uses must be a bounded list")
        parsed_uses = []
        for use in uses:
            if not isinstance(use, dict) or set(use) != {
                "kind",
                "teaching_goal",
                "evidence_keys",
                "paired_asset_sha256s",
                "constraints",
            }:
                raise ValueError("candidate use does not match the v1 schema")
            if use["kind"] not in USE_KINDS:
                raise ValueError("invalid salvage use kind")
            if not isinstance(use["teaching_goal"], str) or not use["teaching_goal"].strip():
                raise ValueError("salvage teaching_goal must be non-empty")
            if not isinstance(use["evidence_keys"], list) or not all(
                isinstance(key, str) and key for key in use["evidence_keys"]
            ):
                raise ValueError("salvage evidence_keys must be strings")
            pairs = use["paired_asset_sha256s"]
            if not isinstance(pairs, list) or not all(
                isinstance(pair, str) and len(pair) == 64 for pair in pairs
            ):
                raise ValueError("invalid paired_asset_sha256s")
            if not isinstance(use["constraints"], list) or not all(
                isinstance(constraint, str) and constraint for constraint in use["constraints"]
            ):
                raise ValueError("salvage constraints must be strings")
            parsed_uses.append(
                {
                    **use,
                    "teaching_goal": use["teaching_goal"].strip(),
                }
            )
        if item["bucket"] != "propose_use" and parsed_uses:
            raise ValueError("only propose_use may contain candidate uses")
        rows.append(
            {
                "asset_sha256": asset,
                "bucket": item["bucket"],
                "candidate_uses": parsed_uses,
                "reason": reason.strip(),
            }
        )
    return rows


def salvage_prompt(items: list[dict[str, Any]]) -> str:
    evidence = []
    for item in items:
        evidence.append(
            {
                "asset_sha256": item["asset_sha256"],
                "original_teaching_goal": item.get("original_teaching_goal"),
                "original_commission_decision": item.get("commission_decision"),
                "failure_reasons": item.get("failure_reasons") or [],
                "mechanical_observations": item.get("mechanical_observations") or {},
                "visual_observations": item.get("visual_observations") or {},
                "candidate_pair_assets": item.get("candidate_pair_assets") or [],
            }
        )
    return (
        "You are a read-only assistant to the Ninereeds strategic orchestrator. These assets "
        "failed or need review for their original visual commission. The original decision is "
        "immutable: never turn a failed original commission into an acceptance. Instead, decide "
        "whether the supplied evidence supports a different, explicitly named teaching use. "
        "Never invent visual facts, never treat a model guess as mechanical evidence, and never "
        "propose a count contradicted by a deterministic count. Pairwise uses must name every "
        "other asset required. Sol will inspect the pixels and independently accept or reject each "
        "proposed use; your output has no admission authority. Return only one JSON array. Every "
        "item must have exactly asset_sha256, bucket, candidate_uses, reason. bucket is propose_use, "
        "discard, or needs_visual_recheck. Each candidate use has exactly kind, teaching_goal, "
        "evidence_keys, paired_asset_sha256s, constraints. Allowed kinds: "
        + ", ".join(sorted(USE_KINDS))
        + ".\n\nEVIDENCE:\n"
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    )


def sol_review_envelope(
    *,
    asset: dict[str, Any],
    original_report: dict[str, Any],
    salvage_proposal: dict[str, Any],
) -> dict[str, Any]:
    """Package pixels-by-hash, failures, and non-authoritative advice for Sol."""
    return {
        "schema_version": "ninereeds_visual_salvage_review_envelope_v1",
        "authority": {
            "deepseek_may_propose": True,
            "deepseek_may_accept": False,
            "sol_must_verify_pixels": True,
            "original_commission_decision_is_immutable": True,
        },
        "asset": asset,
        "original_report": original_report,
        "deepseek_salvage_proposal": salvage_proposal,
        "required_sol_output": {
            "decision": "accept_specific_use | reject | request_visual_recheck",
            "accepted_use_indexes": "array of candidate-use indexes; empty unless accepted",
            "verified_evidence_keys": "array of evidence keys Sol checked",
            "reason": "concise evidence-bearing explanation",
        },
    }
