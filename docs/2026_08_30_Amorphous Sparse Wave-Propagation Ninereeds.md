# Campaign 36C Scratchpad — Amorphous Sparse Wave-Propagation Ninereeds

**Status:** design exploration
**Purpose:** preserve the architectural decisions reached during the Campaign 36B/36C discussion before implementation choices harden them into code.

---

## 1. Why 36C exists

Campaign 36A and 36B expose two different scaling limits.

### 36A — fixed BDH

36A is a conventional fixed-capacity Ninereeds substrate.

Its advantage is BDH sparse activation.

Its limitation is fixed anatomy. At some point, continued learning has to fit inside the capacity that was allocated before training.

### 36B — growing residual-cell substrate

36B demonstrated something important:

- a decentralised cellular substrate can learn;
- real new parameter cohorts can be created during training;
- the organism can grow continuously;
- developmental state can be checkpointed and resumed.

However, 36B executes every admitted/provisional cell.

Therefore:

`more cells -> more compute for every thought`

36B can grow, but sufficiently successful growth eventually makes it computationally unusable.

It remains valuable as a growth experiment and baseline.

### 36C — intended architecture

36C combines growth with genuinely sparse local execution.

Its desired scaling law is:

`total capacity ~ lifetime tissue`

while:

`compute for thought X ~ tissue actually recruited by thought X`

A trivial problem should require very little computation even if the organism contains enormous amounts of knowledge.

A difficult or unfamiliar problem should recruit more tissue and therefore cost more.

Model size should no longer determine inference cost.

---

# 2. Central architectural principle

**The thought finds its own path.**

There is no semantic router deciding which expert or cell should execute.

Instead, latent state propagates locally through neighbouring tissue.

A cell receives the travelling state.

If its learned anatomy has a useful transformation for that state, it changes the state and propagates it onward.

If it has nowhere useful to send the state, it terminates.

Thus:

`receive -> transform -> propagate OR terminate`

A cell has only these two terminal behaviours:

- **PROPAGATE**
- **TERMINATE**

The cell does not know:

- whether the overall thought succeeded;
- whether it was the last useful cell;
- whether its local prediction was globally correct;
- whether the entire thought has finished;
- what semantic task is being solved.

Its responsibility is entirely local.

---

# 3. Wave propagation rather than routing

The network should behave like an excitable medium rather than an MoE.

A mature prediction should tend to follow one strong established path.

An immature prediction may activate several possible continuations.

A prediction error should cause broader local branching.

Completely irrelevant tissue should terminate the wave.

Conceptually:

```text
mature prediction
    -> one strong continuation

uncertain prediction
    -> several continuations

prediction error
    -> broader exploratory fan-out

irrelevant state
    -> terminate
```

Branching is not explicitly commanded.

It emerges because several neighbouring paths have sufficient learned conductance.

Repeated successful use should make paths increasingly easy to traverse.

The desired long-term tendency is:

`expensive reasoning -> learned prediction -> cheap propagation`

---

# 4. Compute scales with problem difficulty

36C should make “thinking harder” physically observable.

Example:

```text
"What is the capital of France?"
```

Once learned well:

```text
small frontier
short established trajectory
little/no branching
very low compute
```

A more constrained reasoning problem:

```text
"My car is dirty.
I live 100 m from a car wash.
Should I walk or drive?"
```

may require multiple interacting constraints and therefore:

```text
larger frontier
branching
constraint reconciliation
more propagation
higher compute
```

The system therefore does not allocate a fixed reasoning budget.

Difficulty manifests as the amount of tissue required before the wave settles.

As a problem becomes familiar, the same problem should become cheaper.

---

# 5. The cell

A cell is not a concept.

It does not represent:

- dog;
- Python;
- Japanese grammar;
- D&D lore;
- planning;
- arithmetic.

Those names may be useful retrospective descriptions for humans but must not be part of the architecture.

A cell is a small learned transformation embedded in a traffic geography.

Its identity is primarily behavioural:

- what latent states usually engage it;
- how those states normally arrive;
- how it transforms them;
- where transformed states usually propagate;
- how stable those relationships have become.

---

# 6. Cell “DNA”

DNA is the persistent learned anatomy of a cell.

Exact implementation remains experimental, but it may contain:

```text
stable UID
content receptivity
latent transformation
neighbour relationships
outgoing conductances
route expectations
plasticity / rigidity
usage history
metabolic state
merge/fission ancestry
```

The DNA is not episodic memory.

A cell “remembers” only insofar as experience has altered its trained behaviour.

---

# 7. Thought “RNA”

RNA is the transient state carried by one travelling thought.

Possible contents:

```text
latent state
signal amplitude
immediate predecessor UID(s)
bounded recent-route provenance
other transient propagation state
```

RNA exists only while the thought wave passes.

The key addition is **short provenance**.

A cell may need to know not merely:

> What latent state reached me?

but also:

> How did it reach me?

---

# 8. Provenance as cognitive evidence

Provenance is not required for thought-completion bookkeeping.

It is useful to the cells themselves.

A cell can compare:

### Content familiarity

How similar is this latent state to states I normally transform?

### Route familiarity

How similar is the recent path to routes through which relevant states normally reach me?

This allows an important distinction.

### Strange content, familiar route

The state is unusual, but it arrived through a route normally associated with this tissue.

Interpretation:

```text
this may concern me,
but my established prediction is failing
```

Result:

```text
explore / fan out
```

### Strange content, strange route

Neither the content nor the route resembles this cell's normal traffic.

Interpretation:

```text
this probably has nothing to do with me
```

Result:

```text
terminate
```

### Familiar content, familiar route

Strong established prediction.

Result:

```text
narrow propagation
possibly one child
```

### Familiar content, unusual route

Potentially relevant but less settled.

Result:

```text
respond cautiously
possibly broaden propagation
```

Route familiarity must remain evidence rather than an absolute veto.

Rare useful routes must still have some opportunity to establish themselves.

---

# 9. Momentum / path history

Bounded route provenance provides a form of computational momentum.

A cell does not need to know the global task.

It merely receives evidence that:

```text
states travelling through this kind of neighbourhood
usually continue through me in a particular way
```

Recent trajectory therefore helps predict the next continuation.

A short exact UID tail should be used initially because it is interpretable.

Possible later replacement:

- rolling route embedding;
- fixed-size provenance sketch;
- learned route state.

Do not optimise this prematurely.

---

# 10. Immediate reversal is forbidden

When a cell receives a wave from a predecessor, it must not immediately send the wave back to that predecessor.

Example:

```text
Hans -> Bob
```

Bob may propagate to:

```text
Jim
Jane
Sue
...
```

but not directly back to Hans during that propagation.

This prevents trivial ping-pong.

It does **not** prohibit meaningful later recurrence:

```text
Hans -> Bob -> Jim -> Sue -> Hans
```

The state reaching Hans later may have changed substantially.

Longer cycles are therefore allowed.

---

# 11. Recurrent paths and settlement

A thought may loop through a cell again after that cell has completed its previous local responsibility.

Example:

```text
Tom -> Bob -> Jim -> Jane -> Bob
```

Bob's earlier participation ended when Bob propagated to Jim.

When the transformed thought later returns from Jane, Bob can participate again.

No permanent branch object is required.

Useful recurrence should remain possible.

Pathological endless oscillation may eventually require local physical safeguards such as:

- attenuation;
- refractoriness;
- diminishing transformation thresholds;
- metabolic limits.

These should not become semantic routing mechanisms.

---

# 12. Merging wavefronts

Multiple incoming paths may converge on the same cell.

This is potentially a computational feature, not merely an engineering problem.

Signals can interact at a cell.

Two weak trajectories may jointly make a continuation conductive.

One incoming state may suppress or alter another.

The cell still performs one local computation on the combined state.

The architecture should therefore allow convergence rather than modelling every path as an isolated search branch.

---

# 13. No branch identity

Branches do not need persistent IDs.

Branches are not objects.

