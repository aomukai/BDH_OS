from __future__ import annotations

import hashlib
import io
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import statistics
import tempfile
import time
from typing import Any

import torch

from .cell import StandaloneBDHCell
from .checkpoint import build_cell_optimizer
from .config import BDHCellConfig, CellOptimizerConfig, SparseWaveConfig
from .persistence import (
    CorruptStoreError,
    DirtyCellBuffer,
    FaultPoint,
    InjectedCrash,
    PackedCellStore,
)
from .residency import GraphResidencyManager
from .wave import SparseWaveSubstrate, WaveCell


CAMPAIGN36C_PERSISTENCE_LAB_RESULT_SCHEMA = (
    "ninereeds_campaign36c_persistence_lab_result_v0"
)


@dataclass(frozen=True)
class PersistenceLabConfig:
    width: int = 512
    rotary_pairs: int = 2
    sequence_length: int = 16
    disconnected_cells: int = 200
    page_capacities: tuple[int, ...] = (2, 20, 200)
    access_set_sizes: tuple[int, ...] = (2, 20, 200)
    dirty_update_events: int = 8
    seed: int = 36_500

    def validate(self) -> None:
        if self.width <= 0 or self.rotary_pairs <= 0 or self.sequence_length <= 1:
            raise ValueError("persistence laboratory dimensions are invalid")
        if self.disconnected_cells < max(self.access_set_sizes, default=0):
            raise ValueError("disconnected inventory must cover every access-set size")
        if not self.page_capacities or any(value <= 1 for value in self.page_capacities):
            raise ValueError("page capacities must all exceed one")
        if not self.access_set_sizes or any(value <= 0 for value in self.access_set_sizes):
            raise ValueError("access set sizes must be positive")
        if self.dirty_update_events <= 1 or self.seed < 0:
            raise ValueError("dirty update count and seed are invalid")


