from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def test_loss_has_no_checkpoint_decision_authority() -> None:
    source = (REPO / "training/pipeline/cortex/evaluation.py").read_text(encoding="utf-8")
    assert 'LOSS_ROLE = "telemetry_only"' in source
    assert 'EVALUATION_BASIS = ["behavioral_chat", "mri_activation"]' in source
    assert "nonfinite_heldout_loss" not in source


def test_operator_prompt_does_not_grant_loss_decision_authority() -> None:
    source = (REPO / "config/mission_hub/prompts/campaign-decision-v1.toml").read_text(encoding="utf-8")
    assert "Loss is telemetry only" in source
