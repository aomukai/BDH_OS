# Hermes MSM Setup

This is the concrete setup contract for GPT-Hermes while it is temporarily allowed to set up
cronjobs and Discord reporting. After setup, Hermes should return to a simple reporter model.

Repository path on the current main machine:

```bash
~/Ninereeds
```

Do not invent new filenames, sentinel names, or decision paths. Use the files and commands in
this document.

## Role Boundary

Hermes is a pager and status reporter. It is not the orchestrator and not the executor.

The active strategic orchestrator provider is OpenRouter DeepSeek V4 Flash
(`deepseek/deepseek-v4-flash-0731`), with the legacy Codex→Fugu route retained only when
`NINEREEDS_STRATEGIC_PROVIDER=codex_fugu` is set. Hermes must not try to replace that
strategic boundary with its own reasoning. After setup, Hermes may run on a cheaper/simple
model such as Nemotron/Nemo because its normal job is only to check deterministic reports,
refresh status artifacts, ping Discord, and run `training/pipeline/start.sh` when a report or
sentinel contract says the pipeline should be woken.

Hermes may:

- read files under `~/Ninereeds`
- run deterministic repo status commands listed here
- post Discord messages from generated digest files
- append operational notes to `training/pipeline/msm/logs/hermes.jsonl`
- create only repo-defined sentinel files when a deterministic watchdog condition requires it

Hermes must not:

- edit plans, queues, concept state, campaign policy, corpus files, or checkpoints
- approve training turns
- write update manifests
- promote checkpoints
- decide strategy
- run broad LLM repo analysis during normal cron operation
- inject commands into a live Codex tmux session

## Canonical Files

Executor session report for later MSM sessions:

```text
training/pipeline/msm/sessions/SESSION_ID/report_card.json
training/pipeline/msm/sessions/SESSION_ID/report.md
```

Current Phase 0/1 block report:

```text
training/pipeline/msm/phase_blocks/PHASE_ID/BLOCK_ID/block_report.json
```

Sentinel files to watch anywhere under `training/pipeline/msm/`:

```text
HUMAN_ATTENTION
BLOCKED
TRAINING_MACHINE_DOWN
API_CREDITS_EXHAUSTED
PROMOTION_REVIEW_REQUIRED
```

The sentinel for Andi specifically is:

```text
HUMAN_ATTENTION
```

Orchestrator state-of-the-union files:

```text
training/pipeline/msm/state/orchestrator_status.json
training/pipeline/msm/state/orchestrator_status.md
```

Hermes digest file to post to Discord:

```text
training/pipeline/msm/state/hermes_digest.md
```

Codex brake/status files:

```text
training/pipeline/msm/state/codex_status.json
training/pipeline/msm/state/codex_status.md
training/pipeline/msm/state/codex_brake.json
```

Optional training-machine heartbeat once the trainbox exists:

```text
training/pipeline/msm/state/trainbox_heartbeat.json
```

## Deterministic Commands

Refresh orchestrator state-of-the-union files:

```bash
cd ~/Ninereeds && python3 meta/scripts/msm_orchestrator_status.py --write-files --quiet
```

Refresh Codex rate-limit brake files, only if a `codex` tmux session exists:

```bash
cd ~/Ninereeds && tmux has-session -t codex 2>/dev/null && python3 meta/scripts/watch_codex_status.py || true
```

Build Hermes digest markdown:

```bash
cd ~/Ninereeds && python3 meta/scripts/hermes_digest.py --quiet
```

Check current pipeline status without starting work:

```bash
cd ~/Ninereeds && training/pipeline/start.sh --status-only
```

Wake the pipeline when a report/sentinel requires action:

```bash
cd ~/Ninereeds && training/pipeline/start.sh
```

Force an orchestrator turn only when the deterministic status says a strategic decision is
needed, or when Andi explicitly asks:

```bash
cd ~/Ninereeds && training/pipeline/start.sh --orchestrator
```

## Report Scans

Find executor session reports:

```bash
cd ~/Ninereeds && find training/pipeline/msm/sessions -maxdepth 2 -name report_card.json 2>/dev/null | sort
```

Find Phase 0/1 block reports:

```bash
cd ~/Ninereeds && find training/pipeline/msm/phase_blocks -maxdepth 3 -name block_report.json 2>/dev/null | sort
```

