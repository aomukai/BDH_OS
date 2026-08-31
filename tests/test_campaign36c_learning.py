from __future__ import annotations

import torch
import torch.nn.functional as F

from campaign36c import (
    BDHCellConfig,
    Campaign36COrganism,
    CellOptimizerConfig,
    CreditGrade,
    CreditPolicyConfig,
    ExecutedSubgraphTrainer,
    LearningExample,
    LearningLabConfig,
    OrganismConfig,
    PatchReducer,
    PatchRelationship,
    ReceiptDisposition,
    RetentionProbe,
    ResultGrade,
    SparseWaveConfig,
    SparseWaveSubstrate,
    StandaloneBDHCell,
    WaveCell,
    make_latent_patch,
    merge_learning_lab_results,
    run_learning_laboratory,
)


WIDTH = 8


def root(seed: int = 36_300) -> torch.Tensor:
    return torch.randn(1, 5, WIDTH, generator=torch.Generator().manual_seed(seed))


def member(uid: int) -> WaveCell:
    return WaveCell(
        StandaloneBDHCell(
            BDHCellConfig(
                width=WIDTH,
                rotary_pairs=2,
                initialization_seed=36_400 + uid,
            ),
            uid=uid,
        ),
        max_degree=8,
        max_fanout=4,
    )


def chain() -> tuple[SparseWaveSubstrate, torch.Tensor]:
    substrate = SparseWaveSubstrate(
        SparseWaveConfig(
            initial_route_energy=32,
            max_degree=8,
            max_fanout=4,
        )
    )
    state = root()
    for uid in (1, 2, 3, 90, 91):
        cell = member(uid)
        if uid != 90:
            cell.receptor.tune_to(state)
        else:
            cell.receptor.tune_to(-state)
        substrate.add_cell(cell)
    substrate.connect(1, 2)
    substrate.connect(2, 3)
    substrate.connect(1, 90, route_familiarity=0.0)
    return substrate, state


def example(state: torch.Tensor, target: torch.Tensor | None = None) -> LearningExample:
    direction = torch.linspace(-0.5, 0.5, WIDTH).view(1, 1, WIDTH)
    expected = target if target is not None else F.layer_norm(state + direction, (WIDTH,))
    return LearningExample(
        root_state=state,
        target_state=expected,
        ingress_uids=1,
        claim_address="synthetic:route-effect",
        evidence_lineage=("observation:route-1",),
    )


def snapshot(cell: WaveCell) -> dict[str, torch.Tensor]:
    return {key: value.detach().clone() for key, value in cell.state_dict().items()}


def assert_snapshot(cell: WaveCell, expected: dict[str, torch.Tensor]) -> None:
    observed = cell.state_dict()
    assert observed.keys() == expected.keys()
    for key in expected:
        torch.testing.assert_close(observed[key], expected[key], atol=0, rtol=0)


def patch(
    patch_id: str,
    delta: torch.Tensor,
    *,
    claim: str = "swan:colour",
    lineage: tuple[str, ...] = ("observation:one",),
):
    return make_latent_patch(
        patch_id=patch_id,
        source_uid=int(patch_id[-1]),
        base_version="root",
        claim_address=claim,
        expected_merge_mode="single_value",
        state_before=torch.ones_like(delta),
        operation_delta=delta,
        dependency_ids=(),
        evidence_lineage=lineage,
        route_provenance=((1,),),
        ownership=0.9,
        coverage=0.9,
        footprint_size=WIDTH,
    )


