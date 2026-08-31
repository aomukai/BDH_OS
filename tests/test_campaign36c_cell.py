from __future__ import annotations

import pytest

torch = pytest.importorskip(
    "torch", reason="Campaign 36C cell tests require the Cortex torch environment",
)

from campaign36c import (
    BDHCellConfig,
    LowRankResidualControl,
    MaskedDenseBDHHeadControl,
    MaskedLocalBDHHeadControl,
    StandaloneBDHCell,
    batch_composition_max_difference,
    compare_masked_dense_cohort,
    paired_rotary_frequencies,
)
from bdh import BDH, BDHConfig


def test_rotary_pairs_are_the_mechanical_parameter_atom() -> None:
    frequencies = paired_rotary_frequencies(8, theta=float(2**16))
    torch.testing.assert_close(frequencies[::2], frequencies[1::2])

    cell = StandaloneBDHCell(
        BDHCellConfig(width=12, rotary_pairs=3),
        uid=41,
    )
    assert cell.config.gate_width == 6
    assert cell.parameter_count == 6 * 12 * 3
    assert cell.storage_telemetry()["uid"] == 41


def test_cell_is_batch_invariant_and_does_not_modify_padding() -> None:
    torch.manual_seed(7)
    cell = StandaloneBDHCell(
        BDHCellConfig(width=8, rotary_pairs=2),
        uid=2,
    ).eval()
    state = torch.randn(3, 5, 8)
    mask = torch.tensor([
        [1, 1, 1, 1, 1],
        [1, 1, 1, 0, 0],
        [1, 1, 1, 1, 0],
    ])

    output = cell(state, mask)

    assert batch_composition_max_difference(cell, state, mask) == 0
    torch.testing.assert_close(output[1, 3:], state[1, 3:], rtol=0, atol=0)
    torch.testing.assert_close(output[2, 4:], state[2, 4:], rtol=0, atol=0)


def test_masked_dense_cohort_matches_independent_cell_and_gradients() -> None:
    torch.manual_seed(11)
    cell = StandaloneBDHCell(
        BDHCellConfig(width=8, rotary_pairs=2),
        uid=3,
    )
    control = MaskedLocalBDHHeadControl.containing_cell(
        cell,
        prefix_pairs=2,
        suffix_pairs=3,
    )
    comparison = compare_masked_dense_cohort(
        control,
        torch.randn(2, 5, 8),
    )

    assert comparison.maximum_difference <= 1e-9


def test_current_dense_bdh_semantics_are_measured_as_an_architectural_delta() -> None:
    cell = StandaloneBDHCell(
        BDHCellConfig(width=8, rotary_pairs=2),
        uid=5,
    )
    dense_reference = MaskedDenseBDHHeadControl.containing_cell(cell)
    comparison = compare_masked_dense_cohort(
        dense_reference,
        torch.randn(2, 5, 8),
    )

    assert comparison.output_max_abs > 0
    assert comparison.maximum_difference > 0


def test_dense_reference_control_matches_the_current_bdh_layer() -> None:
    control = MaskedDenseBDHHeadControl(
        width=8,
        rotary_pairs=4,
        active_pair_start=0,
        active_pair_count=4,
    ).eval()
    reference = BDH(BDHConfig(
        n_layer=1,
        n_embd=8,
        n_head=1,
        mlp_internal_dim_multiplier=1,
        vocab_size=16,
        dropout=0,
    )).eval()
    with torch.no_grad():
        reference.encoder.copy_(control.encoder.unsqueeze(0))
        reference.encoder_v.copy_(control.value_encoder.unsqueeze(0))
        reference.decoder.copy_(control.decoder)
    state = torch.randn(2, 5, 8)

    expected = reference.encode_embeds(state)
    observed = control(state)

    torch.testing.assert_close(observed, expected, rtol=0, atol=0)


def test_parameter_nearest_control_uses_the_closest_valid_rank() -> None:
    width = 512
    cell = StandaloneBDHCell(
        BDHCellConfig(width=width, rotary_pairs=1),
        uid=4,
    )
    control = LowRankResidualControl.for_parameter_budget(
        width=width,
        budget=cell.parameter_count,
    )
    alternatives = {
        rank: abs(
            LowRankResidualControl.parameter_count_for(width=width, rank=rank)
            - cell.parameter_count
        )
        for rank in range(1, width + 1)
    }

    assert alternatives[control.rank] == min(alternatives.values())


def test_cell_rejects_invalid_shapes_and_uids() -> None:
    with pytest.raises(ValueError, match="uid"):
        StandaloneBDHCell(BDHCellConfig(width=8), uid=-1)
    cell = StandaloneBDHCell(BDHCellConfig(width=8), uid=1)
    with pytest.raises(ValueError, match="shape"):
        cell(torch.randn(2, 8))
    with pytest.raises(ValueError, match="attention_mask"):
        cell(torch.randn(2, 3, 8), torch.ones(2, 2))
