from __future__ import annotations

import copy
from pathlib import Path

from tests.test_msm_trainer import script
from training.pipeline.control.script_finalize import finalize_msm_script


ROOT = Path(__file__).resolve().parents[1]


def test_finalize_replaces_model_guesses_and_hashes_prompts() -> None:
    proposed = script("model-guessed-session")
    original_items = copy.deepcopy(proposed["items"])
    first = finalize_msm_script(
        proposed,
        repo_root=ROOT,
        orchestrator_plan_id="plan-authoritative",
        session_id="session-authoritative",
        checkpoint="core/msm/accepted.pt",
        executor_id="gemma-4-26b-a4b",
        created_at="2026-07-25T00:00:00Z",
    )
    second = finalize_msm_script(
        proposed,
        repo_root=ROOT,
        orchestrator_plan_id="plan-authoritative",
        session_id="session-authoritative",
        checkpoint="core/msm/accepted.pt",
        executor_id="gemma-4-26b-a4b",
        created_at="2026-07-25T00:00:00Z",
    )
    assert first == second
    assert first["items"] == original_items
    assert first["script_id"] == "script-session-authoritative"
    assert first["script_author"] == "executor:gemma-4-26b-a4b"
    assert first["checkpoint"] == "core/msm/accepted.pt"
    assert len(first["script_fingerprint"]["structural_hash"]) == 64
    assert len(first["script_fingerprint"]["prompt_hash"]) == 64
    assert first["script_fingerprint"]["structural_hash"] != "test"
