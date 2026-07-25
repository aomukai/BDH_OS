from __future__ import annotations

import json
from pathlib import Path

from lab.backend.artifacts.indexer import ArtifactIndex
from tests.helpers import make_lab_config
from training.pipeline.cortex.artifacts import CortexCampaignPublisher
from training.pipeline.cortex.evaluation import (
    compare_evaluations,
    enrich_cross_prompt_metrics,
    repetition_metrics,
    score_response,
)
from training.pipeline.cortex.retention import (
    load_registry,
    record_certificate,
)


def test_behavioral_scoring_rejects_repetition_and_forbidden_answers() -> None:
    case = {
        "required_all": ["bag", "container"],
        "required_any": ["hold", "holds"],
        "forbidden": ["machine"],
    }
    assert score_response(
        case, "A bag is a container used to hold things."
    )["passed"]
    assert not score_response(case, "A bag is a machine.")["passed"]
    assert repetition_metrics("A. A. A. A.")["pathological"]


def test_admission_gate_uses_behavior_and_protected_anchors() -> None:
    candidate = _model_result(overall=0.8, protected=1.0, target=1.0)
    parent = _model_result(overall=0.6, protected=1.0, target=0.5)
    raw = _raw_vectors()
    admitted = compare_evaluations(
        candidate,
        raw,
        parent,
        raw,
        candidate_checkpoint="core/cortex/candidate.pt",
        parent_checkpoint="core/cortex/parent.pt",
        target_concept="container",
    )
    assert admitted["status"] == "admitted"
    assert admitted["recommended_parent_checkpoint"].endswith("candidate.pt")

    candidate["summary"]["overall"]["pathological"] = 5
    rejected = compare_evaluations(
        candidate,
        raw,
        parent,
        raw,
        candidate_checkpoint="core/cortex/candidate.pt",
        parent_checkpoint="core/cortex/parent.pt",
        target_concept="container",
    )
    assert rejected["status"] == "rejected"
    assert rejected["recommended_parent_checkpoint"].endswith("parent.pt")


def test_cross_prompt_mode_collapse_rejects_identical_short_answers() -> None:
    evaluation = _evaluation()
    base_case = evaluation["candidate"]["cases"][0]
    evaluation["candidate"]["cases"] = [
        {
            **base_case,
            "case_id": f"case-{index}",
            "prompt": f"Distinct prompt {index}",
            "response": "I were not.",
            "score": 0.0,
            "passed": False,
        }
        for index in range(5)
    ]

    enriched = enrich_cross_prompt_metrics(evaluation)

    overall = enriched["candidate"]["summary"]["overall"]
    certificate = enriched["certificate"]
    assert overall["cross_prompt_collapse"] is True
    assert overall["unique_response_fraction"] == 0.2
    assert certificate["status"] == "rejected"
    assert "cross_prompt_generation_collapse" in certificate["failure_modes"]
    assert certificate["recommended_parent_checkpoint"].endswith("parent.pt")
    assert "expression-bridge" in certificate["recommended_next_action"]


def test_foundational_checkpoint_continues_without_becoming_a_winner() -> None:
    candidate = _model_result(overall=0.0, protected=0.0, target=0.0)
    parent = _model_result(overall=0.0, protected=0.0, target=0.0)
    candidate["summary"]["overall"]["pathological"] = 10
    certificate = compare_evaluations(
        candidate,
        _raw_vectors(),
        parent,
        _raw_vectors(),
        candidate_checkpoint="core/cortex/candidate.pt",
        parent_checkpoint="core/cortex/parent.pt",
        target_concept="container",
        development_stage="foundational_bootstrap",
    )

    assert certificate["status"] == "developmental_progress"
    assert certificate["behavioral_admission_eligible"] is False
    assert certificate["recommended_parent_checkpoint"].endswith("candidate.pt")
    assert certificate["blocking_reasons"] == []
    assert certificate["diagnostic_findings"]
    assert "full-core" in certificate["recommended_next_action"]


