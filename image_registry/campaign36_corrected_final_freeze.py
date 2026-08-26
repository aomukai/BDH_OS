"""Freeze and validate Campaign 36's final ordinary still-image manifest."""

from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from image_registry.campaign36_flux_streaming_luna import load_jsonl
from image_registry.campaign36_visual_reconcile import accepted_generated


ROOT = Path("/media/aomukai/FILES/Ninereeds/image-corpus/exports/campaign36-foundation-preparation-v1")
CORRECTED = ROOT / "lexicon-revision-v1/corrected-manifest-v1"
OUTPUT = CORRECTED / "frozen-ordinary-still-v1"
FLUX = ROOT / "flux-specialist-v1"
SCHEMA_VERSION = "ninereeds_campaign36_frozen_ordinary_still_v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    )
    temporary.replace(path)


def validate(row: dict[str, Any]) -> tuple[str, str, tuple[int, int]]:
    path = Path(str(row["local_path"]))
    expected = str(row["asset_sha256"])
    if not path.is_file():
        raise RuntimeError(f"missing asset bytes for {row['slot_id']}: {path}")
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"hash mismatch for {row['slot_id']}: {path}")
    with Image.open(path) as image:
        image.load()
        size = image.size
    return str(row["slot_id"]), actual, size


def recovery_rows(
    queue: list[dict[str, Any]], accepted: dict[str, dict[str, Any]], phase: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target in queue:
        assignment = str(target["assignment_id"])
        if assignment not in accepted:
            raise RuntimeError(f"missing accepted recovery assignment: {assignment}")
        decision = accepted[assignment]
        rows.append({
            **target,
            "schema_version": SCHEMA_VERSION,
            "assignment_id": assignment,
            "asset_sha256": decision["sha256"],
            "local_path": decision["local_path"],
            "accepted_provider": decision["accepted_provider"],
            "literal_caption": (decision.get("luna_result") or {}).get("literal_caption"),
            "manifest_phase": phase,
            "disposition": "accepted_distinct_variation",
        })
    return rows


def main() -> int:
    requirements = load_jsonl(CORRECTED / "requirements.jsonl")
    requirement_by_slot = {str(row["slot_id"]): row for row in requirements}
    if len(requirements) != 25_000 or len(requirement_by_slot) != 25_000:
        raise RuntimeError("requirements are not the exact 25,000-slot contract")

    base = load_jsonl(CORRECTED / "base-variation-recovery-v1/accepted-distinct-base.jsonl")
    original = load_jsonl(CORRECTED / "variation-recovery-v1/accepted-distinct-generated.jsonl")
    first_queue = load_jsonl(CORRECTED / "variation-recovery-v1/eligible-generation-queue.jsonl")
    base_queue = load_jsonl(CORRECTED / "base-variation-recovery-v1/eligible-generation-queue.jsonl")
    accepted = accepted_generated(FLUX)

    assets: list[dict[str, Any]] = []
    for row in base:
        assets.append({
            **row,
            "schema_version": SCHEMA_VERSION,
            "asset_sha256": row.get("sha256") or row.get("asset_sha256"),
            "manifest_phase": "retained_distinct_base",
        })
    for row in original:
        assets.append({
            **row,
            "schema_version": SCHEMA_VERSION,
            "manifest_phase": "retained_distinct_corrected_generation",
        })
    assets.extend(recovery_rows(first_queue, accepted, "generated_variation_recovery"))
    assets.extend(recovery_rows(base_queue, accepted, "base_variation_recovery"))
    assets.sort(key=lambda row: row["slot_id"])

    by_slot = {str(row["slot_id"]): row for row in assets}
    if len(assets) != 18_890 or len(by_slot) != len(assets):
        raise RuntimeError(f"final ordinary manifest slot mismatch: {len(assets)} / {len(by_slot)}")
    if not set(by_slot) <= set(requirement_by_slot):
        raise RuntimeError("final ordinary manifest contains an unknown slot")

    with ThreadPoolExecutor(max_workers=8) as pool:
        validated = list(pool.map(validate, assets))
    hashes = Counter(asset_hash for _slot, asset_hash, _size in validated)
    over_cap = {asset_hash: count for asset_hash, count in hashes.items() if count > 4}
    if over_cap:
        raise RuntimeError(f"global asset reuse cap exceeded: {list(over_cap.items())[:3]}")

    seen: dict[str, set[str]] = defaultdict(set)
    same_concept_duplicates: list[dict[str, Any]] = []
    for row in assets:
        concept_id = str(row["concept_id"])
        asset_hash = str(row["asset_sha256"])
        if asset_hash in seen[concept_id]:
            same_concept_duplicates.append({
                "slot_id": row["slot_id"],
                "concept_id": concept_id,
                "asset_sha256": asset_hash,
            })
        seen[concept_id].add(asset_hash)
    if same_concept_duplicates:
        raise RuntimeError(
            f"same-concept pixel duplicates remain: {same_concept_duplicates[:3]}"
        )

    duplicate_flags = [
        {
            "asset_sha256": asset_hash,
            "slot_count": count,
            "slot_ids": [row["slot_id"] for row in assets if row["asset_sha256"] == asset_hash],
            "concept_ids": sorted({
                str(row["concept_id"]) for row in assets if row["asset_sha256"] == asset_hash
            }),
            "same_concept_duplicate": False,
        }
        for asset_hash, count in sorted(hashes.items())
        if count > 1
    ]

    residual_slots = sorted(set(requirement_by_slot) - set(by_slot))
    manifest_summary = json.loads((CORRECTED / "summary.json").read_text())
    if len(residual_slots) != int(manifest_summary["separate_non_single_image_or_unplanned_slots"]):
        raise RuntimeError("separate-route residual count changed")
    inventory = {
        str(row["concept_id"]): row
        for row in load_jsonl(FLUX / "inventory/gap_inventory.jsonl")
    }
    residual_rows = [
        {
            "schema_version": SCHEMA_VERSION,
            "slot_id": slot,
            "concept_id": requirement_by_slot[slot]["concept_id"],
            "word": requirement_by_slot[slot]["word"],
            "route": inventory.get(str(requirement_by_slot[slot]["concept_id"]), {}).get(
                "route", "missing_inventory_route"
            ),
        }
        for slot in residual_slots
    ]
    coverage = Counter(str(row["concept_id"]) for row in assets)
    concept_rows = [
        {
            "schema_version": SCHEMA_VERSION,
            "concept_id": concept_id,
            "accepted_distinct_still_images": coverage[concept_id],
            "required_slots": 10,
            "residual_slots": 10 - coverage[concept_id],
            "residual_route": inventory.get(concept_id, {}).get("route", "accepted_images"),
        }
        for concept_id in sorted({str(row["concept_id"]) for row in requirements})
    ]

    write_jsonl(OUTPUT / "accepted-assets.jsonl", assets)
    write_jsonl(OUTPUT / "duplicate-hash-flags.jsonl", duplicate_flags)
    write_jsonl(OUTPUT / "residual-route-slots.jsonl", residual_rows)
    write_jsonl(OUTPUT / "concept-coverage.jsonl", concept_rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "status": "ordinary_still_manifest_frozen",
        "contract_slots": len(requirements),
        "accepted_distinct_ordinary_still_assets": len(assets),
        "retained_distinct_base_assets": len(base),
        "retained_distinct_original_corrected_assets": len(original),
        "generated_variation_recovery_assets": len(first_queue),
        "base_variation_recovery_assets": len(base_queue),
        "separate_non_single_image_or_unplanned_slots": len(residual_rows),
        "validated_asset_files": len(validated),
        "hash_mismatches": 0,
        "missing_asset_files": 0,
        "same_concept_pixel_duplicate_slots": 0,
        "cross_concept_duplicate_hash_flags": len(duplicate_flags),
        "max_slots_per_asset_hash": max(hashes.values(), default=0),
        "asset_hashes_over_reuse_cap": 0,
        "unique_slot_ids": len(by_slot),
        "concepts_at_ten_still_images": sum(row["accepted_distinct_still_images"] == 10 for row in concept_rows),
        "concepts_below_ten_still_images": sum(row["accepted_distinct_still_images"] < 10 for row in concept_rows),
        "ready_for_non_single_image_routes": True,
        "ready_for_deepseek_vl_pretraining_audit": False,
    }
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
