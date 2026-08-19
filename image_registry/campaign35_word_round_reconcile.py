"""Fold a Campaign 35 follow-up review round into the authoritative slot ledger."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reconcile(prior_path: Path, round_path: Path, output: Path) -> dict[str, Any]:
    prior = {row["slot_id"]: row for row in _rows(prior_path)}
    current = {row["slot_id"]: row for row in _rows(round_path)}
    if len(prior) != 25_000 or set(prior) != set(current):
        raise ValueError("prior and round ledgers must contain the same 25,000 unique slots")

    decisions: list[dict[str, Any]] = []
    for slot_id, old in prior.items():
        new = current[slot_id]
        has_round_candidate = new["disposition"] != "missing_candidate"
        if old["disposition"] == "accepted" and has_round_candidate:
            raise ValueError(f"round attempted to overwrite accepted slot: {slot_id}")
        chosen = new if has_round_candidate else old
        decisions.append({
            **chosen,
            "decision_round": "follow_up" if has_round_candidate else "prior",
            "prior_disposition": old["disposition"],
        })

    decisions.sort(key=lambda row: row["sequence_position"])
    if [row["sequence_position"] for row in decisions] != list(range(1, 25_001)):
        raise ValueError("reconciled positions are not exactly 1..25000")
    accepted = [row for row in decisions if row["disposition"] == "accepted"]
    residual = [row for row in decisions if row["disposition"] != "accepted"]
    output.mkdir(parents=True, exist_ok=True)
    _write(output / "decisions.jsonl", decisions)
    _write(output / "accepted.jsonl", accepted)
    _write(output / "residual_wishlist.jsonl", residual)
    summary = {
        "schema_version": "ninereeds_campaign35_word_round_reconciliation_v1",
        "status": "reconciled_not_frozen",
        "required_slots": 25_000,
        "accepted_slots": len(accepted),
        "residual_slots": len(residual),
        "accepted_from_follow_up_round": sum(
            row["disposition"] == "accepted" and row["decision_round"] == "follow_up"
            for row in decisions
        ),
        "dispositions": dict(sorted(Counter(row["disposition"] for row in decisions).items())),
        "exact_partition": len(accepted) + len(residual) == 25_000,
        "prior_sha256": _sha256(prior_path),
        "follow_up_sha256": _sha256(round_path),
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior", type=Path, required=True)
    parser.add_argument("--round", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reconcile(args.prior, args.round, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
