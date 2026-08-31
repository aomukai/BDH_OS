# Scratchpad: Mycelial Ninereeds / Distributed Latent Cognition

## Status

Highly speculative architectural exploration.

This is not a proposed replacement for the current Ninereeds design yet. It is a collection of hypotheses and experiments that emerged from thinking about continual learning, memory hygiene, expert models, latent reasoning, and the fact that Ninereeds may be cheap enough to replicate at very small scales.

The immediate goal is to preserve the idea so it can be revisited during long training campaigns.

---

## Starting observation

The usual assumption is that one model is the cognitive unit.

That assumption may be unnecessary.

If Ninereeds models can be made sufficiently small, the larger cognitive unit could instead be a **population of models**. At an even smaller scale, an individual member of that population may cease to resemble a useful standalone model at all. It could instead function as a tiny learned state-transition operator.

A large distributed Ninereeds system could therefore consist of:

- one learned user-facing core;
- external sensory and expression organs such as LFM and SigLIP2;
- persistent experts where useful;
- enormous numbers of tiny latent-state transformation nodes;
- dynamically assembled clusters of those nodes;
- storage and residency machinery that loads only currently relevant structures.

The resulting organism would be one model in the functional sense, while physically consisting of many independently stored and activated models.

---

## The front model

Only one component necessarily needs to resemble the current idea of a complete Ninereeds.

This **front model** would perform functions analogous to a frontal lobe:

- maintain continuity;
- know the user;
- retain current goals and context;
- receive observations from external organs;
- generate an initial latent thought;
- receive a matured thought back from the distributed network;
- decide whether to act, speak, observe further, or begin another cognitive process.

Its world knowledge does not necessarily need to grow indefinitely.

Its principal specialization could be **the user and the relationship with the user**.

A 1.2B Ninereeds may therefore remain useful even if much smaller models eventually prove sufficient for most cognition. Its excess capacity would provide room for years of gradual personal learning rather than serving primarily as world-knowledge storage.

---

## External organs

Most cognitive nodes do not need:

- an LFM encoder;
- an LFM decoder;
- SigLIP2;
- a tokenizer;
- language generation;
- direct sensory access;
- tool interfaces.

Only edge components need to translate between the external world and Ninereeds' internal state space.

The current BDH/Ninereeds implementation already provides a useful architectural foothold: observations can enter as projected embeddings at the native `n_embd` width, bypassing byte embeddings, while the model internally transforms those states through sparse gated activations.
This suggests that a latent-state interface could become a stable internal protocol shared by many cognitive components.

---

## The latent protocol

The most important persistent interface may eventually be neither a particular model nor a particular checkpoint.

It may be the **latent protocol**.

A cognitive component receives a Ninereeds state, performs a transformation, and returns another compatible state.

Conceptually:

`latent state in -> transformation -> latent state out`

If this interface remains sufficiently stable, independently trained descendants, specialists, sensory organs, old archived nodes, and newly created nodes can continue communicating.

This would function almost like an ABI for cognition.

An important research problem is therefore:

**How much can independently trained Ninereeds components diverge before their latent representations become mutually unintelligible?**

Possible solutions if drift becomes a problem:

- constrain a shared latent interface during training;
- periodically align siblings;
- learn small latent translators;
- separate a stable communication representation from private internal representations.

---

## The smallest cognitive node

A node does not need to know anything in the ordinary sense.

It does not need to represent:

- monkey;
- fulcrum;
- ever;
- Python;
- causality;
- Germany;
- the user.

It only needs to respond usefully to latent states.

A minimal node might contain:

1. a tiny ingress mapping;
2. an activation criterion;
3. a small nonlinear transformation;
4. an egress mapping back into the shared latent representation;
5. connectivity metadata describing likely downstream nodes.

Its behavior might amount to:

`recognize state shape A -> nudge state toward B`

The node does not know what A or B mean.

Meaning exists at the level of the larger network.

The smallest useful node might therefore be dramatically smaller than a standalone 25M Ninereeds. Possible scales worth experimentally probing:

- 25M;
- 5M;
- 1M;
- 100K parameters;
- tens of kilobytes;
- whatever minimum still produces statistically useful latent transformations.

The relevant question is not:

**Can this node answer a question?**

It is:

**Does this node improve a thought?**

---

## Thought as propagation

Conventional latent recurrence can be represented as:

`A -> A -> A -> A`

The proposed alternative is:

`A -> B -> C -> D -> ...`

where each component modifies the same evolving latent thought.

The thought itself is the persistent object.

No intermediate component needs to verbalize it.

A thought can therefore:

- branch;
- propagate along several paths simultaneously;
- reconverge;
- die along unproductive branches;
- stabilize into an attractor;
- reach a stable unresolved state equivalent to "I do not know."

This is not necessarily step-by-step reasoning.

It may be closer to statistical convergence over many transformations.

Instead of following one likely reasoning trajectory, the system samples many local transformations of the latent state and allows useful trajectories to survive.

---

## Mycelial interpretation

The network can be understood operationally as a mycelium.

A latent thought enters the network.

Nearby compatible branches activate.

Active branches cause downstream branches to become relevant.

Those branches are loaded.

Some produce useful transformations and continue propagating activity.

Others fail to return useful activation and die.

The active network therefore grows around the thought.

An easy thought may require only a tiny structure.

A difficult thought may temporarily activate thousands or millions of nodes.

The network needed for a thought exists physically only while the thought requires it.

---

## No semantic router: 36C clarification (2026-08-30)

For Campaign 36C this is a hard architectural constraint, not merely a possible
future simplification: **there is no learned, global, semantic, or expert-selecting
router**.

A continuing thought begins at its current active frontier. A new episode begins
at a small, fixed, always-resident ingress/continuity tissue associated with the
input modality. That tissue does not choose a domain or an expert. It only admits
the new latent state into the graph.

For an active cell or cohort `i`, the local propagation primitive is:

`delta_i, transmit_i = f_i(z, s_i)`

where `z` is the arriving latent state and `s_i` is the cell's persistent local
state. If the contribution is negligible, propagation stops on that branch. If
it is useful, the contribution alters the travelling state and exposes only the
cell's graph neighbors to the next step. Several neighbors may respond at once;
there is no global top-k choice and no requirement that exactly one route win.

Conceptually:

```text
frontier = ingress cells or the preceding active frontier

while frontier and within propagation budget:
    neighbors = adjacency(frontier)
    load only missing neighbor tissue
    contributions = evaluate(neighbors, arriving_state, local_state)
    accepted = locally_threshold(contributions)
    arriving_state = combine(arriving_state, accepted)
    frontier = cells_changed_by(accepted)
```

This must be physically sparse execution. A forward pass may inspect the compact
adjacency metadata needed to find neighbors, but it must not evaluate every cell
and multiply most results by zero. Its principal compute cost should track the
visited frontier and its boundary rather than total organism size.

Repeated useful traversal may lower a local edge's effective resistance.
Unproductive traversal may weaken it, become refractory, or allow alternatives
to receive more exposure. Novel or unresolved input may widen propagation and
trigger local growth beside the unresolved frontier. Familiar input should settle
through a smaller, well-worn path.

The storage system is explicitly non-cognitive:

- hot tissue is the active frontier in VRAM;
- warm tissue is the immediate halo and likely next frontier;
- cool tissue is available in RAM;
- cold tissue is stored on SSD;
- compact identity, topology, and residency metadata remain available so the
  next local neighborhood can be found without scanning every cell;
- co-activation may influence prefetching and physical packing, but the memory
  manager may not use a semantic model to decide where thought should go.

