from __future__ import annotations

import json
from pathlib import Path

from training.pipeline.cortex.development import DevelopmentStateStore


def _write_report(
    reports: Path,
    name: str,
    completed_at: str,
    result: dict,
) -> None:
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"{name}.json").write_text(
        json.dumps(
            {
                "plan_id": name,
                "completed_at": completed_at,
                "result": {"status": "completed", **result},
            }
        ),
        encoding="utf-8",
    )


def test_development_state_reconstructs_only_the_active_lineage(
    tmp_path: Path,
) -> None:
    reports = tmp_path / "control/reports"
    policy = Path(__file__).parents[1] / (
        "training/pipeline/cortex/development_policy.json"
    )
    for sequence, (checkpoint, steps) in enumerate(
        (("block_0001.pt", 4), ("block_0002.pt", 5), ("rejected.pt", 99)),
        start=1,
    ):
        _write_report(
            reports,
            f"block-{sequence}",
            f"2026-07-25T00:0{sequence}:00Z",
            {
                "kind": "cortex_block",
                "checkpoint_after": f"core/cortex/{checkpoint}",
                "metadata": {
                    "architecture": (
                        "lfm2_5_encoder_230m_frozen__ninereeds_1_2b__lfm2_5_230m_frozen"
                    ),
                    "epochs": 1,
                    "examples": steps,
                    "batch_size": 1,
                    "step_losses": [1.0] * steps,
                    "ownership": {"trainable_parameters": 1_209_936_896},
                    "training_source": {"concept": f"concept-{sequence}"},
                },
            },
        )
    _write_report(
        reports,
        "evaluation",
        "2026-07-25T00:10:00Z",
        {
            "kind": "cortex_evaluation",
            "certificate": {
                "status": "rejected",
                "candidate_checkpoint": "core/cortex/rejected.pt",
                "parent_checkpoint": "core/cortex/block_0002.pt",
                "rollback_target": "core/cortex/block_0002.pt",
                "recommended_parent_checkpoint": "core/cortex/block_0002.pt",
            },
        },
    )
    _write_report(
        reports,
        "evaluation-parent",
        "2026-07-25T00:09:00Z",
        {
            "kind": "cortex_evaluation",
            "certificate": {
                "status": "developmental_progress",
                "candidate_checkpoint": "core/cortex/block_0002.pt",
                "parent_checkpoint": "core/cortex/block_0001.pt",
                "rollback_target": "core/cortex/block_0001.pt",
                "recommended_parent_checkpoint": "core/cortex/block_0002.pt",
            },
        },
    )
    _write_report(
        reports,
        "archived-mbert-block",
        "2026-07-25T00:11:00Z",
        {
            "kind": "cortex_block",
            "checkpoint_after": "core/cortex/archived-mbert.pt",
            "metadata": {
                "architecture": (
                    "mbert_frozen__ninereeds_1_2b__lfm2_5_230m_frozen"
                ),
                "epochs": 1,
                "examples": 999,
                "batch_size": 1,
                "step_losses": [1.0] * 999,
                "ownership": {"trainable_parameters": 1_209_936_896},
                "training_source": {"concept": "archived"},
            },
        },
    )
    store = DevelopmentStateStore(
        tmp_path,
        reports_dir=reports,
        policy_path=policy,
    )

    state = store.reconcile()

    assert state["stage"] == "foundational_bootstrap"
    assert state["current_checkpoint"] == "core/cortex/block_0002.pt"
    assert state["evidence"]["full_core_optimizer_steps"] == 9
    assert state["evidence"]["completed_blocks"] == 2
    assert state["evidence"]["all_experimental_blocks"] == 3
    assert state["evidence"]["developmental_progress_certificates"] == 1
    assert state["evidence"]["rejected_certificates"] == 1
    assert state["behavioral_admission_eligible"] is False
    assert store.read() == state


def test_development_state_tracks_lexical_and_language_exposure(
    tmp_path: Path,
) -> None:
    control = tmp_path / "control"
    reports = control / "reports"
    plans = control / "plans"
    plans.mkdir(parents=True)
    policy = Path(__file__).parents[1] / (
        "training/pipeline/cortex/development_policy.json"
    )
    plan_id = "plan-cortex-lexical"
    (plans / f"{plan_id}.json").write_text(
        json.dumps(
            {
                "payload": {
                    "script": {
                        "items": [
                            {
                                "user_prompt": "Where is the key?",
                                "teacher_correction": None,
                                "ask_after_correction": False,
                                "expected_original": {
                                    "acceptable": ["The key is in the box."]
                                },
                            },
                            {
                                "user_prompt": "Wo ist der Schlüssel?",
                                "teacher_correction": None,
                                "ask_after_correction": False,
                                "expected_original": {
                                    "acceptable": ["Der Schlüssel ist in der Kiste."]
                                },
                            },
                            {
                                "user_prompt": "鍵はどこですか？",
                                "teacher_correction": None,
                                "ask_after_correction": False,
                                "expected_original": {
                                    "acceptable": ["鍵は箱の中です。"]
                                },
                            },
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    _write_report(
        reports,
        plan_id,
        "2026-07-25T00:01:00Z",
        {
            "kind": "cortex_block",
            "checkpoint_after": "core/cortex/lexical.pt",
            "metadata": {
                    "architecture": (
                        "lfm2_5_encoder_230m_frozen__ninereeds_1_2b__"
                        "lfm2_5_230m_frozen"
                    ),
                "epochs": 2,
                "examples": 3,
                "batch_size": 1,
                "step_losses": [1.0] * 6,
                "ownership": {"trainable_parameters": 1_209_936_896},
                "training_source": {"concept": "containment"},
            },
        },
    )
    state = DevelopmentStateStore(
        tmp_path,
        reports_dir=reports,
        plans_dir=plans,
        policy_path=policy,
    ).reconstruct()

    exposure = state["evidence"]["lexical_exposure"]
    assert exposure["documented_examples"] == 6
    assert exposure["unaccounted_examples"] == 0
    assert exposure["unique_surface_word_types"] > 5
    assert exposure["language_mix"]["english"]["examples"] == 2
    assert exposure["language_mix"]["german"]["examples"] == 2
    assert exposure["language_mix"]["japanese"]["examples"] == 2


def test_broad_foundation_label_satisfies_foundation_concept_gate(
    tmp_path: Path,
) -> None:
    reports = tmp_path / "control/reports"
    policy = Path(__file__).parents[1] / (
        "training/pipeline/cortex/development_policy.json"
    )
    _write_report(
        reports,
        "foundation",
        "2026-07-25T00:01:00Z",
        {
            "kind": "cortex_block",
            "checkpoint_after": "core/cortex/foundation.pt",
            "metadata": {
                "architecture": (
                    "lfm2_5_encoder_230m_frozen__ninereeds_1_2b__"
                    "lfm2_5_230m_frozen"
                ),
                "epochs": 1,
                "examples": 10_000,
                "batch_size": 1,
                "step_losses": [1.0] * 10_000,
                "ownership": {"trainable_parameters": 1_209_936_896},
                "training_source": {"concept": "broad_foundational_replay"},
            },
        },
    )

    state = DevelopmentStateStore(
        tmp_path,
        reports_dir=reports,
        policy_path=policy,
    ).reconstruct()

    assert state["readiness_gates"]["unique_curriculum_concepts"] == {
        "observed": 1,
        "required": 1,
        "met": True,
    }
