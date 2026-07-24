# MSM Pipeline

Design reference for the active autonomous training pipeline.

Last updated: 2026-07-08

---

## Pipeline Shape

```text
orchestrator strategy
  -> executor selects the next phase-appropriate item from policy and writes one script
  -> trainer runs the script mechanically against Ninereeds
  -> raw chat log
  -> executor grades every scripted item
  -> executor either appends another script or escalates a report
  -> orchestrator decides strategy only when needed
  -> optional approved micro-update / probe / replay / scan / escalation
```

The active loop is cold-start, phase-gated, and epochless. One script is the smallest
execution unit. Cold-start MSM starts from random weights and follows the phase contract in
`cold_start_phases.md`; each phase defines frontload data, evaluation probes, and success
gates before the next phase can start.

Phase 0 and Phase 1 use a frontload block runner before ordinary MSM sessions are useful:

```text
phase policy -> generate examples -> train block -> probe -> block report
```

The current bounded runner is `meta/scripts/msm_phase_runner.py`. The normal recovery
entrypoint is `training/pipeline/start.sh`, which reconciles the workstation control ledger
through the installed supervisor. Phase blocks run only on the trainbox after an explicit
durable plan is accepted.

---

## Directories

Planned active layout:

```text
training/pipeline/msm/
  state/
    phase_registry.json
    concept_state.json
    session_archive.json
    protected_anchors.json
    orchestrator_state.json
    orchestrator_config.json
    meta_scratchpad.md
    orchestrator_status.json
    orchestrator_status.md
    active_campaign_policy.json
    word_queue.json
    auto_advance_state.json
    trainbox_heartbeat.json
  plans/
    PLAN_ID.json
  sessions/
    SESSION_ID/
      script.json
      raw_chat.jsonl
      turn_grades.jsonl
      report_card.json
      report.md
      proposed_training.jsonl
      failed_turns.jsonl
  phase_blocks/
    PHASE_ID/
      BLOCK_ID/
        frontload.jsonl
        probes.jsonl
        probe_results.jsonl
        train_stdout.log
        block_report.json
  buffers/
    BUFFER_ID/
      approved_training.jsonl
  updates/
    UPDATE_ID/
      update_manifest.json
      source_sessions.txt
      update_candidate_eval.json
  logs/
    orchestrator.jsonl
    executor.jsonl
```

Existing historical campaign logs remain under `training/logs/`.

---

## Components

### Orchestrator

Strategic owner. Reads report cards and state, chooses policy, and writes bounded plans.

Required outputs:

- campaign/session policy JSON
- strategic decision JSON when escalation occurs
- human-attention sentinel when blocked

The orchestrator should spend reasoning tokens on strategy, not routine script execution or
routine grading. It is called when the executor reaches a stop condition, when update or
promotion decisions are ready, or when the policy boundary is exhausted.

### Executor

Tactical local model worker. Converts policy into scripts, reads raw logs, grades each
scripted item, writes reports, and extracts proposed training turns.

Commissioned local executor models:

- `gemma-4-26b-a4b` - default
- `ternary-bonsai-27b` - long-context route above 32K
- `qwen3.6-35b-a3b` - bounded fallback

Quality matters more than throughput. The executor should be evaluated by script quality,
grading reliability, and ability to escalate at the right time.

Executor selection is fixed in v1. The orchestrator may call a `select_executor` helper,
but it must currently return the configured default executor. Do not implement UCB or
bandit executor routing until there are multiple real backends with comparable outcome
data.

Required outputs:

- `script.json`
- `turn_grades.jsonl`
- `report_card.json`
- `report.md`
- optional `proposed_training.jsonl`

Each `script.json` records executor ID, selection method, whether `meta_scratchpad.md`
was injected, and a deterministic script fingerprint. The fingerprint uses normalized
text, question-type sequence, contrast pairs, and target failure modes. It is deliberately
not embedding-based in v1.

### Trainer

Deterministic runner. The trainer may be a Python script. It does not need to be a model.

The trainer executes fixed scripts only:

1. send the scripted user prompt to Ninereeds
2. record Ninereeds' answer
3. print or send the scripted correction/teacher line
4. record the follow-up Ninereeds answer when the script asks for one
5. write a clean `raw_chat.jsonl`

The trainer must not grade, summarize, choose a next question, or alter the script.

### Lab and control services

The workstation Lab is the notification, message, and visibility layer. The orchestrator
supervisor and trainbox worker are deterministic services backed by durable ledgers. They
may dispatch or execute only explicit bounded plans and must not approve checkpoint
promotion or invent research strategy.

### Codex Brake

Codex need not remain in a tmux session for the deterministic supervisor, trainbox worker,
or local executor to continue. The brake artifacts remain an optional policy input for
future subscription-backed strategic wakes; they do not gate already-authorized local
ledger reconciliation.
The visible status should include rate limits, token counters, context stats, session ID,
and project root. The watchdog observes the pane passively:

