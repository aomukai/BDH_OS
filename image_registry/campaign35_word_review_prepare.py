"""Resolve Campaign 35 word-image proposals into one immutable semantic queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .campaign35_word_review import initialize_queue
from .cli import DEFAULT_DB, connect


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def resolve_bindings(
    db,
    registry_proposal: Path,
    metadata_proposals: list[Path],
    mechanically_ready_selection: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ready = {
        row["asset_id"]
        for row in db.execute(
            "SELECT asset_id FROM selection WHERE name=?",
            (mechanically_ready_selection,),
        )
    }
    if not ready:
        raise ValueError(f"mechanically ready selection is empty: {mechanically_ready_selection}")

    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in _rows(registry_proposal):
        asset = db.execute(
            "SELECT id,status,local_path,sha256 FROM asset WHERE id=?", (row["asset_id"],),
        ).fetchone()
        if (
            asset is None
            or asset["status"] != "reviewed_usable"
            or not asset["local_path"]
            or not asset["sha256"]
        ):
            raise ValueError(f"registry proposal references an unavailable reviewed asset: {row['asset_id']}")
        accepted.append({
            "slot_id": row["slot_id"], "asset_id": row["asset_id"],
            "word": row["word"], "concept": row["concept"],
            "concept_id": row.get("concept_id"),
            "teaching_sense": row.get("teaching_sense"),
            "ordinal": row["ordinal"], "exposure_index": row["exposure_index"],
            "sequence_position": row["sequence_position"],
            "source_caption": row.get("caption"), "candidate_tier": "reviewed_registry_word_match",
        })

    for proposal in metadata_proposals:
        default_tier = "localized_narrative_word_match" if "metadata" in proposal.parent.name else "visual_genome_region_word_match"
        for row in _rows(proposal):
            asset = db.execute(
                "SELECT id FROM asset WHERE source=? AND source_id=?",
                (row["source"], str(row["source_image_id"])),
            ).fetchone()
            if asset is None:
                raise ValueError(
                    f"metadata proposal was not admitted: {row['source']}:{row['source_image_id']}"
                )
            binding = {
                "slot_id": row["slot_id"], "asset_id": asset["id"],
                "word": row["word"], "concept": row["concept"],
                "concept_id": row.get("concept_id"),
                "teaching_sense": row.get("teaching_sense"),
                "ordinal": row["ordinal"], "exposure_index": row["exposure_index"],
                "sequence_position": row["sequence_position"],
                "source_caption": row.get("caption"),
                "candidate_tier": row.get("candidate_tier", default_tier),
            }
            if asset["id"] in ready:
                accepted.append(binding)
            else:
                excluded.append({**binding, "reason": "failed_mechanical_inspection"})

    accepted.sort(key=lambda row: row["sequence_position"])
    excluded.sort(key=lambda row: row["sequence_position"])
    slot_ids = [row["slot_id"] for row in accepted]
    positions = [row["sequence_position"] for row in accepted]
    if len(slot_ids) != len(set(slot_ids)):
        raise ValueError("resolved proposals assign more than one candidate to a slot")
    if len(positions) != len(set(positions)):
        raise ValueError("resolved proposals contain duplicate sequence positions")
    return accepted, excluded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--registry-proposal", type=Path, required=True)
    parser.add_argument("--metadata-proposal", type=Path, action="append", required=True)
    parser.add_argument("--mechanically-ready-selection", required=True)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with connect(args.db) as db:
        bindings, excluded = resolve_bindings(
            db, args.registry_proposal, args.metadata_proposal,
            args.mechanically_ready_selection,
        )
        result = initialize_queue(
            db, args.queue, bindings, selection_name=args.selection,
        )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "bindings.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in bindings),
        encoding="utf-8",
    )
    (args.output / "mechanically_excluded.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in excluded),
        encoding="utf-8",
    )
    summary = {**result, "mechanically_excluded_slot_bindings": len(excluded)}
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
