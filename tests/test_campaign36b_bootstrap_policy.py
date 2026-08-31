from __future__ import annotations

import json
from pathlib import Path

import torch

from meta.scripts.train_campaign36b_bootstrap import (
    MAX_CHECKPOINT_BYTES,
    append_jsonl,
    provisional_credit,
    prune_checkpoints,
    runtime_state,
)


def test_compact_journal_is_append_only(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    append_jsonl(path, {"event": 1})
    append_jsonl(path, {"event": 2}, durable=True)
    assert [json.loads(line) for line in path.read_text().splitlines()] == [
        {"event": 1},
        {"event": 2},
    ]


def test_checkpoint_retention_keeps_milestones_and_latest_two(tmp_path: Path) -> None:
    for index in range(12):
        (tmp_path / f"session-{index:02d}.pt").touch()
    removed = prune_checkpoints(tmp_path, 11)
    retained = {path.name for path in tmp_path.glob("*.pt")}
    assert retained == {
        "session-00.pt",
        "session-09.pt",
        "session-10.pt",
        "session-11.pt",
    }
    assert "session-08.pt" in removed


def test_runtime_state_is_tensor_only_and_checkpoint_ceiling_is_bounded() -> None:
    torch.manual_seed(36_002)
    state = runtime_state()
    assert state["cpu_rng_state"].dtype == torch.uint8
    assert MAX_CHECKPOINT_BYTES == 16 * 1024**3


def test_provisional_credit_is_positive_when_zero_ablation_would_raise_loss() -> None:
    cohort = torch.nn.Linear(2, 1, bias=False)
    with torch.no_grad():
        cohort.weight.fill_(2.0)
    cohort.weight.grad = torch.full_like(cohort.weight, -0.5)
    assert provisional_credit(cohort) == 2.0
