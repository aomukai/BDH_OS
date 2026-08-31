# Campaign 36C Checkpoint 01: Cell and Thought Lifecycle

**Date:** 2026-08-30
**Status:** Design checkpoint, not a final implementation contract
**Scope:** Cell anatomy, local routing, travelling context, terminal hypotheses, delayed plasticity, and bounded inference compute

## 1. Goal and governing constraints

Campaign 36C is intended to be a decentralised, amorphous latent-state model that can:

- grow when existing cells cannot cover persistent residuals;
- metabolise cells that have become obsolete;
- merge cells or structures that repeatedly agree under appropriate conditions;
- fission when a high-ownership prediction error shows that an old assumption no longer covers reality;
- retain multiple hypotheses when the available evidence does not justify a single answer;
- remain computationally sustainable as the number of cells grows.

The model is based on sparse BDH-style activation. Network size must not imply that every thought evaluates every cell. Computation must scale with the admitted active wave and a hard per-thought budget, not with total stored model size.

The system does not possess an oracle for truth. It can measure recognition, local predictive fit, residual reduction, historical calibration, provenance, agreement, and later outcome feedback. These are evidence about groundedness and usefulness, not proof of correctness.

## 2. Current working model of a cell

A cell is not currently assumed to be a complete standalone mini-model. The leading BDH mapping is a fixed-size, head-local microcohort of multiplicative gates that owns corresponding slices of the encoder, value encoder, and decoder. This remains provisional until an implementation experiment determines the useful cohort size and collective computation boundary.

A cell needs the following persistent anatomy:

1. **Stable identity and lifecycle state**
   - stable UID;
   - version/generation;
   - embryonic, shadow, probationary, admitted, mature, dormant, or metabolic state;
   - residency state where relevant.

2. **Ingress receptor**
   - tests whether any relevant subspace of an incoming latent state falls inside the cell's learned receptive envelope;
   - produces calibrated ownership/recognition, coverage, and unexplained residual measures;
   - should be cheap enough to run before the expensive BDH transformation.

3. **Transformation or nudge**
   - performs the cell's BDH-style contribution on the subspace it is qualified to modify;
   - emits a delta rather than claiming ownership of the entire context;
   - should make weak or no changes when coverage is insufficient.

4. **Bounded neighbour ports**
   - the cell knows only a bounded set of local destinations;
   - a port stores destination UID and local relationship/routing state, not a semantic description of the destination or its weights;
   - total degree and per-thought fan-out must be bounded.

5. **Bounded recent routing history**
   - compact signatures or prototypes of states received and sent;
   - sender/recipient UID;
   - incoming and outgoing signal measures;
   - immediate receipt disposition;
   - delayed usefulness/outcome where later available;
   - count, variance, recency, and calibration summaries rather than only a raw average.

6. **Local eligibility trace**
   - ephemeral record of what this cell recognized, changed, and routed during the current thought;
   - retained until terminal reduction and delayed credit assignment;
   - activation creates eligibility but does not itself authorize durable learning.

7. **Homeostatic and lifecycle statistics**
   - use frequency, useful contribution rate, harm/conflict rate, rigidity, plasticity, dormancy pressure, and structural evidence.

## 3. Neighbour relationships and egress memory

An edge should not be represented by one undifferentiated relationship scalar. The working edge state includes a bounded vector of local evidence such as:

- conductance or route strength;
- immediate acceptance rate;
- delayed usefulness after acceptance;
- conditional co-participation;
- independence/correlation evidence;
- disagreement or error history;
- refractory/cooldown state;
- fusion evidence where relevant;
- compact accepted and rejected egress-state prototypes.

For an incoming state, the cell makes two distinct comparisons:

- **Ingress familiarity:** Is this similar to states for which this cell's own transformation was useful?
- **Egress affinity:** Is the post-nudge state similar to states that a particular neighbour previously accepted and later used?

Immediate acceptance estimates whether a neighbour will accept a state. Delayed outcome estimates whether that route was useful. The two must not be collapsed, because a neighbour can confidently accept states while repeatedly contributing to wrong answers.

If several ports are locally plausible, the cell may offer the state to several of them, subject to a hard fan-out and compute-energy budget. Forked descendants remain correlated and cannot be counted as independent votes.

## 4. Three communication planes

The design currently distinguishes three kinds of communication.

### 4.1 Forward cognitive propagation

The travelling latent context or a context-version handle activates a destination and may cause a transformation, relay, branch, or termination.

### 4.2 Immediate receipt acknowledgement

The recipient reports a non-cognitive disposition to the source edge record. Current reason codes are:

