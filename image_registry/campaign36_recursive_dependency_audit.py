"""Audit lexical prerequisites introduced by the Campaign 36 expansion.

The first dependency pass already reviewed the 2,500 source contracts.  This
pass presents only the newly commissioned contracts to Luna, while resolving
their proposed dependencies against the complete source-plus-expansion
vocabulary.  That makes the audit recursive without paying to re-review the
unchanged source curriculum.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from typing import Any

from image_registry.campaign36_dependency_order import (
    atomic_json,
    atomic_jsonl,
    candidate_rows,
    dictionary_words,
    load_jsonl,
    surface_key,
    resolve as dependency_resolve,
    review as dependency_review,
)


DEPENDENCY_ROOT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/infinitive-label-v1/dependency-order-v1"
)
DEFAULT_SOURCE = DEPENDENCY_ROOT / "teaching-contracts.jsonl"
DEFAULT_NEW = DEPENDENCY_ROOT / "prerequisite-commission-v1/commission-contracts-clean.jsonl"
DEFAULT_OUTPUT = DEPENDENCY_ROOT / "prerequisite-commission-v1/recursive-dependency-audit-v1"
DEFAULT_REPORT = Path(
    "/home/aomukai/Documents/Codex/2026-08-24/he/outputs/"
    "campaign36-recursive-missing-prerequisites.csv"
)
DEFAULT_CODEX = Path("/home/aomukai/.local/bin/codex")
DEFAULT_DICTIONARY = [
    Path("/usr/share/dict/words"),
    Path("/usr/share/hunspell/en_US.dic"),
]
SCHEMA_VERSION = "ninereeds_campaign36_recursive_dependency_audit_v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def combined_contracts(
    source: list[dict[str, Any]], new: list[dict[str, Any]], *, id_prefix: str = "prereq-",
) -> list[dict[str, Any]]:
    rows = []
    for ordinal, row in enumerate(source, 1):
        contract_id = f"source-c{ordinal:04d}"
        rows.append({**row, "ordinal": ordinal, "contract_id": contract_id, "concept_id": contract_id})
    for offset, row in enumerate(new, 1):
        ordinal = len(source) + offset
        contract_id = f"source-c{ordinal:04d}"
        rows.append({
            **row,
            "ordinal": ordinal,
            "contract_id": contract_id,
            "concept_id": contract_id,
            "prerequisite_contract_id": f"{id_prefix}{row['commission_id']}",
        })
    return rows


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source = load_jsonl(args.source)
    new = load_jsonl(args.new)
    contracts = combined_contracts(source, new, id_prefix=args.id_prefix)
    words = dictionary_words(args.dictionary)
    candidates = [row for row in candidate_rows(contracts, words) if int(row["original_ordinal"]) > len(source)]
    atomic_jsonl(args.output / "combined-contracts.jsonl", contracts)
    atomic_jsonl(args.output / "candidates.jsonl", candidates)
    mapping = [{
        "audit_contract_id": f"source-c{len(source) + offset:04d}",
        "prerequisite_contract_id": f"{args.id_prefix}{row['commission_id']}",
        "commission_id": row["commission_id"],
        "display_label": row["display_label"],
    } for offset, row in enumerate(new, 1)]
    atomic_jsonl(args.output / "new-contract-mapping.jsonl", mapping)
    result = {
        "source_contracts": len(source),
        "new_contracts": len(new),
        "new_candidate_targets": len(candidates),
        "created_at": now(),
    }
    atomic_json(args.output / "prepare-summary.json", result)
    return result


def dependency_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        contracts=args.output / "combined-contracts.jsonl",
        output=args.output,
        batch_size=args.batch_size,
        workers=args.workers,
        codex=args.codex,
        model=args.model,
        timeout=args.timeout,
    )


def review(args: argparse.Namespace) -> dict[str, Any]:
    if not (args.output / "candidates.jsonl").is_file():
        prepare(args)
    return dependency_review(dependency_args(args))


def resolve(args: argparse.Namespace) -> dict[str, Any]:
    return dependency_resolve(dependency_args(args))


def csv_text(rows: list[dict[str, Any]]) -> str:
    fields = [
        "target_contract_id", "target_display_label", "target_teaching_sense",
        "missing_component", "relation", "confidence", "reason",
    ]
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def report(args: argparse.Namespace) -> dict[str, Any]:
    claims = {row["claim_id"]: row for row in load_jsonl(args.output / "dependency-claims.jsonl")}
    decisions = load_jsonl(args.output / "resolved-dependencies.jsonl")
    mapping = {row["audit_contract_id"]: row for row in load_jsonl(args.output / "new-contract-mapping.jsonl")}
    present, missing, rejected = [], [], []
    for decision in decisions:
        claim = claims[decision["claim_id"]]
        target = mapping[claim["target_contract_id"]]
        row = {
            **claim,
            **decision,
            "target_contract_id": target["prerequisite_contract_id"],
            "target_display_label": target["display_label"],
            "missing_component": claim["component"],
            "reason": decision["rationale"],
        }
        if decision["resolution"] == "present":
            matched = decision["matched_contract_id"]
            row["dependency_contract_id"] = mapping.get(matched, {}).get("prerequisite_contract_id", matched)
            present.append(row)
        elif decision["resolution"] == "absent":
            missing.append(row)
        else:
            rejected.append(row)
    atomic_jsonl(args.output / "present-dependency-edges.jsonl", present)
    atomic_jsonl(args.output / "recursive-missing-prerequisites.jsonl", missing)
    atomic_jsonl(args.output / "rejected-dependency-claims.jsonl", rejected)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(csv_text(missing), encoding="utf-8")
    result = {
        "new_contracts_audited": len(mapping),
        "claims": len(decisions),
        "present_dependencies": len(present),
        "missing_prerequisites": len(missing),
        "rejected_claims": len(rejected),
        "non_high_confidence": sum(row["confidence"] != "high" for row in decisions),
        "recursive_closure_reached": not missing and all(row["confidence"] == "high" for row in decisions),
        "created_at": now(),
    }
    atomic_json(args.output / "summary.json", result)
    return result


def collect(args: argparse.Namespace) -> dict[str, Any]:
    occupied = {
        surface_key(row["display_label"])
        for path in args.occupied_contracts for row in load_jsonl(path)
    }
    collected = []
    for round_index, path in enumerate(args.round_contracts, 2):
        for row in load_jsonl(path):
            collected.append({
                **row,
                "source_round": round_index,
                "source_commission_id": row["commission_id"],
                "commission_id": f"t{len(collected) + 1:04d}",
            })
    labels = [surface_key(row["display_label"]) for row in collected]
    collisions = sorted({label for label in labels if labels.count(label) > 1 or label in occupied})
    if collisions:
        raise ValueError(f"tail collection has display-label collisions: {collisions}")
    atomic_jsonl(args.combined_new, collected)
    result = {
        "contracts": len(collected),
        "required_images": len(collected) * 10,
        "display_label_collisions": 0,
        "created_at": now(),
    }
    atomic_json(args.combined_new.with_suffix(".summary.json"), result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "review", "resolve", "report", "collect", "all"))
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--new", type=Path, default=DEFAULT_NEW)
    parser.add_argument("--id-prefix", default="prereq-")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--dictionary", type=Path, action="append", default=DEFAULT_DICTIONARY)
    parser.add_argument("--codex", type=Path, default=DEFAULT_CODEX)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--round-contracts", type=Path, action="append", default=[])
    parser.add_argument("--occupied-contracts", type=Path, action="append", default=[])
    parser.add_argument("--combined-new", type=Path, default=DEFAULT_OUTPUT / "tail-contracts.jsonl")
    args = parser.parse_args()
    if args.command in ("prepare", "all"):
        print(json.dumps(prepare(args), indent=2, sort_keys=True))
    if args.command in ("review", "all"):
        print(json.dumps(review(args), indent=2, sort_keys=True))
    if args.command in ("resolve", "all"):
        print(json.dumps(resolve(args), indent=2, sort_keys=True))
    if args.command in ("report", "all"):
        print(json.dumps(report(args), indent=2, sort_keys=True))
    if args.command == "collect":
        print(json.dumps(collect(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