def test_publisher_allocates_campaign_18_and_lab_keeps_artifacts_together(
    tmp_path: Path,
) -> None:
    old = tmp_path / "training/logs/campaign_17_reports/old_report.md"
    old.parent.mkdir(parents=True)
    old.write_text("# Old\n", encoding="utf-8")
    publisher = CortexCampaignPublisher(tmp_path)
    evaluation = _evaluation()
    state = {
        "campaign_id": "cortex-language-recovery-20260725-a",
        "objective": "Recover early Cortex language.",
        "status": "paused",
        "stop_reason": "Budget complete.",
        "created_at": "2026-07-25T00:00:00Z",
    }
    result = publisher.publish_evaluation(
        campaign_state=state,
        source_plan_id="plan-eval-candidate",
        evaluation=evaluation,
    )
    assert result["campaign_number"] == 18
    root = tmp_path / "training/logs/campaign_18_reports"
    for name in (
        "00_manifest.json",
        "01_report.md",
        "metrics.json",
        "decision.json",
        "cortex_mri.html",
        "cortex_3d_map.html",
        "cortex_atlas.html",
        "retention_manifest.json",
    ):
        assert (root / name).is_file()

    config = make_lab_config(tmp_path)
    index = ArtifactIndex(config)
    index.scan()
    dashboard = index.dashboard()
    assert dashboard["current_campaign"]["title"] == (
        "18: cortex-language-recovery-20260725-a"
    )
    assert dashboard["latest_report"]["campaign_id"] == "18"
    assert dashboard["latest_mri"]["campaign_id"] == "18"
    assert dashboard["latest_graph"]["campaign_id"] == "18"
    assert dashboard["latest_atlas"]["campaign_id"] == "18"
    published_decision = json.loads(
        (root / "decision.json").read_text(encoding="utf-8")
    )
    assert dashboard["latest_recommendations"] == (
        published_decision["recommended_next_action"]
    )

    (root / "decision.json").write_text(
        json.dumps(
            {
                "failure_modes": [
                    "cross_prompt_generation_collapse",
                    "target_nontransfer",
                ]
            }
        ),
        encoding="utf-8",
    )
    index.scan()
    assert index.dashboard()["current_bottleneck"] == (
        "cross prompt generation collapse · target nontransfer"
    )


def test_checkpoint_registry_records_quarantine_certificate(tmp_path: Path) -> None:
    checkpoint = tmp_path / "core/cortex/candidate.pt"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"checkpoint")
    certificate = _evaluation()["certificate"]
    record_certificate(
        tmp_path / "core/cortex/checkpoint_registry.json",
        campaign_id="campaign-test",
        certificate=certificate,
        checkpoint_root=tmp_path,
    )
    registry = load_registry(tmp_path / "core/cortex/checkpoint_registry.json")
    entry = registry["checkpoints"]["core/cortex/candidate.pt"]
    assert entry["state"] == "admitted"
    assert entry["rollback_target"] == "core/cortex/parent.pt"


def test_campaign_without_evaluation_still_finalizes_registry(
    tmp_path: Path,
) -> None:
    publisher = CortexCampaignPublisher(tmp_path)
    publisher.registry.get_or_allocate(
        campaign_id="diagnostic-only",
        objective="Run a diagnostic.",
        created_at="2026-07-25T00:00:00Z",
    )

    result = publisher.finalize(
        {
            "campaign_id": "diagnostic-only",
            "status": "completed",
            "stop_reason": "No checkpoint was produced.",
        }
    )

    entry = publisher.registry.read()["campaigns"][0]
    assert result is not None
    assert result["changed"] is False
    assert entry["status"] == "completed"


def _raw_vectors():
    import torch

    values = [torch.tensor([1.0, 0.0]), torch.tensor([0.0, 1.0])]
    return {
        "vectors": {
            "ingress": values,
            "core": values,
            "intentions": values,
        }
    }