- `REJECTED`: no useful match or negligible contribution;
- `ABSORBED`: useful transformation with no outgoing route;
- `FORWARDED`: useful transformation followed by one or more outgoing offers;
- `UNRESOLVED`: the state concerned this cell, but an established prediction failed.

This acknowledgement is routing evidence, not a truth grade and not a reverse thought wave.

### 4.3 Delayed learning and structural credit

After terminal reduction, a delayed signal follows retained eligibility/provenance and determines which type of plasticity is permitted. Useful reason codes include:

- `CONTRIBUTION_RETAINED`;
- `ROUTED_USEFULLY`;
- `RESOLVED_ELSEWHERE`;
- `CONTRADICTED`;
- `STILL_UNRESOLVED`;
- `OUTCOME_UNKNOWN`.

The delayed signal must separately gate transformation learning, receptor-boundary learning, route learning, and structural change.

## 5. Knowing what a cell knows

A cell does not require a language-level statement of its specialty. Operationally, it estimates:

1. **Content ownership:** how strongly the relevant input subspace matches its learned receptive manifold;
2. **Coverage:** how much of the relevant thought it can explain, not merely whether some familiar features are present;
3. **Route match:** whether similar post-nudge states have been accepted and used by particular neighbours;
4. **Transformation fit:** whether its nudge reduces the present residual without damaging already-explained components;
5. **Strangeness or residual:** what remains unexplained after projecting the input onto what the cell recognizes.

Similarity and strangeness are not complements. A state can contain a strongly familiar component and a strongly unfamiliar component at the same time. A Warhammer-trained region may strongly recognize generic fantasy-character structure in a DnD question while failing to cover DnD-specific rules.

Two admission thresholds are therefore useful:

- a lower **routing threshold**, which permits relay or a cheap offer;
- a higher **writing threshold**, which permits a confident latent-state modification.

Moderate overlap is not permission to invent missing details.

## 6. Root anchoring and semantic drift

Every active thought retains an immutable root context and a compact root-question or task signature. Each transformative cell should be able to compare its activity with both:

- the current, already-modified branch state; and
- the original root signature.

This prevents a chain in which every local handoff is reasonable but the final branch no longer answers the original question. High local similarity combined with declining root relevance is a semantic-drift signal.

Raw similarity scores from different cells are not directly comparable. Each cell must calibrate its receptor score against its own positive and negative experience. A path such as 9.7, 8.9, 8.0, 7.5 is meaningful only after those values have a comparable interpretation, such as estimated in-domain probability or calibrated percentile.

The path trace is a chain of epistemic custody. It can identify weak grounding or unsupported confidence, but it still cannot prove that a branch is false. A low-grounded surprising answer may be correct and should normally be retained as speculative rather than silently destroyed.

## 7. Signal quantities must remain separate

The word *amplitude* had been overloaded. The current design separates at least three quantities:

1. **Wave or route energy**
   - controls compute allocation and propagation;
   - is conserved or consumed, never manufactured by a cell's self-confidence;
   - is divided at forks.

2. **Claim or hypothesis support**
   - estimates how strongly a patch is grounded;
   - may rise or fall when a cell adds calibrated, information-bearing evidence;
   - is evaluated from the contribution and its provenance, not set by the terminal cell alone.

3. **Novelty/error amplitude**
   - represents unexplained residual;
   - drives bounded exploration, deferred growth, or possible fission;
   - must not be extinguished merely because familiar cells cannot explain it.

Increasing strangeness should transfer authority away from assertion and toward uncertainty/exploration. It should not simply erase a potential black swan.

The confidence of the last cell remains a local feature. It cannot overwrite a weak chain of custody. A terminal confidence spike without root coverage, residual reduction, or new evidence is an unsupported-confidence signal.

## 8. New-cell development

Newborn cells cannot begin with unrestricted live broadcast because they have no calibrated receptive envelope or route history. Birth creates a temporary dossier containing the triggering state, local provenance, sponsor/frontier, residual, bounded candidate neighbours, and later correction or outcome if available.

The current developmental stages are:

1. **Embryonic:** replay only; no live contribution.
2. **Shadow:** hypothetical nudges and destination tests; no canonical effect.
3. **Probationary:** low-amplitude contribution and very limited port probes.
4. **Admitted:** normal bounded propagation while remaining highly plastic.
5. **Mature:** eligible for rigidity and structural decisions.

Maturity is multidimensional: receptor discrimination, transformation usefulness, per-port calibration, outcome calibration, and structural stability. Promotion should require distinct thought epochs, positive and negative controls, counterfactual usefulness relative to a no-cell baseline, bounded harm, and held-out local generalisation. One lucky event is insufficient.

