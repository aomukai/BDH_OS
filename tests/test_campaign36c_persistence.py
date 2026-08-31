from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
import torch

from campaign36c import (
    BDHCellConfig,
    CellOptimizerConfig,
    CorruptStoreError,
    DirtyCellBuffer,
    FaultPoint,
    GraphResidencyManager,
    InjectedCrash,
    NeighborPort,
    PackedCellStore,
    PersistenceLabConfig,
    ResidencyTier,
    SparseWaveConfig,
    SparseWaveSubstrate,
    StandaloneBDHCell,
    WaveCell,
    build_cell_optimizer,
    merge_persistence_lab_results,
    run_persistence_laboratory,
)


WIDTH = 8


def member(uid: int, state: torch.Tensor | None = None) -> WaveCell:
    cell = WaveCell(
        StandaloneBDHCell(
            BDHCellConfig(
                width=WIDTH,
                rotary_pairs=2,
                initialization_seed=55_000 + uid,
            ),
            uid=uid,
        ),
        max_degree=8,
        max_fanout=4,
    )
    if state is not None:
        cell.receptor.tune_to(state)
    return cell


def graph(disconnected: int = 3) -> tuple[SparseWaveSubstrate, torch.Tensor]:
    root = torch.randn(1, 5, WIDTH, generator=torch.Generator().manual_seed(36_500))
    substrate = SparseWaveSubstrate(
        SparseWaveConfig(max_degree=8, max_fanout=4)
    )
    for uid in (1, 2, 3):
        substrate.add_cell(member(uid, root))
    for offset in range(disconnected):
        substrate.add_cell(member(1_000 + offset))
    substrate.connect(1, 2)
    substrate.connect(2, 3)
    return substrate, root


def state_digest(value: object) -> str:
    buffer = io.BytesIO()
    torch.save(value, buffer)
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def file_fingerprints(root: Path) -> dict[str, tuple[int, str]]:
    result = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        payload = path.read_bytes()
        result[path.relative_to(root).as_posix()] = (
            path.stat().st_mtime_ns,
            hashlib.sha256(payload).hexdigest(),
        )
    return result


def test_packed_cold_restore_preserves_graph_cell_optimizer_and_anatomy(
    tmp_path: Path,
) -> None:
    substrate, root = graph(disconnected=3)
    optimizer_config = CellOptimizerConfig(learning_rate=0.01)
    optimizer = build_cell_optimizer(
        substrate._cell(2).transform.parameters(), optimizer_config
    )
    optimizer.zero_grad(set_to_none=True)
    substrate._cell(2).transform(root).square().mean().backward()
    optimizer.step()
    expected = substrate.run_thought(root, ingress_uids=1).state.detach().clone()
    optimizer_digest = state_digest(optimizer.state_dict())
    store = PackedCellStore(tmp_path / "store", page_capacity=2)

    commit = store.commit_substrate(
        substrate,
        optimizers={2: optimizer},
        optimizer_configs={2: optimizer_config},
        metadata={
            2: {
                "lifecycle": "admitted",
                "route_ring": [{"thought": 7, "destination": 3}],
                "predecessor_aliases": [2002],
                "evidence_influence": {"source-a": 0.7},
            }
        },
    )
    restored, optimizers, configs, anatomy = store.load_substrate()
    observed = restored.run_thought(root, ingress_uids=1).state

    assert len(commit.segment_ids) < len(substrate.cells)
    torch.testing.assert_close(observed, expected, atol=0, rtol=0)
    assert state_digest(optimizers[2].state_dict()) == optimizer_digest
    assert configs[2] == optimizer_config
    assert anatomy[2]["route_ring"] == [{"thought": 7, "destination": 3}]
    assert anatomy[2]["lineage"]["predecessor_aliases"] == [2002]
    assert store.inventory() == store.rebuild_index_from_segments()