They are temporary visible consequences of signal propagation.

The network contains:

- cells with stable UIDs;
- transient propagation between those cells.

A “branch” exists only from an observer's perspective.

---

# 14. Mapper

The system does require one simple central bookkeeping mechanism:

**the mapper**

The mapper does not route thought.

It does not interpret latent state.

It does not choose promising cells.

It does not determine correctness.

Its only important question is:

> Is any part of the current thought still alive?

The mapper maintains a set/table of UIDs currently holding an unresolved propagation obligation.

Conceptually:

```text
pending = {UIDs}
```

When a cell receives the thought:

```text
add UID
```

When that cell propagates:

```text
remove UID
responsibility transfers to receiving children
```

When that cell terminates:

```text
remove UID
```

Thought is finished when:

```text
pending == empty
```

This gives the system a single boolean:

```text
ready_for_next_turn = mapper_is_empty
```

A second thought cannot begin while the first one is still active.

---

# 15. Atomic responsibility transfer

Propagation must not create a temporary false-empty mapper.

Bad sequence:

```text
Bob removed
mapper becomes empty
system declares completion
Jim receipt arrives afterward
```

Responsibility therefore needs transactional transfer.

Possible implementation:

```text
Bob -> {Jim, Jane}
```

becomes one logical mapper update:

```text
remove Bob
add Jim
add Jane
```

or Bob remains pending until downstream receipt is confirmed.

This is infrastructure bookkeeping only.

It must not influence the cognitive path.

---

# 16. What the last termination means

The final UID to terminate is not necessarily:

- the correct answer;
- the winning branch;
- the most important cell;
- the most confident prediction.

It only means:

**this was the last active propagation obligation.**

When it terminates:

```text
mapper becomes empty
```

The wave has reached quiescence.

The settled latent state is the current prediction.

Correctness remains external.

---

# 17. Confidence is not truth

A prediction can be extremely rigid and still be wrong.

Example:

Ninereeds has observed 1,233 white swans.

Its current prediction is strongly:

```text
swan -> white
```

This is a high-confidence prediction model.

Then it observes a black swan.

The correct response is not global recomputation.

Only the implicated predictive structure needs updating.

The system learns:

```text
swan colour is variable
white remains strongly expected
black is now a demonstrated possibility
```

Prediction error changes rigidity and opens alternatives.

Confidence therefore describes internal predictive stability, not objective truth.

---

# 18. Hallucination as internal exploration

36C is not intended to eliminate hallucination-like dynamics.

Generating plausible alternatives is useful.

When a prediction is weak:

```text
wave fans out
multiple continuations are explored
```

That behaviour supports:

- reasoning;
- hypothesis generation;
- creativity;
- debugging;
- analogy;
- uncertainty resolution.

The problem is not internal speculation.

The problem is expressing unresolved speculation as settled fact.

36C should make uncertainty physically observable.

---

# 19. Verbose diagnostic mode

Ordinary operation should retain minimal bookkeeping.

A verbose mode may log every propagation event.

Possible telemetry:

```text
cell received
predecessor
bounded provenance
latent-change magnitude
signal amplitude
children
termination
branching factor
cold/warm/hot load
latency
prediction residual
birth
metabolism
merge
fission
```

This permits reconstruction of the travelling wave after the fact.

Verbose mode provides a different kind of interpretability.

The question is not:

> What did cell 19382 mean?

The useful questions are:

- How much tissue activated?
- How widely did the thought fan out?
- How deeply did it propagate?
- Where did it repeatedly encounter prediction errors?
- Did it converge quickly?
- Did it need cold tissue?
- Did a supposedly familiar task require broad exploration?

Large diffuse activation is evidence that the model's internal prediction was not yet rigid.

It is not evidence that the answer was false.

---

# 20. Epistemic humility

Internal propagation difficulty can later train the expression system to distinguish:

```text
settled prediction
uncertain prediction
poorly resolved prediction
```

If the system struggled broadly but verbalizes the result with unjustified certainty, that is an epistemic-calibration failure.

