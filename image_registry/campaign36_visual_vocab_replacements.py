"""Build the 611-word concrete replacement vocabulary for Campaign 36.

The ranked source is the archived frequency-sorted allowlist kernel.  DeepSeek only
adjudicates whether a candidate denotes a directly photographable physical entity in a
common beginner sense; it does not alter the curriculum or acquire images.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from typing import Any
import urllib.request

import inflect
from wordfreq import zipf_frequency

REPO = Path("/home/aomukai/Ninereeds")
CAMPAIGN = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1"
)
KERNEL = REPO / (
    "archive/workstation/cleanup-2026-08-06/training/corpus_admin/kernel/"
    "kernel_full_words.jsonl"
)
REQUIREMENTS = CAMPAIGN / "lexicon-revision-v1/corrected-manifest-v1/requirements.jsonl"
RESIDUAL = CAMPAIGN / (
    "lexicon-revision-v1/corrected-manifest-v1/reconciliation-final/"
    "residual-route-slots.json"
)
OUTPUT = REPO / (
    "config/mission_hub/campaign_material/campaign36/"
    "visual-vocabulary-replacement-v1"
)
SCHEMA_VERSION = "ninereeds_campaign36_visual_vocab_replacement_v1"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-flash"
ALLOWED_CATEGORIES = {
    "animals", "body", "clothing", "food", "household", "materials", "nature",
    "people", "places", "shapes", "technology", "tools", "unsorted",
}
HARDWARE = [
    ("CPU", "A central processing unit: the main processor chip installed in a computer."),
    ("GPU", "A graphics processing unit shown as a discrete graphics card used in a computer."),
    ("RAM", "Computer memory shown as removable RAM modules."),
    ("SSD", "A solid-state drive used for computer storage."),
    ("HDD", "A hard disk drive used for computer storage."),
    ("motherboard", "The main circuit board that holds and connects computer components."),
    ("power supply unit", "The internal computer component that supplies electrical power."),
    ("computer tower", "An upright desktop-computer case containing internal components."),
    ("laptop", "A portable computer with an attached screen and keyboard."),
    ("desktop computer", "A non-portable personal computer used at a desk."),
    ("monitor", "A standalone screen used to display a computer's visual output."),
]
REGISTRY_DB = REPO / "training_data/image_registry/registry.sqlite3"


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_jsonl(
    path: Path, *, tolerate_partial_tail: bool = False
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if tolerate_partial_tail and index == len(lines) - 1:
                break
            raise
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def command_inventory(_args: argparse.Namespace) -> int:
    requirements = load_jsonl(REQUIREMENTS)
    current = {normalized(str(row["word"])) for row in requirements}
    residual_document = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    residual_slots = residual_document["slots"]
    residual_concepts = {str(row["concept_id"]) for row in residual_slots}
    if len(residual_slots) != 6110 or len(residual_concepts) != 611:
        raise RuntimeError("residual replacement contract is not exactly 611 concepts")

    candidates = []
    for rank, row in enumerate(load_jsonl(KERNEL), 1):
        term = str(row["concept_id"]).strip()
        if row.get("kind") != "concrete_noun" or row.get("category") not in ALLOWED_CATEGORIES:
            continue
        if normalized(term) in current:
            continue
        candidates.append({
            "schema_version": SCHEMA_VERSION,
            "allowlist_rank": rank,
            "term": term,
            "normalized_term": normalized(term),
            "zipf_frequency": zipf_frequency(term, "en"),
            "legacy_category": row.get("category"),
            "legacy_kind": row.get("kind"),
            "source": str(KERNEL),
        })
    hardware = [
        {
            "schema_version": SCHEMA_VERSION,
            "term": term,
            "normalized_term": normalized(term),
            "teaching_sense": sense,
            "source": "user_reserved_hardware",
        }
        for term, sense in HARDWARE
    ]
    if len({row["normalized_term"] for row in hardware}) != 11:
        raise RuntimeError("hardware reserve is not eleven unique concepts")
    if {row["normalized_term"] for row in hardware} & current:
        raise RuntimeError("hardware reserve overlaps the current teaching vocabulary")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUTPUT / "ranked-candidate-pool.jsonl", candidates)
    write_jsonl(OUTPUT / "hardware-reserve.jsonl", hardware)
    write_json(OUTPUT / "inventory-summary.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "replacement_concepts": 611,
        "frequency_ranked_replacements": 600,
        "hardware_reserve": 11,
        "current_unique_terms": len(current),
        "ranked_candidate_pool": len(candidates),
        "allowed_legacy_categories": sorted(ALLOWED_CATEGORIES),
        "candidate_source": str(KERNEL),
    })
    print((OUTPUT / "inventory-summary.json").read_text(encoding="utf-8"), end="")
    return 0


def classifier_prompt(rows: list[dict[str, Any]]) -> str:
    return """You are auditing replacement vocabulary for an image-only beginner curriculum.