@pytest.mark.parametrize(
    ("fault_point", "new_visible"),
    [
        (FaultPoint.AFTER_PREPARE, False),
        (FaultPoint.AFTER_WRITE, False),
        (FaultPoint.AFTER_VALIDATE, False),
        (FaultPoint.AFTER_COMMIT, True),
        (FaultPoint.AFTER_PUBLISH, True),
    ],
)
def test_fault_injection_exposes_whole_old_or_new_graph_only(
    tmp_path: Path,
    fault_point: FaultPoint,
    new_visible: bool,
) -> None:
    substrate, _ = graph(disconnected=1)
    store_root = tmp_path / fault_point.value
    store = PackedCellStore(store_root, page_capacity=2)
    store.commit_substrate(substrate)
    old_encoder = store.load_record(1)["transform"]["wave_cell_state"][
        "transform.encoder"
    ].clone()
    with torch.no_grad():
        substrate._cell(1).transform.encoder.add_(0.25)
    new_encoder = substrate._cell(1).transform.encoder.detach().clone()

    with pytest.raises(InjectedCrash):
        store.commit_cells(
            {1: substrate._cell(1)},
            reason="fault-injected-learning",
            fault_at=fault_point,
        )

    recovered = PackedCellStore(store_root, page_capacity=2)
    visible = recovered.load_record(1)["transform"]["wave_cell_state"][
        "transform.encoder"
    ]
    torch.testing.assert_close(
        visible,
        new_encoder if new_visible else old_encoder,
        atol=0,
        rtol=0,
    )
    restored, _, _, _ = recovered.load_substrate()
    assert set(map(int, restored.cells.keys())) == {1, 2, 3, 1000}


def test_uid_from_failed_durable_birth_is_retired_and_never_reused(
    tmp_path: Path,
) -> None:
    substrate, _ = graph(disconnected=0)
    store_root = tmp_path / "uid-retirement"
    store = PackedCellStore(store_root, page_capacity=2)
    store.commit_substrate(substrate)
    uid = store.allocate_uid()
    newborn = member(uid)

    with pytest.raises(InjectedCrash):
        store.commit_cells(
            {uid: newborn},
            fault_at=FaultPoint.AFTER_WRITE,
            reason="failed-birth",
        )

    recovered = PackedCellStore(store_root, page_capacity=2)
    assert uid in recovered.aborted_uids
    assert recovered.allocate_uid() > uid
    assert str(uid) not in recovered.manifest["uid_index"]


