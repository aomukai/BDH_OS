"""Publish Campaign 36 teaching labels with explicit infinitive verb markers.

The frozen Campaign 36 manifest stores a bare surface word for every teaching
contract.  That makes noun/verb homographs byte-identical (``paint``/``paint``).
This migration consumes a semantic, one-decision-per-ordinal POS ledger and
publishes a new manifest in which verified verbs are taught as ``to <lemma>``.

Nouns never receive an article.  Ambiguous decisions are preserved unchanged
and block a release-ready status so that the script cannot silently guess POS.
The frozen source manifest is never modified.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable


SCHEMA_VERSION = "ninereeds_campaign36_infinitive_labels_v1"
DEFAULT_CAMPAIGN = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1"
)
DEFAULT_MANIFEST = DEFAULT_CAMPAIGN / (
    "visual-vocabulary-replacement-v1/final-v1/accepted-assets.jsonl"
)
DEFAULT_OUTPUT = DEFAULT_CAMPAIGN / "infinitive-label-v1"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def atomic_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    hasher = hashlib.sha256()
    with temporary.open("w", encoding="utf-8") as stream:
        for value in values:
            line = json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
            stream.write(line)
            hasher.update(line.encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    return hasher.hexdigest()


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def image_hash(row: dict[str, Any]) -> str:
    return str(row.get("sha256") or row.get("asset_sha256") or "")


def row_ordinal(row: dict[str, Any]) -> int:
    slot_id = str(row.get("slot_id") or row.get("target_slot_id") or "")
    match = re.fullmatch(r"c(\d{4})-i\d{2}", slot_id)
    slot_ordinal = int(match.group(1)) if match else None
    explicit = row.get("ordinal")
    if explicit is None:
        if slot_ordinal is None:
            raise ValueError("manifest row lacks both ordinal and a canonical slot ID")
        return slot_ordinal
    ordinal = int(explicit)
    if slot_ordinal is not None and ordinal != slot_ordinal:
        raise ValueError(
            f"manifest row ordinal {ordinal} disagrees with slot ID {slot_id}"
        )
    return ordinal


def contracts_by_ordinal(
    manifest: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest:
        grouped[row_ordinal(row)].append(row)
    contracts: dict[int, dict[str, Any]] = {}
    for ordinal, rows in grouped.items():
        signatures = {
            (
                str(row.get("concept_id") or ""),
                str(row.get("word") or ""),
                str(row.get("part_of_speech") or ""),
                str(row.get("teaching_sense") or ""),
            )
            for row in rows
        }
        if len(signatures) != 1:
            raise ValueError(f"ordinal {ordinal} has inconsistent teaching metadata")
        concept_id, word, part_of_speech, teaching_sense = signatures.pop()
        contracts[ordinal] = {
            "ordinal": ordinal,
            "concept_id": concept_id,
            "word": word,
            "part_of_speech": part_of_speech,
            "teaching_sense": teaching_sense,
            "image_slots": len(rows),
        }
    return contracts


def validated_decisions(
    path: Path,
    contracts: dict[int, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    rows = load_jsonl(path)
    decisions: dict[int, dict[str, Any]] = {}
    allowed = {"verified_verb", "not_verb"}
    for row in rows:
        ordinal = int(row["ordinal"])
        if ordinal in decisions:
            raise ValueError(f"duplicate POS decision for ordinal {ordinal}")
        if ordinal not in contracts:
            raise ValueError(f"POS decision references unknown ordinal {ordinal}")
        contract = contracts[ordinal]
        if str(row.get("concept_id")) != contract["concept_id"]:
            raise ValueError(f"concept mismatch in POS decision for ordinal {ordinal}")
        if str(row.get("original_word")) != contract["word"]:
            raise ValueError(f"word mismatch in POS decision for ordinal {ordinal}")
        decision = str(row.get("decision"))
        if decision not in allowed:
            raise ValueError(f"invalid POS decision for ordinal {ordinal}: {decision}")
        verified_pos = str(row.get("verified_part_of_speech") or "").strip()
        if not verified_pos or verified_pos.casefold() == "unspecified":
            raise ValueError(
                f"POS decision does not resolve the grammatical role at ordinal {ordinal}"
            )
        label = str(row.get("proposed_display_label") or "").strip()
        if not label:
            raise ValueError(f"empty proposed label for ordinal {ordinal}")
        if decision == "verified_verb":
            if not label.startswith("to ") or len(label) <= 3:
                raise ValueError(
                    f"verified verb lacks an infinitive label at ordinal {ordinal}: {label}"
                )
            if verified_pos != "verb":
                raise ValueError(f"verified verb lacks verb POS at ordinal {ordinal}")
        elif label != contract["word"]:
            raise ValueError(
                f"non-verb decision changes the label at ordinal {ordinal}: {label}"
            )
        fit_count = int(row.get("image_fit_count", -1))
        mismatch_count = int(row.get("image_mismatch_count", -1))
        mismatch_slots = row.get("image_mismatch_slots")
        if fit_count < 0 or mismatch_count < 0 or fit_count + mismatch_count != 10:
            raise ValueError(
                f"image-fit counts do not cover ten slots at ordinal {ordinal}"
            )
        if not isinstance(mismatch_slots, list) or len(mismatch_slots) != mismatch_count:
            raise ValueError(
                f"image mismatch slot ledger disagrees at ordinal {ordinal}"
            )
        expected_prefix = f"c{ordinal:04d}-i"
        if any(not str(slot).startswith(expected_prefix) for slot in mismatch_slots):
            raise ValueError(f"invalid image mismatch slot at ordinal {ordinal}")
        assessment = str(row.get("image_contract_assessment") or "")
        expected_assessment = (
            "pass" if mismatch_count == 0 else "fail" if fit_count == 0 else "partial"
        )
        if assessment != expected_assessment:
            raise ValueError(
                f"image assessment/count disagreement at ordinal {ordinal}"
            )
        decisions[ordinal] = row
    missing = sorted(set(contracts) - set(decisions))
    if missing:
        raise ValueError(f"POS ledger is missing {len(missing)} ordinals")
    return decisions


def migrated_contract(
    contract: dict[str, Any], decision: dict[str, Any]
) -> dict[str, Any]:
    label = str(decision["proposed_display_label"]).strip()
    verified_pos = str(decision.get("verified_part_of_speech") or "").strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "ordinal": contract["ordinal"],
        "concept_id": contract["concept_id"],
        "lemma": contract["word"],
        "display_label": label,
        "word": label,
        "original_part_of_speech": contract["part_of_speech"],
        "part_of_speech": verified_pos or contract["part_of_speech"],
        "teaching_sense": contract["teaching_sense"],
        "pos_decision": decision["decision"],
        "pos_confidence": decision.get("confidence"),
        "pos_rationale": decision.get("rationale"),
        "image_contract_assessment": decision.get("image_contract_assessment"),
        "image_contract_issue": decision.get("image_contract_issue"),
        "image_fit_count": decision["image_fit_count"],
        "image_mismatch_count": decision["image_mismatch_count"],
        "image_mismatch_slots": decision["image_mismatch_slots"],
        "image_slots": contract["image_slots"],
    }


def publish(args: argparse.Namespace) -> dict[str, Any]:
    manifest = load_jsonl(args.manifest)
    contracts = contracts_by_ordinal(manifest)
    if len(manifest) != args.expected_rows or len(contracts) != args.expected_contracts:
        raise ValueError(
            f"expected {args.expected_rows:,} rows / {args.expected_contracts:,} "
            f"contracts, got "
            f"{len(manifest)} / {len(contracts)}"
        )
    bad_slot_counts = {
        ordinal: contract["image_slots"]
        for ordinal, contract in contracts.items()
        if contract["image_slots"] != args.images_per_contract
    }
    if bad_slot_counts:
        raise ValueError(f"contracts without ten image slots: {bad_slot_counts}")

    decisions = validated_decisions(args.decisions, contracts)
    migrated_contracts = [
        migrated_contract(contracts[ordinal], decisions[ordinal])
        for ordinal in sorted(contracts)
    ]
    migrated_by_ordinal = {row["ordinal"]: row for row in migrated_contracts}
    migrated_manifest = []
    for source in manifest:
        ordinal = row_ordinal(source)
        contract = migrated_by_ordinal[ordinal]
        migrated_manifest.append({
            **source,
            "schema_version": SCHEMA_VERSION,
            "source_schema_version": source.get("schema_version"),
            "lemma": contract["lemma"],
            "display_label": contract["display_label"],
            "word": contract["word"],
            "original_word": contract["lemma"],
            "original_part_of_speech": contract["original_part_of_speech"],
            "part_of_speech": contract["part_of_speech"],
            "pos_decision": contract["pos_decision"],
            "ordinal": ordinal,
        })

    label_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for contract in migrated_contracts:
        label_groups[normalized(contract["display_label"])].append(contract)
    collisions = [
        {
            "normalized_display_label": key,
            "contracts": [
                {
                    "ordinal": row["ordinal"],
                    "concept_id": row["concept_id"],
                    "lemma": row["lemma"],
                    "display_label": row["display_label"],
                    "part_of_speech": row["part_of_speech"],
                    "teaching_sense": row["teaching_sense"],
                }
                for row in values
            ],
        }
        for key, values in sorted(label_groups.items())
        if len(values) > 1
    ]
    ambiguous = [row for row in migrated_contracts if row["pos_decision"] == "ambiguous"]
    verified_verbs = [
        row for row in migrated_contracts if row["pos_decision"] == "verified_verb"
    ]
    original_unspecified = sum(
        normalized(row["original_part_of_speech"]) == "unspecified"
        for row in migrated_contracts
    )
    final_unspecified = sum(
        normalized(row["part_of_speech"]) == "unspecified"
        for row in migrated_contracts
    )
    pos_counts = Counter(row["part_of_speech"] for row in migrated_contracts)
    remediation = [
        row for row in migrated_contracts if int(row["image_mismatch_count"]) > 0
    ]
    mismatched_images = sum(int(row["image_mismatch_count"]) for row in remediation)
    hashes = Counter(image_hash(row) for row in migrated_manifest)
    hashes.pop("", None)
    output = args.output
    contracts_sha = atomic_jsonl(output / "teaching-contracts.jsonl", migrated_contracts)
    manifest_sha = atomic_jsonl(output / "accepted-assets.jsonl", migrated_manifest)
    atomic_jsonl(output / "display-label-collisions.jsonl", collisions)
    atomic_jsonl(output / "ambiguous-pos-review.jsonl", ambiguous)
    atomic_jsonl(output / "image-remediation-queue.jsonl", remediation)
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(args.manifest.resolve()),
        "source_decisions": str(args.decisions.resolve()),
        "source_rows": len(manifest),
        "teaching_contracts": len(migrated_contracts),
        "verified_verbs": len(verified_verbs),
        "original_unspecified_pos": original_unspecified,
        "final_unspecified_pos": final_unspecified,
        "verified_pos_counts": dict(sorted(pos_counts.items())),
        "ambiguous_pos_contracts": len(ambiguous),
        "image_remediation_contracts": len(remediation),
        "mismatched_images": mismatched_images,
        "unique_display_labels": len(label_groups),
        "display_label_collision_groups": len(collisions),
        "max_image_reuse": max(hashes.values(), default=0),
        "image_hashes_over_four_uses": sum(count > 4 for count in hashes.values()),
        "teaching_contracts_sha256": contracts_sha,
        "accepted_assets_sha256": manifest_sha,
        "label_migration_complete": (
            not ambiguous
            and not collisions
            and not final_unspecified
            and max(hashes.values(), default=0) <= 4
        ),
        "training_ready": (
            not ambiguous
            and not collisions
            and not final_unspecified
            and not remediation
            and max(hashes.values(), default=0) <= 4
        ),
    }
    atomic_json(output / "migration-audit.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--images-per-contract", type=int, default=10)
    parser.add_argument("--expected-rows", type=int, default=25_000)
    parser.add_argument("--expected-contracts", type=int, default=2_500)
    args = parser.parse_args()
    print(json.dumps(publish(args), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
