"""Freeze and verify Campaign 35's final visual-material handoff to Sol."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .cli import DEFAULT_DB, connect


NON_STILL_ROUTES = {
    "contrast_pair", "image_sequence", "image_plus_context", "story_or_activity",
    "text_only", "curriculum_rewrite", "not_visually_teachable",
}


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values),
        encoding="utf-8",
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--gap-inventory", type=Path, required=True)
    parser.add_argument("--representation-evidence", type=Path, action="append", default=[])
    parser.add_argument("--flux-ledger", type=Path, action="append", default=[])
    parser.add_argument("--generated-source", action="append", default=[])
    parser.add_argument("--review-evidence", type=Path, action="append", default=[])
    parser.add_argument("--reuse-cap", type=int, default=4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    requirements = rows(args.requirements)
    decisions = rows(args.decisions)
    inventory_rows = rows(args.gap_inventory)
    if len(requirements) != 25_000 or len({row["slot_id"] for row in requirements}) != 25_000:
        raise ValueError("requirements are not the exact 25,000-slot Campaign 35 contract")
    if len(decisions) != 25_000 or len({row["slot_id"] for row in decisions}) != 25_000:
        raise ValueError("decisions are not an exact 25,000-slot partition")
    requirement_ids = {row["slot_id"] for row in requirements}
    if {row["slot_id"] for row in decisions} != requirement_ids:
        raise ValueError("decision slot IDs differ from requirements")

    inventory = {row["concept_id"]: row for row in inventory_rows}
    accepted: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    asset_uses: Counter[int] = Counter()
    generated_asset_ids: set[int] = set()
    legacy_review_evidence_assets: set[int] = set()
    generated_sources = set(args.generated_source)
    with connect(args.db) as db:
        has_review_decision = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_decision'"
        ).fetchone() is not None
        for row in decisions:
            if row.get("disposition") == "accepted":
                asset_id = row.get("asset_id")
                if not isinstance(asset_id, int):
                    raise ValueError(f"accepted slot lacks asset ID: {row['slot_id']}")
                asset = db.execute(
                    "SELECT source,source_id,local_path,sha256,status FROM asset WHERE id=?",
                    (asset_id,),
                ).fetchone()
                if asset is None:
                    raise ValueError(f"accepted asset is absent from registry: {row['slot_id']}")
                generated = asset["source"] in generated_sources
                if asset["status"] != "reviewed_usable":
                    positive_target_evidence = bool(row.get("target_evidence")) or (
                        row.get("word_fit_adjudication") == "accept"
                        and bool(row.get("word_fit_adjudication_reason"))
                    )
                    watermark_cleared = row.get("watermark") is not True or (
                        row.get("watermark_adjudication") == "in_scene_text_or_branding"
                    )
                    legacy_evidence = (
                        not generated
                        and asset["status"] == "mechanically_valid"
                        and row.get("status") == "mechanically_valid"
                        and bool(row.get("review_backend"))
                        and bool(row.get("review_model"))
                        and bool(row.get("literal_caption"))
                        and positive_target_evidence
                        and watermark_cleared
                    )
                    if not legacy_evidence:
                        raise ValueError(f"accepted asset lacks usable review evidence: {row['slot_id']}")
                    legacy_review_evidence_assets.add(asset_id)
                path = Path(asset["local_path"] or "")
                if not path.is_file() or digest(path) != asset["sha256"]:
                    raise ValueError(f"accepted asset bytes fail hash validation: {row['slot_id']}")
                if generated:
                    generated_asset_ids.add(asset_id)
                    if not has_review_decision or db.execute(
                        "SELECT 1 FROM review_decision WHERE asset_id=?", (asset_id,),
                    ).fetchone() is None:
                        raise ValueError(f"generated accepted asset lacks final review: {asset_id}")
                asset_uses[asset_id] += 1
                accepted.append({**row, "verified_local_path": str(path)})
                continue
            concept_id = row.get("concept_id") or row.get("word")
            need = inventory.get(concept_id)
            if need is None:
                raise ValueError(f"residual slot has no representation disposition: {row['slot_id']}")
            route = need["route"]
            record = {
                "slot_id": row["slot_id"], "concept_id": concept_id,
                "word": need["word"], "route": route,
                "curriculum_source": need.get("source_path"),
            }
            if route in NON_STILL_ROUTES:
                dispositions.append(record)
            else:
                unresolved.append(record)

        if generated_sources and has_review_decision:
            for source in generated_sources:
                unreviewed = db.execute(
                    """SELECT COUNT(*) FROM asset a LEFT JOIN review_decision r ON r.asset_id=a.id
                       WHERE a.source=? AND r.asset_id IS NULL""", (source,),
                ).fetchone()[0]
                if unreviewed:
                    raise ValueError(f"generated source has {unreviewed} assets without final review: {source}")

    over_cap = {str(key): count for key, count in asset_uses.items() if count > args.reuse_cap}
    if over_cap:
        raise ValueError(f"accepted asset reuse exceeds cap: {over_cap}")

    generated_records = [
        {**row, "_ledger_path": str(path)} for path in args.flux_ledger for row in rows(path)
    ]
    identities = [
        (row["_ledger_path"], row["production_brief_id"], int(row["variant_index"]))
        for row in generated_records
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("Flux evidence ledgers contain duplicate generation identities")
    if len({row["sha256"] for row in generated_records}) != len(generated_records):
        raise ValueError("Flux evidence ledgers contain pixel-identical generations")

    args.output.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output / "accepted_assignments.jsonl", accepted)
    write_jsonl(args.output / "representation_dispositions.jsonl", dispositions)
    write_jsonl(args.output / "unresolved_single_image.jsonl", unresolved)
    decisions_by_concept: dict[str, list[dict[str, Any]]] = {}
    requirements_by_concept: dict[str, list[dict[str, Any]]] = {}
    for row in requirements:
        requirements_by_concept.setdefault(row["concept_id"], []).append(row)
    for row in decisions:
        concept_id = row.get("concept_id") or row.get("word")
        decisions_by_concept.setdefault(concept_id, []).append(row)
    concept_summary: list[dict[str, Any]] = []
    for concept_id, concept_requirements in sorted(
        requirements_by_concept.items(), key=lambda item: (item[1][0].get("ordinal", 0), item[0]),
    ):
        concept_decisions = decisions_by_concept[concept_id]
        accepted_count = sum(row.get("disposition") == "accepted" for row in concept_decisions)
        need = inventory.get(concept_id)
        route = need["route"] if need else "accepted_images"
        concept_summary.append({
            "concept_id": concept_id,
            "word": concept_requirements[0]["word"],
            "ordinal": concept_requirements[0].get("ordinal"),
            "required_slots": len(concept_requirements),
            "accepted_image_slots": accepted_count,
            "representation_disposition_slots": len(concept_requirements) - accepted_count,
            "route": route,
            "curriculum_source": need.get("source_path") if need else None,
        })
    write_jsonl(args.output / "concept_summary.jsonl", concept_summary)
    route_slots = Counter(row["route"] for row in dispositions)
    route_concepts = Counter(
        row["route"] for row in concept_summary if row["route"] != "accepted_images"
    )
    input_paths = [args.requirements, args.decisions, args.gap_inventory, *args.representation_evidence,
                   *args.flux_ledger, *args.review_evidence]
    inputs = [{"path": str(path), "sha256": digest(path)} for path in input_paths]
    complete = not unresolved
    report = {
        "schema_version": "ninereeds_campaign35_visual_completion_v1",
        "status": "task_complete" if complete else "incomplete",
        "contract_slots": len(requirements), "accepted_image_slots": len(accepted),
        "representation_disposition_slots": len(dispositions),
        "representation_disposition_routes": dict(sorted(route_slots.items())),
        "fully_image_covered_concepts": sum(
            row["accepted_image_slots"] == row["required_slots"] for row in concept_summary
        ),
        "representation_disposition_concepts": dict(sorted(route_concepts.items())),
        "unresolved_teachable_items": len(unresolved),
        "accepted_unique_assets": len(asset_uses), "maximum_asset_uses": max(asset_uses.values(), default=0),
        "reuse_cap": args.reuse_cap, "flux_generated_assets": len(generated_records),
        "verified_generated_accepted_assets": len(generated_asset_ids),
        "legacy_accepted_assets_verified_from_decision_evidence": len(legacy_review_evidence_assets),
        "inputs": inputs,
    }
    (args.output / "validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    handoff = {
        **report,
        "authoritative_decisions": str(args.decisions),
        "accepted_assignment_manifest": str(args.output / "accepted_assignments.jsonl"),
        "representation_disposition_manifest": str(args.output / "representation_dispositions.jsonl"),
        "concept_summary_manifest": str(args.output / "concept_summary.jsonl"),
        "unresolved_manifest": str(args.output / "unresolved_single_image.jsonl"),
        "review_evidence": [str(path) for path in args.review_evidence],
        "representation_evidence": [str(path) for path in args.representation_evidence],
        "flux_ledgers": [str(path) for path in args.flux_ledger],
        "message_to_sol": "task complete" if complete else "visual material remains unresolved",
    }
    (args.output / "sol-handoff.json").write_text(
        json.dumps(handoff, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
