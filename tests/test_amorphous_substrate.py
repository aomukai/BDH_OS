from __future__ import annotations

import pytest

torch = pytest.importorskip(
    "torch", reason="Amorphous substrate tests require the Cortex torch environment",
)

from amorphous import (
    AmorphousSubstrate,
    CellSubstrateConfig,
    GrowthController,
    GrowthObservation,
    GrowthPolicyConfig,
)


def small_config(**overrides) -> CellSubstrateConfig:
    values = {
        "width": 8,
        "rank": 4,
        "seed_cells": 3,
        "birth_cohort_size": 2,
        "propagation_steps": 2,
        "initialization_seed": 19,
        "max_cells": 32,
    }
    values.update(overrides)
    return CellSubstrateConfig(**values)


def observation(index: int, *, residual: float = 1.0) -> GrowthObservation:
    return GrowthObservation(
        internal_residual=residual,
        externally_verified_failure=True,
        capacity_saturated=True,
        event_id=f"event-{index}",
    )


def test_seed_population_is_real_allocated_parameters() -> None:
    substrate = AmorphousSubstrate(small_config())
    per_cell = 8 * 4 + 4 * 8 + 8 + 4

    assert substrate.anatomy() == {
        "allocated_cells": 3,
        "allocated_cell_parameters": 3 * per_cell,
        "admitted_cells": 3,
        "dormant_cells": 0,
        "provisional_cells": 0,
        "admitted_cell_parameters": 3 * per_cell,
        "dormant_cell_parameters": 0,
        "provisional_cell_parameters": 0,
    }


def test_forward_is_deterministic_and_traced() -> None:
    first = AmorphousSubstrate(small_config()).eval()
    second = AmorphousSubstrate(small_config()).eval()
    values = torch.randn(2, 5, 8)
    mask = torch.tensor([[1, 1, 1, 0, 0], [1, 1, 1, 1, 1]])

    output, trace = first(values, mask, collect_trace=True)
    repeated = second(values, mask)

    assert output.shape == values.shape
    torch.testing.assert_close(output, repeated, rtol=0, atol=0)
    assert trace["propagation_steps"] == 2
    assert trace["steps"][0]["cell_ids"] == [0, 1, 2]
    assert len(trace["steps"][0]["mean_gate_by_cell"]) == 3


def test_growth_requires_persistent_grounded_saturation_and_updates_optimizer() -> None:
    substrate = AmorphousSubstrate(small_config())
    controller = GrowthController(GrowthPolicyConfig(
        residual_threshold=0.5,
        qualifying_observations=2,
        cooldown_observations=1,
    ))
    optimizer = torch.optim.Adam(substrate.trainable_parameters(), lr=1e-3)
    initial_groups = len(optimizer.param_groups)

    assert substrate.consider_growth(
        controller, observation(1), optimizer=optimizer,
    ) is None
    cohort_index = substrate.consider_growth(
        controller, observation(2), optimizer=optimizer,
    )

    assert cohort_index == 1
    assert substrate.anatomy()["allocated_cells"] == 5
    assert substrate.anatomy()["provisional_cells"] == 2
    assert len(optimizer.param_groups) == initial_groups + 1


def test_growth_rejects_internal_residual_without_organism_level_evidence() -> None:
    controller = GrowthController(GrowthPolicyConfig(qualifying_observations=1))
    assert controller.observe(GrowthObservation(
        internal_residual=10.0,
        externally_verified_failure=False,
        capacity_saturated=True,
        event_id="ungrounded",
    )) is False


def test_cohort_lifecycle_and_checkpoint_round_trip() -> None:
    substrate = AmorphousSubstrate(small_config())
    controller = GrowthController(GrowthPolicyConfig(qualifying_observations=1))
    new_index = substrate.consider_growth(controller, observation(1))
    assert new_index == 1
    substrate.set_cohort_status(new_index, "admitted")
    substrate.set_cohort_status(0, "dormant")
    with torch.no_grad():
        substrate.cohorts[new_index].egress.normal_(std=0.01)

    values = torch.randn(1, 4, 8)
    expected = substrate(values)
    restored, restored_controller = AmorphousSubstrate.from_checkpoint(
        substrate.checkpoint(growth_controller=controller, metadata={"track": "36B"})
    )

    torch.testing.assert_close(expected, restored(values), rtol=0, atol=0)
    assert restored.anatomy() == substrate.anatomy()
    assert restored.cohorts[0].status == "dormant"
    assert restored_controller is not None
    assert restored_controller.birth_count == 1
    assert restored_controller.last_event_id == "event-1"


def test_cell_population_learns_a_small_latent_residual() -> None:
    torch.manual_seed(5)
    substrate = AmorphousSubstrate(small_config(
        seed_cells=6,
        propagation_steps=1,
        residual_scale=0.5,
    ))
    values = torch.randn(12, 3, 8)
    direction = torch.randn(8, 8) * 0.1
    target = torch.nn.functional.layer_norm(
        values + torch.tanh(values @ direction), (8,)
    )
    optimizer = torch.optim.Adam(substrate.parameters(), lr=0.03)

    with torch.no_grad():
        initial = torch.nn.functional.mse_loss(substrate(values), target).item()
    for _ in range(80):
        optimizer.zero_grad(set_to_none=True)
        loss = torch.nn.functional.mse_loss(substrate(values), target)
        loss.backward()
        optimizer.step()
    final = torch.nn.functional.mse_loss(substrate(values), target).item()

    assert final < initial * 0.5
