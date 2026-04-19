# Skill: oversample_cluster

## Purpose

Increase exposure to a domain where failures are concentrated without changing the whole curriculum.

## Use When

- a specific cluster lags badly
- the broader curriculum still looks sound
- the likely issue is uneven data coverage or repetition

## Inputs

- target cluster
- evidence of concentrated failure
- candidate data sources or existing corpus slices

## Steps

1. Identify the underperforming cluster.
2. Select or define a bounded oversampling strategy.
3. Run the oversampled training/eval step.
4. Compare cluster-local and global metrics.

## Success Metrics

- cluster-local failure rate decreases
- retention within the cluster improves
- overall model quality does not regress badly elsewhere

## Stop Conditions

- no meaningful cluster improvement after budget is spent
- oversampling creates noticeable regressions or imbalance
- evidence shifts toward prerequisite/order problems

## Likely Next Interventions if It Fails

- `reorder_curriculum`
- `add_contrastive_pairs`
- `request_more_data`
