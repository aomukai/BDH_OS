from __future__ import annotations

import torch

from training.optim import FactoredAdamW


def test_factored_adamw_reduces_quadratic_and_factors_second_moment() -> None:
    parameter = torch.nn.Parameter(torch.full((32, 64), 2.0))
    optimizer = FactoredAdamW([parameter], lr=0.05)
    before = float(parameter.square().mean().detach())
    parameter.square().mean().backward()
    optimizer.step()

    assert float(parameter.square().mean()) < before
    state = optimizer.state[parameter]
    assert state["factored"] is True
    assert state["exp_avg_sq_row"].shape == (32,)
    assert state["exp_avg_sq_col"].shape == (64,)
    full_adam_state_bytes = parameter.numel() * 4 * 2
    assert optimizer.state_bytes() < full_adam_state_bytes


def test_factored_adamw_policy_keeps_features_independent() -> None:
    parameter = torch.nn.Parameter(torch.ones(4))
    optimizer = FactoredAdamW(
        [parameter],
        momentum=False,
        rms_clip=1.0,
        stochastic_rounding=True,
    )
    policy = optimizer.policy()
    assert policy["momentum"] is False
    assert policy["rms_clip"] == 1.0
    assert policy["stochastic_rounding"] is True
