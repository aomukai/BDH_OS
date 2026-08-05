from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from cortex.siglip2 import BoundedVisualResampler, Siglip2ProjectorConfig


def test_visual_resampler_preserves_a_bounded_shape_and_gradients() -> None:
    config = Siglip2ProjectorConfig(
        receptor_width=12,
        cortex_width=8,
        observation_tokens=4,
        attention_heads=2,
    )
    resampler = BoundedVisualResampler(config)
    patches = torch.randn(2, 12, 12)
    mask = torch.tensor([[1] * 12, [1] * 6 + [0] * 6], dtype=torch.bool)
    shapes = torch.tensor([[3, 4], [2, 3]])

    observed, observed_mask = resampler(patches, mask, shapes)
    observed.square().mean().backward()

    assert observed.shape == (2, 4, 8)
    assert observed_mask.all()
    assert any(parameter.grad is not None for parameter in resampler.parameters())


def test_visual_positions_change_with_aspect_shape() -> None:
    tall = BoundedVisualResampler._positions(
        torch.tensor([[4, 2]]), 8, device=torch.device("cpu"), dtype=torch.float32
    )
    wide = BoundedVisualResampler._positions(
        torch.tensor([[2, 4]]), 8, device=torch.device("cpu"), dtype=torch.float32
    )

    assert not torch.equal(tall, wide)
