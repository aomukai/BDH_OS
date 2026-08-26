"""Audit preserved Campaign 36 rejections for blanket visible-text policy casualties."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from image_registry.campaign36_flux_streaming_luna import (
    effective_visible_text_note,
    effective_visible_text_policy,
    load_jsonl,
)
from image_registry.campaign36_imagegen_fallback import source_attempts


DEFAULT_ROOT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/flux-specialist-v1"
)
TEXT_MARKERS = ("text", "writ", "label", "letter", "spell", "word", "title", "pseudo")


def text_related(reason: str) -> bool:
    value = reason.lower()
    return value == "visible_text" or any(marker in value for marker in TEXT_MARKERS)


def semantic_pass(result: dict[str, Any]) -> bool:
    return (
        result.get("admission") == "usable"
        and not result.get("watermark")
        and not result.get("uncertainties")
        and bool(result.get("targets"))
        and all(target.get("verdict") == "present" for target in result["targets"])
    )


def inspect_decisions(
    decisions: list[dict[str, Any]], sources: dict[str, dict[str, Any]], provider: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    assignments: dict[str, set[str]] = defaultdict(set)
    for decision in decisions:
        if decision.get("verdict") == "accepted":
            continue
        counts["rejected_attempts"] += 1
        reasons = [str(reason) for reason in decision.get("failure_reasons", [])]
        if any(text_related(reason) for reason in reasons):
            counts["attempts_with_text_reason"] += 1
            assignments["with_text_reason"].add(decision["assignment_id"])
        source = sources.get(decision.get("attempt_id", ""), {})
        luna = decision.get("luna_result") or {}
        exact_outer_only = reasons == ["visible_text"]
        semantic_text_only = (
            semantic_pass(luna)
            and bool(reasons)
            and all(text_related(reason) for reason in reasons)
        )
        if exact_outer_only:
            counts["exact_visible_text_only_attempts"] += 1
            assignments["exact_visible_text_only"].add(decision["assignment_id"])
        if not semantic_text_only:
            continue
        counts["semantic_pass_text_only_attempts"] += 1
        assignments["semantic_pass_text_only"].add(decision["assignment_id"])
        inferred = effective_visible_text_policy(source)
        if inferred == "required_evidence":
            counts["contract_supported_salvage_attempts"] += 1
            assignments["contract_supported_salvage"].add(decision["assignment_id"])
        path = Path(str(decision.get("local_path", "")))
        if path.is_file():
            counts["preserved_candidate_files"] += 1
        candidates.append({
            "schema_version": "ninereeds_campaign36_text_rejection_candidate_v1",
            "provider": provider,
            "assignment_id": decision["assignment_id"],
            "attempt_id": decision.get("attempt_id"),
            "concept_ids": decision.get("concept_ids") or source.get("concept_ids"),
            "evidence_by_concept": source.get("evidence_by_concept", {}),
            "effective_visible_text_policy": inferred,
            "visible_text_note": effective_visible_text_note(source),
            "failure_reasons": reasons,
            "literal_caption": luna.get("literal_caption"),
            "local_path": str(path),
            "sha256": decision.get("sha256"),
            "preserved": path.is_file(),
            "disposition": (
                "re-review_under_required-text-policy"
                if inferred == "required_evidence"
                else "human-contract-review-before-re-review"
            ),
        })
    summary = dict(counts)
    summary.update({f"unique_assignments_{key}": len(value) for key, value in assignments.items()})
    return candidates, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.root / "text-policy-audit-v1"
    output.mkdir(parents=True, exist_ok=True)

    streaming = args.root / "streaming-luna"
    flux_sources = source_attempts(streaming)
    flux_decisions = load_jsonl(streaming / "decisions.jsonl", tolerate_partial_tail=True)
    flux_candidates, flux_summary = inspect_decisions(flux_decisions, flux_sources, "flux")

    imagegen = args.root / "imagegen-v1"
    imagegen_sources = {
        row.get("attempt_id", ""): row
        for row in load_jsonl(imagegen / "generation.jsonl", tolerate_partial_tail=True)
    }
    # Older generation records do not store attempt_id; reconstruct the review identity.
    for row in load_jsonl(imagegen / "generation.jsonl", tolerate_partial_tail=True):
        key = (
            f"{row['production_brief_id']}-v{int(row['variant_index']):02d}"
            f"-a{int(row['generation_attempt']):02d}"
        )
        imagegen_sources[key] = row
    imagegen_decisions = load_jsonl(imagegen / "decisions.jsonl", tolerate_partial_tail=True)
    imagegen_candidates, imagegen_summary = inspect_decisions(
        imagegen_decisions, imagegen_sources, "codex-imagegen"
    )
    candidates = flux_candidates + imagegen_candidates
    with (output / "candidates.jsonl").open("w", encoding="utf-8") as handle:
        for row in candidates:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {
        "schema_version": "ninereeds_campaign36_text_rejection_audit_v1",
        "scope": "preserved rejected attempts; no admission changes",
        "flux": flux_summary,
        "imagegen": imagegen_summary,
        "combined_candidate_attempts": len(candidates),
        "combined_unique_candidate_assignments": len({row["assignment_id"] for row in candidates}),
        "combined_contract_supported_attempts": sum(
            row["effective_visible_text_policy"] == "required_evidence" for row in candidates
        ),
        "combined_preserved_candidate_files": sum(row["preserved"] for row in candidates),
        "candidate_ledger": str(output / "candidates.jsonl"),
        "interpretation": (
            "Candidates passed Luna semantically and failed only text-related gates. They are "
            "not auto-admitted; required text must be checked for accuracy and relevance."
        ),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