A functional fission child may inherit discounted portions of the parent's receptor, transformation, and edges. A de-novo cell receives sponsor examples and bounded local candidates. If no correction or useful outcome arrives, the provisional cell remains untrusted and eventually dies.

## 9. Travelling context and branch storage

The full logical context must be visible to every descendant, but physical full copies are unnecessary.

The working representation is:

- an immutable root context `C0`;
- copy-on-write context versions represented by parent handle plus local delta;
- shared ancestry across forks;
- periodic materialised checkpoints to prevent unbounded delta-chain depth;
- an active table mapping cell UID to the relevant context-version handle;
- an ephemeral provenance/version DAG retained until the thought becomes quiescent.

Every cell's delta is visible to downstream descendants immediately. Cells do not mutate one shared central context in place, and they do not wait until termination to expose their contribution.

Copy-on-write removes duplication of unchanged context, but it does not solve dense deltas. The eventual implementation still needs a compact delta form: sparse latent dimensions, sparse gate effects, low-rank or quantised updates, reconstructable activations, or another bounded representation.

Historical last-N routing memory and exact current-thought ancestry are different objects. The first may be bounded and lossy. The second must remain sufficient to deduplicate shared ancestry during the active thought.

## 10. Terminal patches and hypothesis sets

The last terminator does not win. It only establishes that no further contribution can arrive once the active frontier is empty.

Each cell produces a local delta. At quiescence, the system returns one resolution envelope that may contain one or several candidate patches. A terminal candidate currently requires:

- patch/version handle;
- touched-subspace or effect signature;
- applicability signature or conditions;
- residual before/after or current-evidence fit;
- branch support metadata;
- novelty/conflict score;
- provenance DAG reference;
- unresolved dimensions.

There are three distinct operations:

1. **Sequential composition:** apply ordered deltas along one branch.
2. **Compatible aggregation:** combine redundant, reinforcing, or complementary branch contributions.
3. **Hypothesis competition:** preserve contradictory patches as alternatives rather than averaging them.

Shared ancestry is applied once. Fan-out copies do not manufacture corroboration. Independent evidence may increase support; correlated descendants do not count as independent votes.

The result object is provisionally:

```text
ResolutionEnvelope
  optional consensus patch
  candidate hypotheses[]
    patch handle
    support
    applicability/conditions
    provenance reference
    unresolved components
  unresolved mass
  conflict summary
```

If many terminal branches collapse into a few equivalent modes, only those modes need remain. If many materially distinct possibilities remain equally supported, the correct internal result is high uncertainty or underdetermination, not an arbitrary winner. A bounded set of representative modes plus preserved unresolved/other mass prevents unlimited downstream expansion.

Only a sufficiently dominant hypothesis should be committed as a single new context. Otherwise the source retains a compact hypothesis set or emits a cautious result that expresses the alternatives.

## 11. Domain ownership and delayed plasticity

Inference may visit a neighbouring domain because partial overlap can be useful. Durable learning must be more selective.

A DnD thought reaching a Warhammer branch may legitimately:

- teach the branch that similar states should be routed elsewhere;
- narrow the branch's assertion boundary;
- update genuinely shared generic fantasy/RPG cells if their retained contribution was useful.

It should not:

- rewrite Warhammer-specific content merely because those cells activated;
- trigger Warhammer growth or fission when another existing route resolved the residual;
- punish a minority hypothesis strongly merely because another branch won provisionally.

The principal cases are:

- **Low ownership + high residual + resolved elsewhere:** boundary/route learning only.
- **High ownership + high residual + unresolved elsewhere:** in-domain assumption failure; possible fission or correction.
- **Low ownership + high residual + unresolved everywhere:** genuinely unclaimed territory; sponsor a provisional new cell instead of corrupting the nearest existing branch.
- **Useful shared contribution retained:** transform learning only for the contributing subspace/cells.
- **Outcome ambiguous or unknown:** retain eligibility briefly or apply no strong content update.

The core rule is:

> Activation creates eligibility. Resolution assigns plasticity.

## 12. Bounded inference compute

Fast rejection is expected but is not a sufficient complexity guarantee. Ambiguous overlap can otherwise create exponential fan-out.

Every thought therefore needs a hard mechanical compute budget:

1. The thought begins with route-energy budget `B`.
2. Every cheap offer and full cell execution consumes an explicit cost.
3. A fork partitions remaining route energy; it never clones it.
4. A child below branch floor `epsilon` terminates or becomes a bounded suspended candidate.
5. Cells cannot replenish route energy from claim confidence.
6. Refractory/visited-state rules prevent cycles from repeatedly evaluating the same cell for the same thought/version.
7. Degree, outgoing offers, active frontier, and retained terminal modes are bounded.

