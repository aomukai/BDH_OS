import json

from image_registry.campaign35_word_yield import analyze


def _jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")


def test_consistent_low_performer_leaves_external_search(tmp_path):
    root = tmp_path / "loop"
    for round_number in (1, 2):
        _jsonl(root / f"round-{round_number:04d}/semantic-decisions/decisions.jsonl", [
            {
                "slot_id": f"dog-{round_number}-{index}", "word": "dog",
                "concept": "dog", "concept_id": "dog",
                "asset_id": round_number * 100 + index, "source": "source-a",
                "disposition": "target_not_visible",
            }
            for index in range(4)
        ])
    authoritative = tmp_path / "authoritative.jsonl"
    _jsonl(authoritative, [
        {"slot_id": "dog-final", "word": "dog", "concept": "dog", "concept_id": "dog",
         "sequence_position": 1,
         "disposition": "missing_candidate"},
        {"slot_id": "cat-final", "word": "cat", "concept": "cat", "concept_id": "cat",
         "sequence_position": 2,
         "disposition": "missing_candidate"},
    ])

    summary = analyze(root, authoritative, tmp_path / "out")

    assert summary["low_yield_words"] == 1
    assert summary["specialist_slots"] == 1
    specialist = [json.loads(line) for line in (tmp_path / "out/specialist-needs.jsonl").read_text().splitlines()]
    external = [json.loads(line) for line in (tmp_path / "out/external-needs.jsonl").read_text().splitlines()]
    assert [row["word"] for row in specialist] == ["dog"]
    assert [row["word"] for row in external] == ["cat"]


def test_duplicate_surface_words_are_routed_by_concept(tmp_path):
    root = tmp_path / "loop"
    for round_number in (1, 2):
        _jsonl(root / f"round-{round_number:04d}/semantic-decisions/decisions.jsonl", [
            {
                "slot_id": f"kind-a-{round_number}-{index}", "word": "kind",
                "concept": "kind", "concept_id": "kind", "asset_id": index,
                "source": "source-a", "disposition": "target_not_visible",
            }
            for index in range(4)
        ] + [{
            "slot_id": f"kind-b-{round_number}", "word": "kind",
            "concept": "kind 2", "concept_id": "kind_2", "asset_id": 100 + round_number,
            "source": "source-a", "disposition": "accepted",
        }])
    authoritative = tmp_path / "authoritative.jsonl"
    _jsonl(authoritative, [
        {"slot_id": "kind-a", "word": "kind", "concept": "kind", "concept_id": "kind",
         "sequence_position": 1, "disposition": "missing_candidate"},
        {"slot_id": "kind-b", "word": "kind", "concept": "kind 2", "concept_id": "kind_2",
         "sequence_position": 2, "disposition": "missing_candidate"},
    ])

    summary = analyze(root, authoritative, tmp_path / "out")

    assert summary["low_yield_concepts"] == 1
    specialist = [json.loads(line) for line in (tmp_path / "out/specialist-needs.jsonl").read_text().splitlines()]
    external = [json.loads(line) for line in (tmp_path / "out/external-needs.jsonl").read_text().splitlines()]
    assert [row["concept_id"] for row in specialist] == ["kind"]
    assert [row["concept_id"] for row in external] == ["kind_2"]
