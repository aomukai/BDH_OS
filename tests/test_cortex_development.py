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
                        "mbert_frozen__ninereeds_1_2b__lfm2_5_230m_frozen"
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
