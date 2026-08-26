"""Reconcile the corrected Campaign 36 still-image queue without counting pixel clones.

The first accepted asset for a concept/hash pair is retained deterministically. Later
pixel-identical assets remain preserved in the append-only provider ledgers, but their
slots are emitted as variation-recovery assignments with materially different prompt
strategies. This module never starts generation or training.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from image_registry.campaign36_flux_streaming_luna import digest, load_jsonl
from image_registry.campaign36_visual_reconcile import accepted_generated


ROOT = Path("/media/aomukai/FILES/Ninereeds/image-corpus/exports/campaign36-foundation-preparation-v1")
CORRECTED = ROOT / "lexicon-revision-v1/corrected-manifest-v1"
OUTPUT = CORRECTED / "variation-recovery-v1"
FLUX = ROOT / "flux-specialist-v1"
SCHEMA_VERSION = "ninereeds_campaign36_corrected_variation_recovery_v1"

STRATEGIES = (
    "Use a different subject, setting, camera angle, and object arrangement from earlier examples.",
    "Use a close educational detail view with a materially different composition and background.",
    "Use a wide contextual scene with different subjects and a clearly different viewpoint.",
    "Use a clean diagrammatic or studio composition instead of the earlier photographic arrangement.",
    "Use a new real-world scenario that demonstrates the same exact sense through different visual evidence.",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in values)
    )
    temporary.replace(path)


def file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    base = load_jsonl(CORRECTED / "accepted-assets.jsonl")
    queue = load_jsonl(CORRECTED / "eligible-generation-queue.jsonl")
    accepted = accepted_generated(FLUX)
    queue_ids = {row["assignment_id"] for row in queue}
    missing = queue_ids - set(accepted)
    if missing:
        raise RuntimeError(f"corrected queue is not fully accepted: {sorted(missing)[:5]}")

    seen: dict[str, set[str]] = defaultdict(set)
    for row in base:
        asset_hash = str(row.get("sha256") or row.get("asset_sha256") or "")
        if asset_hash:
            seen[str(row["concept_id"])].add(asset_hash)

    retained: list[dict[str, Any]] = []
    residual: list[dict[str, Any]] = []
    for target in sorted(queue, key=lambda row: row["slot_id"]):
        assignment = str(target["assignment_id"])
        decision = accepted[assignment]
        path = Path(str(decision.get("local_path", "")))
        asset_hash = str(decision.get("sha256", ""))
        if not path.is_file() or not asset_hash or digest(path) != asset_hash:
            raise RuntimeError(f"accepted bytes fail validation: {assignment}")
        concept_id = str(target["concept_id"])
        merged = {
            **target,
            "accepted_provider": decision["accepted_provider"],
            "asset_sha256": asset_hash,
            "local_path": str(path),
            "literal_caption": (decision.get("luna_result") or {}).get("literal_caption"),
        }
        if asset_hash in seen[concept_id]:
            residual.append({
                **merged,
                "disposition": "accepted_semantics_but_not_distinct_variation",
                "reason": "pixel_identical_to_prior_asset_for_same_concept",
            })
        else:
            seen[concept_id].add(asset_hash)
            retained.append({**merged, "disposition": "accepted_distinct_variation"})

    recovery_queue: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for index, row in enumerate(residual):
        slot_id = str(row["slot_id"])
        brief = f"lexvar-{slot_id}"
        assignment = f"{brief}-v01"
        strategy = STRATEGIES[index % len(STRATEGIES)]
        prompt = (
            f"Create direct, unambiguous visual evidence for {row['word']!r}: "
            f"{row['teaching_sense']} {strategy} The result must be materially different "
            "from prior examples; a pixel-identical or near-identical reuse is not acceptable."
        )
        recovery_queue.append({
            "schema_version": SCHEMA_VERSION,
            "assignment_id": assignment,
            "replaces_assignment_id": row["assignment_id"],
            "duplicate_asset_sha256": row["asset_sha256"],
            **{key: row[key] for key in (
                "slot_id", "ordinal", "exposure_index", "concept_id", "word",
                "teaching_sense", "part_of_speech",
            )},
            "variation_strategy": strategy,
        })
        source_rows.append({
            "schema_version": SCHEMA_VERSION,
            "production_brief_id": brief,
            "variant_index": 1,
            "generation_attempt": 3,
            "concept_ids": [row["concept_id"]],
            "words": [row["word"]],
            "evidence_by_concept": {row["concept_id"]: row["teaching_sense"]},
            "grounding_mode": "direct",
            "visible_text_policy": "reject",
            "prompt": prompt,
            "width": 512,
            "height": 384,
            "sha256": "0" * 64,
            "local_path": "",
        })
        decisions.append({
            "schema_version": SCHEMA_VERSION,
            "attempt_id": f"{assignment}-a03",
            "assignment_id": assignment,
            "production_brief_id": brief,
            "variant_index": 1,
            "generation_attempt": 3,
            "concept_ids": [row["concept_id"]],
            "sha256": "0" * 64,
            "local_path": "",
            "verdict": "recommission",
            "failure_reasons": ["pixel_identical_asset_does_not_count_as_variation"],
            "recommission_instruction": prompt,
            "review_backend": "corrected_variation_reconciler",
            "review_model": None,
        })

    write_jsonl(OUTPUT / "accepted-distinct-generated.jsonl", retained)
    write_jsonl(OUTPUT / "duplicate-residual-slots.jsonl", residual)
    write_jsonl(OUTPUT / "eligible-generation-queue.jsonl", recovery_queue)
    incoming = FLUX / "streaming-luna/incoming/recommissioned/recommission-lexicon-variation-recovery.jsonl"
    write_jsonl(incoming, source_rows)

    decision_path = FLUX / "streaming-luna/decisions.jsonl"
    existing = load_jsonl(decision_path, tolerate_partial_tail=True)
    existing_ids = {row["assignment_id"] for row in existing}
    wanted_ids = {row["assignment_id"] for row in decisions}
    overlap = existing_ids & wanted_ids
    if overlap and overlap != wanted_ids:
        raise RuntimeError("partial variation-recovery decision set already exists")
    if not overlap:
        with decision_path.open("a", encoding="utf-8") as handle:
            for row in decisions:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()

    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "base_accepted_assets": len(base),
        "corrected_queue_assignments": len(queue),
        "accepted_queue_assignments": len(queue_ids),
        "retained_distinct_generated_assets": len(retained),
        "pixel_duplicate_residual_slots": len(residual),
        "affected_concepts": len({row["concept_id"] for row in residual}),
        "variation_recovery_assignments": len(recovery_queue),
        "ready_for_variation_recovery": bool(recovery_queue),
        "ready_for_final_manifest": not recovery_queue,
        "base_manifest_sha256": file_sha256(CORRECTED / "accepted-assets.jsonl"),
        "corrected_queue_sha256": file_sha256(CORRECTED / "eligible-generation-queue.jsonl"),
    }
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
