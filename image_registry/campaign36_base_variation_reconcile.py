"""Create the final bounded recovery wave for pixel clones in retained base assets."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from image_registry.campaign36_flux_streaming_luna import load_jsonl


ROOT = Path("/media/aomukai/FILES/Ninereeds/image-corpus/exports/campaign36-foundation-preparation-v1")
CORRECTED = ROOT / "lexicon-revision-v1/corrected-manifest-v1"
OUTPUT = CORRECTED / "base-variation-recovery-v1"
FLUX = ROOT / "flux-specialist-v1"
SCHEMA_VERSION = "ninereeds_campaign36_base_variation_recovery_v1"
STRATEGIES = (
    "Use different subjects, a different setting, and a different camera angle.",
    "Use a materially different close educational view and object arrangement.",
    "Use a wide contextual scene with a new viewpoint and background.",
    "Use a clean diagrammatic or studio composition unlike prior examples.",
    "Use a different real-world scenario demonstrating the same exact sense.",
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    )
    temporary.replace(path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    base_path = CORRECTED / "accepted-assets.jsonl"
    base = sorted(load_jsonl(base_path), key=lambda row: row["slot_id"])
    seen: dict[str, set[str]] = defaultdict(set)
    retained: list[dict[str, Any]] = []
    residual: list[dict[str, Any]] = []
    for row in base:
        concept_id = str(row["concept_id"])
        asset_hash = str(row.get("sha256") or row.get("asset_sha256") or "")
        if not asset_hash:
            raise RuntimeError(f"base asset lacks a hash: {row['slot_id']}")
        if asset_hash in seen[concept_id]:
            residual.append({
                **row,
                "duplicate_asset_sha256": asset_hash,
                "disposition": "accepted_semantics_but_not_distinct_variation",
                "reason": "pixel_identical_to_prior_base_asset_for_same_concept",
            })
        else:
            seen[concept_id].add(asset_hash)
            retained.append({**row, "disposition": "accepted_distinct_base_variation"})

    queue: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for index, row in enumerate(residual):
        slot_id = str(row["slot_id"])
        brief = f"lexbasevar-{slot_id}"
        assignment = f"{brief}-v01"
        strategy = STRATEGIES[index % len(STRATEGIES)]
        instruction = (
            f"Create direct, unambiguous visual evidence for {row['word']!r}: "
            f"{row['teaching_sense']} {strategy} The image must be materially different "
            "from earlier assets; pixel-identical reuse is invalid."
        )
        queue.append({
            "schema_version": SCHEMA_VERSION,
            "assignment_id": assignment,
            "replaces_base_slot_id": slot_id,
            "duplicate_asset_sha256": row["duplicate_asset_sha256"],
            "slot_id": slot_id,
            "ordinal": int(row.get("ordinal") or slot_id[1:5]),
            "exposure_index": int(row.get("exposure_index") or slot_id[7:9]),
            "concept_id": row["concept_id"],
            "word": row["word"],
            "teaching_sense": row["teaching_sense"],
            "part_of_speech": row.get("part_of_speech", "unspecified"),
            "variation_strategy": strategy,
        })
        sources.append({
            "schema_version": SCHEMA_VERSION,
            "production_brief_id": brief,
            "variant_index": 1,
            "generation_attempt": 3,
            "concept_ids": [row["concept_id"]],
            "words": [row["word"]],
            "evidence_by_concept": {row["concept_id"]: row["teaching_sense"]},
            "grounding_mode": "direct",
            "visible_text_policy": "reject",
            "prompt": instruction,
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
            "failure_reasons": ["pixel_identical_base_asset_does_not_count_as_variation"],
            "recommission_instruction": instruction,
            "review_backend": "corrected_base_variation_reconciler",
            "review_model": None,
        })

    write_jsonl(OUTPUT / "accepted-distinct-base.jsonl", retained)
    write_jsonl(OUTPUT / "duplicate-residual-slots.jsonl", residual)
    write_jsonl(OUTPUT / "eligible-generation-queue.jsonl", queue)
    write_jsonl(
        FLUX / "streaming-luna/incoming/recommissioned/recommission-base-variation-recovery.jsonl",
        sources,
    )
    decision_path = FLUX / "streaming-luna/decisions.jsonl"
    existing = load_jsonl(decision_path, tolerate_partial_tail=True)
    existing_ids = {row["assignment_id"] for row in existing}
    wanted_ids = {row["assignment_id"] for row in decisions}
    overlap = existing_ids & wanted_ids
    if overlap and overlap != wanted_ids:
        raise RuntimeError("partial base-variation decision set already exists")
    if not overlap:
        with decision_path.open("a", encoding="utf-8") as handle:
            for row in decisions:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()

    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "base_assets": len(base),
        "retained_distinct_base_assets": len(retained),
        "pixel_duplicate_residual_slots": len(residual),
        "affected_concepts": len({row["concept_id"] for row in residual}),
        "variation_recovery_assignments": len(queue),
        "ready_for_base_variation_recovery": bool(queue),
        "base_manifest_sha256": sha256(base_path),
    }
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
