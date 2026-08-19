"""Review several external image candidates per Campaign 35 residual slot."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from .campaign35_word_review_export import classify
from .cli import connect


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_rows(path: Path, values: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values),
        encoding="utf-8",
    )


def virtualize(candidate_paths: list[Path], output: Path) -> dict[str, Any]:
    candidates = [row for path in candidate_paths for row in rows(path)]
    virtual = []
    seen = set()
    per_slot: Counter[str] = Counter()
    for candidate in candidates:
        identity = (candidate["source"], str(candidate["source_image_id"]), candidate["slot_id"])
        if identity in seen:
            continue
        seen.add(identity)
        per_slot[candidate["slot_id"]] += 1
        suffix = hashlib.sha256("\0".join(identity).encode("utf-8")).hexdigest()[:16]
        virtual.append({
            **candidate,
            "target_slot_id": candidate["slot_id"],
            "target_sequence_position": candidate["sequence_position"],
            "slot_id": f"{candidate['slot_id']}::candidate::{suffix}",
            "sequence_position": len(virtual) + 1,
            "candidate_rank_for_slot": candidate.get(
                "candidate_rank_for_slot", per_slot[candidate["slot_id"]]
            ),
        })
    output.mkdir(parents=True, exist_ok=True)
    write_rows(output / "candidates.jsonl", virtual)
    summary = {
        "schema_version": "ninereeds_campaign35_candidate_pool_v1",
        "candidate_claims": len(virtual), "target_slots": len(per_slot),
        "maximum_candidates_per_slot": max(per_slot.values(), default=0),
        "status": "virtual_candidate_claims_ready_for_pixel_review",
    }
    (output / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return summary


def export(
    db_path: Path, queue: str, requirements_path: Path, candidate_map_path: Path,
    output: Path, *, watermark_queue: str | None = None, usability_queue: str | None = None,
    word_fit_queue: str | None = None, sol_word_fit_queue: str | None = None,
) -> dict[str, Any]:
    requirements = rows(requirements_path)
    if len(requirements) != 25_000:
        raise ValueError("Campaign 35 requirements must contain exactly 25,000 slots")
    candidates = rows(candidate_map_path)
    candidate_requirements = [{
        "slot_id": row["slot_id"], "word": row["word"], "concept": row["concept"],
        "ordinal": row["ordinal"], "exposure_index": row["exposure_index"],
        "sequence_position": row["sequence_position"],
    } for row in candidates]
    mapping = {row["slot_id"]: row for row in candidates}
    with connect(db_path) as db:
        candidate_decisions = classify(
            db, queue, candidate_requirements,
            watermark_queue=watermark_queue, usability_queue=usability_queue,
            word_fit_queue=word_fit_queue, sol_word_fit_queue=sol_word_fit_queue,
        )
    accepted_by_target: dict[str, list[dict[str, Any]]] = {}
    mapped_decisions = []
    for decision in candidate_decisions:
        source = mapping[decision["slot_id"]]
        mapped = {
            **decision,
            "candidate_slot_id": decision["slot_id"],
            "target_slot_id": source["target_slot_id"],
            "target_sequence_position": source["target_sequence_position"],
            "candidate_rank_for_slot": source["candidate_rank_for_slot"],
        }
        mapped_decisions.append(mapped)
        if decision["disposition"] == "accepted":
            accepted_by_target.setdefault(source["target_slot_id"], []).append(mapped)
    final = []
    selected_candidate_ids = set()
    for requirement in requirements:
        accepted = sorted(
            accepted_by_target.get(requirement["slot_id"], []),
            key=lambda row: (row["candidate_rank_for_slot"], row["asset_id"]),
        )
        if not accepted:
            final.append({**requirement, "disposition": "missing_candidate"})
            continue
        chosen = accepted[0]
        selected_candidate_ids.add(chosen["candidate_slot_id"])
        final.append({
            **chosen, **requirement,
            "candidate_slot_id": chosen["candidate_slot_id"],
            "disposition": "accepted",
        })
    for row in mapped_decisions:
        row["selected_for_target_slot"] = row["candidate_slot_id"] in selected_candidate_ids
    final.sort(key=lambda row: row["sequence_position"])
    output.mkdir(parents=True, exist_ok=True)
    write_rows(output / "decisions.jsonl", final)
    write_rows(output / "candidate-decisions.jsonl", mapped_decisions)
    write_rows(
        output / "surplus-accepted.jsonl",
        [row for row in mapped_decisions if row["disposition"] == "accepted" and not row["selected_for_target_slot"]],
    )
    dispositions = Counter(row["disposition"] for row in mapped_decisions)
    summary = {
        "schema_version": "ninereeds_campaign35_candidate_pool_export_v1",
        "required_slots": len(requirements), "candidate_claims": len(mapped_decisions),
        "candidate_dispositions": dict(sorted(dispositions.items())),
        "accepted_target_slots": len(selected_candidate_ids),
        "surplus_accepted_candidates": dispositions.get("accepted", 0) - len(selected_candidate_ids),
        "status": "review_complete_not_frozen",
    }
    (output / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("virtualize")
    make.add_argument("--candidate", type=Path, action="append", required=True)
    make.add_argument("--output", type=Path, required=True)
    freeze = sub.add_parser("export")
    freeze.add_argument("--db", type=Path, required=True)
    freeze.add_argument("--queue", required=True)
    freeze.add_argument("--requirements", type=Path, required=True)
    freeze.add_argument("--candidate-map", type=Path, required=True)
    freeze.add_argument("--output", type=Path, required=True)
    freeze.add_argument("--watermark-queue")
    freeze.add_argument("--usability-queue")
    freeze.add_argument("--word-fit-queue")
    freeze.add_argument("--sol-word-fit-queue")
    args = parser.parse_args()
    if args.command == "virtualize":
        result = virtualize(args.candidate, args.output)
    else:
        result = export(
            args.db, args.queue, args.requirements, args.candidate_map, args.output,
            watermark_queue=args.watermark_queue, usability_queue=args.usability_queue,
            word_fit_queue=args.word_fit_queue, sol_word_fit_queue=args.sol_word_fit_queue,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