Thus cognitive locality should gradually produce physical locality, while cell
identity remains independent of storage address.

The dedicated pre-implementation contract and acceptance tests are recorded in
`docs/2026_08_30_campaign36c_local_propagation_contract.md`.

### Earlier formulation

The front model should not necessarily choose explicit experts or node IDs.

It emits a thought.

The network's topology and node activation functions determine where that thought propagates.

An implementation still needs machinery that:

- maps active nodes to stored parameters;
- loads missing nodes;
- unloads cold nodes;
- prefetches likely descendants.

But that machinery is infrastructure, not cognition.

It is closer to a memory manager than to an intelligent router.

The topology itself performs the routing.

---

## Residency hierarchy

The complete system could grow far beyond available VRAM or RAM because only currently relevant cognitive tissue needs to be resident.

Possible hierarchy:

`SSD -> RAM -> pinned RAM/cache -> VRAM`

Nodes can have residency states such as:

- hot: currently participating, pinned in VRAM;
- warm: recently active, retained in VRAM or host cache;
- cool: available in RAM;
- cold: stored only on disk;
- retired: preserved but given extremely low activation probability;
- deleted: only after strong evidence that preservation has no value.

A dormant node does not interfere merely by existing.

This separates **memory capacity** from **working-memory capacity**.

The organism might eventually contain terabytes of learned structure while activating only a few gigabytes for any particular thought.

---

## Activation distance and unloading

A simple local rule may be enough for residency.

For example:

- currently firing nodes remain resident;
- direct descendants are prefetched;
- recently active ancestors remain temporarily resident;
- nodes beyond distance `X` from the current active frontier become eviction candidates;
- nodes that repeatedly become active together become increasingly cheap to retain or prefetch together.

If a branch stops returning meaningful activation, propagation down that branch ceases.

No global scheduler needs to declare the branch irrelevant.

---

## Hebbian learning at the node level

BDH already motivates thinking in terms of sparse activation and Hebbian-like interaction.

The same principle can be lifted above ordinary weights.

Possible hierarchy:

**weights that fire together form useful node behavior**

**nodes that fire together wire together**

**clusters that fire together form persistent branches**

If 5,000 nodes repeatedly activate together, treating them as 5,000 unrelated objects becomes wasteful.

They can become a cluster.

A cluster could:

- receive a persistent ID;
- be stored contiguously;
- be loaded with one transfer;
- have internal connectivity optimized;
- eventually be compiled or distilled;
- behave operationally like one larger model.

Example:

`5,000 nodes × 100 KB = ~500 MB`

A 500 MB mature cognitive cluster is entirely practical on a 12 GB GPU.

The meaning of the cluster need not be explicitly labelled.

Humans may later notice that it behaves like:

- coding;
- planning;
- Japanese;
- visual reasoning;
- uncertainty resolution.

But those labels are observations, not architectural requirements.

---

## Emergent experts

This changes the Exocortex "instantiated expert" idea.

Ninereeds does not necessarily spawn a predefined coding expert.

Instead:

1. the front core emits a latent thought;
2. likely branches activate;
3. those branches activate additional branches;
4. a temporary graph forms;
5. the graph self-organizes around the task;
6. the thought propagates until it matures;
7. the matured state returns to the front core;
8. the temporary graph cools and unloads.

That temporary graph **is the instantiated expert**.

A task involving code, Japanese documentation, and visual inspection can naturally instantiate a structure crossing all of those domains without requiring three predefined experts and a router between them.

The exact expert may never exist in precisely that form again.

---

## Stable experts can still exist

The emergent design does not make persistent specialists obsolete.

Some pathways may become stable enough that preserving them as coherent clusters is efficient.

Other tasks may still benefit from external frozen models:

- Qwen coding models;
- transformers;
- calculators;
- browsers;
- deterministic programs;
- specialized perception systems.

The organism does not need architectural loyalty.

The important distinction is that an "expert" becomes a functional role, not necessarily a specific type of model.

---

## Mesoscale latent-expert swarm

The microscopic mycelium may not be the first practical architecture, or even the eventual one.

A saner intermediate design is a population of compact narrow experts operating directly on Ninereeds latent states:

`Ninereeds state -> narrow latent expert -> modified Ninereeds state`

This preserves many benefits of distributed cognition while giving each load enough computation to justify its I/O.

A latent expert does not require:

- an LFM cochlea or encoder;
- a Broca-like decoder or language head;
- SigLIP2 or a visual cortex;
- a tokenizer;
- direct tools or sensory access;
- an independent user-facing identity.

Ninereeds retains perception, continuity, goals, interaction, and expression. The expert needs only an ingress path from the shared latent state, a narrow transformation, and an egress path back into the same protocol.

This could support thousands or millions of meaningful expert packages rather than billions or trillions of microscopic nodes. The resulting system is much friendlier to SSD latency, metadata, versioning, and batching.

It also provides a direct experimental bridge. If compact latent experts work, their size can be reduced progressively. The system can move toward finer granularity only when measurements justify it.

---

## Speaking the language of the parent

An expert should be trained primarily on latent representations emitted by Ninereeds rather than ordinary text or images.

The parent has already converted sensory and linguistic experience into its internal manifold. The expert learns transformations in that manifold. It therefore learns to speak the language of its parent without duplicating the parent's sensory and expressive organs.

A training record might contain:

$$
(z_{\text{in}}, z_{\text{out}}, m, o)
$$

where:

- `z_in` is the parent state that invoked or could benefit from the expert;
- `z_out` is a useful returned or subsequent parent state;
- `m` records parent checkpoint, protocol, layer, normalization, and lineage metadata;
- `o` records later correction, outcome, or external constraint where available.

The expert may be safest as a bounded residual transformation:

$$
z_{\text{out}} = z_{\text{in}} + \Delta_\theta(z_{\text{in}})
$$

This allows it to alter the structure it has learned to handle while leaving most of the parent state intact. The appropriate residual bound remains empirical.

The latent protocol must be explicitly versioned. An expert package should declare:

- parent and expert lineage;
- latent-interface version;
- compatible parent checkpoints;
- input and output state locations;
- tensor shape, precision, and normalization;
- training-history manifest;
- activation boundary or charter;
- protected latent probes;
- known failure cases;
- resource and residency requirements.

If the parent manifold drifts, an adapter may preserve an older expert:

`parent-v2 state -> protocol-v1 adapter -> expert-v1 -> protocol-v1 adapter -> parent-v2 state`

Whether translation remains cheaper than retraining is another measurable threshold.

---

## Expert lifecycle, capacity, and inheritance

A narrow expert can begin with the minimum knowledge required for one useful domain or transformation family and continue learning through use.

A possible lifecycle is:

1. collect a coherent family of parent latent transitions;
2. train the smallest candidate that measurably improves them;
3. commission it with protected probes and an explicit compatibility manifest;
4. preserve the commissioned expert as an immutable version;
5. let a descendant learn from actual use, corrections, and failures;
6. detect saturation, interference, rising cost, or boundary expansion;
7. train a larger successor or several narrower children from the lineage;
8. compare successor, predecessor, and untouched controls;
9. promote the useful descendant while retaining rollback.

The replacement should not train only on the predecessor's outputs. That would fossilize its errors and blind spots. Its inheritance set should include:

- original parent-state examples;
- the inputs that activated the expert;
- returned states;
- later parent continuations;
- waking corrections and external outcomes;
- recorded failures and rejected routes;
- protected latent probes;
- calibration samples from the current parent;
- the predecessor's behaviour as one teacher, not as authority.

