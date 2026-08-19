#!/usr/bin/env python3
"""Create a byte-audited successor to an ordered JSONL corpus.

The source is never modified.  Every changed row is selected by its exact
prompt, remains at the same block/line position, and is recorded with before
and after hashes.  The active identity policy must accept the complete output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mission_hub.config import load_config_bundle
from mission_hub.jsonutil import canonical_json, content_hash
from mission_hub.lesson_policy import policy_sha256, validate_lesson_material


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repair", type=Path, required=True)
    parser.add_argument("--concept-inventory", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    output = args.output.resolve()
    repair = json.loads(args.repair.resolve().read_text(encoding="utf-8"))
    if repair.get("schema_version") != "ninereeds_ordered_corpus_repair_v1":
        raise SystemExit("unsupported corpus repair contract")
    source_manifest = source / "manifest.json"
    if _sha256(source_manifest) != repair["source_manifest_sha256"]:
        raise SystemExit("source manifest hash does not match the repair contract")
    if output.exists() and any(output.iterdir()):
        raise SystemExit("output directory must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)

    source_manifest_value = json.loads(source_manifest.read_text(encoding="utf-8"))
    inventory: list[str] = []
    inventory_rank: dict[str, int] = {}
    if args.concept_inventory:
        for rank, line in enumerate(args.concept_inventory.resolve().read_text(encoding="utf-8").splitlines(), 1):
            concept = json.loads(line)["concept_id"]
            inventory.append(concept)
            inventory_rank[concept.casefold()] = rank
    block_concepts = {
        f"block-{item['block_index']:02d}.jsonl": item["concepts"]
        for item in source_manifest_value.get("blocks", [])
    }

    bundle = load_config_bundle(REPO / "config/mission_hub")
    replacements = repair["prompt_replacements"]
    row_replacements = repair.get("row_replacements", {})
    audit: list[dict] = []
    block_records: list[dict] = []
    order_map: list[dict] = []
    used_prompts: set[str] = set()
    used_rows: set[str] = set()
    total_rows = 0
    for block in sorted(source.glob("block-*.jsonl")):
        rows: list[dict] = []
        source_positions: list[int] = []
        original_sha = _sha256(block)
        for line_number, line in enumerate(block.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            before = dict(row)
            row_key = f"{block.name}:{line_number}"
            exact_repair = row_replacements.get(row_key)
            if exact_repair is not None:
                if content_hash(row) != exact_repair["expected_before_sha256"]:
                    raise SystemExit(f"{row_key}: source row no longer matches its exact repair")
                row["prompt"] = exact_repair["prompt"]
                row["completion"] = exact_repair["completion"]
                used_rows.add(row_key)
                audit.append({
                    "block": block.name,
                    "line": line_number,
                    "reason": "source_boundary_token_contamination",
                    "before_sha256": content_hash(before),
                    "after_sha256": content_hash(row),
                    "before": before,
                    "after": dict(row),
                    "findings": [],
                })
            findings = validate_lesson_material(row, bundle.identity_policy)
            if findings:
                replacement = replacements.get(row.get("prompt"))
                if replacement is None:
                    raise SystemExit(f"{block.name}:{line_number}: flagged row has no exact repair")
                row["prompt"], row["completion"] = replacement
                used_prompts.add(before["prompt"])
                remaining = validate_lesson_material(row, bundle.identity_policy)
                if remaining:
                    raise SystemExit(f"{block.name}:{line_number}: repair still violates identity policy")
                audit.append({
                    "block": block.name,
                    "line": line_number,
                    "reason": "obsolete_identity_assumption",
                    "before_sha256": content_hash(before),
                    "after_sha256": content_hash(row),
                    "before": before,
                    "after": row,
                    "findings": findings,
                })
            rows.append(row)
            source_positions.append(line_number)
        if len(rows) != 500:
            raise SystemExit(f"{block.name}: expected exactly 500 ordered rows")
        concepts = block_concepts.get(block.name, [])
        if concepts:
            if not inventory:
                raise SystemExit("a concept inventory is required for manifest-backed lesson blocks")
            new_positions = [index for index, row in enumerate(rows) if row.get("stage") == "new_allowlist"]
            if len(new_positions) != len(concepts):
                raise SystemExit(f"{block.name}: new-lesson rows do not match the concept manifest")
            assigned: dict[str, tuple[dict, int]] = {}
            archive_root = source.parents[4]
            for concept in concepts:
                lesson_path = REPO / concept["train_source"]
                if not lesson_path.is_file():
                    lesson_path = archive_root / concept["train_source"]
                turns = _lesson_turns(lesson_path)
                matches = [
                    index for index in new_positions
                    if (rows[index]["prompt"], rows[index]["completion"]) in turns
                ]
                if not matches:
                    prompts = {prompt for prompt, _ in turns}
                    matches = [index for index in new_positions if rows[index]["prompt"] in prompts]
                if len(matches) != 1:
                    raise SystemExit(f"{block.name}: cannot bind concept {concept['concept_id']} to exactly one row")
                source_index = matches[0]
                if any(source_index == value[1] for value in assigned.values()):
                    raise SystemExit(f"{block.name}: two concepts resolve to one lesson row")
                assigned[concept["concept_id"]] = (dict(rows[source_index]), source_index)
            ordered_concepts = sorted(concepts, key=lambda item: item["rank"])
            for target_index, concept in zip(new_positions, ordered_concepts):
                row, source_index = assigned[concept["concept_id"]]
                dependencies = _dependencies(concept["concept_id"], concept["rank"], inventory_rank)
                row["concept"] = concept["concept_id"]
                row["depends_on"] = dependencies
                rows[target_index] = row
                source_positions[target_index] = source_index + 1
        target = output / block.name
        target.write_text("".join(canonical_json(row) + "\n" for row in rows), encoding="utf-8")
        for output_line, (row, source_line) in enumerate(zip(rows, source_positions), 1):
            order_map.append({
                "block": block.name, "output_line": output_line,
                "source_line": source_line, "row_sha256": content_hash(row),
                "concept": row.get("concept"), "depends_on": row.get("depends_on", []),
            })
        block_records.append({
            "block": block.name,
            "row_count": len(rows),
            "source_sha256": original_sha,
            "reconciled_sha256": _sha256(target),
        })
        total_rows += len(rows)

    unused = sorted(set(replacements) - used_prompts)
    if unused:
        raise SystemExit("repair contract contains unused prompt mappings: " + ", ".join(unused))
    unused_rows = sorted(set(row_replacements) - used_rows)
    if unused_rows:
        raise SystemExit("repair contract contains unused exact rows: " + ", ".join(unused_rows))
    audit_path = output / "repair-audit.jsonl"
    audit_path.write_text("".join(canonical_json(item) + "\n" for item in audit), encoding="utf-8")
    order_path = output / "order-map.jsonl"
    order_path.write_text("".join(canonical_json(item) + "\n" for item in order_map), encoding="utf-8")
    manifest = {
        "schema_version": "ninereeds_reconciled_ordered_corpus_v1",
        "repair_id": repair["repair_id"],
        "reason": repair["reason"],
        "source_manifest_sha256": repair["source_manifest_sha256"],
        "identity_policy_id": bundle.identity_policy["id"],
        "identity_policy_version": bundle.identity_policy["version"],
        "identity_policy_sha256": policy_sha256(bundle.identity_policy),
        "order_policy": "declared_only",
        "shuffle_allowed": False,
        "block_count": len(block_records),
        "row_count": total_rows,
        "changed_row_count": len(audit),
        "audit_sha256": _sha256(audit_path),
        "order_map_sha256": _sha256(order_path),
        "concept_order": "ascending_source_rank_within_declared_new_lesson_slots",
        "dependency_derivation": "exact_earlier_inventory_components_v1",
        "blocks": block_records,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


def _lesson_turns(path: Path) -> set[tuple[str, str]]:
    turns: set[tuple[str, str]] = set()
    prompt: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("[user]"):
            prompt = line[len("[user]"):].strip()
        elif line.startswith("[Ninereeds]") and prompt is not None:
            turns.add((prompt, line[len("[Ninereeds]"):].strip()))
            prompt = None
    return turns


def _dependencies(concept: str, rank: int, inventory_rank: dict[str, int]) -> list[str]:
    stop = {"a", "an", "the", "of", "that", "has", "during"}
    dependencies: list[str] = []
    for component in re.split(r"[\s-]+", concept.casefold()):
        component_rank = inventory_rank.get(component)
        if component in stop or component_rank is None or component_rank >= rank:
            continue
        if component not in dependencies:
            dependencies.append(component)
    return dependencies


if __name__ == "__main__":
    raise SystemExit(main())
