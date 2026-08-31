# Campaign 36C Checkpoint 02: Patch Algebra and Delayed Credit

**Date:** 2026-08-30
**Status:** Design checkpoint; semantic contracts are settled, numerical estimators remain provisional
**Depends on:** Checkpoint 01 — Cell and Thought Lifecycle
**Scope:** Claim-addressed patches, compatibility and uncertainty reduction, evidence-governed hypothesis support, and typed delayed credit

## 1. Identity-level epistemic rule

The design is governed by Ninereeds' identity as a continuing, fallible mind:

> I know what I have learned. I predict from what I currently know. I notice when those predictions fail, and I may change my mind when new evidence gives me a better model.

Ninereeds does not possess final truth. It maintains the best model its experience currently supports. It must make useful predictions rather than abstaining universally, but it must preserve uncertainty and revise when new discriminating evidence or prediction errors justify revision.

Consequences:

- beliefs retain evidence, scope, assumptions, conditions, and calibration history;
- empirical success does not silently promote a rule into logical or definitional necessity;
- an old prediction may have been reasonable under the evidence then available even if a better model later replaces it;
- new evidence changes addressed claims and dependencies rather than indiscriminately rewriting nearby knowledge;
- historical observations remain real even when their explanation changes;
- unknown unknowns remain compressed as bounded unknown/other mass rather than enumerated hypotheses;
- disagreement alone does not warrant revision; evidence that discriminates among claims does.

## 2. The grading surface: supported, refuted, unresolved

At the level of an addressed question, the minimal result space is:

```text
SUPPORTED    true given the current evidence and scope
REFUTED      false given the current evidence and scope
UNRESOLVED   I do not know
```

The internal names `SUPPORTED`, `REFUTED`, and `UNRESOLVED` are preferable to metaphysical `TRUE` and `FALSE`. They make explicit that the grade is evidence-relative and revisable.

A hypothesis is not a fourth truth value. It is a possible conditional explanation inside an unresolved concern. The conditional rule may itself be supported while the current antecedent remains unknown:

```text
IF condition C holds, claim X follows.
C is unresolved.
Therefore the current status of X is unresolved.
```

An unresolved result is a completed thought, not a processing failure.

## 3. Sparse uncertainty representation

Ninereeds must not materialise a separate world for every possibility. The physical world model remains one sparse context containing resolved facts, compact uncertainty markers, and only a few lazily materialised disputes.

```text
Concern
  claim address
  state: resolved | uncertain | disputed
  retained patch               if resolved
  uncertainty/support sketch   if uncertain
  bounded candidate handles    only if disputed and useful
  missing discriminator        optional
  confirmation route           optional
  other/unknown mass
```

For a cat in a closed box, the sufficient representation is:

```text
known:
  a box exists
  a cat is inside

unresolved:
  the cat's current state
```

`I do not know` compresses the alternatives. Alive and dead do not require separate context branches unless they predict different consequences relevant to the current task.

Materialise explicit alternatives only when they:

- explain an actual residual;
- have evidential or mechanistic grounding;
- make different predictions;
- affect the answer or an action;
- guide a useful observation, lookup, or experiment;
- justify their compute and complexity cost.

There must be no Cartesian expansion across unresolved concerns. Unsupported possibilities remain in `OTHER`. Low-support but historically useful candidates may become dormant rather than active.

## 4. What a patch is

A patch is not a free-floating latent vector addition. It is a base-dependent, conditional latent transaction.

```text
Patch
  patch_id
  base_version
  claim_address
  read_footprint
  write_footprint
  operation_or_delta
  effect_signature
  applicability_conditions
  dependency_ids
  evidence_lineage
  route_provenance
  support_metadata
```

Why this is required:

- a delta calculated from one context may be invalid after another patch changes its assumptions;
- nonlinear cell transformations and collective normalisation make raw vector addition order-sensitive;
- shared ancestry must be applied once;
- delayed credit must distinguish a retained conclusion from the premises and transformations that produced it;
- right answers produced by invalid dependencies must not reinforce the invalid rule.

Terminal patches may remain a compact DAG of conditional edits until reduction. Flattening them early would destroy dependency and provenance information.

## 5. Claim addresses

Two patches can only be classified correctly if the reducer knows what addressed concern each modifies.

```text
ClaimAddress
  subject_or_target_binding
  relation_or_question_binding
  object_or_outcome_binding
  time_and_scope
  conditions_or_world_binding
  expected_merge_mode
```

