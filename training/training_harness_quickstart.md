# BDH Training Harness Quickstart

This is the short version of the BDH training harness design.
For the full rationale and architecture, see:

- `training/training_harness_design.md`

---

## What this is

The BDH training harness is an **offline autonomous experiment loop** for improving the model in a controlled way.

It is inspired by the shape of Karpathy's `autoresearch`, but adapted to BDH.

Instead of blind training tweaks, the harness runs **bounded research rounds**:

1. choose one intervention
2. execute it
3. evaluate the result
4. log what happened
5. decide what to do next

---

## What it is for

The harness is designed around the actual BDH goal:

- **BDH as a model capable of chatting coherently**
- **broad knowledge base rather than deep specialization**
- **depth added later via Skill LoRA**
- **autonomous continued growth via Dream LoRA, but only in a controlled offline process**

This is **not** an infinite-growth machine.
The system should optimize for targeted improvement toward the goal state, not for endless expansion.

---

## Main roles

### Hermes = orchestrator

Hermes:

- owns the round state
- reads reports
- chooses the next intervention
- decides whether to continue, switch, or escalate
- decides whether an emergency-exit request is valid
- decides whether Claude-authored requested data drafts should be rejected, iterated, or accepted

### Claude Code = execution model

Claude Code:

- reads the harness docs
- reads the selected intervention skill
- executes exactly one bounded round
- writes structured artifacts to disk
- stops

### Verifier = safety layer

The verifier checks teacher-generated student-facing content before it is accepted.

That includes:

- corrections
- drill prompts
- contrastive pairs
- draft data requests
- draft training pieces when relevant

Core rule:

> No raw teacher output reaches the student or accepted training corpus without verification.

---

## Current intervention skills

Stored in:

- `training/teacher_skills/`

Current set:

1. `train_longer`
2. `teacher_student_drill`
3. `oversample_cluster`
4. `reorder_curriculum`
5. `add_contrastive_pairs`
6. `simplify_wording`
7. `verify_teacher_output`
8. `request_more_data`

These are markdown files in the repo so they stay:

- transparent
- versioned
- patchable
- easy to reason about

---

## Why teacher/student drill matters

The harness explicitly includes **teacher/student drill** because with BDH there is a soft boundary between:

- evaluation
- rehearsal
- correction
- data generation
- training

MSM-style interaction is not only an eval. It can also be used as a bounded corrective intervention.

---

## Why the verifier matters

Teacher models can make subtle conceptual mistakes.
Even strong models can produce corrections that are locally plausible but globally misleading.

The verifier checks at least:

- factual correctness
- ontology consistency
- contrast safety
- curriculum-level fit
- dependency fit
- internal corpus consistency
- pedagogical usefulness

---

## Round IDs

Round IDs are **stateful**, not arbitrary.

Canonical format:

- `R{global_round}-{intervention_code}-A{attempt}-{cluster_code}`

Example:

- `R012-DR-A03-SOCROLE`

Meaning:

- global round 12
- intervention `DR` = `teacher_student_drill`
- local attempt 3
- target cluster `SOCROLE`

This makes the history legible at a glance.

---

## Required round artifacts

Each round should usually produce:

- `plan.md`
- `summary.md`
- `metrics.json`
- `decision.json`
- `claude_report.json`

Optional when relevant:

- `verifier_report.json`
- `draft_data_request.json`
- `draft_training_data.md`
- `notes.md`

Schemas/templates are stored in:

- `training/harness/artifact_schemas.md`
- `training/harness/*.template.json`

---

## Emergency exit

The system should only request more data after realistic internal interventions are exhausted.

A valid emergency-exit request must specify:

- target cluster
- dominant failure types
- exhausted interventions
- why they were exhausted
- what new data shape is needed
- how it serves the BDH goal
- what remains out of scope

If Claude proposes an emergency exit and Hermes agrees, Hermes may then tell Claude to draft the requested data pieces.
Those drafts are then reviewed and either:

- rejected
- iterated
- accepted

---

## Cron model

Intended cadence:

- **one round per hour**

But this is not turned on yet.

At the moment, the harness is still a scaffold because the corpus is not finished.
Training remains disabled until corpus v1.0 is complete.

---

## Current status

The scaffold already exists under:

- `training/`

Key files:

- `training/README.md`
- `training/training_harness_design.md`
- `training/harness/ROUND_STATE.json`
- `training/harness/decision_policy.md`
- `training/harness/verifier_policy.md`
- `training/harness/emergency_exit_policy.md`
- `training/harness/artifact_schemas.md`
- `training/teacher_skills/*.md`

Current blocker in state:

- `corpus_v1_0_not_complete`

---

## Short summary

The BDH training harness turns future training into:

- explicit experiments
- logged rounds
- transparent intervention skills
- verifier-gated teacher behavior
- bounded escalation to new data only when necessary

It exists so the baby dragon can be improved through a legible research loop, not through blind tweaking or uncontrolled growth.
