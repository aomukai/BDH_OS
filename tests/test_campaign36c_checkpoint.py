from __future__ import annotations

import pytest

torch = pytest.importorskip(
    "torch", reason="Campaign 36C checkpoint tests require the Cortex torch environment",
)

from campaign36c import (
    BDHCellConfig,
    CellOptimizerConfig,
    StandaloneBDHCell,
    build_cell_optimizer,
    load_cell_checkpoint,
    save_cell_checkpoint,
)


def test_cell_and_uid_local_optimizer_survive_cold_restore(tmp_path) -> None:
    torch.manual_seed(13)
    cell = StandaloneBDHCell(
        BDHCellConfig(width=8, rotary_pairs=2, initialization_seed=17),
        uid=91,
    )
    policy = CellOptimizerConfig(learning_rate=0.01)
    optimizer = build_cell_optimizer(cell.parameters(), policy)
    state = torch.randn(3, 4, 8)
    target = torch.randn(3, 4, 8)
    optimizer.zero_grad(set_to_none=True)
    torch.nn.functional.mse_loss(cell(state), target).backward()
    optimizer.step()
    expected = cell(state).detach()

    path = tmp_path / "cell.pt"
    telemetry = save_cell_checkpoint(
        path,
        cell,
        optimizer,
        optimizer_config=policy,
        metadata={"evidence": "test"},
    )
    restored, restored_optimizer, restored_policy, metadata = load_cell_checkpoint(path)

    assert restored.uid == 91
    assert restored_policy == policy
    assert metadata == {"evidence": "test"}
    assert telemetry["optimizer_tensor_bytes"] > 0
    assert not list(tmp_path.glob(".*.tmp"))
    torch.testing.assert_close(expected, restored(state), rtol=0, atol=0)

    for model, model_optimizer in (
        (cell, optimizer),
        (restored, restored_optimizer),
    ):
        model_optimizer.zero_grad(set_to_none=True)
        torch.nn.functional.mse_loss(model(state), target).backward()
        model_optimizer.step()
    for source, resumed in zip(cell.parameters(), restored.parameters(), strict=True):
        torch.testing.assert_close(source, resumed, rtol=0, atol=0)
