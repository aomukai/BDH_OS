"""Reconcile Gemma's residual representation proposal with Luna's full still-image audit."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any, Iterable

from .representation_reassessment import load_jsonl


def reconcile(
    needs: list[dict[str, Any]], proposal: list[dict[str, Any]], audit: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    proposed = {row["item_id"]: row for row in proposal}
    audited = {row["item_id"]: row for row in audit}
    need_ids = {row["item_id"] for row in needs}
    if set(proposed) != need_ids:
        raise ValueError("Gemma proposal does not exactly cover the residual needs")
    proposed_singles = {item_id for item_id, row in proposed.items() if row["representation_class"] == "single_image"}
    if set(audited) != proposed_singles:
        raise ValueError("Luna audit does not exactly cover every proposed single image")
    single, dispositions = [], []
    final_counts: Counter[str] = Counter()
    for need in needs:
        item_id = need["item_id"]
        gemma = proposed[item_id]
        luna = audited.get(item_id)
        final_class = luna["representation_class"] if luna else gemma["representation_class"]
        final_counts[final_class] += 1
        evidence = {
            "gemma_proposal": gemma,
            "luna_single_image_boundary_audit": luna,
            "final_representation_class": final_class,
        }
        row = {**need, "representation_reassessment": evidence}
        if final_class == "single_image":
            single.append(row)
        else:
            row["representation_class"] = final_class
            dispositions.append(row)
    summary = {
        "schema_version": "ninereeds_representation_boundary_reconciliation_v1",
        "input_residual_items": len(needs), "single_image_needs": len(single),
        "reclassified_dispositions": len(dispositions),
        "final_representation_counts": dict(final_counts),
        "status": "validated_residual_partition_pending_material_completion",
    }
    if len(single) + len(dispositions) != len(needs):
        raise AssertionError("residual partition lost items")
    return single, dispositions, summary


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--needs", type=Path, required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    single, dispositions, summary = reconcile(
        load_jsonl(args.needs), load_jsonl(args.proposal), load_jsonl(args.audit),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("single_image_needs", single), ("reclassified_dispositions", dispositions)):
        (args.output / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
