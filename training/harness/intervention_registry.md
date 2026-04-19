# Intervention Registry

This file lists the currently supported intervention methods for the training harness.
Each intervention must also have a matching markdown skill in `training/teacher_skills/`.

## Intervention Principles

- Interventions are **explicit**, not hidden behavior.
- Each intervention has:
  - trigger conditions
  - execution steps
  - success metrics
  - stop conditions
  - likely follow-up interventions
- Interventions are considered **exhausted** only after their defined budget is spent without meaningful improvement.

## Registered Interventions

### 1. `train_longer`
Use when the current dataset/order looks reasonable and additional training still appears to improve MSM metrics.

### 2. `teacher_student_drill`
Use when concepts appear nearly learnable but unstable, and corrective rehearsal may increase retention.

### 3. `oversample_cluster`
Use when failures are concentrated in a domain or concept family rather than globally distributed.

### 4. `reorder_curriculum`
Use when failures appear prerequisite-shaped and current ordering likely introduces concepts too early.

### 5. `add_contrastive_pairs`
Use when the student confuses sibling concepts, roles, or neighboring categories and needs explicit differentiation.

### 6. `simplify_wording`
Use when the target content is conceptually valid but phrased above the model's current level.

### 7. `verify_teacher_output`
Mandatory safety/verifier skill used before student-facing corrections or generated training data are accepted.

### 8. `request_more_data`
Emergency-exit intervention. Only valid after all applicable interventions have been exhausted or ruled out.

## Not Yet Registered

These may be added later if the harness proves they are necessary:

- paraphrase-stability intervention
- spaced-retention scheduling intervention
- cluster-splitting intervention
- negative-example balancing intervention
- data-pruning / decontamination intervention

## Exhaustion Definition

An intervention is exhausted for a target cluster only if:

1. it was attempted up to its skill-defined budget
2. it failed to produce meaningful improvement
3. the verifier did not propose an obvious safe variant still worth trying
4. the orchestrator agrees it is no longer the best next move

## Emergency Exit Rule

`request_more_data` is allowed only when:

- the selected cluster has no promising remaining in-harness intervention
- the likely bottleneck is missing or insufficient data
- the requested data can be described concretely enough to create and review new corpus pieces
