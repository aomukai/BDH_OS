from __future__ import annotations

from dataclasses import replace

import pytest
import torch

from campaign36c import (
    BDHCellConfig,
    ReceptorConfig,
    SparseWaveConfig,
    SparseWaveSubstrate,
    StandaloneBDHCell,
    WaveCell,
    WaveLabConfig,
    WaveStatus,
    batched_cell_transform,
    merge_wave_lab_results,
    run_wave_laboratory,
)


WIDTH = 8
PAIRS = 2


def state() -> torch.Tensor:
    generator = torch.Generator().manual_seed(36_200)
    return torch.randn(1, 5, WIDTH, generator=generator)


def cell(uid: int, *, receptor: ReceptorConfig | None = None) -> WaveCell:
    transform = StandaloneBDHCell(
        BDHCellConfig(
            width=WIDTH,
            rotary_pairs=PAIRS,
            initialization_seed=36_100 + uid,
        ),
        uid=uid,
    )
    return WaveCell(
        transform,
        receptor_config=receptor,
        max_degree=8,
        max_fanout=4,
    )


def graph(
    uids: tuple[int, ...],
    edges: tuple[tuple[int, int], ...],
    *,
    config: SparseWaveConfig | None = None,
    tune: bool = True,
) -> SparseWaveSubstrate:
    substrate = SparseWaveSubstrate(
        config
        or SparseWaveConfig(
            initial_route_energy=32,
            max_degree=8,
            max_fanout=4,
            max_uid_activations=3,
        )
    )
    root = state()
    for uid in uids:
        member = cell(uid)
        if tune:
            member.receptor.tune_to(root)
        substrate.add_cell(member)
    for source, destination in edges:
        substrate.connect(source, destination)
    return substrate


def test_vectorized_active_cells_match_individual_outputs_and_gradients() -> None:
    members = [cell(1).transform, cell(2).transform, cell(3).transform]
    inactive = cell(99).transform
    generator = torch.Generator().manual_seed(36_201)
    inputs = torch.randn(3, 1, 5, WIDTH, generator=generator)

    individual_inputs = inputs.detach().clone().requires_grad_(True)
    individual_outputs = torch.stack(
        [member(individual_inputs[index]) for index, member in enumerate(members)]
    )
    individual_outputs.square().sum().backward()
    individual_input_grad = individual_inputs.grad.detach().clone()
    individual_parameter_grads = [
        tuple(parameter.grad.detach().clone() for parameter in member.parameters())
        for member in members
    ]

    for member in members:
        member.zero_grad(set_to_none=True)
    batch_inputs = inputs.detach().clone().requires_grad_(True)
    batch_outputs = batched_cell_transform(members, batch_inputs).state
    batch_outputs.square().sum().backward()

    torch.testing.assert_close(batch_outputs, individual_outputs, atol=1e-6, rtol=1e-5)
    torch.testing.assert_close(
        batch_inputs.grad, individual_input_grad, atol=1e-6, rtol=1e-5
    )
    for member, expected in zip(members, individual_parameter_grads):
        for parameter, expected_gradient in zip(member.parameters(), expected):
            torch.testing.assert_close(
                parameter.grad, expected_gradient, atol=1e-6, rtol=1e-5
            )
    assert all(parameter.grad is None for parameter in inactive.parameters())


def test_chain_reaches_natural_quiescence() -> None:
    substrate = graph((1, 2, 3), ((1, 2), (2, 3)))
    result = substrate.run_thought(state(), ingress_uids=1, collect_trace=True)

    assert result.status is WaveStatus.QUIESCENT
    assert result.telemetry["activation_sequence"] == [1, 2, 3]
    assert result.telemetry["full_transforms"] == 3
    assert result.telemetry["receptor_probes"] == 2
    assert result.telemetry["terminations"] == 1
    assert result.telemetry["energy_conservation_error"] == pytest.approx(0.0)
    assert substrate.ready_for_next_turn


def test_receptor_rejection_stops_before_destination_transform() -> None:
    substrate = graph((1, 2), ((1, 2),))
    with torch.no_grad():
        receptor = substrate.cells["2"].receptor
        pooled = receptor.content_prototype.detach().clone()
        receptor.content_prototype.copy_(-pooled)
        receptor.coverage_prototype.copy_(-pooled)
    substrate.cells["1"].ports[2] = replace(
        substrate.cells["1"].ports[2], route_familiarity=0.0
    )

    result = substrate.run_thought(state(), ingress_uids=1)

    assert result.telemetry["activation_sequence"] == [1]
    assert result.telemetry["full_transforms"] == 1
    assert result.telemetry["receptor_rejections"] == 1


def test_known_route_can_relay_without_full_transform() -> None:
    substrate = graph((1, 2), ((1, 2),))
    with torch.no_grad():
        receptor = substrate.cells["2"].receptor
        receptor.content_prototype.mul_(-1)
        receptor.coverage_prototype.mul_(-1)
    substrate.cells["1"].ports[2] = replace(
        substrate.cells["1"].ports[2], route_familiarity=1.0
    )

    result = substrate.run_thought(state(), ingress_uids=1, collect_trace=True)

    assert result.telemetry["activation_sequence"] == [1, 2]
    assert result.telemetry["full_transforms"] == 1
    assert result.telemetry["route_only_activations"] == 1
    assert result.trace[0]["offers"][0]["admission"] == "route_only"


