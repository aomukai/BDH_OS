"""Freeze all local-registry candidates for Campaign 36 replacement-word review."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from image_registry.campaign35_word_review import initialize_queue
from image_registry.cli import connect


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--candidate-pools", type=Path, required=True)
    parser.add_argument("--replacement-map", type=Path, required=True)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mapping = {
        int(row["replacement_rank"]): row for row in rows(args.replacement_map)
    }
    bindings = []
    sequence = 0
    for pool in rows(args.candidate_pools):
        rank = int(pool["replacement_rank"])
        ordinal = int(mapping[rank]["ordinal"])
        for candidate_rank, candidate in enumerate(pool["candidates"], 1):
            sequence += 1
            identity = f'{rank}\0{candidate["asset_id"]}\0{pool["term"]}'
            suffix = hashlib.sha256(identity.encode()).hexdigest()[:16]
            bindings.append({
                "slot_id": f"c{ordinal:04d}::local::{suffix}",
                "asset_id": candidate["asset_id"],
                "word": pool["term"],
                "concept": pool["term"],
                "concept_id": pool["term"],
                "teaching_sense": pool["teaching_sense"],
                "ordinal": ordinal,
                "exposure_index": candidate_rank,
                "sequence_position": sequence,
                "source_caption": candidate.get("caption"),
                "candidate_tier": "reviewed_registry_exact_token_candidate",
            })
    with connect(args.db) as db:
        result = initialize_queue(
            db, args.queue, bindings, selection_name=args.selection,
        )
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "bindings.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in bindings),
        encoding="utf-8",
    )
    summary = {
        **result,
        "word_image_claims": len(bindings),
        "unique_images": result["items"],
        "policy": "review every bounded local candidate; select best ten accepted per word later",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
