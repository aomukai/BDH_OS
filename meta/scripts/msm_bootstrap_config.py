#!/usr/bin/env python3
"""Create the default MSM orchestrator config when it is missing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": "msm_orchestrator_config_v1",
    "checkpoint_policy": {
        "initial_parent": "scratch",
        "current_parent": "scratch",
        "accepted_checkpoint": None,
        "historical_checkpoints_are_parents": False,
    },
    "thresholds": {
        "max_malformed_rate": 0.10,
        "max_repetition_collapse": 0,
        "max_empty_or_near_empty_rate": 0.10,
        "min_correct_items_to_continue": 1,
        "max_off_topic_answers_to_continue": 0,
    },
    "buffer_policy": {
        "min_proposed_turns_for_update": 5,
        "min_approved_turns_for_update": 1,
        "max_sessions_per_buffer": 5,
        "allow_single_session_repair_update": True,
    },
    "scheduler_policy": {
        "learnability_weight": 1.0,
        "severity_weight": 1.0,
        "underexplored_weight": 0.5,
        "retry_penalty_weight": 1.0,
        "protected_anchor_weight": 2.0,
    },
    "executor_selection": {
        "selection_mode": "fixed",
        "default_executor": "deepseek:deepseek-v4-flash",
        "available_executors": [
            "deepseek:deepseek-v4-flash",
            "local:qwen3.6-35b-a3b-q4-k-m-turboquant",
            "local:gemma-4-26b-a4b",
            "local:ternary-bonsai-27b",
            "local:qwen3.6-35b-a3b",
            "openrouter:deepseek-v4-flash-0731",
        ],
    },
    "executor_prompt_context": {
        "inject_meta_scratchpad": False,
        "meta_scratchpad_path": "training/pipeline/msm/state/meta_scratchpad.md",
    },
    "deduplication_policy": {
        "script_fingerprint_algorithm": "msm_script_fingerprint_v1",
        "reject_exact_structural_duplicates": True,
        "warn_prompt_jaccard_above": 0.85,
        "allow_repetition_with_policy_reason": True,
    },
    "sentinel_contract": "training/pipeline/sentinel_files.md",
    "codex_status_schema": "training/pipeline/codex_status_schema.json",
    "codex_brake_schema": "training/pipeline/codex_brake_schema.json",
    "script_schema": "training/pipeline/script_schema.json",
    "raw_chat_line_schema": "training/pipeline/raw_chat_line_schema.json",
    "phase_registry_schema": "training/pipeline/phase_registry_schema.json",
    "phase_block_report_schema": "training/pipeline/phase_block_report_schema.json",
    "concept_state_schema": "training/pipeline/concept_state_schema.json",
    "session_archive_schema": "training/pipeline/session_archive_schema.json",
    "active_campaign_policy_schema": "training/pipeline/active_campaign_policy_schema.json",
    "word_queue_schema": "training/pipeline/word_queue_schema.json",
    "auto_advance_state_schema": "training/pipeline/auto_advance_state_schema.json",
    "update_manifest_schema": "training/pipeline/update_manifest_schema.json",
    "update_candidate_eval_schema": "training/pipeline/update_candidate_eval_schema.json",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing config.")
    args = parser.parse_args()

    root = args.repo.resolve()
    path = root / "training/pipeline/msm/state/orchestrator_config.json"
    if path.exists() and not args.force:
        print(f"Config already exists: {path.relative_to(root).as_posix()}")
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DEFAULT_CONFIG, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote default config: {path.relative_to(root).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
