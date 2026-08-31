from __future__ import annotations

from pathlib import Path

import pytest
import torch

from campaign36c.cell import StandaloneBDHCell
from campaign36c.config import BDHCellConfig, SparseWaveConfig
from campaign36c.structural import (
    CoAccessTracker,
    CompositeStage,
    ConditionalTrustProfile,
    FissionEvidence,
    FusionEvidence,
    FusionPolicyConfig,
    FusionProbe,
    HealingProbe,
    HealingAuthorization,
    ReversibleCompositeCell,
    StructuralController,
    StructuralPressure,
)
from campaign36c.structural_laboratory import (
    StructuralLabConfig,
    merge_structural_lab_results,
    run_structural_laboratory,
)
from campaign36c.persistence import FaultPoint, InjectedCrash, PackedCellStore
from campaign36c.wave import SparseWaveSubstrate, WaveCell


WIDTH = 8


def member(uid: int, root: torch.Tensor) -> WaveCell:
    cell = WaveCell(
        StandaloneBDHCell(
            BDHCellConfig(
                width=WIDTH,
                rotary_pairs=2,
                initialization_seed=66_000 + uid,
            ),
            uid=uid,
        ),
        max_degree=8,
        max_fanout=4,
    )
    cell.receptor.tune_to(root)
    return cell


def graph() -> tuple[SparseWaveSubstrate, torch.Tensor]:
    root = torch.randn(1, 5, WIDTH, generator=torch.Generator().manual_seed(36_600))
    substrate = SparseWaveSubstrate(
        SparseWaveConfig(
            max_degree=8,
            max_fanout=4,
            initial_route_energy=64.0,
        )
    )
    for uid in (1, 2, 3, 10):
        substrate.add_cell(member(uid, root))
    substrate.connect(1, 2, conductance=0.95, route_familiarity=0.95)
    substrate.connect(2, 3, conductance=0.9, route_familiarity=0.9)
    substrate.connect(10, 1, conductance=0.9, route_familiarity=0.9)
    return substrate, root


def evidence(left: int = 1, right: int = 2) -> FusionEvidence:
    return FusionEvidence(
        left_uid=left,
        right_uid=right,
        left_lifecycle="mature",
        right_lifecycle="mature",
        left_rigidity=0.9,
        right_rigidity=0.85,
        conductance=0.95,
        conditional_coparticipation=0.95,
        left_independent_use=0.05,
        right_independent_use=0.04,
        recent_error=0.001,
        measured_dispatch_savings=0.25,
        thought_epochs=(1, 2, 3),
        evidence_lineages=("source:a", "source:b"),
        trust_profiles=(
            ConditionalTrustProfile(1, "common", 0.7, 0.1, 0.05),
            ConditionalTrustProfile(2, "common", 0.8, 0.4, 0.2),
        ),
    )


def fuse_pair(
    substrate: SparseWaveSubstrate,
    root: torch.Tensor,
    *,
    policy: FusionPolicyConfig | None = None,
) -> tuple[StructuralController, int]:
    controller = StructuralController(substrate, next_uid=100, policy=policy)
    decision = controller.fuse(
        evidence(),
        (FusionProbe(root, 1), FusionProbe(root, 2)),
    )
    assert decision.admitted
    assert decision.successor_uid is not None
    return controller, decision.successor_uid


def valid_fission(uid: int) -> FissionEvidence:
    return FissionEvidence(
        composite_uid=uid,
        thought_epochs=(10, 11, 12),
        evidence_lineages=("lineage:a", "lineage:b"),
        regimes=("regime:old", "regime:new"),
        negative_transfer=0.2,
        left_regime_useful=True,
        right_regime_useful=True,
        left_boundary_regression=0.0,
        right_boundary_regression=0.0,
        routing_calibrated=True,
        shadow_specialists_win_after_cost=True,
        successor_obligations_closed=True,
    )


def test_coaccess_plans_physical_packing_without_identity_change() -> None:
    tracker = CoAccessTracker()
    for _ in range(5):
        tracker.observe((1, 7))
    tracker.observe((2, 3))

    assert tracker.count(1, 7) == 5
    assert tracker.repack_order((1, 2, 3, 7, 9))[:2] == (1, 7)


def test_pairwise_fusion_preserves_behavior_aliases_and_effort_accounting() -> None:
    substrate, root = graph()
    expected_left = substrate.run_thought(root, ingress_uids=1).state.detach().clone()
    expected_right = substrate.run_thought(root, ingress_uids=2).state.detach().clone()
    controller, successor = fuse_pair(substrate, root)

    observed_left = substrate.run_thought(root, ingress_uids=1)
    observed_right = substrate.run_thought(root, ingress_uids=2)
    deduplicated = substrate.run_thought(root, ingress_uids=(1, 2))

    torch.testing.assert_close(observed_left.state, expected_left, atol=0, rtol=0)
    torch.testing.assert_close(observed_right.state, expected_right, atol=0, rtol=0)
    assert substrate.resolve_uid(1) == successor
    assert substrate.resolve_uid(2) == successor
    assert observed_left.telemetry["total_activations"] == 2
    assert observed_left.telemetry["composite_activations"] == 1
    assert observed_left.telemetry["constituent_full_transforms"] == 3
    assert observed_left.telemetry["saved_dispatch_boundaries"] == 1
    assert deduplicated.telemetry["activation_sequence"].count(successor) == 1
    assert substrate._cell(10).ports[successor].entry_alias_uid == 1
    assert controller.events[-1].pressure is StructuralPressure.FUSION


