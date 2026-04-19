# Round Artifact Schemas

This document defines the canonical structured artifacts for each training-harness round.
The goal is to make Claude Code outputs consistent, easy to diff, and easy for Hermes to reason over.

## Required Round Artifacts

Every round folder should contain:

- `plan.md`
- `summary.md`
- `metrics.json`
- `decision.json`
- `claude_report.json`

Optional but strongly recommended when relevant:

- `verifier_report.json`
- `draft_data_request.json`
- `draft_training_data.md`
- `notes.md`

## General Rules

1. Use valid JSON only.
2. Never omit `round_id`, `global_round`, `intervention`, or `target_cluster` from structured artifacts.
3. Prefer explicit `null` over silently missing semantically important fields.
4. Use lowercase snake_case keys.
5. Include short free-text summaries, but preserve machine-readable fields.

## `metrics.json`

Purpose: capture measurable outcomes from the round.

Required top-level fields:

- `round_id` — string
- `global_round` — integer
- `intervention` — string
- `intervention_code` — string
- `intervention_attempt` — integer
- `target_cluster` — string or null
- `target_cluster_code` — string or null
- `mode` — `dry_run` or `live_run`
- `comparison_basis` — string or null
- `baseline` — object
- `post_intervention` — object
- `delta` — object
- `plateau_detected` — boolean
- `meaningful_improvement` — boolean
- `notes` — array of strings

Recommended metric subfields in `baseline`, `post_intervention`, and `delta`:

- `pass_rate`
- `weak_pass_rate`
- `fail_rate`
- `retention_pass_rate`
- `rescue_depth_avg`
- `dominant_failure_type`
- `cluster_local_fail_rate`
- `generalization_pass_rate`

## `decision.json`

Purpose: record what Hermes or the worker thinks should happen next.

Required top-level fields:

- `round_id`
- `global_round`
- `intervention`
- `intervention_attempt`
- `target_cluster`
- `status` — e.g. `completed`, `blocked`, `dry_run_completed`, `failed`
- `recommended_next_intervention`
- `recommended_next_intervention_code`
- `recommended_next_cluster`
- `recommended_next_cluster_code`
- `reasoning_summary`
- `switch_intervention` — boolean
- `request_emergency_exit` — boolean
- `emergency_exit_rationale` — string or null
- `all_interventions_exhausted_for_cluster` — boolean
- `follow_up_actions` — array of strings

## `claude_report.json`

Purpose: capture the execution model's own report of the round.

Required top-level fields:

- `round_id`
- `global_round`
- `worker` — usually `claude_code`
- `worker_model` — string or null
- `intervention`
- `target_cluster`
- `task_mode` — `dry_run` or `live_run`
- `files_read` — array
- `files_written` — array
- `actions_taken` — array of strings
- `constraints_observed` — array of strings
- `verifier_used` — boolean
- `training_executed` — boolean
- `evaluation_executed` — boolean
- `errors` — array
- `warnings` — array
- `recommendation_summary` — string

Recommended optional fields:

- `budget_used`
- `runtime_seconds`
- `report_version`

## `verifier_report.json`

Purpose: record approval/rewrite/rejection of teacher-generated student-facing content.

Required top-level fields:

- `round_id`
- `artifact_id`
- `artifact_type`
- `reviewed_text`
- `outcome` — `approve`, `approve_with_rewrite`, `reject`, `needs_higher_level_dependency_check`
- `reasons` — array of strings
- `warnings` — array of strings
- `rewritten_text` — string or null
- `checks` — object

Required `checks` fields:

- `local_factual_correctness`
- `ontology_consistency`
- `contrast_safety`
- `curriculum_level_fit`
- `dependency_fit`
- `internal_corpus_consistency`
- `pedagogical_usefulness`

Each check should be one of:

- `pass`
- `warning`
- `fail`
- `unknown`

## `draft_data_request.json`

Purpose: structured emergency-exit request for new data.

Required top-level fields:

- `round_id`
- `target_cluster`
- `target_cluster_code`
- `dominant_failures` — array
- `exhausted_interventions` — array
- `request_summary`
- `requested_data_shape`
- `goal_alignment`
- `out_of_scope` — array
- `approved_by_orchestrator` — boolean or null

## Source of Truth

When prose and JSON disagree, the JSON artifact is the source of truth for machine decisions, and the summary markdown should be revised to match it.