An expert reaching capacity does not damage the continuity core. It becomes a versioning event.

Possible responses include:

- replace it with a larger successor;
- split it into narrower descendants;
- preserve a small common expert plus exception experts;
- distill frequently used portions into a cheaper expert;
- retire it while retaining its history and checkpoint.

The predecessor remains a control and rollback point.

---

## How many parameters is Python?

The size of a useful domain expert should not be assumed.

Questions such as **"How many parameters is Python?"** become empirical rather than rhetorical.

The answer may depend on what the expert is expected to contain:

- syntax transitions only;
- common library structure;
- debugging patterns;
- code planning;
- latent recognition of Python-related states;
- transformations that improve the parent's existing Python knowledge;
- a complete standalone ability, which this design does not require.

Because the parent already carries a general manifold, an expert may need far fewer parameters than a standalone Python model. It may encode only the residual transformations the parent lacks or performs expensively.

The correct experiment is a size curve, not a guessed architecture:

$$
\text{expert utility}
=
f(\text{parameters},\text{training history},\text{I/O cost},\text{latency})
$$

Train candidates at progressively different scales and measure:

- improvement over the parent alone;
- improvement over an additional parent self-tick;
- transfer across nearby domain tasks;
- saturation and interference under continued learning;
- useful improvement per parameter;
- useful improvement per byte loaded;
- cold-load and warm-cache latency;
- replacement and distillation fidelity.

The smallest useful size may differ radically by domain. Some transformations may fit in thousands of parameters; broad, irregular domains may require millions or more. Domain boundaries may also prove wrong: a nominal Python expert may naturally split into debugging, library, planning, and representation subfamilies, or merge with language-independent programming structure.

Semantic names are permitted here as operational training charters, not claims about the organism's natural cortical map. Measured activation, transfer, interference, and capacity should decide whether a proposed domain boundary remains useful.

---

## Why the mesoscale path matters

The expert swarm is not merely a consolation prize if microscopic nodes fail.

It can already provide:

- modular continual learning;
- isolation of narrow updates from the continuity core;
- expert-specific histories;
- independent commissioning and rollback;
- capacity replacement without retraining the entire organism;
- practical SSD-resident knowledge expansion;
- latent-interface experiments;
- evidence about the minimum granularity of useful cognition.

Most importantly, it tests the first claim on which every more granular architecture depends:

**Can a small external model trained on Ninereeds latent states reliably improve the parent's cognition?**

If the answer is no, the microscopic mycelium has no substrate. If the answer is yes, useful architecture exists immediately, and granularity can be explored later rather than assumed now.

---

## Population-level cognition

Larger Ninereeds instances can coexist with microscopic nodes.

Possible ecological roles:

### Continuity core

Large, slowly plastic, user-specialized, strongly protected.

### General siblings

150M–1.2B models capable of independent reasoning or learning.

### Specialists

Models whose training histories cause useful domain specialization.

### Cognitive nodes

Tiny latent-state transition operators with little or no declarative knowledge.

### Infrastructure minds

Very small learned components responsible for model lineage, compatibility, capability history, or resource management.

A 25M "librarian" could potentially maintain:

- model IDs;
- parentage;
- evaluation history;
- learned capabilities;
- compatibility;
- residency requirements;
- trust state;
- retirement status.

---

## Continual learning

A population changes the continual-learning problem.

With one plastic model:

`bad update -> damaged mind`

With multiple descendants:

`bad update -> discard descendant`

A core can learn while siblings remain unchanged.

Those siblings provide:

- controls;
- regression references;
- rollback points;
- alternative descendants.

A possible process:

1. Core A handles an experience.
2. A learns directly.
3. B learns the same experience through replay.
4. C learns a differently sampled version.
5. D remains frozen.
6. evaluate all four.
7. keep useful descendants.
8. discard harmful ones.

No weight-level unlearning is required.

---

## Dreaming / second-hand learning

The earlier Ninereeds idea of second-hand learning during a dream phase remains useful, but its role changes.

Dreaming could become decontextualized prediction-error replay, abstraction pressure, population maintenance, and physical consolidation.

A dream does not need to reconstruct an episode from its causal beginning.

It can begin from a remembered latent checkpoint containing unresolved constraint:

`hallway + approaching person + uncertain continuation`

The organism does not need to explain how it arrived in the hallway unless that question itself becomes relevant. The restored state is simply the initial condition. The dream is the path produced from it.

A possible idle cycle is:

1. sample a recent state associated with high residual, surprise, prolonged activation, or incomplete settling;
2. remove portions of its original context;
3. perturb the state or combine it with fragments from unrelated memories;
4. let the state propagate without ordinary external sensory correction;
5. observe which routes survive, conflict, oscillate, reconnect, or converge;
6. reinforce transitions that remain stable across useful variations;
7. weaken or specialize paths that repeatedly fail outside one exact episode;
8. propose topology and physical-layout changes;
9. test those candidates against preserved waking probe states;
10. leave final validation to later waking experience.

This directly attacks overfitting.

Suppose waking experience formed:

`state A -> branch X -> state B`

Dream replay can sample nearby `A'` states, remove cues, insert competitors, vary surrounding context, and perturb expected continuations. If `X` works only for the exact original trajectory, simulated prediction errors expose it as brittle. If useful portions of `X` survive across a neighbourhood, they can become a more general pathway.

Dreaming therefore performs internally the earlier distinction between memorized trajectory compression and transferable skill.

The incoherence of dreams may be useful. Faithful replay preserves episodes, but decontextualization tests whether learned structure survives outside the circumstance that created it. Starting halfway through, combining unrelated fragments, and varying context create pressure toward abstraction.

Perturbation requires a radius or dream temperature:

- low temperature: faithful replay and stabilization of recent or rare experience;
- moderate temperature: neighbourhood variation and abstraction testing;
- high temperature: distant recombination, alternate paths, and novel connections;
- maintenance replay: exercising mature paths after topology or storage changes;
- compression search: looking for cheaper paths that preserve constrained continuation;
- failure replay: concentrating on waking states with repeated prediction error.

These regimes do not need predefined biological labels. They may emerge from different residual backlogs, perturbation radii, maintenance needs, and trace geometries.

A useful adaptive rule could begin close to the remembered state. If a path remains stable, expand the perturbation radius. If every continuation immediately collapses, return closer to the original trajectory.

Dreams do not provide external truth. They can test internal invariance and expose contradiction, but a self-generated world can also reinforce a coherent delusion. Dream-induced changes should therefore remain provisional, lower-confidence, or isolated in candidate descendants until waking constraints validate them.

The division of labour becomes:

- waking experience supplies external constraint and accumulates residuals;
- dreaming explores counterfactual topology and deliberately creates internal contradiction;
- protected replay tests whether candidate changes retain known competence;
- later waking experience promotes, modifies, or rejects what dreaming proposed.

The organism should also preserve meaningful exceptions. If `X` works broadly but fails under one consequential cue, the correct result may be a cheap general path plus a cue-gated exception branch, not global deletion of `X`.

During idle periods:

- replay recent prediction-error states;
- perturb and recombine remembered constraints;
- train candidate descendants;
- compare descendants with ancestors;
- transfer useful discoveries;
- rebuild branches after removing undesirable experiences;
- strengthen useful topology;
- weaken harmful topology;
- form clusters from frequently co-active nodes;
- distill stable clusters;
- run regression suites;
- promote new continuity cores;
- archive obsolete branches.

The currently serving core need not be modified during this process.