def test_trust_profiles_remain_conditional_and_do_not_sum_authority() -> None:
    substrate, root = graph()
    _, successor = fuse_pair(substrate, root)
    composite = substrate._cell(successor)
    assert isinstance(composite, ReversibleCompositeCell)

    trust = composite.inherited_trust("common")

    assert trust == {
        "positive_authority": 0.8,
        "negative_history": 0.4,
        "calibration_error": 0.2,
    }
    assert substrate.resolve_credit_target(1) == (successor, 1)


def test_newborn_or_merely_coaccessed_tissue_cannot_fuse() -> None:
    substrate, root = graph()
    controller = StructuralController(substrate, next_uid=100)
    newborn = evidence()
    newborn = FusionEvidence(**{**newborn.__dict__, "left_lifecycle": "probationary"})

    decision = controller.fuse(
        newborn,
        (FusionProbe(root, 1), FusionProbe(root, 2)),
    )

    assert not decision.admitted
    assert "left_mature" in decision.failed_gates
    assert set(map(int, substrate.cells.keys())) == {1, 2, 3, 10}


def test_fusion_bound_prevents_recursive_dense_supercell() -> None:
    substrate, root = graph()
    policy = FusionPolicyConfig(maximum_composite_leaves=2)
    controller, successor = fuse_pair(substrate, root, policy=policy)
    second = evidence(successor, 3)

    decision = controller.fuse(
        second,
        (FusionProbe(root, successor), FusionProbe(root, 3)),
    )

    assert not decision.admitted
    assert "leaf_budget" in decision.failed_gates
    assert set(map(int, substrate.cells.keys())) == {3, 10, successor}


def test_early_fission_restores_constituents_and_retires_successor() -> None:
    substrate, root = graph()
    expected = substrate.run_thought(root, ingress_uids=10).state.detach().clone()
    controller, successor = fuse_pair(substrate, root)

    decision = controller.fission(valid_fission(successor))
    observed = substrate.run_thought(root, ingress_uids=10).state

    assert decision.admitted
    assert decision.restored_uids == (1, 2)
    assert successor in substrate.retired_uids
    assert successor not in substrate.aliases
    assert substrate.resolve_uid(1) == 1
    assert substrate.resolve_uid(2) == 2
    assert substrate._cell(10).ports[1].destination_uid == 1
    torch.testing.assert_close(observed, expected, atol=0, rtol=0)


def test_healed_rigid_composite_is_repaired_or_budded_not_fake_fissioned() -> None:
    substrate, root = graph()
    controller, successor = fuse_pair(substrate, root)
    composite = substrate._cell(successor)
    assert isinstance(composite, ReversibleCompositeCell)
    with torch.no_grad():
        composite.transform.healing_adapter.weight.copy_(
            torch.randn(
                WIDTH,
                WIDTH,
                generator=torch.Generator().manual_seed(36_601),
            )
        )
        composite.transform.healing_strength.fill_(1.0)
    target = composite.execute_composite(
        root, entry_alias_uid=1, attention_mask=None
    ).detach()

    audit = controller.audit_rigidity(
        successor,
        (HealingProbe(root, target, 1),),
    )
    decision = controller.fission(valid_fission(successor))

    assert not audit.extractable
    assert audit.stage is CompositeStage.RIGID
    assert not decision.admitted
    assert decision.action == "repair_in_place_or_bud"
    assert set(map(int, substrate.cells.keys())) == {3, 10, successor}


def test_participation_conditioned_rigidity_ignores_inactivity_and_error_reopens() -> None:
    substrate, _ = graph()
    controller = StructuralController(substrate, next_uid=100)
    controller.rigidity.set(1, 0.5)

    assert controller.rigidity.record(1, participated=False) == 0.5
    assert controller.rigidity.record(1, participated=True, low_error=True) == 0.55
    assert controller.rigidity.record(1, participated=True, implicated_error=True) == 0.4


def test_semantic_healing_is_a_separately_disabled_transition() -> None:
    substrate, root = graph()
    controller, successor = fuse_pair(substrate, root)
    composite = substrate._cell(successor)
    assert isinstance(composite, ReversibleCompositeCell)
    target = composite.execute_composite(
        root, entry_alias_uid=1, attention_mask=None
    ).detach()

    with pytest.raises(RuntimeError, match="semantic healing is disabled"):
        controller.train_healing(
            successor,
            (HealingProbe(root, target, 1),),
            authorization=HealingAuthorization(
                equivalent_addressed_effects=True,
                no_material_independent_residual=True,
                shadow_consolidation_passed=True,
                evidence_lineages=("source:a", "source:b"),
            ),
        )


