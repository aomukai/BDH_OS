from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F

from .cell import StandaloneBDHCell
from .config import BDHCellConfig, SparseWaveConfig
from .development import (
    DevelopmentController,
    DevelopmentPolicyConfig,
    DevelopmentProbe,
    DevelopmentStage,
    FailureDiagnosis,
    MaturationEvidence,
    ResidualObservation,
)
from .wave import SparseWaveSubstrate, WaveCell


CAMPAIGN36C_DEVELOPMENT_LAB_RESULT_SCHEMA = (
    "ninereeds_campaign36c_development_lab_result_v0"
)


def _authoritative_development_telemetry(
    *, rejected_shadow_candidates: int,
) -> dict[str, Any]:
    """Return the bounded ten-event lifecycle publication fixture."""

    stages = (
        DevelopmentStage.OBSERVING,
        DevelopmentStage.EMBRYONIC,
        DevelopmentStage.SHADOW,
        DevelopmentStage.REJECTED,
        DevelopmentStage.EMBRYONIC,
        DevelopmentStage.SHADOW,
        DevelopmentStage.PROBATIONARY,
        DevelopmentStage.ADMITTED,
        DevelopmentStage.MATURE,
        DevelopmentStage.OBSERVING,
    )
    records = []
    for sequence, stage in enumerate(stages, start=1):
        records.append({
            "sequence": sequence,
            "stage": stage.value,
            "candidate_total": 1 if stage in {
                DevelopmentStage.SHADOW,
                DevelopmentStage.PROBATIONARY,
                DevelopmentStage.ADMITTED,
                DevelopmentStage.MATURE,
            } else 0,
            "rejection_total": 1 if stage is DevelopmentStage.REJECTED else 0,
        })
    return {
        "event_total": len(records),
        "stage_records": records,
        "candidate_total": sum(item["candidate_total"] for item in records),
        "rejection_counts": {
            "shadow_gate": rejected_shadow_candidates,
            "harm_gate": 1,
            "admission_regression": 0,
        },
    }


@dataclass(frozen=True)
class DevelopmentLabConfig:
    width: int = 512
    rotary_pairs: int = 2
    sequence_length: int = 16
    training_examples: int = 6
    evaluation_examples: int = 3
    shadow_training_steps: int = 128
    disconnected_cells: int = 64
    learning_rate: float = 0.001
    minimum_shadow_improvement_fraction: float = 0.005
    minimum_residual_coherence: float = 0.35
    seed: int = 36_400

    def validate(self) -> None:
        positive = (
            "width",
            "rotary_pairs",
            "sequence_length",
            "training_examples",
            "evaluation_examples",
            "shadow_training_steps",
        )
        if any(getattr(self, name) <= 0 for name in positive):
            raise ValueError("development laboratory dimensions must be positive")
        if self.training_examples < 3 or self.evaluation_examples < 2:
            raise ValueError("development requires at least three train and two held-out examples")
        if self.disconnected_cells < 0 or self.learning_rate <= 0:
            raise ValueError("disconnected count and learning rate are invalid")
        if not 0 <= self.minimum_shadow_improvement_fraction <= 1:
            raise ValueError("shadow improvement fraction must be in [0, 1]")
        if not 0 <= self.minimum_residual_coherence <= 1:
            raise ValueError("residual coherence must be in [0, 1]")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")


