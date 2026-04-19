# Skill: teacher_student_drill

## Purpose

Run corrective rehearsal in MSM style when concepts seem nearly learnable but unstable.
This sits between pure evaluation and corpus modification.

## Use When

- corrections help immediately but do not stick
- the student appears close to the right answer
- failures look like instability or retrieval weakness rather than deep prerequisite absence

## Inputs

- target concept cluster
- MSM prompts/items
- drill budget
- verifier policy

## Steps

1. Select a bounded set of items from one cluster.
2. Ask the student.
3. Grade the response.
4. Provide an MSM-style correction.
5. Retest immediately.
6. Retest again after short delay or across nearby items.
7. Log what stuck and what did not.

## Success Metrics

- improved delayed retention
- lower rescue depth needed
- improved nearby-item generalization
- fewer repeat failures of the same type

## Stop Conditions

- two consecutive drill runs without meaningful gain
- only exact prompt parroting improves
- verifier rejects the corrective formulation repeatedly
- evidence suggests ordering/data changes are needed instead

## What to Log

- items used
- immediate correction success
- delayed retention result
- generalization result
- dominant remaining failure class

## Likely Next Interventions if It Fails

- `reorder_curriculum`
- `add_contrastive_pairs`
- `simplify_wording`