def _model_result(*, overall: float, protected: float, target: float) -> dict:
    return {
        "checkpoint_sha256": "a" * 64,
        "summary": {
            "overall": {
                "score": overall,
                "passed": 2,
                "total": 10,
                "pathological": 0,
            },
            "groups": {
                "capability": {
                    "score": overall,
                    "passed": 1,
                    "total": 6,
                    "pathological": 0,
                },
                "protected": {
                    "score": protected,
                    "passed": 1,
                    "total": 4,
                    "pathological": 0,
                },
            },
            "concepts": {
                "container": {
                    "score": target,
                    "passed": 1,
                    "total": 2,
                    "pathological": 0,
                }
            },
            "languages": {},
            "heldout_loss": 2.0,
        },
        "scan": {
            "activation_health": {
                "hidden_mean_abs": 1.0,
                "hidden_std": 1.0,
                "dead_layers": [],
                "saturated_layers": [],
                "layers": [],
            },
            "representation_health": {},
            "points": {},
        },
        "cases": [],
    }


def _evaluation() -> dict:
    candidate = _model_result(overall=0.8, protected=1.0, target=1.0)
    parent = _model_result(overall=0.6, protected=1.0, target=0.5)
    case = {
        "case_id": "container",
        "group": "capability",
        "concept": "container",
        "language": "en",
        "prompt": "What is a bag?",
        "expected_response": "A bag is a container.",
        "response": "A bag is a container.",
        "heldout_loss": 1.0,
        "score": 1.0,
        "passed": True,
        "required_all_hits": ["bag", "container"],
        "required_any_hits": [],
        "forbidden_hits": [],
        "repetition": {
            "token_count": 5,
            "dominant_token_fraction": 0.2,
            "repeated_bigram_fraction": 0.0,
            "pathological": False,
        },
    }
    candidate["cases"] = [case]
    candidate["scan"]["activation_health"]["layers"] = [
        {
            "tick": 1,
            "layer": 0,
            "x_sparse_density": 0.5,
            "x_sparse_mean_abs": 0.1,
            "y_sparse_density": 0.4,
            "y_sparse_mean_abs": 0.1,
            "xy_sparse_density": 0.2,
            "xy_sparse_mean_abs": 0.05,
        }
    ]
    points = [
        {
            "case_id": "container",
            "group": "capability",
            "concept": "container",
            "language": "en",
            "x": 0.1,
            "y": 0.2,
            "z": 0.3,
        }
    ]
    candidate["scan"]["points"] = {
        "ingress": points,
        "core": points,
        "intentions": points,
    }
    candidate["scan"]["representation_health"] = {
        stage: {
            "within_concept_cosine": 0.8,
            "between_concept_cosine": 0.2,
            "concept_separation": 0.6,
        }
        for stage in ("ingress", "core", "intentions")
    }
    certificate = {
        "schema_version": "ninereeds_cortex_admission_certificate_v1",
        "status": "admitted",
        "candidate_checkpoint": "core/cortex/candidate.pt",
        "candidate_sha256": "a" * 64,
        "parent_checkpoint": "core/cortex/parent.pt",
        "parent_sha256": "b" * 64,
        "rollback_target": "core/cortex/parent.pt",
        "target_concept": "container",
        "target_score": 1.0,
        "parent_target_score": 0.5,
        "target_gain": 0.5,
        "protected_score": 1.0,
        "parent_protected_score": 1.0,
        "overall_score": 0.8,
        "parent_overall_score": 0.6,
        "pathological_fraction": 0.0,
        "representation_drift": {
            "ingress": 0.0,
            "core": 0.1,
            "intentions": 0.1,
        },
        "reasons": [],
        "recommended_parent_checkpoint": "core/cortex/candidate.pt",
    }
    return {
        "schema_version": "ninereeds_cortex_candidate_evaluation_v1",
        "campaign_id": "cortex-language-recovery-20260725-a",
        "suite_id": "suite-test",
        "candidate": candidate,
        "parent": parent,
        "certificate": certificate,
    }