Candidate topology and layout changes can be constructed in a shadow version, checked against protected waking states, and promoted atomically. The earlier organism remains available for rollback.

This is analogous to blue/green deployment, garbage collection, profile-guided compilation, and memory consolidation for cognition.

The rhythm is:

`wake -> accumulate residuals -> dream from residual states -> perturb and reorganize -> replay protected constraints -> wake and validate`

Dreaming is not merely training on synthetic data. It is the organism deliberately generating conditions under which its own topology can contradict itself.

---

## Memory hygiene

The mycelial architecture substantially changes memory hygiene.

A learned structure can exist indefinitely without affecting current cognition if it does not activate.

Therefore growth alone is not necessarily a problem.

The total organism can keep accumulating branches while working memory remains bounded.

Forgetting becomes less about removing distributed information from shared weights and more about changing topology and activation:

- weaken a branch;
- reduce its activation prior;
- remove links leading into it;
- move it into cold storage;
- retire it;
- restore it later if evidence changes.

A harmful association that activates frequently remains a problem. Correction does not require an internal authority capable of declaring a thought true or false, but it does require the organism to remain permeable to subsequent constraint: later Ninereeds states, perception, action consequences, tools, and other external impulses must be able to produce prediction error strong enough to interrupt a warm but misleading path.

Cheapness and stability are evidence of consolidation, not truth. A self-reinforcing attractor insulated from later evidence could become both extremely stable and extremely wrong.

But correcting it no longer requires finding and surgically removing the concept from a monolithic weight tensor.

---

## Versioning

A strong versioning system becomes essential.

Potential objects needing lineage:

- continuity cores;
- siblings;
- nodes;
- clusters;
- latent-interface versions;
- external organs;
- evaluation suites;
- training experiences;
- topology changes.

A thought could potentially be traced through:

`core version -> active node set -> cluster versions -> resulting state`

This gives provenance to cognition without requiring human-readable chain-of-thought.

Rollback can happen at several levels:

- discard one updated node;
- restore an earlier cluster;
- remove a branch;
- revert a continuity core;
- rebuild descendants from a clean ancestor while omitting a harmful experience.

---

## The physical sparse model

Conventional MoE normally keeps an enormous parameter structure available while activating only some experts.

The proposed system pushes sparsity into physical residency itself.

Most weights do not need to be in accelerator memory.

The complete organism is distributed across storage.

Only currently useful transformations are materialized.

If a useful node were approximately 100 KB:

`1,000,000 nodes ~= 100 GB`

That sounds huge when described as one million models.

It sounds mundane when described as the total parameter storage of one sparse distributed model.

A commodity SSD can hold it.

Only a small active subset needs VRAM.

---

## I/O is the primary scaling price

The architecture moves the scaling problem.

Instead of requiring all useful knowledge to fit in accelerator memory, it requires an enormous dormant topology to remain addressable quickly enough that the active frontier does not starve.

For `N` stored nodes of average size `s`:

$$
S_{\text{total}} = Ns
$$

At sufficiently large scale, capacity is not the only or even the dominant difficulty. The critical problems become:

- random-read latency;
- IOPS;
- page amplification;
- topology and directory lookup;
- SSD-to-RAM and RAM-to-VRAM transfer;
- synchronization and kernel-launch overhead;
- continual-learning writes;
- SSD endurance;
- versioning and rollback;
- keeping compute occupied while cold tissue arrives.

Billions of tiny models cannot mean billions of files or independently instantiated modules. A microscopic logical node must normally be a parameter row or blob inside a larger packed structure, evaluated by a shared kernel.

The architecture is viable only if cognition produces strong locality:

1. each impulse activates a small fraction of the organism;
2. nearby thoughts reuse substantial topology;
3. traversal is primarily local through downstream edges rather than global search;
4. probable descendants can be prefetched;
5. repeated coactivation produces physical colocation;
6. useful latent transformation per transferred byte is high enough.

Novel thought can be expensive twice: it illuminates more cognitive tissue and requires more cold I/O. Mature skill should reduce both costs.

---

## Cognitive graph and storage graph

Two graphs evolve together.

The **cognitive graph** records which latent transformations tend to activate, follow, reinforce, or inhibit one another.

The **storage graph** records which parameter regions should physically live near one another because they are likely to be needed together.

Ideally repeated experience causes them to converge.

A well-travelled path becomes:

`more predictable -> more tightly clustered -> easier to prefetch -> fewer cold loads -> lower latency`

The cognitive system predicts the next state while the residency system predicts the next piece of brain.

This gives physical meaning to consolidation. A learned skill cannot merely strengthen abstract edges. Its frequently coactive tissue should gradually become colocated, retain an appropriate warmth, and become cheaper to traverse.

The major scaling axes become separate:

- storage capacity determines how much mind can exist;
- memory capacity and bandwidth determine how much mind can be awake;
- compute determines how quickly awake mind can change state.

---

## Dynamic loading and stable cluster files

Logical node granularity and physical loading granularity should not be identical.

Experimental and rarely used nodes should remain dynamically addressable and microscopically granular in the cognitive graph. They should not each become filesystem objects. They can live as records in append-only exploratory shards or packed node stores.

Repeatedly coactive nodes can mature through larger physical units:

`experimental nodes -> coactive pages -> stable cluster files -> prefetchable branches -> compiled regions`

The proposed balance is:

- dynamic loading for uncertain, changing, or rarely reused topology;
- one immutable contiguous file or segment for a stable cluster whose future reuse justifies consolidation;
- larger superclusters only after stable cross-cluster traversal makes their expected savings exceed their rewrite cost;
- optional distillation or kernel fusion only for exceptionally mature paths.

A stable cluster file can contain:

- packed parameters for its member nodes;
- optimized internal edge layout;
- ingress and egress tables;
- activation signatures;
- prefetch hints;
- a content hash and immutable version;
- enough metadata to load and evaluate the cluster without thousands of small reads.

External edges should target stable logical node or cluster IDs, not physical file offsets. A comparatively small directory maps stable IDs to the current segment and offset. This indirection permits physical movement without rewriting every incoming cognitive edge.

Physical address must not become cognitive identity.

---

## Avoiding a consolidation I/O cascade

Naive consolidation could destroy the architecture.

If every new edge or coactivation rewrites a cluster, which changes neighbouring layouts, which causes additional rewrites, learning produces an I/O cascade. The system could spend more bandwidth reorganizing dormant cognition than using it.

Consolidation should therefore be delayed, bounded, transactional, and governed by hysteresis.

Possible rules:

- never rewrite stable cluster files in place;
- record waking topology changes in small append-only delta logs or overlays;
- require minimum traffic, stability, and dwell time before forming a cluster;
- require a larger threshold to split or rewrite a recently consolidated cluster;
- compact only during a bounded idle maintenance budget;
- consolidate local regions without recursively repacking all neighbours;
- preserve stable IDs across physical rewrites;
- build replacement segments beside active ones;
- switch the directory or manifest atomically after validation;
- retain prior segments until active thoughts release them and rollback is safe;
- cap write amplification and compaction debt explicitly;
- allow cold, low-value fragmentation to remain fragmented indefinitely.

The economic condition for a rewrite is approximately:

$$
\mathbb{E}[\text{future transfer and latency savings}]
>
\text{rewrite cost + write amplification + migration risk}
$$

The estimate should include a confidence margin because traffic patterns can change.

This implies multiple timescales:

