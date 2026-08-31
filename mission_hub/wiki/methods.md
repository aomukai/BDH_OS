<!-- ninereeds-wiki: {"schema_version":"ninereeds_research_wiki_page_v1","page_id":"wiki-methods","page_type":"method_catalogue","status":"active","updated":"2026-08-19","source_ids":["src-training-modes-v1","src-current-intervention-catalogue-v1","src-historical-intervention-registry-20260806","src-historical-decision-policy-20260806","src-historical-training-harness-design-20260515","src-bdh-cq-paper","src-current-evaluation-methodology-v1","src-campaign35-session20-reconstruction-20260819","src-campaign35-post-reconstruction-planning-20260819"]} -->
# Methods

The detailed lesson grammar, scaffolding ladder, and script/teacher control boundary
live in the maintained [teaching methodology](teaching.md). This page catalogues the
broader interventions that select or modify such lessons.

The maintained [evaluation methodology](evaluation.md) defines the BDH-CQ-derived
protocol for concept profiles, strict consistency, controlled complexity ladders,
matched-support comparisons, atomic-versus-composed tests, contamination controls,
and failure-shape analysis. Aggregate score is an outer profile, not a substitute for
mapping where and why a behavior stops transferring. This protocol applies from
Campaign 36 onward and does not amend Campaign 35's frozen experiment.

## Intervention doctrine

An intervention is a bounded change selected to answer a stated question or repair a
diagnosed failure. It must declare its trigger, exact change, success and failure
criteria, budget, stop conditions, follow-up choices, and retained-capability checks.
Change one major variable at a time when causal interpretation matters. Exhaustion
means the declared budget failed and no obvious safe variant remains; it does not mean
that a checklist grew tired of the option.

This doctrine is retained from the historical intervention registry and decision
policy. Their old orchestrator, verifier, timing, and filesystem mechanics are not
current authority.

## Current intervention families

The names below are research abstractions. A campaign must still bind them to an exact
training, evaluation, lineage, and artifact contract.

### Increase exposure depth

Historical name: `train_longer`.

Use when performance is still improving and the evidence does not indicate a material,
sequencing, or interference defect. Under the current teaching model, this means more
repetitions of the already certified lesson material, followed by retention and transfer
checks. The repetition schedule must be explicit and may later vary ordering, but it does
not add new teaching examples or new concepts. Plateau when the preregistered repetition
or exposure budget is spent without meaningful improvement.

### Increase curriculum breadth

Historical relatives: `request_more_data`, corpus expansion, and adding concepts or
facts.

Use when evaluation identifies a concrete coverage gap. Add a bounded set of concepts,
facts, relations, or genuinely new examples with their prerequisites and complete
instructional cycles. For an established relation such as `X under Y`, this can mean new
valid subject/object scenes; it is distinct from repeating the existing scenes. Existing
registered material is searched and adapted first; acquisition or Flux generation is
prerequisite work for unresolved gaps. “More data” without a named gap, coverage target,
and acceptance test is not an intervention.

### Focused rehearsal

Historical names: `teacher_student_drill` and `oversample_cluster`.

Use when failures are localized or knowledge appears immediately available but
unstable. Modern rehearsal should vary question form, polarity, examples, and
production demand rather than merely duplicate positive answer pairs. Check delayed
retention, unseen examples, and neighboring capabilities so short-lived activation is
not mistaken for learning.

### Change curriculum order

Historical name: `reorder_curriculum`.

Use when failures are dependency-shaped. Stabilize prerequisites before derived
concepts, then compare the reordered lineage with a matched control where feasible.
Reordering changes the training trajectory and therefore requires an immutable ordered
session plan; it is not a harmless data-loader setting.

### Add distinctions and boundaries

Historical names: `add_contrastive_pairs`, negative-example balancing, and
cluster-splitting.

Use when sibling concepts, inverse relations, roles, or category boundaries are
confused. A present-day cycle may include positive examples, explicit negatives,
W-questions, alternatives, corrections, and freer production. Evaluate whether the
distinction transfers beyond the exact surface forms used in practice.

### Adjust instructional form

Historical name: `simplify_wording`.

Use when the content is appropriate but its linguistic or visual presentation exceeds
the current learner boundary. Simplification must preserve the target proposition and
receive a later generalization check; otherwise it may only teach a narrower prompt.

