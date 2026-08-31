# Ninereeds × Sakana Error Diffusion — Research Scratchpad

**Date:** 2026-07-25
**Status:** Research note and implementation handoff; no changes have been made to the training code yet.
**Primary source:** [Sakana AI paper, arXiv:2606.31700](https://arxiv.org/abs/2606.31700)
**PDF:** [arXiv PDF](https://arxiv.org/pdf/2606.31700)

## Purpose

This note records ideas from Sakana AI's Error Diffusion paper that may be useful for Ninereeds/BDH training. It is intended to be dropped into the Ninereeds repository and read by Codex before inspecting the actual implementation.

The central conclusion is:

> Do not transplant Sakana's architecture wholesale. First use its methodology to determine what Ninereeds' existing Hebbian plasticity is doing, where it acts, and whether it cooperates with or fights the backpropagation objective.

The paper is relevant because it combines local learning, sparse routing of global error, excitation/inhibition, and self-organized balance. The closest connection to Ninereeds is between Sakana's local Error Diffusion update and Ninereeds' existing Hebbian gate.

## Current Ninereeds context and assumptions

These statements describe the project as understood when this note was written. Codex must verify them against the repository before proposing or making changes.

- Ninereeds is a BDH-based small reasoning model and long-term identity/memory system.
- Existing experiments include approximately 25M, 150M, and 604M parameter configurations.
- The existing Hebbian mechanism uses a sparse local gate resembling:

  ```text
  x_sparse * y_sparse
  ```

- `V = x` in the current design.
- The model has recurrent depth/layer applications.
- We have commonly used shared weights across recurrent applications with `per_layer_weights=False`.
- The current curriculum has explicit buckets, concept dependencies, hard edges, soft hints, and staged tiers.
- MRI-style diagnostics measure concept strength and relational structure, but presently do not distinguish weak activation from incorrect or conflicting credit assignment.
- Campaign 16 exposed uneven concept formation. Household, animals, and colors were much stronger than actions, food, nature, and emotions.
- Continual learning, interference, boundary formation, and preservation of existing knowledge remain major concerns.
- Training hardware makes cheap 25M experiments attractive before modifying 150M or 604M runs.

## The transferable idea

Sakana's local update can be summarized conceptually as:

\[
\Delta W \propto
\text{presynaptic activity}
\times
\text{postsynaptic sensitivity}
\times
\text{routed task error}
\]

Ninereeds already appears to contain the first two pieces through its local sparse activity gate. The missing or less explicit part is a structured teaching signal that tells local plasticity which error, concept, or task channel should influence it.

A possible future extension is:

\[
\Delta W_{\mathrm{Hebb}}
\propto
x_{\mathrm{sparse}}
y_{\mathrm{sparse}}
r
\]

where \(r\) is a routed teaching or correction signal.

This should not initially replace backpropagation. The conservative interpretation is that \(r\) modulates the additional Hebbian update that Ninereeds already performs.

Before adding \(r\), however, we should measure the current Hebbian update.

## Highest-priority change: diagnostic instrumentation

The first experiment should change no learning behavior. Add instrumentation that compares the actual Hebbian update with the ordinary backpropagation gradient:

\[
\operatorname{alignment}
=
\cos(\Delta W_{\mathrm{Hebb}}, \Delta W_{\mathrm{BP}})
\]

Record this by:

- recurrent depth/application;
- model layer or parameter group where meaningful;
- curriculum bucket;
- training phase or epoch;
- batch;
- preferably concept or auxiliary-task channel if labels are available.

Interpretation:

- **Positive alignment:** Hebbian plasticity reinforces the loss objective.
- **Near-zero alignment:** it may be organizing representations in a mostly orthogonal direction, or simply adding noise.
- **Negative alignment:** it is actively opposing the backpropagation objective.
- **Highly unstable alignment:** different examples, concepts, or recurrence depths may be issuing conflicting local updates.

This could clarify the Campaign 16 MRI results. Strong household or color representations may receive dense, consistently aligned local updates. Weak actions, food, nature, or emotions may suffer from sparse activation, attenuated plasticity, conflicting credit, or negative alignment. MRI strength alone cannot separate those cases.

### Suggested metrics

At each recurrent application/depth, log:

- mean and RMS absolute BP gradient;
- mean and RMS absolute Hebbian update;
- cosine similarity between Hebbian and BP updates;
- norm ratio:

  \[
  \frac{\lVert\Delta W_{\mathrm{Hebb}}\rVert}
       {\lVert\Delta W_{\mathrm{BP}}\rVert+\epsilon}
  \]

- `x_sparse` density;
- `y_sparse` density;
- combined Hebbian-gate density;
- activation mean, variance, and saturation rate;
- positive/negative update fractions where applicable;
- share of the total accumulated shared-weight update contributed by each recurrent depth;
- per-bucket and per-language summaries;
- old-concept versus new-concept summaries during sequential curricula.

Do not retain full dense gradients or update tensors longer than necessary. Accumulate summary statistics online so the diagnostic does not create excessive memory or storage costs.

### Practical alignment calculation

If the Hebbian update is currently applied directly rather than represented as a gradient tensor, expose or reconstruct the proposed update before it is committed. For each relevant parameter tensor \(W\), accumulate:

```text
dot += sum(hebb_update * bp_gradient)
hebb_sq += sum(hebb_update ** 2)
bp_sq += sum(bp_gradient ** 2)

cosine = dot / (sqrt(hebb_sq) * sqrt(bp_sq) + epsilon)
```

Clarify sign conventions in code. If the optimizer applies `W -= lr * grad` while the Hebbian rule is stored as a direct additive weight delta, compare directions that represent the same actual parameter movement. A sign mistake would invert the interpretation.

Possible reporting levels:

1. per tensor, for debugging;
2. per logical parameter group, for useful analysis;
3. global, only as a coarse summary.

Per-tensor logs can become noisy and large. Prefer stable logical groups once correctness has been validated.

## Depth attenuation and shared-weight recurrence

Sakana reports strong attenuation of its local teaching signal between the output and early hidden layers. Its architectural fix is specific to its model, but the general lesson transfers:

> Measure plasticity strength at every depth before assuming that every recurrent application contributes meaningfully.

Because Ninereeds often shares weights across recurrent applications, a single parameter's final update may contain contributions from multiple depths. A global norm therefore hides whether one depth dominates.

Instrument each depth's contribution before accumulation into shared weights. Determine:

- whether early recurrence steps contribute almost nothing;
- whether late steps dominate;
- whether the sign or alignment changes with depth;
- whether different curriculum buckets use recurrence differently;
- whether greater recurrence depth adds useful credit or mostly interference.

If the imbalance is real, test normalization or scaling of each depth's Hebbian contribution before summing into the shared parameter update. Do not immediately give every depth an arbitrary hand-tuned multiplier.

Candidate normalizations to evaluate:

- equal expected norm per depth;
- exponential moving-average norm normalization;
- clipping only extreme depth contributions;
- learned positive depth scales with a conservative regularizer;
- no normalization as the baseline.

Always record the raw, pre-normalized statistics as well as the effective post-normalization update.

## Routed and centered auxiliary teaching signals

Sakana's batch-centered class error is highly important in its more difficult image task. The transferable principle is to remove persistent base-rate components from a local teaching signal so that local units receive information about how examples differ.

For an auxiliary concept-teaching signal:

\[
\tilde r_{b,c}
=
r_{b,c}
-
\operatorname{mean}_b(r_{b,c})
\]

where \(b\) indexes examples and \(c\) indexes concept or error channels.

This may matter for Ninereeds because repeated curriculum spines and unequal concept frequencies can create a large common update component. Such a component may strengthen already dominant hubs while drowning weaker distinctions.

### Important restriction

Do **not** blindly center the normal language-model loss or the entire BDH objective.

Do **not** assume centering is appropriate inside homogeneous no-shuffle batches. If every example teaches the same concept, centering may erase the lesson itself.

Centering is best tested on a deliberately constructed auxiliary objective whose batches contain:

- positive examples;
- contrasts;
- boundary negatives;
- nearby confounders;
- multiple concepts or buckets where the relative signal is meaningful.

This suggests a future concept/bucket head used only to produce a teaching signal for the Hebbian path. It should be ablated cleanly and must not become an accidental primary classifier that makes the main representation task easier for unrelated reasons.

## Semantic routing instead of modulo routing

Sakana uses deterministic modulo routing in some experiments: hidden unit \(i\) receives output-error channel \(i \bmod C\). This is appealingly cheap, but probably too coarse for language, relational learning, and dependency structure.

Ninereeds has an advantage the paper's generic classifier does not: an explicit curriculum ontology and concept dependency graph.

A future router could use sparse, overlapping semantic assignments:

- animal errors influence overlapping animal-associated populations;
- spatial errors influence spatial populations;
- action and process errors influence their associated populations;
- social, identity, emotion, and agent errors influence corresponding populations;
- dependency parents and bridge concepts deliberately overlap with related children.

Avoid hard non-overlapping partitions. Ninereeds is intended to form distributed, relational representations; forcing one fixed error channel per neuron could fragment those representations.

Reasonable routing variants, from least to most complex:

1. random fixed sparse overlapping routes;
2. ontology-seeded sparse overlapping routes;
3. ontology-seeded routes with limited learned adjustment;
4. learned sparse router with regularization and collapse diagnostics.

Random sparse routing is an essential control. If ontology routing does not outperform it, the ontology is not providing useful credit structure.

## Excitatory/inhibitory streams: interesting, but later

Sakana separates excitatory and inhibitory streams using non-negative matrices. Same-stream connections excite; cross-stream connections inhibit. The paper reports self-organized balance and substantial implicit pruning.

Possible relevance to Ninereeds:

- explicit suppressor structure may help encode boundaries, contradictions, contextual inhibition, and “not this” relations;
- inhibition may restrain destructive update excursions;
- it may offer a useful substrate for clean negative evidence rather than asking ordinary signed weights to represent every role;
- it may improve retention during sequential learning.

However:

- the paper does not establish that E/I separation improves continual learning;
- continual-learning protection is a hypothesis, not a demonstrated result;
- the dual-stream design has a major parameter and compute cost;
- capacity differences could masquerade as architectural improvement;
- changing the architecture now would confound the much simpler credit-assignment questions.

Therefore, defer E/I work until the existing Hebbian mechanism has been measured.

If tested, use a 25M-scale experiment with:

- a width-matched control;
- a parameter-matched control;
- identical curricula and seeds;
- sequential A→B training followed by an A retention evaluation;
- MRI, task performance, interference, sparsity, and update-alignment diagnostics.

## Proposed experiment sequence

### Phase 0 — Repository audit

Before implementation, Codex should locate and document:

- the exact Hebbian update calculation;
- the point at which `x_sparse` and `y_sparse` are produced;
- whether the Hebbian term is a direct weight delta, a gradient modification, or part of the forward computation;
- optimizer and sign conventions;
- recurrent-depth loop and shared-weight accumulation;
- existing logging and metrics systems;
- MRI evaluation entry points;
- curriculum bucket metadata available to the trainer;
- existing configuration and checkpoint compatibility constraints.

The audit should end with a small implementation map naming the relevant files, functions, and tensor shapes.

### Phase 1 — Observational baseline

Add diagnostics only. Do not normalize, route, center, or otherwise change training.

Run at least one representative 25M baseline and answer:

- Is the Hebbian update generally aligned with BP?
- Does alignment vary substantially by depth?
- Which curriculum buckets have weak, noisy, or negative alignment?
- Does Hebbian update magnitude track MRI strength?
- Is the combined sparse gate inactive for weak concepts?
- Are shared-weight updates dominated by one recurrence depth?
- Does behavior change across epochs?

Ideally use three seeds for claims, though a single short smoke run is sufficient to validate instrumentation.

### Phase 2 — Depth contribution experiment

Compare:

- current Hebbian update;
- depth-normalized Hebbian contributions.

Keep all other behavior constant. Select the normalization rule using Phase 1 evidence rather than intuition.

### Phase 3 — Routed/centered auxiliary signal

Introduce an auxiliary concept teaching signal with intentionally mixed batches. Compare:

- no auxiliary routing;
- fixed random sparse routing;
- ontology-seeded sparse routing;
- ontology-seeded routing plus batch centering.

If the matrix is too costly, begin with no routing versus random routing versus ontology routing, then test centering only on the best routed variant.

### Phase 4 — Combined 2×2 core test

At minimum:

| Variant | Depth normalization | Routed/centered concept signal |
|---|---:|---:|
| Baseline | No | No |
| Depth only | Yes | No |
| Routing only | No | Yes |
| Combined | Yes | Yes |

Use three seeds if the initial smoke tests show non-trivial effects.

### Phase 5 — E/I continual-learning test

Only after the earlier phases are understood:

1. train curriculum A;
2. evaluate A;
3. train curriculum B;
4. evaluate B;
5. re-evaluate A;
6. compare retention and representational damage across controls and E/I variants.

## Evaluation criteria

Do not judge these changes only by final training loss.

Track:

- existing shaped/task accuracy;
- MRI strength by concept bucket;
- hub dominance and distribution of concept strength;
- old-concept retention after new learning;
- new-concept acquisition;
- boundary-negative performance;
- cross-language consistency for EN/DE/JP/ZH where applicable;
- Hebbian/BP alignment;
- update norm ratio;
- depth contribution balance;
- gate density and activation saturation;
- variance across seeds;
- wall time, peak memory, and logging overhead.

A promising intervention should improve either learning or retention without merely increasing a few already dominant hubs.

### Suggested stop conditions

Stop or reconsider a variant if:

- diagnostic overhead makes training materially impractical;
- alignment values are corrupted by optimizer/sign mistakes;
- depth normalization causes widespread saturation or unstable update norms;
- routed signals collapse into a few populations;
- ontology routing performs no better than random routing;
- centering erases useful homogeneous curriculum signals;
- apparent gains vanish under parameter-matched controls;
- improvements occur only in training loss while MRI, retention, or boundary behavior degrades.

## Implementation principles

- Keep all new behavior behind configuration flags.
- Default configurations should reproduce existing behavior.
- Separate instrumentation flags from learning-behavior flags.
- Preserve checkpoint compatibility wherever practical.
- Make the cheapest observational change first.
- Prefer online summary statistics over storing update tensors.
- Include deterministic small tests for cosine calculation, sign convention, per-depth accumulation, and centered-signal behavior.
- Ensure diagnostics can be disabled with negligible overhead.
- Record enough configuration metadata that runs can be compared later.
- Avoid combining architecture, optimizer, curriculum, and Hebbian-rule changes in the same first experiment.

## Suggested configuration surface

Names should follow the repository's conventions; these are semantic placeholders:

```yaml
hebbian_diagnostics:
  enabled: false
  log_every_n_steps: 100
  group_by_depth: true
  group_by_bucket: true
  group_by_language: true

hebbian_depth_scaling:
  mode: none  # none | ema_norm | equal_norm | learned
  epsilon: 1.0e-8
  clip_max: null

hebbian_teaching_signal:
  enabled: false
  source: concept_aux
  routing: none  # none | random_sparse | ontology_sparse | learned_sparse
  center_across_batch: false
  route_density: 0.1
  scale: 1.0
```

Do not introduce this exact schema without first checking how Ninereeds presently handles command-line arguments and configuration files.

## Questions the first Codex session should answer

After reading this note and inspecting the repository:

1. What is the exact mathematical update currently called “Hebbian” in Ninereeds?
2. Is it possible to observe its proposed parameter delta independently of BP?
3. What is the correct direction/sign for alignment comparison?
4. Where can recurrence-depth contributions be intercepted before shared-weight accumulation?
5. Is bucket/language metadata available at the point where metrics are recorded?
6. What is the cheapest diagnostic implementation that preserves behavior exactly?
7. Which existing 25M training command is the best reproducible baseline?
8. Which MRI/evaluation command should run after it?
9. How much compute and storage will the proposed logging add?
10. What tests prove that enabling diagnostics alone leaves weights and results unchanged?

## Requested Codex workflow

When this file is first used in the repository:

1. Read this note.
2. Inspect the current repository and relevant recent notes.
3. Check every “current context” assumption against the code.
4. Report discrepancies before designing around them.
5. Produce a concrete implementation plan for **Phase 1 only**.
6. Identify exact files/functions to change and tests to add.
7. Do not implement routed signals, depth normalization, or E/I architecture unless Andi explicitly asks to proceed beyond the diagnostic phase.

## Bottom line

The immediate value of the Sakana paper is not a replacement architecture. It gives Ninereeds a mechanistic investigation:

> Where does local Hebbian plasticity receive credit, how strongly does it act at each recurrent depth, and does it agree with the global learning objective?

Answering that question could make the next MRI far more informative. It may reveal whether weak concept buckets suffer from insufficient activation, attenuated local learning, conflicting updates, or genuinely incorrect credit assignment. Only after that evidence exists should Ninereeds add routed teaching signals, depth compensation, or explicit excitatory/inhibitory structure.
