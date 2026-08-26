"""Deterministic gates for foundation-corpus expansion work.

The acquisition/generation route is policy-driven and may use several executors. This
module owns the two fail-closed boundaries that must remain deterministic:

* every commissioned teaching contract has the exact requested image count; and
* a folded curriculum has complete files, valid hashes, bounded image reuse, and a
  dependency-respecting teaching order.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Iterable


SCHEMA_VERSION = "ninereeds_foundation_corpus_expansion_audit_v1"

UNDEFINED_LABELS = {
    "", "[unk]", "<unk>", "n/a", "na", "none", "null", "placeholder",
    "tbd", "undefined", "unknown",
}

DEFINED_LEXICAL_CLASSES = {
    "adjective", "adverb", "auxiliary_contraction", "gerund_noun", "noun",
    "interjection", "modal_auxiliary", "past_tense_verb", "phrase_noun",
    "preposition", "quantifier", "verb",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def asset_hash(row: dict[str, Any]) -> str:
    return str(row.get("sha256") or row.get("asset_sha256") or "")


def contract_identity(row: dict[str, Any]) -> str:
    value = row.get("contract_id") or row.get("commission_id") or row.get("prerequisite_contract_id") or row.get("concept_id")
    if value:
        return str(value)
    slot = str(row.get("slot_id") or "")
    if "-i" in slot:
        return slot.rsplit("-i", 1)[0]
    raise ValueError(f"cannot determine contract identity: {row}")


def lexical_contract_errors(row: dict[str, Any]) -> list[str]:
    """Return deterministic violations of the no-undefined-words gate."""
    errors: list[str] = []
    label = " ".join(str(row.get("display_label") or row.get("word") or row.get("lemma") or "").split())
    normalized_label = label.casefold()
    teaching_sense = " ".join(str(row.get("teaching_sense") or "").split())
    lexical_class = str(row.get("part_of_speech") or "").strip().casefold()
    if normalized_label in UNDEFINED_LABELS:
        errors.append("undefined_or_empty_label")
    if not teaching_sense or teaching_sense.casefold() in UNDEFINED_LABELS:
        errors.append("undefined_or_empty_teaching_sense")
    if lexical_class not in DEFINED_LEXICAL_CLASSES:
        errors.append("undefined_or_invalid_part_of_speech")
    return errors


def write_json(path: Path | None, value: dict[str, Any]) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(rendered, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def apply_lexical_overrides(args: argparse.Namespace) -> dict[str, Any]:
    """Derive a new immutable curriculum after explicit lexical adjudication."""
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite derived curriculum: {args.output}")
    overrides_document = json.loads(args.overrides.read_text(encoding="utf-8"))
    overrides = overrides_document.get("overrides", [])
    by_id = {str(row["contract_id"]): row for row in overrides}
    if len(by_id) != len(overrides):
        raise ValueError("lexical override contract identities are not unique")
    allowed = {"contract_id", "display_label", "lemma", "part_of_speech", "teaching_sense", "rationale"}
    for row in overrides:
        unknown = set(row) - allowed
        if unknown:
            raise ValueError(f"unsupported lexical override fields: {sorted(unknown)}")
    contracts = load_jsonl(args.curriculum / "teaching-contracts.jsonl")
    known = {str(row["contract_id"]) for row in contracts}
    if set(by_id) - known:
        raise ValueError(f"unknown lexical override contracts: {sorted(set(by_id) - known)}")
    assets = load_jsonl(args.curriculum / "accepted-assets.jsonl")
    changed_fields = ("display_label", "lemma", "part_of_speech", "teaching_sense")
    derived_contracts = []
    for row in contracts:
        override = by_id.get(str(row["contract_id"]))
        derived = {
            **row,
            **({key: override[key] for key in changed_fields if key in override} if override else {}),
        }
        if lexical_contract_errors(derived):
            raise ValueError(f"override remains lexically undefined: {row['contract_id']}")
        derived_contracts.append(derived)
    derived_assets = []
    for row in assets:
        override = by_id.get(str(row["contract_id"]))
        derived_assets.append({
            **row,
            **({key: override[key] for key in changed_fields if key in override} if override else {}),
        })
    args.output.mkdir(parents=True)
    write_jsonl(args.output / "teaching-contracts.jsonl", derived_contracts)
    write_jsonl(args.output / "accepted-assets.jsonl", derived_assets)
    shutil.copyfile(args.curriculum / "dependency-edges.jsonl", args.output / "dependency-edges.jsonl")
    shutil.copyfile(args.overrides, args.output / "lexical-overrides.json")
    result = {
        "schema_version": "ninereeds_foundation_lexical_override_v1",
        "source_curriculum": str(args.curriculum),
        "contracts": len(derived_contracts), "assets": len(derived_assets),
        "overridden_contracts": sorted(by_id),
    }
    write_json(args.output / "derivation-summary.json", result)
    return result


def verify_files(rows: Iterable[dict[str, Any]]) -> tuple[int, list[str], list[str], list[str]]:
    expected_by_path: dict[str, str] = {}
    inconsistent: list[str] = []
    for row in rows:
        path = str(row.get("local_path") or "")
        expected = asset_hash(row)
        if not path or not expected:
            inconsistent.append(path or "<missing-local_path>")
            continue
        prior = expected_by_path.setdefault(path, expected)
        if prior != expected:
            inconsistent.append(path)
    missing: list[str] = []
    mismatched: list[str] = []
    for path_text, expected in expected_by_path.items():
        path = Path(path_text)
        if not path.is_file():
            missing.append(path_text)
        elif digest(path) != expected:
            mismatched.append(path_text)
    return len(expected_by_path), missing, mismatched, inconsistent


def audit_acquisition(args: argparse.Namespace) -> dict[str, Any]:
    contracts = load_jsonl(args.contracts)
    contract_ids = [contract_identity(row) for row in contracts]
    if len(contract_ids) != len(set(contract_ids)):
        raise ValueError("commission contract identities are not unique")
    rows = [row for ledger in args.ledger for row in load_jsonl(ledger)]
    slots = [str(row.get("slot_id") or "") for row in rows]
    counts = Counter(contract_identity(row) for row in rows)
    duplicate_slots = sorted(slot for slot, count in Counter(slots).items() if not slot or count > 1)
    missing_contracts = sorted(set(contract_ids) - set(counts))
    unknown_contracts = sorted(set(counts) - set(contract_ids))
    bad_counts = {contract: counts.get(contract, 0) for contract in contract_ids if counts.get(contract, 0) != args.images_per_contract}
    hashes = Counter(asset_hash(row) for row in rows)
    hashes.pop("", None)
    unique_files, missing_files, hash_mismatches, inconsistent_paths = verify_files(rows)
    errors = {
        "duplicate_or_empty_slots": duplicate_slots,
        "missing_contracts": missing_contracts,
        "unknown_contracts": unknown_contracts,
        "wrong_image_counts": bad_counts,
        "missing_files": missing_files,
        "hash_mismatches": hash_mismatches,
        "inconsistent_or_missing_path_hash": inconsistent_paths,
        "image_hashes_over_reuse_cap": sorted(value for value, count in hashes.items() if count > args.max_image_reuse),
    }
    passed = not any(errors.values()) and len(rows) == len(contracts) * args.images_per_contract
    result = {
        "schema_version": SCHEMA_VERSION,
        "audit": "acquisition",
        "contracts": len(contracts),
        "assets": len(rows),
        "images_per_contract": args.images_per_contract,
        "contracts_with_exact_count": sum(counts.get(contract, 0) == args.images_per_contract for contract in contract_ids),
        "unique_asset_files_verified": unique_files,
        "max_image_reuse": max(hashes.values(), default=0),
        "errors": errors,
        "passed": passed,
    }
    write_json(args.output, result)
    if not passed:
        raise SystemExit(2)
    return result


def audit_curriculum(args: argparse.Namespace) -> dict[str, Any]:
    contracts = load_jsonl(args.curriculum / "teaching-contracts.jsonl")
    assets = load_jsonl(args.curriculum / "accepted-assets.jsonl")
    edges = load_jsonl(args.curriculum / "dependency-edges.jsonl")
    ids = [str(row["contract_id"]) for row in contracts]
    labels = [" ".join(str(row["display_label"]).casefold().split()) for row in contracts]
    slots = [str(row["slot_id"]) for row in assets]
    counts = Counter(str(row["contract_id"]) for row in assets)
    ordinal = {str(row["contract_id"]): int(row["ordinal"]) for row in contracts}
    dependency_violations = [
        row for row in edges
        if row["dependency_contract_id"] not in ordinal
        or row["target_contract_id"] not in ordinal
        or ordinal[row["dependency_contract_id"]] >= ordinal[row["target_contract_id"]]
    ]
    graph = defaultdict(set)
    for row in edges:
        graph[str(row["target_contract_id"])].add(str(row["dependency_contract_id"]))
    dependency_mismatches = [
        contract_id for contract_id, row in ((str(row["contract_id"]), row) for row in contracts)
        if set(row.get("depends_on", [])) != graph[contract_id] or row.get("missing_dependencies")
    ]
    asset_dependency_mismatches = [
        str(row["slot_id"]) for row in assets
        if set(row.get("depends_on", [])) != graph[str(row["contract_id"])] or row.get("missing_dependencies")
    ]
    hashes = Counter(asset_hash(row) for row in assets)
    hashes.pop("", None)
    unique_files, missing_files, hash_mismatches, inconsistent_paths = verify_files(assets)
    lexical_contract_violations = [
        {
            "contract_id": str(row.get("contract_id") or ""),
            "display_label": str(row.get("display_label") or row.get("word") or row.get("lemma") or ""),
            "part_of_speech": str(row.get("part_of_speech") or ""),
            "violations": violations,
        }
        for row in contracts
        if (violations := lexical_contract_errors(row))
    ]
    errors = {
        "duplicate_contract_ids": sorted(value for value, count in Counter(ids).items() if count > 1),
        "duplicate_display_labels": sorted(value for value, count in Counter(labels).items() if count > 1),
        "duplicate_slots": sorted(value for value, count in Counter(slots).items() if count > 1),
        "wrong_image_counts": {value: counts.get(value, 0) for value in ids if counts.get(value, 0) != args.images_per_contract},
        "unknown_asset_contracts": sorted(set(counts) - set(ids)),
        "dependency_violations": dependency_violations,
        "dependency_manifest_mismatches": dependency_mismatches,
        "asset_dependency_mismatches": asset_dependency_mismatches,
        "missing_files": missing_files,
        "hash_mismatches": hash_mismatches,
        "inconsistent_or_missing_path_hash": inconsistent_paths,
        "image_hashes_over_reuse_cap": sorted(value for value, count in hashes.items() if count > args.max_image_reuse),
        "lexical_contract_violations": lexical_contract_violations,
    }
    passed = not any(errors.values()) and len(assets) == len(contracts) * args.images_per_contract
    result = {
        "schema_version": SCHEMA_VERSION,
        "audit": "curriculum",
        "contracts": len(contracts),
        "assets": len(assets),
        "images_per_contract": args.images_per_contract,
        "dependency_edges": len(edges),
        "unique_asset_files_verified": unique_files,
        "max_image_reuse": max(hashes.values(), default=0),
        "errors": errors,
        "training_ready": passed,
        "passed": passed,
    }
    write_json(args.output, result)
    if not passed:
        raise SystemExit(2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    acquisition = subparsers.add_parser("audit-acquisition")
    acquisition.add_argument("--contracts", type=Path, required=True)
    acquisition.add_argument("--ledger", type=Path, action="append", required=True)
    acquisition.add_argument("--images-per-contract", type=int, default=10)
    acquisition.add_argument("--max-image-reuse", type=int, default=4)
    acquisition.add_argument("--output", type=Path)
    acquisition.set_defaults(function=audit_acquisition)
    curriculum = subparsers.add_parser("audit-curriculum")
    curriculum.add_argument("--curriculum", type=Path, required=True)
    curriculum.add_argument("--images-per-contract", type=int, default=10)
    curriculum.add_argument("--max-image-reuse", type=int, default=4)
    curriculum.add_argument("--output", type=Path)
    curriculum.set_defaults(function=audit_curriculum)
    lexical = subparsers.add_parser("apply-lexical-overrides")
    lexical.add_argument("--curriculum", type=Path, required=True)
    lexical.add_argument("--overrides", type=Path, required=True)
    lexical.add_argument("--output", type=Path, required=True)
    lexical.set_defaults(function=apply_lexical_overrides)
    args = parser.parse_args()
    args.function(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
