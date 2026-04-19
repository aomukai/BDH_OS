# Claude Worker Contract

This document defines what the execution model must do in a single training-harness round.

## Worker Identity

Claude Code acts as the **execution model**, not the final policy owner.
Hermes remains the orchestrator.

## Worker Duties

For one round only, the worker must:

1. read `training/harness/ROUND_STATE.json`
2. read the relevant harness policy documents
3. read the selected intervention skill
4. execute the bounded round
5. write all required artifacts to `training/rounds/<round_id>/`
6. update append-only logs if instructed
7. stop

The worker should also read the artifact contract files before writing structured outputs:

- `training/harness/artifact_schemas.md`
- `training/harness/metrics.template.json`
- `training/harness/decision.template.json`
- `training/harness/claude_report.template.json`
- `training/harness/verifier_report.template.json` when verifier output is needed
- `training/harness/draft_data_request.template.json` when emergency-exit data requests are needed

## Required Behavior

- obey repo scope and design constraints
- do not start real training if `training_enabled` is false
- fail loudly if required inputs are missing
- do not silently skip verification
- do not invent additional interventions outside the registry
- do not mutate accepted corpus files without explicit instruction

## Required Round Outputs

Each round folder should contain at minimum:

Round ids should follow the canonical stateful scheme from `ROUND_STATE.json`, for example:

- `R012-DR-A03-SOCROLE`

The worker must preserve both:

- the human-readable round id string
- the structured round-state fields used to construct it

- `plan.md`
- `summary.md`
- `metrics.json`
- `decision.json`
- `claude_report.json`

Optional files as needed:

- `verifier_report.json`
- `draft_data_request.json`
- `draft_training_data.md`
- `notes.md`

Structured JSON files should follow the canonical shapes defined in `training/harness/artifact_schemas.md` and the corresponding template files.

## Round Result Expectations

The worker report should always state:

- what it tried
- why it tried it
- what evidence it used
- what improved or failed to improve
- what it recommends next
- whether an emergency exit is being proposed

## Emergency Exit Constraint

If proposing `request_more_data`, the worker must explain why the remaining interventions are exhausted.
That claim is only a proposal until Hermes accepts it.
