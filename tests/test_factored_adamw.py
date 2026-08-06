from __future__ import annotations

import pytest

torch = pytest.importorskip(
    "torch", reason="Cortex tests run in the isolated ninereeds-cortex environment",
)

from training.optim import FactoredAdamW


def test_factored_adamw_reduces_quadratic_and_factors_second_moment() -> None:
    parameter = torch.nn.Parameter(torch.full((32, 64), 2.0))
    optimizer = FactoredAdamW([parameter], lr=0.05)
    before = float(parameter.square().mean().detach())
    parameter.square().mean().backward()
    optimizer.step()

    assert float(parameter.square().mean().detach()) < before
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


def test_resume_preserves_fp32_optimizer_state_for_bf16_parameters() -> None:
    source = torch.nn.Parameter(torch.ones(32, 64, dtype=torch.bfloat16))
    optimizer = FactoredAdamW([source], lr=1e-3)
    source.grad = torch.ones_like(source)
    optimizer.step()

    target = torch.nn.Parameter(torch.ones(32, 64, dtype=torch.bfloat16))
    resumed = FactoredAdamW([target], lr=1e-3)
    resumed.load_state_dict(optimizer.state_dict())

    floating = [
        value
        for value in resumed.state[target].values()
        if isinstance(value, torch.Tensor) and value.is_floating_point()
    ]
    assert floating
    assert all(value.dtype == torch.float32 for value in floating)


def test_resume_can_preserve_newly_commissioned_hyperparameters() -> None:
    source = torch.nn.Parameter(torch.ones(4, dtype=torch.bfloat16))
    original = FactoredAdamW(
        [source],
        lr=1e-5,
        rms_clip=None,
        stochastic_rounding=False,
    )
    source.grad = torch.ones_like(source)
    original.step()

    target = torch.nn.Parameter(torch.ones(4, dtype=torch.bfloat16))
    revised = FactoredAdamW(
        [target],
        lr=3e-6,
        rms_clip=1.0,
        stochastic_rounding=True,
    )
    revised.load_state_dict(
        original.state_dict(),
        preserve_current_hyperparameters=True,
    )

    group = revised.param_groups[0]
    assert group["lr"] == 3e-6
    assert group["rms_clip"] == 1.0
    assert group["stochastic_rounding"] is True
    assert revised.state[target]["step"] == 1
