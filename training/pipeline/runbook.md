# MSM Runbook

Open this document when running or supervising the active training loop.

This runbook is for the cold-start MSM loop. Read
`training/pipeline/msm/state/phase_registry.json` before planning. Early nonsense is not
ordinary concept failure; use the current phase gates.

---

## Step 0 - Orient

Check the Codex brake, active sessions, pending reports, and human-attention sentinels.

```bash
test -f training/pipeline/msm/state/codex_brake.json && cat training/pipeline/msm/state/codex_brake.json || true
ps aux | grep -E "trainer|ninereeds|chat|inference" | grep -v grep
find training/pipeline/msm \( \
  -name HUMAN_ATTENTION \
  -o -name BLOCKED \
  -o -name TRAINING_MACHINE_DOWN \
  -o -name API_CREDITS_EXHAUSTED \
  -o -name PROMOTION_REVIEW_REQUIRED \
\) 2>/dev/null
find training/pipeline/msm/sessions -maxdepth 2 -name report_card.json 2>/dev/null | tail -20
```

States:

- **Codex brake missing** - continue manually, but write a warning to
  `training/pipeline/msm/logs/orchestrator.jsonl` before autonomous work.
- **Codex brake `continue`** - normal campaign mode.
- **Codex brake `conservative_mode`** - avoid optional probes, broad scans, cleanup,
  nonessential repo edits, and exploratory branches.
- **Codex brake `finish_current_only`** - finish the current safe boundary, persist
  state, then stop or sleep.
- **Codex brake `pause_until_reset`** - do not launch a new session, call executor for
  new work, or apply updates. Write a pause note to
  `training/pipeline/msm/logs/orchestrator.jsonl`, sleep until `reset_at` in an autonomous shell
  loop, then re-read the brake.
- **Codex brake `blocked_unknown_reset`** - write or preserve `BLOCKED` and stop.
- **Session running** - monitor, do not launch another session for the same card.
- **Raw log exists, report missing** - task executor to write the report card.
- **Report exists, decision missing** - orchestrator reads the report and writes next plan.
- **Human sentinel exists** - Lab reports it; wait for manual resolution.

---

## Step 1 - Read Current State

Read:

- phase registry
- latest orchestrator log
- active campaign policy
- word queue and auto-advance state
- latest `report_card.json` for the target concept
- concept state JSON
- session archive JSON
- protected-anchor status
- parent checkpoint metadata

Do not plan from memory. JSON artifacts are the source of truth.

---

## Step 2 - Orchestrator Sets Policy

The orchestrator writes or updates bounded policy for the executor:

- campaign objective
- word/card queue
- parent checkpoint
- permitted session modes
- max scripts per word
- max retries per word
- target axes
- forbidden scope
- escalation conditions
- whether proposed training turns may be extracted
- whether a micro-update is allowed after a report
- scheduler weights for learnability, severity, under-exploration, retry penalty, and
  protected-anchor priority
- whether `meta_scratchpad.md` may be injected into executor prompts

Before writing or dispatching new work, re-check `training/pipeline/msm/state/codex_brake.json`.
Do not start new work when the action is `pause_until_reset` or `blocked_unknown_reset`.

If the policy needs human input, write the configured sentinel file and stop.

---

## Step 3 - Executor Builds One Script

For Phase 0 and Phase 1 cold-start frontload blocks, use
`meta/scripts/msm_phase_runner.py` instead of the later MSM session loop. The runner
generates direct training examples, calls `train.py`, and writes a phase block report.

For later phase-appropriate scripted sessions:

The executor follows the current word queue and writes one `script.json`.

Schema contract: `training/pipeline/script_and_raw_log_schema.md`.

Script requirements:

- one word/card focus
- fixed ordered prompts
- no trainer discretion
- teacher/correction lines written exactly
- expected-answer metadata where useful
- per-item grading metadata
- stop conditions for execution errors only
- script ID and orchestrator plan/policy ID
- executor ID and fixed selection method
- `meta_scratchpad` injection flag
- deterministic script fingerprint using normalized prompt text, question-type sequence,
  contrast pairs, and target failure modes

The trainer must be able to execute the script without interpreting the research goal.

Before dispatch, reject an exact structural duplicate unless the active policy explicitly
allows repetition and records the reason. Prompt-overlap warnings are advisory; exact
fingerprint duplicates are a hard stop by default.

Example item shape:

```text
[user]Is a dog a cat?
[Ninereeds]
[teacher]A dog is not a cat.
[Ninereeds]
```

