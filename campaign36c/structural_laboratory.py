from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
import statistics
import tempfile
import time
from typing import Any

import torch

from .cell import StandaloneBDHCell
from .config import BDHCellConfig, SparseWaveConfig
from .persistence import FaultPoint, InjectedCrash, PackedCellStore
from .residency import GraphResidencyManager
from .structural import (
    CoAccessTracker,
    ConditionalTrustProfile,
    FissionEvidence,
    FusionEvidence,
    FusionPolicyConfig,
    FusionProbe,
    HealingProbe,
    ReversibleCompositeCell,
    StructuralController,
)
from .wave import SparseWaveSubstrate, WaveCell


CAMPAIGN36C_STRUCTURAL_LAB_RESULT_SCHEMA = (
    "ninereeds_campaign36c_structural_lab_result_v0"
)


@dataclass(frozen=True)
class StructuralLabConfig:
    width: int = 512
    rotary_pairs: int = 2
    sequence_length: int = 16
    benchmark_warmup: int = 3
    benchmark_iterations: int = 20
    page_capacity: int = 2
    maximum_composite_leaves: int = 2
    behavior_tolerance: float = 0.02
    maximum_seam_regression: float = 1e-4
    seed: int = 36_600

    def validate(self) -> None:
        if self.width <= 0 or self.rotary_pairs <= 0 or self.sequence_length <= 1:
            raise ValueError("structural laboratory dimensions are invalid")
        if self.benchmark_warmup < 0 or self.benchmark_iterations <= 0:
            raise ValueError("benchmark bounds are invalid")
        if self.page_capacity <= 1 or self.maximum_composite_leaves < 2:
            raise ValueError("packing and composite bounds are invalid")
        if self.behavior_tolerance < 0 or self.maximum_seam_regression < 0:
            raise ValueError("structural tolerances must be non-negative")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")