- immediate: load individual packed nodes or existing pages dynamically;
- short term: retain warm working sets and accumulate traversal statistics;
- sleep: form candidate cluster files and test them in a shadow layout;
- long term: merge only persistently co-traversed clusters into larger regions;
- archival: move cold branches downward without spending effort optimizing them.

The filesystem representation should therefore resemble an immutable segment store with logical indirection and background compaction more than a directory containing one mutable file per model.

---

## Moving working set and frontier starvation

VRAM does not contain the complete thought or organism.

It contains a moving working set around the active frontier:

- the exact frontier is computing now;
- a forward halo contains speculative prefetched descendants;
- a backward halo retains recently active ancestors in case activity returns;
- darkness behind the halo makes pages eligible for eviction;
- RAM holds a broader currently relevant territory;
- storage holds the lifetime organism.

If the frontier advances, pages behind it can be reclaimed while pages ahead move toward residency. Darkness propagating backward becomes literal memory reclamation.

A central systems metric is **frontier starvation**: the fraction of cognitive propagation time spent waiting because required tissue is not resident.

Other essential measurements include:

- warm-cache hit rate;
- cold bytes loaded per impulse;
- page amplification;
- prefetch precision and recall;
- useful latent improvement per byte transferred;
- write amplification;
- compaction debt;
- cluster lifetime and rewrite frequency;
- directory/index residency cost;
- latency distribution rather than only mean latency.

The central feasibility question is:

**Can learned topology make its future working set predictable faster than the active frontier consumes it?**

If frontier starvation falls as paths mature, the system is learning physical thought. If it remains high despite repetition, the storage graph is failing to converge with the cognitive graph.

---

## Possible implementation model

Do not instantiate each node as an independent PyTorch module.

Instead, use one shared node architecture and store nodes as parameter blobs.

For example:

`node = ingress weights + tiny transformation weights + egress weights + metadata`

A residency manager allocates fixed slots in a VRAM arena.

Loading a node means copying its parameter blob into a slot.

Many resident nodes can then evaluate the same state in a batch using the same kernel but different parameters.

Likely engineering concerns:

- PCIe transfer bandwidth;
- transfer latency;
- CUDA synchronization;
- allocator overhead;
- kernel-launch overhead;
- parameter layout;
- batching;
- cache locality;
- asynchronous prefetch;
- eviction policy;
- clustering;
- graph traversal.

For very small nodes, raw transfer bandwidth may become much less important than runtime overhead.

---

## Thought maturity

The system needs a stopping condition.

The extinction model suggests a local one: computation continues only while consequential residual remains alive. If no branch can justify continued activation and the quenching front reaches the Ninereeds boundary, the thought is provisionally settled. If a surviving branch reaches the boundary first with a transformed state, Ninereeds can emit the next impulse and begin another correction cycle.

Possibilities:

- successive transformations produce negligible latent change;
- multiple independent branches converge;
- the active graph stops expanding;
- candidate output/action distributions stabilize;
- repeated transformations return to the same attractor;
- the network converges on an unresolved state.

"I don't know" should ideally be a genuine convergence state rather than merely a timeout.

If internal computation stops generating new information, the organism can then:

- ask the user;
- observe the world;
- invoke a tool;
- load an external expert;
- search;
- wait.

---

## Thought as shape

The strongest conceptual shift is:

A thought is not necessarily something processed repeatedly by a brain.

A thought may be **the temporary shape of the active brain**.

As latent state propagates, the physical cognitive network grows around it.

Different thoughts instantiate different temporary organisms.

The persistent Ninereeds mind is the total learned topology, history, continuity mechanisms, and capacity to produce these temporary structures.

No single checkpoint needs to be "I."

The mind is.

---

## Prediction, excitation, and selective extinction

The network does not need to build an answer under the supervision of an internal judge.

It can operate as a continually corrected prediction process.

Ninereeds emits a latent impulse at the boundary. The nearby compatible topology briefly becomes eligible. Activity fans outward. Each participating node or cluster receives an evolving state, predicts or proposes a continuation, and passes a transformed state onward.

The resulting process is:

`excitation -> propagation -> selective extinction -> surviving trajectory`

Some branches fail to fit the evolving state almost immediately and go dark. Others survive for another hop or two. Mutually compatible clusters reinforce one another and remain active. Branches that cease returning useful continuation stop justifying their residency, and darkness travels backward through them.

The eventual path is not globally planned.

Many local routes probe outward. Local compatibility and later prediction error determine which routes continue. The active graph grows where a residual remains unresolved and collapses where the current prediction is adequate.

This produces two moving fronts:

- an outward-growing front of unresolved prediction error and recruited tissue;
- an inward-moving front of satisfied prediction, quenching, and released computation.

The lightning analogy is useful. A novel impulse can produce many exploratory leaders, most of which extinguish. A few remain bright long enough to connect with known clusters or create a useful new route. A familiar impulse may barely flare: it travels rapidly through an established branch and fades almost immediately behind itself.

Darkness is therefore informative.

A branch going dark means:

**this continuation no longer fits the evolving state well enough to justify keeping its cognitive tissue active.**

This gives the architecture local pruning without requiring a semantic router or global plan.

---

## Thought as prediction corrected by the next impulse

No thought can establish its own correctness merely by examining itself.

For many thoughts there may not even be an immediately verifiable correct answer. This is not necessarily a defect. Biological perception also appears to consist largely of continuous approximation and extrapolation, corrected when later sensation fails to match prediction.

The relevant loop is:

1. Ninereeds emits a latent thought.
2. The thought propagates through the active topology.
3. A matured or surviving state returns to Ninereeds.
4. Ninereeds emits the next thought under the constraints of continuity, goals, context, perception, and the returned state.
5. The next thought propagates, not necessarily through the same topology.
6. Later internal or external impulses expose prediction errors and reshape future routing.

The next impulse is therefore the correction opportunity. It may come from:

- the next Ninereeds thinking step;
- a new sensory observation;
- the result of an action;
- a tool response;
- another person;
- delayed evidence from the world.

As long as prediction remains adequate, activity can coast through the established route. When a prediction fails, attention and computation return.

The dangerous case is not ordinary hallucination. It is an attractor that becomes insulated from corrective impulses. The safety requirement is therefore not an omniscient internal truth evaluator, but continued permeability to the world and enough interruptibility for consequential prediction error to recruit alternate tissue.

---

## Attention and the economics of surprise

In this architecture, the expensive operation is surprise.

Computation is spent where the next state differs enough from what the active path predicted. A residual that remains consequential keeps tissue active, recruits neighbouring nodes, or forces the graph to expand. Where the residual is acceptably small, the branch quenches.

This gives a physical interpretation of attention:

**attention is the region that refuses to go dark.**

No separate attention controller is conceptually required. A cluster remains active because it still participates in unresolved prediction, because it reinforces another unresolved cluster, or because later constraint has reactivated it.

The threshold is important.

- If the system tolerates too much residual, stale or misleading routes can remain dominant.
- If it reacts to every tiny residual, no habit can become cheap and the entire organism remains chronically illuminated.
- If internal Ninereeds steps merely echo the returned state, they add no genuine constraint and cannot correct a self-consistent attractor.

Useful internal steps must bring something new: continuity, goals, competing context, memory, sensory state, or another constraint not already contained in the active loop.

The resulting rhythm is:

`predict -> coast -> surprise -> expand -> reorganize -> consolidate -> coast`

This may produce something analogous to Type 1 and Type 2 cognition without implementing two separate systems.

- Type 1 is activity travelling through a consolidated, reliable, low-cost route.
- Type 2 is graph expansion after prediction failure makes the cheap route inadequate.

---