The desired behaviour is eventually:

```text
stable narrow wave
    -> answer directly

moderate uncertainty
    -> qualify answer

large unresolved propagation
    -> acknowledge uncertainty
    -> ask for help / seek evidence / use tool
```

“Knowing that I do not know” should emerge from internal dynamics, not merely from a canned language behaviour.

---

# 21. Hebbian neighbour learning

Cells are trained by the tissue around them.

A cell receives states shaped by its neighbours.

It propagates transformed states toward other neighbours.

Repeated useful interaction strengthens the path.

Conceptually:

```text
Bob activity
x
Jim activity
x
later prediction-error / success modulation
```

Repeated successful:

```text
Bob -> Jim
```

traffic should make that continuation increasingly conductive.

Prediction error should reopen or weaken recently implicated pathways.

This can eventually produce neighbour-local learning.

For early experiments, global backpropagation may remain as scaffolding so propagation mechanics can be isolated from the separate credit-assignment problem.

---

# 22. Cell birth

When existing tissue cannot absorb persistent prediction error, more local capacity can be created.

A new cell should be added near the unresolved neighbourhood.

The newborn is initially undifferentiated.

Its neighbours determine:

- what states reach it;
- what transformations become useful;
- which downstream relationships strengthen.

This resembles differentiation:

```text
birth
-> local exposure
-> useful transformation
-> repeated successful participation
-> specialization
```

No semantic role is assigned.

---

# 23. Metabolism

Cells that cease to contribute for sufficiently long periods can eventually be metabolised.

Metabolism means real deletion and resource reclamation.

No global graph-cleanup pass is required.

When a cell disappears:

- its UID stops appearing in live traffic;
- neighbouring route expectations involving that UID receive no further reinforcement;
- those expectations gradually decay;
- traffic reorganises naturally.

If another cell attempts to propagate toward a dead UID, that route simply behaves as unavailable / effectively infinite resistance.

Prediction error can then drive alternative propagation.

If the missing capability becomes important enough again, new tissue can grow.

Thus forgetting is normal.

Knowledge that has no continuing relevance need not occupy computational tissue forever.

---

# 24. UID rules

Stable UIDs are important because they define learned traffic geography.

Rules:

- every newborn gets a fresh UID;
- UIDs should never be recycled for unrelated tissue;
- metabolised UIDs remain permanently dead/tombstoned;
- morphology may create aliases through fusion;
- provenance can therefore remain meaningful across storage movement and anatomical change.

---

# 25. Rigidity

Rigidity measures how stable a cell/connection has become under repeated successful prediction.

Rigidity should exist on a scale.

Repeated traffic without prediction error increases rigidity.

Prediction error decreases rigidity and restores plasticity.

The exact unit may be:

- cell rigidity;
- edge rigidity;
- pairwise rigidity;
- some combination.

The relationship between neighbouring cells is especially important.

---

# 26. Fusion / consolidation

When two neighbouring cells have sufficiently strong and sufficiently rigid interaction, they can merge.

Example:

```text
Jim + Bob
-> JimBob
```

Later:

```text
Dan + Harry
-> DanHarry
```

Then:

```text
JimBob + DanHarry
-> JimBobDanHarry
```

Fusion happens one local step at a time.

The criterion is not semantic similarity.

It is repeated stable traffic compatibility.

A fused cell represents a region whose internal boundary has become computationally unnecessary.

This should reduce:

- propagation boundaries;
- scheduling overhead;
- memory loads;
- latency.

Stable knowledge therefore compresses itself.

---

# 27. Emergent experts

Repeated fusion will naturally create increasingly large stable cells/clusters.

These are emergent experts.

They are not predefined.

They do not need labels.

A stable Japanese grammar region may gradually coalesce because its traffic repeatedly follows compatible paths.

A D&D lore region may separately coalesce.

Their provenance, state distributions and downstream traffic differ, so they will normally not fuse.

Expert boundaries therefore emerge from traffic.

A cross-domain problem can still create bridges.

Example:

```text
Japanese translation of D&D material
```