def test_corrupt_page_fails_closed(tmp_path: Path) -> None:
    substrate, _ = graph(disconnected=0)
    store = PackedCellStore(tmp_path / "corrupt", page_capacity=2)
    store.commit_substrate(substrate)
    location = store.manifest["uid_index"]["1"]
    declaration = next(
        item for item in store.manifest["segments"]
        if item["segment_id"] == location["segment_id"]
    )
    path = store.segment_root / declaration["path"]
    payload = bytearray(path.read_bytes())
    payload[len(payload) // 2] ^= 0xFF
    path.write_bytes(payload)

    with pytest.raises(CorruptStoreError, match="checksum"):
        store.load_record(1)


def test_dirty_updates_coalesce_snapshot_restores_and_repack_preserves_identity(
    tmp_path: Path,
) -> None:
    substrate, root = graph(disconnected=3)
    store = PackedCellStore(tmp_path / "lifecycle", page_capacity=2)
    store.commit_substrate(substrate)
    expected = substrate.run_thought(root, ingress_uids=1).state.detach().clone()
    snapshot_generations = {
        uid: location.record_generation for uid, location in store.inventory().items()
    }
    store.create_snapshot("before-learning")
    buffer = DirtyCellBuffer(store)
    for _ in range(3):
        with torch.no_grad():
            substrate._cell(2).transform.decoder.add_(0.01)
        buffer.mark(substrate._cell(2))
    result = buffer.flush()
    assert result is not None
    assert buffer.update_events == 3
    assert result.written_uids == (2,)
    assert store.inventory()[2].record_generation == snapshot_generations[2] + 1

    locations_before = store.inventory()
    generations_before = {
        uid: value.record_generation for uid, value in locations_before.items()
    }
    store.repack(reversed(sorted(locations_before)))
    locations_after = store.inventory()
    assert locations_after == store.rebuild_index_from_segments()
    assert {
        uid: value.record_generation for uid, value in locations_after.items()
    } == generations_before
    assert any(
        locations_after[uid].segment_id != locations_before[uid].segment_id
        for uid in locations_before
    )

    store.restore_snapshot("before-learning")
    restored, _, _, _ = store.load_substrate()
    observed = restored.run_thought(root, ingress_uids=1).state
    torch.testing.assert_close(observed, expected, atol=0, rtol=0)
    assert {
        uid: value.record_generation for uid, value in store.inventory().items()
    } == snapshot_generations


def test_graph_halo_cache_avoids_repeat_io_and_disconnected_growth(
    tmp_path: Path,
) -> None:
    substrate, _ = graph(disconnected=0)
    store = PackedCellStore(tmp_path / "residency", page_capacity=20)
    store.commit_substrate(substrate)
    before_inference = file_fingerprints(store.root)
    manager = GraphResidencyManager(store)

    manager.activate(1, halo_hops=2)
    cold_loads = manager.telemetry.page_loads
    cold_bytes = manager.telemetry.bytes_read
    manager.activate(1, halo_hops=2)

    assert cold_loads == 1
    assert manager.telemetry.page_loads == cold_loads
    assert manager.telemetry.cache_hits >= 1
    assert manager.tier_for_uid(1) is ResidencyTier.HOT
    assert manager.quiescent
    assert manager.telemetry.persistent_writes == 0
    assert file_fingerprints(store.root) == before_inference

    disconnected = {uid: member(uid) for uid in range(1_000, 1_100)}
    store.commit_cells(disconnected, reason="disconnected-growth")
    after_growth = file_fingerprints(store.root)
    grown_manager = GraphResidencyManager(store)
    grown_manager.activate(1, halo_hops=2)

    assert grown_manager.telemetry.page_loads == cold_loads
    assert grown_manager.telemetry.bytes_read == cold_bytes
    assert grown_manager.telemetry.persistent_writes == 0
    assert file_fingerprints(store.root) == after_growth
    assert grown_manager.pending_uids == ()


def test_dormant_tissue_is_resident_metadata_but_never_prefetched(
    tmp_path: Path,
) -> None:
    substrate, _ = graph(disconnected=0)
    store = PackedCellStore(tmp_path / "dormant", page_capacity=2)
    store.commit_substrate(substrate, metadata={2: {"lifecycle": "dormant"}})
    manager = GraphResidencyManager(store)

    manager.activate(1, halo_hops=2)

    assert manager.tier_for_uid(2) is ResidencyTier.DORMANT
    assert manager.telemetry.prefetched_uids == 0
    with pytest.raises(RuntimeError, match="dormant tissue"):
        manager.activate(2)


def test_stage5_persistence_laboratory_meets_bounded_exit_gate(
    tmp_path: Path,
) -> None:
    config = PersistenceLabConfig(
        width=16,
        rotary_pairs=2,
        sequence_length=6,
        disconnected_cells=20,
        page_capacities=(2, 10, 20),
        access_set_sizes=(2, 10, 20),
        dirty_update_events=4,
    )
    report = run_persistence_laboratory(
        config,
        scratch_root=tmp_path,
    )

    assert report["selection"]["stage5_exit_gate_met"] is True
    assert report["selection"]["cold_resume_equivalence_pass"] is True
    assert report["selection"]["touched_tissue_io_independence_pass"] is True
    assert report["selection"]["read_only_inference_pass"] is True
    assert report["fault_injection"]["all_boundaries_old_or_new"] is True
    assert report["fault_injection"]["failed_birth_uid_retired"] is True
    assert all(item["one_file_per_cell_avoided"] for item in report["page_trials"])

    merged = merge_persistence_lab_results([report, report])
    assert merged["selection"]["all_devices_pass"] is True