### Branch and specialize

Historical names: branch campaign, specialist training, challenger, and explorer.

Use separate checkpoint lineages to test competing curricula, isolate a capability, or
develop specialists without immediately altering the main lineage. Preserve the common
ancestor, exact data, ordering, optimizer regime, exposure budget, and evaluations.
Specialist success alone does not authorize integration.

### Merge and heal

Current training-mode policy retains merge as a distinct research purpose. The
historical harness proposed specialist merging, optional pre-merge alignment,
architecture-specific BDH structural merging, and bounded `postmerge_repair` through
joint rehearsal, calibration, or corrective adaptation.

The durable method is:

1. train or select explicit specialist lineages;
2. evaluate each specialist and its retained capabilities;
3. create a sandbox merge using a commissioned architecture-specific recipe;
4. measure composition, interference, and regression against sources and mainline;
5. if the merge is promising but damaged, run one bounded healing intervention on
   combined material;
6. reevaluate retention, transfer, and source capabilities before any promotion;
7. preserve every behaviorally promising healed checkpoint before further training;
8. apply one frozen short continuation challenge to compare retention, behavior,
   representation change, gate response, optimizer movement, relative update
   magnitude, and recovery after controlled interference;
9. treat continuation response as part of checkpoint qualification and replicate
   seeds or reconstructions before inferring a stable healing basin.

The historical recipe catalogue—averaging, task arithmetic, TIES/DARE, Git Re-Basin,
and neuron-axis BDH composition—is a proposal inventory, not evidence that any recipe
is safe for the present Ninereeds architecture. Current policy requires a concrete
tensor procedure and compatibility checks before execution.

Campaign 35 motivates but does not fully validate steps 7–9. Its reconstructed
session 20 matched the original's coarse behavior and macro geometry while responding
differently to the same next five sessions. Snapshot behavior, aggregate geometry,
microstate organization, stability, and plasticity must therefore remain separate
reported axes. A single weighted “best checkpoint” score would hide the distinction.

### Evaluate without training

Historical examples include retention probes, layer gates, language isolation,
localization audits, and cross-layer probes. These interventions change evidence, not
weights. They are often the correct next action when the failure mechanism is unclear.

Boundary evaluation freezes the checkpoint and then constructs fresh, controlled
tasks. One factor changes at a time; deterministic generators and oracles are preferred;
item accuracy and strict family consistency are both retained. When failure could be
either insufficient demonstrated support or execution difficulty, use the same query
under short and matched-complexity contexts. When composition is tested, establish
each atomic prerequisite first.

### Qualify continuation phenotype

Use when several checkpoints look similarly capable now but may differ in stability
or readiness for further grafts. Freeze and preserve each candidate, then apply an
identical bounded experience whose purpose is diagnostic rather than promotion. The
challenge may contain controlled rehearsal, interference, one small novel addition,
or a fixed sequence combining them, but its bytes, order, optimizer policy, and stop
point must be identical across candidates.

Compare both destination and path:

- current and post-challenge behavior, strict consistency, and pathological output;
- delayed retention and recovery after interference;
- macro representation geometry and neuron-level diagnostic retention;
- gate, gradient, optimizer-movement, and update-to-parameter telemetry;
- fresh transfer and reacquisition cost;
- variance across seeds or repeated reconstructions.

This does not turn one probe into a universal fitness test. A stable checkpoint may be
too rigid for later learning; a plastic checkpoint may forget too easily. Sol must
state which stability/plasticity profile serves the proposed next intervention.

## Intervention selection questions

Before choosing a training action, ask:

1. Is the target absent, weak, confused, unstable, badly sequenced, or damaged by
   another intervention?
2. Did the evaluation distinguish immediate recall, delayed retention, surface-form
   transfer, conceptual transfer, and retained capabilities?
3. Can existing material answer the need, or is prerequisite work required?
4. What is the smallest intervention that discriminates the leading explanations?
5. What observation stops the intervention, falsifies its rationale, or selects the
   next family?
6. Does the action require a new lineage, merge contract, or healing phase?

## Evidence boundary

The taxonomy is a synthesis of historical designs and current training-mode policy.
It is not evidence that every intervention works. Campaign-specific effects belong in
the findings catalogue only after their artifacts are ingested and their applicability
boundaries are stated.
