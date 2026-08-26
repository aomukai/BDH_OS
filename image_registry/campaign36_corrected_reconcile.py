"""Reconcile Campaign 36's frozen post-lexicon still-image manifest.

The corrected manifest deliberately separates ordinary still-image work from slots that
need another representation route.  This audit verifies the preserved accepted assets,
the complete lexfix generation queue, and every referenced byte without treating the
separate-route slots as failed generator work.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from image_registry.campaign36_flux_streaming_luna import load_jsonl
from image_registry.campaign36_imagegen_fallback import DEFAULT_ROOT


CAMPAIGN_ROOT = DEFAULT_ROOT.parent
CORRECTED = CAMPAIGN_ROOT / "lexicon-revision-v1/corrected-manifest-v1"
SCHEMA_VERSION = "ninereeds_campaign36_corrected_reconciliation_v1"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def accepted_imagegen(output: Path) -> dict[str, dict[str, Any]]:
    accepted: dict[str, dict[str, Any]] = {}
    for provider, ledger in (
        ("codex-imagegen", output / "decisions.jsonl"),
        ("policy-recovery", output / "policy-recoveries.jsonl"),
    ):
        for row in load_jsonl(ledger, tolerate_partial_tail=True):
            if row.get("verdict") != "accepted":
                continue
            assignment = str(row["assignment_id"])
            if assignment not in accepted or provider == "policy-recovery":
                accepted[assignment] = {**row, "accepted_provider": provider}
    return accepted


def accepted_replacements(output: Path) -> dict[str, dict[str, Any]]:
    replacements: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(output / "asset-replacements.jsonl", tolerate_partial_tail=True):
        if row.get("verdict") != "accepted":
            continue
        for slot in row.get("replaces_slots") or []:
            replacements[str(slot)] = row
    return replacements


def validate_asset(row: dict[str, Any]) -> tuple[str, str, tuple[int, int]]:
    identity = str(row.get("slot_id") or row.get("assignment_id"))
    path = Path(str(row.get("local_path", "")))
    # Preserved downloaded/base rows use ``sha256``; rows inherited from the
    # earlier generated-slot reconciliation use ``asset_sha256``.
    expected = str(row.get("sha256") or row.get("asset_sha256") or "")
    if not path.is_file():
        raise ValueError(f"missing accepted bytes for {identity}: {path}")
    actual = sha256(path)
    if not expected or actual != expected:
        raise ValueError(f"accepted hash mismatch for {identity}: {path}")
    with Image.open(path) as image:
        image.load()
        size = image.size
    return identity, actual, size


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, default=CAMPAIGN_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    corrected = args.campaign_root / "lexicon-revision-v1/corrected-manifest-v1"
    output = args.output or corrected / "reconciliation-final"
    imagegen = args.campaign_root / "flux-specialist-v1/imagegen-v1"

    requirements = load_jsonl(corrected / "requirements.jsonl")
    baseline = load_jsonl(corrected / "accepted-assets.jsonl")
    queue = load_jsonl(corrected / "eligible-generation-queue.jsonl")
    manifest_summary = json.loads((corrected / "summary.json").read_text(encoding="utf-8"))
    inventory = {
        str(row["concept_id"]): row
        for row in load_jsonl(
            args.campaign_root / "flux-specialist-v1/inventory/gap_inventory.jsonl"
        )
    }

    requirement_by_slot = {str(row["slot_id"]): row for row in requirements}
    baseline_by_slot = {str(row["slot_id"]): row for row in baseline}
    queue_by_assignment = {str(row["assignment_id"]): row for row in queue}
    if len(requirements) != 25_000 or len(requirement_by_slot) != 25_000:
        raise ValueError("corrected requirements are not the exact 25,000-slot contract")
    if len(baseline_by_slot) != len(baseline):
        raise ValueError("duplicate slot in corrected accepted-assets manifest")
    if len(queue_by_assignment) != len(queue):
        raise ValueError("duplicate assignment in corrected generation queue")

    accepted = accepted_imagegen(imagegen)
    replacements = accepted_replacements(imagegen)
    missing_assignments = sorted(set(queue_by_assignment) - set(accepted))
    if missing_assignments:
        raise ValueError(f"corrected queue still has missing assignments: {missing_assignments[:5]}")
    generated = {assignment: accepted[assignment] for assignment in queue_by_assignment}
    queue_slots = {str(row["slot_id"]) for row in queue}
    if len(queue_slots) != len(queue):
        raise ValueError("corrected queue does not map one-to-one onto residual slots")
    if set(baseline_by_slot) & queue_slots:
        raise ValueError("corrected generated queue overlaps preserved accepted slots")
    unknown_replacement_slots = set(replacements) - set(baseline_by_slot)
    if unknown_replacement_slots:
        raise ValueError(
            f"asset replacements target unknown preserved slots: {sorted(unknown_replacement_slots)[:5]}"
        )
    for slot, replacement in replacements.items():
        expected_assignment = baseline_by_slot[slot].get("assignment_id")
        if replacement.get("replaces_assignment") != expected_assignment:
            raise ValueError(f"asset replacement assignment mismatch for {slot}")
        baseline_by_slot[slot] = {
            **baseline_by_slot[slot],
            "local_path": replacement["local_path"],
            "sha256": replacement["sha256"],
            "asset_sha256": replacement["sha256"],
            "accepted_provider": "asset-replacement",
            "replacement_id": replacement["assignment_id"],
        }

    final_slots = set(baseline_by_slot) | queue_slots
    if not final_slots <= set(requirement_by_slot):
        raise ValueError("corrected manifest contains slots outside the 25,000-slot contract")
    residual_slots = set(requirement_by_slot) - final_slots
    expected_residual = int(manifest_summary["separate_non_single_image_or_unplanned_slots"])
    if len(residual_slots) != expected_residual:
        raise ValueError(
            f"separate-route residual changed: {len(residual_slots)} != {expected_residual}"
        )

    generated_rows = []
    for assignment, decision in generated.items():
        queue_row = queue_by_assignment[assignment]
        generated_rows.append({
            **decision,
            "assignment_id": assignment,
            "slot_id": queue_row["slot_id"],
            "concept_id": queue_row["concept_id"],
            "word": queue_row["word"],
        })
    assets = list(baseline_by_slot.values()) + generated_rows
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        validated = list(pool.map(validate_asset, assets))

    hashes = Counter(value for _identity, value, _size in validated)
    hashes_over_cap = {value: count for value, count in hashes.items() if count > 4}
    if hashes_over_cap:
        raise ValueError(
            f"accepted asset reuse exceeds four slots: {list(hashes_over_cap.items())[:3]}"
        )
    generated_sizes = Counter(
        size for identity, _value, size in validated if identity in queue_slots
    )
    providers = Counter(row["accepted_provider"] for row in generated_rows)
    coverage = Counter(
        requirement_by_slot[slot]["concept_id"] for slot in final_slots
    )
    contract_concepts = {
        str(row["concept_id"]) for row in requirement_by_slot.values()
    }
    residual_concepts = {
        str(requirement_by_slot[slot]["concept_id"]) for slot in residual_slots
    }
    residual_routes = Counter(
        str(inventory.get(concept_id, {}).get("route", "missing_inventory_route"))
        for concept_id in residual_concepts
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "corrected_still_image_queue_complete",
        "contract_slots": len(requirement_by_slot),
        "preserved_accepted_slots": len(baseline_by_slot),
        "corrected_generation_assignments": len(queue_by_assignment),
        "accepted_corrected_generation_assignments": len(generated),
        "current_accepted_still_image_slots": len(final_slots),
        "separate_non_single_image_or_unplanned_slots": len(residual_slots),
        "missing_required_generation_assignments": 0,
        "validated_asset_files": len(validated),
        "hash_mismatches": 0,
        "missing_asset_files": 0,
        "accepted_generation_providers": dict(sorted(providers.items())),
        "accepted_asset_replacement_slots": len(replacements),
        "generated_image_sizes": {
            f"{width}x{height}": count
            for (width, height), count in sorted(generated_sizes.items())
        },
        "pixel_duplicate_hashes": sum(count > 1 for count in hashes.values()),
        "max_slots_per_asset_hash": max(hashes.values(), default=0),
        "asset_hashes_over_four_slots": len(hashes_over_cap),
        "concepts_at_ten_still_images": sum(
            coverage[concept_id] == 10 for concept_id in contract_concepts
        ),
        "concepts_below_ten_still_images": sum(
            coverage[concept_id] < 10 for concept_id in contract_concepts
        ),
        "concepts_with_zero_still_images": sum(
            coverage[concept_id] == 0 for concept_id in contract_concepts
        ),
        "separate_route_concepts_by_route": dict(sorted(residual_routes.items())),
        "corrected_manifest": str(corrected),
    }
    write_json(output / "summary.json", report)
    write_json(output / "residual-route-slots.json", {
        "schema_version": SCHEMA_VERSION,
        "route": "separate_non_single_image_or_unplanned",
        "slots": [
            {
                "slot_id": slot,
                "concept_id": requirement_by_slot[slot]["concept_id"],
                "word": requirement_by_slot[slot]["word"],
                "route": inventory.get(
                    str(requirement_by_slot[slot]["concept_id"]), {}
                ).get("route", "missing_inventory_route"),
            }
            for slot in sorted(residual_slots)
        ],
    })
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
