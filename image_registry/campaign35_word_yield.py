"""Aggregate per-concept target-fit yield and route consistent low performers.

The curriculum can contain the same surface word more than once (for example
``kind`` and ``kind 2``).  Routing therefore uses ``concept_id`` rather than
silently combining distinct curriculum entries, while retaining ``word`` in
the human-facing ledger.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any


def rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_rows(path: Path, values: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values),
        encoding="utf-8",
    )


def analyze(
    loop_root: Path,
    authoritative_decisions: Path,
    output: Path,
    *,
    yield_floor: float = 0.15,
    minimum_attempts: int = 8,
    minimum_rounds: int = 2,
) -> dict[str, Any]:
    aggregate: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "attempt_keys": set(), "accepted_keys": set(), "rounds": set(), "sources": set(),
        "words": set(), "concepts": set(),
    })
    scanned_rounds = []
    for round_root in sorted(loop_root.glob("round-[0-9][0-9][0-9][0-9]")):
        decisions_root = round_root / "semantic-decisions"
        candidate_path = decisions_root / "candidate-decisions.jsonl"
        decision_path = candidate_path if candidate_path.is_file() else decisions_root / "decisions.jsonl"
        records = rows(decision_path)
        if not records:
            continue
        round_number = int(round_root.name.rsplit("-", 1)[1])
        scanned_rounds.append(round_number)
        for record in records:
            disposition = record.get("disposition")
            if disposition == "missing_candidate":
                continue
            word = str(record.get("word", "")).strip()
            concept_id = str(record.get("concept_id") or word).strip()
            if not concept_id:
                continue
            target_slot = str(record.get("target_slot_id") or record.get("slot_id") or "")
            candidate_slot = str(record.get("candidate_slot_id") or record.get("slot_id") or "")
            asset_id = str(record.get("asset_id") or record.get("source_id") or "")
            key = (round_number, target_slot, candidate_slot, asset_id)
            item = aggregate[concept_id]
            item["attempt_keys"].add(key)
            item["rounds"].add(round_number)
            item["words"].add(word or concept_id)
            item["concepts"].add(str(record.get("concept") or word or concept_id))
            source = record.get("source")
            if source:
                item["sources"].add(str(source))
            if disposition == "accepted":
                item["accepted_keys"].add(key)

    residual_by_concept: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in rows(authoritative_decisions):
        if record.get("disposition") != "accepted":
            concept_id = str(record.get("concept_id") or record.get("word", "")).strip()
            residual_by_concept[concept_id].append(record)

    yields = []
    low_concepts = set()
    for concept_id in sorted(set(aggregate) | set(residual_by_concept)):
        item = aggregate[concept_id]
        attempts = len(item["attempt_keys"])
        accepted = len(item["accepted_keys"])
        rate = accepted / attempts if attempts else None
        remaining = len(residual_by_concept[concept_id])
        low = bool(
            remaining
            and attempts >= minimum_attempts
            and len(item["rounds"]) >= minimum_rounds
            and rate is not None
            and rate < yield_floor
        )
        if low:
            low_concepts.add(concept_id)
        residual_example = residual_by_concept[concept_id][0] if remaining else {}
        word = str(residual_example.get("word") or next(iter(item["words"]), concept_id))
        concept = str(residual_example.get("concept") or next(iter(item["concepts"]), word))
        yields.append({
            "concept_id": concept_id,
            "concept": concept,
            "word": word,
            "reviewed_candidate_claims": attempts,
            "accepted_candidate_claims": accepted,
            "target_fit_yield": rate,
            "rounds_with_attempts": sorted(item["rounds"]),
            "source_count": len(item["sources"]),
            "sources": sorted(item["sources"]),
            "remaining_slots": remaining,
            "routing": (
                "representation_triage_then_flux_if_single_image"
                if low else "external_search_still_eligible"
            ),
        })

    low_yields = [row for row in yields if row["concept_id"] in low_concepts]
    external_needs = [
        record for concept_id, records in residual_by_concept.items() if concept_id not in low_concepts
        for record in records
    ]
    specialist_needs = [
        record for concept_id, records in residual_by_concept.items() if concept_id in low_concepts
        for record in records
    ]
    external_needs.sort(key=lambda row: row["sequence_position"])
    specialist_needs.sort(key=lambda row: row["sequence_position"])
    output.mkdir(parents=True, exist_ok=True)
    write_rows(output / "word-yields.jsonl", yields)
    write_rows(output / "low-yield-words.jsonl", low_yields)
    write_rows(output / "external-needs.jsonl", external_needs)
    write_rows(output / "specialist-needs.jsonl", specialist_needs)
    summary = {
        "schema_version": "ninereeds_campaign35_word_yield_routing_v1",
        "scanned_rounds": scanned_rounds,
        "yield_floor": yield_floor,
        "minimum_attempts": minimum_attempts,
        "minimum_rounds": minimum_rounds,
        "residual_slots": sum(map(len, residual_by_concept.values())),
        "low_yield_words": len({row["word"] for row in low_yields}),
        "low_yield_concepts": len(low_concepts),
        "specialist_slots": len(specialist_needs),
        "external_eligible_slots": len(external_needs),
        "estimated_external_candidates_avoided_at_2x": len(specialist_needs) * 2,
        "specialist_route": "representation_triage_then_flux_if_single_image",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop-root", type=Path, required=True)
    parser.add_argument("--authoritative-decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--yield-floor", type=float, default=0.15)
    parser.add_argument("--minimum-attempts", type=int, default=8)
    parser.add_argument("--minimum-rounds", type=int, default=2)
    args = parser.parse_args()
    result = analyze(
        args.loop_root, args.authoritative_decisions, args.output,
        yield_floor=args.yield_floor,
        minimum_attempts=args.minimum_attempts,
        minimum_rounds=args.minimum_rounds,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
