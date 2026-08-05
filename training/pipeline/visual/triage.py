"""Policy triage for observations produced by a multimodal image judge."""

from __future__ import annotations

import json
from typing import Any


TRIAGE_BUCKETS = {"accept", "check_again", "reject"}


def parse_triage_response(text: str) -> list[dict[str, str]]:
    """Parse a deliberately small DeepSeek response schema."""
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        candidate = "\n".join(lines[1:-1]).strip()
    value = json.loads(candidate)
    if not isinstance(value, list):
        raise ValueError("triage response must be a JSON array")
    rows: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"asset_sha256", "bucket", "reason"}:
            raise ValueError("triage response item does not match the v1 schema")
        asset = item["asset_sha256"]
        bucket = item["bucket"]
        reason = item["reason"]
        if not isinstance(asset, str) or len(asset) != 64:
            raise ValueError("invalid triage asset_sha256")
        if bucket not in TRIAGE_BUCKETS:
            raise ValueError("invalid triage bucket")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
            raise ValueError("invalid triage reason")
        rows.append({"asset_sha256": asset, "bucket": bucket, "reason": reason.strip()})
    return rows


def effective_triage(gemma_item: dict[str, Any], proposed: dict[str, str] | None) -> dict[str, Any]:
    """Apply non-negotiable evidence and retry gates to a policy proposal."""
    if not gemma_item.get("parse_ok", False):
        return {"bucket": "check_again", "reason": "Gemma output did not parse", "source": "deterministic_gate"}
    hard_reasons = gemma_item.get("hard_gate_reasons") or []
    if hard_reasons:
        return {
            "bucket": "reject",
            "reason": "Hard gate: " + ", ".join(str(reason) for reason in hard_reasons),
            "source": "deterministic_gate",
        }
    if proposed is None:
        return {"bucket": "check_again", "reason": "No policy decision returned", "source": "deterministic_gate"}
    return {"bucket": proposed["bucket"], "reason": proposed["reason"], "source": "deepseek"}


def decision_prompt(items: list[dict[str, Any]]) -> str:
    evidence = []
    for item in items:
        evidence.append(
            {
                "asset_sha256": item.get("asset_sha256"),
                "teaching_goal": item.get("teaching_goal") or f"a {item.get('expected_species')}",
                "blind_observation": item.get("blind"),
                "gemma_rubric": item.get("rubric"),
                "hard_gate_reasons": item.get("hard_gate_reasons") or [],
            }
        )
    return (
        "You are the policy stage for an image-training curator. The pixels were inspected "
        "by Gemma; you receive only its structured evidence. Put every asset into exactly one "
        "bucket: accept when the evidence is complete, consistent, clean, and clearly supports "
        "the teaching goal; check_again when evidence is ambiguous, incomplete, uncertain, or "
        "internally conflicting; reject when evidence clearly shows a mismatch or unsuitable "
        "training image. Never invent visual facts. A listed hard_gate_reason requires reject. "
        "Return only a JSON array. Every object must have exactly asset_sha256, bucket, reason; "
        "bucket must be accept, check_again, or reject.\n\nEVIDENCE:\n"
        + json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    )
