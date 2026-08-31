from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import torch
import torch.nn.functional as F

from .cell import StandaloneBDHCell
from .config import BDHCellConfig, CellOptimizerConfig
from .wave import Admission, NeighborPort, SparseWaveSubstrate, WaveCell, probe_receptors


class FailureDiagnosis(str, Enum):
    """Typed alternatives that must be excluded before a capacity claim."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    EVIDENCE_FAILURE = "evidence_failure"
    ROUTE_FAILURE = "route_failure"
    EXISTING_TISSUE_LEARNING = "existing_tissue_learning"
    CAPACITY_FAILURE = "capacity_failure"


class DevelopmentStage(str, Enum):
    OBSERVING = "observing"
    EMBRYONIC = "embryonic"
    SHADOW = "shadow"
    PROBATIONARY = "probationary"
    ADMITTED = "admitted"
    MATURE = "mature"
    REJECTED = "rejected"


class GrowthKind(str, Enum):
    FRONTIER = "frontier"
    BUDDING = "budding"


@dataclass(frozen=True)
class DevelopmentPolicyConfig:
    """Conservative Stage-4 gates; no weighted score can bypass a missing gate."""

    ownership_threshold: float = 0.70
    minimum_evidence_reliability: float = 0.80
    minimum_residual_magnitude: float = 1e-5
    minimum_existing_improvement_fraction: float = 0.02
    maximum_existing_regression: float = 1e-4
    minimum_route_improvement_fraction: float = 0.02
    minimum_observations: int = 6
    minimum_independent_lineages: int = 6
    minimum_source_families: int = 2
    minimum_residual_coherence: float = 0.80
    maximum_dossier_observations: int = 64
    maximum_open_dossiers: int = 32
    maximum_candidate_neighbors: int = 4
    maximum_shadow_candidates: int = 3
    source_quarantine_failures: int = 2
    shadow_training_steps: int = 64
    shadow_learning_rate: float = 0.03
    minimum_shadow_train_examples: int = 3
    minimum_shadow_holdout_examples: int = 2
    minimum_shadow_improvement_fraction: float = 0.02
    maximum_established_regression: float = 1e-4
    probation_contribution_scale: float = 0.10
    cooldown_epochs: int = 8
    minimum_maturation_epochs: int = 4

    def validate(self) -> None:
        probabilities = (
            "ownership_threshold",
            "minimum_evidence_reliability",
            "minimum_residual_coherence",
        )
        for name in probabilities:
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        nonnegative = (
            "minimum_residual_magnitude",
            "minimum_existing_improvement_fraction",
            "maximum_existing_regression",
            "minimum_route_improvement_fraction",
            "minimum_shadow_improvement_fraction",
            "maximum_established_regression",
        )
        if any(getattr(self, name) < 0 for name in nonnegative):
            raise ValueError("developmental loss and regression bounds must be non-negative")
        positive = (
            "minimum_observations",
            "minimum_independent_lineages",
            "minimum_source_families",
            "maximum_dossier_observations",
            "maximum_open_dossiers",
            "maximum_candidate_neighbors",
            "maximum_shadow_candidates",
            "source_quarantine_failures",
            "shadow_training_steps",
            "minimum_shadow_train_examples",
            "minimum_shadow_holdout_examples",
            "cooldown_epochs",
            "minimum_maturation_epochs",
        )
        if any(getattr(self, name) <= 0 for name in positive):
            raise ValueError("developmental counts must be positive")
        if self.shadow_learning_rate <= 0:
            raise ValueError("shadow_learning_rate must be positive")
        if not 0.0 < self.probation_contribution_scale <= 1.0:
            raise ValueError("probation_contribution_scale must be in (0, 1]")


@dataclass(frozen=True)
class ResidualObservation:
    """One outcome-grounded residual at an unresolved local frontier.

    ``frontier_state`` is what a child beside ``sponsor_uid`` would receive.
    ``root_state`` is retained separately so probation can exercise the live
    route rather than accepting a shadow-only improvement.
    """

    thought_epoch: int
    sponsor_uid: int
    claim_address: str
    evidence_lineage: str
    source_family: str
    source_reliability: float
    root_state: torch.Tensor
    frontier_state: torch.Tensor
    target_state: torch.Tensor
    ownership: float
    coverage: float
    outcome_available: bool = True
    measurement_consistent: bool = True
    alternatives_checked: bool = False
    route_resolved: bool = False
    existing_trial_completed: bool = False
    existing_loss_before: float | None = None
    existing_loss_after: float | None = None
    existing_regression: float = 0.0
    best_alternative_loss: float | None = None
    held_out: bool = False
    expected_utility: float = 1.0
    candidate_neighbors: tuple[int, ...] = ()

    def validate(self) -> None:
        if self.thought_epoch < 0 or self.sponsor_uid < 0:
            raise ValueError("thought epoch and sponsor UID must be non-negative")
        if not self.claim_address or not self.evidence_lineage or not self.source_family:
            raise ValueError("claim, evidence lineage, and source family are required")
        if not 0.0 <= self.source_reliability <= 1.0:
            raise ValueError("source reliability must be in [0, 1]")
        if not 0.0 <= self.ownership <= 1.0 or not 0.0 <= self.coverage <= 1.0:
            raise ValueError("ownership and coverage must be in [0, 1]")
        if self.expected_utility < 0 or self.existing_regression < 0:
            raise ValueError("utility and regression must be non-negative")
        if self.root_state.shape != self.frontier_state.shape:
            raise ValueError("root and frontier states must share a shape")
        if self.frontier_state.shape != self.target_state.shape:
            raise ValueError("frontier and target states must share a shape")
        if self.root_state.ndim != 3 or self.root_state.size(0) != 1:
            raise ValueError("developmental states must be [1, token, width]")
        for value in (
            self.existing_loss_before,
            self.existing_loss_after,
            self.best_alternative_loss,
        ):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError("reported losses must be finite and non-negative")
        if self.existing_trial_completed and (
            self.existing_loss_before is None or self.existing_loss_after is None
        ):
            raise ValueError("a completed existing-tissue trial requires before/after loss")

    @property
    def baseline_loss(self) -> float:
        return float(F.mse_loss(self.frontier_state.float(), self.target_state.float()))

    @property
    def residual_magnitude(self) -> float:
        return float((self.target_state.float() - self.frontier_state.float()).square().mean().sqrt())

    @property
    def residual_signature(self) -> torch.Tensor:
        residual = self.target_state.detach().float() - self.frontier_state.detach().float()
        pooled = residual.mean(dim=(0, 1)).cpu()
        if float(pooled.norm()) <= 1e-12:
            pooled = residual.flatten().cpu()
        return F.normalize(pooled, dim=0, eps=1e-12)

    @property
    def existing_improvement_fraction(self) -> float:
        if self.existing_loss_before is None or self.existing_loss_after is None:
            return 0.0
        return (self.existing_loss_before - self.existing_loss_after) / max(
            self.existing_loss_before, 1e-12
        )

    @property
    def route_improvement_fraction(self) -> float:
        if self.best_alternative_loss is None:
            return 0.0
        return (self.baseline_loss - self.best_alternative_loss) / max(
            self.baseline_loss, 1e-12
        )


@dataclass(frozen=True)
class DevelopmentProbe:
    root_state: torch.Tensor
    frontier_state: torch.Tensor
    target_state: torch.Tensor
    maximum_absolute_regression: float = 1e-4

    def validate(self) -> None:
        if self.root_state.shape != self.frontier_state.shape or self.frontier_state.shape != self.target_state.shape:
            raise ValueError("probe states must share a shape")
        if self.maximum_absolute_regression < 0:
            raise ValueError("probe regression bound must be non-negative")


@dataclass
class CapacityDossier:
    dossier_id: str
    sponsor_uid: int
    claim_address: str
    growth_kind: GrowthKind
    stage: DevelopmentStage = DevelopmentStage.OBSERVING
    observations: list[ResidualObservation] = field(default_factory=list)
    candidate_neighbors: tuple[int, ...] = ()
    coherence: float = 0.0
    created_epoch: int = 0
    last_epoch: int = 0
    rejected_reason: str | None = None
    shadow_attempts: int = 0

    @property
    def independent_lineages(self) -> int:
        return len({item.evidence_lineage for item in self.observations})

    @property
    def source_families(self) -> int:
        return len({item.source_family for item in self.observations})

    @property
    def distinct_epochs(self) -> int:
        return len({item.thought_epoch for item in self.observations})


@dataclass(frozen=True)
class DevelopmentDecision:
    diagnosis: FailureDiagnosis
    action: str
    dossier_id: str | None
    stage: DevelopmentStage | None
    reason: str


@dataclass(frozen=True)
class ShadowEvaluation:
    no_cell_loss: float
    candidate_loss: float
    best_existing_loss: float
    improvement_fraction: float
    independent_value: bool
    maximum_established_regression: float
    positive_write_rate: float
    negative_write_rate: float
    passed: bool
    reason: str


@dataclass
class DevelopmentalCell:
    uid: int
    dossier_id: str
    cell: WaveCell
    optimizer: torch.optim.AdamW
    stage: DevelopmentStage
    shadow_evaluation: ShadowEvaluation | None = None
    live_probation_loss: float | None = None
    admitted_epoch: int | None = None
    maturation_epochs: set[int] = field(default_factory=set)


@dataclass(frozen=True)
class MaturationEvidence:
    thought_epoch: int
    receptor_discriminated: bool
    transform_useful: bool
    port_calibrated: bool
    outcome_calibrated: bool
    harm_free: bool

    @property
    def complete(self) -> bool:
        return all((
            self.receptor_discriminated,
            self.transform_useful,
            self.port_calibrated,
            self.outcome_calibrated,
            self.harm_free,
        ))


class UIDAllocator:
    """Monotonic allocator: rejected and retired UIDs are never reused."""

    def __init__(self, next_uid: int) -> None:
        if next_uid < 0:
            raise ValueError("next UID must be non-negative")
        self._next_uid = next_uid

    def allocate(self) -> int:
        uid = self._next_uid
        self._next_uid += 1
        return uid


class DevelopmentController:
    """Evidence-gated birth, shadow training, probation, and atomic admission."""

    def __init__(
        self,
        substrate: SparseWaveSubstrate,
        *,
        next_uid: int,
        policy: DevelopmentPolicyConfig | None = None,
        cell_optimizer: CellOptimizerConfig | None = None,
        rotary_pairs: int = 2,
        initialization_seed: int = 36_000,
    ) -> None:
        self.substrate = substrate
        self.policy = policy or DevelopmentPolicyConfig()
        self.policy.validate()
        self.cell_optimizer = cell_optimizer or CellOptimizerConfig(
            learning_rate=self.policy.shadow_learning_rate
        )
        self.cell_optimizer.validate()
        if rotary_pairs <= 0:
            raise ValueError("rotary_pairs must be positive")
        self.rotary_pairs = rotary_pairs
        self.initialization_seed = initialization_seed
        self.uid_allocator = UIDAllocator(next_uid)
        self.dossiers: dict[str, CapacityDossier] = {}
        self.cells: dict[int, DevelopmentalCell] = {}
        self._source_failures: dict[str, int] = {}
        self._quarantined_sources: set[str] = set()
        self._cooldown_until: dict[tuple[int, str], int] = {}

    @property
    def quarantined_sources(self) -> tuple[str, ...]:
        return tuple(sorted(self._quarantined_sources))

    @property
    def allocated_uids(self) -> tuple[int, ...]:
        return tuple(sorted(self.cells))

    @staticmethod
    def _key(observation: ResidualObservation, kind: GrowthKind) -> str:
        return f"{kind.value}:{observation.sponsor_uid}:{observation.claim_address}"

    @staticmethod
    def _coherence(observations: list[ResidualObservation]) -> float:
        if len(observations) < 2:
            return 1.0
        signatures = torch.stack([item.residual_signature for item in observations])
        centroid = F.normalize(signatures.mean(dim=0), dim=0, eps=1e-12)
        return float((signatures @ centroid).mean())

    def _record_source_failure(self, source: str) -> None:
        count = self._source_failures.get(source, 0) + 1
        self._source_failures[source] = count
        if count >= self.policy.source_quarantine_failures:
            self._quarantined_sources.add(source)

    def _immediate_diagnosis(self, item: ResidualObservation) -> DevelopmentDecision | None:
        if not item.outcome_available:
            return DevelopmentDecision(
                FailureDiagnosis.INSUFFICIENT_EVIDENCE,
                "retain_eligibility_without_structural_update",
                None,
                None,
                "an unknown outcome cannot diagnose either evidence or capacity",
            )
        if (
            not item.measurement_consistent
            or item.source_family in self._quarantined_sources
            or item.source_reliability < self.policy.minimum_evidence_reliability
        ):
            self._record_source_failure(item.source_family)
            return DevelopmentDecision(
                FailureDiagnosis.EVIDENCE_FAILURE,
                "recalibrate_or_quarantine_source",
                None,
                None,
                "the outcome or its provenance is not reliable enough for structural evidence",
            )
        if not item.alternatives_checked:
            return DevelopmentDecision(
                FailureDiagnosis.INSUFFICIENT_EVIDENCE,
                "test_existing_routes",
                None,
                None,
                "existing routes have not yet been excluded",
            )
        if item.route_resolved or (
            item.best_alternative_loss is not None
            and item.route_improvement_fraction
            >= self.policy.minimum_route_improvement_fraction
        ):
            return DevelopmentDecision(
                FailureDiagnosis.ROUTE_FAILURE,
                "update_route_or_receptor",
                None,
                None,
                "an existing route resolves the residual",
            )
        if item.ownership >= self.policy.ownership_threshold:
            if not item.existing_trial_completed:
                return DevelopmentDecision(
                    FailureDiagnosis.INSUFFICIENT_EVIDENCE,
                    "try_existing_tissue_learning",
                    None,
                    None,
                    "owned residual has not received a safe local learning trial",
                )
            if (
                item.existing_improvement_fraction
                >= self.policy.minimum_existing_improvement_fraction
                and item.existing_regression <= self.policy.maximum_existing_regression
            ):
                return DevelopmentDecision(
                    FailureDiagnosis.EXISTING_TISSUE_LEARNING,
                    "continue_uid_local_learning",
                    None,
                    None,
                    "existing tissue absorbs the correction without retained regression",
                )
        if (
            item.residual_magnitude < self.policy.minimum_residual_magnitude
            or item.expected_utility <= 0
        ):
            return DevelopmentDecision(
                FailureDiagnosis.INSUFFICIENT_EVIDENCE,
                "return_unresolved",
                None,
                None,
                "the residual is too small or has no demonstrated utility",
            )
        return None

    def observe(self, observation: ResidualObservation) -> DevelopmentDecision:
        observation.validate()
        immediate = self._immediate_diagnosis(observation)
        if immediate is not None:
            return immediate
        kind = (
            GrowthKind.BUDDING
            if observation.ownership >= self.policy.ownership_threshold
            else GrowthKind.FRONTIER
        )
        key = self._key(observation, kind)
        cooldown = self._cooldown_until.get((observation.sponsor_uid, observation.claim_address), -1)
        if observation.thought_epoch < cooldown:
            return DevelopmentDecision(
                FailureDiagnosis.INSUFFICIENT_EVIDENCE,
                "cooldown",
                key if key in self.dossiers else None,
                self.dossiers[key].stage if key in self.dossiers else None,
                "the frontier is inside a post-decision structural cooldown",
            )
        dossier = self.dossiers.get(key)
        if dossier is None:
            open_count = sum(
                item.stage in {DevelopmentStage.OBSERVING, DevelopmentStage.EMBRYONIC, DevelopmentStage.SHADOW}
                for item in self.dossiers.values()
            )
            if open_count >= self.policy.maximum_open_dossiers:
                return DevelopmentDecision(
                    FailureDiagnosis.INSUFFICIENT_EVIDENCE,
                    "dossier_budget_exhausted",
                    None,
                    None,
                    "the bounded open-dossier budget is exhausted",
                )
            dossier = CapacityDossier(
                dossier_id=key,
                sponsor_uid=observation.sponsor_uid,
                claim_address=observation.claim_address,
                growth_kind=kind,
                created_epoch=observation.thought_epoch,
                last_epoch=observation.thought_epoch,
            )
            self.dossiers[key] = dossier
        elif dossier.stage is DevelopmentStage.REJECTED:
            # Fresh post-cooldown evidence may reopen diagnosis, but receives a
            # new bounded shadow-attempt allowance rather than an infinite loop.
            dossier.stage = DevelopmentStage.OBSERVING
            dossier.shadow_attempts = 0
            dossier.rejected_reason = None
            self._cooldown_until.pop(
                (observation.sponsor_uid, observation.claim_address), None
            )
        if dossier.stage in {DevelopmentStage.ADMITTED, DevelopmentStage.MATURE}:
            return DevelopmentDecision(
                FailureDiagnosis.EXISTING_TISSUE_LEARNING,
                "route_to_admitted_child",
                key,
                dossier.stage,
                "this concern already has admitted tissue",
            )
        identity = (observation.thought_epoch, observation.evidence_lineage)
        if identity not in {
            (item.thought_epoch, item.evidence_lineage) for item in dossier.observations
        }:
            dossier.observations.append(observation)
            dossier.observations[:] = dossier.observations[-self.policy.maximum_dossier_observations :]
            dossier.last_epoch = observation.thought_epoch
            neighbors = list(dossier.candidate_neighbors)
            for uid in observation.candidate_neighbors:
                if uid not in neighbors and len(neighbors) < self.policy.maximum_candidate_neighbors:
                    neighbors.append(uid)
            dossier.candidate_neighbors = tuple(neighbors)
        dossier.coherence = self._coherence(dossier.observations)
        if dossier.stage in {
            DevelopmentStage.SHADOW,
            DevelopmentStage.PROBATIONARY,
        }:
            return DevelopmentDecision(
                FailureDiagnosis.INSUFFICIENT_EVIDENCE,
                "retain_provisional_exposure",
                key,
                dossier.stage,
                "a provisional candidate is already under bounded evaluation",
            )
        gates = {
            "observations": len(dossier.observations) >= self.policy.minimum_observations,
            "epochs": dossier.distinct_epochs >= self.policy.minimum_observations,
            "lineages": dossier.independent_lineages >= self.policy.minimum_independent_lineages,
            "sources": dossier.source_families >= self.policy.minimum_source_families,
            "coherence": dossier.coherence >= self.policy.minimum_residual_coherence,
        }
        if all(gates.values()):
            dossier.stage = DevelopmentStage.EMBRYONIC
            return DevelopmentDecision(
                FailureDiagnosis.CAPACITY_FAILURE,
                "allocate_shadow_candidate",
                key,
                dossier.stage,
                "persistent coherent residual survived evidence, route, and safe-learning alternatives",
            )
        missing = ",".join(name for name, passed in gates.items() if not passed)
        return DevelopmentDecision(
            FailureDiagnosis.INSUFFICIENT_EVIDENCE,
            "retain_bounded_dossier",
            key,
            dossier.stage,
            f"capacity is not established; missing gates: {missing}",
        )

    def _optimizer(self, cell: WaveCell) -> torch.optim.AdamW:
        config = self.cell_optimizer
        return torch.optim.AdamW(
            cell.transform.parameters(),
            lr=config.learning_rate,
            betas=config.betas,
            eps=config.epsilon,
            weight_decay=config.weight_decay,
            amsgrad=config.amsgrad,
        )

    def begin_shadow(self, dossier_id: str) -> DevelopmentalCell:
        dossier = self.dossiers[dossier_id]
        if dossier.stage is not DevelopmentStage.EMBRYONIC:
            raise RuntimeError("only an embryonic dossier may allocate a shadow cell")
        example = dossier.observations[0]
        uid = self.uid_allocator.allocate()
        config = BDHCellConfig(
            width=example.frontier_state.size(-1),
            rotary_pairs=self.rotary_pairs,
            initialization_seed=self.initialization_seed + uid,
        )
        cell = WaveCell(
            StandaloneBDHCell(config, uid=uid),
            max_degree=min(8, self.substrate.config.max_degree),
            max_fanout=min(4, self.substrate.config.max_fanout),
        ).to(device=example.frontier_state.device, dtype=example.frontier_state.dtype)
        train = [item for item in dossier.observations if not item.held_out]
        if len(train) < self.policy.minimum_shadow_train_examples:
            raise RuntimeError("the dossier lacks bounded shadow-training exposure")
        cell.receptor.tune_to(train[0].frontier_state)
        developmental = DevelopmentalCell(
            uid=uid,
            dossier_id=dossier_id,
            cell=cell,
            optimizer=self._optimizer(cell),
            stage=DevelopmentStage.SHADOW,
        )
        self.cells[uid] = developmental
        dossier.shadow_attempts += 1
        dossier.stage = DevelopmentStage.SHADOW
        return developmental

    def train_shadow(self, uid: int) -> None:
        developmental = self.cells[uid]
        if developmental.stage is not DevelopmentStage.SHADOW:
            raise RuntimeError("only a shadow cell may receive replay learning")
        dossier = self.dossiers[developmental.dossier_id]
        examples = [item for item in dossier.observations if not item.held_out]
        if len(examples) < self.policy.minimum_shadow_train_examples:
            raise RuntimeError("not enough shadow training examples")
        for step in range(self.policy.shadow_training_steps):
            item = examples[step % len(examples)]
            developmental.optimizer.zero_grad(set_to_none=True)
            # Evidence may have been captured under inference_mode; cloning at
            # replay time creates ordinary tensors that autograd may save.
            frontier = item.frontier_state.detach().clone()
            target = item.target_state.detach().clone()
            output = developmental.cell.transform(frontier)
            loss = F.mse_loss(output.float(), target.float())
            loss.backward()
            torch.nn.utils.clip_grad_norm_(developmental.cell.transform.parameters(), 1.0)
            developmental.optimizer.step()

    @staticmethod
    def _mean(values: list[float]) -> float:
        return sum(values) / len(values) if values else float("inf")

    def evaluate_shadow(
        self,
        uid: int,
        *,
        established_probes: tuple[DevelopmentProbe, ...] = (),
    ) -> ShadowEvaluation:
        developmental = self.cells[uid]
        dossier = self.dossiers[developmental.dossier_id]
        held_out = [item for item in dossier.observations if item.held_out]
        if len(held_out) < self.policy.minimum_shadow_holdout_examples:
            raise RuntimeError("the dossier lacks independent held-out exposure")
        for probe in established_probes:
            probe.validate()
        no_cell_losses: list[float] = []
        candidate_losses: list[float] = []
        alternatives: list[float] = []
        positive_writes = 0
        with torch.inference_mode():
            for item in held_out:
                no_cell_losses.append(item.baseline_loss)
                candidate_losses.append(
                    float(F.mse_loss(
                        developmental.cell.transform(item.frontier_state).float(),
                        item.target_state.float(),
                    ))
                )
                alternatives.append(
                    item.best_alternative_loss
                    if item.best_alternative_loss is not None
                    else item.baseline_loss
                )
                assessment = probe_receptors(
                    [developmental.cell.receptor],
                    item.frontier_state.unsqueeze(0),
                    [0.0],
                )[0]
                positive_writes += assessment.admission is Admission.WRITE

            regressions: list[float] = []
            negative_writes = 0
            for probe in established_probes:
                before = float(F.mse_loss(probe.frontier_state.float(), probe.target_state.float()))
                assessment = probe_receptors(
                    [developmental.cell.receptor],
                    probe.frontier_state.unsqueeze(0),
                    [0.0],
                )[0]
                if assessment.admission is Admission.WRITE:
                    negative_writes += 1
                    state = developmental.cell.transform(probe.frontier_state)
                else:
                    state = probe.frontier_state
                after = float(F.mse_loss(state.float(), probe.target_state.float()))
                regressions.append(max(0.0, after - before))
        no_cell = self._mean(no_cell_losses)
        candidate = self._mean(candidate_losses)
        best_existing = self._mean(alternatives)
        improvement = (no_cell - candidate) / max(no_cell, 1e-12)
        independent = (
            candidate < no_cell
            and candidate < best_existing
            and improvement >= self.policy.minimum_shadow_improvement_fraction
        )
        maximum_regression = max(regressions, default=0.0)
        harm_pass = all(
            regression <= min(probe.maximum_absolute_regression, self.policy.maximum_established_regression)
            for regression, probe in zip(regressions, established_probes)
        )
        positive_rate = positive_writes / len(held_out)
        negative_rate = negative_writes / len(established_probes) if established_probes else 0.0
        passed = independent and harm_pass and positive_rate > 0.0
        if passed:
            reason = (
                "shadow ablation demonstrates independent held-out value without "
                "established regression"
            )
        else:
            failed_gates = []
            if not independent:
                failed_gates.append("independent_value")
            if positive_rate <= 0.0:
                failed_gates.append("positive_receptive_envelope")
            if not harm_pass:
                failed_gates.append("established_route_harm")
            reason = "shadow candidate rejected: " + ",".join(failed_gates)
        evaluation = ShadowEvaluation(
            no_cell_loss=no_cell,
            candidate_loss=candidate,
            best_existing_loss=best_existing,
            improvement_fraction=improvement,
            independent_value=independent,
            maximum_established_regression=maximum_regression,
            positive_write_rate=positive_rate,
            negative_write_rate=negative_rate,
            passed=passed,
            reason=reason,
        )
        developmental.shadow_evaluation = evaluation
        if not passed:
            developmental.stage = DevelopmentStage.REJECTED
            dossier.rejected_reason = reason
            if dossier.shadow_attempts < self.policy.maximum_shadow_candidates:
                dossier.stage = DevelopmentStage.EMBRYONIC
            else:
                dossier.stage = DevelopmentStage.REJECTED
                self._cooldown_until[(dossier.sponsor_uid, dossier.claim_address)] = (
                    dossier.last_epoch + self.policy.cooldown_epochs
                )
        return evaluation

    def _rollback_install(self, sponsor_uid: int, uid: int) -> None:
        sponsor = self.substrate._cell(sponsor_uid)
        sponsor.ports.pop(uid, None)
        if str(uid) in self.substrate.cells:
            self.substrate.cells.pop(str(uid))
        self.substrate.graph_version += 1

    def admit(
        self,
        uid: int,
        *,
        established_probes: tuple[DevelopmentProbe, ...] = (),
    ) -> ShadowEvaluation:
        developmental = self.cells[uid]
        dossier = self.dossiers[developmental.dossier_id]
        evaluation = developmental.shadow_evaluation
        if developmental.stage is DevelopmentStage.REJECTED or evaluation is None or not evaluation.passed:
            raise RuntimeError("shadow gates must pass before probation")
        if not self.substrate.ready_for_next_turn:
            raise RuntimeError("structural admission requires a quiescent substrate")
        sponsor = self.substrate._cell(dossier.sponsor_uid)
        if str(uid) in self.substrate.cells or uid in sponsor.ports:
            raise RuntimeError("candidate UID or edge already exists")
        if len(sponsor.ports) >= min(sponsor.max_degree, self.substrate.config.max_degree):
            raise RuntimeError("sponsor has no bounded port capacity")
        for neighbor in dossier.candidate_neighbors:
            self.substrate._cell(neighbor)

        installed = False
        try:
            developmental.cell.set_contribution_scale(self.policy.probation_contribution_scale)
            self.substrate.add_cell(developmental.cell)
            installed = True
            self.substrate.connect(
                dossier.sponsor_uid,
                uid,
                conductance=self.policy.probation_contribution_scale,
                route_familiarity=0.0,
            )
            developmental.stage = DevelopmentStage.PROBATIONARY
            dossier.stage = DevelopmentStage.PROBATIONARY

            held_out = [item for item in dossier.observations if item.held_out]
            probation_losses: list[float] = []
            with torch.inference_mode():
                for item in held_out:
                    result = self.substrate.run_thought(
                        item.root_state,
                        ingress_uids=dossier.sponsor_uid,
                        claim_address=item.claim_address,
                        evidence_lineage=(item.evidence_lineage,),
                    )
                    probation_losses.append(float(F.mse_loss(result.state.float(), item.target_state.float())))
            developmental.live_probation_loss = self._mean(probation_losses)
            if developmental.live_probation_loss >= evaluation.no_cell_loss:
                raise RuntimeError("live probation did not beat the no-cell route")

            developmental.cell.set_contribution_scale(1.0)
            for probe in established_probes:
                with torch.inference_mode():
                    result = self.substrate.run_thought(
                        probe.root_state,
                        ingress_uids=dossier.sponsor_uid,
                        claim_address="development:retention-probe",
                        evidence_lineage=("development:retention-probe",),
                    )
                    after = float(F.mse_loss(result.state.float(), probe.target_state.float()))
                    before = float(F.mse_loss(probe.frontier_state.float(), probe.target_state.float()))
                if after > before + min(
                    probe.maximum_absolute_regression,
                    self.policy.maximum_established_regression,
                ):
                    raise RuntimeError("full-authority admission regressed established tissue")
        except Exception:
            if installed:
                self._rollback_install(dossier.sponsor_uid, uid)
            developmental.stage = DevelopmentStage.REJECTED
            dossier.stage = DevelopmentStage.REJECTED
            dossier.rejected_reason = "probation transaction rolled back"
            self._cooldown_until[(dossier.sponsor_uid, dossier.claim_address)] = (
                dossier.last_epoch + self.policy.cooldown_epochs
            )
            raise

        developmental.stage = DevelopmentStage.ADMITTED
        developmental.admitted_epoch = dossier.last_epoch
        dossier.stage = DevelopmentStage.ADMITTED
        self.substrate.graph_version += 1
        return evaluation

    def record_maturation_evidence(
        self,
        uid: int,
        evidence: MaturationEvidence,
    ) -> DevelopmentStage:
        """Promote only after multidimensional success across distinct epochs."""

        developmental = self.cells[uid]
        if developmental.stage not in {
            DevelopmentStage.ADMITTED,
            DevelopmentStage.MATURE,
        }:
            raise RuntimeError("only admitted tissue may accumulate maturity evidence")
        if evidence.thought_epoch < 0:
            raise ValueError("maturation epoch must be non-negative")
        if evidence.complete:
            developmental.maturation_epochs.add(evidence.thought_epoch)
        if len(developmental.maturation_epochs) >= self.policy.minimum_maturation_epochs:
            developmental.stage = DevelopmentStage.MATURE
            self.dossiers[developmental.dossier_id].stage = DevelopmentStage.MATURE
        return developmental.stage

    def state_summary(self) -> dict[str, Any]:
        return {
            "dossiers": {
                key: {
                    "stage": item.stage.value,
                    "growth_kind": item.growth_kind.value,
                    "observations": len(item.observations),
                    "independent_lineages": item.independent_lineages,
                    "source_families": item.source_families,
                    "coherence": item.coherence,
                    "shadow_attempts": item.shadow_attempts,
                }
                for key, item in sorted(self.dossiers.items())
            },
            "cells": {
                str(uid): {
                    "stage": item.stage.value,
                    "dossier_id": item.dossier_id,
                    "optimizer_state_entries": len(item.optimizer.state),
                    "maturation_epochs": len(item.maturation_epochs),
                }
                for uid, item in sorted(self.cells.items())
            },
            "quarantined_sources": list(self.quarantined_sources),
        }
