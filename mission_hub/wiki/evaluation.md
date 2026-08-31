<!-- ninereeds-wiki: {"schema_version":"ninereeds_research_wiki_page_v1","page_id":"wiki-evaluation","page_type":"evaluation_methodology","status":"active","updated":"2026-08-29","source_ids":["src-bdh-cq-paper","src-current-evaluation-methodology-v1","src-campaign35-session20-reconstruction-20260819","src-campaign35-post-reconstruction-planning-20260819"]} -->
# Evaluation methodology

## Purpose and evidence boundary

Ninereeds evaluation should locate controlled capability boundaries, not merely
produce an aggregate score. The source method comes from BDH-CQ's ARC-like behavioral
analysis: concept profiles identify pressure points, deterministic ladders increase
one demand at a time, matched contexts distinguish support from execution limits, and
strict task scoring tests whether an inferred rule is applied consistently.

This is an adaptation, not a transferred finding. BDH-CQ's reported ARC boundaries
belong to that evaluated system, data, and task family. Ninereeds must establish its
own boundaries with frozen checkpoints, fresh evaluation material, explicit controls,
and campaign artifacts. The executable planning catalogue is
`mission_hub/research/evaluation-methodology.json`; pipeline integration remains
future work.

## Campaign boundary

This methodology begins with Campaign 36 and successor campaigns. It does not amend
Campaign 35, change its frozen questions, or retroactively judge Campaign 35 by
requirements that were not in its contract. Campaign 35 remains useful on its own
terms as the text/image/combined/merge/healing experiment. Its observations may
motivate later boundary probes, but those probes receive new Campaign 36+ contracts
and fresh evaluation artifacts.

## Evaluation stack

### 1. Coverage profile

Begin with results grouped by a preregistered concept, operation, lesson, modality, or
other meaningful family. Report aggregate and family results with sample counts and
uncertainty. The profile finds candidate strengths and pressure points; it does not
establish that one operation is intrinsically easier than another.

### 2. Strict consistency

Report both individual-item success and strict family success. A family passes only
when every declared held-out item governed by the same rule passes. Preserve the
distribution of zero, partial, and complete success. Several isolated correct answers
may show partial recovery without showing stable rule acquisition.

For a Ninereeds lesson, this may mean reporting each answer alongside a strict block
result across affirmative, negative, W-question, OR-question, mixed, and held-out
forms. The block definition must be frozen before answers are observed.

### 3. Controlled generalization ladder

Freeze the checkpoint before generating fresh tasks. Hold the target rule and relevant
surface properties fixed while increasing one declared demand. Useful axes include
demonstration count, simultaneous bindings, relation or dependency depth, sequence
length, question-form novelty, scene novelty, modality, composition count, delay, and
recurrent effort.

Include levels inside the demonstrated range, near its boundary, and beyond it where
meaningful. Use deterministic generators and exact oracles when possible. If a cliff
appears, replicate more densely around the transition instead of averaging it away.
Every curve states the generator family and held constants; it is not silently
generalized to unrelated operations.

### 4. Matched-support comparison

When a difficult item fails, rerun the byte-identical query under matched contexts:

- `short`: demonstrations stop below the query's complexity;
- `supported`: at least one demonstration reaches the query's complexity.

Recovery localizes a contribution from demonstration coverage or extrapolation. If
failure remains despite matched support, an execution, composition, output-construction,
or other limitation remains plausible. Neither outcome uniquely reveals the latent
mechanism.

In lesson research, the analogous intervention can hold the exact question and image
fixed while changing only whether controlled practice included the tested depth,
form, or composition.

### 5. Atomic versus composed capability

Measure every atomic prerequisite separately before evaluating a composition. Compare
the operation alone with the same operation composed with another already established
operation. Do not call a failure “compositional” when one component was never acquired.
When representation dependence is plausible, repeat across different object layouts,
wordings, scenes, or visual styles.

### 6. Cue and contamination controls

Apparent learning may use request-side shortcuts. Where applicable:

- replace semantic lesson, task, or concept identifiers with opaque identities;
- mix family and batch order;
- break predictable answer and question cadence;
- hold task content fixed while changing only the suspected cue;
- check training overlap, prompt-example contamination, and near duplicates;
- compare output stability as well as aggregate stability.

An unchanged aggregate does not imply byte-identical behavior. A cue intervention can
rule out its combined tested confound without making an old benchmark fresh or ruling
out every other contamination route.

### 7. Effort, attempts, and replication