These are transient latent bindings or compact signatures, not language labels and not a fixed hand-written ontology. Amorphous latent cognition still requires enough structural addressing to prevent a patch about one entity or relation from being mistaken for another.

Relation type is part of the address. At minimum, the system must preserve distinctions corresponding to:

- `is-a` or type membership;
- attribute/property;
- resemblance or shared feature;
- correlation/co-occurrence;
- causation/influence;
- temporal order/state change;
- condition or applicability;
- analogy/metaphor.

The `cats are liquid` joke intentionally promotes one shared property into category identity:

```text
liquids conform to containers
cats sometimes conform to containers
therefore cats are liquids
```

The shared feature and analogy are supported; the literal `is-a` conclusion is not. Partial similarity cannot automatically change relation type.

## 6. Patch relationship algebra

The reducer classifies addressed patches as follows:

| Relationship | Meaning | Reduction |
| --- | --- | --- |
| Sequential | Q was calculated from a context already containing P | Apply P, then Q |
| Equivalent | P and Q have functionally the same addressed effect | Apply one representative; preserve provenance |
| Subsuming | Q includes P's valid effect plus additional compatible effects | Retain Q; credit shared component carefully |
| Reinforcing | Independent evidence supports the same effect | Apply effect once; increase bounded support |
| Complementary | P and Q answer different concerns or compatible aspects | Compose both |
| Conditional | Different effects apply under different conditions, times, or scopes | Retain conditions without forcing conflict |
| Contradictory | Incompatible writes target the same single-valued address under overlapping conditions | Preserve dispute or return unresolved |

The reducer compares candidates relative to their nearest common ancestor, not merely their terminal vectors.

A bounded compatibility procedure is:

1. Resolve obvious sequential dependencies from shared ancestry.
2. Use claim address and read/write footprints to separate non-overlapping concerns.
3. Use effect signatures to bucket equivalent or aligned effects.
4. Test only overlapping, high-support ambiguous candidates counterfactually.
5. Preserve uncertainty when compatibility remains unclear.

Where a functional test is needed, the reducer asks whether applying P invalidates Q, whether Q invalidates P, whether both orders remain useful, and whether the composition reduces or worsens residual. Full replay is reserved for high-impact ambiguity or structural decisions.

## 7. Equivalent output versus reinforcing evidence

Equivalence concerns the resulting effect. Reinforcement concerns evidence independence.

Two branches deriving the same arithmetic change from the same root statement are redundant even if they travelled through different cells. Forking one observation does not create corroboration.

Two branches producing the same effect from genuinely distinct evidence may reinforce it. The effect is still applied once.

Within an equivalent-effect group:

- group candidates by evidence lineage;
- count shared upstream evidence once;
- treat different cells alone as insufficient proof of independence;
- permit distinct external observations to reinforce approximately;
- give unknown independence only a conservative, capped bonus;
- retain every contributor for local learning and structural statistics;
- choose a safe representative patch rather than averaging arbitrary latent deltas.

The representative should favour valid applicability, strong root coverage, residual reduction, historical calibration, and minimal disturbance outside the claimed footprint.

Perfect independence detection is impossible. Provenance and historically different error patterns are bounded proxies.

## 8. Complementarity, causation, and multiple mechanisms

Two true claims often answer different questions. An author may hold a sexist belief, and a character may hold a sexist belief. Both attribute claims can be true without establishing that the author's belief caused the character's.

Multiple causal mechanisms can also coexist:

```text
author's sexism -> treatment or fate of female character
author's justice -> punishment of male character
```

Both may influence the same book without cancelling each other. A broad question such as `which beliefs influenced the book?` expects a set of mechanisms. A question such as `is this claim true under this scope?` may expect one value. The claim address therefore carries an expected merge mode: single value, set, additive contribution, ordered sequence, conditional alternatives, or another learned operator.

Successful co-participation remains correlation. A causal edge requires dependency evidence; it cannot be inferred merely because two properties or cells occurred together.

The central contradiction rule is:

> Only incompatible writes to the same single-valued claim address, under overlapping conditions, are contradictions.

## 9. Empirical expectations are distributions, not static/variable bits

Knowledge about an empirical property needs more structure than `static` or `variable`.

```text
ExpectationBundle
  possibility_or_support
  expected_distribution_or_interval
  epistemic_uncertainty
  conditioning_signature
  volatility_or_change_hazard
  rigidity_or_modal_status
  evidence_scope_and_sampling_provenance
  unknown_or_other_mass
```

Important distinctions include:

