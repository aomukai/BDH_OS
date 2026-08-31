from __future__ import annotations

import json
import hashlib
import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import statistics
import tempfile
import time
from typing import Any

import torch

from .cell import StandaloneBDHCell
from .config import (
    CAMPAIGN36C_WAVE_ABI,
    BDHCellConfig,
    SparseWaveConfig,
)
from .wave import SparseWaveSubstrate, WaveCell, WaveStatus


CAMPAIGN36C_WAVE_LAB_RESULT_SCHEMA = "ninereeds_campaign36c_wave_lab_result_v0"


@dataclass(frozen=True)
class WaveLabConfig:
    width: int = 512
    rotary_pairs: int = 2
    sequence_length: int = 16
    disconnected_cell_counts: tuple[int, ...] = (0, 256, 4096)
    benchmark_warmup: int = 5
    benchmark_iterations: int = 25
    maximum_material_latency_ratio: float = 3.0
    maximum_serviceable_p95_ms: float = 5_000.0
    seed: int = 36_200

    def validate(self) -> None:
        if self.width <= 0 or self.rotary_pairs <= 0 or self.sequence_length < 2:
            raise ValueError("cell and sequence dimensions must be positive")
        if not self.disconnected_cell_counts:
            raise ValueError("at least one disconnected population size is required")
        if tuple(sorted(set(self.disconnected_cell_counts))) != self.disconnected_cell_counts:
            raise ValueError("disconnected counts must be sorted and unique")
        if self.disconnected_cell_counts[0] != 0:
            raise ValueError("the disconnected population sweep must begin at zero")
        if self.benchmark_warmup < 0 or self.benchmark_iterations <= 0:
            raise ValueError("benchmark bounds are invalid")
        if self.maximum_material_latency_ratio < 1:
            raise ValueError("material latency ratio must be at least one")
        if self.maximum_serviceable_p95_ms <= 0:
            raise ValueError("serviceable latency bound must be positive")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")