```bash
python3 meta/scripts/watch_codex_status.py
```

The watchdog writes `training/pipeline/msm/state/codex_status.json`,
`training/pipeline/msm/state/codex_status.md`, and `training/pipeline/msm/state/codex_brake.json`.
`codex_status.json` is observational. `codex_brake.json` is normative and must be read
before starting a new orchestration boundary.

Do not monitor by sending `/status` or `/statusline` into the live Codex session. The
watchdog should only use `tmux capture-pane` against already-visible output.

Brake actions:

- `continue` - proceed normally.
- `conservative_mode` - skip optional probes, cleanup, broad scans, and exploratory work.
- `finish_current_only` - finish the current safe boundary, persist state, then stop or
  sleep.
- `pause_until_reset` - do not launch sessions, call executor for new work, or apply
  updates until reset is confirmed.
- `blocked_unknown_reset` - preserve or write `BLOCKED` and stop.

Schemas:

- `training/pipeline/codex_status_schema.json`
- `training/pipeline/codex_brake_schema.json`
- `training/pipeline/cold_start_phase_schema.json`

### Auto-Advance Policy

Codex/orchestrator may authorize bounded executor auto-advance through:

- `training/pipeline/msm/state/active_campaign_policy.json`
- `training/pipeline/msm/state/word_queue.json`
- `training/pipeline/msm/state/auto_advance_state.json`
- `training/pipeline/msm/state/concept_state.json`
- `training/pipeline/msm/state/session_archive.json`

The executor follows the word queue and writes one script at a time. After grading a
script, it may append another script for the same word only while all of these remain true:

- at least one scripted item has a correct original answer or correct post-correction
  answer
- no answer is off-topic
- the retry/script budget for the word is not exhausted
- no protected-anchor, malformed-output, artifact-conflict, or brake condition blocks work

The executor must escalate to the orchestrator when any of these occur:

- no scripted item receives a correct answer
- at least one answer is off-topic
- the same failure repeats beyond retry limits
- protected anchors fail
- an update/promotion decision is ready
- artifacts conflict or grading uncertainty is high
- the queue is exhausted
- the Codex brake blocks new work

Allowed executor actions:

- `PASS_AUTONEXT`
- `PASS_BUT_BUFFER`
- `RETRY_SAME_WORD`
- `ESCALATE_CODEX`
- `ESCALATE_HUMAN`

Scheduler scoring should use accumulated state when available:

```text
score = learnability + severity + underexplored_bonus - retry_penalty
```

Protected anchors may add a separate priority weight, but protected-anchor failures still
block promotion rather than acting like ordinary failed cards.

Schemas:

- `training/pipeline/active_campaign_policy_schema.json`
- `training/pipeline/word_queue_schema.json`
- `training/pipeline/auto_advance_state_schema.json`

---

## Session Lifecycle

The canonical executable step sequence is `runbook.md`. This lifecycle is a design map,
not a second runbook.

1. **Plan** - orchestrator sets campaign policy, word queue, limits, and escalation rules.
2. **Script** - executor writes one exact prompt/correction script for one word/card.
3. **Execute** - trainer runs the script against Ninereeds and logs all turns.
4. **Grade** - executor grades each scripted item individually.
5. **Auto-advance or escalate** - executor appends another script only if policy permits.
6. **Decide** - orchestrator handles escalations, updates, promotion, repair, or user asks.
7. **Update** - optional buffered micro-update from orchestrator-approved turns only.
8. **Gate** - protected anchors and target checks determine promotion.

---

## Sentinel Files

Canonical names are defined in `sentinel_files.md`:

- `HUMAN_ATTENTION` - user action required
- `BLOCKED` - automation cannot continue safely
- `TRAINING_MACHINE_DOWN` - local runner unavailable
- `API_CREDITS_EXHAUSTED` - paid API worker cannot continue
- `PROMOTION_REVIEW_REQUIRED` - update candidate needs manual approval

The Lab exposes sentinel files and blocked control receipts to the user.

---

## Update Backend

Initial implementation: buffered micro-updates.

Invocation contract:

```bash
python3 meta/scripts/msm_micro_update.py --manifest training/pipeline/msm/updates/UPDATE_ID/update_manifest.json
```

If that script does not exist yet, the orchestrator must write `BLOCKED` and request
implementation. Update artifact schemas are defined in `update_artifact_schema.md`.
Thresholds and buffer triggers are defined by `msm_config.md`.

The rest of the pipeline must treat update execution as a backend. Later backends may
support true online Hebbian updates, but logs, report cards, and orchestrator decisions
should not depend on that implementation detail.

---

## Deprecated Pipeline

The old campaign runner flow trained corpus files for fixed epoch counts and selected
winners from eval/brain-map metrics. That flow is archived as historical infrastructure.

Use it only for explicit comparison experiments.