- constitutive/type constraint versus empirical regularity;
- species/body-plan default versus current individual state;
- possible value versus probable value;
- population variation versus ignorance about population frequency;
- stable mixture versus temporal regime change;
- representative evidence versus a correlated or selected stream.

Examples:

- `a swan is a bird` is normally a constitutive type constraint; a purported non-bird swan primarily challenges identification or concept usage;
- `a swan normally has two legs` is a biological default with developmental and acquired exceptions;
- `this swan has one leg` is an individual state and does not rewrite the species body plan;
- `swans are commonly white` is an empirical population expectation with possible subspecies, ancestry, and location conditions;
- a six-legged dog and a red-haired human are both possible variations but occupy very different probability regions and generative mechanisms.

An empirical property should normally retain a small unknown tail. Finite success does not justify exact zero probability for every unseen alternative.

## 10. The black-swan stream

Observing 1,234 white swans and then 123 black swans establishes the observed stream and its order. It does not by itself establish global prevalence.

Competing explanations include:

- one stable mixed population;
- a location or sampling change;
- a different subspecies or ancestry group;
- a temporal regime change;
- changed identification or measurement;
- correlated observations.

The ordered run is evidence about hidden conditions or change, not merely a count. A bounded implementation can retain long-term effective counts, a short recent window, conditional prototypes, a change-point score, and source reliability instead of every raw event.

Patch classification follows scope:

- different individual swans with different colours are complementary observations;
- one individual asserted white and black at the same time may be contradictory;
- `swans are usually white` is compatible with a black individual;
- `all swans are white` is refuted by one sufficiently reliable black-swan counterexample;
- different population, time, ancestry, or subspecies conditions yield compatible conditional models.

The first reliable exception should preserve the observation, weaken universal rigidity, expand possible support, and create a provisional exception/condition signal. Repeated structured residuals may later justify functional fission.

## 11. Novelty, evidence, and hypothesis support

Novelty is a trigger, not a vote.

The system distinguishes:

- **input novelty/error:** unexplained incoming residual;
- **unique contribution:** a cell adds an addressed effect not already present;
- **new evidence:** a new, provenance-distinct observation capable of testing claims;
- **hypothesis support:** how well a candidate explains the currently available evidence.

The existence of a competing branch does not make it more probable. Repeating a branch, replaying one observation, or producing many correlated descendants does not create evidence.

When new evidence E arrives, A and C are reweighted only to the extent that E is more expected under one than the other. If both predict E equally, their relative support does not change. If E supports neither, it may create a new hypothesis or remain unexplained.

One hundred independently useful observations can provide new evidence. One hundred cells repeating the same observation cannot. A flock may be strong evidence that a variant exists without being one hundred independent estimates of global prevalence.

Hypothesis support is current evidential support, not literal access to ultimate truth. Empirical weights may approach certainty without reaching it because measurement error, mistaken assumptions, missing conditions, and unknown models retain some mass.

## 12. Swan identification debate and correct unresolved output

For a black bird swimming with white swans:

```text
A:
  IF colour is an exceptionless swan identifier,
  THEN this bird is not a swan.

C:
  IF non-white swans exist
  AND this bird matches them,
  THEN this bird may be a swan.
```

If neither condition is established, the correct result is:

```text
known:
  the bird is black
  it resembles or associates with swans

unresolved:
  whether it is a swan
```

The dispute compresses into an addressed uncertainty marker with the missing discriminator and optional confirmation route. The core need not preserve two complete possible worlds.

The answer renderer depends on the actual question:

- `Is it a swan?` -> `I do not know.`
- `Could it be a black swan?` -> `Possibly.`
- `What might it be?` -> mention the few supported candidates.
- `How can we find out?` -> provide the missing discriminator or lookup route.
- `Make the best guess.` -> provide the leading candidate with qualification.

`Maybe` is a reporting form for unresolved status when one candidate is salient. It is not a fourth truth value.

## 13. External lookup, right conclusions, and wrong dependencies

If Ninereeds looks up the bird and learns both that the individual is another species and that black swans exist, the lookup produces at least two addressed evidence patches:

```text
E1: this individual is species X, not a swan
E2: black swans exist; black colour cannot universally exclude swan identity
```

The dogmatic branch may have reached the correct individual conclusion through an invalid general dependency. The exception branch may have held the correct general possibility but misclassified this individual.

Credit must therefore separate:

- result claim;
- premise/evidence;
- transformation or inference dependency;
- calibration/confidence;
- the decision to seek information.

