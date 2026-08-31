#!/usr/bin/env python3
"""Validate frozen sources and truth-binding invariants in v8 visual contracts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_visual_worklist import ROOT, parse_lesson


REPOSITORY = ROOT.parent.parent
CONTRACTS = ROOT / "visuals" / "contracts"
CANONICAL_MANIFEST = REPOSITORY / "training_data/grounded_stories/assets/canonical/reference_manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def resolve(relative: str) -> Path:
    path = (REPOSITORY / relative).resolve()
    require(path == REPOSITORY or REPOSITORY in path.parents, f"path escapes repository: {relative}")
    return path


def validate_contract(path: Path, canonical_by_id: dict[str, dict]) -> None:
    contract = json.loads(path.read_text(encoding="utf-8"))
    lesson_id = contract["lesson_id"]
    require(path.stem == lesson_id, f"{path}: filename and lesson_id differ")

    source = resolve(contract["source"]["path"])
    require(source.is_file(), f"{path}: missing lesson source")
    require(sha256(source) == contract["source"]["sha256"], f"{path}: stale lesson source hash")
    lesson = parse_lesson(source)
    require(lesson["lesson_id"] == lesson_id, f"{path}: wrong lesson source")

    contract_sets = [entry["referents"] for entry in contract["vocab_sets"]]
    require(contract_sets == lesson["vocab_sets"], f"{path}: vocabulary sets differ from source")
    labels = [label for values in contract_sets for label in values]
    referents = contract["generic_referents"]
    require([entry["label"] for entry in referents] == labels, f"{path}: generic referent order differs")
    require(len({entry["entity_id"] for entry in referents}) == len(labels), f"{path}: duplicate entity ID")

    ppp = contract["presentation_and_practice"]
    require(ppp["order"] == ["AFFIRMATIVE", "NEGATIVE", "W", "OR"], f"{path}: unsafe form order")
    rules = ppp["binding_rules"]
    require(rules["NEGATIVE"]["actual_referent"] == "next_sibling_in_vocab_set", f"{path}: negative binding must use a sibling")
    require(rules["NEGATIVE"]["queried_referent"] == "target", f"{path}: negative query must retain target")
    require(rules["NEGATIVE"]["truth"] is False, f"{path}: negative truth must be false")
    for values in contract_sets:
        for index, target in enumerate(values):
            actual = values[(index + 1) % len(values)]
            require(actual != target, f"{path}: negative binding collapsed for {target}")

    performance = contract["performance"]
    world_bible = resolve(performance["world_bible"]["path"])
    require(sha256(world_bible) == performance["world_bible"]["sha256"], f"{path}: stale world-bible hash")
    manifest_path = resolve(performance["canonical_manifest"]["path"])
    require(sha256(manifest_path) == performance["canonical_manifest"]["sha256"], f"{path}: stale canonical manifest hash")
    for reference in performance["canonical_inputs"]:
        canonical = canonical_by_id.get(reference["id"])
        require(canonical is not None, f"{path}: unknown canonical input {reference['id']}")
        require(canonical["sha256"] == reference["sha256"], f"{path}: canonical hash mismatch for {reference['id']}")

    entity_ids = {entry["entity_id"] for entry in referents}
    require(set(performance["required_scene_entities"]) == entity_ids, f"{path}: incomplete Performance scene entities")
    derivatives = performance["focus_derivatives"]
    require(set(derivatives["required_entity_ids"]) == entity_ids, f"{path}: incomplete Performance derivatives")
    require(derivatives["source"] == "one_accepted_performance_master", f"{path}: derivatives must share one accepted master")


def main() -> None:
    manifest = json.loads(CANONICAL_MANIFEST.read_text(encoding="utf-8"))
    canonical_by_id = {entry["id"]: entry for entry in manifest["assets"]}
    paths = sorted(CONTRACTS.glob("L[0-9][0-9][0-9].json"))
    require(bool(paths), "no visual contracts found")
    for path in paths:
        validate_contract(path, canonical_by_id)
    print(f"OK: {len(paths)} visual lesson contract(s)")


if __name__ == "__main__":
    main()
