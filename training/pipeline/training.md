# Ninereeds MSM Training Reference

Active regime as of 2026-07-08: Ninereeds is trained through Mommy Says Machine
scripted developmental teaching from scratch, not broad pretraining campaigns and not free
chat.

Traditional `corpus -> epochs -> eval -> winner` training is deprecated for the active
path. Historical campaign docs remain useful evidence, but they are not the procedure for
new work.

Cold-start MSM starts from random weights and follows gated developmental phases. Its phase
contract is `training/pipeline/cold_start_phases.md`. Early cold-start failure is expected
until the current phase gate is met.

---

## Doctrine

MSM is now the training substrate.

Canonical operational sequence: `training/pipeline/runbook.md`. This file explains the
doctrine and constraints; do not use it as a replacement for the runbook steps.

The atomic unit is a **scripted word/card session**:

1. The orchestrator sets strategy, policy, queue order, and escalation rules.
2. The executor follows the queue and writes one bounded script for the next word/card.
3. The trainer executes the script mechanically against Ninereeds and writes the raw log.
4. The executor grades every scripted item and writes a fixed report card.
5. The executor either appends another allowed script or escalates to the orchestrator.
6. The orchestrator decides strategy only when needed: accept, replay, repair, probe,
   scan, rollback, update, escalate, or ask the user.
7. Proposed turns may be approved and applied through a small micro-update backend.

The orchestrator also maintains accumulated evidence:

- `concept_state.json` - per-card and per-axis attempts, successes, failures, retry
  counts, last strategy, and last session
- `session_archive.json` - queryable report-card summaries and deterministic script
  fingerprints

Raw chat logs are evidence. They are not training data by default.
Only orchestrator-approved `training_answer` turns may enter an update buffer.

---

## Roles

### Trainer

The trainer is a deterministic I/O runner. It may be a Python script.

Allowed:

- run a fixed script one prompt at a time
- call the Ninereeds inference endpoint/script
- print or send scripted teacher correction lines exactly as written
- record original and post-correction Ninereeds answers
- write complete raw logs
- report execution errors

Forbidden:

- summarize
- grade
- decide correctness
- change a script
- choose a next question
- decide whether a turn should train the model

The trainer does not need to be a language model.

### Executor

The executor performs tactical lab work. The commissioned default is
`gemma-4-26b-a4b`; jobs requiring more than 32K context route to
`ternary-bonsai-27b`, and `qwen3.6-35b-a3b` is the bounded fallback. Commissioning
evidence lives in `training/executor/BAKEOFF_2026-07-25.md`.

Allowed:

- write the next script from orchestrator policy and the word queue
- invoke the trainer or another deterministic runner
- read raw logs
- grade each scripted item independently
- fill `report_card.json`
- write `report.md`
- extract proposed training turns for orchestrator review
- append another script while auto-advance policy permits it

Forbidden:

- choose the long-range research direction
- promote checkpoints
- override rollback policy
- silently change the orchestrator policy
- continue auto-advance after an escalation condition

Executor grading categories:

- `correct`
- `wrong_on_topic`
- `wrong_off_topic`
- `ungradable`

When a teacher/correction line is present, the executor grades both the original answer and
the post-correction answer.

Executor selection is fixed in v1. A helper may return the configured default executor,
but UCB/bandit selection is intentionally deferred until there are multiple real executor
backends with comparable outcome data.

Executor prompts may optionally include `meta_scratchpad.md` only when
`orchestrator_config.json` sets `executor_prompt_context.inject_meta_scratchpad` to true.
This gate exists for ablations; scratchpad context must not become implicit
infrastructure.

### Orchestrator

The orchestrator owns strategy.

Responsibilities:

- read prior report cards, session summaries, and update summaries
- maintain campaign policy and word queue
- set escalation and retry boundaries
- decide repair, replay, probe, brain scan, update, or escalation
- approve update triggers
- protect the current best checkpoint
- decide whether auto-advance remains appropriate

The orchestrator should not spend tokens on routine script execution or routine grading.

### Lab and control supervisor

The workstation Lab is the human status and message surface. The restart-safe control
supervisor owns durable dispatch and receipt reconciliation; the trainbox worker owns
bounded execution. Neither chooses research strategy, approves checkpoint promotion, or
changes training policy. Historical Hermes setup documents are retained for provenance but
are not active contracts.

---

## Starting Point

Cold-start MSM starts from random weights. It is expected to produce byte
noise, letters, malformed fragments, word-like text, and semantically wrong sentences
before coherent answers appear. Cold-start procedures must use phase-specific frontload,
evaluation, and gate criteria.

## Strategic Provider Failover

Codex/Sol is the primary campaign brain. The workstation supervisor reads its structured
ChatGPT limits from `codex app-server` using `account/rateLimits/read` every 30 seconds and
writes the sanitized state outside Git at:

`~/.local/state/ninereeds-orchestrator-control/provider/status.json`

At a hard Codex limit, a fresh `strategic_decision` boundary is claimed exactly once and
run through the separately billed Sakana Fugu profile. A Codex command that returns a
rate-limit error also transfers that same leased boundary to Fugu. It does not create a
second boundary. Provider output is read-only and schema-bound; a deterministic validator
must accept the decision before the supervisor can materialize one child control plan.

If both providers are limited, the boundary completes as blocked without a child plan. If
the structured Codex status is unavailable, the harness refuses to guess or double-spend.
Already authorized trainbox work may finish, but provider handoff happens only between
strategic boundaries.

Every newly observed provider-limit event creates one idempotent `system_notice` in the
Lab inbox. The Lab control panel shows the selected provider and the sanitized status of
both providers.

`meta/scripts/watch_codex_status.py` and the tracked `codex_status`/`codex_brake` schemas
remain historical compatibility tools for the retired tmux-scraping loop; they are not
authoritative for the active supervisor.

