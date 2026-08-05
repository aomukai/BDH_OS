# Play: word-training research regime

Play is a research regime for the language-only Cortex continuation. It reuses the
established foundational word-curriculum and training machinery. Image training is
out of scope.

## Objective

The objective is information gain about the Hebbian model, not a passing score.
Scores, losses, probe outputs, activation measurements, and checkpoint comparisons
are instruments. A high score is one observation among many. It does not end the
campaign while untried branch budget remains.

Look for regularities, quirks, delayed recovery, transient collapse, reversals,
prompt sensitivity, representation drift, response-form changes, contradictions,
absurdities, and other surprises. Preserve negative and ambiguous results.

## Campaign and branch semantics

- One campaign is one research question explored through several training branches.
- Every branch starts from the same preserved language-only baseline.
- Within a branch, every ordinary candidate becomes the next parent even if its
  behavioral score temporarily regresses. Evaluation is trajectory telemetry, not
  a one-block admission veto.
- A branch ends at its configured optimizer-step horizon, at its aspirational score
  milestone, or at a deterministic structural failure.
- Only structural invalidity ends a branch early: an invalid or corrupt checkpoint,
  non-finite tensors or loss, dead or saturated core layers, or execution failure.
- Reaching the score milestone documents that branch and starts another contrasting
  branch. It does not declare the campaign solved.
- The campaign ends when its branch research budget is exhausted (or an operator
  stops it), not when the first appealing checkpoint appears.

## Experimental discipline

Before each branch, state a falsifiable hypothesis and a coherent method or method
mix in the executor task title and instructions. Use the controller-provided branch
ID in session, job, artifact, and checkpoint identities. Later branches should be
deliberate contrasts or focused follow-ups informed by earlier observations.

Keep experimental entropy high. Search across meaningfully separated choices in
ordering, dependency staging, contrast density, identity-reinforcement cadence,
replay proportion, optimizer dynamics, curriculum interleaving, and deliberately
odd but structurally safe combinations. Use some clean single-variable contrasts
for attribution and some chaotic mixed-method branches for discovery. Do not spend
the branch budget making only timid adjustments around the latest score. Record all
settings and seeds so surprising behavior can be reproduced.

Experimental entropy is scientific variation, not workflow churn. Retrying a failed
schema, changing serialization, switching between a direct script and a chunked
curriculum, or repairing an identifier preserves the experiment; it does not create a
new experimental treatment. Conversely, a renamed copy of an earlier branch is not a
new branch strategy.

At each healthy strategic boundary, make the next experiment legible by recording:

- the active branch hypothesis;
- the exact variable or reproducible recipe being tested;
- how it differs scientifically from completed branches and prior blocks;
- the observation that would support, contradict, or complicate the hypothesis.

Keep a branch coherent enough to interpret its trajectory. Mutate its method only when
the latest evidence motivates a named follow-up. Make branch-to-branch recipes
substantially different, and never carry another branch's number or title into the
active lineage.

Train complete prepared 500-example word blocks with the established bootstrap
mechanics. Do not replace them with tiny probes, isolated concepts, or image work.
Keep the exact checkpoint lineage auditable.

After every block, record at least:

- behavioral overall, target, protected, and cross-prompt measurements;
- held-out and training-loss trajectory without treating loss as proof of learning;
- activation health, response diversity, representation separation, and drift;
- qualitative output oddities and counterexamples;
- whether a valley persisted, deepened, reversed, or recovered;
- the next question suggested by the evidence.

The final synthesis must compare every branch, including losing branches. Report the
best-scoring checkpoint, but prioritize robust patterns, informative anomalies, and
new hypotheses over declaring a winner.

## Experimental-evolution interpretation

Treat each branch as a lineage, each recipe change as a mutation, mixed recipes as
recombination, and each evaluation as a phenotype observation. The checkpoint and
report archive is the fossil record. Selection pressure is primarily “did this teach
us something?” rather than “did this score higher?” A strange low-fitness lineage
may be more valuable than a modest winner if it exposes a mechanism, phase change,
dependency, or previously invisible capability.
