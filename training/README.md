# Training Harness

This directory defines the **offline training/evaluation control loop** for BDH.

It is intentionally designed as a **transparent harness**, not a hidden pile of prompts.
Every intervention the teacher may use is written down as a markdown skill, versioned in the repo,
reviewable by humans, and patchable when it fails.

## Purpose

The harness exists to support the long-term BDH goal:

- **BDH as a model capable of chatting coherently**
- **broad knowledge base rather than deep specialization**
- **depth added later via Skill LoRA**
- **autonomous continued growth via Dream LoRA, but only in a controlled offline process**

This is **not** an infinite-growth machine.
The goal is targeted, bounded improvement toward a clear end state.
If a data request does not serve that goal, it should be rejected.

## Current Status

This harness is being built **before** training starts.
We are waiting for **corpus v1.0 completion** before enabling real training rounds.

That means:

- the folder structure and policies can be built now
- round numbering can begin now
- worker prompts and intervention skills can be refined now
- actual model training remains disabled until the corpus gate is opened

## Round ID Scheme

Round ids should be **stateful and legible**, not arbitrary serial numbers.

Canonical format:

- `R{global_round}-{intervention_code}-A{attempt}-{cluster_code}`

Example:

- `R012-DR-A03-SOCROLE`

This means:

- global round 12
- intervention `DR` (`teacher_student_drill`)
- attempt 3 within the current intervention streak for that cluster
- target cluster `SOCROLE`

Keep the structured machine-readable fields in JSON as separate values as well. The string id is for human legibility, while the structured fields remain the source of truth.

## Core Roles

- **Hermes / orchestrator**
  - owns round state
  - chooses the next intervention
  - reads reports
  - decides whether to continue, switch intervention, or escalate

- **Claude Code / execution model**
  - executes one bounded round
  - reads harness policy + selected intervention skill
  - runs eval / drill / data operations / reporting
  - writes artifacts to disk

- **Verifier layer**
  - checks any teacher-generated student-facing correction, drill prompt, or candidate training pair
  - blocks unsafe or conceptually misleading outputs

## Directory Layout

- `harness/` — controller policies, state, decision rules, worker contract
- `teacher_skills/` — intervention docs the teacher may use
- `rounds/` — one folder per round
- `logs/` — durable append-only histories and summaries

## Design Rules

1. **One bounded round at a time**
2. **One major intervention per round** unless a skill explicitly defines a micro-loop
3. **Every decision must be logged**
4. **No raw teacher output reaches the student without verification**
5. **When all interventions are exhausted, request targeted new data**
6. **Emergency-exit data requests must be specific and goal-shaped**
7. **Emergency-exit requests may themselves trigger a Claude-authored draft-data creation step for orchestrator review**

## Round Lifecycle

1. Load `harness/ROUND_STATE.json`
2. Read harness policy docs
3. Read the selected teacher skill
4. Execute exactly one bounded round
5. Write round artifacts into `rounds/<round_id>/`
6. Update logs + state
7. Stop

## Future Cron Use

The intended cadence is **one round per hour** via cron.
The cron worker should always use the canonical documents in this directory, not stale prompt memory.
