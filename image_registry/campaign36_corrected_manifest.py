"""Freeze the repaired Campaign 36 image manifest and ImageGen recovery queue.

This preserves compatible accepted assets, removes assets rejected by the post-lexicon
Luna audit, supersedes the stale unfinished generation plan, and creates one immutable
ImageGen assignment for each eligible residual slot. It starts no generation or training.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path("/media/aomukai/FILES/Ninereeds/image-corpus/exports/campaign36-foundation-preparation-v1")
LEXICON = ROOT / "lexicon-revision-v1/luna-repair-v1/repaired-lexicon.jsonl"
COMPAT = ROOT / "lexicon-revision-v1/luna-image-compatibility-v1/decisions.jsonl"
COMPAT_SUMMARY = ROOT / "lexicon-revision-v1/luna-image-compatibility-v1/summary.json"
BASE = ROOT / "loop/corrections/2026-08-22-knew-to-know/decisions.jsonl"
OLD_ACCEPTED_GENERATED = ROOT / "flux-specialist-v1/reconciliation-current/accepted-generated-slots.jsonl"
OLD_PENDING = ROOT / "flux-specialist-v1/reconciliation-current/pending-generated-slots.jsonl"
FLUX = ROOT / "flux-specialist-v1"
OUTPUT = ROOT / "lexicon-revision-v1/corrected-manifest-v1"
SCHEMA_VERSION = "ninereeds_campaign36_corrected_manifest_v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in values),
        encoding="utf-8",
    )
    temporary.replace(path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    gate = json.loads(COMPAT_SUMMARY.read_text(encoding="utf-8"))
    if not gate.get("ready_for_image_reconciliation"):
        raise RuntimeError("image-compatibility gate is not complete")
    lexicon_rows = rows(LEXICON)
    if len(lexicon_rows) != 2500:
        raise RuntimeError("repaired lexicon is not exactly 2,500 rows")
    lexicon = {row["source"]["concept_id"]: row for row in lexicon_rows}
    by_ordinal = {int(row["source"]["ordinal"]): row for row in lexicon_rows}
    changed_ids = {key for key, row in lexicon.items() if row.get("luna_decision")}

    accepted: dict[str, dict[str, Any]] = {}
    for row in rows(BASE):
        if row.get("disposition") == "accepted":
            accepted[row["slot_id"]] = row
    for row in rows(OLD_ACCEPTED_GENERATED):
        accepted[row["slot_id"]] = {**row, "disposition": "accepted"}

    compat = rows(COMPAT)
    compatible_slots = {row["slot_id"] for row in compat if row.get("compatible") is True}
    audited_slots = {row["slot_id"] for row in compat}
    changed_accepted = {
        slot_id for slot_id, row in accepted.items() if row.get("concept_id") in changed_ids
    }
    if changed_accepted != audited_slots:
        raise RuntimeError(
            f"changed accepted/audited mismatch: accepted={len(changed_accepted)} audited={len(audited_slots)}"
        )
    accepted = {
        slot_id: row for slot_id, row in accepted.items()
        if row.get("concept_id") not in changed_ids or slot_id in compatible_slots
    }

    lexicon_digest = sha256(LEXICON)
    manifest: list[dict[str, Any]] = []
    for slot_id, asset in sorted(accepted.items()):
        concept = lexicon[asset["concept_id"]]
        effective = concept["effective"]
        manifest.append({
            **asset,
            "schema_version": SCHEMA_VERSION,
            "word": effective["teaching_term"],
            "teaching_sense": effective["teaching_sense"],
            "part_of_speech": effective["part_of_speech"],
            "lexicon_sha256": lexicon_digest,
            "post_lexicon_compatibility": (
                "luna_compatible" if asset["concept_id"] in changed_ids else "unchanged_concept"
            ),
        })

    all_slots: dict[str, dict[str, Any]] = {}
    for ordinal in range(1, 2501):
        concept = by_ordinal[ordinal]
        effective = concept["effective"]
        for exposure in range(1, 11):
            slot_id = f"c{ordinal:04d}-i{exposure:02d}"
            all_slots[slot_id] = {
                "slot_id": slot_id,
                "ordinal": ordinal,
                "exposure_index": exposure,
                "concept_id": concept["source"]["concept_id"],
                "word": effective["teaching_term"],
                "teaching_sense": effective["teaching_sense"],
                "part_of_speech": effective["part_of_speech"],
            }

    missing = set(all_slots) - set(accepted)
    old_pending_rows = rows(OLD_PENDING)
    old_pending_slots = {row["slot_id"] for row in old_pending_rows}
    # All gaps caused by changed targets are eligible for new still images. For unchanged
    # targets, preserve only the previously frozen ordinary still-image backlog; other
    # representation routes remain separate.
    eligible = sorted(
        slot_id for slot_id in missing
        if all_slots[slot_id]["concept_id"] in changed_ids or slot_id in old_pending_slots
    )

    queue: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    synthetic_decisions: list[dict[str, Any]] = []
    for slot_id in eligible:
        target = all_slots[slot_id]
        brief = f"lexfix-{slot_id}"
        assignment = f"{brief}-v00"
        attempt = f"{assignment}-a03"
        queue.append({
            "schema_version": SCHEMA_VERSION,
            "assignment_id": assignment,
            **target,
            "reason": (
                "changed_teaching_target_requires_compatible_asset"
                if target["concept_id"] in changed_ids else "unfinished_frozen_still_image_backlog"
            ),
        })
        source_rows.append({
            "schema_version": SCHEMA_VERSION,
            "production_brief_id": brief,
            "variant_index": 0,
            "generation_attempt": 3,
            "concept_ids": [target["concept_id"]],
            "words": [target["word"]],
            "evidence_by_concept": {target["concept_id"]: target["teaching_sense"]},
            "grounding_mode": "direct",
            "visible_text_policy": "reject",
            "prompt": "Frozen corrected-lexicon ImageGen assignment.",
            "width": 512,
            "height": 384,
            "sha256": "0" * 64,
            "local_path": "",
        })
        synthetic_decisions.append({
            "schema_version": SCHEMA_VERSION,
            "attempt_id": attempt,
            "assignment_id": assignment,
            "production_brief_id": brief,
            "variant_index": 0,
            "generation_attempt": 3,
            "concept_ids": [target["concept_id"]],
            "sha256": "0" * 64,
            "local_path": "",
            "verdict": "recommission",
            "failure_reasons": ["corrected_lexicon_requires_new_asset"],
            "recommission_instruction": (
                f"Create direct, unambiguous visual evidence for {target['word']!r}: "
                f"{target['teaching_sense']}"
            ),
            "review_backend": "corrected_manifest_planner",
            "review_model": None,
        })

    old_pending_assignments = sorted({row["assignment_id"] for row in old_pending_rows})
    superseded = [
        {
            "schema_version": SCHEMA_VERSION,
            "created_at": now(),
            "assignment_id": assignment,
            "reason": "Superseded by the frozen post-lexicon corrected manifest and per-slot queue.",
        }
        for assignment in old_pending_assignments
    ]

    write_jsonl(OUTPUT / "accepted-assets.jsonl", manifest)
    write_jsonl(OUTPUT / "requirements.jsonl", list(all_slots.values()))
    write_jsonl(OUTPUT / "eligible-generation-queue.jsonl", queue)
    write_jsonl(FLUX / "imagegen-v1/superseded-assignments.jsonl", superseded)
    write_jsonl(
        FLUX / "streaming-luna/incoming/recommissioned/recommission-lexicon-repair.jsonl",
        source_rows,
    )

    decision_path = FLUX / "streaming-luna/decisions.jsonl"
    existing_decisions = rows(decision_path)
    existing_ids = {row["assignment_id"] for row in existing_decisions}
    unexpected = existing_ids & {row["assignment_id"] for row in synthetic_decisions}
    if unexpected:
        if unexpected != {row["assignment_id"] for row in synthetic_decisions}:
            raise RuntimeError("partial corrected queue already exists in the append-only decision ledger")
    else:
        with decision_path.open("a", encoding="utf-8") as handle:
            for row in synthetic_decisions:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()

    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "contract_slots": 25000,
        "accepted_assets": len(manifest),
        "all_missing_slots": len(missing),
        "changed_concepts": len(changed_ids),
        "changed_concept_generation_slots": sum(
            all_slots[slot_id]["concept_id"] in changed_ids for slot_id in eligible
        ),
        "preserved_old_pending_slots": sum(
            all_slots[slot_id]["concept_id"] not in changed_ids for slot_id in eligible
        ),
        "eligible_generation_assignments": len(queue),
        "superseded_old_assignments": len(superseded),
        "separate_non_single_image_or_unplanned_slots": len(missing) - len(eligible),
        "lexicon_sha256": lexicon_digest,
        "compatibility_sha256": sha256(COMPAT),
        "accepted_manifest_sha256": sha256(OUTPUT / "accepted-assets.jsonl"),
        "queue_sha256": sha256(OUTPUT / "eligible-generation-queue.jsonl"),
        "ready_for_headless_imagegen": True,
    }
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
