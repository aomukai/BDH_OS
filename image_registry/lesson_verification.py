"""Create and export claim-specific Luna pixel-verification work."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from .cli import DEFAULT_DB, connect
from .review_queue import create_queue, ensure_schema, queue_status


DEFAULT_QUEUE = "campaign35-luna-pixel-verification-v2"
DEFAULT_SELECTION = "campaign35-material-proposal-v1"


def load_proposal(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # Acquisition-loop proposals name the authoritative field
    # ``exact_teaching_claim``.  Normalize it to the historical Luna worker
    # interface so every proposal route uses the same pixel-verification queue.
    for row in rows:
        if "intended_teaching_claim" not in row and "exact_teaching_claim" in row:
            row["intended_teaching_claim"] = row["exact_teaching_claim"]
    required = {
        "item_id", "asset_id", "path", "sha256", "concept",
        "intended_teaching_claim", "query_tier", "verification_status",
    }
    if not rows:
        raise ValueError("selection proposal is empty")
    for row in rows:
        missing = required - set(row)
        if missing:
            raise ValueError(f"proposal row lacks {sorted(missing)}")
        if row["verification_status"] != "pending_luna_pixel_verification":
            raise ValueError(f"item is not pending Luna verification: {row['item_id']}")
    if len({row["item_id"] for row in rows}) != len(rows):
        raise ValueError("proposal repeats an item_id")
    if len({row["asset_id"] for row in rows}) != len(rows):
        raise ValueError("proposal repeats an asset_id")
    return rows


def initialize_queue(
    db: sqlite3.Connection,
    proposal: list[dict[str, Any]],
    *,
    selection_name: str,
    queue_name: str,
) -> dict[str, Any]:
    """Freeze the proposal as an immutable selection and create its queue."""
    ensure_schema(db)
    expected = [(row["asset_id"], ordinal) for ordinal, row in enumerate(proposal)]
    for row in proposal:
        asset = db.execute(
            "SELECT status,local_path,sha256 FROM asset WHERE id=?", (row["asset_id"],),
        ).fetchone()
        if asset is None:
            raise ValueError(f"proposal asset is absent: {row['asset_id']}")
        if asset["status"] != "reviewed_usable":
            raise ValueError(f"proposal asset is not reviewed_usable: {row['asset_id']}")
        if asset["local_path"] != row["path"] or asset["sha256"] != row["sha256"]:
            raise ValueError(f"proposal asset authority changed: {row['asset_id']}")

    existing_selection = [
        (row["asset_id"], row["ordinal"]) for row in db.execute(
            "SELECT asset_id,ordinal FROM selection WHERE name=? ORDER BY ordinal",
            (selection_name,),
        )
    ]
    selection_created = False
    if existing_selection:
        if existing_selection != expected:
            raise ValueError(f"immutable selection differs: {selection_name}")
    else:
        db.executemany(
            "INSERT INTO selection(name,asset_id,stratum,ordinal) VALUES (?,?,'pending_luna_pixel_verification',?)",
            ((selection_name, asset_id, ordinal) for asset_id, ordinal in expected),
        )
        db.commit()
        selection_created = True

    existing_queue = [
        (row["asset_id"], row["ordinal"]) for row in db.execute(
            "SELECT asset_id,ordinal FROM review_queue WHERE queue_name=? ORDER BY ordinal",
            (queue_name,),
        )
    ]
    queue_created = False
    if existing_queue:
        if existing_queue != expected:
            raise ValueError(f"immutable queue differs: {queue_name}")
    else:
        create_queue(db, queue_name, selection_name)
        queue_created = True
    return {
        "selection": selection_name,
        "queue": queue_name,
        "items": len(expected),
        "selection_created": selection_created,
        "queue_created": queue_created,
        "status": queue_status(db, queue_name),
    }


def export_results(
    db: sqlite3.Connection,
    proposal: list[dict[str, Any]],
    queue_name: str,
    output: Path,
    base_wishlist: Path | None = None,
) -> dict[str, int]:
    by_asset = {row["asset_id"]: row for row in proposal}
    buckets: dict[str, list[dict[str, Any]]] = {
        "accepted": [], "rejected": [], "uncertain": [], "unfinished": [],
    }
    for row in db.execute(
        "SELECT asset_id,ordinal,status,result_json FROM review_queue WHERE queue_name=? ORDER BY ordinal",
        (queue_name,),
    ):
        proposal_row = by_asset[row["asset_id"]]
        if row["status"] != "completed":
            bucket = "unfinished"
            result = None
        else:
            result = json.loads(row["result_json"])
            bucket = {
                "accept": "accepted", "reject": "rejected", "uncertain": "uncertain",
            }[result["verdict"]]
        buckets[bucket].append({
            **proposal_row,
            "queue_ordinal": row["ordinal"],
            "queue_status": row["status"],
            "luna_result": result,
        })
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in buckets.items():
        (output / f"{name}.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in rows),
            encoding="utf-8",
        )
    metadata_needs: list[dict[str, Any]] = []
    if base_wishlist is not None:
        for line in base_wishlist.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            claims = {item["item_id"]: item["teaching_claim"] for item in row["teaching_needs"]}
            for item_id in row["item_ids"]:
                metadata_needs.append({
                    "schema_version": "ninereeds_metadata_material_need_v1",
                    "item_id": item_id, "concept": row["concept"],
                    "teaching_claim": claims[item_id], "need_origin": "sol_residual",
                    "gap_class": row["gap_class"],
                    "acceptable_alternatives": row["acceptable_alternatives"],
                    "prior_asset_id": None, "luna_reason": None, "disqualifiers": [],
                })
    for bucket in ("rejected", "uncertain"):
        for row in buckets[bucket]:
            result = row["luna_result"]
            metadata_needs.append({
                "schema_version": "ninereeds_metadata_material_need_v1",
                "item_id": row["item_id"], "concept": row["concept"],
                "teaching_claim": row["intended_teaching_claim"],
                "need_origin": f"luna_{bucket[:-2] if bucket.endswith('ed') else bucket}",
                "gap_class": "rejected_provisional_assignment" if bucket == "rejected" else "uncertain_provisional_assignment",
                "acceptable_alternatives": [], "prior_asset_id": row["asset_id"],
                "luna_reason": result["reason"],
                "disqualifiers": result.get("disqualifiers", []),
            })
    if metadata_needs:
        metadata_needs.sort(key=lambda row: row["item_id"])
        if len({row["item_id"] for row in metadata_needs}) != len(metadata_needs):
            raise ValueError("metadata needs contain duplicate item IDs")
        (output / "metadata_needs.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in metadata_needs),
            encoding="utf-8",
        )
    summary = {name: len(rows) for name, rows in buckets.items()}
    summary["metadata_need_items"] = len(metadata_needs)
    (output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    return summary


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--queue", default=DEFAULT_QUEUE)
    parser.add_argument("--selection", default=DEFAULT_SELECTION)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("initialize")
    export = commands.add_parser("export")
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--base-wishlist", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    proposal = load_proposal(args.proposal)
    with connect(args.db) as db:
        if args.command == "initialize":
            result = initialize_queue(
                db, proposal, selection_name=args.selection, queue_name=args.queue,
            )
        else:
            result = export_results(
                db, proposal, args.queue, args.output, base_wishlist=args.base_wishlist,
            )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
