"""Apply the audited Campaign 36 ``knew`` -> ``know`` lexeme correction.

The stable source concept ID remains ``knew`` so all prior provenance stays connected.
Only the teaching term, sense, rejected legacy slot, and ten-image representation plan
change. Historical generation/review ledgers remain append-only.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from image_registry.campaign36_flux_streaming_luna import append_jsonl, load_jsonl
from image_registry.campaign36_imagegen_fallback import provider_attempts


CAMPAIGN = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1"
)
FLUX = CAMPAIGN / "flux-specialist-v1"
STATE = CAMPAIGN / "loop/state.json"
CORRECTION_ID = "2026-08-22-knew-to-know"
CORRECTION = CAMPAIGN / "loop/corrections" / CORRECTION_ID
SENSE = (
    "To have knowledge, understanding, recognition, or familiarity concerning a fact, "
    "subject, person, place, or skill."
)
EVIDENCE = (
    "A clear conventional symbol or observable demonstration of knowledge, learning, "
    "understanding, recognition, or organized concepts is prominent and coherent."
)
OVERRIDE_REVISION = 2
PROMPTS = [
    "A clean educational anatomical illustration of a healthy human brain, centered and detailed, symbolizing knowledge and understanding.",
    "A warm, uncluttered study scene with several books and one open book, clearly symbolizing accumulated knowledge.",
    "A historical writing scene with papyrus and a reed pen, carefully arranged as preserved written knowledge.",
    "A university graduate wearing a mortarboard and gown and holding a diploma, clearly symbolizing acquired knowledge.",
    "A stylized tree of knowledge: instead of leaves, its branches carry coherent concept icons, with land animals on one branch, fish on another, and birds on another.",
    "A whimsical but coherent educational illustration of a watering can watering a brain growing on a flower stem, symbolizing knowledge being cultivated.",
    "A bright illuminated light bulb beside an open book, a simple conventional symbol of knowing and understanding.",
    "A person confidently and correctly matching several animals to their habitats on a learning board, visibly demonstrating knowledge.",
    "A teacher clearly explaining a coherent diagram to attentive learners, visibly demonstrating organized knowledge and understanding.",
    "A library reading table with books, a globe, a microscope, and organized notes, presented as varied sources of knowledge without clutter.",
]
EVIDENCES = [
    "A prominent, anatomically coherent human brain is used as the conventional contextual anchor for thought, memory, understanding, and knowledge; it need not expose a person's hidden mental state.",
    "Several coherent books and a clearly open book are prominent conventional sources and stores of accumulated knowledge.",
    "Papyrus together with a reed pen is plainly visible as a historical medium for recording, preserving, and transmitting knowledge.",
    "Graduation regalia, a mortarboard, and a diploma are plainly visible as a conventional milestone of acquired knowledge and completed education.",
    "A coherent tree organizes recognizable concept icons into meaningful branches, visibly representing structured and connected knowledge.",
    "A watering can visibly nourishes a brain growing like a flower, an intentional visual metaphor for cultivating and taking in knowledge.",
    "An illuminated light bulb beside an open book is plainly visible as a conventional contextual symbol of knowing and understanding.",
    "A person visibly makes correct animal-to-habitat matches, providing an observable demonstration of knowledge rather than an inferred expression.",
    "A teacher visibly explains a coherent diagram to learners, providing an observable demonstration and transmission of organized knowledge.",
    "Books, a globe, a microscope, and organized notes are coherently arranged as visibly distinct sources and tools of knowledge.",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def rewrite_one(path: Path, predicate, transform) -> dict[str, Any]:
    rows = load_jsonl(path)
    matches = [index for index, row in enumerate(rows) if predicate(row)]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one matching row in {path}, found {len(matches)}")
    index = matches[0]
    before = rows[index]
    rows[index] = transform(dict(before))
    write_jsonl(path, rows)
    return before


def corrected_base(source: Path, target: Path) -> tuple[int, dict[str, Any]]:
    rows = load_jsonl(source)
    affected = [row for row in rows if row.get("concept_id") == "knew"]
    if len(affected) != 10:
        raise ValueError(f"expected ten knew slots, found {len(affected)}")
    accepted_before = sum(row.get("disposition") == "accepted" for row in rows)
    for row in affected:
        row["word"] = "know"
        row["concept"] = "know"
        row["teaching_sense"] = SENSE
        row["lexeme_correction"] = CORRECTION_ID
        if row.get("disposition") == "accepted":
            row["superseded_disposition"] = "accepted"
            row["disposition"] = "lexeme_correction_replacement_required"
    write_jsonl(target, rows)
    accepted_after = sum(row.get("disposition") == "accepted" for row in rows)
    return accepted_after, {
        "source": str(source),
        "target": str(target),
        "accepted_before": accepted_before,
        "accepted_after": accepted_after,
        "corrected_slots": [row["slot_id"] for row in affected],
    }


def append_variant_ten_source() -> None:
    decision_path = FLUX / "streaming-luna/decisions.jsonl"
    if any(row.get("assignment_id") == "scene-0027-a4-g1-v09" for row in load_jsonl(decision_path)):
        return
    prior = next(
        row for row in reversed(load_jsonl(decision_path))
        if row.get("assignment_id") == "scene-0027-a4-g1-v08"
    )
    source = {
        "schema_version": "ninereeds_campaign36_flux_recommission_request_v1",
        "production_brief_id": "scene-0027-a4-g1",
        "variant_index": 9,
        "generation_attempt": 3,
        "concept_ids": ["knew"],
        "words": ["know"],
        "evidence_by_concept": {"knew": EVIDENCE},
        "grounding_mode": "contextual_transfer",
        "local_path": prior["local_path"],
        "sha256": prior["sha256"],
        "width": 512,
        "height": 384,
        "correction_id": CORRECTION_ID,
    }
    append_jsonl(
        FLUX / "streaming-luna/incoming/recommissioned/recommission-lexeme-correction.jsonl",
        source,
    )
    append_jsonl(decision_path, {
        "schema_version": "ninereeds_campaign36_flux_streaming_luna_v1",
        "assignment_id": "scene-0027-a4-g1-v09",
        "attempt_id": "scene-0027-a4-g1-v09-a03",
        "production_brief_id": "scene-0027-a4-g1",
        "variant_index": 9,
        "generation_attempt": 3,
        "concept_ids": ["knew"],
        "local_path": prior["local_path"],
        "sha256": prior["sha256"],
        "verdict": "recommission",
        "failure_reasons": ["lexeme-correction:new-know-representation-required"],
        "recommission_instruction": PROMPTS[9],
        "correction_id": CORRECTION_ID,
    })


def append_overrides() -> None:
    output = FLUX / "imagegen-v1"
    attempts = provider_attempts(output)
    existing = {
        row.get("assignment_id")
        for row in load_jsonl(output / "representation-overrides.jsonl", tolerate_partial_tail=True)
        if row.get("correction_id") == CORRECTION_ID
        and int(row.get("override_revision", 1)) == OVERRIDE_REVISION
    }
    for variant, (prompt, evidence) in enumerate(zip(PROMPTS, EVIDENCES, strict=True)):
        assignment = f"scene-0027-a4-g1-v{variant:02d}"
        if assignment in existing:
            continue
        append_jsonl(output / "representation-overrides.jsonl", {
            "schema_version": "ninereeds_campaign36_imagegen_fallback_v1",
            "assignment_id": assignment,
            "after_attempt": attempts.get(assignment, 0),
            "allowed_attempts": 3,
            "evidence_by_concept": {"knew": evidence},
            "words": ["know"],
            "grounding_mode": "contextual_transfer",
            "representation_prompt": prompt,
            "reason": "User-approved minimal lexeme correction and representation set.",
            "authority": "user-approved-manual-representation-triage",
            "visible_text_policy": "reject",
            "visible_text_note": None,
            "correction_id": CORRECTION_ID,
            "override_revision": OVERRIDE_REVISION,
        })


def main() -> int:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    source = Path(state["authoritative_decisions"])
    if CORRECTION_ID in str(source):
        source = Path(json.loads((CORRECTION / "manifest.json").read_text())["base_correction"]["source"])
    target = CORRECTION / "decisions.jsonl"
    accepted_after, base_manifest = corrected_base(source, target)

    inventory_path = FLUX / "inventory/gap_inventory.jsonl"
    inventory_before = rewrite_one(
        inventory_path,
        lambda row: row.get("concept_id") == "knew",
        lambda row: {
            **row,
            "word": "know",
            "accepted_examples": [],
            "accepted_slots": 0,
            "missing_slot_ids": [f"c1498-i{i:02d}" for i in range(1, 11)],
            "missing_slots": 10,
            "route": "single_image_contextual_transfer",
            "curriculum_excerpt": "Know means to have knowledge, understanding, recognition, or familiarity. The language curriculum later teaches knew as its irregular past form.",
            "lexeme_correction": CORRECTION_ID,
        },
    )
    brief_path = FLUX / "prompt-composition/production_briefs.jsonl"
    brief_before = rewrite_one(
        brief_path,
        lambda row: row.get("production_brief_id") == "scene-0027-a4-g1",
        lambda row: {
            **row,
            "assignment_count": 10,
            "variant_count": 10,
            "flux_edit_jobs": 9,
            "capture_description": PROMPTS[0],
            "flux_prompt_template": PROMPTS[0],
            "evidence_by_concept": {"knew": EVIDENCE},
            "grounding_mode": "contextual_transfer",
            "status": "lexeme_corrected_for_imagegen",
            "lexeme_correction": CORRECTION_ID,
        },
    )
    append_variant_ten_source()
    append_overrides()

    state["authoritative_decisions"] = str(target)
    state["accepted_slots"] = accepted_after
    state["residual_slots"] = 25_000 - accepted_after
    state["updated_at"] = now()
    state["lexeme_correction"] = CORRECTION_ID
    temporary = STATE.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATE)

    manifest = {
        "schema_version": "ninereeds_campaign36_lexeme_correction_v1",
        "correction_id": CORRECTION_ID,
        "created_at": now(),
        "source_concept_id": "knew",
        "source_term": "knew",
        "teaching_term": "know",
        "teaching_sense": SENSE,
        "base_correction": base_manifest,
        "inventory_before": inventory_before,
        "production_brief_before": brief_before,
        "representations": PROMPTS,
        "provenance_policy": "stable source concept ID; append-only review history",
    }
    CORRECTION.mkdir(parents=True, exist_ok=True)
    (CORRECTION / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    append_jsonl(CAMPAIGN / "loop/events.jsonl", {
        "schema_version": "ninereeds_campaign35_word_image_loop_event_v1",
        "at": now(),
        "event": "lexeme_correction_applied",
        "correction_id": CORRECTION_ID,
        "source_concept_id": "knew",
        "teaching_term": "know",
        "manifest": str(CORRECTION / "manifest.json"),
    })
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