def test_patch_reducer_deduplicates_forks_composes_and_preserves_conflicts() -> None:
    reducer = PatchReducer()
    positive = torch.ones(1, 2, WIDTH)
    same_fork = patch("p1", positive)
    copied_fork = patch("p2", positive)
    independent = patch("p3", positive, lineage=("observation:two",))
    complementary = patch("p4", positive, claim="swan:location")
    contrary = patch("p5", -positive)

    assert reducer.classify(same_fork, copied_fork) is PatchRelationship.EQUIVALENT
    assert reducer.classify(same_fork, independent) is PatchRelationship.REINFORCING
    assert reducer.classify(same_fork, complementary) is PatchRelationship.COMPLEMENTARY
    assert reducer.classify(same_fork, contrary) is PatchRelationship.CONTRADICTORY
    deduplicated = reducer.reduce((same_fork, copied_fork, independent))
    assert deduplicated.grade is ResultGrade.SUPPORTED
    assert len(deduplicated.consensus_patch_ids) == 1
    composed = reducer.reduce((same_fork, complementary))
    assert len(composed.consensus_patch_ids) == 2
    disputed = reducer.reduce((same_fork, contrary))
    assert disputed.grade is ResultGrade.UNRESOLVED
    assert len(disputed.hypotheses) == 2


def test_wave_emits_eligibility_receipts_and_dependency_aware_resolution() -> None:
    substrate, state = chain()
    result = substrate.run_thought(
        state,
        ingress_uids=1,
        claim_address="synthetic:route-effect",
        evidence_lineage=("observation:route-1",),
    )

    assert [record.uid for record in result.eligibility] == [1, 2, 3]
    assert len(result.patches) == 3
    assert result.resolution.grade is ResultGrade.SUPPORTED
    assert len(result.resolution.retained_patch_ids) == 3
    dispositions = {
        (record.source_uid, record.destination_uid): record.disposition
        for record in result.receipts
    }
    assert dispositions[(1, 2)] is ReceiptDisposition.FORWARDED
    assert dispositions[(2, 3)] is ReceiptDisposition.ABSORBED
    assert dispositions[(1, 90)] is ReceiptDisposition.REJECTED
    assert result.patches[-1].dependency_ids == tuple(
        patch.patch_id for patch in result.patches[:-1]
    )


def test_executed_route_learns_while_inactive_tissue_is_bit_identical() -> None:
    substrate, state = chain()
    trainer = ExecutedSubgraphTrainer(
        substrate,
        optimizer_config=CellOptimizerConfig(learning_rate=0.03),
    )
    task = example(state)
    inactive_rejected = snapshot(substrate.cells["90"])
    inactive_disconnected = snapshot(substrate.cells["91"])
    loss_before = trainer.evaluate_loss(task)
    last = None
    for _ in range(48):
        last = trainer.train_step(task)
    assert last is not None
    loss_after = trainer.evaluate_loss(task)

    assert loss_after < loss_before * 0.8
    assert trainer.optimizer_uids == (1, 2, 3)
    assert set(last.updated_uids) == {1, 2, 3}
    assert {(1, 2), (2, 3)}.issubset(set(last.updated_edges))
    assert any(event.grade is CreditGrade.POSITIVE for event in last.credit_events)
    assert_snapshot(substrate.cells["90"], inactive_rejected)
    assert_snapshot(substrate.cells["91"], inactive_disconnected)


def test_unknown_outcome_expires_without_parameters_or_optimizer_state() -> None:
    substrate, state = chain()
    trainer = ExecutedSubgraphTrainer(
        substrate,
        optimizer_config=CellOptimizerConfig(learning_rate=0.03),
    )
    before = {uid: snapshot(substrate.cells[str(uid)]) for uid in (1, 2, 3, 90, 91)}

    result = trainer.train_step(example(state), outcome_available=False)

    assert result.outcome_applied is False
    assert result.updated_uids == ()
    assert trainer.optimizer_uids == ()
    assert all(event.grade is CreditGrade.PENDING for event in result.credit_events)
    for uid, expected in before.items():
        assert_snapshot(substrate.cells[str(uid)], expected)


def test_correct_result_does_not_reinforce_declared_invalid_dependency() -> None:
    substrate, state = chain()
    trainer = ExecutedSubgraphTrainer(substrate)
    invalid_before = snapshot(substrate.cells["2"])

    result = trainer.train_step(example(state), invalid_dependency_uids=(2,))

    assert 2 not in result.updated_uids
    assert_snapshot(substrate.cells["2"], invalid_before)
    assert any(
        event.grade is CreditGrade.NEGATIVE
        and event.reason_code == "correct_result_invalid_dependency"
        for event in result.credit_events
    )


