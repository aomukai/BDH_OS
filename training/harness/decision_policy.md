# Decision Policy

This document tells the orchestrator how to choose the next round.

## Goal

Improve BDH toward the target state:

- coherent chat ability
- broad grounded knowledge
- bounded, targeted growth
- no blind optimization toward infinite expansion

## General Rules

1. One major intervention per round.
2. Preserve a clear causal story: what changed, why, and what happened next.
3. Prefer the smallest intervention likely to improve the failure pattern.
4. Avoid changing multiple major variables at once.
5. Keep all decisions auditable.

## Inputs to the Decision

The orchestrator should read:

- `training/harness/ROUND_STATE.json`
- latest `training/logs/round_index.jsonl` entries
- the previous round's `metrics.json`
- the previous round's `decision.json`
- the previous round's `summary.md`
- any verifier rejection or warning files

## Required Evaluation Dimensions

At minimum, every decision should consider:

- baseline pass / weak pass / fail rate
- retention pass rate
- dominant failure taxonomy
- whether corrections stick
- whether failures are local or global
- whether the model improves with more exposure alone
- whether current requests align with the BDH goal state

## Default Intervention Order

This is a preference order, not a hard law:

1. `train_longer`
2. `teacher_student_drill`
3. `oversample_cluster`
4. `reorder_curriculum`
5. `add_contrastive_pairs`
6. `simplify_wording`
7. `request_more_data`

The orchestrator may skip ahead if the evidence clearly indicates a different best move.

## When to Prefer Each Intervention

### Prefer `train_longer`
When:
- metrics are still improving
- failures are shrinking without structural changes
- no strong prerequisite problem is visible

### Prefer `teacher_student_drill`
When:
- concepts are nearly learnable
- corrective interaction helps immediately
- retention remains unstable
- the student may benefit from rehearsal before corpus edits

### Prefer `oversample_cluster`
When:
- failure is concentrated in one domain
- the general curriculum is acceptable
- additional targeted exposure is likely to help

### Prefer `reorder_curriculum`
When:
- failures are dependency-shaped
- simpler prerequisite concepts are not stable yet
- rescue only works after reducing task complexity

### Prefer `add_contrastive_pairs`
When:
- the student confuses sibling categories or nearby roles
- positive-only statements are not enough
- explicit differentiation is needed

### Prefer `simplify_wording`
When:
- concept content is fine
- wording is too abstract or overloaded
- the model performs better when the target is reduced to simpler anchors

### Prefer `request_more_data`
Only when:
- all realistic in-harness interventions are exhausted
- missing data is the likely bottleneck
- a specific, bounded request can be written

## Plateau Rules

### Training Plateau
Treat `train_longer` as plateaued if:
- two consecutive training rounds show no meaningful MSM improvement, or
- the skill-defined budget is exhausted

### Drill Plateau
Treat `teacher_student_drill` as plateaued if:
- two consecutive drill runs show no meaningful retention gain, or
- corrected items do not generalize beyond the exact prompt form

## Emergency Exit Review

If the execution model takes the emergency exit and requests more data:

1. Hermes reviews whether interventions truly are exhausted.
2. If Hermes agrees, Hermes may direct Claude Code to draft the requested corpus pieces.
3. Those drafts must then be reviewed against the verifier and scope rules.
4. Hermes may reject, request iteration, or accept the drafts.

## Scope Gate

Reject or downgrade any candidate action that pushes toward:

- unnecessary depth instead of breadth
- uncontrolled endless growth
- data that does not improve BDH-as-chatting-model goals
- complexity that should be delegated to Skill LoRA rather than core corpus growth
