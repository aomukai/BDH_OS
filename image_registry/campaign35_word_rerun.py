"""Build a re-entrant Campaign 35 word-image review round.

Accepted slot bindings are protected.  Unresolved slots receive only locally
available registry candidates that have not previously been tried for the same
word.  The remaining slots form the exact external-acquisition wishlist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import sqlite3
from typing import Any

from .cli import DEFAULT_DB, connect
from .campaign35_word_review import initialize_queue


SCHEMA_VERSION = "ninereeds_campaign35_word_image_rerun_v1"


def _rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_decisions(rows: list[dict[str, Any]]) -> None:
    if len(rows) != 25_000:
        raise ValueError(f"expected exactly 25,000 slot decisions, found {len(rows)}")
    slots = [row.get("slot_id") for row in rows]
    positions = [row.get("sequence_position") for row in rows]
    if len(set(slots)) != len(slots) or None in slots:
        raise ValueError("decisions do not contain 25,000 unique slot IDs")
    if sorted(positions) != list(range(1, 25_001)):
        raise ValueError("decision sequence positions are not exactly 1..25000")


def _available_assets(db: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    return {
        row["id"]: dict(row)
        for row in db.execute(
            """SELECT id,status,local_path,sha256,source,source_id,width,height
               FROM asset
               WHERE local_path IS NOT NULL AND sha256 IS NOT NULL
                 AND status NOT LIKE 'deleted_%'"""
        )
    }


def _attempted_by_concept(
    db: sqlite3.Connection, queue_names: list[str],
) -> dict[str, set[int]]:
    attempted: dict[str, set[int]] = defaultdict(set)
    for queue_name in queue_names:
        for row in db.execute(
            """SELECT concept,asset_id FROM campaign35_word_review_slot_binding
               WHERE queue_name=?""",
            (queue_name,),
        ):
            attempted[row["concept"]].add(row["asset_id"])
    return attempted


def build_rerun(
    db: sqlite3.Connection,
    decisions_path: Path,
    candidate_pools_path: Path,
    output_root: Path,
    *,
    prior_queues: list[str],
    max_asset_uses: int = 4,
) -> dict[str, Any]:
    if max_asset_uses < 1:
        raise ValueError("max_asset_uses must be positive")
    decisions = _rows(decisions_path)
    _validate_decisions(decisions)
    pools = _rows(candidate_pools_path)
    pool_by_ordinal = {row["ordinal"]: row for row in pools}
    if len(pool_by_ordinal) != 2_500:
        raise ValueError(
            f"expected candidate pools for 2,500 curriculum ordinals, found {len(pool_by_ordinal)}"
        )

    available = _available_assets(db)
    attempted = _attempted_by_concept(db, prior_queues)
    protected: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    accepted_assets_by_concept: dict[str, set[int]] = defaultdict(set)
    accepted_hashes_by_concept: dict[str, set[str]] = defaultdict(set)
    asset_use_counts: Counter[int] = Counter()

    for decision in sorted(decisions, key=lambda row: row["sequence_position"]):
        if decision["disposition"] != "accepted":
            unresolved.append(decision)
            continue
        asset_id = decision.get("asset_id")
        asset = available.get(asset_id)
        if asset is None:
            raise ValueError(
                f"accepted slot {decision['slot_id']} references unavailable asset {asset_id}"
            )
        if decision.get("sha256") and decision["sha256"] != asset["sha256"]:
            raise ValueError(f"accepted slot {decision['slot_id']} changed sha256")
        protected.append({
            **decision,
            "protected": True,
            "protection_reason": "accepted_in_prior_review_round",
        })
        accepted_assets_by_concept[decision["concept_id"]].add(asset_id)
        accepted_hashes_by_concept[decision["concept_id"]].add(asset["sha256"])
        asset_use_counts[asset_id] += 1

    over_cap = {asset_id: uses for asset_id, uses in asset_use_counts.items() if uses > max_asset_uses}
    if over_cap:
        raise ValueError(
            f"protected decisions already exceed max_asset_uses={max_asset_uses}: "
            f"{len(over_cap)} asset(s)"
        )

    candidates_by_ordinal: dict[int, list[dict[str, Any]]] = {}
    for ordinal, pool in pool_by_ordinal.items():
        word = pool["word"]
        concept_id = pool.get("concept_id") or pool.get("concept") or word
        concept = pool.get("concept") or concept_id
        candidates: list[dict[str, Any]] = []
        seen_assets = set(accepted_assets_by_concept[concept_id])
        seen_hashes = set(accepted_hashes_by_concept[concept_id])
        for candidate in pool.get("candidates", []):
            asset_id = candidate["asset_id"]
            asset = available.get(asset_id)
            if (
                asset is None
                or asset_id in attempted[concept]
                or asset_id in seen_assets
                or asset["sha256"] in seen_hashes
            ):
                continue
            seen_assets.add(asset_id)
            seen_hashes.add(asset["sha256"])
            candidates.append({**candidate, **asset})
        candidates_by_ordinal[ordinal] = candidates

    proposal: list[dict[str, Any]] = []
    wishlist: list[dict[str, Any]] = []
    remaining_candidates = {
        ordinal: list(candidates) for ordinal, candidates in candidates_by_ordinal.items()
    }
    for decision in unresolved:
        word = decision["word"]
        ordinal = decision["ordinal"]
        candidates = remaining_candidates.get(ordinal, [])
        eligible = [
            (asset_use_counts[candidate["asset_id"]], index, candidate)
            for index, candidate in enumerate(candidates)
            if asset_use_counts[candidate["asset_id"]] < max_asset_uses
        ]
        if not eligible:
            wishlist.append({
                "slot_id": decision["slot_id"],
                "sequence_position": decision["sequence_position"],
                "ordinal": decision["ordinal"],
                "concept": decision["concept"],
                "concept_id": decision.get("concept_id"),
                "teaching_sense": decision.get("teaching_sense"),
                "word": word,
                "exposure_index": decision["exposure_index"],
                "prior_disposition": decision["disposition"],
                "status": "unresolved_after_untried_registry_candidates",
                "next_action": "search_external_metadata_then_flux_as_last_resort",
            })
            continue
        _, index, candidate = min(eligible, key=lambda item: (item[0], item[1]))
        candidates.pop(index)
        asset_use_counts[candidate["asset_id"]] += 1
        proposal.append({
            "slot_id": decision["slot_id"],
            "asset_id": candidate["asset_id"],
            "word": word,
            "concept": decision["concept"],
            "concept_id": decision.get("concept_id"),
            "teaching_sense": decision.get("teaching_sense"),
            "ordinal": decision["ordinal"],
            "exposure_index": decision["exposure_index"],
            "sequence_position": decision["sequence_position"],
            "source_caption": candidate.get("caption"),
            "candidate_tier": "reviewed_registry_untried_word_match",
            "prior_disposition": decision["disposition"],
            "sha256": candidate["sha256"],
            "local_path": candidate["local_path"],
            "source": candidate["source"],
            "source_id": candidate["source_id"],
        })

    output_root.mkdir(parents=True, exist_ok=True)
    _jsonl(output_root / "protected_accepted.jsonl", protected)
    _jsonl(output_root / "selection_proposal.jsonl", proposal)
    _jsonl(output_root / "wishlist.jsonl", wishlist)
    accounting = len(protected) + len(proposal) + len(wishlist)
    if accounting != 25_000:
        raise AssertionError(f"slot partition is not exact: {accounting}")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "round_proposal_pending_pixel_review",
        "required_slots": 25_000,
        "protected_accepted_slots": len(protected),
        "new_registry_review_slots": len(proposal),
        "external_wishlist_slots": len(wishlist),
        "exact_partition": accounting == 25_000,
        "prior_queues": prior_queues,
        "decisions_sha256": _sha256(decisions_path),
        "candidate_pools_sha256": _sha256(candidate_pools_path),
        "policy": {
            "accepted_slots_are_immutable": True,
            "rejected_candidates_are_not_recycled_for_the_same_word": True,
            "deleted_or_unavailable_assets_are_excluded": True,
            "external_metadata_search_precedes_flux": True,
            "max_asset_uses": max_asset_uses,
            "least_used_suitable_asset_is_preferred": True,
        },
    }
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--candidate-pools", type=Path, required=True)
    parser.add_argument("--prior-queue", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--queue")
    parser.add_argument("--selection")
    parser.add_argument("--max-asset-uses", type=int, default=4)
    args = parser.parse_args()
    with connect(args.db) as db:
        summary = build_rerun(
            db, args.decisions, args.candidate_pools, args.output,
            prior_queues=args.prior_queue,
            max_asset_uses=args.max_asset_uses,
        )
        if args.queue:
            proposal = _rows(args.output / "selection_proposal.jsonl")
            if not proposal:
                raise ValueError("cannot initialize an empty rerun review queue")
            queue_result = initialize_queue(
                db, args.queue, proposal,
                selection_name=args.selection or args.queue,
            )
            summary["review_queue"] = queue_result
            (args.output / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
