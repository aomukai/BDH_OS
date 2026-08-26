"""Freeze Campaign 36 visual-material preparation inputs from the M2 mapping.

This command starts no training.  It converts the 2,500 mapped teaching concepts into
ten image requirements each, preserves only semantically unchanged reviewed Campaign 35
assignments, and overlays explicitly reviewed remediation assignments.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "ninereeds_campaign36_material_inputs_v1"


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_inputs(
    lexicon_path: Path,
    prior_decisions_path: Path,
    remediation_path: Path | None,
    output: Path,
) -> dict[str, Any]:
    lexicon = rows(lexicon_path)
    if len(lexicon) != 2_500:
        raise ValueError(f"expected 2,500 mapped concepts, found {len(lexicon)}")
    lexicon.sort(key=lambda row: int(row["source"]["ordinal"]))
    if [row["source"]["ordinal"] for row in lexicon] != list(range(1, 2_501)):
        raise ValueError("mapped concept ordinals are not exactly 1..2500")
    concept_ids = [str(row["source"]["concept_id"]) for row in lexicon]
    if len(set(concept_ids)) != 2_500:
        raise ValueError("mapped concept_id values are not unique")

    prior = {row["slot_id"]: row for row in rows(prior_decisions_path)}
    if len(prior) != 25_000:
        raise ValueError("prior decision ledger is not exactly 25,000 unique slots")
    remediations = rows(remediation_path) if remediation_path else []
    remediation_by_slot: dict[str, dict[str, Any]] = {}
    for row in remediations:
        ordinal = int(row["source"]["ordinal"])
        exposure = int(row["exposure_index"])
        slot_id = f"c{ordinal:04d}-i{exposure:02d}"
        if slot_id in remediation_by_slot:
            raise ValueError(f"duplicate remediation slot: {slot_id}")
        remediation_by_slot[slot_id] = row

    curriculum: list[dict[str, Any]] = []
    requirements: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    carried = remediated = 0
    for mapped in lexicon:
        source = mapped["source"]
        mapping = mapped["mapping"]
        ordinal = int(source["ordinal"])
        term = str(mapping["teaching_term"]).strip()
        sense = str(mapping["teaching_sense"]).strip()
        if not term or not sense:
            raise ValueError(f"empty teaching term or sense at ordinal {ordinal}")
        curriculum.append({
            "ordinal": ordinal,
            "concept": source["concept"],
            "concept_id": source["concept_id"],
            "teaching_term": term,
            "teaching_sense": sense,
            "depends_on": source.get("depends_on", []),
            "source_path": source.get("source_path"),
            "source_sha256": source.get("source_sha256"),
            "mapping_relation": mapping.get("mapping_relation"),
            "image_compatibility": mapping.get("image_compatibility"),
        })
        for exposure in range(1, 11):
            slot_id = f"c{ordinal:04d}-i{exposure:02d}"
            requirement = {
                "slot_id": slot_id,
                "sequence_position": (ordinal - 1) * 10 + exposure,
                "ordinal": ordinal,
                "concept": source["concept"],
                "concept_id": source["concept_id"],
                "teaching_sense": sense,
                "word": term,
                "exposure_index": exposure,
            }
            requirements.append(requirement)
            remediation = remediation_by_slot.get(slot_id)
            if remediation is not None:
                if str(remediation["source"]["concept_id"]) != str(source["concept_id"]):
                    raise ValueError(f"remediation concept mismatch for {slot_id}")
                asset = remediation["asset"]
                decisions.append({
                    **requirement,
                    "asset_id": asset["asset_id"],
                    "candidate_tier": "campaign36_reviewed_manual_remediation",
                    "decision_round": "campaign36_input",
                    "disposition": "accepted",
                    "height": None,
                    "literal_caption": remediation["caption"],
                    "local_path": asset["path"],
                    "quality_flags": [],
                    "review_backend": "manual_pixel_review",
                    "review_model": "sol",
                    "sha256": asset["sha256"],
                    "source": asset["source"],
                    "source_id": asset["source_id"],
                    "status": "reviewed_usable",
                    "target_evidence": remediation["caption"],
                    "uncertainties": [],
                    "visible_text": None,
                    "watermark": False,
                    "width": None,
                })
                remediated += 1
                continue
            old = prior.get(slot_id)
            may_carry = (
                old is not None
                and old.get("disposition") == "accepted"
                and mapping.get("image_compatibility") == "unchanged"
                and str(old.get("word", "")).casefold() == term.casefold()
            )
            if may_carry:
                decisions.append({
                    **old,
                    **requirement,
                    "decision_round": "campaign35_semantic_carryover",
                    "prior_disposition": old.get("disposition"),
                })
                carried += 1
            else:
                decisions.append({
                    **requirement,
                    "decision_round": "campaign36_input",
                    "disposition": "missing_candidate",
                    "prior_disposition": None if old is None else old.get("disposition"),
                })

    if set(remediation_by_slot) - {row["slot_id"] for row in requirements}:
        raise ValueError("remediation contains a slot outside the mapped curriculum")
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "curriculum.jsonl", curriculum)
    write_jsonl(output / "requirements.jsonl", requirements)
    write_jsonl(output / "initial-decisions.jsonl", decisions)
    accepted = sum(row["disposition"] == "accepted" for row in decisions)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "status": "preparation_inputs_frozen_no_training_started",
        "concepts": len(curriculum),
        "requirements": len(requirements),
        "accepted_slots": accepted,
        "residual_slots": len(requirements) - accepted,
        "campaign35_semantic_carryovers": carried,
        "reviewed_manual_remediations": remediated,
        "unique_teaching_terms": len({row["teaching_term"].casefold() for row in curriculum}),
        "multiword_teaching_terms": sum(
            any(character.isspace() for character in row["teaching_term"].strip())
            for row in curriculum
        ),
        "image_compatibility": dict(sorted(Counter(
            row["image_compatibility"] for row in curriculum
        ).items())),
        "inputs": {
            "lexicon": str(lexicon_path.resolve()),
            "lexicon_sha256": sha256(lexicon_path),
            "prior_decisions": str(prior_decisions_path.resolve()),
            "prior_decisions_sha256": sha256(prior_decisions_path),
            "remediation": None if remediation_path is None else str(remediation_path.resolve()),
            "remediation_sha256": None if remediation_path is None else sha256(remediation_path),
        },
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--prior-decisions", type=Path, required=True)
    parser.add_argument("--remediation", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(json.dumps(compile_inputs(
        args.lexicon, args.prior_decisions, args.remediation, args.output,
    ), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
