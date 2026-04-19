# BDH Training Harness Design

This document describes the **offline autonomous training/evaluation loop** scaffold created for BDH.

It exists so the system can improve through **explicit experiments**, not blind tweaking.
The design is inspired by the shape of Karpathy's `autoresearch` loop, but adapted to the BDH project, its corpus-building workflow, and its long-term architectural goals.

---

## 1. Why this exists

The BDH project is not trying to build an unbounded self-modifying growth machine.
The goal is narrower and more disciplined:

- **BDH as a model capable of chatting coherently**
- **broad knowledge base rather than deep specialization**
- **depth added later via Skill LoRA**
- **autonomous continued growth via Dream LoRA, but only in a controlled offline process**

This matters because it defines what the harness should optimize for.

The harness should help answer:

- what is the next best intervention?
- did the last intervention help?
- are we facing a data problem, an ordering problem, a wording problem, or a retention problem?
- when should we stop trying internal interventions and ask for more data?

The harness should **not** optimize for:

- vague endless growth
- arbitrary expansion of knowledge depth
- piling on training data without scope discipline
- opaque, undocumented teacher behavior

---

## 2. High-level idea

The training harness treats improvement as a sequence of **bounded research rounds**.

Each round:

1. reads the current state
2. chooses or confirms one intervention
3. executes that intervention in a bounded way
4. evaluates the result
5. logs what happened in structured artifacts
6. decides what should happen next

This is close in spirit to `autoresearch`:

- a controlled loop
- stable evaluation
- explicit keep/change/escalate decisions
- all behavior written down in transparent instruction files

But this harness is adapted to BDH in a few important ways:

- it is designed around **training data and curriculum quality**, not only code edits
- it uses **teacher interventions as explicit skills**
- it includes a **verifier layer** between teacher and student
- it respects the BDH distinction between:
  - broad core knowledge
  - later specialization via Skill LoRA
  - controlled offline growth via Dream LoRA

---

## 3. Current status

The harness is being built **before live training begins**.

Right now:

- the folder structure exists
- the core harness docs exist
- the intervention skills exist
- round IDs and reporting formats are defined
- training is still disabled because **corpus v1.0 is not complete yet**

This is intentional.

The idea is to finish the thinking and infrastructure now, while training-data creation is still ongoing, so the loop can be switched on later without inventing policy from scratch.

Current blocker encoded in state:

- `corpus_v1_0_not_complete`

---

## 4. System roles

### 4.1 Hermes = orchestrator

Hermes is the policy owner.

Responsibilities:

- own round state
- inspect logs and prior reports
- choose the next intervention
- decide whether to continue or switch strategies
- decide whether an emergency-exit request is valid
- decide whether Claude-authored requested data drafts should be rejected, iterated, or accepted

Hermes is the **research director** for the loop.

### 4.2 Claude Code = execution model

Claude Code is the worker.

Responsibilities:

- read the harness docs
- read the selected intervention skill
- execute one bounded round
- run eval, drill, reporting, or data-prep steps as instructed
- write artifacts into the round folder
- stop after one round

Claude Code is the **executor**, not the final policy owner.

### 4.3 Verifier layer

The verifier is mandatory whenever teacher-generated student-facing content is involved.

Responsibilities:

- check candidate corrections
- check contrastive pairs
- check drill corrections/prompts
- check draft data requests and draft training pieces when relevant

The verifier exists because teacher models can make subtle mistakes.
A strong model can still produce locally plausible but globally misleading corrections.

The core rule is:

> No raw teacher output reaches the student or accepted training corpus without verification.

---

## 5. Core design principles

### 5.1 Transparent over opaque

The training loop is written down as markdown docs and JSON state/templates.
Interventions are explicit, legible, and patchable.

### 5.2 One bounded round at a time

The loop is intentionally granular.
It should be possible to look at a round and understand:

- what changed
- why it changed
- what the measured outcome was
- what the next recommendation is

### 5.3 One major intervention per round

The harness should avoid changing too many major variables at once.
Otherwise it becomes difficult to know why a round improved or failed.

### 5.4 AI-led evaluation, not human vibes

The loop is designed to keep humans mostly out of the repetitive judgment process.
The idea is that:

- AI can be faster
- AI can be more consistent
- AI can classify failure types at scale
- humans often judge too much by intuition and too little by structured evidence

Humans still matter for:

- architecture decisions
- scope boundaries
- major policy changes
- reviewing whether the harness still serves the actual BDH goal

