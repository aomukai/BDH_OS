from collections import Counter

from image_registry.campaign36_replacement_reconcile import candidate_identity, choose_candidates


def candidate(word, digest, rank=1):
    return {
        "word": word,
        "sha256": digest,
        "asset_id": int(digest[-2:], 16),
        "candidate_pool": "local_registry",
        "slot_id": f"{word}-{digest}",
        "candidate_rank": rank,
        "literal_caption": f"A visible {word}.",
        "source_caption": f"A visible {word}.",
        "target_evidence": f"The {word} is visible.",
        "quality_flags": [],
    }


def test_min_cost_flow_preserves_scarce_word_and_baseline_capacity():
    shared = "a" * 62 + "01"
    common_only = "b" * 62 + "02"
    rows = [
        candidate("scarce", shared),
        candidate("common", shared),
        candidate("common", common_only, rank=2),
    ]
    selected, maximum = choose_candidates(
        rows,
        words=["common", "scarce"],
        baseline_uses=Counter({shared: 3}),
        quota=1,
        reuse_cap=4,
    )
    assert maximum == 2
    assert {(row["word"], row["sha256"]) for row in selected} == {
        ("scarce", shared),
        ("common", common_only),
    }


def test_baseline_asset_at_cap_is_never_selected():
    capped = "c" * 62 + "03"
    free = "d" * 62 + "04"
    selected, maximum = choose_candidates(
        [candidate("dog", capped), candidate("dog", free, rank=2)],
        words=["dog"],
        baseline_uses=Counter({capped: 4}),
        quota=1,
        reuse_cap=4,
    )
    assert maximum == 1
    assert selected[0]["sha256"] == free


def test_generated_candidate_identity_does_not_require_retrieval_slot():
    digest = "a" * 64
    assert candidate_identity({
        "candidate_pool": "generated_imagegen",
        "word": "dog",
        "sha256": digest,
        "asset_id": 42,
    }) == ("generated_imagegen", f"generated:dog:{digest}")