---

## Session Types

### `scripted_trainer_session`

Default mode. The executor writes a fixed script. The trainer executes it exactly. Used
for ordinary concept teaching, probes, and scripted repair.

### `probe_session`

No correction. Measures current behavior for a concept or protected anchor.

### `repair_replay_session`

Rollback to the pre-session checkpoint and replay the card with prescribed correction
turns for a known failure mode.

### `contrast_session`

Targets sibling or cross-category confusion, such as cat/dog, cat/tool, tree/plant,
airport/airplane, or animal/machine.

### `protected_anchor_session`

Tests identity, unknown-boundary behavior, and permanent anchors. A protected-anchor
regression blocks promotion.

---

## Report Card Contract

Every session must produce:

- `raw_chat.jsonl` - exact prompts, teacher lines, and Ninereeds outputs
- `script.json` - script the trainer executed
- `report_card.json` - machine-readable executor report; source of truth
- `report.md` - human-readable summary
- `turn_grades.jsonl` - one grade record per scripted item
- `proposed_training.jsonl` - optional executor-proposed training turns only
- `failed_turns.jsonl` - diagnosis records for rejected or failed turns

The schema is defined in `training/pipeline/session_report_schema.md`.

Every `script.json` and `report_card.json` must record the executor context and
`msm_script_fingerprint_v1`. The fingerprint is deterministic and cheap: normalized prompt
hash, question-type sequence, contrast pairs, and target failure modes. Do not require an
embedding model for v1 duplicate detection.

When markdown and JSON disagree, `report_card.json` is authoritative.

Executor validation and orchestrator approval are separate gates:

- The executor writes `proposed_training.jsonl` when turns pass grading-level checks.
- The orchestrator may copy accepted records into an update buffer as
  `approved_training.jsonl`.
- Only `approved_training.jsonl` may appear in an `update_manifest.json`.

---

## Auto-Advance Rule

The executor may continue without consulting the orchestrator only inside the active
campaign policy.

Continue/appending is allowed when:

- at least one scripted item has a correct original answer or correct post-correction
  answer
- all answers are on-topic
- no retry/script budget is exhausted
- no sentinel, protected-anchor failure, artifact conflict, or brake condition blocks work

Escalate to the orchestrator when:

- no scripted item receives a correct answer
- at least one answer is off-topic
- the same failure repeats beyond retry limits
- protected anchors fail
- an update/promotion decision is ready
- grading uncertainty is high
- the word queue is exhausted

---

## Update Policy

There are no campaign epochs in the active regime.

The current update backend is **buffered micro-update**:

1. The executor extracts proposed training turns from one or more sessions.
2. The orchestrator approves selected turns into a named buffer.
3. A small update runs from the protected parent or last accepted checkpoint.
4. The update-candidate checkpoint is evaluated against the session target and protected anchors.
5. The update candidate is accepted only if target behavior improves and protected behavior does
   not regress.

Use update-oriented names, not epoch names:

- `session_update`
- `micro_update`
- `patch`
- `update_candidate`

Do not call these epochs.

Future work may replace buffered updates with a true online Hebbian update path. The
report-card and logging interface should not depend on the backend.

Update artifact schemas and backend invocation contract are in
`training/pipeline/update_artifact_schema.md`.

---

## Rollback-Replay Repair

If a session creates or reveals a harmful pattern, such as `a cat is a dog`, do not keep
training forward from that damaged branch by default.

Procedure:

1. Mark the failure mode in the report card.
2. Roll back to the pre-session checkpoint.
3. Generate a repair replay script.
4. Keep correction turns short and staged.
5. Retest the same prompt form and nearby contrast forms.
6. Promote only if protected anchors still pass.

Preferred correction shape:

```text
[user] Is a cat a dog?
[Ninereeds] A cat is an animal. A dog is an animal. A cat is a dog.
[teacher] A cat is an animal. A dog is an animal. A cat is not a dog.
[Ninereeds] A cat is an animal. A dog is an animal. A cat is not a dog.
[user] Is a cat a tool?
[Ninereeds] A cat is not a tool. A cat is an animal.
```

Avoid dense all-in-one correction paragraphs unless the orchestrator explicitly tests that
style. One contrast per turn is easier to attribute and safer to repair.

---

## Anytime Evaluation

Evaluation is no longer tied to epochs.

The orchestrator may request evaluation after:

- a single session
- a repair replay
- a buffer fill
- a micro-update
- a suspected regression
- inconclusive logs
- a concept becoming stable enough to promote a card state

Available diagnostics:

- chat report cards - primary evidence for session behavior
- strict grounding evals - protected gate and regression checks
- manual gates - human-readable greedy outputs
- brain maps - use when logs do not explain where a concept is routed or confused

Brain scans are diagnostic instruments. They answer where something lives and what it is
connected to; they do not replace chat evidence.

---

## Promotion Gates

An update candidate may be accepted only when:

- target concept behavior improves or remains stable as intended
- protected anchors pass
- malformed output does not increase beyond the configured threshold
- repetition collapse is absent or below threshold
- no high-severity new failure appears
- the report card and turn grades are complete

An update candidate must be rejected or rolled back when:

- protected identity or unknown-boundary anchors regress
- a harmful equivalence is learned
- malformed language dominates the session
- executor cannot produce a valid report card
- trainer deviated from the script
- the Lab or orchestrator exposes a human-attention sentinel

---

## Deprecated Active Procedure

The following are historical tools and evidence, not the active training loop:

- broad corpus ingestion as the main learning path
- fixed campaign blocks
- multi-epoch winner selection
- shaped score as a promotion target

These may still be used for controlled comparison or diagnostics, but only when the
orchestrator explicitly chooses that experiment.
