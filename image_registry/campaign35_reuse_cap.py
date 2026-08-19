"""Enforce a deterministic global image-reuse cap on Campaign 35 decisions."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _mentions(word: str, value: Any) -> int:
    if not isinstance(value, str) or not value:
        return 0
    pattern = r"(?<!\w)" + re.escape(word.casefold()) + r"(?!\w)"
    return int(re.search(pattern, value.casefold()) is not None)


def enforce_reuse_cap(input_path: Path, output: Path, *, max_uses: int = 4) -> dict[str, Any]:
    if max_uses < 1:
        raise ValueError("max_uses must be positive")
    rows = _rows(input_path)
    if len(rows) != 25_000 or len({row["slot_id"] for row in rows}) != 25_000:
        raise ValueError("input must contain exactly 25,000 unique slots")

    accepted_by_ordinal = Counter(
        row["ordinal"] for row in rows if row["disposition"] == "accepted"
    )
    by_asset: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["disposition"] == "accepted":
            by_asset[row["asset_id"]].append(row)

    keep_slots: set[str] = set()
    reuse_ledger: list[dict[str, Any]] = []
    for asset_id, uses in sorted(by_asset.items()):
        ranked = sorted(
            uses,
            key=lambda row: (
                accepted_by_ordinal[row["ordinal"]],
                -sum(_mentions(row["word"], row.get(field)) for field in (
                    "literal_caption", "source_caption", "target_evidence",
                )),
                row["sequence_position"],
            ),
        )
        kept = ranked[:max_uses]
        demoted = ranked[max_uses:]
        keep_slots.update(row["slot_id"] for row in kept)
        reuse_ledger.append({
            "asset_id": asset_id,
            "uses_before": len(uses),
            "uses_after": len(kept),
            "kept_slots": [row["slot_id"] for row in kept],
            "kept_words": [row["word"] for row in kept],
            "demoted_slots": [row["slot_id"] for row in demoted],
            "demoted_words": [row["word"] for row in demoted],
        })

    decisions: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: item["sequence_position"]):
        if row["disposition"] != "accepted" or row["slot_id"] in keep_slots:
            decisions.append(row)
            continue
        decisions.append({
            **row,
            "prior_disposition": "accepted",
            "disposition": "reuse_cap_exceeded",
            "reuse_cap": max_uses,
            "reuse_cap_reason": (
                "Asset exceeded the global curriculum-use cap; scarcer concepts and more "
                "explicit caption evidence retained priority."
            ),
        })

    accepted = [row for row in decisions if row["disposition"] == "accepted"]
    residual = [row for row in decisions if row["disposition"] != "accepted"]
    final_counts = Counter(row["asset_id"] for row in accepted)
    if final_counts and max(final_counts.values()) > max_uses:
        raise AssertionError("reuse cap enforcement failed")
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "decisions.jsonl", decisions)
    _write(output / "accepted.jsonl", accepted)
    _write(output / "residual_wishlist.jsonl", residual)
    _write(output / "reuse_ledger.jsonl", reuse_ledger)
    summary = {
        "schema_version": "ninereeds_campaign35_image_reuse_cap_v1",
        "status": "reuse_cap_enforced",
        "max_uses_per_asset": max_uses,
        "accepted_slots": len(accepted),
        "residual_slots": len(residual),
        "demoted_over_cap_slots": sum(
            row["disposition"] == "reuse_cap_exceeded" for row in decisions
        ),
        "assets_over_cap_before": sum(len(uses) > max_uses for uses in by_asset.values()),
        "max_uses_after": max(final_counts.values(), default=0),
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "retention_policy": "scarcity_then_explicit_evidence_then_sequence",
        "exact_partition": len(accepted) + len(residual) == 25_000,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-uses", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(enforce_reuse_cap(args.input, args.output, max_uses=args.max_uses), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
