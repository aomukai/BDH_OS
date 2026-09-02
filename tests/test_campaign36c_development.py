from __future__ import annotations

import pytest
import torch
import torch.nn.functional as F

from campaign36c import (
    BDHCellConfig,
    DevelopmentController,
    DevelopmentLabConfig,
    DevelopmentPolicyConfig,
    DevelopmentProbe,
    DevelopmentStage,
    FailureDiagnosis,
    MaturationEvidence,
    ResidualObservation,
    SparseWaveConfig,
    SparseWaveSubstrate,
    StandaloneBDHCell,
    WaveCell,
    merge_development_lab_results,
    run_development_laboratory,
)


WIDTH = 8
TOKENS = 5


def member(uid: int, *, seed: int = 36_400) -> WaveCell:
    return WaveCell(
        StandaloneBDHCell(
            BDHCellConfig(
                width=WIDTH,
                rotary_pairs=2,
                initialization_seed=seed + uid,
            ),
            uid=uid,
        ),
        max_degree=8,
        max_fanout=4,
    )


def controller(*, training_steps: int = 96) -> tuple[SparseWaveSubstrate, DevelopmentController]:
    substrate = SparseWaveSubstrate(
        SparseWaveConfig(max_degree=8, max_fanout=4)
    )
    substrate.add_cell(member(1))
    policy = DevelopmentPolicyConfig(
        minimum_observations=6,
        minimum_independent_lineages=6,
        minimum_source_families=2,
        minimum_residual_coherence=0.35,
        shadow_training_steps=training_steps,
        shadow_learning_rate=0.05,
        minimum_shadow_train_examples=4,
        minimum_shadow_holdout_examples=2,
        minimum_shadow_improvement_fraction=0.005,
        maximum_established_regression=0.0,
    )
    return substrate, DevelopmentController(
        substrate,
        next_uid=100,
        policy=policy,
        rotary_pairs=2,
    )


def state(seed: int, *, sign: float = 1.0) -> torch.Tensor:
    generator = torch.Generator().manual_seed(seed)
    prototype = torch.linspace(-1.0, 1.0, WIDTH).view(1, 1, WIDTH)
    return sign * prototype.expand(1, TOKENS, -1) + 0.03 * torch.randn(
        1, TOKENS, WIDTH, generator=generator
    )


def observation(
    substrate: SparseWaveSubstrate,
    epoch: int,
    *,
    ownership: float = 0.2,
    source: str | None = None,
    held_out: bool = False,
    measurement_consistent: bool = True,
    source_reliability: float = 0.99,
    route_resolved: bool = False,
    existing_trial_completed: bool = False,
    existing_improvement: float = 0.0,
) -> ResidualObservation:
    root = state(40_000 + epoch)
    with torch.inference_mode():
        frontier = substrate.run_thought(root, ingress_uids=1).state.detach()
    teacher = StandaloneBDHCell(
        BDHCellConfig(
            width=WIDTH,
            rotary_pairs=2,
            initialization_seed=99_999,
        ),
        uid=99_999,
    )
    with torch.no_grad():
        teacher.encoder.mul_(12.0)
        teacher.value_encoder.mul_(12.0)
        teacher.decoder.mul_(50.0)
        target = frontier
        for _ in range(3):
            target = teacher(target)
        target = target.detach()
    baseline = float(F.mse_loss(frontier.float(), target.float()))
    return ResidualObservation(
        thought_epoch=epoch,
        sponsor_uid=1,
        claim_address="synthetic:unowned-capacity",
        evidence_lineage=f"independent:{epoch}",
        source_family=source or f"source:{epoch % 2}",
        source_reliability=source_reliability,
        root_state=root,
        frontier_state=frontier,
        target_state=target,
        ownership=ownership,
        coverage=0.2 if ownership < 0.7 else 0.9,
        measurement_consistent=measurement_consistent,
        alternatives_checked=True,
        route_resolved=route_resolved,
        existing_trial_completed=existing_trial_completed,
        existing_loss_before=baseline if existing_trial_completed else None,
        existing_loss_after=(
            baseline * (1.0 - existing_improvement)
            if existing_trial_completed
            else None
        ),
        best_alternative_loss=baseline * (0.5 if route_resolved else 1.05),
        held_out=held_out,
    )