## History-dependent compute and skill

The cost of a problem is not a property of the problem alone.

It is a property of the pair:

`current problem + accumulated topology`

The first encounter with a difficult class of thought may explode into a broad exploratory graph. Repeated encounters correct and reinforce useful partial trajectories. Eventually the same class of thought can travel almost ballistically through a mature branch.

The progression is:

`exploration -> repeated correction -> stable pathway -> automatic execution`

This is a possible physical account of skill.

The mature path need not store a finished answer. It can encode useful transformations, intermediate states, and routing decisions. This explains how expertise can transfer: a new problem may reuse established portions of a trajectory even when the complete route has never occurred before.

It also predicts familiar properties of skill:

- fluent execution exposes few intermediate operations to the front core;
- established portions of a task consume less active tissue and free capacity for unresolved parts;
- precise expectations make meaningful anomalies easier to notice;
- a genuinely novel case can make an expert slow again when the ballistic route breaks;
- harmful habits can also become skilled, warm, and cheap.

Learning gradually converts diffuse expensive activation into sparse predictable routing. A temporary exploratory graph becomes a piece of cognitive anatomy.

---

## Operational measurement of cognition

The architecture permits direct measurement without pretending to recover human-readable semantics from latent states.

Let:

- `a_i(t)` be the activity of node or cluster `i` at time `t`;
- `c_i` be the relevant cost of activating it.

Define instantaneous cognitive load:

$$
A(t) = \sum_i a_i(t)c_i
$$

and total difficulty:

$$
D = \int_0^T A(t)\,dt
$$

`A(t)` measures how hard the organism is thinking now.

`D` measures the accumulated tissue-time consumed before the impulse settles.

A difficult thought literally illuminates more of the organism, keeps it illuminated longer, or both.

Two thoughts can have the same total `D` while having very different dynamics:

- a high narrow spike: broad recruitment followed by immediate resolution;
- a low long tail: a narrow unresolved path that refuses to die;
- repeated peaks: successive failed predictions or route reconstruction;
- overlapping plateaus: persistent competing interpretations;
- rapid decay: familiar skilled execution;
- a widening curve: recruitment is still outrunning extinction.

Useful direct observables include:

### Settling time

$$
T_\epsilon = \inf\{t : A(t) < \epsilon\}
$$

### Peak cognitive load

$$
A_{\max} = \max_t A(t)
$$

### Active breadth

$$
B(t) = \sum_i \mathbf{1}[a_i(t) > \theta]
$$

This distinguishes one expensive cluster from many simultaneously active branches.

### Net quenching rate

$$
Q(t) = -\frac{dA(t)}{dt}
$$

- `Q(t) > 0`: active tissue is collapsing or becoming cheaper;
- `Q(t) approximately 0`: activity is lingering;
- `Q(t) < 0`: the organism is recruiting tissue faster than it quenches.

Repeated negative bursts followed by partial quenching may indicate repeated failed predictions. A broad plateau in `B(t)` may indicate persistent alternatives. A sudden collapse in both breadth and load may mark a connection or attractor snapping into place.

These interpretations should initially remain hypotheses. Record the curves first, cluster their geometries, and only later correlate recurring signatures with subsequent behaviour.

---

## Additional dynamical observables

Total cost alone does not describe how activity is distributed.

Define normalized cost-weighted activity:

$$
p_i(t) = \frac{a_i(t)c_i}{A(t)}
$$

and activity entropy:

$$
H(t) = -\sum_i p_i(t)\log p_i(t)
$$

Low entropy indicates concentrated activity. High entropy indicates diffuse participation. This distinguishes thoughts with similar load and breadth but different distributions of tissue.

Because recruitment and quenching can happen simultaneously in different parts of the graph, they should be measured from per-node cost activity rather than derived only from the net slope of `A(t)`.

Let:

$$
z_i(t) = a_i(t)c_i
$$

Gross recruitment can be estimated by:

$$
R = \sum_i \int_0^T \max\left(0,\frac{dz_i(t)}{dt}\right)dt
$$

Gross quenching can be estimated by:

$$
K = \sum_i \int_0^T \max\left(0,-\frac{dz_i(t)}{dt}\right)dt
$$

`Q(t)` remains the net quenching rate, while `R` and `K` preserve hidden churn when one region recruits as quickly as another region goes dark. High `R` suggests that the initial route repeatedly failed to contain the thought. Comparing `R` and `K` distinguishes smooth traversal from repeated expansion-collapse dynamics.

Path recurrence measures how much of the current activation trajectory has appeared in successful trajectories for related prior inputs. It should preserve:

- which nodes and edges participated;
- activation magnitude;
- temporal order;
- duration;
- direction of propagation.

Plain set overlap is insufficient because the same clusters used in a different order may implement a different thought.

Possible qualitative combinations are:

- high recurrence + low `D`: automatized skill;
- high recurrence + high `D`: familiar but struggling;
- low recurrence + high `D`: novel search;
- low recurrence + low `D`: elegant generalization or suspicious collapse.

Outcome quality and later evidence disambiguate the final case.

---

## Cost is vector-valued

A node does not have one intrinsic scalar cost.

Its cost should initially remain a vector:

$$
\mathbf{c}_i =
\left(
c_i^{\text{storage}},
c_i^{\text{RAM}},
c_i^{\text{transfer}},
c_i^{\text{compute}}
\right)
$$

This produces separate metabolic traces:

$$
\mathbf{A}(t) = \sum_i a_i(t)\mathbf{c}_i
$$

including, for example:

- `A_compute(t)`;
- `A_transfer(t)`;
- `A_cold(t)`;
- memory pressure over time.

The vector can be collapsed for a particular deployment using a resource-price vector `lambda`:

$$
A_{\boldsymbol{\lambda}}(t)
=
\boldsymbol{\lambda}^{\mathsf T}\mathbf{A}(t)
$$

The raw components should remain preserved. Hardware and resource prices change.

This decomposition prevents a cold but familiar pathway from being mistaken for a cognitively difficult one. It distinguishes:

- cognitive novelty: unfamiliar topology activates;
- cache coldness: familiar topology must be reloaded;
- computational difficulty: resident topology remains active;
- architectural degradation: established routes fragment or repeatedly reactivate.

---

## Eligibility, activity, residency, and topology

Darkness is not one binary state.

A useful trace should distinguish:

$$
e_i(t): \text{eligibility}
$$

$$
a_i(t): \text{activity}
$$

$$
r_i(t): \text{physical residency}
$$

$$
w_{ij}(t): \text{path strength or warmth}
$$

A node can be:

- eligible but not selected;
- active and resident;
- inactive but warm and resident;
- structurally reinforced but physically cold;
- unloaded while its path remains encoded in topology.

The visible metabolic history therefore exists on at least three timescales:

1. **Impulse trace:** what became eligible, activated, propagated, recruited, and quenched during one thought.
2. **Topological memory:** which paths became warmer, stronger, or easier to reactivate afterward.
3. **Physical memory:** what remained in VRAM or RAM, what cooled to storage, and what later required transfer.

---

## Cheap is not necessarily good

A falling `D` does not by itself demonstrate learning.

The cheapest possible cognitive policy is to go dark immediately.

Learning must therefore be measured under preserved or improved externally observed competence. It should also be tested over a neighbourhood of related inputs rather than one exact repeated trajectory.

For a neighbourhood `N(x)` around task `x`, a useful empirical criterion is:

$$
\mathbb{E}_{x' \sim N(x)}[D_{n+1}(x')]
<
\mathbb{E}_{x' \sim N(x)}[D_n(x')]
$$

