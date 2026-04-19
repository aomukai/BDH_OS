# Skill: add_contrastive_pairs

## Purpose

Add explicit differentiating examples when the student confuses nearby concepts or sibling categories.

## Use When

- the student repeatedly confuses one concept with another
- positive-only statements do not resolve the confusion
- the verifier can frame the contrast without damaging ontology

## Inputs

- confused concept pair or cluster
- failure examples
- verifier policy

## Steps

1. Identify the exact confusion pattern.
2. Draft candidate contrastive pairs.
3. Send them through `verify_teacher_output`.
4. Use only approved contrastive formulations.
5. Run the bounded intervention/eval step.

## Success Metrics

- reduced confusion on the targeted pair/cluster
- preserved higher-level category structure
- no new ontology distortion introduced

## Stop Conditions

- verifier repeatedly rejects the generated contrasts
- confusion does not improve after the defined budget
- a broader data gap appears to be the real issue

## Likely Next Interventions if It Fails

- `simplify_wording`
- `request_more_data`
