from __future__ import annotations

import json

import pytest

from training.pipeline.visual.foundation import FoundationPlanError, build_plan, validate_plan


def _words(tmp_path):
    path = tmp_path / "words.jsonl"
    path.write_text(
        "\n".join(
            json.dumps({"concept_id": word, "category": category, "kind": kind, "source": "allowlist"})
            for word, category, kind in [
                ("dog", "animals", "concrete_noun"),
                ("apple", "food", "concrete_noun"),
                ("happy", "emotions", "abstract"),
            ]
        ) + "\n",
        encoding="utf-8",
    )
    return path


def test_build_plan_is_foundation_anchored_and_deterministic(tmp_path) -> None:
    plan = build_plan(
        words_path=_words(tmp_path), pack_id="probe-v1", concepts=["dog", "apple"],
        images_per_concept=2, seed=10,
    )
    validate_plan(plan)
    assert [item["canonical_caption"] for item in plan["items"]] == ["a dog", "a dog", "an apple", "an apple"]
    assert [item["seed"] for item in plan["items"]] == [10, 11, 12, 13]
    assert plan["scope"]["target_image_count"] == 4


def test_first_pack_rejects_non_concrete_and_unknown_words(tmp_path) -> None:
    with pytest.raises(FoundationPlanError, match="concrete nouns"):
        build_plan(words_path=_words(tmp_path), pack_id="probe-v1", concepts=["happy"], images_per_concept=1, seed=1)
    with pytest.raises(FoundationPlanError, match="absent"):
        build_plan(words_path=_words(tmp_path), pack_id="probe-v1", concepts=["cat"], images_per_concept=1, seed=1)
