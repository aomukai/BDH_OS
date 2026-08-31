from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Literal, Sequence


AdmissionDecision = Literal["promote", "provisional", "dormant"]


@dataclass(frozen=True)
class SelectiveBirthConfig:
    block_exposures: int = 10
    minimum_failures: int = 8
    residual_threshold: float = 0.25
    maximum_improvement_fraction: float = 0.10
    minimum_active_admitted_fraction: float = 0.45
    minimum_newest_cohort_credit_observations: int = 32


@dataclass(frozen=True)
class ConceptBlockEvidence:
    residuals: tuple[float, ...]
    exact_predictions: tuple[bool, ...]
    all_admitted_cells_executed: tuple[bool, ...]
    active_admitted_fractions: tuple[float, ...]


@dataclass(frozen=True)
class SelectiveAdmissionConfig:
    minimum_age_exposures: int = 128
    minimum_credit_observations: int = 32
    minimum_helpful_fraction: float = 0.60
    minimum_median_replay_delta_nll: float = 0.02
    maximum_anchor_harm_nll: float = 0.01
    audits_before_dormancy: int = 2


@dataclass(frozen=True)
class CohortAdmissionEvidence:
    age_exposures: int
    online_credit_deltas: tuple[float, ...]
    replay_delta_nll: tuple[float, ...]
    anchor_harm_nll: tuple[float, ...]
    completed_failed_audits: int = 0


def _finite(values: Sequence[float]) -> bool:
    return all(math.isfinite(value) for value in values)


def selective_birth_decision(
    evidence: ConceptBlockEvidence,
    config: SelectiveBirthConfig | None = None,
) -> bool:
    config = config or SelectiveBirthConfig()
    lengths = {
        len(evidence.residuals),
        len(evidence.exact_predictions),
        len(evidence.all_admitted_cells_executed),
        len(evidence.active_admitted_fractions),
    }
    if lengths != {config.block_exposures}:
        raise ValueError("concept-block evidence must match block_exposures")
    if not _finite(evidence.residuals) or not _finite(
        evidence.active_admitted_fractions
    ):
        return False
    failures = sum(not value for value in evidence.exact_predictions)
    median_residual = statistics.median(evidence.residuals)
    midpoint = config.block_exposures // 2
    early = statistics.fmean(evidence.residuals[:midpoint])
    late = statistics.fmean(evidence.residuals[midpoint:])
    improvement = (early - late) / max(abs(early), 1e-12)
    capacity_saturated = (
        all(evidence.all_admitted_cells_executed)
        and statistics.fmean(evidence.active_admitted_fractions)
        >= config.minimum_active_admitted_fraction
    )
    return (
        failures >= config.minimum_failures
        and median_residual >= config.residual_threshold
        and improvement < config.maximum_improvement_fraction
        and capacity_saturated
    )


def selective_birth_integration_ready(
    newest_cohort_credit_observations: int | None,
    config: SelectiveBirthConfig | None = None,
) -> bool:
    """Prevent another birth before the newest cohort has had a fair trial."""
    config = config or SelectiveBirthConfig()
    return (
        newest_cohort_credit_observations is None
        or newest_cohort_credit_observations
        >= config.minimum_newest_cohort_credit_observations
    )


def selective_admission_decision(
    evidence: CohortAdmissionEvidence,
    config: SelectiveAdmissionConfig | None = None,
) -> AdmissionDecision:
    config = config or SelectiveAdmissionConfig()
    if evidence.age_exposures < config.minimum_age_exposures:
        return "provisional"
    if len(evidence.online_credit_deltas) < config.minimum_credit_observations:
        return "provisional"
    all_values = (
        *evidence.online_credit_deltas,
        *evidence.replay_delta_nll,
        *evidence.anchor_harm_nll,
    )
    passed = bool(evidence.replay_delta_nll) and _finite(all_values)
    if passed:
        helpful_fraction = sum(
            value > 0 for value in evidence.online_credit_deltas
        ) / len(evidence.online_credit_deltas)
        passed = (
            helpful_fraction >= config.minimum_helpful_fraction
            and statistics.median(evidence.replay_delta_nll)
            >= config.minimum_median_replay_delta_nll
            and (
                not evidence.anchor_harm_nll
                or statistics.fmean(evidence.anchor_harm_nll)
                <= config.maximum_anchor_harm_nll
            )
        )
    if passed:
        return "promote"
    if evidence.completed_failed_audits + 1 >= config.audits_before_dormancy:
        return "dormant"
    return "provisional"
