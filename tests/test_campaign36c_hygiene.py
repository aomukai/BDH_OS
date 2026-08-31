from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
import torch

from campaign36c.cell import StandaloneBDHCell
from campaign36c.config import BDHCellConfig, SparseWaveConfig
from campaign36c.hygiene import (
    HygieneAuthorization,
    HygieneController,
    HygienePolicyConfig,
    PurgeAuthorization,
    QuarantineReason,
    RevivalEvidence,
    RevivalRequest,
    RootedParticipationLedger,
    TissueLifecycle,
    UsefulCreditKind,
)
from campaign36c.hygiene_laboratory import (
    HygieneLabConfig,
    merge_hygiene_lab_results,
    run_hygiene_laboratory,
)
from campaign36c.persistence import FaultPoint, InjectedCrash, PackedCellStore
from campaign36c.wave import NeighborPort, SparseWaveSubstrate, WaveCell


WIDTH = 8


def member(uid: int, root: torch.Tensor | None = None) -> WaveCell:
    cell = WaveCell(
        StandaloneBDHCell(
            BDHCellConfig(
                width=WIDTH,
                rotary_pairs=2,
                initialization_seed=37_000 + uid,
            ),
            uid=uid,
        ),
        max_degree=8,
        max_fanout=4,
    )
    if root is not None:
        cell.receptor.tune_to(root)
    return cell


def graph() -> tuple[SparseWaveSubstrate, torch.Tensor]:
    root = torch.randn(1, 5, WIDTH, generator=torch.Generator().manual_seed(37_700))
    substrate = SparseWaveSubstrate(
        SparseWaveConfig(max_degree=8, max_fanout=4, initial_route_energy=64.0)
    )
    for uid in (1, 2, 3, 10, 11, 20, 21, 30):
        substrate.add_cell(member(uid, root))
    substrate.connect(1, 2, route_familiarity=0.95)
    substrate.connect(2, 3, route_familiarity=0.95)
    substrate.connect(10, 11, route_familiarity=0.95)
    substrate.connect(11, 10, route_familiarity=0.95)
    return substrate, root


def policy(*, sweeps: int = 1) -> HygienePolicyConfig:
    return HygienePolicyConfig(
        senescence_interval=2,
        rooted_use_window=2,
        minimum_senescence_sweeps=sweeps,
        newborn_grace_epochs=4,
        revival_grace_epochs=4,
        maximum_revival_candidates=2,
        minimum_revival_similarity=0.8,
        minimum_revival_improvement_fraction=0.05,
        maximum_revival_regression=0.01,
        minimum_revival_lineages=2,
        minimum_neighbor_acceptances=1,
    )


def authorization(*, allow: bool = True) -> HygieneAuthorization:
    return HygieneAuthorization(
        actor="test:hygiene",
        reason="bounded idle-cycle test",
        thought_closed=True,
        delayed_credit_closed=True,
        structural_work_closed=True,
        allow_quarantine=allow,
    )


def pressure(*, authorized: bool = True, enough_space: bool = False) -> PurgeAuthorization:
    return PurgeAuthorization(
        actor="test:operator",
        reason="measured packed-store pressure",
        operator_authorized=authorized,
        measured_free_bytes=200 if enough_space else 10,
        required_free_bytes=100,
        requested_reclaim_bytes=50,
    )


def digest(cell: WaveCell) -> str:
    buffer = io.BytesIO()
    # Contribution authority and ports legitimately change on revival; learned
    # transform/receptor content must not.
    torch.save({
        "transform": cell.transform.state_dict(),
        "receptor": cell.receptor.state_dict(),
    }, buffer)
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def prepare_controller(
    *, sweeps: int = 1,
) -> tuple[HygieneController, torch.Tensor]:
    substrate, root = graph()
    selected = policy(sweeps=sweeps)
    ledger = RootedParticipationLedger(selected)
    controller = HygieneController(substrate, ledger=ledger, policy=selected)
    ledger.record_useful_credit(
        20, epoch=9, kind=UsefulCreditKind.ROUTING
    )
    ledger.record_useful_credit(
        21, epoch=9, kind=UsefulCreditKind.ABSTENTION
    )
    ledger.ensure(30, current_epoch=8, newborn=True)
    return controller, root


