#!/usr/bin/env python3
"""Derive a stable, dependency-checked ordering variant from a certified corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from mission_hub.config import load_config_bundle
from mission_hub.jsonutil import canonical_json, content_hash
from mission_hub.lesson_policy import policy_sha256, validate_lesson_material


PROTECTED_STAGES = {"identity", "special_de", "special_ja"}


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
    parser.add_argument("--variant-id", required=True)
    parser.add_argument("--protected-position", choices=("first", "last"), required=True)
    parser.add_argument("--known-inventory", type=Path, required=True)
    parser.add_argument("--known-count", type=int, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit("output directory must be absent or empty")
    output.mkdir(parents=True, exist_ok=True)
    source_manifest_path = source / "manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    inventory = [
        json.loads(line)["concept_id"]
        for line in args.known_inventory.resolve().read_text(encoding="utf-8").splitlines()
    ]
    if not 1 <= args.known_count <= len(inventory):
        raise SystemExit("known-count is outside the concept inventory")
    available = {value.casefold() for value in inventory[:args.known_count]}
    bundle = load_config_bundle(REPO / "config/mission_hub")
    order_map: list[dict] = []
    blocks: list[dict] = []
    total = 0
    for block in sorted(source.glob("block-*.jsonl")):
        source_rows = [json.loads(line) for line in block.read_text(encoding="utf-8").splitlines() if line.strip()]
        protected = [(index + 1, row) for index, row in enumerate(source_rows) if row.get("stage") in PROTECTED_STAGES]
        ordinary = [(index + 1, row) for index, row in enumerate(source_rows) if row.get("stage") not in PROTECTED_STAGES]
        ordered = protected + ordinary if args.protected_position == "first" else ordinary + protected
        if len(ordered) != 500 or len(protected) != 50:
            raise SystemExit(f"{block.name}: expected 500 rows and exactly 50 protected anchors")
        output_rows = []
        for output_line, (source_line, row) in enumerate(ordered, 1):
            findings = validate_lesson_material(row, bundle.identity_policy)
            if findings:
                raise SystemExit(f"{block.name}:{source_line}: source violates active identity policy")
            if len(row["completion"].encode("utf-8")) > bundle.training["max_completion_utf8_bytes"]:
                raise SystemExit(f"{block.name}:{source_line}: completion exceeds active byte bound")
            if "concept" in row:
                missing = [value for value in row["depends_on"] if value.casefold() not in available]
                if missing:
                    raise SystemExit(
                        f"{block.name}:{source_line}: dependency-order violation for {row['concept']}: {missing}"
                    )
                available.add(row["concept"].casefold())
            output_rows.append(row)
            order_map.append({
                "block": block.name, "output_line": output_line,
                "source_line": source_line, "row_sha256": content_hash(row),
                "stage": row["stage"], "concept": row.get("concept"),
            })
        target = output / block.name
        target.write_text("".join(canonical_json(row) + "\n" for row in output_rows), encoding="utf-8")
        blocks.append({
            "block": block.name, "row_count": 500, "protected_count": 50,
            "source_sha256": _sha256(block), "variant_sha256": _sha256(target),
            "ordered_concepts": [
                {"concept": row["concept"], "depends_on": row["depends_on"]}
                for row in output_rows if "concept" in row
            ],
        })
        total += 500
    order_path = output / "order-map.jsonl"
    order_path.write_text("".join(canonical_json(item) + "\n" for item in order_map), encoding="utf-8")
    manifest = {
        "schema_version": "ninereeds_ordered_corpus_variant_v1",
        "variant_id": args.variant_id, "source_manifest_sha256": _sha256(source_manifest_path),
        "source_repair_id": source_manifest["repair_id"],
        "ordering_recipe": f"stable_protected_{args.protected_position}_v1",
        "protected_stages": sorted(PROTECTED_STAGES),
        "order_policy": "declared_only", "shuffle_allowed": False,
        "dependency_order_required": True, "known_inventory_count": args.known_count,
        "identity_policy_sha256": policy_sha256(bundle.identity_policy),
        "row_count": total, "block_count": len(blocks),
        "order_map_sha256": _sha256(order_path), "blocks": blocks,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