The trainer sends the user line to Ninereeds, records the original answer, prints or sends
the teacher line, then records the post-correction answer when requested by the script.

---

## Step 4 - Trainer Executes

The trainer is a deterministic runner, usually a Python script. It runs the script against
Ninereeds and writes `raw_chat.jsonl`.

Each `raw_chat.jsonl` line must validate against
`training/pipeline/raw_chat_line_schema.json`.

Trainer records:

- turn ID
- script item ID
- user prompt
- Ninereeds original answer
- teacher correction line, if present
- Ninereeds post-correction answer, if requested
- timestamp
- execution error, if any

Trainer does not grade, summarize, choose the next question, or alter the script.

---

## Step 5 - Executor Grades

The executor reads `raw_chat.jsonl` and writes:

- `turn_grades.jsonl`
- `report_card.json`
- `report.md`
- `proposed_training.jsonl` if proposed training turns exist
- `failed_turns.jsonl`

The executor also carries the script fingerprint and executor context into
`report_card.json`.

Every scripted item receives an individual grade. At minimum the grade records:

1. the user line
2. original answer status: `correct`, `wrong_on_topic`, `wrong_off_topic`, or `ungradable`
3. post-correction status when present: `correct`, `wrong_on_topic`, `wrong_off_topic`,
   or `not_applicable`

Example:

```text
1. [user] Is a dog a cat?
   original answer: incorrect, on-topic
   after correction: correct
```

---

## Step 6 - Executor Auto-Advances Or Escalates

The executor may append another script for the same word only while all of these remain
true:

- at least one scripted item has a correct original answer or correct post-correction answer
- no answer is off-topic
- malformed/repetition thresholds are not exceeded
- retry/script limits are not exhausted
- no protected-anchor, artifact-conflict, or Codex brake condition blocks work

The executor must wrap the session and send the file to the orchestrator when:

- no scripted item receives a correct answer
- at least one answer is off-topic
- the same failure repeats beyond retry limits
- a protected anchor fails
- an update/promotion decision is ready
- grading uncertainty is high
- the word queue is exhausted
- a sentinel or brake blocks progress

Executor recommendations are advisory. The orchestrator decides strategy.

---

## Step 7 - Orchestrator Decides

Possible decisions:

- accept session evidence and update concept state
- auto-advance to the next word
- run another script on the same word
- rollback and replay with repair
- run protected anchors
- run grounding eval
- run brain map
- apply buffered micro-update
- reject session as unusable
- escalate to the user through the Lab message/status surface

Record the decision in a stable JSON artifact.

After accepting a report card as usable evidence, update:

- `training/pipeline/msm/state/concept_state.json`
- `training/pipeline/msm/state/session_archive.json`

`concept_state.json` accumulates per-card and per-axis attempts, successes, failures,
off-topic/malformed counts, last strategy, and last session. `session_archive.json` indexes
the report card, script fingerprint, executor ID, strategy, scores, axes, and failure
modes so later scheduling can query evidence without reparsing every session directory.

---

## Step 8 - Optional Micro-Update

If allowed:

1. Confirm `proposed_training.jsonl` exists if executor proposed trainable turns.
2. Confirm the orchestrator copied accepted records into `approved_training.jsonl`.
3. Confirm every proposed/approved turn validates against `training_turn_schema.json`.
4. Confirm approved turn count meets `min_approved_turns_for_update`.
5. Confirm `approved_turn_count` equals the line count of every referenced
   `approved_training.jsonl` file combined.
6. Confirm parent checkpoint is correct.
7. Confirm `output_checkpoint` does not already exist, unless an explicit overwrite
   decision has been recorded.
8. Write `update_manifest.json`.
9. Run the micro-update backend command from `update_artifact_schema.md`.
10. Write `update_candidate_eval.json`.
11. Accept or reject the update candidate.

Never update from raw chat logs.
Buffer policy and quality thresholds are documented in `msm_config.md`.
The MSM backend intentionally passes `--skip-training-audit` to `train.py`; do not remove
that unless the MSM manifest/update gates are replaced by a stronger equivalent.

---

## Step 9 - Lab Visibility

The Lab reports:

- session completed
- report card summary
- accepted/rejected update candidate
- blocked state
- human attention required

The Lab exposes sentinel files, blocked/dead-letter receipts, and machine health. The user
may respond through Lab messages.

Sentinel contract: `training/pipeline/sentinel_files.md`.