def test_diagnosis_excludes_learning_route_and_evidence_before_capacity() -> None:
    substrate, development = controller()
    learnable = observation(
        substrate,
        1,
        ownership=0.95,
        existing_trial_completed=True,
        existing_improvement=0.25,
    )
    routed = observation(substrate, 2, route_resolved=True)
    faulty = observation(
        substrate,
        3,
        source="broken-instrument",
        measurement_consistent=False,
    )

    assert development.observe(learnable).diagnosis is FailureDiagnosis.EXISTING_TISSUE_LEARNING
    assert development.observe(routed).diagnosis is FailureDiagnosis.ROUTE_FAILURE
    assert development.observe(faulty).diagnosis is FailureDiagnosis.EVIDENCE_FAILURE
    assert development.allocated_uids == ()
    assert development.dossiers == {}


def test_one_off_and_incoherent_novelty_do_not_allocate_tissue() -> None:
    substrate, development = controller()
    first = development.observe(observation(substrate, 1))
    assert first.diagnosis is FailureDiagnosis.INSUFFICIENT_EVIDENCE
    assert first.stage is DevelopmentStage.OBSERVING

    for epoch in range(2, 7):
        item = observation(substrate, epoch)
        if epoch % 2:
            item = ResidualObservation(
                **{
                    **item.__dict__,
                    "target_state": 2.0 * item.frontier_state - item.target_state,
                }
            )
        decision = development.observe(item)

    assert decision.diagnosis is FailureDiagnosis.INSUFFICIENT_EVIDENCE
    dossier = development.dossiers[first.dossier_id]
    assert dossier.stage is DevelopmentStage.OBSERVING
    assert dossier.coherence < development.policy.minimum_residual_coherence
    assert development.allocated_uids == ()


def test_persistent_coherent_residual_gets_shadow_value_and_atomic_admission() -> None:
    substrate, development = controller(training_steps=128)
    decisions = []
    for epoch in range(1, 7):
        decisions.append(
            development.observe(
                observation(substrate, epoch, held_out=epoch > 4)
            )
        )
    final = decisions[-1]
    assert final.diagnosis is FailureDiagnosis.CAPACITY_FAILURE
    assert final.stage is DevelopmentStage.EMBRYONIC
    assert development.allocated_uids == ()
    assert str(100) not in substrate.cells

    candidate = development.begin_shadow(final.dossier_id)
    assert candidate.stage is DevelopmentStage.SHADOW
    assert str(candidate.uid) not in substrate.cells
    development.train_shadow(candidate.uid)

    familiar_root = state(80_000, sign=-1.0)
    with torch.inference_mode():
        familiar_frontier = substrate.run_thought(familiar_root, ingress_uids=1).state.detach()
    retention = DevelopmentProbe(
        root_state=familiar_root,
        frontier_state=familiar_frontier,
        target_state=familiar_frontier,
        maximum_absolute_regression=0.0,
    )
    evaluation = development.evaluate_shadow(
        candidate.uid,
        established_probes=(retention,),
    )
    assert evaluation.passed is True
    assert evaluation.independent_value is True
    assert evaluation.candidate_loss < evaluation.no_cell_loss
    assert str(candidate.uid) not in substrate.cells

    development.admit(candidate.uid, established_probes=(retention,))
    assert candidate.stage is DevelopmentStage.ADMITTED
    assert development.dossiers[final.dossier_id].stage is DevelopmentStage.ADMITTED
    assert str(candidate.uid) in substrate.cells
    assert candidate.uid in substrate._cell(1).ports
    assert float(candidate.cell.contribution_scale) == pytest.approx(1.0)
    assert len(candidate.optimizer.state) > 0
    for epoch in range(4):
        stage = development.record_maturation_evidence(
            candidate.uid,
            MaturationEvidence(
                thought_epoch=1_000 + epoch,
                receptor_discriminated=True,
                transform_useful=True,
                port_calibrated=True,
                outcome_calibrated=True,
                harm_free=True,
            ),
        )
    assert stage is DevelopmentStage.MATURE


