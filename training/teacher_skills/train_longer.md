# Skill: train_longer

## Purpose

Use additional training time when the current corpus and ordering seem broadly correct and the model is still improving.

## Use When

- recent training rounds improved MSM metrics
- failure taxonomy does not strongly indicate a structural curriculum problem
- the likely bottleneck is insufficient consolidation rather than bad data shape

## Inputs

- current checkpoint or training target
- prior round metrics
- intervention budget from `ROUND_STATE.json`

## Steps

1. Define the next bounded training increment.
2. Run or simulate the additional training step.
3. Run MSM evaluation on the fixed eval slice.
4. Compare against the previous round.
5. Log whether improvement was meaningful.

## Success Metrics

- pass rate improves
- fail rate decreases
- retention improves
- dominant failure severity decreases

## Stop Conditions

- two consecutive non-improving rounds
- intervention budget exhausted
- another intervention is clearly better supported by the evidence

## What to Log

- training increment
- eval slice
- metric deltas
- whether plateau was reached

## Likely Next Interventions if It Fails

- `teacher_student_drill`
- `oversample_cluster`
- `reorder_curriculum`