### 5.5 Targeted growth, not cancer

Growth is not the goal by itself.
The goal is the target BDH end state.

Any request for more data, more complexity, or more coverage should be filtered through:

- does this help BDH become a coherent broad-knowledge chatting model?
- should this instead be handled by a future Skill LoRA?
- is this useful breadth, or just uncontrolled expansion?

---

## 6. The intervention model

The harness is built around the idea that the teacher has access to a set of **intervention skills**.

These are stored as markdown docs in the repo, not hidden in an opaque prompt.

Current intervention set:

1. `train_longer`
2. `teacher_student_drill`
3. `oversample_cluster`
4. `reorder_curriculum`
5. `add_contrastive_pairs`
6. `simplify_wording`
7. `verify_teacher_output`
8. `request_more_data`

### 6.1 Why interventions are skills

Storing interventions as repo markdown files gives several benefits:

- transparency
- versioning
- diffability
- patchability when they fail
- easier reasoning about policy
- clearer delegation to Claude Code

This mirrors the general Hermes skill philosophy: reusable procedures should be visible, not mystical.

---

## 7. What each intervention is for

### 7.1 `train_longer`
Use when the current curriculum/data mix seems broadly sound and more training may still improve outcomes.

### 7.2 `teacher_student_drill`
Use when concepts seem almost learnable, correction helps immediately, but retention is unstable.
This is the “soft boundary” zone between evaluation and training.

### 7.3 `oversample_cluster`
Use when a particular domain lags but the overall curriculum still looks acceptable.

### 7.4 `reorder_curriculum`
Use when failures look prerequisite-shaped and the ordering appears to introduce concepts too early.

### 7.5 `add_contrastive_pairs`
Use when the student confuses nearby concepts or sibling categories and needs explicit differentiation.

### 7.6 `simplify_wording`
Use when the concept is valid but phrased above the model’s current level.

### 7.7 `verify_teacher_output`
This is not an optional enhancement; it is a required safety skill.

### 7.8 `request_more_data`
This is the emergency exit.
It is only valid once realistic in-harness interventions are exhausted.

---

## 8. The special role of teacher/student drill

One of the important adaptations in this design is that the harness explicitly includes **teacher/student drill**.

This matters because with BDH there is a softer boundary between:

- evaluation
- rehearsal
- data generation
- training

The same interaction that reveals a weakness can also become a structured corrective experience.

So the harness does not treat MSM-style evaluation as only a benchmark.
It treats it as a potential tool for:

- diagnosis
- rehearsal
- retention testing
- generation of future correction data

This is one of the main ways the BDH harness differs from a standard static eval pipeline.

---

## 9. Why the verifier is mandatory

A key design discovery here was that even a strong teacher model can make subtle conceptual mistakes.

Example class of failure:

- a correction that is locally useful but globally distorts an ontology boundary
- a negative contrast that omits an important shared parent category
- a factually true statement that is pedagogically wrong for the current level

Because LLMs do not automatically propagate all downstream consequences cleanly, the harness assumes:

> teacher output is fallible and must be checked

The verifier checks at least:

- local factual correctness
- ontology consistency
- contrast safety
- curriculum-level fit
- dependency fit
- internal corpus consistency
- pedagogical usefulness

This is one of the most important safety rules in the whole design.

---

## 10. Round IDs as state, not arbitrary labels

A major design choice is that round IDs are **stateful**.

Canonical format:

- `R{global_round}-{intervention_code}-A{attempt}-{cluster_code}`

Example:

- `R012-DR-A03-SOCROLE`

Meaning:

- global round 12
- intervention `DR` = `teacher_student_drill`
- attempt 3 in this intervention streak
- target cluster `SOCROLE`

This matters because the ID itself helps explain:

- where we are globally
- what kind of thing we are trying
- how many times we have tried it on this cluster
- whether we are still in the same local line of experimentation or have switched

The string ID is for human legibility.
The structured JSON fields remain the machine source of truth.

---

## 11. Artifact discipline

The harness uses structured outputs so Hermes can reason over them later.

Required round artifacts:

- `plan.md`
- `summary.md`
- `metrics.json`
- `decision.json`
- `claude_report.json`

Optional artifacts when relevant:

- `verifier_report.json`
- `draft_data_request.json`
- `draft_training_data.md`
- `notes.md`

Artifact schemas and templates have been defined so the execution model does not improvise format each round.

This makes the loop:

