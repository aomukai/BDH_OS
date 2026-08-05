"""Contracts for the first foundation-aligned visual bootstrap pack."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


FOUNDATION_PACK_SCHEMA = "ninereeds_foundational_visual_plan_v1"
DEFAULT_CONCEPTS = (
    "house", "car", "book", "water", "head", "hand", "food", "room",
    "girl", "woman", "saw", "watch", "phone", "board", "cup", "dog",
    "table", "ball", "fish", "tree", "square", "cat", "apple", "chair",
)
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")


class FoundationPlanError(ValueError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_foundation_words(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows or any(not isinstance(row.get("concept_id"), str) for row in rows):
        raise FoundationPlanError("foundation word corpus is empty or malformed")
    return rows


def article_for(concept: str) -> str:
    return "an" if concept[:1].casefold() in "aeiou" else "a"


def concept_prompt(concept: str, attempt: int) -> str:
    viewpoints = (
        "eye-level three-quarter view",
        "eye-level front view",
        "eye-level side view",
        "slightly elevated three-quarter view",
    )
    return (
        f"Natural educational photograph of exactly one {concept}, with the {concept} as the "
        f"single clear primary subject. {viewpoints[attempt % len(viewpoints)]}. The complete "
        "subject is prominent, sharply focused, and easy for a young learner to recognize. "
        "Simple realistic setting, soft daylight, restrained colors, uncluttered composition. "
        "No people unless the requested subject is a person or body part; no duplicate primary "
        "subject, labels, writing, logo, border, or watermark."
    )


def build_plan(
    *,
    words_path: Path,
    pack_id: str,
    concepts: list[str],
    images_per_concept: int,
    seed: int,
) -> dict[str, Any]:
    if not SAFE_ID.fullmatch(pack_id):
        raise FoundationPlanError("pack_id must be a safe lowercase identifier")
    if not 1 <= images_per_concept <= 16:
        raise FoundationPlanError("images_per_concept must be in 1..16")
    if len(concepts) != len(set(concepts)) or not concepts:
        raise FoundationPlanError("concepts must be a non-empty unique list")
    rows = load_foundation_words(words_path)
    indexed = {row["concept_id"]: (rank, row) for rank, row in enumerate(rows, 1)}
    missing = sorted(set(concepts) - set(indexed))
    if missing:
        raise FoundationPlanError("concepts absent from foundation: " + ", ".join(missing))
    items = []
    for concept in concepts:
        rank, row = indexed[concept]
        if row.get("kind") != "concrete_noun":
            raise FoundationPlanError(f"first object pack requires concrete nouns: {concept}")
        for image_index in range(images_per_concept):
            item_seed = seed + len(items)
            items.append(
                {
                    "item_id": f"{concept}_{image_index + 1:02d}",
                    "concept_id": concept,
                    "canonical_caption": f"{article_for(concept)} {concept}",
                    "foundation_rank": rank,
                    "category": row["category"],
                    "source": row["source"],
                    "split": "train",
                    "reuse_query": f'"{article_for(concept)} {concept}"',
                    "prompt": concept_prompt(concept, image_index),
                    "seed": item_seed,
                    "status": "pending",
                }
            )
    return {
        "schema_version": FOUNDATION_PACK_SCHEMA,
        "pack_id": pack_id,
        "status": "planned",
        "foundation_source": str(words_path),
        "foundation_source_sha256": file_sha256(words_path),
        "scope": {
            "stage": "stage_1_concrete_object_alignment",
            "concept_count": len(concepts),
            "images_per_concept": images_per_concept,
            "target_image_count": len(items),
            "excluded_semantics": ["abstract", "verb", "adjective", "relation", "story_continuity"],
        },
        "generation": {
            "backend": "black-forest-labs/FLUX.2-klein-4B",
            "width": 512,
            "height": 384,
            "steps": 4,
            "guidance_scale": 1.0,
            "max_generation_attempts_per_item": 2,
        },
        "validation": {
            "blind_observer": "google/gemma-4-E2B-it",
            "policy_assistant": "deepseek-v4-flash",
            "policy_assistant_authority": "proposal_only",
            "final_reviewer": "sol",
            "independent_eval_required": True,
        },
        "items": items,
    }


def validate_plan(value: dict[str, Any]) -> None:
    if value.get("schema_version") != FOUNDATION_PACK_SCHEMA:
        raise FoundationPlanError("unsupported foundation visual plan schema")
    scope = value.get("scope") or {}
    items = value.get("items")
    if not isinstance(items, list) or len(items) != scope.get("target_image_count"):
        raise FoundationPlanError("plan item count does not match scope")
    ids = [item.get("item_id") for item in items]
    if len(ids) != len(set(ids)) or any(not isinstance(item_id, str) for item_id in ids):
        raise FoundationPlanError("plan item IDs must be unique strings")
    for item in items:
        if set(item) != {
            "item_id", "concept_id", "canonical_caption", "foundation_rank", "category",
            "source", "split", "reuse_query", "prompt", "seed", "status",
        }:
            raise FoundationPlanError("plan item fields do not match v1")
        if item["status"] != "pending" or item["split"] != "train":
            raise FoundationPlanError("new plan items must be pending train items")
