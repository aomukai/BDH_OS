"""Reconcile a Luna gate into protected selections and external metadata needs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconcile(
    *, prior_accepted: Path, base_external: Path, verification_dir: Path,
    decisions_path: Path, output: Path, expected_curriculum_items: int | None = None,
    expected_gate_items: int | None = None,
) -> dict[str, Any]:
    prior = load_jsonl(prior_accepted)
    accepted = load_jsonl(verification_dir / "accepted.jsonl")
    rejected = load_jsonl(verification_dir / "rejected.jsonl")
    uncertain = load_jsonl(verification_dir / "uncertain.jsonl")
    unfinished = load_jsonl(verification_dir / "unfinished.jsonl")
    external = load_jsonl(base_external)
    decisions = load_jsonl(decisions_path)
    if unfinished:
        raise ValueError("verification gate still has unfinished items")

    external_ids = {row["item_id"] for row in external}
    for verdict, rows in (("reject", rejected), ("uncertain", uncertain)):
        for row in rows:
            item_id = row["item_id"]
            if item_id in external_ids:
                raise ValueError(f"verification item already exists in base external needs: {item_id}")
            claim = row.get("exact_teaching_claim") or row["intended_teaching_claim"]
            result = row["luna_result"]
            external.append({
                "schema_version": "ninereeds_external_metadata_need_v1",
                "campaign_id": row.get("campaign_id"),
                "item_id": item_id,
                "concept": row["concept"],
                "exact_teaching_claim": claim,
                "representation_class": "single_image",
                "priority": "normal",
                "metadata_queries": [
                    {"tier": "exact_claim", "query": claim},
                    {"tier": "exact_concept", "query": row["concept"]},
                ],
                "suitable_source_type": "Open Images first; use relation- or caption-rich metadata when the exact claim requires it.",
                "required_visible_evidence": [f"Pixels must directly and unambiguously show: {claim}"],
                "forbidden_shortcuts": [
                    "Metadata, captions, filenames, and annotations are retrieval evidence only.",
                    "Do not infer hidden state, intent, causality, or off-frame content.",
                    "Do not relax taxonomy, cardinality, direction, arguments, or relation.",
                ],
                "prior_excluded_asset_ids": sorted(set(row.get("prior_excluded_asset_ids", [])) | {row["asset_id"]}),
                "luna_gate": {
                    "verdict": verdict,
                    "reason": result["reason"],
                    "disqualifiers": result.get("disqualifiers", []),
                },
                "expected_license_provenance_fields": [
                    "dataset", "release_or_version", "split", "source_image_id",
                    "official_landing_or_download_identity", "matched_annotations",
                    "query_tier", "license_name_or_url", "creator_or_provenance",
                    "pixel_url_or_official_downloader_identity",
                ],
                "status": "prepared_for_step_7_metadata_search_not_executed",
            })
            external_ids.add(item_id)

    protected = sorted(prior + accepted, key=lambda row: row["item_id"])
    external.sort(key=lambda row: row["item_id"])
    decision_by_id = {row["item_id"]: row for row in decisions}
    protected_ids = {row["item_id"] for row in protected}
    external_ids = {row["item_id"] for row in external}
    non_single_ids = {
        row["item_id"] for row in decisions if row["representation_class"] != "single_image"
    }
    checks = {
        "protected_unique": len(protected_ids) == len(protected),
        "external_unique": len(external_ids) == len(external),
        "route_disjoint": not (
            protected_ids & external_ids or protected_ids & non_single_ids or external_ids & non_single_ids
        ),
        "complete_curriculum_partition": (
            expected_curriculum_items is None
            or len(protected_ids | external_ids | non_single_ids) == expected_curriculum_items
        ),
        "external_is_single_image": all(
            decision_by_id[item_id]["representation_class"] == "single_image"
            for item_id in external_ids
        ),
        "new_gate_partition": (
            expected_gate_items is None
            or len(accepted) + len(rejected) + len(uncertain) == expected_gate_items
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "protected_selections.jsonl", protected)
    write_jsonl(output / "external_metadata_needs.jsonl", external)
    summary = {
        "schema_version": "ninereeds_acquisition_reconciliation_v1",
        "protected_selections": len(protected),
        "new_luna_accepts": len(accepted),
        "new_luna_rejects": len(rejected),
        "new_luna_uncertain": len(uncertain),
        "external_metadata_needs": len(external),
        "non_single_or_nonvisual_dispositions": len(non_single_ids),
        "curriculum_items": len(protected_ids | external_ids | non_single_ids),
        "status": "passed_incomplete_external_acquisition_pending" if all(checks.values()) else "failed",
    }
    (output / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    validation = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "inputs": {
            str(path): sha256(path) for path in (
                prior_accepted, base_external, decisions_path,
                verification_dir / "accepted.jsonl", verification_dir / "rejected.jsonl",
                verification_dir / "uncertain.jsonl", verification_dir / "unfinished.jsonl",
            )
        },
        "outputs": {
            name: sha256(output / name) for name in (
                "protected_selections.jsonl", "external_metadata_needs.jsonl", "summary.json",
            )
        },
    }
    (output / "validation_report.json").write_text(
        json.dumps(validation, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    if validation["status"] != "passed":
        raise ValueError(f"reconciliation validation failed: {checks}")
    return summary


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-accepted", type=Path, required=True)
    parser.add_argument("--base-external", type=Path, required=True)
    parser.add_argument("--verification-dir", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-curriculum-items", type=int)
    parser.add_argument("--expected-gate-items", type=int)
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = reconcile(
        prior_accepted=args.prior_accepted, base_external=args.base_external,
        verification_dir=args.verification_dir, decisions_path=args.decisions, output=args.output,
        expected_curriculum_items=args.expected_curriculum_items,
        expected_gate_items=args.expected_gate_items,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