Report pass@1 and any multi-attempt metric separately. When the same items are tested
under different recurrent-effort, context, seed, or checkpoint conditions, preserve
paired outcomes rather than only comparing totals. Record repeated-request stability,
runtime, cost, and latency independently; greater effort is an experimental variable,
not a free accuracy correction.

### 8. Failure structure

Keep the shape of wrong answers. Separate malformed output from semantic error and
record observable global-construction, localized-relation, selection, reversal,
incomplete-coverage, and consistency failures. For language lessons, preserve whether
the answer used the correct referent, polarity, relation direction, question form,
and response structure.

Output morphology can distinguish useful failure families, but it cannot prove which
latent rule or reasoning path produced the output.

### 9. Teaching efficiency and adaptive trajectories

When two configurations receive the same immutable lesson contract, their realized
teaching paths may differ. Preserve paired per-item trajectories rather than forcing
identical exposure counts. Compare eventual acquisition together with exposures,
presentation replays, intervention types, runtime, compute, leech creation, delayed
retention, and reacquisition cost.

One configuration reaching the same behavioral boundary with materially less teaching
is a substantive result even when final accuracy is equal. Conversely, unequal paths
make a simple final-score comparison incomplete; report both the path and destination.

The ordinary lesson stream is continuous behavioral evidence. The candidate schedule
adds repetition lessons after provisional eight-lesson blocks and deeper controlled-
boundary/MRI snapshots at provisional forty-lesson boundaries. These intervals are
design parameters to freeze, not findings.

### 10. Developmental and incidental-exposure controls

Compare acquisition efficiency across preregistered curriculum-age bands using Points
matched as closely as practical for novelty and difficulty. Do not call later learning
faster merely because later lessons are easier or receive richer support.

Retain unscored Topic exposure and relation metadata for controlled comparisons.
Positive, null, and harmful effects use the same standard. Co-occurrence-sensitive
behavior or MRI proximity is not sufficient evidence of a world model.

### 11. Continuation phenotype and basin stability

A checkpoint evaluation is incomplete when the intended use includes later teaching,
merging, healing, or grafting. Preserve the candidate and run an identical short
continuation challenge across plausible checkpoints. Report whether apparently
similar starting states retain the same concepts, move through similar optimizer and
gate trajectories, preserve comparable representations, and arrive at similar
behavioral endpoints.

Near-identical loss is not sufficient evidence of equivalent learning response.
Campaign 35 produced loss correlations above 0.9987 while optimizer-movement
correlations were only 0.29–0.53 and the endpoint behavioral profiles diverged. The
challenge must therefore retain parameter-movement and representation evidence rather
than using loss as its proxy.

The result is a profile, not a rank. Stability, plasticity, interference resistance,
reacquisition cost, and readiness for a later graft may conflict. Replicate across
seeds or reconstructed lineages before treating one observed continuation as a basin
property.

## Campaign construction protocol

Before authorization, an evaluation-bearing campaign preregisters:

1. target capability and exact success unit;
2. trained or demonstrated support range;
3. held-out ladder levels and the one varied factor;
4. relevant held constants and matched controls;
5. checkpoint freeze, generator, item-manifest, and oracle identities;
6. sample counts, seeds, attempts, effort settings, and cliff-replication rule;
7. item, strict-consistency, boundary, failure, retention, and cost metrics;
8. overlap, near-duplicate, identifier, ordering, and cadence controls;
9. invalidation and stopping conditions;
10. exact artifact roles needed for later Sol judgment;
11. when the checkpoint will receive more training, the frozen continuation challenge,
    preservation boundary, replication policy, and stability/plasticity measures.

Freshness is relative to the frozen checkpoint and selection process. Post-freeze
generation reduces direct reuse risk, but generated tasks can still contain authoring
bias, invalid examples, or narrow templates. Deterministic oracles, validation,
deduplication, and multiple construction families remain necessary.

## Interpretation discipline

- Aggregate performance describes the tested distribution, not the boundary.
- A family profile proposes the next controlled probe; it does not isolate a cause.
- A ladder localizes a boundary only within its task family and held constants.
- Matched-support recovery shows that support matters; it does not prove unlimited
  execution capacity.
- Atomic failure blocks a composition-only interpretation.
- Partial family success is not consistent rule acquisition.
- Generated-task performance includes generator and authoring effects.
- Correct or incorrect final output does not reveal latent reasoning uniquely.

These restrictions are deliberate. The method should help Sol ask a narrower next
question rather than turn every result into a persuasive story.
