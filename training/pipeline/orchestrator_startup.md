# MSM Orchestrator Startup

This is the master wake-up file for the stateless cold-start MSM pipeline.

The orchestrator has no hidden memory. On every wake-up, reconstruct state from explicit
artifacts and durable control receipts, decide the next safe boundary, write one bounded
plan, then stop. The workstation supervisor dispatches it to the trainbox worker.

---

## Startup Order

Read these in order:

1. `CLAUDE.md`
2. `index.md`
3. `todo.md`
4. `training/pipeline/orchestrator_startup.md`
5. `training/pipeline/runbook.md`
6. `training/pipeline/cold_start_phases.md`
7. `training/pipeline/msm_config.md`
8. `training/pipeline/msm/state/phase_registry.json`

Then run or read the deterministic startup summary:

```bash
python3 meta/scripts/msm_orchestrator_status.py
```

The summary is advisory. JSON/report artifacts remain the source of truth.

---

## Required Artifact Reads

Always check:

- `training/pipeline/msm/state/phase_registry.json`
- `training/pipeline/msm/state/orchestrator_config.json` if present
- `training/pipeline/msm/state/codex_brake.json` if present
- sentinel files anywhere under `training/pipeline/msm/`
- latest phase block reports under `training/pipeline/msm/phase_blocks/`
- latest session report cards under `training/pipeline/msm/sessions/`
- latest update evals under `training/pipeline/msm/updates/`

Read derived indexes only after source reports:

- `training/pipeline/msm/state/concept_state.json`
- `training/pipeline/msm/state/session_archive.json`

If a derived index conflicts with source reports, prefer the source report.

---

## Wake Reasons

Classify why the orchestrator woke up:

- `manual_start` - user started the pipeline or asked for status.
- `no_config` - `orchestrator_config.json` is missing and must be created from the
  config contract.
- `no_block_yet` - current phase has no block report yet.
- `block_finished` - a phase block report exists and needs a decision.
- `block_failed` - block report or runner status is failed/blocked.
- `gate_review` - local report says phase gate may be met.
- `sentinel_present` - human/Codex attention sentinel exists.
- `brake_blocks` - Codex brake disallows new work.
- `update_review` - update candidate requires acceptance/rejection.

Write the wake reason into the next decision/log artifact.

---

## Decision Boundaries

The orchestrator may decide:

- create missing `orchestrator_config.json`
- run a cold-start phase block with `meta/scripts/msm_phase_runner.py`
- repeat the same phase with adjusted block policy
- request probe implementation or repair a runner failure
- mark phase gate for manual review
- advance to the next phase after gates pass
- stop because sentinel/brake blocks work

Do not run open-ended loops inside the orchestrator. The orchestrator sets bounded policy;
deterministic runners do the repetitive work.

---

## Kickoff Model

The recommended launch shape is:

```text
supervisor process
  -> calls deterministic status helper
  -> calls orchestrator at most once per hour at a decision boundary
  -> orchestrator writes decision
  -> supervisor calls runner for bounded block
  -> runner writes report
  -> supervisor records the report and waits for the next hourly orchestrator window
```

For early manual operation, it is acceptable to keep an orchestrator terminal open. For
24/7 operation, prefer a small Python supervisor that invokes Codex/orchestrator only at
decision boundaries. Do not keep Codex responsible for watching every training micro-step.

## Manual Start Or Restart

For the normal recovery/reconciliation entrypoint on the workstation, run:

```bash
training/pipeline/start.sh
```

This is safe after a clean start, crash, reboot, or power outage. It runs one idempotent
supervisor reconciliation pass. The installed path and timer units normally do this
automatically.

To inspect both control ledgers without dispatching, run:

```bash
training/pipeline/start.sh --status-only
```

On a strategic wake, the orchestrator must reconstruct state from disk, run:

```bash
python3 meta/scripts/msm_orchestrator_status.py
```

Then it creates only the next safe plan through
`training.pipeline.control.ledger.ControlLedger`. If status says a phase block is ready,
queue a `phase_block` plan; never run the phase runner on the workstation. The installed
`ninereeds-orchestrator-supervisor.path` and hourly `.timer` provide reboot-safe
unattended reconciliation. `meta/scripts/wake_msm_orchestrator.sh` is a compatibility
alias for one supervisor pass and does not invoke Fugu or a persistent Codex session.

---

## First Cold-Start Boundary

For `phase_0_form`, if no block report exists and no sentinel/brake blocks work, the next
safe action is usually a dry or live bounded block:

```bash
python3 meta/scripts/msm_phase_runner.py --phase-id phase_0_form --parent scratch
```

The runner omits `--resume` when parent is `scratch`; no scratch checkpoint file is
required.