- easier to diff
- easier to automate
- easier to inspect after the fact
- easier for Hermes to continue from in future rounds

---

## 12. Emergency exit logic

The emergency exit is a crucial part of the harness.

The idea is:

- the system keeps trying internal interventions
- it does not ask for more data too early
- it only requests new data when existing interventions are exhausted

A valid emergency exit must say more than “need more data.”
It must specify:

- target cluster
- dominant failure types
- exhausted interventions
- why those interventions were exhausted
- what new data shape is needed
- how the request serves BDH’s real goal
- what remains out of scope

### 12.1 Important extension

A particularly useful extension is this:

If Claude Code proposes an emergency exit, and Hermes agrees the request is valid, Hermes may then instruct Claude Code to **draft the requested data pieces**.

Those drafts are then reviewed and either:

- rejected
- iterated
- accepted

So the emergency exit does not only identify missing data.
It can also become the trigger for a bounded, reviewable data-generation step.

---

## 13. Cron model

The intended operational cadence is:

- **one round per hour**

Why this cadence:

- bounded progress
- clean checkpoints
- easier debugging
- easier historical review
- no need for constant human supervision

Because cron runs in a fresh session, the cron worker must always re-read the canonical files in `training/`.
The system should not rely on stale conversational context.

At the moment, the cron prompt exists as a template, but live training is still disabled until the corpus gate opens.

---

## 14. Current infrastructure created

The scaffold now includes:

### Top level
- `training/README.md`
- `training/training_harness_design.md` (this file)

### Harness docs
- `training/harness/intervention_registry.md`
- `training/harness/decision_policy.md`
- `training/harness/verifier_policy.md`
- `training/harness/emergency_exit_policy.md`
- `training/harness/claude_worker_contract.md`
- `training/harness/cron_round_worker_prompt.md`
- `training/harness/ROUND_STATE.json`
- `training/harness/artifact_schemas.md`

### Artifact templates
- `training/harness/metrics.template.json`
- `training/harness/decision.template.json`
- `training/harness/claude_report.template.json`
- `training/harness/verifier_report.template.json`
- `training/harness/draft_data_request.template.json`
- `training/harness/README_artifact_templates.md`

### Teacher skills
- `training/teacher_skills/train_longer.md`
- `training/teacher_skills/teacher_student_drill.md`
- `training/teacher_skills/oversample_cluster.md`
- `training/teacher_skills/reorder_curriculum.md`
- `training/teacher_skills/add_contrastive_pairs.md`
- `training/teacher_skills/simplify_wording.md`
- `training/teacher_skills/verify_teacher_output.md`
- `training/teacher_skills/request_more_data.md`
- `training/teacher_skills/README.md`

### Round/log structure
- `training/rounds/README.md`
- `training/logs/README.md`
- `training/logs/round_index.jsonl`
- `training/logs/intervention_history.jsonl`
- `training/logs/emergency_requests.jsonl`

---

## 15. What has not been turned on yet

Important: this is still a scaffold.

Not yet active:

- live training rounds
- real checkpoint evolution through the harness
- real hourly cron execution of rounds
- real cluster-code registry
- real campaign/streak tracking beyond the current scaffold state
- full sample round artifact directories populated from real runs

This is fine.
The point right now is to finish the training corpus while keeping the future loop legible and ready.

---

## 16. What this design gives us

The value of this design is that it turns “train the baby dragon” into:

- a research process
- a logged experiment loop
- a transparent intervention system
- a policy-governed training/eval environment

instead of:

- blind fiddling
- ad hoc prompting
- hidden undocumented teacher behavior
- random corpus growth

This is probably the most important conceptual shift.

We are no longer only asking:

- can the model improve?

We are asking:

- what kind of intervention best fits this failure?
- how do we know?
- what evidence do we require before switching strategies?
- when do we stop trying internal fixes and request new data?
- how do we keep all of this aligned with the real BDH goal?

---

## 17. Short summary

The BDH training harness is an offline, autonomous, skill-driven experiment loop.

- Hermes orchestrates.
- Claude Code executes one bounded round at a time.
- Interventions are stored as explicit repo skills.
- Structured artifacts record what happened.
- Teacher-generated student-facing content must pass verification.
- Emergency exit is allowed only after realistic interventions are exhausted.
- Any resulting data request must be specific, bounded, and aligned with BDH’s actual target state.

The whole purpose is to make future training:

- explicit
- legible
- auditable
- targeted
- and safe enough to improve the dragon without turning growth itself into the objective.