subject to unchanged or improved externally observed performance.

If only one exact input becomes cheaper, the system may have cached or memorized a trajectory. If nearby problems also become cheaper while performance holds, the topology has formed reusable skill.

Skill acquisition should tend to produce:

$$
A_{\max}\downarrow,
\quad B(t)\downarrow,
\quad T\downarrow,
\quad D\downarrow
$$

with faster early quenching and greater recurrence along successful partial paths.

This need not be monotonic during acquisition. A system may temporarily become more expensive as it begins noticing distinctions that its earlier cheap pathway ignored. The relevant evidence is the eventual joint change in trace geometry, transfer across `N(x)`, and preserved external performance.

These are observational expectations, not direct reward targets.

Optimizing the organism to minimize `D`, `R`, entropy, or settling time would invite immediate Goodhart failure. It could learn to suppress activity rather than think efficiently. The metrics should be passive instrumentation conditioned on continued competence and contact with external consequences.

---

## Cognitive health and early degradation

The same traces can reveal degradation before task-level evaluations visibly fail.

If a previously cheap probe distribution begins producing:

- broader activation;
- longer settling time;
- rising `D`;
- rising `R`;
- rising activity entropy;
- repeated recruitment spikes;
- lower recurrence or fragmented established paths;

then the organism may be compensating for damage, incompatibility, interference, or cache/topology decay while still producing acceptable outputs.

This is analogous to an elevated resting heart rate: not a diagnosis, but evidence that maintaining competence has become metabolically more expensive.

The trace can therefore measure:

- difficulty;
- automatization;
- hesitation;
- consolidation;
- recovery;
- possible degradation.

It does so without asking the model to introspect or report whether it was uncertain.

---

## From correlation to causal cognitive anatomy

Recurring trace shapes can be discovered without assigning human cognitive labels beforehand.

However, correlation alone cannot show that illuminated tissue mattered. Controlled perturbations can test causal participation:

- replay matched probes with warm and cold physical residency;
- delay or suppress one active cluster;
- temporarily weaken a recurrent edge;
- force an alternate route;
- restore the original topology and verify recovery.

If suppressing a cluster changes the continuation or causes compensatory recruitment elsewhere, it played a causal role. If nothing changes, its activity may have been incidental or redundant.

The empirical chain becomes:

`stimulus -> metabolic trace -> topological change -> later behaviour`

with controlled intervention between stages.

This is a semantics-free cognitive science for Ninereeds. It does not claim to read the meaning of a latent state. It observes what the organism spends, where it spends it, what physical and topological history that expenditure leaves, and how that history changes later cognition.

Over time, temporary flashes should visibly condense into cognitive anatomy.

---

## Relationship to current Ninereeds experiments

Do not replace current planned experiments yet.

The existing thinking-loop work remains useful as a baseline.

Important comparison:

### Baseline

`core -> recurrent self-processing -> output`

### Mycelial experiment

`core -> dynamically selected micro-transformations -> convergence -> core -> output`

Control total compute where possible.

If dynamic external state transformations outperform repeated self-ticks, the thinking loop may represent only a primitive approximation of a more distributed mechanism.

---

## First experiments

### Experiment 1: Minimal useful state transformer

Freeze a trained Ninereeds.

Train an external module to receive and return its native latent state.

Determine whether the module can improve downstream task performance.

Shrink the module progressively.

Measure:

- parameter count;
- bytes transferred;
- FLOPs;
- latency;
- improvement over no transformation;
- improvement over one additional core tick.

Question:

**What is the smallest independently stored transformation that can measurably improve a Ninereeds thought?**

### Experiment 2: Self-loop versus sibling-loop

Compare:

`A -> A -> A -> A`

with:

`A -> B -> A -> B`

Begin with identical siblings.

Gradually allow B to diverge through additional learning.

Measure where cross-model cognition becomes:

- better;
- equivalent;
- harmful.

This also tests latent compatibility under divergent learning.

### Experiment 3: Parallel latent sampling

Give the same state to many tiny nodes.

Cluster resulting states.

Propagate the strongest surviving clusters.

Compare with serial recurrence under equal compute budgets.

### Experiment 4: Emergent clustering

Allow nodes to accumulate co-activation statistics.

Repeatedly co-active nodes become contiguous storage clusters.

Measure whether learned clustering improves:

- load latency;
- cache hit rate;
- reasoning latency;
- task performance.

### Experiment 5: Dynamic residency

Implement a fixed VRAM node arena.

Nodes live canonically in RAM.

Load and evict them according to synthetic graph activity.

Measure the real cost floor of node swapping before investing in learning algorithms.

Compare:

- independent packed-node gathers;
- fixed-size coactive pages;
- immutable stable-cluster files;
- a moving VRAM working set with forward and backward halos;
- synchronous loading versus speculative asynchronous prefetch.

Measure frontier starvation, cold bytes, page amplification, prefetch accuracy, and useful latent improvement per transferred byte.

### Experiment 6: Communication bandwidth

Quantize inter-node latent communication progressively.

Test:

- FP32;
- FP16/BF16;
- INT8;
- INT4;
- sparse activations;
- learned codebooks;
- extremely low-bandwidth state messages.

Question:

**How much information does one useful cognitive transition actually require?**

### Experiment 7: Population rollback

Allow one sibling to learn online.

Keep several controls unchanged.

Automatically detect regression using protected tests.

Discard the changed descendant if it regresses.

This tests whether population-level memory hygiene is practically simpler than model-level unlearning.

### Experiment 8: Metabolic trace and skill formation

Instrument a small dynamic network before assigning semantic interpretations to its activity.

Record per impulse:

- eligibility, activity, and residency by node;
- edge traversal and temporal order;
- `A(t)`, `B(t)`, `Q(t)`, `H(t)`, `R`, `K`, `T`, and `D`;
- compute, transfer, cold-load, and memory-pressure traces separately;
- path recurrence against prior successful trajectories;
- externally observed outcome quality.

Present families of related tasks repeatedly.

Test whether preserved competence is accompanied by:

- lower expected `D` across the task neighbourhood;
- narrower and shorter activity traces;
- earlier quenching;
- higher recurrence of useful partial trajectories;
- reduced cold-loading after controlling for cache state.

Then perform bounded causal interventions on frequently active clusters and paths. Compare behavioural change, compensatory recruitment, and recovery after restoration.

Question:

**Can the formation, reuse, failure, and degradation of skill be observed directly as changes in activation geometry without decoding latent semantics?**

### Experiment 9: Dream replay, consolidation, and write amplification

Record waking residual states and construct three replay distributions:

- faithful episodic replay;
- neighbourhood perturbation with missing and competing cues;
- high-temperature recombination across unrelated remembered fragments.

Compare whether each distribution produces:

- exact-trajectory memorization;
- lower-cost transfer across related task neighbourhoods;
- useful exception branches;
- harmful self-consistent attractors;
- changes in path recurrence and metabolic trace geometry.

In parallel, maintain a logical topology with stable IDs and compare physical layouts:

- no consolidation;
- eager coactivation-based rewriting;
- hysteretic immutable cluster formation with append-only overlays;
- stable-cluster files plus bounded background compaction;
- larger superclusters formed only when predicted savings exceed rewrite cost.

Measure:

- read and write amplification;
- frontier starvation;
- compaction debt;
- SSD bytes written per useful topology change;
- cluster lifetime and rewrite frequency;
- cache hit rate and thought latency;
- regression on protected waking probes;
- rollback correctness after rejected candidate layouts.

