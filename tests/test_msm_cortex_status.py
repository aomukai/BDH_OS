from __future__ import annotations

import json
from pathlib import Path

from meta.scripts.msm_orchestrator_status import latest_cortex_run


def test_latest_cortex_run_sanitizes_successful_report(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "report.json").write_text(
        json.dumps(
            {
                "status": "succeeded",
                "plan_id": "plan-cortex",
                "completed_at": "2026-07-25T00:00:00Z",
                "result": {
                    "kind": "cortex_block",
                    "status": "completed",
                    "checkpoint_after": "core/cortex/block.pt",
                    "metadata": {
                        "architecture": "mbert__ninereeds_1_2b__lfm",
                        "initial_loss": 9.5,
                        "final_loss": 6.8,
                        "optimizer": {"policy_version": "factored_v1"},
                        "ownership": {"trainable_parameters": 1_200_000_000},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    result = latest_cortex_run(tmp_path)
    assert result is not None
    assert result["checkpoint"] == "core/cortex/block.pt"
    assert result["trainable_parameters"] == 1_200_000_000
    assert result["optimizer_policy"] == "factored_v1"
