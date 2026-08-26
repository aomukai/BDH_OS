"""Reconcile reviewed replacement-word candidates into ten-image teaching sets.

This stage is deliberately word-level.  Every candidate is reviewed before selection;
ten is the final curriculum quota, never an acquisition or review cutoff.  Selection is
a deterministic min-cost maximum flow so the global four-use image cap cannot starve a
scarce word merely because a common word was processed first.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import networkx as nx

from image_registry.campaign35_word_review_export import classify
from image_registry.cli import connect


SCHEMA_VERSION = "ninereeds_campaign36_replacement_reconciliation_v1"


def rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_rows(path: Path, values: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in values
        ),
        encoding="utf-8",
    )


def requirement_rows(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "slot_id": row["slot_id"],
            "word": row["word"],
            "concept": row.get("concept", row["word"]),
            "concept_id": row.get("concept_id", row["word"]),
            "teaching_sense": row.get("teaching_sense", ""),
            "ordinal": int(row["ordinal"]),
            "exposure_index": int(row.get("exposure_index", 1)),
            "sequence_position": int(row["sequence_position"]),
        }
        for row in bindings
    ]


def classify_pool(
    db: Any,
    *,
    semantic_queue: str,
    bindings: list[dict[str, Any]],
    watermark_queue: str,
    usability_queue: str,
    word_fit_queue: str,
    sol_queue: str,
    pool: str,
) -> list[dict[str, Any]]:
    decisions = classify(
        db,
        semantic_queue,
        requirement_rows(bindings),
        watermark_queue=watermark_queue,
        usability_queue=usability_queue,
        word_fit_queue=word_fit_queue,
        sol_word_fit_queue=sol_queue,
    )
    source = {row["slot_id"]: row for row in bindings}
    enriched = []
    for decision in decisions:
        binding = source[decision["slot_id"]]
        enriched.append(
            {
                **decision,
                "candidate_pool": pool,
                "candidate_rank": int(
                    binding.get(
                        "candidate_rank_for_slot",
                        binding.get("exposure_index", 1),
                    )
                ),
                "target_slot_id": binding.get("target_slot_id"),
                "retrieval_evidence": binding.get("retrieval_evidence"),
            }
        )
    return enriched


def mentions(word: str, value: Any) -> int:
    if not isinstance(value, str) or not value:
        return 0
    return int(
        re.search(
            r"(?<!\w)" + re.escape(word.casefold()) + r"(?!\w)",
            value.casefold(),
        )
        is not None
    )


def quality_cost(row: dict[str, Any]) -> int:
    """Smaller is better; all terms are deterministic and evidence-backed."""
    explicit = sum(
        mentions(row["word"], row.get(field))
        for field in ("literal_caption", "source_caption", "target_evidence")
    )
    pool_penalty = 0 if row["candidate_pool"] == "local_registry" else 20
    adjudication_penalty = 0
    if row.get("watermark_adjudication"):
        adjudication_penalty += 3
    if row.get("usability_adjudication"):
        adjudication_penalty += 3
    if row.get("word_fit_adjudication"):
        adjudication_penalty += 2
    flags = len(row.get("quality_flags") or [])
    rank = min(int(row.get("candidate_rank", 999)), 999)
    # Explicit pixel/caption evidence dominates source and retrieval rank.
    return (3 - min(explicit, 3)) * 1000 + pool_penalty + adjudication_penalty + flags * 5 + rank


def candidate_identity(row: dict[str, Any]) -> tuple[str, str]:
    """Identify retrieved and generated candidates across reconciliation ticks."""
    pool = str(row["candidate_pool"])
    slot = str(row.get("slot_id") or "").strip()
    if slot:
        return pool, slot
    word = str(row.get("word") or "").strip()
    digest = str(row.get("sha256") or "").strip()
    if not word or not digest:
        raise ValueError("candidate lacks both slot_id and generated word/hash identity")
    return pool, f"generated:{word}:{digest}"


def baseline_hash_uses(path: Path) -> Counter[str]:
    uses: Counter[str] = Counter()
    for row in rows(path):
        digest = str(row.get("asset_sha256") or row.get("sha256") or "")
        if digest:
            uses[digest] += 1
    return uses


def choose_candidates(
    accepted: list[dict[str, Any]],
    *,
    words: list[str],
    baseline_uses: Counter[str],
    quota: int,
    reuse_cap: int,
) -> tuple[list[dict[str, Any]], int]:
    # The same word/image may enter through multiple metadata slots or pools.
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in accepted:
        digest = str(row.get("sha256") or "")
        if not digest:
            continue
        key = (row["word"], digest)
        old = unique.get(key)
        if old is None or (quality_cost(row), row["asset_id"]) < (
            quality_cost(old), old["asset_id"]
        ):
            unique[key] = row

    graph = nx.DiGraph()
    source, sink = "source", "sink"
    graph.add_node(source)
    graph.add_node(sink)
    by_word: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_hash: dict[str, dict[str, Any]] = {}
    for row in unique.values():
        digest = row["sha256"]
        if baseline_uses[digest] >= reuse_cap:
            continue
        by_word[row["word"]].append(row)
        by_hash.setdefault(digest, row)
    for word in words:
        node = ("word", word)
        graph.add_edge(source, node, capacity=quota, weight=0)
        for row in sorted(
            by_word.get(word, []),
            key=lambda item: (quality_cost(item), item["sha256"], item["asset_id"]),
        ):
            graph.add_edge(
                node,
                ("asset", row["sha256"]),
                capacity=1,
                weight=quality_cost(row),
            )
    for digest in sorted(by_hash):
        graph.add_edge(
            ("asset", digest),
            sink,
            capacity=max(0, reuse_cap - baseline_uses[digest]),
            weight=0,
        )
    if graph.number_of_edges() == 0:
        return [], 0
    maximum = int(nx.maximum_flow_value(graph, source, sink, capacity="capacity"))
    graph.nodes[source]["demand"] = -maximum
    graph.nodes[sink]["demand"] = maximum
    flow = nx.min_cost_flow(graph, demand="demand", capacity="capacity", weight="weight")
    selected = []
    for word in words:
        node = ("word", word)
        for asset_node, amount in flow.get(node, {}).items():
            if amount:
                selected.append(unique[(word, asset_node[1])])
    return selected, maximum


def reconcile(args: argparse.Namespace) -> dict[str, Any]:
    local_bindings = rows(args.local_bindings)
    metadata_bindings = rows(args.metadata_candidates)
    replacement_map = rows(args.replacement_map)
    replacement_by_word = {row["new_word"]: row for row in replacement_map}
    words = [row["new_word"] for row in sorted(replacement_map, key=lambda row: row["ordinal"])]
    requirements = [
        row
        for row in rows(args.requirements)
        if row["ordinal"] in {int(item["ordinal"]) for item in replacement_map}
    ]
    if len(words) != 611 or len(requirements) != 6110:
        raise ValueError("replacement contract must be exactly 611 words x 10 slots")

    with connect(args.db) as db:
        decisions = classify_pool(
            db,
            semantic_queue=args.local_queue,
            bindings=local_bindings,
            watermark_queue=args.local_watermark_queue,
            usability_queue=args.local_usability_queue,
            word_fit_queue=args.local_word_fit_queue,
            sol_queue=args.local_sol_queue,
            pool="local_registry",
        )
        decisions.extend(
            classify_pool(
                db,
                semantic_queue=args.metadata_queue,
                bindings=metadata_bindings,
                watermark_queue=args.metadata_watermark_queue,
                usability_queue=args.metadata_usability_queue,
                word_fit_queue=args.metadata_word_fit_queue,
                sol_queue=args.metadata_sol_queue,
                pool="downloaded_metadata",
            )
        )
    if args.generated_accepted and args.generated_accepted.is_file():
        generated_latest: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows(args.generated_accepted):
            if row.get("disposition") != "accepted":
                continue
            generated_latest[(row["word"], row["sha256"])] = row
        decisions.extend(generated_latest.values())

    accepted = [row for row in decisions if row["disposition"] == "accepted"]
    baseline = baseline_hash_uses(args.baseline_accepted)
    selected, maximum = choose_candidates(
        accepted,
        words=words,
        baseline_uses=baseline,
        quota=args.quota,
        reuse_cap=args.reuse_cap,
    )
    selected_by_word: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        selected_by_word[row["word"]].append(row)
    for value in selected_by_word.values():
        value.sort(key=lambda row: (quality_cost(row), row["sha256"], row["asset_id"]))

    requirement_by_word: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in requirements:
        requirement_by_word[row["word"]].append(row)
    chosen_slots = []
    selected_keys = set()
    residual_words = []
    for word in words:
        chosen = selected_by_word.get(word, [])[: args.quota]
        slots = sorted(requirement_by_word[word], key=lambda row: row["exposure_index"])
        for requirement, candidate in zip(slots, chosen):
            identity = candidate_identity(candidate)
            selected_keys.add(identity)
            chosen_slots.append(
                {
                    **requirement,
                    **candidate,
                    "slot_id": requirement["slot_id"],
                    "sequence_position": int(
                        requirement.get(
                            "sequence_position",
                            (int(requirement["ordinal"]) - 1) * args.quota
                            + int(requirement["exposure_index"]),
                        )
                    ),
                    "exposure_index": requirement["exposure_index"],
                    "candidate_slot_id": identity[1],
                    "selection_cost": quality_cost(candidate),
                    "disposition": "accepted",
                }
            )
        missing = args.quota - len(chosen)
        if missing:
            contract = replacement_by_word[word]
            residual_words.append(
                {
                    "word": word,
                    "concept_id": contract["new_concept_id"],
                    "teaching_sense": contract["new_teaching_sense"],
                    "ordinal": int(contract["ordinal"]),
                    "target_count": args.quota,
                    "accepted_count": len(chosen),
                    "remaining_count": missing,
                    "status": "unclaimed",
                    "accepted_asset_ids": [row["asset_id"] for row in chosen],
                    "accepted_sha256": [row["sha256"] for row in chosen],
                }
            )

    surplus = [
        row
        for row in accepted
        if candidate_identity(row) not in selected_keys
    ]
    counts = Counter(row["disposition"] for row in decisions)
    semantic_unfinished = sum(
        disposition.startswith("review_") for disposition in counts.elements()
    )
    cascade_unfinished = sum(
        counts[name]
        for name in (
            "needs_luna_watermark",
            "needs_luna_usability",
            "needs_luna_word_fit",
            "needs_sol_word_fit",
        )
    )
    final_hash_uses = baseline.copy()
    final_hash_uses.update(row["sha256"] for row in chosen_slots)
    if final_hash_uses and max(final_hash_uses.values()) > args.reuse_cap:
        raise AssertionError("global image reuse cap was exceeded")

    args.output.mkdir(parents=True, exist_ok=True)
    write_rows(args.output / "candidate-decisions.jsonl", decisions)
    write_rows(args.output / "selected-assets.jsonl", chosen_slots)
    write_rows(args.output / "surplus-accepted.jsonl", surplus)
    write_rows(args.output / "generation-queue.jsonl", residual_words)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "review_in_progress"
            if semantic_unfinished or cascade_unfinished
            else "review_complete_generation_required"
            if residual_words
            else "replacement_corpus_complete"
        ),
        "candidate_claims": len(decisions),
        "candidate_dispositions": dict(sorted(counts.items())),
        "accepted_candidate_claims": len(accepted),
        "selected_slots": len(chosen_slots),
        "maximum_flow_slots": maximum,
        "complete_words": len(words) - len(residual_words),
        "residual_words": len(residual_words),
        "residual_images": sum(row["remaining_count"] for row in residual_words),
        "surplus_accepted_claims": len(surplus),
        "semantic_unfinished_claims": semantic_unfinished,
        "cascade_unfinished_claims": cascade_unfinished,
        "reuse_cap": args.reuse_cap,
        "max_global_hash_uses_after_selection": max(final_hash_uses.values(), default=0),
        "baseline_sha256": hashlib.sha256(args.baseline_accepted.read_bytes()).hexdigest(),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--local-bindings", type=Path, required=True)
    parser.add_argument("--metadata-candidates", type=Path, required=True)
    parser.add_argument("--replacement-map", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--baseline-accepted", type=Path, required=True)
    parser.add_argument("--generated-accepted", type=Path)
    parser.add_argument("--local-queue", required=True)
    parser.add_argument("--local-watermark-queue", required=True)
    parser.add_argument("--local-usability-queue", required=True)
    parser.add_argument("--local-word-fit-queue", required=True)
    parser.add_argument("--local-sol-queue", required=True)
    parser.add_argument("--metadata-queue", required=True)
    parser.add_argument("--metadata-watermark-queue", required=True)
    parser.add_argument("--metadata-usability-queue", required=True)
    parser.add_argument("--metadata-word-fit-queue", required=True)
    parser.add_argument("--metadata-sol-queue", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quota", type=int, default=10)
    parser.add_argument("--reuse-cap", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(reconcile(args), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