def _root_state(
    config: WaveLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> torch.Tensor:
    generator = torch.Generator(device="cpu").manual_seed(config.seed)
    return torch.randn(
        1,
        config.sequence_length,
        config.width,
        generator=generator,
    ).to(device=device, dtype=dtype)


def _member(
    uid: int,
    config: WaveLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> WaveCell:
    transform = StandaloneBDHCell(
        BDHCellConfig(
            width=config.width,
            rotary_pairs=config.rotary_pairs,
            initialization_seed=config.seed + uid,
        ),
        uid=uid,
    )
    return WaveCell(transform).to(device=device, dtype=dtype)


def _substrate(
    config: WaveLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
    max_waves: int = 32,
    max_uid_activations: int = 3,
) -> tuple[SparseWaveSubstrate, torch.Tensor]:
    governor = SparseWaveConfig(
        initial_route_energy=64,
        max_waves=max_waves,
        max_total_activations=256,
        max_receptor_probes=1_024,
        max_frontier_width=64,
        max_degree=16,
        max_fanout=4,
        max_uid_activations=max_uid_activations,
    )
    substrate = SparseWaveSubstrate(governor).to(device=device, dtype=dtype)
    root = _root_state(config, device=device, dtype=dtype)
    return substrate, root


def _add_tuned_cells(
    substrate: SparseWaveSubstrate,
    root: torch.Tensor,
    uids: tuple[int, ...],
    config: WaveLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> None:
    for uid in uids:
        member = _member(uid, config, device=device, dtype=dtype)
        member.receptor.tune_to(root)
        substrate.add_cell(member)


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def _benchmark(
    substrate: SparseWaveSubstrate,
    root: torch.Tensor,
    config: WaveLabConfig,
    *,
    device: torch.device,
) -> tuple[dict[str, float], Any]:
    with torch.inference_mode():
        for _ in range(config.benchmark_warmup):
            substrate.run_thought(root, ingress_uids=1)
        _synchronize(device)
        latencies: list[float] = []
        last = None
        for _ in range(config.benchmark_iterations):
            _synchronize(device)
            started = time.perf_counter_ns()
            last = substrate.run_thought(root, ingress_uids=1)
            _synchronize(device)
            latencies.append((time.perf_counter_ns() - started) / 1_000_000)
    assert last is not None
    median_ms = statistics.median(latencies)
    return (
        {
            "median_ms": median_ms,
            "p95_ms": _percentile(latencies, 0.95),
            "minimum_ms": min(latencies),
            "maximum_ms": max(latencies),
            "thoughts_per_second_at_median": 1_000 / median_ms,
            "latent_tokens_per_second_at_median": (
                config.sequence_length * 1_000 / median_ms
            ),
        },
        last,
    )


def _work_signature(telemetry: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "unique_uids",
        "activation_sequence",
        "total_activations",
        "full_transforms",
        "route_only_activations",
        "receptor_probes",
        "receptor_acceptances",
        "receptor_rejections",
        "convergence_groups",
        "transmissions",
        "terminations",
        "hardware_transform_batches",
        "energy_consumed",
        "frontier_widths",
    )
    return {key: telemetry[key] for key in keys}


def _max_abs(left: torch.Tensor, right: torch.Tensor) -> float:
    return float((left.float() - right.float()).abs().max().detach().cpu())


def _tensor_sha256(value: torch.Tensor) -> str:
    canonical = value.detach().float().contiguous().cpu()
    return hashlib.sha256(canonical.view(torch.uint8).numpy().tobytes()).hexdigest()


def run_wave_laboratory(
    config: WaveLabConfig | None = None,
    *,
    device: str | torch.device = "cpu",
    dtype: torch.dtype = torch.float32,
) -> dict[str, Any]:
    """Run the fixed-graph Stage-2 exit-gate experiment on one device."""

    config = config or WaveLabConfig()
    config.validate()
    target = torch.device(device)
    if target.type == "cpu" and dtype != torch.float32:
        raise ValueError("the CPU wave lab requires float32")
    if target.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is not available")

    substrate, root = _substrate(config, device=target, dtype=dtype)
    connected_uids = (1, 2, 3, 4, 5)
    _add_tuned_cells(
        substrate,
        root,
        connected_uids,
        config,
        device=target,
        dtype=dtype,
    )
    for source, destination in ((1, 2), (1, 3), (2, 4), (3, 4), (4, 5)):
        substrate.connect(source, destination)

    with torch.inference_mode():
        baseline = substrate.run_thought(root, ingress_uids=1, collect_trace=True)
        replay = substrate.run_thought(root, ingress_uids=1, collect_trace=True)
    baseline_signature = _work_signature(baseline.telemetry)
    replay_difference = _max_abs(baseline.state, replay.state)
    deterministic_replay = (
        replay_difference == 0.0
        and baseline.trace == replay.trace
        and baseline_signature == _work_signature(replay.telemetry)
    )

    scale_trials: list[dict[str, Any]] = []
    added = 0
    baseline_median = 0.0
    baseline_parameters = sum(p.numel() for p in substrate.parameters())
    transform_parameters = substrate.cells["1"].transform.parameter_count
    for disconnected_count in config.disconnected_cell_counts:
        while added < disconnected_count:
            uid = 10_000 + added
            substrate.add_cell(
                _member(uid, config, device=target, dtype=dtype)
            )
            added += 1
        timings, observed = _benchmark(
            substrate, root, config, device=target
        )
        if disconnected_count == 0:
            baseline_median = timings["median_ms"]
        parameters = sum(parameter.numel() for parameter in substrate.parameters())
        trial = {
            "disconnected_cell_count": disconnected_count,
            "total_cell_count": len(substrate.cells),
            "total_stored_parameters": parameters,
            "connected_baseline_parameters": baseline_parameters,
            "active_transform_parameter_time": (
                observed.telemetry["full_transforms"] * transform_parameters
            ),
            "active_stored_parameter_fraction": (
                observed.telemetry["unique_uid_count"]
                * transform_parameters
                / parameters
            ),
            "output_max_abs_from_baseline": _max_abs(
                baseline.state, observed.state
            ),
            "logical_work_unchanged": (
                _work_signature(observed.telemetry) == baseline_signature
            ),
            "visited_graph_unchanged": (
                observed.telemetry["unique_uids"]
                == baseline.telemetry["unique_uids"]
            ),
            "median_latency_ratio_to_baseline": (
                timings["median_ms"] / baseline_median
            ),
            **timings,
        }
        scale_trials.append(trial)

    recurrence, recurrence_root = _substrate(
        config,
        device=target,
        dtype=dtype,
        max_uid_activations=2,
    )
    _add_tuned_cells(
        recurrence,
        recurrence_root,
        (21, 22, 23),
        config,
        device=target,
        dtype=dtype,
    )
    for source, destination in ((21, 22), (22, 23), (23, 21)):
        recurrence.connect(source, destination)
    with torch.inference_mode():
        recurrence_result = recurrence.run_thought(recurrence_root, ingress_uids=21)

    reversal, reversal_root = _substrate(config, device=target, dtype=dtype)
    _add_tuned_cells(
        reversal,
        reversal_root,
        (31, 32),
        config,
        device=target,
        dtype=dtype,
    )
    reversal.connect(31, 32)
    reversal.connect(32, 31)
    with torch.inference_mode():
        reversal_result = reversal.run_thought(reversal_root, ingress_uids=31)

    exhausted, exhausted_root = _substrate(
        config,
        device=target,
        dtype=dtype,
        max_waves=2,
        max_uid_activations=32,
    )
    _add_tuned_cells(
        exhausted,
        exhausted_root,
        (41, 42, 43),
        config,
        device=target,
        dtype=dtype,
    )
    for source, destination in ((41, 42), (42, 43), (43, 41)):
        exhausted.connect(source, destination)
    with torch.inference_mode():
        exhausted_result = exhausted.run_thought(exhausted_root, ingress_uids=41)

    protocol_checks = {
        "branching_pass": baseline.telemetry["peak_frontier_width"] == 2,
        "convergence_pass": baseline.telemetry["convergence_groups"] == 1,
        "same_target_executes_once_pass": (
            baseline.telemetry["activation_sequence"].count(4) == 1
        ),
        "deterministic_replay_pass": deterministic_replay,
        "deterministic_replay_max_abs": replay_difference,
        "immediate_reversal_pass": (
            reversal_result.telemetry["activation_sequence"] == [31, 32]
            and reversal_result.status is WaveStatus.QUIESCENT
        ),
        "longer_recurrence_pass": (
            recurrence_result.telemetry["activation_sequence"]
            == [21, 22, 23, 21, 22, 23]
            and recurrence_result.telemetry["recurrence_suppressed"] == 1
        ),
        "natural_quiescence_pass": baseline.status is WaveStatus.QUIESCENT,
        "governor_abort_is_distinct_pass": (
            exhausted_result.status is WaveStatus.EXHAUSTED
            and exhausted_result.telemetry["exhaustion_reason"] == "max_waves"
        ),
        "energy_conservation_pass": all(
            result.telemetry["energy_conservation_error"] <= 1e-6
            for result in (
                baseline,
                recurrence_result,
                reversal_result,
                exhausted_result,
            )
        ),
        "active_execution_vectorized_pass": (
            baseline.telemetry["hardware_transform_batches"]
            == baseline.telemetry["wave_depth"]
        ),
    }
    all_protocol_pass = all(
        bool(value)
        for key, value in protocol_checks.items()
        if key.endswith("_pass")
    )
    disconnected_sparse_pass = all(
        trial["logical_work_unchanged"]
        and trial["visited_graph_unchanged"]
        and trial["output_max_abs_from_baseline"] == 0.0
        for trial in scale_trials
    )
    max_latency_ratio = max(
        trial["median_latency_ratio_to_baseline"] for trial in scale_trials
    )
    max_p95_ms = max(trial["p95_ms"] for trial in scale_trials)
    material_cost_pass = max_latency_ratio <= config.maximum_material_latency_ratio
    serviceability_pass = max_p95_ms <= config.maximum_serviceable_p95_ms
    stage2_exit_gate_met = (
        all_protocol_pass
        and disconnected_sparse_pass
        and material_cost_pass
        and serviceability_pass
    )
    return {
        "schema_version": CAMPAIGN36C_WAVE_LAB_RESULT_SCHEMA,
        "wave_abi": CAMPAIGN36C_WAVE_ABI,
        "lab_config": {
            **asdict(config),
            "disconnected_cell_counts": list(config.disconnected_cell_counts),
        },
        "execution": {
            "device": str(target),
            "dtype": str(dtype),
            "cuda_device_name": (
                torch.cuda.get_device_name(target) if target.type == "cuda" else None
            ),
        },
        "protocol_checks": protocol_checks,
        "baseline": {
            "status": baseline.status.value,
            "state_sha256_float32": _tensor_sha256(baseline.state),
            "telemetry": baseline.telemetry,
            "trace": list(baseline.trace),
        },
        "scale_trials": scale_trials,
        "selection": {
            "all_protocol_checks_pass": all_protocol_pass,
            "disconnected_sparse_execution_pass": disconnected_sparse_pass,
            "material_forward_cost_pass": material_cost_pass,
            "serviceability_pass": serviceability_pass,
            "maximum_observed_median_latency_ratio": max_latency_ratio,
            "maximum_observed_p95_ms": max_p95_ms,
            "speed_claim": (
                "serviceability and capacity-independent sparse work only; "
                "no claim of winning tiny-task latency against a resident transformer"
            ),
            "stage2_exit_gate_met": stage2_exit_gate_met,
        },
    }


def merge_wave_lab_results(
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one device report is required")
    first = reports[0]
    for report in reports:
        if report.get("schema_version") != CAMPAIGN36C_WAVE_LAB_RESULT_SCHEMA:
            raise ValueError("wave lab report schema mismatch")
        if report.get("lab_config") != first.get("lab_config"):
            raise ValueError("device wave labs used different configurations")
    cross_device_replay_pass = len(
        {
            report["baseline"]["state_sha256_float32"]
            for report in reports
        }
    ) == 1 and len(
        {
            json.dumps(_work_signature(report["baseline"]["telemetry"]), sort_keys=True)
            for report in reports
        }
    ) == 1
    all_device_protocols_pass = all(
        report["selection"]["stage2_exit_gate_met"] for report in reports
    )
    return {
        "schema_version": CAMPAIGN36C_WAVE_LAB_RESULT_SCHEMA,
        "wave_abi": CAMPAIGN36C_WAVE_ABI,
        "lab_config": first["lab_config"],
        "execution": {
            "devices": [report["execution"] for report in reports],
        },
        "device_reports": reports,
        "selection": {
            "all_devices_pass": all_device_protocols_pass,
            "cross_device_replay_pass": cross_device_replay_pass,
            "stage2_exit_gate_met": (
                all_device_protocols_pass and cross_device_replay_pass
            ),
            "speed_claim": first["selection"]["speed_claim"],
        },
    }


def write_wave_lab_result(path: str | Path, result: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