def _member(
    uid: int,
    config: StructuralLabConfig,
    root: torch.Tensor,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> WaveCell:
    cell = WaveCell(
        StandaloneBDHCell(
            BDHCellConfig(
                width=config.width,
                rotary_pairs=config.rotary_pairs,
                initialization_seed=config.seed + uid,
            ),
            uid=uid,
        ),
        max_degree=8,
        max_fanout=4,
    ).to(device=device, dtype=dtype)
    cell.receptor.tune_to(root)
    return cell


def _root(
    config: StructuralLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> torch.Tensor:
    return torch.randn(
        1,
        config.sequence_length,
        config.width,
        generator=torch.Generator(device="cpu").manual_seed(config.seed),
    ).to(device=device, dtype=dtype)


def _path_graph(
    config: StructuralLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[SparseWaveSubstrate, torch.Tensor]:
    root = _root(config, device=device, dtype=dtype)
    substrate = SparseWaveSubstrate(
        SparseWaveConfig(
            max_degree=8,
            max_fanout=4,
            initial_route_energy=64.0,
        )
    ).to(device=device, dtype=dtype)
    for uid in (1, 2, 3, 10):
        substrate.add_cell(_member(uid, config, root, device=device, dtype=dtype))
    substrate.connect(1, 2, conductance=0.95, route_familiarity=0.95)
    substrate.connect(2, 3, conductance=0.90, route_familiarity=0.90)
    substrate.connect(10, 1, conductance=0.90, route_familiarity=0.90)
    return substrate, root


def _fusion_evidence(left: int = 1, right: int = 2) -> FusionEvidence:
    return FusionEvidence(
        left_uid=left,
        right_uid=right,
        left_lifecycle="mature",
        right_lifecycle="mature",
        left_rigidity=0.90,
        right_rigidity=0.85,
        conductance=0.95,
        conditional_coparticipation=0.95,
        left_independent_use=0.04,
        right_independent_use=0.03,
        recent_error=0.001,
        measured_dispatch_savings=0.25,
        thought_epochs=(1, 2, 3),
        evidence_lineages=("source:a", "source:b"),
        trust_profiles=(
            ConditionalTrustProfile(1, "route:common", 0.70, 0.10, 0.05),
            ConditionalTrustProfile(2, "route:common", 0.80, 0.40, 0.20),
        ),
    )


def _fission_evidence(uid: int) -> FissionEvidence:
    return FissionEvidence(
        composite_uid=uid,
        thought_epochs=(10, 11, 12),
        evidence_lineages=("lineage:a", "lineage:b"),
        regimes=("regime:a", "regime:b"),
        negative_transfer=0.20,
        left_regime_useful=True,
        right_regime_useful=True,
        left_boundary_regression=0.0,
        right_boundary_regression=0.0,
        routing_calibrated=True,
        shadow_specialists_win_after_cost=True,
        successor_obligations_closed=True,
    )


def _sync(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _benchmark(
    substrate: SparseWaveSubstrate,
    root: torch.Tensor,
    *,
    ingress_uid: int,
    warmup: int,
    iterations: int,
    device: torch.device,
) -> dict[str, float]:
    with torch.inference_mode():
        for _ in range(warmup):
            substrate.run_thought(root, ingress_uids=ingress_uid)
        _sync(device)
        samples: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter_ns()
            substrate.run_thought(root, ingress_uids=ingress_uid)
            _sync(device)
            samples.append((time.perf_counter_ns() - start) / 1_000_000)
    return {
        "mean_ms": statistics.fmean(samples),
        "p95_ms": sorted(samples)[max(0, int(len(samples) * 0.95) - 1)],
    }


def _optimizer_partition(cell: WaveCell, root: torch.Tensor) -> dict[str, Any]:
    optimizer = torch.optim.AdamW(cell.transform.parameters(), lr=0.001)
    optimizer.zero_grad(set_to_none=True)
    cell.transform(root).float().square().mean().backward()
    optimizer.step()
    return {
        "policy": "torch_adamw_uid_local_full_moments_v1",
        "state": optimizer.state_dict(),
    }


def _packing_trial(
    root: Path,
    config: StructuralLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    state = _root(config, device=device, dtype=dtype)
    substrate = SparseWaveSubstrate(SparseWaveConfig(max_degree=8, max_fanout=4)).to(
        device=device, dtype=dtype
    )
    for uid in (1, 2, 3, 4):
        substrate.add_cell(_member(uid, config, state, device=device, dtype=dtype))
    store = PackedCellStore(root / "packing", page_capacity=config.page_capacity)
    store.commit_substrate(substrate)
    expected = substrate.run_thought(state, ingress_uids=(1, 3)).state.detach().clone()
    before = GraphResidencyManager(store)
    before.activate((1, 3), halo_hops=0)
    tracker = CoAccessTracker()
    for _ in range(8):
        tracker.observe((1, 3))
    order = tracker.repack_order((1, 2, 3, 4))
    store.repack(order)
    after = GraphResidencyManager(store)
    after.activate((1, 3), halo_hops=0)
    restored, _, _, _ = store.load_substrate(device=device)
    observed = restored.run_thought(state, ingress_uids=(1, 3)).state
    behavior_difference = float(
        (observed.detach().float() - expected.float()).abs().max().cpu()
    )
    return {
        "coaccess_count": tracker.count(1, 3),
        "repack_order": list(order),
        "before_page_loads": before.telemetry.page_loads,
        "after_page_loads": after.telemetry.page_loads,
        "before_bytes": before.telemetry.bytes_read,
        "after_bytes": after.telemetry.bytes_read,
        "behavior_max_difference": behavior_difference,
        "uids_preserved": set(store.inventory()) == {1, 2, 3, 4},
        "aliases_unchanged": store.manifest["aliases"] == {},
        "pass": (
            after.telemetry.page_loads < before.telemetry.page_loads
            and behavior_difference <= config.behavior_tolerance
            and set(store.inventory()) == {1, 2, 3, 4}
            and store.manifest["aliases"] == {}
        ),
    }


def _fusion_trial(
    root: Path,
    config: StructuralLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    substrate, state = _path_graph(config, device=device, dtype=dtype)
    expected_left = substrate.run_thought(state, ingress_uids=1)
    expected_right = substrate.run_thought(state, ingress_uids=2)
    expected_route = substrate.run_thought(state, ingress_uids=10)
    before_timing = _benchmark(
        substrate,
        state,
        ingress_uid=10,
        warmup=config.benchmark_warmup,
        iterations=config.benchmark_iterations,
        device=device,
    )
    partitions = {
        uid: _optimizer_partition(substrate._cell(uid), state) for uid in (1, 2)
    }
    # Optimizer steps changed the pair; establish the exact post-learning baseline.
    expected_left = substrate.run_thought(state, ingress_uids=1)
    expected_right = substrate.run_thought(state, ingress_uids=2)
    expected_route = substrate.run_thought(state, ingress_uids=10)
    policy = FusionPolicyConfig(
        maximum_composite_leaves=config.maximum_composite_leaves,
        behavior_tolerance=config.behavior_tolerance,
        maximum_seam_regression=config.maximum_seam_regression,
    )
    controller = StructuralController(substrate, next_uid=100, policy=policy)
    decision = controller.fuse(
        _fusion_evidence(),
        (FusionProbe(state, 1), FusionProbe(state, 2)),
        optimizer_partitions=partitions,
    )
    if not decision.admitted or decision.successor_uid is None:
        return {"pass": False, "decision": asdict(decision)}
    successor = decision.successor_uid
    observed_left = substrate.run_thought(state, ingress_uids=1)
    observed_right = substrate.run_thought(state, ingress_uids=2)
    observed_route = substrate.run_thought(state, ingress_uids=10)
    duplicate_alias = substrate.run_thought(state, ingress_uids=(1, 2))
    after_timing = _benchmark(
        substrate,
        state,
        ingress_uid=10,
        warmup=config.benchmark_warmup,
        iterations=config.benchmark_iterations,
        device=device,
    )
    composite = substrate._cell(successor)
    assert isinstance(composite, ReversibleCompositeCell)
    trust = composite.inherited_trust("route:common")
    store = PackedCellStore(root / "fusion", page_capacity=config.page_capacity)
    store.commit_substrate(substrate, reason="reversible-fusion")
    cold, _, _, anatomy = store.load_substrate(device=device)
    cold_output = cold.run_thought(state, ingress_uids=10).state
    cold_composite = cold._cell(successor)
    assert isinstance(cold_composite, ReversibleCompositeCell)
    fission_controller = StructuralController(cold, next_uid=101, policy=policy)
    fission = fission_controller.fission(_fission_evidence(successor))
    split_output = cold.run_thought(state, ingress_uids=10).state

    differences = {
        "left_alias": float(
            (observed_left.state.detach().float() - expected_left.state.detach().float()).abs().max().cpu()
        ),
        "right_alias": float(
            (observed_right.state.detach().float() - expected_right.state.detach().float()).abs().max().cpu()
        ),
        "neighbor_route": float(
            (observed_route.state.detach().float() - expected_route.state.detach().float()).abs().max().cpu()
        ),
        "cold_resume": float(
            (cold_output.detach().float() - expected_route.state.detach().float()).abs().max().cpu()
        ),
        "post_fission": float(
            (split_output.detach().float() - expected_route.state.detach().float()).abs().max().cpu()
        ),
    }
    return {
        "successor_uid": successor,
        "fusion_audit": asdict(decision.audit) if decision.audit else None,
        "behavior_max_differences": differences,
        "before_wave_depth": expected_route.telemetry["wave_depth"],
        "after_wave_depth": observed_route.telemetry["wave_depth"],
        "after_saved_dispatch_boundaries": observed_route.telemetry[
            "saved_dispatch_boundaries"
        ],
        "after_logical_activations": observed_route.telemetry["total_activations"],
        "after_constituent_transforms": observed_route.telemetry[
            "constituent_full_transforms"
        ],
        "duplicate_alias_successor_activations": duplicate_alias.telemetry[
            "activation_sequence"
        ].count(successor),
        "trust": trust,
        "credit_target": list(substrate.resolve_credit_target(1)),
        "optimizer_partition_uids": sorted(cold_composite.optimizer_partitions),
        "fusion_tree": anatomy[successor]["lineage"]["fusion_tree"],
        "before_timing": before_timing,
        "after_timing": after_timing,
        "fission": asdict(fission),
        "fission_retired_successor": successor in cold.retired_uids,
        "pass": (
            max(differences.values()) <= config.behavior_tolerance
            and observed_route.telemetry["wave_depth"]
            < expected_route.telemetry["wave_depth"]
            and observed_route.telemetry["saved_dispatch_boundaries"] >= 1
            and observed_route.telemetry["constituent_full_transforms"]
            == expected_route.telemetry["full_transforms"]
            and duplicate_alias.telemetry["activation_sequence"].count(successor) == 1
            and trust["positive_authority"] == 0.8
            and trust["negative_history"] == 0.4
            and substrate.resolve_credit_target(1) == (successor, 1)
            and sorted(cold_composite.optimizer_partitions) == [1, 2]
            and fission.admitted
            and successor in cold.retired_uids
        ),
    }


def _rigidity_and_gate_trial(
    config: StructuralLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    policy = FusionPolicyConfig(
        maximum_composite_leaves=config.maximum_composite_leaves,
        behavior_tolerance=config.behavior_tolerance,
        maximum_seam_regression=config.maximum_seam_regression,
    )
    substrate, state = _path_graph(config, device=device, dtype=dtype)
    controller = StructuralController(substrate, next_uid=100, policy=policy)
    admitted = controller.fuse(
        _fusion_evidence(),
        (FusionProbe(state, 1), FusionProbe(state, 2)),
    )
    assert admitted.successor_uid is not None
    successor = admitted.successor_uid
    composite = substrate._cell(successor)
    assert isinstance(composite, ReversibleCompositeCell)
    with torch.no_grad():
        generator = torch.Generator(device="cpu").manual_seed(config.seed + 99)
        weight = torch.randn(
            config.width,
            config.width,
            generator=generator,
        ).to(device=device, dtype=dtype)
        composite.transform.healing_adapter.weight.copy_(weight)
        composite.transform.healing_strength.fill_(1.0)
    target = composite.execute_composite(
        state, entry_alias_uid=1, attention_mask=None
    ).detach()
    rigidity = controller.audit_rigidity(
        successor, (HealingProbe(state, target, 1),)
    )
    refused_fission = controller.fission(_fission_evidence(successor))

    bound_graph, bound_state = _path_graph(config, device=device, dtype=dtype)
    bound_controller = StructuralController(bound_graph, next_uid=100, policy=policy)
    first = bound_controller.fuse(
        _fusion_evidence(),
        (FusionProbe(bound_state, 1), FusionProbe(bound_state, 2)),
    )
    assert first.successor_uid is not None
    bound = bound_controller.fuse(
        _fusion_evidence(first.successor_uid, 3),
        (FusionProbe(bound_state, first.successor_uid), FusionProbe(bound_state, 3)),
    )

    newborn_graph, newborn_state = _path_graph(config, device=device, dtype=dtype)
    newborn_controller = StructuralController(newborn_graph, next_uid=100, policy=policy)
    value = _fusion_evidence().__dict__.copy()
    value["left_lifecycle"] = "probationary"
    newborn = newborn_controller.fuse(
        FusionEvidence(**value),
        (FusionProbe(newborn_state, 1), FusionProbe(newborn_state, 2)),
    )
    unrelated_value = _fusion_evidence().__dict__.copy()
    unrelated_value["conditional_coparticipation"] = 0.05
    unrelated_graph, unrelated_state = _path_graph(
        config, device=device, dtype=dtype
    )
    unrelated = StructuralController(
        unrelated_graph, next_uid=100, policy=policy
    ).fuse(
        FusionEvidence(**unrelated_value),
        (FusionProbe(unrelated_state, 1), FusionProbe(unrelated_state, 2)),
    )
    return {
        "rigidity": asdict(rigidity),
        "rigid_fission": asdict(refused_fission),
        "fusion_bound_failed_gates": list(bound.failed_gates),
        "newborn_failed_gates": list(newborn.failed_gates),
        "unrelated_failed_gates": list(unrelated.failed_gates),
        "pass": (
            not rigidity.extractable
            and refused_fission.action == "repair_in_place_or_bud"
            and "leaf_budget" in bound.failed_gates
            and "left_mature" in newborn.failed_gates
            and "coparticipation" in unrelated.failed_gates
        ),
    }


def _fault_trial(
    root: Path,
    config: StructuralLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    results: dict[str, bool] = {}
    for fault in FaultPoint:
        substrate, state = _path_graph(config, device=device, dtype=dtype)
        store_root = root / fault.value
        store = PackedCellStore(store_root, page_capacity=config.page_capacity)
        store.commit_substrate(substrate)
        controller = StructuralController(substrate, next_uid=100)
        decision = controller.fuse(
            _fusion_evidence(),
            (FusionProbe(state, 1), FusionProbe(state, 2)),
        )
        assert decision.successor_uid is not None
        try:
            store.commit_substrate(
                substrate,
                reason="fault-injected-fusion",
                fault_at=fault,
            )
        except InjectedCrash:
            pass
        recovered = PackedCellStore(store_root, page_capacity=config.page_capacity)
        active = set(map(int, recovered.manifest["uid_index"]))
        old = active == {1, 2, 3, 10} and recovered.manifest["aliases"] == {}
        new = active == {3, 10, 100} and recovered.manifest["aliases"] == {
            "1": 100,
            "2": 100,
        }
        expected_new = fault in {FaultPoint.AFTER_COMMIT, FaultPoint.AFTER_PUBLISH}
        results[fault.value] = new if expected_new else old
    return {"boundaries": results, "pass": all(results.values())}


def run_structural_laboratory(
    config: StructuralLabConfig | None = None,
    *,
    device: str | torch.device = "cpu",
    dtype: torch.dtype = torch.float32,
    scratch_root: str | Path | None = None,
) -> dict[str, Any]:
    config = config or StructuralLabConfig()
    config.validate()
    target_device = torch.device(device)
    if target_device.type == "cpu" and dtype != torch.float32:
        raise ValueError("the CPU Stage-6 lab requires float32")
    if target_device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable")
    parent = Path(scratch_root) if scratch_root is not None else None
    if parent is not None:
        parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="campaign36c-stage6-", dir=parent) as temp:
        root = Path(temp)
        packing = _packing_trial(
            root, config, device=target_device, dtype=dtype
        )
        fusion = _fusion_trial(
            root, config, device=target_device, dtype=dtype
        )
        rigidity = _rigidity_and_gate_trial(
            config, device=target_device, dtype=dtype
        )
        faults = _fault_trial(
            root / "faults", config, device=target_device, dtype=dtype
        )
    exit_gate = all(
        item["pass"] for item in (packing, fusion, rigidity, faults)
    )
    return {
        "schema_version": CAMPAIGN36C_STRUCTURAL_LAB_RESULT_SCHEMA,
        "lab_config": asdict(config),
        "execution": {
            "device": str(target_device),
            "dtype": str(dtype),
            "scratch_filesystem": str(parent or Path(tempfile.gettempdir())),
        },
        "packing": packing,
        "fusion": fusion,
        "rigidity_and_gates": rigidity,
        "fault_injection": faults,
        "selection": {
            "packing_io_benefit_pass": packing["pass"],
            "fresh_fusion_behavior_pass": fusion["pass"],
            "rigidity_and_fission_pass": rigidity["pass"],
            "crash_consistency_pass": faults["pass"],
            "stage6_exit_gate_met": exit_gate,
        },
    }


def merge_structural_lab_results(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one structural report is required")
    first = reports[0]
    if any(report["lab_config"] != first["lab_config"] for report in reports[1:]):
        raise ValueError("structural reports must use identical laboratory bounds")
    return {
        "schema_version": CAMPAIGN36C_STRUCTURAL_LAB_RESULT_SCHEMA,
        "lab_config": first["lab_config"],
        "execution": {"devices": [report["execution"] for report in reports]},
        "device_reports": reports,
        "selection": {
            "all_devices_pass": all(
                report["selection"]["stage6_exit_gate_met"] for report in reports
            ),
            "stage6_exit_gate_met": all(
                report["selection"]["stage6_exit_gate_met"] for report in reports
            ),
        },
    }


def write_structural_lab_result(path: str | Path, result: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