The dogmatic branch may receive small instance or hypothesis-generation credit while its `black -> not swan` rule receives no causal credit and, after E2, negative calibration. The exception branch may receive general-model credit and negative instance-classification credit.

If the lookup discovers only the lookalike species and no black swans, the available evidence supports the dogmatic branch's concrete prediction. Ninereeds cannot punish it using future omniscience. It records empirical predictive success without promoting the rule into a constitutive truth. A later black swan supplies the prediction error that revises the overgeneralisation.

The governing distinction is:

> Causing Ninereeds to learn something is not the same as being the fact it learned.

And:

> A right answer must not reinforce a dependency that later evidence shows was invalid.

## 14. Unknown unknowns and unfalsifiable additions

The model should not enumerate every logically possible explanation. Unsupported possibilities remain compressed in unknown/other mass.

A concrete hypothesis deserves active state when it addresses a residual, has mechanism or evidence, makes distinguishing predictions, and can guide investigation. Planet-like and compact-object explanations for an orbital residual can both remain active if they make potentially different predictions.

An unrestricted `invisible gods arrange every observation` hypothesis adds no distinguishing prediction and reduces no residual beyond the empirical model. Logical non-disproof does not grant equal epistemic support. Specific versions that make observable predictions can be tested; an unfalsifiable remainder stays outside the active hypothesis set.

Operational model preference is based on calibrated prediction, residual reduction, specificity/testability, intervention or counterfactual power, compression/parsimony, and the cost of ad hoc exceptions.

## 15. Route provenance versus contribution dependency

Delayed credit requires more than a record of packet delivery.

- **Route provenance:** who sent the state to whom.
- **Contribution dependency:** which incoming deltas materially affected later transformations.

These may be represented as one DAG with typed edges.

```text
A emits delta dA
B's read footprint materially consumes dA
B emits dB dependent on dA
dB survives terminal reduction
typed credit can return B -> A
```

Temporal succession is not causation. A recipient should record whether an incoming delta crossed its read/write threshold or materially altered its gates/output. Exact leave-one-out replay is too expensive for every contribution; footprint overlap and local gate effects are bounded approximations. Expensive counterfactual replay is reserved for ambiguous high-impact cases and structural decisions.

For synergy, a downstream delta may depend jointly on several inputs:

```text
{dA, dB} -> dC
```

The dependency group receives joint-contribution credit if dC survives, without treating A and B as independent proofs of one proposition.

For redundancy, equivalent deltas form one effect group. The effect is applied once; contributors may receive local competence credit, while global support increases only for independent evidence.

## 16. Typed grading and delayed credit

One scalar reward cannot represent the cases above. A cell, delta, edge, or dependency may simultaneously receive positive and negative grades in different dimensions.

The current credit vector includes:

```text
content correctness or retained usefulness
dependency/rule validity
residual reduction or regression
calibration and appropriate abstention
routing usefulness
inquiry or information gain
compute/tool cost and harm
evidence independence/correlation
```

Important role cases:

| Event | Credit consequence |
| --- | --- |
| Unique delta causes a retained useful downstream effect | Transform/content credit |
| Unique delta causes harmful or rejected effects | Negative transform/regression credit |
| Delta arrives but downstream ignores it | No transform credit |
| No delta, but routing activates a useful destination | Route credit |
| Equivalent effect has independent evidence | Corroboration/calibration credit without double application |
| Cell appropriately abstains | Boundary/calibration credit, no content credit |
| Useful terminal delta has no downstream cell | Reducer acts as consumer |
| Unresolved concern receives no later evidence | No factual credit; eligibility may expire neutral |
| Conflict triggers a useful lookup | Bounded inquiry credit, charged for tool/compute cost |

An always-uncertain cell cannot dominate: abstention avoids a large error but earns no transformation or residual-reduction credit. A noisy cell cannot profit merely by starting arguments: inquiry credit is granted only when the conflict produced useful information and is net of investigation cost.

## 17. Staged credit flow

Credit arrives in stages rather than as one global verdict.

### Stage 1: immediate local use

The recipient records whether it rejected, relayed, absorbed, transformed, or depended on an incoming delta. This creates typed route and contribution eligibility, not truth credit.

### Stage 2: thought-level reduction

The reducer determines which addressed effects were retained, merged, left unresolved, contradicted, or resolved elsewhere. It returns typed thought-level credit along the retained dependency/provenance DAG.

### Stage 3: later evidence or outcome