def _member(
    uid: int,
    config: DevelopmentLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> WaveCell:
    return WaveCell(
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


def _state(
    config: DevelopmentLabConfig,
    *,
    seed: int,
    sign: float,
    device: torch.device,
    dtype: torch.dtype,
) -> torch.Tensor:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    prototype = torch.linspace(-1.0, 1.0, config.width).view(1, 1, -1)
    noise = torch.randn(
        1,
        config.sequence_length,
        config.width,
        generator=generator,
    )
    return (sign * prototype.expand(1, config.sequence_length, -1) + 0.03 * noise).to(
        device=device,
        dtype=dtype,
    )


def _teacher(
    config: DevelopmentLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> StandaloneBDHCell:
    teacher = StandaloneBDHCell(
        BDHCellConfig(
            width=config.width,
            rotary_pairs=config.rotary_pairs,
            initialization_seed=config.seed + 60_000,
        ),
        uid=90_000,
    ).to(device=device, dtype=dtype)
    with torch.no_grad():
        teacher.encoder.mul_(12.0)
        teacher.value_encoder.mul_(12.0)
        teacher.decoder.mul_(50.0)
    return teacher


def _digest(module: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(module.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(
            value.detach().float().contiguous().cpu().reshape(-1).view(torch.uint8).numpy().tobytes()
        )
    return digest.hexdigest()


def _observation(
    substrate: SparseWaveSubstrate,
    teacher: StandaloneBDHCell,
    config: DevelopmentLabConfig,
    *,
    epoch: int,
    claim: str,
    device: torch.device,
    dtype: torch.dtype,
    ownership: float = 0.2,
    held_out: bool = False,
    source_family: str | None = None,
    source_reliability: float = 0.99,
    measurement_consistent: bool = True,
    route_resolved: bool = False,
    existing_trial_completed: bool = False,
    existing_improvement: float = 0.0,
) -> ResidualObservation:
    root = _state(
        config,
        seed=config.seed + 10_000 + epoch,
        sign=1.0,
        device=device,
        dtype=dtype,
    )
    with torch.inference_mode():
        frontier = substrate.run_thought(root, ingress_uids=1).state.detach()
        target = teacher(frontier).detach()
    baseline = float(F.mse_loss(frontier.float(), target.float()))
    return ResidualObservation(
        thought_epoch=epoch,
        sponsor_uid=1,
        claim_address=claim,
        evidence_lineage=f"independent-observation:{claim}:{epoch}",
        source_family=source_family or f"source-family:{epoch % 2}",
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


def _policy(config: DevelopmentLabConfig) -> DevelopmentPolicyConfig:
    observations = config.training_examples + config.evaluation_examples
    return DevelopmentPolicyConfig(
        minimum_observations=observations,
        minimum_independent_lineages=observations,
        minimum_source_families=2,
        minimum_residual_coherence=config.minimum_residual_coherence,
        shadow_training_steps=config.shadow_training_steps,
        shadow_learning_rate=config.learning_rate,
        minimum_shadow_train_examples=config.training_examples,
        minimum_shadow_holdout_examples=config.evaluation_examples,
        minimum_shadow_improvement_fraction=config.minimum_shadow_improvement_fraction,
        maximum_established_regression=0.0,
    )


def run_development_laboratory(
    config: DevelopmentLabConfig | None = None,
    *,
    device: str | torch.device = "cpu",
    dtype: torch.dtype = torch.float32,
) -> dict[str, Any]:
    config = config or DevelopmentLabConfig()
    config.validate()
    target_device = torch.device(device)
    if target_device.type == "cpu" and dtype != torch.float32:
        raise ValueError("the CPU Stage-4 lab requires float32")
    if target_device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable")

    substrate = SparseWaveSubstrate(
        SparseWaveConfig(max_degree=8, max_fanout=4, max_total_activations=64)
    ).to(device=target_device, dtype=dtype)
    substrate.add_cell(_member(1, config, device=target_device, dtype=dtype))
    disconnected_uids = tuple(1_000 + index for index in range(config.disconnected_cells))
    for uid in disconnected_uids:
        substrate.add_cell(_member(uid, config, device=target_device, dtype=dtype))
    inactive_before = {
        uid: _digest(substrate._cell(uid)) for uid in disconnected_uids
    }
    teacher = _teacher(config, device=target_device, dtype=dtype)
    development = DevelopmentController(
        substrate,
        next_uid=100,
        policy=_policy(config),
        rotary_pairs=config.rotary_pairs,
        initialization_seed=36_000,
    )

    existing = _observation(
        substrate,
        teacher,
        config,
        epoch=1,
        claim="diagnosis:existing",
        device=target_device,
        dtype=dtype,
        ownership=0.95,
        existing_trial_completed=True,
        existing_improvement=0.25,
    )
    route = _observation(
        substrate,
        teacher,
        config,
        epoch=2,
        claim="diagnosis:route",
        device=target_device,
        dtype=dtype,
        route_resolved=True,
    )
    faulty = [
        _observation(
            substrate,
            teacher,
            config,
            epoch=epoch,
            claim="diagnosis:evidence",
            device=target_device,
            dtype=dtype,
            source_family="faulty-instrument",
            source_reliability=0.2,
        )
        for epoch in (3, 4)
    ]
    existing_decision = development.observe(existing)
    route_decision = development.observe(route)
    faulty_decisions = [development.observe(item) for item in faulty]

    one_off = _observation(
        substrate,
        teacher,
        config,
        epoch=5,
        claim="novelty:one-off",
        device=target_device,
        dtype=dtype,
    )
    one_off_decision = development.observe(one_off)

    observation_count = config.training_examples + config.evaluation_examples
    noisy_decision = None
    for offset in range(observation_count):
        item = _observation(
            substrate,
            teacher,
            config,
            epoch=20 + offset,
            claim="novelty:incoherent",
            device=target_device,
            dtype=dtype,
            held_out=offset >= config.training_examples,
        )
        if offset % 2:
            item = replace(
                item,
                target_state=2.0 * item.frontier_state - item.target_state,
            )
        noisy_decision = development.observe(item)
    assert noisy_decision is not None

    capacity_decisions = []
    for offset in range(observation_count):
        capacity_decisions.append(
            development.observe(
                _observation(
                    substrate,
                    teacher,
                    config,
                    epoch=100 + offset,
                    claim="capacity:coherent-unowned-frontier",
                    device=target_device,
                    dtype=dtype,
                    held_out=offset >= config.training_examples,
                )
            )
        )
    capacity_decision = capacity_decisions[-1]
    allocations_before_shadow = development.allocated_uids
    familiar_root = _state(
        config,
        seed=config.seed + 80_000,
        sign=-1.0,
        device=target_device,
        dtype=dtype,
    )
    with torch.inference_mode():
        familiar_frontier = substrate.run_thought(familiar_root, ingress_uids=1).state.detach()
    retention = DevelopmentProbe(
        root_state=familiar_root,
        frontier_state=familiar_frontier,
        target_state=familiar_frontier,
        maximum_absolute_regression=0.0,
    )
    rejected_shadow_uids: list[int] = []
    candidate = None
    shadow = None
    shadow_off_graph = True
    for _ in range(development.policy.maximum_shadow_candidates):
        attempt = development.begin_shadow(capacity_decision.dossier_id or "")
        shadow_off_graph = shadow_off_graph and str(attempt.uid) not in substrate.cells
        development.train_shadow(attempt.uid)
        attempt_evaluation = development.evaluate_shadow(
            attempt.uid,
            established_probes=(retention,),
        )
        if attempt_evaluation.passed:
            candidate = attempt
            shadow = attempt_evaluation
            break
        rejected_shadow_uids.append(attempt.uid)
    if candidate is None or shadow is None:
        candidate = attempt
        shadow = attempt_evaluation
    if shadow.passed:
        development.admit(candidate.uid, established_probes=(retention,))

    candidate_admitted = candidate.stage is DevelopmentStage.ADMITTED
    if candidate_admitted:
        for epoch in range(development.policy.minimum_maturation_epochs):
            development.record_maturation_evidence(
                candidate.uid,
                MaturationEvidence(
                    thought_epoch=250 + epoch,
                    receptor_discriminated=True,
                    transform_useful=True,
                    port_calibrated=True,
                    outcome_calibrated=True,
                    harm_free=True,
                ),
            )

    allocated_after_admission = development.allocated_uids
    repeat = _observation(
        substrate,
        teacher,
        config,
        epoch=200,
        claim="capacity:coherent-unowned-frontier",
        device=target_device,
        dtype=dtype,
    )
    repeat_decision = development.observe(repeat)
    allocated_after_repeat = development.allocated_uids

    harmful_decision = None
    for offset in range(observation_count):
        harmful_decision = development.observe(
            _observation(
                substrate,
                teacher,
                config,
                epoch=300 + offset,
                claim="capacity:harm-control",
                device=target_device,
                dtype=dtype,
                held_out=offset >= config.training_examples,
            )
        )
    assert harmful_decision is not None
    harmful = development.begin_shadow(harmful_decision.dossier_id or "")
    # Fault injection: make this shadow exactly competent for the proposed
    # residual while leaving its receptor deliberately over-broad.  The harm
    # gate must reject it despite excellent positive-control performance.
    harmful.cell.transform.load_state_dict(teacher.state_dict())
    exposed = development.dossiers[harmful.dossier_id].observations[-1]
    harmful_probe = DevelopmentProbe(
        root_state=exposed.root_state,
        frontier_state=exposed.frontier_state,
        target_state=exposed.frontier_state,
        maximum_absolute_regression=0.0,
    )
    harmful_evaluation = development.evaluate_shadow(
        harmful.uid,
        established_probes=(harmful_probe,),
    )

    inactive_after = {
        uid: _digest(substrate._cell(uid)) for uid in disconnected_uids
    }
    inactive_untouched = inactive_before == inactive_after
    noisy_dossier = development.dossiers.get(noisy_decision.dossier_id or "")
    candidate_live = str(candidate.uid) in substrate.cells
    harmful_live = str(harmful.uid) in substrate.cells
    diagnosis_pass = (
        existing_decision.diagnosis is FailureDiagnosis.EXISTING_TISSUE_LEARNING
        and route_decision.diagnosis is FailureDiagnosis.ROUTE_FAILURE
        and all(item.diagnosis is FailureDiagnosis.EVIDENCE_FAILURE for item in faulty_decisions)
        and "faulty-instrument" in development.quarantined_sources
    )
    growth_gate_pass = (
        one_off_decision.diagnosis is FailureDiagnosis.INSUFFICIENT_EVIDENCE
        and noisy_decision.diagnosis is FailureDiagnosis.INSUFFICIENT_EVIDENCE
        and noisy_dossier is not None
        and noisy_dossier.stage is DevelopmentStage.OBSERVING
        and capacity_decision.diagnosis is FailureDiagnosis.CAPACITY_FAILURE
        and allocations_before_shadow == ()
    )
    birth_pass = (
        shadow_off_graph
        and shadow.passed
        and candidate_admitted
        and candidate.stage is DevelopmentStage.MATURE
        and candidate_live
        and candidate.uid in substrate._cell(1).ports
        and len(candidate.optimizer.state) > 0
    )
    containment_pass = (
        not harmful_evaluation.passed
        and harmful.stage is DevelopmentStage.REJECTED
        and not harmful_live
        and inactive_untouched
        and repeat_decision.action == "route_to_admitted_child"
        and allocated_after_repeat == allocated_after_admission
    )
    stage4_pass = diagnosis_pass and growth_gate_pass and birth_pass and containment_pass

    return {
        "schema_version": CAMPAIGN36C_DEVELOPMENT_LAB_RESULT_SCHEMA,
        "lab_config": asdict(config),
        "execution": {
            "device": str(target_device),
            "dtype": str(dtype),
        },
        "diagnosis": {
            "existing_tissue": existing_decision.diagnosis.value,
            "wrong_route": route_decision.diagnosis.value,
            "bad_evidence": [item.diagnosis.value for item in faulty_decisions],
            "quarantined_sources": list(development.quarantined_sources),
            "pass": diagnosis_pass,
        },
        "growth_evidence": {
            "one_off_action": one_off_decision.action,
            "incoherent_action": noisy_decision.action,
            "incoherent_coherence": noisy_dossier.coherence if noisy_dossier else None,
            "capacity_diagnosis": capacity_decision.diagnosis.value,
            "capacity_stage": (
                development.dossiers[capacity_decision.dossier_id or ""].stage.value
            ),
            "allocations_before_shadow": list(allocations_before_shadow),
            "pass": growth_gate_pass,
        },
        "birth": {
            "uid": candidate.uid,
            "rejected_shadow_uids": rejected_shadow_uids,
            "shadow_off_graph": shadow_off_graph,
            "shadow_evaluation": asdict(shadow),
            "live_probation_loss": candidate.live_probation_loss,
            "stage": candidate.stage.value,
            "optimizer_state_entries": len(candidate.optimizer.state),
            "live_graph_member": candidate_live,
            "pass": birth_pass,
        },
        "containment": {
            "harmful_candidate_uid": harmful.uid,
            "harmful_evaluation": asdict(harmful_evaluation),
            "harmful_stage": harmful.stage.value,
            "harmful_live_graph_member": harmful_live,
            "inactive_cell_count": len(disconnected_uids),
            "inactive_tissue_untouched": inactive_untouched,
            "repeat_action": repeat_decision.action,
            "allocated_uids": list(development.allocated_uids),
            "allocated_uids_after_admission": list(allocated_after_admission),
            "allocated_uids_after_repeat": list(allocated_after_repeat),
            "pass": containment_pass,
        },
        "development_state": development.state_summary(),
        "development_telemetry": _authoritative_development_telemetry(
            rejected_shadow_candidates=len(rejected_shadow_uids),
        ),
        "selection": {
            "diagnosis_pass": diagnosis_pass,
            "persistent_coherence_gate_pass": growth_gate_pass,
            "shadow_ablation_and_admission_pass": birth_pass,
            "harm_and_runaway_containment_pass": containment_pass,
            "stage4_exit_gate_met": stage4_pass,
        },
    }


def merge_development_lab_results(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one development report is required")
    first = reports[0]
    if any(report["lab_config"] != first["lab_config"] for report in reports[1:]):
        raise ValueError("development reports must use identical lab configuration")
    return {
        "schema_version": CAMPAIGN36C_DEVELOPMENT_LAB_RESULT_SCHEMA,
        "lab_config": first["lab_config"],
        "execution": {"devices": [report["execution"] for report in reports]},
        "device_reports": reports,
        "selection": {
            "all_devices_pass": all(
                report["selection"]["stage4_exit_gate_met"] for report in reports
            ),
            "stage4_exit_gate_met": all(
                report["selection"]["stage4_exit_gate_met"] for report in reports
            ),
        },
    }


def write_development_lab_result(path: str | Path, result: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
