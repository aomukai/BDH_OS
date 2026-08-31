from __future__ import annotations

from amorphous.selection import (
    CohortAdmissionEvidence,
    ConceptBlockEvidence,
    selective_admission_decision,
    selective_birth_decision,
    selective_birth_integration_ready,
)


def block(
    *, failures: int = 10, early: float = 0.9, late: float = 0.85,
    active: float = 0.5,
) -> ConceptBlockEvidence:
    return ConceptBlockEvidence(
        residuals=(early,) * 5 + (late,) * 5,
        exact_predictions=(False,) * failures + (True,) * (10 - failures),
        all_admitted_cells_executed=(True,) * 10,
        active_admitted_fractions=(active,) * 10,
    )


def test_birth_requires_failure_residual_plateau_and_capacity() -> None:
    assert selective_birth_decision(block())
    assert not selective_birth_decision(block(failures=7))
    assert not selective_birth_decision(block(early=0.9, late=0.7))
    assert not selective_birth_decision(block(active=0.44))


def test_birth_waits_for_newest_cohort_integration_credit() -> None:
    assert selective_birth_integration_ready(None)
    assert not selective_birth_integration_ready(31)
    assert selective_birth_integration_ready(32)


def test_admission_rolls_over_until_old_and_observed() -> None:
    evidence = CohortAdmissionEvidence(
        age_exposures=127,
        online_credit_deltas=(0.1,) * 32,
        replay_delta_nll=(0.03,) * 32,
        anchor_harm_nll=(0.0,) * 8,
    )
    assert selective_admission_decision(evidence) == "provisional"
    assert selective_admission_decision(
        CohortAdmissionEvidence(
            age_exposures=128,
            online_credit_deltas=(0.1,) * 31,
            replay_delta_nll=(0.03,) * 32,
            anchor_harm_nll=(0.0,) * 8,
        )
    ) == "provisional"


def test_admission_promotes_only_causally_helpful_safe_cohort() -> None:
    assert selective_admission_decision(
        CohortAdmissionEvidence(
            age_exposures=256,
            online_credit_deltas=(0.1,) * 20 + (-0.1,) * 12,
            replay_delta_nll=(0.03,) * 32,
            anchor_harm_nll=(0.005,) * 8,
        )
    ) == "promote"


def test_failed_audit_rolls_once_then_becomes_dormant() -> None:
    values = dict(
        age_exposures=256,
        online_credit_deltas=(-0.1,) * 32,
        replay_delta_nll=(-0.02,) * 32,
        anchor_harm_nll=(0.0,) * 8,
    )
    assert selective_admission_decision(
        CohortAdmissionEvidence(**values)
    ) == "provisional"
    assert selective_admission_decision(
        CohortAdmissionEvidence(**values, completed_failed_audits=1)
    ) == "dormant"
