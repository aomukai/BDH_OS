"""Build an exact Campaign 35 residual inventory and representation-audit input."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Any, Iterable


SPECIALIST_HINTS = {
    "aside": (
        "Distinguish 'set aside' from merely 'beside/next to': show a clear central group of "
        "matching objects and one matching object deliberately separated at the side by empty space."
    ),
    "abnormal": (
        "Show an immediate visible norm and one unmistakable structural deviation of the same "
        "kind. Do not rely on size: prior oversized-object attempts rendered as ordinary variation. "
        "Prefer a row of identical manufactured objects with one clearly malformed same-kind item."
    ),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def source_excerpt(root: Path, relative: str, limit: int = 1200) -> str:
    text = (root / relative).read_text(encoding="utf-8", errors="replace")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--curriculum", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse-cap", type=int, default=4)
    parser.add_argument("--representation-reconciliation", type=Path, action="append", default=[])
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.reuse_cap < 1:
        raise ValueError("reuse cap must be positive")

    curriculum = {row["concept_id"]: row for row in load_jsonl(args.curriculum)}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in load_jsonl(args.decisions):
        grouped[row["concept_id"]].append(row)
    if set(grouped) != set(curriculum):
        raise ValueError("decision and curriculum concept partitions differ")

    final_classes: dict[str, str] = {}
    for reconciliation in args.representation_reconciliation:
        for name in ("single_image_needs.jsonl", "reclassified_dispositions.jsonl"):
            for row in load_jsonl(reconciliation / name):
                final_classes[row["item_id"]] = (
                    "single_image" if name.startswith("single") else row["representation_class"]
                )

    inventory: list[dict[str, Any]] = []
    audit_needs: list[dict[str, Any]] = []
    accepted_representation_needs: list[dict[str, Any]] = []
    for concept_id, meta in sorted(curriculum.items(), key=lambda item: item[1]["ordinal"]):
        rows = grouped[concept_id]
        accepted = sum(row.get("disposition") == "accepted" for row in rows)
        missing = len(rows) - accepted
        if not missing:
            continue
        excerpt = source_excerpt(args.repo_root, meta["source_path"])
        route = final_classes.get(
            concept_id,
            "single_image_empirically_demonstrated" if accepted else "representation_audit_required",
        )
        record = {
            "concept_id": concept_id,
            "word": rows[0]["word"],
            "ordinal": meta["ordinal"],
            "accepted_slots": accepted,
            "missing_slots": missing,
            "route": route,
            "source_path": meta["source_path"],
            "curriculum_excerpt": excerpt,
            "specialist_hint": SPECIALIST_HINTS.get(concept_id, ""),
            "accepted_examples": [
                {
                    "literal_caption": row.get("literal_caption", ""),
                    "target_evidence": row.get("target_evidence", ""),
                }
                for row in rows if row.get("disposition") == "accepted"
            ][:3],
            "rejected_generated_examples": [
                {
                    "disposition": row.get("disposition", ""),
                    "source_prompt": row.get("source_caption", ""),
                    "literal_caption": row.get("literal_caption", ""),
                    "target_evidence": row.get("target_evidence", ""),
                    "uncertainties": row.get("uncertainties", []),
                }
                for row in rows
                if row.get("disposition") != "accepted"
                and str(row.get("source", "")).startswith("ninereeds_flux_campaign35")
            ][-6:],
            "missing_slot_ids": [row["slot_id"] for row in rows if row.get("disposition") != "accepted"],
        }
        inventory.append(record)
        if accepted == 0:
            audit_needs.append({
                "item_id": concept_id,
                "concept": rows[0]["word"],
                "exact_teaching_claim": (
                    f'Can one natural, unlabeled still image directly teach the English word '
                    f'"{rows[0]["word"]}" in this curriculum sense? Curriculum material: {excerpt}'
                ),
                "missing_slots": missing,
                "source_path": meta["source_path"],
            })
        else:
            accepted_representation_needs.append({
                "item_id": concept_id,
                "concept": rows[0]["word"],
                "exact_teaching_claim": (
                    f'Can one natural, unlabeled still image directly teach the English word '
                    f'"{rows[0]["word"]}" in this curriculum sense? Existing accepted evidence: '
                    + json.dumps(record["accepted_examples"], ensure_ascii=False)
                    + f" Curriculum material: {excerpt}"
                ),
                "missing_slots": missing,
                "source_path": meta["source_path"],
            })

    generation_slots = sum(
        row["missing_slots"] for row in inventory
        if row["route"] in {"single_image", "single_image_empirically_demonstrated"}
    )
    unresolved_slots = sum(row["missing_slots"] for row in inventory if row["route"] == "representation_audit_required")
    counts = Counter(row["route"] for row in inventory)
    args.output.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output / "gap_inventory.jsonl", inventory)
    write_jsonl(args.output / "zero_acceptance_representation_needs.jsonl", audit_needs)
    write_jsonl(args.output / "accepted_representation_needs.jsonl", accepted_representation_needs)
    summary = {
        "schema_version": "ninereeds_campaign35_flux_gap_inventory_v1",
        "residual_slots": sum(row["missing_slots"] for row in inventory),
        "affected_concepts": len(inventory),
        "zero_acceptance_concepts": len(audit_needs),
        "route_counts": dict(counts),
        "representation_unresolved_slots": unresolved_slots,
        "confirmed_single_image_generation_slots": generation_slots,
        "generation_image_upper_bound_one_per_slot": generation_slots,
        "generation_image_theoretical_floor_at_reuse_cap": (
            (generation_slots + args.reuse_cap - 1) // args.reuse_cap
        ),
        "reuse_cap": args.reuse_cap,
        "note": "The reuse-cap floor is mathematical only; the production-brief count requires compatible visible claims.",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