may repeatedly activate both domains and eventually establish useful connecting tissue without requiring the entire domains to merge.

---

# 28. Experts are reversible

Fusion is not permanent.

If enough prediction errors accumulate inside a fused structure, rigidity falls.

At some threshold, the fused cell can split into finer constituent tissue.

Conceptually:

```text
stable predictions
-> rigidity
-> fusion
-> cheap expert
```

then:

```text
world changes
-> prediction errors
-> rigidity falls
-> fission
-> local plasticity
-> relearning
```

Once the new situation stabilises, cells may consolidate again.

36C therefore moves toward the coarsest computational granularity that current experience permits.

---

# 29. Reversible UID fusion

Fusion must preserve route continuity.

Proposed scheme:

- fused cell receives one canonical active UID;
- constituent UIDs remain as local entry-port aliases;
- routes targeting any constituent alias resolve to the canonical fused cell;
- mapper deduplicates aliases into one active UID;
- constituent entry ports may retain directional/provenance significance;
- if the fused cell later splits, constituent UIDs become independently active again.

Example:

```text
Bob UID -> alias of JimBob
Jim UID -> alias of JimBob

JimBob canonical UID -> active identity
```

After fission:

```text
Bob UID -> independently active again
Jim UID -> independently active again
```

No global route rewrite is required.

---

# 30. Morphology as evidence

The anatomy does not make semantic claims.

However, it provides evidence about learning history.

Possible interpretation:

```text
many small weakly connected cells
    -> immature / changing / exploratory region

stable pathways
    -> increasing predictive confidence

large fused cluster
    -> long period of stable prediction and repeated use

frequent fission
    -> changing or poorly modelled domain

little traffic
    -> declining relevance

metabolism
    -> relevance remained too low to justify retention
```

A large rigid cluster therefore does not mean:

> Ninereeds knows topic X.

It means:

> this region has experienced enough stable successful traffic that its internal boundaries ceased to provide useful plasticity.

That is evidence of coherence.

---

# 31. Homeostasis

The mature organism should not merely grow forever.

Four opposing processes create homeostasis:

```text
insufficient capacity -> grow

stable repeated prediction -> fuse

prediction error -> reopen / split

persistent irrelevance -> metabolise
```

Therefore the organism continuously adjusts both:

- how much tissue exists;
- the granularity at which that tissue computes.

A mature Ninereeds may contain:

- large rigid stable domains;
- medium reusable structures;
- small highly plastic frontier tissue;
- cold/dormant regions;
- newly differentiating cells.

---

# 32. Hot / warm / cool / cold residency

Logical cognition and physical storage remain separate.

Possible residency hierarchy:

```text
hot
    currently active, VRAM

warm
    likely near future / recently active

cool
    RAM

cold
    SSD

dormant / retired
    preserved but very unlikely to activate
```

The active thought frontier determines what needs to be materialised.

Likely neighbouring tissue can be prefetched.

The total organism can therefore be much larger than VRAM.

Per-thought VRAM use depends on the current problem rather than total parameter count.

---

# 33. Cognitive graph vs storage graph

These must remain distinct.

### Cognitive graph

Where latent state can propagate.

### Storage graph

Which cells are physically colocated to reduce I/O.

Repeated coactivation can gradually cause cells to be packed together physically.

This reduces:

- cold loads;
- RAM/VRAM transfers;
- thought latency.

But physical colocation must never determine semantic routing.

Storage serves cognition.

It does not choose cognition.

---

# 34. Dynamic model size

A single parameter-count number becomes increasingly meaningless.

Useful measurements include:

```text
total cells
total stored parameters
hot cells
warm cells
cold cells
active cells per thought
active cell-time
propagation depth
branching factor
cold-load count
VRAM used this thought
RAM used this thought
birth rate
metabolism rate
fusion rate
fission rate
prediction-error traffic
```

The organism may grow in stored capacity while ordinary thoughts become progressively cheaper.

---

# 35. Why 36C does not need predefined experts

36C can theoretically continue acquiring skills as long as storage can hold additional tissue.