External observation, user correction, tool evidence, or later predictive validation may change support and calibration. Persistent content, route, receptor, or structural plasticity is updated only in the corresponding dimension.

A provisional compact credit event is:

```text
CreditEvent
  thought_id
  target_kind: delta | dependency | edge | receptor | structural_candidate
  target_id
  claim_address
  role: transform | route | calibration | inquiry | structural
  grade: positive | negative | neutral | pending
  magnitude_or_strength
  grade_confidence
  evidence_lineage
  dependency_group
  reason_code
```

The exact numeric update functions remain an implementation/experiment question. Suitable bounded proper scoring rules can reward sharp calibrated predictions, penalise unjustified certainty, and give broad uncertainty only modest reward. Shared evidence must be deduplicated before scoring.

## 18. Plasticity gates produced by grading

Typed credit independently controls:

- **transform plasticity:** what the cell predicts or knows;
- **receptor plasticity:** what the cell considers its territory;
- **route plasticity:** where similar states should be sent;
- **calibration:** how much authority claimed support deserves;
- **structural eligibility:** whether repeated evidence justifies growth, fission, fusion, dormancy, or metabolism.

Examples:

- resolved elsewhere with low ownership -> receptor/route update, no content rewrite;
- retained useful delta -> transform and route credit;
- repeated high-ownership residual -> possible fission eligibility;
- unresolved everywhere -> possible sponsored growth;
- repeated functional equivalence -> fusion/consolidation evidence;
- repeated harmful obsolete assumption -> dormancy/metabolism evidence.

Structural changes must not be authorised by one ambiguous thought or by mere co-activation.

## 19. Compute safeguards specific to patch reduction and grading

- uncertainty is stored as one marker unless explicit alternatives have predictive or decision value;
- candidate sets are bounded and local to an addressed concern;
- no cross-product of unrelated concerns is materialised;
- shared context and ancestry remain copy-on-write;
- effect signatures bucket candidates before comparison;
- evidence lineage prevents copied branches from multiplying support;
- most dependency attribution uses recorded footprints and gate effects;
- counterfactual replay is limited to ambiguous high-impact cases;
- low-support hypotheses become dormant or merge into `OTHER`;
- unresolved eligibility expires without content learning if no outcome arrives;
- inquiry credit includes compute/tool cost so conflict is not rewarded for its own sake.

## 20. Settled principles from this checkpoint

- The minimal answer grades are supported, refuted, and unresolved.
- `I do not know` is a valid completed result and a compute-compression mechanism.
- `Maybe` is a task-dependent rendering of unresolved status, not another truth value.
- Hypotheses are conditional candidates under uncertainty, not simultaneous asserted truths.
- Only relevant, predictive hypotheses need explicit state.
- Patches are base-dependent addressed transactions with dependencies and evidence lineage.
- Similarity cannot promote resemblance into identity, correlation into causation, or one shared property into category membership.
- Equivalent effects apply once; independent evidence may reinforce support.
- Contradiction requires the same address, overlapping conditions, and incompatible effects.
- Empirical properties are conditional distributions with unknown mass, not static/variable bits.
- Novelty triggers investigation; only discriminating evidence reweights hypotheses.
- Repeated computation is not repeated evidence.
- Current evidence, not future omniscience, determines credit.
- Correct conclusions do not automatically validate their dependencies.
- Participation, causal contribution, factual validity, calibration, routing, and inquiry are distinct grades.
- Persistent plasticity follows typed credit, not one scalar reward.

## 21. Remaining implementation questions

The semantic contract is settled, but these numerical and implementation choices remain experimental:

- compact latent claim-address and binding representation;
- read/write/effect sketch design;
- calibrated comparison of scores from different cells;
- evidence-lineage grouping and correlation discount;
- representative-patch selection within equivalent groups;
- proper scoring rule and update magnitudes;
- grade-confidence decay and eligibility lifetime;
- bounded counterfactual replay policy;
- sparse storage of active, dormant, and `OTHER` hypotheses;
- how the BDH active frontier exposes dependency strengths;
- deterministic reduction under different execution orders.

These belong in the later BDH implementation and validation checkpoint rather than being guessed into the semantic design.

## 22. Next checkpoint

Checkpoint 03 should cover the structural lifecycle:

1. growth and sponsor selection;
2. functional fission after persistent high-ownership prediction errors;
3. fusion versus consolidation/packing for repeated functional equivalence;
4. dormancy and metabolism;
5. bridge and connectivity preservation;
6. rigidity, reversibility, and structural transaction safety.