Accept a term only when one common everyday sense denotes a physical entity that can be shown
directly and unambiguously in a photograph or clean realistic illustration. Accept ordinary
objects, animals, plants, foods, body parts, garments, vehicles, tools, visibly distinct people,
rooms/buildings, and stable natural objects or places. Reject actions, events, sounds, media,
institutions, organizations, abstractions, properties, relations, collections with no stable
appearance, and terms whose intended physical sense is obscure or depends on a pun. Reject
malformed phrases and accidental corpus fragments. A role such as doctor may pass only if it has
a common concrete teaching scene; a broad word such as thing, matter, form, or material fails.

Keep the supplied term as canonical_term unless a short explicit physical sense phrase is needed
to avoid a common ambiguity (for example, wristwatch rather than watch). Do not make a rare term
look acceptable by inventing a niche sense. Return JSON only, with exactly one decision for every
candidate and no additional candidates:
{"decisions":[{"term":"exact input","decision":"accept|reject","canonical_term":"beginner term or empty","physical_class":"object|animal|plant|food|body_part|clothing|vehicle|tool|person|place|natural_object|other|none","teaching_sense":"one exact visible sense or empty","depiction":"one direct image realization or empty","reason":"brief evidence-based reason"}]}

CANDIDATES:
""" + json.dumps(rows, ensure_ascii=False, indent=2)


def request_deepseek(rows: list[dict[str, Any]], retries: int = 3) -> list[dict[str, Any]]:
    load_env(REPO / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not available")
    body = json.dumps({
        "model": DEEPSEEK_MODEL,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": classifier_prompt(rows)}],
    }).encode()
    expected = {row["term"] for row in rows}
    last: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                DEEPSEEK_ENDPOINT, data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(request, timeout=900) as response:
                payload = json.load(response)
            document = json.loads(payload["choices"][0]["message"]["content"])
            decisions = document.get("decisions")
            if not isinstance(decisions, list):
                raise ValueError("missing decisions list")
            returned = {str(row.get("term")) for row in decisions}
            if returned != expected or len(decisions) != len(rows):
                raise ValueError(
                    f"candidate coverage mismatch: expected={len(expected)} returned={len(returned)}"
                )
            return decisions
        except Exception as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"DeepSeek classification failed: {last}")


def request_deepseek_json(prompt: str, retries: int = 3) -> dict[str, Any]:
    load_env(REPO / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not available")
    body = json.dumps({
        "model": DEEPSEEK_MODEL,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    last: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                DEEPSEEK_ENDPOINT, data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(request, timeout=900) as response:
                payload = json.load(response)
            return json.loads(payload["choices"][0]["message"]["content"])
        except Exception as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"DeepSeek JSON request failed: {last}")


def singular_key(value: str) -> str:
    parts = normalized(value).split()
    if not parts:
        return ""
    singular = inflect.engine().singular_noun(parts[-1])
    if singular:
        parts[-1] = str(singular)
    return " ".join(parts)


def accepted_candidates() -> list[dict[str, Any]]:
    current = {normalized(str(row["word"])) for row in load_jsonl(REQUIREMENTS)}
    hardware = load_jsonl(OUTPUT / "hardware-reserve.jsonl")
    used = current | {row["normalized_term"] for row in hardware}
    accepted = []
    for row in sorted(
        load_jsonl(OUTPUT / "deepseek-decisions.jsonl"),
        key=lambda item: int(item["allowlist_rank"]),
    ):
        if row.get("decision") != "accept":
            continue
        canonical = str(row.get("canonical_term") or row["term"]).strip()
        key = normalized(canonical)
        if not key or key in used:
            continue
        accepted.append({**row, "candidate_term": canonical})
        used.add(key)
    return accepted


def command_audit(args: argparse.Namespace) -> int:
    current_rows = load_jsonl(REQUIREMENTS)
    current = [str(row["word"]) for row in current_rows]
    candidates = accepted_candidates()
    prompt = """Audit candidates for a beginner image-only vocabulary.