def sweep(controller: HygieneController, *, epoch: int = 10):
    return controller.mark_and_sweep(
        current_epoch=epoch,
        ingress_uids=(1,),
        authorization=authorization(),
    )


def test_mark_and_sweep_quarantines_mutual_island_but_keeps_useful_noncontent_cells() -> None:
    controller, _ = prepare_controller()

    report = sweep(controller)

    assert report.quarantined_uids == (10, 11)
    assert set(report.preserved_routing_or_abstention_uids) == {20, 21}
    assert {1, 2, 3, 20, 21, 30}.issubset(set(report.marked_uids))
    assert not controller.substrate.has_active_uid(10)
    assert controller.ledger.records[10].lifecycle is TissueLifecycle.QUARANTINED


def test_quarantine_does_not_change_weights_and_stale_routes_fail_closed() -> None:
    controller, root = prepare_controller()
    before = digest(controller.substrate._cell(10))
    # A disabled historical reference does not make the island reachable.
    controller.substrate._cell(1).connect(NeighborPort(10, enabled=False))
    sweep(controller)
    assert digest(controller.quarantine[10].cell) == before

    controller.substrate._cell(1).ports[10] = NeighborPort(
        10, route_familiarity=0.99, enabled=True
    )
    result = controller.substrate.run_thought(root, ingress_uids=1)
    assert result.telemetry["stale_route_references"] == 1
    assert 10 not in result.telemetry["unique_uids"]


def test_senescence_is_a_candidate_state_before_deliberate_quarantine() -> None:
    controller, _ = prepare_controller(sweeps=2)

    first = sweep(controller)
    second = controller.mark_and_sweep(
        current_epoch=11,
        ingress_uids=(1,),
        authorization=authorization(),
    )

    assert first.quarantined_uids == ()
    assert controller.ledger.records[10].senescence_sweeps == 2
    assert second.quarantined_uids == (10, 11)


def test_pending_credit_obligation_and_protection_are_roots() -> None:
    substrate, _ = graph()
    selected = policy()
    ledger = RootedParticipationLedger(selected)
    controller = HygieneController(substrate, ledger=ledger, policy=selected)
    ledger.set_pending_credit(10, 1)
    ledger.set_obligation(11, "rollback:11")
    ledger.set_protected(20)

    report = controller.mark_and_sweep(
        current_epoch=10,
        ingress_uids=(1,),
        authorization=authorization(),
    )

    assert {10, 11, 20}.issubset(set(report.marked_uids))
    assert not {10, 11, 20}.intersection(report.quarantined_uids)


def test_background_island_chatter_cannot_create_rooted_vitality() -> None:
    controller, root = prepare_controller()
    result = controller.substrate.run_thought(root, ingress_uids=10)
    controller.ledger.record_thought(
        result,
        ingress_uids=(10,),
        substrate=controller.substrate,
        rooted=False,
    )

    report = sweep(controller)

    assert report.quarantined_uids == (10, 11)


def test_revival_search_is_bounded_and_returns_original_uid_in_probation() -> None:
    controller, _ = prepare_controller()
    sweep(controller)
    original = controller.quarantine[10]

    selected = controller.begin_revival(RevivalRequest(
        residual_signature=original.signature.clone(),
        current_epoch=12,
        sponsor_uid=2,
        claim_address="latent:old-route",
    ))
    assert selected.action == "shadow_revival"
    assert selected.uid == 10
    assert not controller.substrate.has_active_uid(10)
    assert controller.ledger.records[10].lifecycle is TissueLifecycle.REVIVAL_SHADOW

    decision = controller.complete_revival(
        RevivalEvidence(
            uid=10,
            improvement_fraction=0.2,
            maximum_established_regression=0.0,
            useful_present_contribution=True,
            evidence_lineages=("lineage:a", "lineage:b"),
            accepted_ports=(NeighborPort(2, route_familiarity=0.9),),
        ),
        current_epoch=13,
    )

    assert decision.admitted
    assert decision.uid == 10
    assert controller.substrate.has_active_uid(10)
    assert tuple(controller.substrate._cell(10).ports) == (2,)
    assert float(controller.substrate._cell(10).contribution_scale) == pytest.approx(0.1)
    assert controller.ledger.records[10].lifecycle is TissueLifecycle.REVIVAL_PROBATION