def test_low_ownership_resolved_elsewhere_updates_boundary_not_content() -> None:
    substrate, state = chain()
    trainer = ExecutedSubgraphTrainer(
        substrate,
        credit_policy=CreditPolicyConfig(content_ownership_threshold=0.9999),
    )
    content_before = snapshot(substrate.cells["2"].transform)
    bias_before = substrate.cells["2"].receptor.calibration_bias.detach().clone()

    result = trainer.train_step(example(state), resolved_elsewhere=True)

    assert 2 not in result.updated_uids
    assert 2 in result.updated_receptor_uids
    assert_snapshot(substrate.cells["2"].transform, content_before)
    assert substrate.cells["2"].receptor.calibration_bias < bias_before
    assert any(
        event.reason_code == "resolved_elsewhere_boundary_only"
        for event in result.credit_events
    )


def test_retention_guard_rolls_back_a_conflicting_update_atomically() -> None:
    substrate, state = chain()
    trainer = ExecutedSubgraphTrainer(
        substrate,
        optimizer_config=CellOptimizerConfig(learning_rate=0.03),
    )
    learned = example(state)
    for _ in range(48):
        trainer.train_step(learned)
    protected_loss = trainer.evaluate_loss(learned)
    before = {uid: snapshot(substrate.cells[str(uid)]) for uid in (1, 2, 3)}
    conflict = example(state, target=-learned.target_state)

    result = trainer.train_step(
        conflict,
        retention_probes=(
            RetentionProbe(learned, maximum_absolute_regression=0.0),
        ),
    )

    assert result.retention_rollback is True
    assert result.updated_uids == ()
    assert trainer.evaluate_loss(learned) == protected_loss
    for uid, expected in before.items():
        assert_snapshot(substrate.cells[str(uid)], expected)


def test_stage3_learning_laboratory_meets_bounded_exit_gate() -> None:
    config = LearningLabConfig(
        width=16,
        rotary_pairs=2,
        sequence_length=6,
        training_examples=4,
        evaluation_examples=2,
        training_steps=32,
        black_swan_steps=24,
        common_replay_steps=4,
        disconnected_cells=4,
        learning_rate=0.03,
        minimum_heldout_improvement_fraction=0.01,
    )
    report = run_learning_laboratory(config)

    assert report["selection"]["stage3_exit_gate_met"] is True
    assert report["selection"]["inactive_tissue_untouched_pass"] is True
    assert report["selection"]["black_swan_survival_pass"] is True
    assert report["containment"]["retention_rollback"] is True
    assert report["black_swan"]["reduction"]["rare_evidence_retained"] is True
    assert "not claimed as Hebbian" in report["selection"]["learning_rule"]

    merged = merge_learning_lab_results([report, report])
    assert merged["selection"]["all_devices_pass"] is True


def test_external_language_loss_creates_state_only_for_executed_retained_cells() -> None:
    organism = Campaign36COrganism.embryo(
        OrganismConfig(
            width=WIDTH,
            core_layers=1,
            core_heads=2,
            core_multiplier=1,
            seed_ingress_cells=2,
            cell_rotary_pairs=2,
        )
    )
    disconnected = member(99)
    organism.substrate.add_cell(disconnected)
    untouched = snapshot(disconnected)
    trainer = ExecutedSubgraphTrainer(organism.substrate)
    thought = organism.think(
        root(),
        claim_address="visual:test",
        evidence_lineage=("asset:test",),
    )

    credit = trainer.apply_external_loss(
        thought.result,
        thought.result.state.float().square().mean(),
        claim_address="visual:test",
        evidence_lineage=("asset:test",),
    )

    assert set(credit.updated_uids) == {0, 1}
    assert trainer.optimizer_uids == (0, 1)
    assert_snapshot(disconnected, untouched)
    assert all(event.target_id != "uid:99" for event in credit.credit_events)