Find update evals:

```bash
cd ~/Ninereeds && find training/pipeline/msm/updates -maxdepth 2 -name update_candidate_eval.json 2>/dev/null | sort
```

Find sentinel files:

```bash
cd ~/Ninereeds && find training/pipeline/msm \( \
  -name HUMAN_ATTENTION \
  -o -name BLOCKED \
  -o -name TRAINING_MACHINE_DOWN \
  -o -name API_CREDITS_EXHAUSTED \
  -o -name PROMOTION_REVIEW_REQUIRED \
\) 2>/dev/null | sort
```

## Cron Jobs

Install these only after verifying the repo path exists. These cron jobs do not perform
strategy work. They refresh deterministic status artifacts and digest markdown.

Edit crontab:

```bash
crontab -e
```

Add:

```cron
*/5 * * * * cd ~/Ninereeds && mkdir -p training/pipeline/msm/logs && python3 meta/scripts/msm_orchestrator_status.py --write-files --quiet >> training/pipeline/msm/logs/hermes_cron.log 2>&1
*/5 * * * * cd ~/Ninereeds && mkdir -p training/pipeline/msm/logs && tmux has-session -t codex 2>/dev/null && python3 meta/scripts/watch_codex_status.py >> training/pipeline/msm/logs/hermes_cron.log 2>&1 || true
*/15 * * * * cd ~/Ninereeds && mkdir -p training/pipeline/msm/logs && python3 meta/scripts/hermes_digest.py --quiet >> training/pipeline/msm/logs/hermes_cron.log 2>&1
```

Discord posting is Hermes-side integration, not repo logic. Every 15 minutes, post
`training/pipeline/msm/state/hermes_digest.md` if it changed materially, and immediately ping
Andi if any sentinel exists.

## Discord Message Rules

For the routine digest, post the contents of:

```text
training/pipeline/msm/state/hermes_digest.md
```

For a sentinel, ping Andi and include:

- sentinel path
- JSON `reason` and `requested_action`, if the sentinel body is JSON
- otherwise the first 500 characters of the plain-text body

For a new executor session report, include:

- path to `report_card.json`
- `session_id`
- `card_id`
- `scores.session_passed`
- `scores.requires_orchestrator`
- `executor_recommendation.recommendation_type`

For a new Phase 0/1 block report, include:

- path to `block_report.json`
- `phase_id`
- `block_id`
- `status`
- `gate_status`
- `local_recommendation`

If a report requires orchestrator action, run:

```bash
cd ~/Ninereeds && training/pipeline/start.sh
```

Do not run `start.sh` repeatedly in a tight loop. Let the next cron tick re-check status.

## Current SSH Status

The training machine is not assembled yet. Do not install SSH execution cronjobs yet.

Once the training machine exists, Andi will provide:

```text
TRAINBOX_SSH_HOST=
TRAINBOX_REPO=
MAIN_SSH_HOST=
MAIN_REPO=
```

Until those values are concrete, Hermes should only operate on `~/Ninereeds` on its current
machine and report that remote trainbox checks are not configured.

Future remote status shape, not active yet:

```bash
ssh "$TRAINBOX_SSH_HOST" "cd '$TRAINBOX_REPO' && training/pipeline/start.sh --status-only"
```

Future remote wake shape, not active yet:

```bash
ssh "$MAIN_SSH_HOST" "cd '$MAIN_REPO' && training/pipeline/start.sh"
```

## Setup Checklist

1. Verify repo:

```bash
test -d ~/Ninereeds && cd ~/Ninereeds && git status --short
```

2. Verify deterministic commands:

```bash
cd ~/Ninereeds && python3 meta/scripts/msm_orchestrator_status.py --write-files
cd ~/Ninereeds && python3 meta/scripts/hermes_digest.py
cd ~/Ninereeds && training/pipeline/start.sh --status-only
```

3. Verify optional Codex watcher:

```bash
command -v tmux
cd ~/Ninereeds && python3 meta/scripts/watch_codex_status.py --help
```

4. Install only the cron lines above.

5. Run one digest build:

```bash
cd ~/Ninereeds && python3 meta/scripts/hermes_digest.py --quiet
```

6. Send one Discord confirmation with the current digest.

7. Stop. Do not modify MSM strategy, plans, queues, concept state, corpus, updates, or
checkpoints.
