"""Fold one or more external-acquisition verification passes into the material ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconcile(
    *, protected_path: Path, external_path: Path, decisions_path: Path,
    verification_dirs: list[Path], output: Path, expected_curriculum_items: int | None = None,
) -> dict[str, Any]:
    protected = _load(protected_path)
    external = _load(external_path)
    decisions = _load(decisions_path)
    external_by_id = {row["item_id"]: row for row in external}
    if len(external_by_id) != len(external):
        raise ValueError("base external ledger repeats item IDs")
    accepted: list[dict[str, Any]] = []
    attempts: dict[str, list[dict[str, Any]]] = {}
    inputs = [protected_path, external_path, decisions_path]
    for pass_number, root in enumerate(verification_dirs, 1):
        unfinished = _load(root / "unfinished.jsonl")
        if unfinished:
            raise ValueError(f"verification pass {pass_number} is unfinished")
        for bucket in ("accepted", "rejected", "uncertain"):
            path = root / f"{bucket}.jsonl"
            inputs.append(path)
            for row in _load(path):
                item_id = row["item_id"]
                if item_id not in external_by_id:
                    raise ValueError(f"verification item is absent from external ledger: {item_id}")
                result = row["luna_result"]
                attempts.setdefault(item_id, []).append({
                    "pass": pass_number,
                    "dataset": row.get("source", "open_images_v7"),
                    "source_image_id": row.get("source_image_id"),
                    "asset_id": row["asset_id"],
                    "verdict": result["verdict"],
                    "reason": result["reason"],
                    "disqualifiers": result.get("disqualifiers", []),
                })
                if bucket == "accepted":
                    accepted.append(row)

    accepted_item_ids = {row["item_id"] for row in accepted}
    accepted_asset_ids = {row["asset_id"] for row in accepted}
    if len(accepted_item_ids) != len(accepted) or len(accepted_asset_ids) != len(accepted):
        raise ValueError("external accepts repeat an item or asset")
    protected_item_ids = {row["item_id"] for row in protected}
    protected_asset_ids = {row["asset_id"] for row in protected}
    if protected_item_ids & accepted_item_ids or protected_asset_ids & accepted_asset_ids:
        raise ValueError("external accepts overlap protected selections")

    remaining: list[dict[str, Any]] = []
    for row in external:
        if row["item_id"] in accepted_item_ids:
            continue
        updated = dict(row)
        if row["item_id"] in attempts:
            updated["acquisition_attempts"] = attempts[row["item_id"]]
            updated["status"] = "external_acquisition_retry_or_representation_reassessment_needed"
        remaining.append(updated)
    combined = sorted(protected + accepted, key=lambda row: row["item_id"])
    non_single = {
        row["item_id"] for row in decisions if row["representation_class"] != "single_image"
    }
    combined_ids = {row["item_id"] for row in combined}
    remaining_ids = {row["item_id"] for row in remaining}
    checks = {
        "protected_unique": len(combined_ids) == len(combined),
        "remaining_unique": len(remaining_ids) == len(remaining),
        "partition_disjoint": not (
            combined_ids & remaining_ids or combined_ids & non_single or remaining_ids & non_single
        ),
        "curriculum_complete": (
            expected_curriculum_items is None
            or len(combined_ids | remaining_ids | non_single) == expected_curriculum_items
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "protected_selections.jsonl", combined)
    _write(output / "external_metadata_needs.jsonl", remaining)
    _write(output / "new_external_accepts.jsonl", sorted(accepted, key=lambda row: row["item_id"]))
    summary = {
        "schema_version": "ninereeds_acquisition_round_reconciliation_v1",
        "new_external_accepts": len(accepted),
        "protected_selections": len(combined),
        "external_metadata_needs": len(remaining),
        "non_single_or_nonvisual_dispositions": len(non_single),
        "curriculum_items": len(combined_ids | remaining_ids | non_single),
        "status": "passed_external_acquisition_incomplete" if all(checks.values()) else "failed",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    report = {
        "status": "passed" if all(checks.values()) else "failed", "checks": checks,
        "inputs": {str(path): _sha(path) for path in inputs},
        "outputs": {
            name: _sha(output / name) for name in (
                "protected_selections.jsonl", "external_metadata_needs.jsonl",
                "new_external_accepts.jsonl", "summary.json",
            )
        },
    }
    (output / "validation_report.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    if report["status"] != "passed":
        raise ValueError(f"round reconciliation failed: {checks}")
    return summary


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected", type=Path, required=True)
    parser.add_argument("--external", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--verification-dir", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-curriculum-items", type=int)
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(json.dumps(reconcile(
        protected_path=args.protected, external_path=args.external,
        decisions_path=args.decisions, verification_dirs=args.verification_dir,
        output=args.output, expected_curriculum_items=args.expected_curriculum_items,
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
