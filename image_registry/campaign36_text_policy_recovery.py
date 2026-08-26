"""Recover Campaign 36 images rejected solely by the obsolete text veto.

This is an append-only policy migration.  It never changes an old review.  A candidate
is recoverable only when Luna already called it usable, found every frozen target
present, reported no watermark, uncertainty, or quality flag, and the outer gate's
only failure reason was ``visible_text``.  The exact file and SHA-256 must still match.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from image_registry.campaign36_flux_streaming_luna import append_jsonl, digest, load_jsonl
from image_registry.campaign36_imagegen_fallback import (
    DEFAULT_ROOT,
    completed_assignments,
    exhausted_assignments,
)


SCHEMA_VERSION = "ninereeds_campaign36_text_policy_recovery_v1"


def semantic_clean(decision: dict[str, Any]) -> bool:
    result = decision.get("luna_result") or {}
    return (
        decision.get("failure_reasons") == ["visible_text"]
        and result.get("admission") == "usable"
        and result.get("visible_text") is True
        and result.get("watermark") is False
        and result.get("quality_flags") == []
        and result.get("uncertainties") == []
        and bool(result.get("targets"))
        and all(target.get("verdict") == "present" for target in result["targets"])
    )


def decision_index(root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    sources = (
        ("flux", root / "streaming-luna" / "decisions.jsonl"),
        ("codex-imagegen", root / "imagegen-v1" / "decisions.jsonl"),
    )
    for provider, path in sources:
        for row in load_jsonl(path, tolerate_partial_tail=True):
            rows[(provider, str(row.get("attempt_id", "")))] = row
    return rows


def accepted_hashes(root: Path) -> set[str]:
    hashes: set[str] = set()
    for path in (
        root / "streaming-luna" / "decisions.jsonl",
        root / "imagegen-v1" / "decisions.jsonl",
        root / "imagegen-v1" / "policy-recoveries.jsonl",
    ):
        for row in load_jsonl(path, tolerate_partial_tail=True):
            if row.get("verdict") == "accepted" and row.get("sha256"):
                hashes.add(str(row["sha256"]))
    return hashes


def select(root: Path, audit: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    unresolved = {
        row["assignment_id"]
        for row in exhausted_assignments(root / "streaming-luna")
    } - completed_assignments(root / "imagegen-v1")
    decisions = decision_index(root)
    used_hashes = accepted_hashes(root)
    selected: list[dict[str, Any]] = []
    seen_assignments: set[str] = set()
    counts = {
        "audit_candidates": 0,
        "unresolved_exact_only": 0,
        "missing_or_changed_file": 0,
        "duplicate_hash": 0,
        "selected": 0,
    }
    candidates = load_jsonl(audit, tolerate_partial_tail=True)
    # Prefer later attempts, and ImageGen over Flux when both are clean.
    candidates.sort(
        key=lambda row: (
            row.get("assignment_id", ""),
            row.get("provider") == "codex-imagegen",
            row.get("attempt_id", ""),
        ),
        reverse=True,
    )
    for candidate in candidates:
        counts["audit_candidates"] += 1
        assignment = str(candidate.get("assignment_id", ""))
        if assignment not in unresolved or assignment in seen_assignments:
            continue
        decision = decisions.get((str(candidate.get("provider")), str(candidate.get("attempt_id"))))
        if not decision or not semantic_clean(decision):
            continue
        counts["unresolved_exact_only"] += 1
        path = Path(str(decision.get("local_path", "")))
        expected_hash = str(decision.get("sha256", ""))
        if not path.is_file() or not expected_hash or digest(path) != expected_hash:
            counts["missing_or_changed_file"] += 1
            continue
        if expected_hash in used_hashes:
            counts["duplicate_hash"] += 1
            continue
        selected.append({
            "schema_version": SCHEMA_VERSION,
            "recovered_at": datetime.now(timezone.utc).isoformat(),
            "verdict": "accepted",
            "assignment_id": assignment,
            "attempt_id": decision["attempt_id"],
            "provider": candidate["provider"],
            "concept_ids": decision.get("concept_ids", []),
            "production_brief_id": decision.get("production_brief_id"),
            "variant_index": decision.get("variant_index"),
            "generation_attempt": decision.get("generation_attempt"),
            "local_path": str(path),
            "sha256": expected_hash,
            "mechanical": decision.get("mechanical"),
            "luna_result": decision["luna_result"],
            "original_failure_reasons": decision["failure_reasons"],
            "original_review_model": decision.get("review_model"),
            "recovery_basis": (
                "Luna already found the image usable with every target present and no "
                "quality flag, uncertainty, or watermark; the sole failure was the retired "
                "blanket visible-text veto."
            ),
        })
        seen_assignments.add(assignment)
        used_hashes.add(expected_hash)
    counts["selected"] = len(selected)
    return selected, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    audit = args.audit or args.root / "text-policy-audit-v1" / "candidates.jsonl"
    rows, counts = select(args.root, audit)
    ledger = args.root / "imagegen-v1" / "policy-recoveries.jsonl"
    if args.apply:
        already = {
            (row.get("assignment_id"), row.get("sha256"))
            for row in load_jsonl(ledger, tolerate_partial_tail=True)
        }
        for row in rows:
            if (row["assignment_id"], row["sha256"]) not in already:
                append_jsonl(ledger, row)
    print(json.dumps({
        "mode": "apply" if args.apply else "dry-run",
        "ledger": str(ledger),
        **counts,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
