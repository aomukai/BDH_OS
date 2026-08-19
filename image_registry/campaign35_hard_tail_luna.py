"""Adjudicate a tiny generated Campaign 35 semantic tail with Luna."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

from image_benchmark.luna_word_fit_worker import review


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(list(argv) if argv is not None else None)

    decisions = load_jsonl(args.decisions)
    inventory = {
        row["concept_id"]: row for row in load_jsonl(args.inventory)
        if row["route"] in {"single_image", "single_image_empirically_demonstrated"}
    }
    residual_ids = {
        row["slot_id"] for row in decisions
        if row.get("disposition") != "accepted" and (row.get("concept_id") or row.get("word")) in inventory
    }
    candidates = [
        row for row in decisions
        if row["slot_id"] in residual_ids and row.get("source") == args.source
    ]
    if {row["slot_id"] for row in candidates} != residual_ids:
        raise ValueError("the selected generated source does not exactly cover the hard tail")

    args.output.mkdir(parents=True, exist_ok=True)
    review_args = SimpleNamespace(codex=args.codex, model=args.model, timeout=args.timeout)
    adjudications: list[dict[str, Any]] = []
    accepted_by_slot: dict[str, dict[str, Any]] = {}
    for row in candidates:
        path = Path(row["local_path"])
        if not path.is_file() or digest(path) != row["sha256"]:
            raise ValueError(f"hard-tail image bytes fail validation: {row['slot_id']}")
        word = str(row.get("word") or row.get("concept") or row["concept_id"]).casefold()
        result, transcript = review(path, [word], review_args)
        target = result["targets"][0]
        evidence = {
            "schema_version": "ninereeds_campaign35_hard_tail_luna_v1",
            "slot_id": row["slot_id"], "concept_id": row.get("concept_id"),
            "word": word, "asset_id": row.get("asset_id"), "source": args.source,
            "local_path": str(path), "sha256": row["sha256"],
            "verdict": target["verdict"], "reason": target["reason"],
            "summary_reason": result["reason"], "model": args.model,
            "transcript": transcript,
        }
        adjudications.append(evidence)
        if target["verdict"] == "accept":
            accepted_by_slot[row["slot_id"]] = evidence

    reconciled: list[dict[str, Any]] = []
    for row in decisions:
        evidence = accepted_by_slot.get(row["slot_id"])
        if evidence is None:
            reconciled.append(row)
            continue
        reconciled.append({
            **row,
            "prior_disposition": row.get("disposition"),
            "disposition": "accepted",
            "decision_round": "hard_tail_luna",
            "review_backend": "codex",
            "review_model": args.model,
            "review_worker": "campaign35-hard-tail-luna",
            "target_evidence": evidence["reason"],
            "uncertainties": [],
        })

    if len(reconciled) != 25_000 or len({row["slot_id"] for row in reconciled}) != 25_000:
        raise ValueError("hard-tail adjudication changed the exact Campaign 35 partition")
    write_jsonl(args.output / "adjudications.jsonl", adjudications)
    write_jsonl(args.output / "decisions.jsonl", reconciled)
    summary = {
        "schema_version": "ninereeds_campaign35_hard_tail_luna_v1",
        "source": args.source, "reviewed_slots": len(candidates),
        "accepted_slots": len(accepted_by_slot),
        "rejected_slots": sum(row["verdict"] == "reject" for row in adjudications),
        "uncertain_slots": sum(row["verdict"] == "uncertain" for row in adjudications),
        "input_decisions_sha256": digest(args.decisions),
        "output_decisions_sha256": digest(args.output / "decisions.jsonl"),
        "status": "adjudicated",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