def test_revival_does_not_restore_harmful_tissue_authority() -> None:
    controller, _ = prepare_controller()
    controller.mark_and_sweep(
        current_epoch=10,
        ingress_uids=(1,),
        authorization=authorization(),
        quarantine_reasons={10: QuarantineReason.HARMFUL_CALIBRATION},
    )
    tissue = controller.quarantine[10]
    selected = controller.begin_revival(RevivalRequest(
        residual_signature=tissue.signature,
        current_epoch=12,
        sponsor_uid=2,
        claim_address="latent:diagnostic",
    ))
    decision = controller.complete_revival(
        RevivalEvidence(
            uid=10,
            improvement_fraction=1.0,
            maximum_established_regression=0.0,
            useful_present_contribution=True,
            evidence_lineages=("a", "b"),
            accepted_ports=(NeighborPort(2),),
        ),
        current_epoch=13,
    )

    assert selected.action == "diagnostic_shadow"
    assert not decision.admitted
    assert "diagnostic_only_reason" in decision.failed_gates
    assert 10 in controller.quarantine


def test_no_quarantine_match_permits_birth_only_after_bounded_search() -> None:
    controller, _ = prepare_controller()
    sweep(controller)
    signatures = torch.stack([
        controller.quarantine[uid].signature for uid in sorted(controller.quarantine)
    ])
    _, _, right = torch.linalg.svd(signatures, full_matrices=True)
    orthogonal = right[-1]

    decision = controller.begin_revival(RevivalRequest(
        residual_signature=orthogonal,
        current_epoch=12,
        sponsor_uid=2,
        claim_address="latent:new",
    ))

    assert decision.action == "permit_birth_after_bounded_quarantine_search"
    assert decision.scanned_candidates <= controller.policy.maximum_revival_candidates


def test_purge_requires_operator_authorized_pressure_and_never_reuses_uid() -> None:
    controller, _ = prepare_controller()
    sweep(controller)

    no_pressure = controller.purge((10,), authorization=pressure(enough_space=True))
    no_authority = controller.purge((10,), authorization=pressure(authorized=False))
    purged = controller.purge((10,), authorization=pressure())

    assert no_pressure.action == "refuse_without_authorized_pressure"
    assert no_authority.action == "refuse_without_authorized_pressure"
    assert purged.purged_uids == (10,)
    assert 10 in controller.substrate.retired_uids
    with pytest.raises(ValueError, match="retired UID"):
        controller.substrate.add_cell(member(10))


def test_quarantine_cold_restore_and_revival_preserve_uid_and_weights(tmp_path: Path) -> None:
    controller, _ = prepare_controller()
    store = PackedCellStore(tmp_path / "cold", page_capacity=2)
    store.commit_substrate(controller.substrate)
    sweep(controller)
    expected = digest(controller.quarantine[10].cell)
    store.commit_hygiene(
        controller.substrate,
        quarantine_cells=controller.quarantine_cells(),
        quarantine_metadata=controller.quarantine_metadata(),
    )

    cold_substrate, _, _, _ = store.load_substrate()
    q_cells, q_optimizers, q_configs, q_metadata = store.load_quarantine()
    cold = HygieneController(cold_substrate, policy=policy())
    cold.restore_quarantine(
        q_cells,
        q_metadata,
        optimizers=q_optimizers,
        optimizer_configs=q_configs,
    )
    assert digest(cold.quarantine[10].cell) == expected
    selected = cold.begin_revival(RevivalRequest(
        residual_signature=cold.quarantine[10].signature,
        current_epoch=12,
        sponsor_uid=2,
        claim_address="latent:cold-revival",
    ))
    assert selected.uid == 10
    revived = cold.complete_revival(
        RevivalEvidence(
            uid=10,
            improvement_fraction=0.2,
            maximum_established_regression=0.0,
            useful_present_contribution=True,
            evidence_lineages=("a", "b"),
            accepted_ports=(NeighborPort(2),),
        ),
        current_epoch=13,
    )
    assert revived.admitted and cold.substrate.has_active_uid(10)
    assert digest(cold.substrate._cell(10)) == expected