Under fixed minimum cell cost `c_min`, full cell evaluations are bounded approximately by `B / c_min`. Under branch floor `epsilon`, simultaneously live branches are bounded approximately by `B / epsilon`.

The dampener acts on computation, not on uncertainty. A low-admission branch may die while returning a tiny residual capsule if it encountered unexplained data.

The working local admission table is:

- high ownership, low residual: execute and propagate normally;
- high ownership, high residual: in-domain prediction error; spend bounded novelty budget;
- medium ownership: cheap probe or suspend for a possible second pass;
- low ownership but strong known egress: relay without an expensive nudge;
- low ownership, low residual: terminate completely;
- low ownership, high residual: terminate the full branch and return a compact unclaimed-residual signal.

A two-stage cell admission protocol is preferred:

1. compact offer and cheap receptor test;
2. full BDH transformation only after acceptance.

Gray-zone branches should be queued lazily rather than all executed immediately. The first wave evaluates high-priority candidates. If substantial residual or contradiction remains, a second bounded latent pass resumes selected gray-zone candidates. If the first wave resolves the thought, they are deleted. This provides adaptive System-2-like compute without paying for it on every familiar thought.

## 13. Settled design principles from this checkpoint

- A cell knows bounded neighbours as local ports, not global topology.
- Content recognition and destination selection are separate comparisons.
- Immediate acceptance is not outcome credit.
- Similarity is jurisdiction evidence, not truth.
- Coverage and residual must accompany similarity.
- Similarity and strangeness may both be high.
- Cells must retain a compact root anchor to detect semantic drift.
- Routing permission and writing permission require different thresholds.
- The terminal cell cannot overwrite branch provenance with self-confidence.
- Wave energy, hypothesis support, and novelty amplitude are separate.
- The full logical context travels as shared root plus copy-on-write deltas.
- Terminal branches reduce into a hypothesis set, not an arrival-time winner.
- Contradictory patches remain alternatives.
- Activation does not authorize learning.
- Structural growth/fission requires unresolved evidence after existing routes have had a chance to resolve it.
- Compute must be hard-bounded by conserved energy, execution tolls, fan-out limits, and lazy exploration.

## 14. Open problems and proposed next order

### Next: patch compatibility algebra

Define how latent deltas are classified as:

- sequentially dependent;
- redundant/equivalent;
- reinforcing/aligned;
- complementary/disjoint;
- conditional;
- contradictory.

This requires a latent compatibility test that is stronger than raw cosine similarity. It may need touched-subspace sketches, applicability signatures, counterfactual application to the shared root, and residual/regression probes. The system also needs deterministic, order-independent reduction where appropriate.

### Then: exact backward credit contract

Specify what the terminal reducer returns to each eligible cell and edge, how retained contributions are attributed, how shared ancestry is deduplicated, how uncertain outcomes defer learning, and how route, receptor, transform, and topology plasticity are independently gated.

### Then: structural lifecycle

Resolve the still-open mechanics for:

1. growth and sponsor selection;
2. true functional fission for black-swan exceptions;
3. merge/fusion versus reversible packing or consolidation;
4. dormancy, metabolism, and bridge/connectivity preservation;
5. rigidity and safe reversibility.

### Then: exact BDH implementation mapping

Determine experimentally:

- the useful gate-cohort size of a cell;
- whether a wave step requires a two-phase active-frontier collective for attention/reduction;
- what part of LayerNorm/reduction is cell-local versus wave-global;
- the compact receptor and delta representations;
- sparse execution and memory-layout costs.

### Then: persistence and validation contracts

Define latent ABI/versioning, graph transaction safety, crash recovery, residency, deterministic replay, long-run homeostasis, and acceptance tests. Required tests should include bounded compute independent of total graph size, black-swan survival, cross-domain contamination resistance, convergence under reordered execution, cycle termination, and recovery from cell metabolism/fission/fusion.

## 15. Recommended checkpoint plan

- **Checkpoint 01 — Cell and thought lifecycle:** this document.
- **Checkpoint 02 — Patch algebra and delayed credit:** next discussion block.
- **Checkpoint 03 — Growth, fission, fusion, and metabolism:** structural lifecycle.
- **Checkpoint 04 — BDH execution mapping, persistence, and validation:** implementation contract.
- **Final synthesis:** reconcile the checkpoint documents with the original Campaign 36C, Mycelial Ninereeds, Amorphous Latent-State Network, sparse-wave propagation, and `bdh.py` sources.