def test_universal_invalidation_replaces_instead_of_fissioning() -> None:
    substrate, root = graph()
    controller, successor = fuse_pair(substrate, root)
    invalid = FissionEvidence(
        **{**valid_fission(successor).__dict__, "universally_invalid": True}
    )

    decision = controller.fission(invalid)

    assert not decision.admitted
    assert decision.action == "replace_whole_composite"
    assert controller.events[-1].pressure is StructuralPressure.REPLACEMENT


def test_open_successor_obligations_block_ambiguous_fission() -> None:
    substrate, root = graph()
    controller, successor = fuse_pair(substrate, root)
    open_credit = FissionEvidence(
        **{**valid_fission(successor).__dict__, "successor_obligations_closed": False}
    )

    decision = controller.fission(open_credit)

    assert not decision.admitted
    assert "obligations_closed" in decision.failed_gates
    assert successor in set(map(int, substrate.cells.keys()))


def test_composite_aliases_fusion_tree_and_fission_cold_resume(
    tmp_path: Path,
) -> None:
    substrate, root = graph()
    store = PackedCellStore(tmp_path / "structural-store", page_capacity=2)
    store.commit_substrate(substrate, reason="before-fusion")
    expected = substrate.run_thought(root, ingress_uids=10).state.detach().clone()
    controller, successor = fuse_pair(substrate, root)
    store.commit_substrate(substrate, reason="reversible-fusion")

    fused, _, _, anatomy = store.load_substrate()
    fused_output = fused.run_thought(root, ingress_uids=10).state
    fused_cell = fused._cell(successor)

    assert isinstance(fused_cell, ReversibleCompositeCell)
    assert set(map(int, fused.cells.keys())) == {3, 10, successor}
    assert fused.aliases == {1: successor, 2: successor}
    assert anatomy[successor]["lineage"]["fusion_tree"]["kind"] == "reversible_composite"
    assert fused_cell.structural_history[-1]["pressure"] == "fusion"
    torch.testing.assert_close(fused_output, expected, atol=0, rtol=0)

    restored_controller = StructuralController(fused, next_uid=successor + 1)
    decision = restored_controller.fission(valid_fission(successor))
    assert decision.admitted
    store.commit_substrate(fused, reason="early-fission")
    split, _, _, _ = store.load_substrate()

    assert set(map(int, split.cells.keys())) == {1, 2, 3, 10}
    assert split.aliases == {}
    assert successor in split.retired_uids
    assert store.inventory()[1].record_generation == 2
    assert store.inventory()[2].record_generation == 2
    assert split._cell(1).structural_history[-1]["pressure"] == "fission"
    torch.testing.assert_close(
        split.run_thought(root, ingress_uids=10).state,
        expected,
        atol=0,
        rtol=0,
    )


@pytest.mark.parametrize(
    ("fault", "new_visible"),
    [
        (FaultPoint.AFTER_VALIDATE, False),
        (FaultPoint.AFTER_COMMIT, True),
    ],
)
def test_persistent_fusion_is_old_or_new_never_hybrid(
    tmp_path: Path,
    fault: FaultPoint,
    new_visible: bool,
) -> None:
    substrate, root = graph()
    store_root = tmp_path / fault.value
    store = PackedCellStore(store_root, page_capacity=2)
    store.commit_substrate(substrate)
    _, successor = fuse_pair(substrate, root)

    with pytest.raises(InjectedCrash):
        store.commit_substrate(
            substrate,
            reason="fault-injected-fusion",
            fault_at=fault,
        )

    recovered = PackedCellStore(store_root, page_capacity=2)
    active = set(map(int, recovered.manifest["uid_index"]))
    if new_visible:
        assert active == {3, 10, successor}
        assert recovered.manifest["aliases"] == {
            "1": successor,
            "2": successor,
        }
    else:
        assert active == {1, 2, 3, 10}
        assert recovered.manifest["aliases"] == {}


def test_stage6_structural_laboratory_meets_bounded_exit_gate(
    tmp_path: Path,
) -> None:
    report = run_structural_laboratory(
        StructuralLabConfig(
            width=16,
            rotary_pairs=2,
            sequence_length=6,
            benchmark_warmup=1,
            benchmark_iterations=3,
            behavior_tolerance=1e-5,
        ),
        scratch_root=tmp_path,
    )

    assert report["selection"]["stage6_exit_gate_met"] is True
    assert report["packing"]["after_page_loads"] == 1
    assert report["packing"]["before_page_loads"] == 2
    assert report["fusion"]["after_saved_dispatch_boundaries"] == 1
    assert report["fusion"]["fission"]["admitted"] is True
    assert report["rigidity_and_gates"]["rigid_fission"]["action"] == (
        "repair_in_place_or_bud"
    )
    assert report["fault_injection"]["pass"] is True

    merged = merge_structural_lab_results([report, report])
    assert merged["selection"]["all_devices_pass"] is True