def test_persistent_purge_reclaims_quarantine_segment_and_retires_uid(tmp_path: Path) -> None:
    controller, _ = prepare_controller()
    store = PackedCellStore(tmp_path / "purge", page_capacity=2)
    store.commit_substrate(controller.substrate)
    sweep(controller)
    store.commit_hygiene(
        controller.substrate,
        quarantine_cells=controller.quarantine_cells(),
        quarantine_metadata=controller.quarantine_metadata(),
    )
    location = store.manifest["quarantine_index"]["10"]
    declaration = next(
        item for item in store.manifest["segments"]
        if item["segment_id"] == location["segment_id"]
    )
    old_path = store.segment_root / declaration["path"]
    assert old_path.exists()

    controller.purge((10, 11), authorization=pressure())
    store.commit_hygiene(
        controller.substrate,
        quarantine_cells=controller.quarantine_cells(),
        quarantine_metadata=controller.quarantine_metadata(),
        purge_uids=controller.purged_uids,
        reason="pressure-purge",
    )

    assert not old_path.exists()
    assert store.manifest["quarantine_index"] == {}
    assert {10, 11}.issubset(set(store.manifest["retired_uids"]))
    assert store.manifest["lifecycle"]["10"] == "purged"
    with pytest.raises(KeyError):
        store.load_quarantine_record(10)


@pytest.mark.parametrize(
    ("fault", "new_visible"),
    [
        (FaultPoint.AFTER_PREPARE, False),
        (FaultPoint.AFTER_WRITE, False),
        (FaultPoint.AFTER_VALIDATE, False),
        (FaultPoint.AFTER_COMMIT, True),
        (FaultPoint.AFTER_PUBLISH, True),
    ],
)
def test_quarantine_transaction_is_whole_old_or_new(
    tmp_path: Path,
    fault: FaultPoint,
    new_visible: bool,
) -> None:
    controller, _ = prepare_controller()
    store_root = tmp_path / fault.value
    store = PackedCellStore(store_root, page_capacity=2)
    store.commit_substrate(controller.substrate)
    sweep(controller)

    with pytest.raises(InjectedCrash):
        store.commit_hygiene(
            controller.substrate,
            quarantine_cells=controller.quarantine_cells(),
            quarantine_metadata=controller.quarantine_metadata(),
            fault_at=fault,
        )

    recovered = PackedCellStore(store_root, page_capacity=2)
    active = set(map(int, recovered.manifest["uid_index"]))
    quarantined = set(map(int, recovered.manifest.get("quarantine_index", {})))
    if new_visible:
        assert not {10, 11}.intersection(active)
        assert {10, 11}.issubset(quarantined)
    else:
        assert {10, 11}.issubset(active)
        assert not {10, 11}.intersection(quarantined)


def test_reduced_stage7_laboratory_meets_exit_gate(tmp_path: Path) -> None:
    result = run_hygiene_laboratory(
        HygieneLabConfig(width=8, sequence_length=5),
        scratch_root=tmp_path,
    )

    assert result["selection"]["stage7_exit_gate_met"] is True
    assert result["vitality_and_reachability"]["quarantined"] == [10, 11]
    assert result["revival"]["restored_uid"] == 10
    assert result["purge"]["old_quarantine_page_reclaimed"] is True


def test_hygiene_multi_device_merge_requires_identical_bounds(tmp_path: Path) -> None:
    report = run_hygiene_laboratory(
        HygieneLabConfig(width=8, sequence_length=5),
        scratch_root=tmp_path,
    )
    merged = merge_hygiene_lab_results([report, report])
    assert merged["selection"]["all_devices_pass"] is True

    changed = dict(report)
    changed["lab_config"] = {**report["lab_config"], "seed": 1}
    with pytest.raises(ValueError, match="identical"):
        merge_hygiene_lab_results([report, changed])