It does not need to allocate a fixed expert taxonomy.

If something becomes relevant enough:

```text
learn
grow if necessary
stabilise
consolidate
```

If it becomes irrelevant:

```text
cool
dormant
metabolise
```

External experts may still be useful as tools for economic or capability reasons, but they are not required because the core has reached a predetermined capacity limit.

---

# 36. Reasoning distillation

Reasoning should be taught after the knowledge curriculum has created enough world structure for meaningful propagation.

A strong reasoning teacher such as DeepSeek can then teach not merely answers but useful reasoning dynamics:

- when the first plausible continuation is insufficient;
- when constraints conflict;
- when to propagate further;
- when uncertainty warrants exploration;
- when assumptions should be revisited;
- when external information is required;
- when the system should say that it does not know.

The long-term ideal is latent-state reasoning distillation rather than mere verbal imitation.

Knowledge constructs the terrain.

Reasoning education teaches the organism how to move through it.

---

# 37. Experimental sequence

Do not implement every mechanism simultaneously.

Suggested progression:

### 36C-0 — wave substrate

Test:

- local neighbour propagation;
- propagation vs termination;
- mapper completion;
- short provenance;
- no-immediate-reversal;
- controlled fan-out;
- convergence;
- real sparse execution.

Use backpropagation initially if necessary.

### 36C-1 — growth

Add:

- prediction-error-driven cell birth;
- local differentiation;
- selective admission if still necessary.

### 36C-2 — local learning

Replace or augment global backprop with neighbour-local / Hebbian plasticity.

### 36C-3 — residency

Add:

- hot/warm/cool/cold hierarchy;
- prefetching;
- dynamic locality packing;
- cold-load telemetry.

### 36C-4 — metabolism

Add:

- dormancy;
- senescence;
- cell deletion;
- capacity recycling;
- natural route-memory decay.

### 36C-5 — rigidity and morphology

Add:

- rigidity measurement;
- fusion;
- canonical UID + alias handling;
- fission after prediction error;
- recursive consolidation into emergent experts.

### Later — reasoning education

After the knowledge curriculum:

- reasoning distillation;
- epistemic calibration;
- tool-use decisions grounded in internal uncertainty.

---

# 38. Core invariants to protect

Several ideas should remain architectural invariants unless experiments falsify them:

1. **No semantic router.**
2. **Thought propagates locally through neighbours.**
3. **Cells only propagate or terminate.**
4. **Cells do not know global correctness.**
5. **The mapper only knows whether thought is still alive.**
6. **Recent provenance may influence cognition; it does not control completion.**
7. **Immediate edge reversal is forbidden.**
8. **Compute follows active tissue, not total organism size.**
9. **Prediction error increases exploration/plasticity.**
10. **Stable prediction creates rigidity and eventually consolidation.**
11. **Persistent irrelevance permits metabolism.**
12. **Fusion must be reversible.**
13. **UID continuity must survive morphology and storage movement.**
14. **Storage topology must not become cognitive routing.**
15. **Semantics should not be assigned to individual cells or clusters.**

---

# 39. Central hypothesis

Campaign 36C asks whether cognition can emerge from a continuously changing population of tiny learned transformations through which latent state propagates as a wave.

The organism does not search a fixed expert set.

It does not activate its entire parameter body.

It does not require globally named concepts.

Instead:

```text
thought enters
-> local tissue responds
-> confident predictions propagate narrowly
-> uncertainty fans outward
-> irrelevant tissue terminates
-> useful paths strengthen
-> stable paths consolidate
-> errors reopen them
-> insufficient regions grow
-> irrelevant regions are metabolised
-> thought ends when no active UID remains
```

Over time, experience changes both the topology and granularity of the organism.

Stable domains naturally form large efficient experts.

Changing domains become fine-grained and plastic again.

Unused knowledge disappears.

The system trends toward homeostasis rather than fixed size.

The fundamental desired scaling law is:

> **knowledge determines how much organism exists; difficulty determines how much organism thinks.**
