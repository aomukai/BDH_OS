# Skill: reorder_curriculum

## Purpose

Adjust sequencing when failures suggest the student is being asked to learn concepts before prerequisites are stable.

## Use When

- errors are strongly dependency-shaped
- simpler anchors are missing or unstable
- rescue works only after reducing complexity

## Inputs

- target cluster
- prerequisite evidence
- current ordering references

## Steps

1. Identify the likely prerequisite gap.
2. Propose a minimal reorder.
3. Justify the reorder with explicit dependency reasoning.
4. Run the bounded test/training step.
5. Compare results with the previous ordering.

## Success Metrics

- fewer prerequisite-shaped failures
- less need for simplification rescue
- improved stability on downstream concepts

## Stop Conditions

- reorder does not reduce dependency-shaped failures
- evidence now points to contrast or data insufficiency instead

## Likely Next Interventions if It Fails

- `add_contrastive_pairs`
- `simplify_wording`
- `request_more_data`
