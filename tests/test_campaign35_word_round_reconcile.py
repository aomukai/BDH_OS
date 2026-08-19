import json

import pytest

from image_registry.campaign35_word_round_reconcile import reconcile


def _write(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _ledgers(tmp_path):
    prior = []
    current = []
    for position in range(1, 25_001):
        slot = f"s{position}"
        prior.append({
            "slot_id": slot, "sequence_position": position,
            "disposition": "accepted" if position == 1 else "target_not_visible",
        })
        current.append({
            "slot_id": slot, "sequence_position": position,
            "disposition": "accepted" if position == 2 else "missing_candidate",
        })
    prior_path = tmp_path / "prior.jsonl"
    round_path = tmp_path / "round.jsonl"
    _write(prior_path, prior)
    _write(round_path, current)
    return prior_path, round_path


def test_reconcile_protects_prior_and_folds_round_acceptance(tmp_path):
    prior, current = _ledgers(tmp_path)
    summary = reconcile(prior, current, tmp_path / "out")
    assert summary["accepted_slots"] == 2
    assert summary["accepted_from_follow_up_round"] == 1
    assert summary["residual_slots"] == 24_998
    assert summary["exact_partition"] is True


def test_reconcile_rejects_overwriting_prior_acceptance(tmp_path):
    prior, current = _ledgers(tmp_path)
    rows = [json.loads(line) for line in current.read_text().splitlines()]
    rows[0]["disposition"] = "target_not_visible"
    _write(current, rows)
    with pytest.raises(ValueError, match="overwrite accepted"):
        reconcile(prior, current, tmp_path / "out")
