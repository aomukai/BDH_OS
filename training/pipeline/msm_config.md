# MSM Configuration Contract

The active config file should live at:

`training/pipeline/msm/state/orchestrator_config.json`

Machine-readable schema:

`training/pipeline/orchestrator_config_schema.json`

If the file does not exist yet, ordinary startup writes the static default with
`meta/scripts/msm_bootstrap_config.py` before autonomous sessions. The orchestrator should
only modify this config after recording an explicit decision.

---

## Required Fields

```json
{
  "schema_version": "msm_orchestrator_config_v1",
  "checkpoint_policy": {
    "initial_parent": "scratch",
    "current_parent": "scratch",
    "accepted_checkpoint": null,
    "historical_checkpoints_are_parents": false
  },
  "thresholds": {
    "max_malformed_rate": 0.10,
    "max_repetition_collapse": 0,
    "max_empty_or_near_empty_rate": 0.10,
    "min_correct_items_to_continue": 1,
    "max_off_topic_answers_to_continue": 0
  },
  "buffer_policy": {
    "min_proposed_turns_for_update": 5,
    "min_approved_turns_for_update": 1,
    "max_sessions_per_buffer": 5,
    "allow_single_session_repair_update": true
  },
  "scheduler_policy": {
    "learnability_weight": 1.0,
    "severity_weight": 1.0,
    "underexplored_weight": 0.5,
    "retry_penalty_weight": 1.0,
    "protected_anchor_weight": 2.0
  },
  "executor_selection": {
    "selection_mode": "fixed",
    "default_executor": "local:gemma-4-26b-a4b",
    "available_executors": [
      "local:gemma-4-26b-a4b",
      "local:ternary-bonsai-27b",
      "local:qwen3.6-35b-a3b"
    ]
  },
  "executor_prompt_context": {
    "inject_meta_scratchpad": false,
    "meta_scratchpad_path": "training/pipeline/msm/state/meta_scratchpad.md"
  },
  "deduplication_policy": {
    "script_fingerprint_algorithm": "msm_script_fingerprint_v1",
    "reject_exact_structural_duplicates": true,
    "warn_prompt_jaccard_above": 0.85,
    "allow_repetition_with_policy_reason": true
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
  "update_candidate_eval_schema": "training/pipeline/update_candidate_eval_schema.json"
}
```

Thresholds are starting defaults, not research findings. The orchestrator may change them
only by writing an explicit decision artifact.

`executor_prompt_context.inject_meta_scratchpad` defaults to `false`. The meta scratchpad
is an ablation-controlled prompt input, not required infrastructure. Every generated
`script.json` must record whether the scratchpad was injected.

`executor_selection.selection_mode` is fixed in v1. Gemma 4 26B A4B is the commissioned
default from the local bakeoff. The adapter deterministically routes jobs above 32K context
to Ternary Bonsai 27B; Qwen3.6-35B-A3B remains a bounded fallback. There is no UCB/bandit
selection until the backends have enough comparable production evidence.

Script de-duplication uses deterministic fingerprints in v1: normalized prompt hashes,
question-type sequences, contrast pairs, and target failure modes. Do not add an embedding
model to this path unless the orchestrator explicitly approves a later experiment.

---

## Buffer Location

Approved buffers live under:

`training/pipeline/msm/buffers/BUFFER_ID/approved_training.jsonl`

The executor never writes this file directly. The orchestrator creates it by selecting records
from one or more `proposed_training.jsonl` files.

An update manifest must not be written unless the approved buffer contains at least
`min_approved_turns_for_update` records.

## Accumulated Evidence

The orchestrator should maintain:

- `training/pipeline/msm/state/phase_registry.json`
- `training/pipeline/msm/state/concept_state.json`
- `training/pipeline/msm/state/session_archive.json`

`phase_registry.json` is the source of truth for the active phase and canonical phase
sequence. `concept_state.json` accumulates card-level and axis-level attempts, successes,
failures, retry counts, last strategy, and last session. `session_archive.json` is a
queryable index of report-card summaries and script fingerprints. The full report
artifacts remain under `training/pipeline/msm/sessions/SESSION_ID/`.

During Phase 0/1 frontload blocks, the local runner may update
`checkpoint_policy.current_parent` to the latest successfully probed block checkpoint so the
next local block continues training instead of restarting from `scratch`. The orchestrator
still owns phase promotion and `accepted_checkpoint`.

## Cold-Start Block Runner

Phase 0 and Phase 1 use a frontload block loop, not the later MSM session loop:

```text
generate examples -> train bounded block -> probe -> write phase block report
```

The runner entry point is:

```bash
python3 meta/scripts/msm_phase_runner.py
```

When the current parent is `scratch`, the runner must call `train.py` without `--resume`.
No explicit scratch checkpoint file is required. After a successfully probed Phase 0/1 block,
later local blocks resume from `checkpoint_policy.current_parent`. The orchestrator promotes
or rejects a phase only after reviewing the gate report.