def test_fork_converges_and_destination_executes_once() -> None:
    substrate = graph(
        (1, 2, 3, 4),
        ((1, 2), (1, 3), (2, 4), (3, 4)),
    )
    result = substrate.run_thought(state(), ingress_uids=1)

    assert result.status is WaveStatus.QUIESCENT
    assert result.telemetry["activation_sequence"] == [1, 2, 3, 4]
    assert result.telemetry["convergence_groups"] == 1
    assert result.telemetry["full_transforms"] == 4
    assert result.telemetry["transmissions"] == 4
    assert result.telemetry["energy_conservation_error"] == pytest.approx(0.0)


def test_immediate_reversal_is_forbidden() -> None:
    substrate = graph((1, 2), ((1, 2), (2, 1)))
    result = substrate.run_thought(state(), ingress_uids=1)

    assert result.telemetry["activation_sequence"] == [1, 2]
    assert result.status is WaveStatus.QUIESCENT


def test_longer_recurrence_is_legal_then_bounded() -> None:
    config = SparseWaveConfig(
        initial_route_energy=32,
        max_degree=8,
        max_fanout=4,
        max_uid_activations=2,
    )
    substrate = graph(
        (1, 2, 3),
        ((1, 2), (2, 3), (3, 1)),
        config=config,
    )
    result = substrate.run_thought(state(), ingress_uids=1)

    assert result.status is WaveStatus.QUIESCENT
    assert result.telemetry["activation_sequence"] == [1, 2, 3, 1, 2, 3]
    assert result.telemetry["recurrent_activations"] == 3
    assert result.telemetry["recurrence_suppressed"] == 1


def test_deterministic_replay_is_independent_of_port_insertion_order() -> None:
    edges = ((1, 2), (1, 3), (2, 4), (3, 4))
    forward = graph((1, 2, 3, 4), edges)
    reverse = graph((1, 2, 3, 4), tuple(reversed(edges)))

    first = forward.run_thought(state(), ingress_uids=1, collect_trace=True)
    second = reverse.run_thought(state(), ingress_uids=1, collect_trace=True)

    torch.testing.assert_close(first.state, second.state, atol=0, rtol=0)
    assert first.trace == second.trace
    assert first.telemetry == second.telemetry


def test_disconnected_tissue_changes_neither_visit_set_nor_logical_work() -> None:
    substrate = graph((1, 2, 3), ((1, 2), (2, 3)))
    baseline = substrate.run_thought(state(), ingress_uids=1)

    root = state()
    for uid in range(100, 164):
        disconnected = cell(uid)
        disconnected.receptor.tune_to(root)
        substrate.add_cell(disconnected)
    enlarged = substrate.run_thought(state(), ingress_uids=1)

    torch.testing.assert_close(baseline.state, enlarged.state, atol=0, rtol=0)
    keys = (
        "unique_uids",
        "activation_sequence",
        "total_activations",
        "full_transforms",
        "route_only_activations",
        "receptor_probes",
        "transmissions",
        "energy_consumed",
        "frontier_widths",
    )
    assert {key: baseline.telemetry[key] for key in keys} == {
        key: enlarged.telemetry[key] for key in keys
    }


def test_hard_governor_exhaustion_is_not_quiescence() -> None:
    config = SparseWaveConfig(
        initial_route_energy=32,
        max_waves=2,
        max_total_activations=64,
        max_degree=8,
        max_fanout=4,
        max_uid_activations=32,
    )
    substrate = graph(
        (1, 2, 3),
        ((1, 2), (2, 3), (3, 1)),
        config=config,
    )
    result = substrate.run_thought(state(), ingress_uids=1)

    assert result.status is WaveStatus.EXHAUSTED
    assert not result.naturally_quiescent
    assert result.telemetry["exhaustion_reason"] == "max_waves"
    assert result.telemetry["energy_conservation_error"] == pytest.approx(0.0)
    assert substrate.ready_for_next_turn


def test_bounded_wave_laboratory_meets_physical_exit_gate() -> None:
    config = WaveLabConfig(
        width=WIDTH,
        rotary_pairs=PAIRS,
        sequence_length=5,
        disconnected_cell_counts=(0, 8),
        benchmark_warmup=0,
        benchmark_iterations=2,
        maximum_material_latency_ratio=20.0,
        maximum_serviceable_p95_ms=5_000,
        seed=36_200,
    )
    report = run_wave_laboratory(config)

    assert report["selection"]["stage2_exit_gate_met"] is True
    assert report["selection"]["disconnected_sparse_execution_pass"] is True
    assert report["protocol_checks"]["governor_abort_is_distinct_pass"] is True
    assert report["scale_trials"][-1]["active_stored_parameter_fraction"] < 1
    assert "no claim" in report["selection"]["speed_claim"]

    merged = merge_wave_lab_results([report, report])
    assert merged["selection"]["all_devices_pass"] is True
    assert merged["selection"]["cross_device_replay_pass"] is True
    assert len(merged["execution"]["devices"]) == 2
