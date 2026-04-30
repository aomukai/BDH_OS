# Training Harness

This directory defines the **offline training/evaluation control loop** for Ninereeds on the BDH architecture.

It is intentionally designed as a **transparent harness**, not a hidden pile of prompts.
Every intervention the teacher may use is written down as a markdown skill, versioned in the repo,
reviewable by humans, and patchable when it fails.

## Purpose

The harness exists to support the long-term Ninereeds goal:

- **Ninereeds as a model capable of chatting coherently**
- **broad knowledge base rather than deep specialization**
- **depth added later via Skill LoRA**
- **autonomous continued growth via Dream LoRA, but only in a controlled offline process**

This is **not** an infinite-growth machine.
The goal is targeted, bounded improvement toward a clear end state.
If a data request does not serve that goal, it should be rejected.

## Current Status

The corpus v1.0 audit is complete, and the training activation gate has been opened.
Live training rounds are now active.

Key points:

- the harness folder structure and policies are stable
- round numbering and execution are live
- worker prompts and intervention skills are actively being used and refined
- model training is enabled and running in a controlled, offline loop

## Extended Capabilities

The base harness has been extended with a **merge-supervised evolutionary pipeline**.
Full specification lives in `training_harness_design.md`. Summary:

- **Branching:** goal-specific capability is developed on side branches, not directly on mainline
- **Frontier:** at most three live candidates per campaign (champion / challenger / explorer)
- **Merge pipeline:** branches are promoted to mainline only after passing a four-gate promotion sequence (target improvement, merge integrity, global safety, retention probe)
- **Lineage tracking:** generation depth and ancestry distance are tracked to prevent redundant or high-risk merges
- **Bias-balancing circuit breaker:** tie-breaks between orchestrator and executor use a deterministic even/odd round rule — zero compute cost, auditable, resistant to single-model dominance

This is not open-ended population search. It is controlled breeding: local search around explicit hypotheses, with narrow promotion rules and a bias toward reversibility.

## Round ID Scheme

Round IDs are **stateful and legible**, not arbitrary serial numbers.

Canonical format:

- `R{global_round}-{intervention_code}-A{attempt}-{cluster_code}`

Example:

- `R012-DR-A03-SOCROLE`

This means:

- global round 12
- intervention `DR` (`teacher_student_drill`)
- attempt 3 within the current intervention streak for that cluster
- target cluster `SOCROLE`

Keep the structured machine-readable fields in JSON as separate values as well. The string ID is for human legibility; the structured fields remain the source of truth.

## Core Roles

- **Hermes / orchestrator (GPT)**
  - owns round state
  - chooses the next intervention
  - reads reports
  - decides whether to continue, switch intervention, escalate, or trigger a merge

- **Gemini / executor**
  - executes one bounded round
  - reads harness policy + selected intervention skill
  - runs eval / drill / data operations / reporting
  - writes artifacts to disk
  - may materialise branches, produce sandbox merges, run repair rounds
  - does not invent policy or silently promote anything

- **Verifier layer**
  - checks any teacher-generated student-facing correction, drill prompt, or candidate training pair
  - validates lineage completeness, merge-plan correctness, and evaluation integrity
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
7. **Emergency-exit requests may themselves trigger a Gemini-authored draft-data creation step for orchestrator review**
8. **Tier 1 evaluation (syntax, loadability, formatting) runs as an automated pre-filter before any model judgment is invoked**
9. **The circuit breaker may only resolve decisions where both options are already valid under harness policy — it never overrides hard gates**

## Round Lifecycle

1. Load `harness/ROUND_STATE.json`
2. Run Tier 1 automated pre-filter — hard stop if failed
3. Read harness policy docs
4. Read the selected teacher skill
5. Execute exactly one bounded round
6. Write round artifacts into `rounds/<round_id>/`
7. Update logs + state
8. Stop

## Future Cron Use

The intended cadence is **one round per hour** via cron, with at least one hour between runs to avoid rate limit walls.
The cron worker should always use the canonical documents in this directory, not stale prompt memory.
