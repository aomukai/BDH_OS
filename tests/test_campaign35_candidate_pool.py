import json

from image_registry.campaign35_candidate_pool import export, virtualize


def test_virtualize_allows_two_candidates_for_one_target_slot(tmp_path):
    source = tmp_path / "candidates.jsonl"
    base = {
        "slot_id": "dog:1", "word": "dog", "concept": "dog", "ordinal": 1,
        "exposure_index": 1, "sequence_position": 1,
        "source": "example", "caption": "a dog", "source_metadata": {},
    }
    source.write_text("".join(
        json.dumps({**base, "source_image_id": source_id}) + "\n"
        for source_id in ("a", "b")
    ), encoding="utf-8")
    output = tmp_path / "pool"

    summary = virtualize([source], output)

    rows = [json.loads(line) for line in (output / "candidates.jsonl").read_text().splitlines()]
    assert summary["candidate_claims"] == 2
    assert summary["target_slots"] == 1
    assert len({row["slot_id"] for row in rows}) == 2
    assert {row["target_slot_id"] for row in rows} == {"dog:1"}
    assert [row["sequence_position"] for row in rows] == [1, 2]


def test_export_selects_best_accepted_candidate_and_restores_real_slot(tmp_path, monkeypatch):
    requirements = tmp_path / "requirements.jsonl"
    requirement_rows = [{
        "slot_id": f"word:{index}", "word": "dog", "concept": "dog", "ordinal": 1,
        "exposure_index": index, "sequence_position": index,
    } for index in range(1, 25_001)]
    requirements.write_text(
        "".join(json.dumps(row) + "\n" for row in requirement_rows), encoding="utf-8"
    )
    candidate_map = tmp_path / "candidate-map.jsonl"
    candidates = [{
        **requirement_rows[0], "slot_id": f"virtual:{rank}",
        "sequence_position": rank, "target_slot_id": "word:1",
        "target_sequence_position": 1, "candidate_rank_for_slot": rank,
    } for rank in (1, 2)]
    candidate_map.write_text(
        "".join(json.dumps(row) + "\n" for row in candidates), encoding="utf-8"
    )

    def fake_classify(*args, **kwargs):
        return [
            {**candidates[0], "asset_id": 10, "disposition": "target_not_visible"},
            {**candidates[1], "asset_id": 11, "disposition": "accepted"},
        ]

    monkeypatch.setattr("image_registry.campaign35_candidate_pool.classify", fake_classify)
    output = tmp_path / "out"
    summary = export(tmp_path / "db.sqlite3", "queue", requirements, candidate_map, output)

    decisions = [json.loads(line) for line in (output / "decisions.jsonl").read_text().splitlines()]
    assert summary["accepted_target_slots"] == 1
    assert decisions[0]["slot_id"] == "word:1"
    assert decisions[0]["asset_id"] == 11
    assert decisions[0]["candidate_slot_id"] == "virtual:2"
    assert decisions[1]["disposition"] == "missing_candidate"