def test_failed_shadow_candidate_never_changes_live_topology() -> None:
    substrate, development = controller(training_steps=1)
    for epoch in range(1, 7):
        decision = development.observe(
            observation(substrate, epoch, held_out=epoch > 4)
        )
    candidate = development.begin_shadow(decision.dossier_id)
    development.train_shadow(candidate.uid)
    before_version = substrate.graph_version
    exposed = development.dossiers[decision.dossier_id].observations[-1]
    harmful_control = DevelopmentProbe(
        root_state=exposed.root_state,
        frontier_state=exposed.frontier_state,
        target_state=exposed.frontier_state,
        maximum_absolute_regression=0.0,
    )

    evaluation = development.evaluate_shadow(
        candidate.uid,
        established_probes=(harmful_control,),
    )

    assert evaluation.passed is False
    assert candidate.stage is DevelopmentStage.REJECTED
    assert str(candidate.uid) not in substrate.cells
    assert candidate.uid not in substrate._cell(1).ports
    assert substrate.graph_version == before_version


def test_faulty_source_is_quarantined_without_growing() -> None:
    substrate, development = controller()
    for epoch in (1, 2):
        result = development.observe(
            observation(
                substrate,
                epoch,
                source="faulty-rangefinder",
                source_reliability=0.2,
            )
        )
        assert result.diagnosis is FailureDiagnosis.EVIDENCE_FAILURE

    assert development.quarantined_sources == ("faulty-rangefinder",)
    assert development.allocated_uids == ()
    assert development.dossiers == {}


def test_unknown_outcome_does_not_quarantine_source_or_seed_growth() -> None:
    substrate, development = controller()
    item = observation(substrate, 1, source="healthy-unresolved-source")
    item = ResidualObservation(**{**item.__dict__, "outcome_available": False})

    decision = development.observe(item)

    assert decision.diagnosis is FailureDiagnosis.INSUFFICIENT_EVIDENCE
    assert decision.action == "retain_eligibility_without_structural_update"
    assert development.quarantined_sources == ()
    assert development.dossiers == {}


def test_probation_transaction_rolls_back_if_live_authority_harms_retention() -> None:
    substrate, development = controller(training_steps=128)
    for epoch in range(1, 7):
        decision = development.observe(
            observation(substrate, epoch, held_out=epoch > 4)
        )
    candidate = development.begin_shadow(decision.dossier_id)
    development.train_shadow(candidate.uid)
    familiar_root = state(80_000, sign=-1.0)
    with torch.inference_mode():
        familiar_frontier = substrate.run_thought(familiar_root, ingress_uids=1).state.detach()
    retention = DevelopmentProbe(
        root_state=familiar_root,
        frontier_state=familiar_frontier,
        target_state=familiar_frontier,
        maximum_absolute_regression=0.0,
    )
    assert development.evaluate_shadow(
        candidate.uid,
        established_probes=(retention,),
    ).passed
    # Simulate a receptor-calibration defect appearing between shadow review
    # and the transaction. The live probation/full-authority checks must catch it.
    with torch.no_grad():
        candidate.cell.receptor.calibration_bias.fill_(10.0)

    with pytest.raises(RuntimeError, match="regressed established tissue"):
        development.admit(candidate.uid, established_probes=(retention,))

    assert candidate.stage is DevelopmentStage.REJECTED
    assert str(candidate.uid) not in substrate.cells
    assert candidate.uid not in substrate._cell(1).ports


def test_stage4_development_laboratory_meets_bounded_exit_gate() -> None:
    config = DevelopmentLabConfig(
        width=16,
        rotary_pairs=2,
        sequence_length=6,
        training_examples=4,
        evaluation_examples=2,
        shadow_training_steps=96,
        disconnected_cells=4,
        learning_rate=0.05,
        minimum_shadow_improvement_fraction=0.005,
    )
    report = run_development_laboratory(config)

    assert report["selection"]["stage4_exit_gate_met"] is True
    assert report["diagnosis"]["pass"] is True
    assert report["birth"]["shadow_off_graph"] is True
    assert report["birth"]["stage"] == "mature"
    assert report["containment"]["harmful_stage"] == "rejected"
    assert report["containment"]["inactive_tissue_untouched"] is True

    telemetry = report["development_telemetry"]
    assert telemetry["event_total"] == 10
    assert {item["stage"] for item in telemetry["stage_records"]} == {
        stage.value for stage in DevelopmentStage
    }
    assert any(item["candidate_total"] == 0 for item in telemetry["stage_records"])
    assert any(item["rejection_total"] == 0 for item in telemetry["stage_records"])
    assert telemetry["rejection_counts"]["harm_gate"] == 1
    assert telemetry["rejection_counts"]["admission_regression"] == 0

    merged = merge_development_lab_results([report, report])
    assert merged["selection"]["all_devices_pass"] is True
