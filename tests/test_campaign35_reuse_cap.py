import json

from image_registry.campaign35_reuse_cap import enforce_reuse_cap


def test_reuse_cap_prioritizes_scarcity_and_is_deterministic(tmp_path):
    rows = []
    for position in range(1, 25_001):
        ordinal = position
        row = {
            "slot_id": f"s{position}", "sequence_position": position,
            "ordinal": ordinal, "word": f"word-{ordinal}",
            "disposition": "target_not_visible",
        }
        rows.append(row)
    for index in range(6):
        rows[index].update({
            "asset_id": 1, "disposition": "accepted",
            "literal_caption": f"A word-{index + 1} is visible.",
        })
    # Give ordinal 1 a second accepted asset, making it less scarce than the others.
    rows[6].update({
        "asset_id": 2, "disposition": "accepted", "ordinal": 1,
        "word": "word-1", "literal_caption": "A word-1 is visible.",
    })
    source = tmp_path / "decisions.jsonl"
    source.write_text("".join(json.dumps(row) + "\n" for row in rows))
    output = tmp_path / "out"
    summary = enforce_reuse_cap(source, output, max_uses=4)
    decisions = [json.loads(line) for line in (output / "decisions.jsonl").read_text().splitlines()]
    kept = [row["slot_id"] for row in decisions if row.get("asset_id") == 1 and row["disposition"] == "accepted"]
    assert len(kept) == 4
    assert "s1" not in kept
    assert summary["demoted_over_cap_slots"] == 2
    assert summary["max_uses_after"] == 4
    first = (output / "decisions.jsonl").read_bytes()
    enforce_reuse_cap(source, output, max_uses=4)
    assert (output / "decisions.jsonl").read_bytes() == first
