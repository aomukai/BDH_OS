"""Choose the first corpus-approved candidate per claim for Luna pixel verification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from .cli import DEFAULT_DB, connect


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _prior_verification(paths: list[Path]) -> tuple[set[str], set[int]]:
    resolved_items: set[str] = set()
    excluded_assets: set[int] = set()
    for root in paths:
        for row in _load(root / "accepted.jsonl"):
            resolved_items.add(row["item_id"])
        for name in ("rejected.jsonl", "uncertain.jsonl"):
            for row in _load(root / name):
                excluded_assets.add(int(row["asset_id"]))
    return resolved_items, excluded_assets


def build(
    db: Any, candidates_path: Path, prior_verification: list[Path] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in _load(candidates_path):
        grouped.setdefault(row["item_id"], []).append(row)
    proposals: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    used_assets: set[int] = set()
    resolved_items, excluded_assets = _prior_verification(prior_verification or [])
    for item_id, candidates in grouped.items():
        if item_id in resolved_items:
            continue
        chosen = None
        attempts = []
        for candidate in sorted(candidates, key=lambda row: row["candidate_rank"]):
            asset = db.execute(
                """SELECT id,local_path,sha256,status FROM asset
                    WHERE source=? AND source_id=?""",
                (candidate.get("source", "open_images_v7"), candidate["source_image_id"]),
            ).fetchone()
            attempts.append({
                "source_image_id": candidate["source_image_id"],
                "candidate_rank": candidate["candidate_rank"],
                "registry_status": None if asset is None else asset["status"],
            })
            if (
                asset is not None and asset["status"] == "reviewed_usable"
                and asset["local_path"] and asset["sha256"]
                and asset["id"] not in used_assets and asset["id"] not in excluded_assets
            ):
                chosen = (candidate, asset)
                break
        if chosen is None:
            first = candidates[0]
            unresolved.append({
                "item_id": item_id, "concept": first["concept"],
                "exact_teaching_claim": first["exact_teaching_claim"],
                "reason": "no_corpus_approved_candidate",
                "candidate_attempts": attempts,
                "next_route": "next_external_candidate_or_representation_reassessment",
            })
            continue
        candidate, asset = chosen
        used_assets.add(asset["id"])
        proposals.append({
            "schema_version": "ninereeds_claim_selection_proposal_v1",
            "item_id": item_id,
            "asset_id": asset["id"],
            "path": asset["local_path"],
            "sha256": asset["sha256"],
            "concept": candidate["concept"],
            "exact_teaching_claim": candidate["exact_teaching_claim"],
            "query_tier": candidate["retrieval_evidence"]["kind"],
            "source": candidate.get("source", "open_images_v7"),
            "source_image_id": candidate["source_image_id"],
            "candidate_rank": candidate["candidate_rank"],
            "retrieval_evidence": candidate["retrieval_evidence"],
            "source_metadata": candidate["source_metadata"],
            "verification_status": "pending_luna_pixel_verification",
        })
    return proposals, unresolved


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior-verification", type=Path, action="append", default=[])
    args = parser.parse_args(list(argv) if argv is not None else None)
    with connect(args.db) as db:
        proposals, unresolved = build(db, args.candidates, args.prior_verification)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, rows in (("selection_proposal", proposals), ("unresolved", unresolved)):
        (args.output / f"{name}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
    summary = {
        "candidate_items": len({row["item_id"] for row in _load(args.candidates)}),
        "proposed": len(proposals), "unresolved": len(unresolved),
        "status": "pending_luna_pixel_verification" if proposals else "no_proposals",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