def _member(
    uid: int,
    config: PersistenceLabConfig,
    *,
    root: torch.Tensor | None,
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
    if root is not None:
        cell.receptor.tune_to(root)
    return cell


def _route_graph(
    config: PersistenceLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[SparseWaveSubstrate, torch.Tensor]:
    root = torch.randn(
        1,
        config.sequence_length,
        config.width,
        generator=torch.Generator(device="cpu").manual_seed(config.seed),
    ).to(device=device, dtype=dtype)
    substrate = SparseWaveSubstrate(
        SparseWaveConfig(max_degree=8, max_fanout=4, max_total_activations=64)
    ).to(device=device, dtype=dtype)
    for uid in (1, 2, 3):
        substrate.add_cell(
            _member(uid, config, root=root, device=device, dtype=dtype)
        )
    substrate.connect(1, 2)
    substrate.connect(2, 3)
    return substrate, root


def _disconnected(
    config: PersistenceLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[int, WaveCell]:
    return {
        1_000 + index: _member(
            1_000 + index,
            config,
            root=None,
            device=device,
            dtype=dtype,
        )
        for index in range(config.disconnected_cells)
    }


def _digest(value: Any) -> str:
    buffer = io.BytesIO()
    torch.save(value, buffer)
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def _fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _cold_hint(store: PackedCellStore) -> bool:
    if not hasattr(os, "posix_fadvise") or not hasattr(os, "POSIX_FADV_DONTNEED"):
        return False
    applied = False
    active = {
        value["segment_id"] for value in store.manifest["uid_index"].values()
    }
    for declaration in store.manifest["segments"]:
        if declaration["segment_id"] not in active:
            continue
        descriptor = os.open(store.segment_root / declaration["path"], os.O_RDONLY)
        try:
            os.posix_fadvise(descriptor, 0, 0, os.POSIX_FADV_DONTNEED)
            applied = True
        finally:
            os.close(descriptor)
    return applied


def _page_trial(
    root: Path,
    config: PersistenceLabConfig,
    *,
    page_capacity: int,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    substrate, thought = _route_graph(config, device=device, dtype=dtype)
    optimizer_config = CellOptimizerConfig(learning_rate=0.001)
    optimizer = build_cell_optimizer(
        substrate._cell(2).transform.parameters(), optimizer_config
    )
    optimizer.zero_grad(set_to_none=True)
    substrate._cell(2).transform(thought).square().mean().backward()
    optimizer.step()
    with torch.inference_mode():
        expected = substrate.run_thought(thought, ingress_uids=1).state.detach().clone()
    optimizer_before = _digest(optimizer.state_dict())
    store = PackedCellStore(root, page_capacity=page_capacity)
    torch.manual_seed(config.seed + page_capacity)
    expected_random = torch.rand(8)
    torch.manual_seed(config.seed + page_capacity)
    route_commit = store.commit_substrate(
        substrate,
        optimizers={2: optimizer},
        optimizer_configs={2: optimizer_config},
        metadata={
            2: {
                "route_ring": [{"thought": 1, "destination": 3}],
                "evidence_influence": {"synthetic-source": 1.0},
            }
        },
    )
    cold_hint = _cold_hint(store)
    start = time.perf_counter_ns()
    restored, optimizers, _, anatomy = store.load_substrate(
        device=device, restore_rng=True
    )
    cold_resume_ms = (time.perf_counter_ns() - start) / 1e6
    with torch.inference_mode():
        restored_output = restored.run_thought(thought, ingress_uids=1).state
    cold_equivalent = torch.equal(restored_output, expected)
    optimizer_equivalent = _digest(optimizers[2].state_dict()) == optimizer_before
    rng_equivalent = torch.equal(torch.rand(8), expected_random)
    inventory_rebuild = store.inventory() == store.rebuild_index_from_segments()

    manager = GraphResidencyManager(store)
    before_inference = _fingerprint(store.root)
    start = time.perf_counter_ns()
    manager.activate(1, halo_hops=2)
    cold_route_ms = (time.perf_counter_ns() - start) / 1e6
    cold_loads = manager.telemetry.page_loads
    cold_bytes = manager.telemetry.bytes_read
    start = time.perf_counter_ns()
    manager.activate(1, halo_hops=2)
    warm_route_ms = (time.perf_counter_ns() - start) / 1e6
    repeat_avoided_io = manager.telemetry.page_loads == cold_loads
    inference_read_only = (
        _fingerprint(store.root) == before_inference
        and manager.telemetry.persistent_writes == 0
    )

    disconnected = _disconnected(config, device=device, dtype=dtype)
    store.commit_cells(disconnected, reason="disconnected-cold-growth")
    grown_manager = GraphResidencyManager(store)
    start = time.perf_counter_ns()
    grown_manager.activate(1, halo_hops=2)
    grown_route_ms = (time.perf_counter_ns() - start) / 1e6
    disconnected_io_independent = (
        grown_manager.telemetry.page_loads == cold_loads
        and grown_manager.telemetry.bytes_read == cold_bytes
    )

    access_results: list[dict[str, Any]] = []
    for size in config.access_set_sizes:
        access_manager = GraphResidencyManager(store)
        uids = tuple(1_000 + index for index in range(size))
        _cold_hint(store)
        start = time.perf_counter_ns()
        access_manager.activate(uids, halo_hops=0)
        latency_ms = (time.perf_counter_ns() - start) / 1e6
        access_results.append({
            "requested_cells": size,
            "latency_ms": latency_ms,
            "page_loads": access_manager.telemetry.page_loads,
            "bytes_read": access_manager.telemetry.bytes_read,
            "useful_byte_ratio": access_manager.telemetry.as_dict()[
                "useful_byte_ratio"
            ],
        })

    before_repack = store.inventory()
    with torch.inference_mode():
        before_repack_output = store.load_substrate(device=device)[0].run_thought(
            thought, ingress_uids=1
        ).state
    store.repack([1, 2, 3, *reversed(sorted(disconnected))])
    after_repack = store.inventory()
    with torch.inference_mode():
        after_repack_output = store.load_substrate(device=device)[0].run_thought(
            thought, ingress_uids=1
        ).state
    repack_identity = (
        torch.equal(before_repack_output, after_repack_output)
        and {
            uid: location.record_generation for uid, location in before_repack.items()
        }
        == {
            uid: location.record_generation for uid, location in after_repack.items()
        }
        and any(
            before_repack[uid].segment_id != after_repack[uid].segment_id
            for uid in before_repack
        )
    )

    generation_before = store.inventory()[2].record_generation
    dirty = DirtyCellBuffer(store)
    for _ in range(config.dirty_update_events):
        dirty.mark(substrate._cell(2), optimizer=optimizer, optimizer_config=optimizer_config)
    flush = dirty.flush()
    dirty_coalesced = (
        flush is not None
        and flush.written_uids == (2,)
        and store.inventory()[2].record_generation == generation_before + 1
    )
    active_segments = {
        value.segment_id for value in store.inventory().values()
    }
    active_file_count = len(active_segments)
    cell_count = len(store.inventory())
    return {
        "page_capacity": page_capacity,
        "route_commit_bytes": route_commit.bytes_written,
        "cold_hint_applied": cold_hint,
        "cold_resume_ms": cold_resume_ms,
        "cold_route_ms": cold_route_ms,
        "warm_route_ms": warm_route_ms,
        "grown_route_ms": grown_route_ms,
        "cold_route_page_loads": cold_loads,
        "cold_route_bytes": cold_bytes,
        "cold_restore_equivalent": cold_equivalent,
        "optimizer_restore_equivalent": optimizer_equivalent,
        "rng_restore_equivalent": rng_equivalent,
        "anatomy_restore_equivalent": (
            anatomy[2]["route_ring"] == [{"thought": 1, "destination": 3}]
        ),
        "inventory_rebuild_equivalent": inventory_rebuild,
        "warm_repeat_avoided_io": repeat_avoided_io,
        "inference_read_only": inference_read_only,
        "disconnected_io_independent": disconnected_io_independent,
        "repack_identity_pass": repack_identity,
        "dirty_updates": config.dirty_update_events,
        "dirty_record_generations_written": 1 if dirty_coalesced else None,
        "dirty_coalescing_pass": dirty_coalesced,
        "active_segment_files": active_file_count,
        "cell_count": cell_count,
        "one_file_per_cell_avoided": active_file_count < cell_count,
        "access_sets": access_results,
        "pass": all((
            cold_equivalent,
            optimizer_equivalent,
            rng_equivalent,
            inventory_rebuild,
            repeat_avoided_io,
            inference_read_only,
            disconnected_io_independent,
            repack_identity,
            dirty_coalesced,
            active_file_count < cell_count,
        )),
    }


def _fault_trials(
    root: Path,
    config: PersistenceLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    results: dict[str, bool] = {}
    for point in FaultPoint:
        substrate, _ = _route_graph(config, device=device, dtype=dtype)
        trial_root = root / point.value
        store = PackedCellStore(trial_root, page_capacity=2)
        store.commit_substrate(substrate)
        old = store.load_record(1)["transform"]["wave_cell_state"][
            "transform.encoder"
        ].clone()
        with torch.no_grad():
            substrate._cell(1).transform.encoder.add_(0.25)
        new = substrate._cell(1).transform.encoder.detach().cpu().clone()
        try:
            store.commit_cells(
                {1: substrate._cell(1)},
                fault_at=point,
                reason="fault-injected-learning",
            )
        except InjectedCrash:
            pass
        recovered = PackedCellStore(trial_root, page_capacity=2)
        visible = recovered.load_record(1)["transform"]["wave_cell_state"][
            "transform.encoder"
        ]
        expected = (
            new
            if point in {FaultPoint.AFTER_COMMIT, FaultPoint.AFTER_PUBLISH}
            else old
        )
        results[point.value] = torch.equal(visible, expected)

    substrate, _ = _route_graph(config, device=device, dtype=dtype)
    uid_root = root / "uid-retirement"
    uid_store = PackedCellStore(uid_root, page_capacity=2)
    uid_store.commit_substrate(substrate)
    uid = uid_store.allocate_uid()
    try:
        uid_store.commit_cells(
            {
                uid: _member(
                    uid,
                    config,
                    root=None,
                    device=device,
                    dtype=dtype,
                )
            },
            fault_at=FaultPoint.AFTER_WRITE,
            reason="fault-injected-birth",
        )
    except InjectedCrash:
        pass
    uid_recovered = PackedCellStore(uid_root, page_capacity=2)
    uid_retired = uid in uid_recovered.aborted_uids and uid_recovered.next_uid > uid

    substrate, _ = _route_graph(config, device=device, dtype=dtype)
    corrupt_root = root / "corruption"
    corrupt_store = PackedCellStore(corrupt_root, page_capacity=2)
    corrupt_store.commit_substrate(substrate)
    location = corrupt_store.manifest["uid_index"]["1"]
    declaration = next(
        item for item in corrupt_store.manifest["segments"]
        if item["segment_id"] == location["segment_id"]
    )
    path = corrupt_store.segment_root / declaration["path"]
    payload = bytearray(path.read_bytes())
    payload[len(payload) // 2] ^= 0xFF
    path.write_bytes(payload)
    corruption_failed_closed = False
    try:
        corrupt_store.load_record(1)
    except CorruptStoreError:
        corruption_failed_closed = True
    return {
        "boundaries": results,
        "all_boundaries_old_or_new": all(results.values()),
        "failed_birth_uid_retired": uid_retired,
        "corruption_failed_closed": corruption_failed_closed,
        "pass": all(results.values()) and uid_retired and corruption_failed_closed,
    }


def run_persistence_laboratory(
    config: PersistenceLabConfig | None = None,
    *,
    device: str | torch.device = "cpu",
    dtype: torch.dtype = torch.float32,
    scratch_root: str | Path | None = None,
) -> dict[str, Any]:
    config = config or PersistenceLabConfig()
    config.validate()
    target_device = torch.device(device)
    if target_device.type == "cpu" and dtype != torch.float32:
        raise ValueError("the CPU Stage-5 lab requires float32")
    if target_device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable")
    parent = Path(scratch_root) if scratch_root is not None else None
    if parent is not None:
        parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="campaign36c-stage5-",
        dir=parent,
    ) as temporary:
        root = Path(temporary)
        trials = [
            _page_trial(
                root / f"page-{capacity}",
                config,
                page_capacity=capacity,
                device=target_device,
                dtype=dtype,
            )
            for capacity in config.page_capacities
        ]
        faults = _fault_trials(
            root / "faults",
            config,
            device=target_device,
            dtype=dtype,
        )
    selected = min(
        trials,
        key=lambda item: (
            statistics.fmean(
                access["latency_ms"] / max(access["useful_byte_ratio"], 1e-9)
                for access in item["access_sets"]
            ),
            item["page_capacity"],
        ),
    )
    page_pass = all(item["pass"] for item in trials)
    exit_gate = page_pass and faults["pass"]
    return {
        "schema_version": CAMPAIGN36C_PERSISTENCE_LAB_RESULT_SCHEMA,
        "lab_config": asdict(config),
        "execution": {
            "device": str(target_device),
            "dtype": str(dtype),
            "scratch_filesystem": str(parent or Path(tempfile.gettempdir())),
        },
        "page_trials": trials,
        "fault_injection": faults,
        "selection": {
            "selected_page_capacity": selected["page_capacity"],
            "selection_basis": "measured_mean_latency_divided_by_useful_byte_ratio",
            "cold_resume_equivalence_pass": all(
                item["cold_restore_equivalent"]
                and item["optimizer_restore_equivalent"]
                and item["rng_restore_equivalent"]
                for item in trials
            ),
            "touched_tissue_io_independence_pass": all(
                item["disconnected_io_independent"] for item in trials
            ),
            "read_only_inference_pass": all(
                item["inference_read_only"] for item in trials
            ),
            "packed_storage_pass": page_pass,
            "crash_consistency_pass": faults["pass"],
            "stage5_exit_gate_met": exit_gate,
        },
    }


def merge_persistence_lab_results(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one persistence report is required")
    first = reports[0]
    if any(report["lab_config"] != first["lab_config"] for report in reports[1:]):
        raise ValueError("persistence reports must use identical laboratory bounds")
    return {
        "schema_version": CAMPAIGN36C_PERSISTENCE_LAB_RESULT_SCHEMA,
        "lab_config": first["lab_config"],
        "execution": {"devices": [report["execution"] for report in reports]},
        "device_reports": reports,
        "selection": {
            "selected_page_capacities": [
                report["selection"]["selected_page_capacity"] for report in reports
            ],
            "all_devices_pass": all(
                report["selection"]["stage5_exit_gate_met"] for report in reports
            ),
            "stage5_exit_gate_met": all(
                report["selection"]["stage5_exit_gate_met"] for report in reports
            ),
        },
    }


def write_persistence_lab_result(path: str | Path, result: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