Return a removal only when one of these is true:
1. It denotes the same ordinary concept as an EXISTING term (including singular/plural or a
   plain synonym such as shop/store, bicycle/bike, adult/grown-up).
2. It denotes the same ordinary concept as an earlier, higher-frequency CANDIDATE. Keep the
   earlier candidate and remove the later one.
3. The named entity itself is not directly visible and recognizable in a still image. Context
   may support a visibly distinctive profession (firefighter, chef, doctor), but must not be the
   only evidence. Reject sounds, events, abstractions, relationships, institutions, inferred
   identities, malformed fragments, and materials with no teachable visible specimen.

Do not remove distinct related concepts: dog/puppy, chicken/hen/rooster, hand/finger, or
computer/laptop are distinct. Do not remove a physical plural-only noun merely because an
unrelated adjective shares its spelling (shorts is not the adjective short). Use each supplied
teaching sense to resolve ambiguity. Return JSON only:
{"remove":[{"term":"exact candidate_term","reason":"duplicate_existing|duplicate_candidate|not_directly_visible|malformed","duplicate_of":"term or empty","explanation":"brief"}]}

EXISTING TERMS:
""" + json.dumps(current, ensure_ascii=False) + "\n\nCANDIDATES IN FREQUENCY ORDER:\n" + json.dumps([
        {
            "candidate_term": row["candidate_term"],
            "teaching_sense": row.get("teaching_sense", ""),
            "physical_class": row.get("physical_class", ""),
        }
        for row in candidates
    ], ensure_ascii=False)
    raw_path = OUTPUT / "semantic-audit-raw.json"
    if args.reuse_raw:
        document = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        document = request_deepseek_json(prompt)
        write_json(raw_path, document)
    removals = document.get("remove")
    if not isinstance(removals, list):
        raise RuntimeError("semantic audit did not return a removal list")
    candidate_terms = {row["candidate_term"] for row in candidates}
    outside = sorted({
        str(row.get("term")) for row in removals
        if str(row.get("term")) not in candidate_terms
    })
    if outside:
        raise RuntimeError(
            "semantic audit returned terms outside the candidate pool: "
            + json.dumps(outside, ensure_ascii=False)
        )

    candidate_order = {
        row["candidate_term"]: index for index, row in enumerate(candidates)
    }
    current_normalized = {normalized(term) for term in current}
    supported_removals = []
    for row in removals:
        reason = row.get("reason")
        duplicate = str(row.get("duplicate_of") or "")
        if reason == "duplicate_existing" and normalized(duplicate) not in current_normalized:
            if (
                duplicate in candidate_order
                and candidate_order[duplicate] < candidate_order[row["term"]]
                and duplicate != row["term"]
            ):
                row = {**row, "reason": "duplicate_candidate"}
            else:
                continue
        elif reason == "duplicate_candidate" and not (
            duplicate in candidate_order
            and candidate_order[duplicate] < candidate_order[row["term"]]
        ):
            continue
        supported_removals.append(row)

    # Deterministic morphology catches obvious number variants even if the semantic audit misses.
    current_by_lemma = {singular_key(term): term for term in current}
    candidate_by_lemma: dict[str, str] = {}
    deterministic = []
    for row in candidates:
        term = row["candidate_term"]
        lemma = singular_key(term)
        if lemma in current_by_lemma and normalized(term) != normalized(current_by_lemma[lemma]):
            # Do not conflate the garment "shorts" with the adjective "short".
            if not (term == "shorts" and current_by_lemma[lemma] == "short"):
                deterministic.append({
                    "term": term,
                    "reason": "duplicate_existing",
                    "duplicate_of": current_by_lemma[lemma],
                    "explanation": "deterministic singular/plural collision",
                })
        elif lemma in candidate_by_lemma:
            deterministic.append({
                "term": term,
                "reason": "duplicate_candidate",
                "duplicate_of": candidate_by_lemma[lemma],
                "explanation": "deterministic singular/plural collision",
            })
        else:
            candidate_by_lemma[lemma] = term
    merged = {row["term"]: row for row in supported_removals}
    for row in deterministic:
        merged.setdefault(row["term"], row)
    result = {
        "schema_version": SCHEMA_VERSION,
        "audited_at": now(),
        "model": DEEPSEEK_MODEL,
        "candidate_count": len(candidates),
        "removal_count": len(merged),
        "removals": sorted(merged.values(), key=lambda row: row["term"]),
    }
    write_json(OUTPUT / "semantic-audit.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


def command_finalize_audited(_args: argparse.Namespace) -> int:
    candidates = accepted_candidates()
    audit = json.loads((OUTPUT / "semantic-audit.json").read_text(encoding="utf-8"))
    removed = {row["term"] for row in audit["removals"]}
    kept = [row for row in candidates if row["candidate_term"] not in removed]
    if len(kept) < 600:
        raise RuntimeError(f"only {len(kept)} audited frequency candidates remain")
    selected = []
    for row in kept[:600]:
        selected.append({
            "schema_version": SCHEMA_VERSION,
            "replacement_rank": len(selected) + 1,
            "selection_source": "frequency_ranked_allowlist_audited",
            "term": row["candidate_term"],
            "source_term": row["term"],
            "allowlist_rank": row["allowlist_rank"],
            "zipf_frequency": row["zipf_frequency"],
            "physical_class": row["physical_class"],
            "teaching_sense": row["teaching_sense"],
            "depiction": row["depiction"],
            "classification_model": row["model"],
        })
    hardware = load_jsonl(OUTPUT / "hardware-reserve.jsonl")
    final = selected + [
        {
            **row,
            "replacement_rank": 601 + index,
            "selection_source": "user_reserved_hardware",
            "physical_class": "computer_hardware",
            "depiction": row["teaching_sense"],
        }
        for index, row in enumerate(hardware)
    ]
    write_jsonl(OUTPUT / "audited-proposed-replacements.jsonl", final)
    (OUTPUT / "audited-proposed-replacements.txt").write_text(
        "".join(str(row["term"]) + "\n" for row in final),
        encoding="utf-8",
    )
    write_json(OUTPUT / "audited-proposal-summary.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "status": "audited_vocabulary_proposal_only",
        "replacement_terms": len(final),
        "frequency_ranked_terms": len(selected),
        "hardware_terms": len(hardware),
        "semantic_removals": len(removed),
        "audited_frequency_candidates_available": len(kept),
        "unique_normalized_terms": len({normalized(row["term"]) for row in final}),
        "images_acquired": 0,
        "lexicon_modified": False,
    })
    print((OUTPUT / "audited-proposal-summary.json").read_text(encoding="utf-8"), end="")
    return 0


def command_build_manifest(_args: argparse.Namespace) -> int:
    requirements = load_jsonl(REQUIREMENTS)
    residual_document = json.loads(RESIDUAL.read_text(encoding="utf-8"))
    residual_ids = {str(row["concept_id"]) for row in residual_document["slots"]}
    old_concepts = []
    seen = set()
    for row in requirements:
        concept_id = str(row["concept_id"])
        if concept_id in residual_ids and concept_id not in seen:
            old_concepts.append({
                "concept_id": concept_id,
                "word": str(row["word"]),
                "ordinal": int(row["ordinal"]),
                "teaching_sense": str(row.get("teaching_sense") or ""),
            })
            seen.add(concept_id)
    replacements = load_jsonl(OUTPUT / "audited-proposed-replacements.jsonl")
    if len(old_concepts) != 611 or len(replacements) != 611:
        raise RuntimeError("manifest replacement mapping is not 611-to-611")
    mapping = {}
    map_rows = []
    for old, new in zip(old_concepts, replacements, strict=True):
        mapping[old["concept_id"]] = new
        map_rows.append({
            "schema_version": SCHEMA_VERSION,
            "replacement_rank": new["replacement_rank"],
            "ordinal": old["ordinal"],
            "old_concept_id": old["concept_id"],
            "old_word": old["word"],
            "old_teaching_sense": old["teaching_sense"],
            "new_concept_id": new["term"],
            "new_word": new["term"],
            "new_teaching_sense": new["teaching_sense"],
            "selection_source": new["selection_source"],
        })
    revised = []
    replaced_slots = 0
    for row in requirements:
        new = mapping.get(str(row["concept_id"]))
        if new is None:
            revised.append(row)
            continue
        revised.append({
            **row,
            "concept_id": new["term"],
            "word": new["term"],
            "teaching_sense": new["teaching_sense"],
            "part_of_speech": "noun",
        })
        replaced_slots += 1
    if replaced_slots != 6110 or len(revised) != 25000:
        raise RuntimeError(
            f"unexpected revised manifest dimensions: slots={replaced_slots} rows={len(revised)}"
        )
    unique = {normalized(str(row["word"])) for row in revised}
    unique_ordinals = {int(row["ordinal"]) for row in revised}
    unique_concept_ids = {str(row["concept_id"]) for row in revised}
    if len(unique_ordinals) != 2500:
        raise RuntimeError(
            f"revised manifest has {len(unique_ordinals)} unique ordinals, not 2500"
        )
    write_jsonl(OUTPUT / "replacement-map.jsonl", map_rows)
    write_jsonl(OUTPUT / "revised-requirements.jsonl", revised)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "source_requirements": str(REQUIREMENTS),
        "source_residual_routes": str(RESIDUAL),
        "requirements_rows": len(revised),
        "unique_curriculum_ordinals": len(unique_ordinals),
        "unique_concept_ids": len(unique_concept_ids),
        "unique_surface_terms": len(unique),
        "inherited_concept_id_collisions": len(unique_ordinals) - len(unique_concept_ids),
        "inherited_polysemous_surface_collisions": len(unique_ordinals) - len(unique),
        "replaced_concepts": len(mapping),
        "replaced_slots": replaced_slots,
        "slots_per_replacement": 10,
        "images_acquired": 0,
    }
    write_json(OUTPUT / "revised-manifest-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


def command_registry_audit(args: argparse.Namespace) -> int:
    from image_registry.campaign35_word_images import (
        _candidates, _connect_read_only, _load_registry_index,
    )

    replacements = load_jsonl(OUTPUT / "audited-proposed-replacements.jsonl")
    replacement_map = {
        int(row["replacement_rank"]): row
        for row in load_jsonl(OUTPUT / "replacement-map.jsonl")
    }
    pools = []
    wishlist = []
    metadata_needs = []
    with _connect_read_only(args.db) as database:
        assets, inverted = _load_registry_index(database)
        for row in replacements:
            candidates = _candidates(
                assets, inverted, str(row["term"]), limit=args.candidates_per_term,
            )
            pool = {
                "schema_version": SCHEMA_VERSION,
                "replacement_rank": row["replacement_rank"],
                "term": row["term"],
                "teaching_sense": row["teaching_sense"],
                "required_images": 10,
                "candidate_count": len(candidates),
                "candidate_status": "retrieval_evidence_only_pending_semantic_review",
                "candidates": candidates,
            }
            pools.append(pool)
            if len(candidates) < 10:
                wishlist.append({
                    "schema_version": SCHEMA_VERSION,
                    "replacement_rank": row["replacement_rank"],
                    "term": row["term"],
                    "teaching_sense": row["teaching_sense"],
                    "required_images": 10,
                    "registry_candidates": len(candidates),
                    "raw_registry_gap": 10 - len(candidates),
                    "next_action": "semantic_review_then_external_metadata_search",
                })
                mapping = replacement_map[int(row["replacement_rank"])]
                ordinal = int(mapping["ordinal"])
                for exposure in range(len(candidates) + 1, 11):
                    metadata_needs.append({
                        "slot_id": f"c{ordinal:04d}-i{exposure:02d}",
                        "sequence_position": (ordinal - 1) * 10 + exposure,
                        "ordinal": ordinal,
                        "concept": row["term"],
                        "concept_id": row["term"],
                        "teaching_sense": row["teaching_sense"],
                        "word": row["term"],
                        "exposure_index": exposure,
                        "status": "preliminary_registry_gap_pending_semantic_review",
                    })
    write_jsonl(OUTPUT / "registry-candidate-pools.jsonl", pools)
    write_jsonl(OUTPUT / "registry-wishlist.jsonl", wishlist)
    write_jsonl(OUTPUT / "preliminary-metadata-needs.jsonl", metadata_needs)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "registry_db": str(args.db),
        "replacement_terms": len(replacements),
        "required_images": len(replacements) * 10,
        "raw_registry_candidate_slots": sum(min(10, row["candidate_count"]) for row in pools),
        "raw_registry_gap_slots": sum(max(0, 10 - row["candidate_count"]) for row in pools),
        "terms_with_at_least_ten_candidates": sum(row["candidate_count"] >= 10 for row in pools),
        "terms_with_raw_registry_gap": len(wishlist),
        "semantic_review_complete": False,
        "images_generated": 0,
    }
    write_json(OUTPUT / "registry-audit-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


def command_classify(args: argparse.Namespace) -> int:
    pool = load_jsonl(OUTPUT / "ranked-candidate-pool.jsonl")
    ledger = OUTPUT / "deepseek-decisions.jsonl"
    existing = {row["term"] for row in load_jsonl(ledger, tolerate_partial_tail=True)}
    pending = [row for row in pool if row["term"] not in existing]
    for offset in range(0, len(pending), args.batch_size):
        batch = pending[offset:offset + args.batch_size]
        decisions = request_deepseek(batch)
        source = {row["term"]: row for row in batch}
        for decision in decisions:
            term = str(decision["term"])
            append_jsonl(ledger, {
                "schema_version": SCHEMA_VERSION,
                "classified_at": now(),
                "model": DEEPSEEK_MODEL,
                **source[term],
                **decision,
            })
        print(json.dumps({
            "classified": min(offset + len(batch), len(pending)),
            "pending_at_start": len(pending),
            "total_pool": len(pool),
        }), flush=True)
    return 0


def command_finalize(_args: argparse.Namespace) -> int:
    decisions = load_jsonl(OUTPUT / "deepseek-decisions.jsonl")
    pool = load_jsonl(OUTPUT / "ranked-candidate-pool.jsonl")
    if len({row["term"] for row in decisions}) != len(pool):
        raise RuntimeError("classification ledger does not cover the complete candidate pool")
    current = {
        normalized(str(row["word"])) for row in load_jsonl(REQUIREMENTS)
    }
    hardware = load_jsonl(OUTPUT / "hardware-reserve.jsonl")
    reserved = {row["normalized_term"] for row in hardware}
    selected = []
    used = set(current) | reserved
    for row in sorted(decisions, key=lambda item: int(item["allowlist_rank"])):
        if row.get("decision") != "accept":
            continue
        canonical = str(row.get("canonical_term") or row["term"]).strip()
        key = normalized(canonical)
        if not key or key in used:
            continue
        selected.append({
            "schema_version": SCHEMA_VERSION,
            "replacement_rank": len(selected) + 1,
            "selection_source": "frequency_ranked_allowlist",
            "term": canonical,
            "source_term": row["term"],
            "allowlist_rank": row["allowlist_rank"],
            "zipf_frequency": row["zipf_frequency"],
            "physical_class": row["physical_class"],
            "teaching_sense": row["teaching_sense"],
            "depiction": row["depiction"],
            "classification_model": row["model"],
        })
        used.add(key)
        if len(selected) == 600:
            break
    if len(selected) != 600:
        raise RuntimeError(f"only {len(selected)} valid frequency-ranked replacements remain")
    final = selected + [
        {
            **row,
            "replacement_rank": 601 + index,
            "selection_source": "user_reserved_hardware",
            "physical_class": "computer_hardware",
            "depiction": row["teaching_sense"],
        }
        for index, row in enumerate(hardware)
    ]
    write_jsonl(OUTPUT / "proposed-replacements.jsonl", final)
    write_json(OUTPUT / "proposal-summary.json", {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "status": "vocabulary_proposal_only",
        "replacement_terms": len(final),
        "frequency_ranked_terms": len(selected),
        "hardware_terms": len(hardware),
        "unique_normalized_terms": len({normalized(row["term"]) for row in final}),
        "images_acquired": 0,
        "lexicon_modified": False,
    })
    print((OUTPUT / "proposal-summary.json").read_text(encoding="utf-8"), end="")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory = subparsers.add_parser("inventory")
    inventory.set_defaults(func=command_inventory)
    classify = subparsers.add_parser("classify")
    classify.add_argument("--batch-size", type=int, default=80)
    classify.set_defaults(func=command_classify)
    finalize = subparsers.add_parser("finalize")
    finalize.set_defaults(func=command_finalize)
    audit = subparsers.add_parser("audit")
    audit.add_argument("--reuse-raw", action="store_true")
    audit.set_defaults(func=command_audit)
    finalize_audited = subparsers.add_parser("finalize-audited")
    finalize_audited.set_defaults(func=command_finalize_audited)
    build_manifest = subparsers.add_parser("build-manifest")
    build_manifest.set_defaults(func=command_build_manifest)
    registry_audit = subparsers.add_parser("registry-audit")
    registry_audit.add_argument("--db", type=Path, default=REGISTRY_DB)
    registry_audit.add_argument("--candidates-per-term", type=int, default=30)
    registry_audit.set_defaults(func=command_registry_audit)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
