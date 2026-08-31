# Campaign 36B selective follow-through contract

**Date:** 2026-08-29
**Status:** Frozen before completion of the unfiltered baseline

## Sequence

1. Allow live run `campaign36b-20260829T203221-11dfa19b` to finish unchanged.
2. Treat it as the unfiltered allocation-rate baseline.
3. Causally audit its terminal anatomy without training it further.
4. Replay the identical 30,220-exposure bootstrap from the identical embryo
   under the selective policy below.
5. Use the resulting evidence, rather than the unfiltered baseline alone, to
   choose the growth policy carried into v8.

No step modifies `training_data/v8_curriculum/`.

## Baseline audit

The terminal baseline checkpoint is evaluated on two deterministic panels:

- 256 audit exposures selected by the lowest SHA-256 rank over the frozen
  bootstrap event identity;
- 64 retention anchors, one hash-selected exposure for each of the first 64
  concepts.

Every birth-session cohort group is ablated as a block. A deterministic sample
of 128 individual newborn cohorts is additionally audited on 32 audit exposures
and eight anchors. The audit reports enabled-versus-ablated target NLL, exact
predictions, helpful fraction, redundancy, and birth-session provenance. It
does not alter the checkpoint.

Because the baseline admitted cohorts without a fitness test and continued to
train them afterward, individual terminal ablations are a counterfactual
estimate, not a reconstruction of admission-time utility.

## Selective birth gate

Birth decisions occur once per ten-exposure concept block rather than once per
exposure. One four-cell cohort is born only when all conditions hold:

1. at least eight of ten exposures fail exact target-token prediction;
2. median target residual is at least 0.25;
3. mean residual improves by less than 10% from exposures 1–5 to 6–10;
4. every admitted cell executed and mean active-admitted fraction is at least
   0.45;
5. the 8,192-cell bootstrap ceiling and storage guards remain satisfied.

The plateau is always calculated backward over all ten completed exposures;
birth occurs only after the block's final update. After any birth, another
birth is ineligible until the newest cohort has accumulated at least 32
subsequent causal-credit observations. Since birth decisions occur only at
ten-exposure boundaries, the effective integration interval is four complete
blocks, or 40 exposures. This prevents a plateau reset at the next concept from
creating redundant cohorts before the preceding newborn has had a meaningful
trial.

This makes capacity saturation a learning-plateau observation rather than a
permanently true dense-execution fact.

## Selective admission gate

Each newborn cohort remains provisional for at least 128 subsequent training
exposures and must collect at least 32 causal-credit observations.

The cheap online credit is the signed first-order effect of the cohort's
residual contribution on target loss. At an audit boundary, candidates with
enough observations receive deterministic enabled-versus-ablated replay.

A cohort is admitted only when all conditions hold:

1. at least 60% of online credit observations are helpful;
2. median replay utility, defined as `ablated NLL - enabled NLL`, is at least
   0.02 nats;
3. enabling the cohort worsens retention-anchor NLL by no more than 0.01 nats;
4. all evidence is finite and identity-bound to the frozen event stream.

An under-age or under-observed cohort rolls over as provisional. A mature
cohort that fails one audit remains provisional for one more audit period. A
second failed audit makes it dormant, never deleted. Dormant cohorts remain in
the checkpoint and may be reactivated by a later, separately registered
causal audit.

## Comparison outputs

The unfiltered and selective replays will be compared on acquisition,
retention, wall-clock cost, total births, admitted fraction, dormant fraction,
active cell-time, checkpoint size, and terminal causal utility. The selective
run is not allowed to revise thresholds after observing its intermediate
results.