Questions:

**Does decontextualized replay produce more transferable pathways than exact episodic replay?**

**Can physical clustering reduce frontier starvation without causing a consolidation I/O cascade?**

### Experiment 10: Mesoscale latent experts and domain size curves

Freeze a trained Ninereeds checkpoint and capture a versioned latent interface.

Choose several candidate transformation families, including at least one narrow formal domain such as Python. Construct training and evaluation records from parent latent states, later continuations, corrections, and externally constrained outcomes.

Train residual experts across a geometric size sweep, for example:

- tens of thousands of parameters;
- hundreds of thousands;
- low millions;
- tens of millions;
- whatever larger control is needed to reveal saturation.

For each size, compare:

- parent alone;
- parent with one additional self-tick;
- parent with the latent expert;
- an expert trained only on predecessor outputs;
- an expert trained on the complete lineage and waking corrections;
- warm-resident and cold-loaded execution.

Measure:

- domain-task improvement;
- transfer across a held-out neighbourhood;
- regression outside the charter;
- residual magnitude and state compatibility;
- continued-learning capacity before interference;
- useful improvement per parameter and per byte loaded;
- latency and cache behaviour;
- successor fidelity at replacement;
- split-versus-grow economics when capacity is reached;
- compatibility after parent latent drift, with and without adapters.

Questions:

**What is the smallest latent expert that improves Ninereeds more than an equal-cost self-tick?**

**How many parameters does a useful Python transformation require when perception, language, and general knowledge remain in the parent?**

**When an expert saturates, is it better to enlarge it, split its domain, distill it, or train a successor from its lineage?**

---

## Open questions

- What exactly constitutes a transferable Ninereeds state?
- How stable is that representation across training?
- Can a compact latent expert improve the parent more than an equal-cost recurrent self-tick?
- Which parent state or layer provides the most durable expert interface?
- How should residual transformations be bounded without suppressing necessary change?
- How much parent-manifold drift can an adapter bridge before retraining becomes cheaper?
- How many parameters are required for different expert charters, including Python?
- What signals reliably distinguish expert saturation from insufficient training or poor routing?
- When should a saturated expert grow, split, distill, or be replaced?
- What minimum lineage must be preserved so a successor inherits experience without fossilizing errors?
- Can expert-specific continual learning remain isolated from unrelated parent capabilities?
- How small can a useful transformation node become?
- Does diversity among nodes improve reasoning or merely introduce noise?
- Can useful topology self-organize from simple activation and reinforcement rules?
- How should successful thought trajectories assign credit to individual nodes?
- How do we prevent highly active but harmful branches from reinforcing themselves?
- What local residual or compatibility signal should cause a branch to continue or quench?
- How should surprise thresholds adapt without producing either stale attractors or chronic overactivation?
- How does a later impulse propagate correction into the topology used by an earlier thought?
- How can internally generated Ninereeds steps add genuine constraint rather than merely echo an attractor?
- What degree of external permeability is sufficient to interrupt a warm but misleading path?
- Which activity geometries recur naturally before correction, tool use, insight, or failure?
- Can rising metabolic cost predict degradation before behavioural tests fail?
- How should temporal path recurrence be measured across graphs of different sizes?
- Which perturbations distinguish causal tissue from redundant or incidental illumination?
- How should waking residual states be selected for dream replay?
- What perturbation radius produces abstraction without destroying useful constraint?
- How should dream-learned topology remain provisional until waking validation?
- How can rare genuine exceptions survive pressure toward invariance?
- Can dream regimes emerge from residual distributions rather than predefined sleep phases?
- What is the minimum useful latent improvement per transferred byte?
- How much frontier starvation is tolerable before distributed cognition loses to monolithic recurrence?
- How should exploratory nodes be packed before they are stable enough to become cluster files?
- What traffic, stability, and dwell-time thresholds justify writing a stable cluster?
- How should cluster boundaries change without recursively rewriting neighbouring regions?
- What bounded write-amplification budget makes lifetime consolidation practical?
- When should stable cluster files become superclusters, distilled models, or fused kernels?
- How large can the stable-ID directory become while its active portion remains resident?
- Can "I don't know" emerge as an attractor?
- At what point should frequently co-active nodes become a permanent cluster?
- Can stable clusters be distilled without destroying useful topology?
- Can the network grow indefinitely while keeping evaluation and indexing tractable?
- What metadata does the system actually require?
- Does a learned librarian help, or does topology make most explicit routing unnecessary?
- How much dormant structure can realistically be indexed without making activation search itself expensive?
- Can approximate-nearest-neighbor lookup over node ingress signatures identify candidate branches cheaply?
- Can candidate-node retrieval itself become local and graph-driven so global search is rarely necessary?
- Can a node be smaller than one traditional Ninereeds layer?
- Can a useful node approach the conceptual scale of a single "macro-weight"?
- Is byte-level input relevant to the minimum granularity of cognition, or is the true minimum entirely latent?
- Is the resulting system better understood as a neural network, a population, an operating system, or something else entirely?

---

## Principle to preserve

Do not design semantic modules prematurely.

Do not create a node called "coding."

Do not create a node called "causality."

Do not impose a cortical map because brains have one.

Construct the smallest useful latent transformation.

Let activation determine connectivity.

Let repeated co-activation determine structure.

Let useful structure persist.

Let unused structure become cold.

Let thought determine what wakes.

Then observe what kind of organism grows.

---

## Short version

The hypothesis is that Ninereeds may not need a larger monolithic reasoning model.

A learned front core could emit a latent thought into a vast dormant population of microscopic state-transition nodes. The impulse excites nearby compatible topology, unresolved prediction error recruits additional tissue, inadequate continuations extinguish, and darkness propagates backward while a small number of trajectories survive. Repeatedly useful paths become warm, cheap, and structurally reinforced. Only the active graph occupies VRAM. The complete learned organism may be orders of magnitude larger than available accelerator memory because dormant cognition lives in RAM or storage.

A practical intermediate architecture is a swarm of compact latent experts. Each expert receives and returns Ninereeds states, speaks a versioned form of its parent's latent language, and omits duplicated sensory and expressive organs. Experts begin with narrow histories, learn through use in versioned descendants, and are enlarged, split, distilled, or replaced when they reach capacity. This provides modular continual learning and rollback even if microscopic cognitive nodes never become practical.

The size of a domain is empirical. "How many parameters is Python?" is answered by training experts across a size curve and comparing utility, transfer, interference, latency, and improvement per byte. Granularity is earned by measurement and can increase later.

Difficulty is not an intrinsic property of a task. It is the total cognitive tissue-time this organism spends on that task today. Skill is visible when related tasks preserve outcome quality while activating less tissue, settling faster, and reusing mature paths. These metabolic traces can be measured without decoding what the latent states mean.

During waking, the system accumulates prediction errors without rewriting its entire physical organism. During sleep, it replays and perturbs residual states, tests whether paths generalize outside their original episodes, and constructs candidate topology and storage layouts. Experimental nodes remain dynamically packed; sufficiently stable coactive structures become immutable contiguous cluster files. Logical IDs and bounded background compaction prevent one consolidation event from cascading into rewrites across the organism.

Storage capacity determines how much mind can exist. Memory bandwidth determines how much can be awake. Compute determines how quickly the awake part can change. The architecture succeeds only if learned cognitive locality becomes predictable physical locality quickly enough to keep the active frontier fed.

The instantiated "expert" is not selected beforehand.

It is the temporary network grown by the thought.

The long-term model is not one checkpoint.

It is the mycelium.
