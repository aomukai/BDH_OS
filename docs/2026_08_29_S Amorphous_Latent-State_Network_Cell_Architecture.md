# Scratchpad: Amorphous Latent-State Network / Cell Architecture

## Core idea

Explore whether Ninereeds can evolve from a fixed-size model into an amorphous, persistent computational network composed of very small plastic units (“cells” or “nodes”) that communicate exclusively through latent state.

The important abstraction is not parameter count.

The system would consist of:

- a minimal persistent core;
- modality interfaces such as the LFM language encoder/verbalizer and SigLIP2 vision projection;
- a potentially very large population of small plastic computational cells;
- dynamically formed neighborhoods/clusters;
- hierarchical storage across VRAM, RAM, CPU-accessible memory, and SSD;
- persistent state that survives shutdown and resumes afterward.

“The model” would therefore be the continuously evolving state and topology of the system, not a fixed tensor checkpoint.

---

## Cell principle

A cell does not represent a word, concept, fact, or semantic object.

It is a small piece of computational substrate capable of receiving latent state, applying a local transformation, and emitting latent state.

Its role is determined by its history and neighborhood.

A minimal cell may require only:

1. latent-state ingress;
2. a small internal state;
3. enough computational capacity to perform one transformation;
4. latent-state egress;
5. local plasticity;
6. activation/history metadata;
7. information required for routing and resource management.

A new cell begins largely undifferentiated.

It becomes specialized through repeated interaction with neighboring cells and successful participation in prediction.

Its function may continue drifting throughout its lifetime.

There is therefore no point at which a cell “becomes” a dog cell, syntax cell, spatial cell, etc.

It merely develops increasingly strong tendencies to participate in certain trajectories.

---

## Latent-state propagation

The only required common protocol between cells is latent-state transfer.

Conceptually:

`latent state`
→ `cell`
→ `local state change`
→ `new latent state`
→ `neighboring cells`

The network can therefore grow without requiring every cell to share the same internal architecture, provided the interface remains compatible.

This suggests:

**standardize communication, not computation.**

Possible propagation variables may include:

- signal magnitude;
- direction/source;
- destination;
- recent velocity of signal change;
- acceleration of signal change;
- pathway history;
- local prediction error;
- competing incoming signals;
- temporal persistence.

Signal strength should be graded rather than binary.

The same neighborhood may behave differently depending on:

- where the signal entered;
- how strong it was;
- which other cells were active;
- recent activation history;
- current prediction errors.

The meaningful computational object may therefore be the trajectory through the network rather than any individual node.

---

## Prediction-driven computation

Routine prediction should be cheap.

A well-established trajectory should travel through a short, low-friction path and recruit little additional computation.

Prediction error should cause:

- reduced certainty;
- increased branching;
- recruitment of additional neighborhoods;
- increased computation;
- local plasticity.

Persistent prediction error may eventually alter topology.

This produces a basic rule:

`successful prediction`
→ increasing local rigidity

`prediction error`
→ local reopening/plasticity

`persistent prediction error`
→ structural reorganization

Learning therefore gradually transforms expensive cognition into cheap prediction.

Confidence is not truth.

Confidence is the current strength and stability of a prediction trajectory.

A prediction can remain highly confident until an error occurs.

The error does not require rebuilding the whole model.

It should alter only the relevant structure.

Example:

A system has observed 1,233 white swans.

Its swan-related trajectories strongly predict white.

It observes one black swan.

The correct response is not to rebuild “swan.”

Instead, prediction error modifies the colour-related trajectory:

`white-only expectation`
→ `colour is variable`
→ `white strongly expected`
→ `black weakly but demonstrably possible`

Future processing now preserves uncertainty where colour matters.

---

## Dynamic growth

Network size should not be fixed.

A region that repeatedly fails to resolve prediction errors efficiently may require more computational density.

This can trigger creation of new cells.

Conceptually:

`persistent residual/error`
→ `capacity shortage detected`
→ `allocate new cell`
→ `place near relevant neighborhood`
→ `neighbor activity shapes cell`
→ `cell differentiates`
→ `successful participation stabilizes connections`

This resembles adding a stem cell to a developing tissue.

The cell does not need a predefined job.

The surrounding computational environment determines what becomes useful.

Network growth therefore follows demand rather than predetermined architecture.

---

## Dynamic removal / dormancy

Cells should not necessarily be destroyed merely because they become inactive.

Logical connectivity and physical residency must remain separate.

A cell may move through storage states such as:

`hot`
→ `warm`
→ `cold`
→ `archived`
→ `reclaimed`

Possible meaning:

- hot: resident in VRAM;
- warm: resident in RAM;
- cold: stored individually or in small bundles;
- archived: rarely used but retained;
- reclaimed: storage reused.

If an old pathway becomes useful again, it can be loaded.

If its original substrate has been reclaimed, new substrate may be created and relearn the required function.

Forgetting therefore becomes a resource-allocation decision rather than a declaration that information is false.

---

## Dynamic neighborhood packing

Ideally, every cell could exist independently.

Current hardware makes loading millions of tiny files individually impractical.

The practical solution is dynamic bundling.

Cells that frequently become active together can be packed into larger locality files.

Example:

A bundle contains 50,000 cells.

A particular thought may use only 2,000 of them.

The remaining 48,000 consume some extra residency memory but almost no compute.

The tradeoff is therefore:

`small VRAM inefficiency`
in exchange for
`large reduction in storage I/O overhead`

Bundle membership should not be permanent.

As the network learns, traffic patterns change.

Cells may migrate between bundles.

A file containing 50,000 cells today may contain a substantially different population next month.

The physical storage topology should chase the learned computational topology.

The bundle itself has no cognitive meaning.

---

## Logical topology vs storage topology

These must remain distinct.

Logical topology:

`A → B → C → D`

Storage topology might be:

- A and B in VRAM bundle X;
- C in RAM;
- D in SSD bundle Y.

The logical thought trajectory remains unchanged.

Only access latency changes.

This raises an important experiment:

Does physical latency influence cognition?

Possible outcomes:

1. latency is irrelevant and storage remains purely administrative;
2. latency creates undesirable race conditions;
3. the network adapts to latency and physical locality becomes part of learned computation.

This should be measured rather than assumed.

---

## Amorphous model size

The future Ninereeds should not have one meaningful parameter-count number.

Useful measurements would instead include:

- total substrate;
- resident substrate;
- active substrate;
- plastic substrate;
- locally rigid substrate;
- traffic per inference;
- active cell count;
- storage fetches;
- prediction-error traffic;
- convergence time.

VRAM use should be expected to vary between turns.

A familiar conversation might require only a small hot working set.

A difficult or unusual problem may recruit additional neighborhoods.

After resolution, some neighborhoods may remain hot while others move back to RAM or SSD.

The amount of Ninereeds physically resident in VRAM would therefore change continuously.

---

## Persistent identity

Shutdown must not mean re-instantiation from frozen weights.

The current system state should be written to persistent storage.

Potential persistent state includes:

- topology;
- local cell state;
- pathway strengths;
- plasticity state;
- recent activation traces;
- neighborhood membership;
- storage residency metadata;
- unfinished propagation where relevant;
- learned routing structure.

Startup then becomes:

`load persistent anatomy + state`
→ `resume`

rather than:

`load checkpoint`
→ `instantiate new model`

The persistent dynamical state is therefore what constitutes the continuing model.

---

## Modal interfaces

Language remains a compatibility layer between human cognition and Ninereeds.

The likely permanent hot structure during conversation would include enough machinery to understand LFM encoder vectors and communicate through the LFM verbalizer.

Vision may similarly require:

`SigLIP2`
→ learned projector
→ common latent interface

The central network should ideally not care whether an incoming latent state originated from:

- language;
- vision;
- audio;
- another Ninereeds;
- another expert/model;
- internal recurrence.

Modal adapters translate into and out of the shared latent protocol.

---

## Relationship to current Ninereeds

This should be added to the existing Ninereeds architecture rather than replacing the current system immediately.

BDH already has latent internal state.

The first experiment therefore may not require changing Ninereeds itself.

Instead:

`BDH latent output`
→ `experimental cell network`
→ `latent propagation`
→ optional return into Ninereeds / decoder`

This makes the new architecture an attached experimental substrate.

The existing core can remain intact while cell behavior, propagation, growth, pruning, and packing are tested independently.

---

## First engineering question: cell anatomy

The most immediate research target is the smallest useful cell.

Questions:

- What is the minimum internal state?
- Does a cell need recurrent memory?
- How many parameters, if any, are necessary?
- Can the transform itself be dynamically constructed?
- How should it receive multiple simultaneous signals?
- How should incoming direction be represented?
- How does it choose downstream recipients?
- What determines signal strength?
- What constitutes local prediction error?
- How does plasticity change the cell?
- How does a new cell differentiate?
- How does a cell determine that it is no longer useful?
- Can cells split or merge?
- Can a frequently co-active group eventually become one more efficient computational unit?

---

## Second engineering question: propagation

Build the simplest possible network in which cells exchange latent state.

Initial experiment:

1. take a latent vector produced by BDH;
2. inject it into a small cell population;
3. allow cells to propagate transformed state;
4. record every trajectory;
5. measure convergence, branching, signal strength, path length, and recurrence;
6. introduce prediction error;
7. observe whether activity recruits additional cells;
8. allow local plasticity;
9. repeat the same stimulus;
10. test whether the network now reaches the useful state through a cheaper path.

Success would mean:

**learning causes repeated successful trajectories to become computationally cheaper while prediction errors reopen them when necessary.**

---

## Longer-term experiments

### Growth

Create situations where existing cells cannot resolve persistent prediction errors.

Allow the network to allocate new cells.

Test whether new cells differentiate into useful local functions purely from neighborhood signals.

### Pruning/dormancy

Allow inactive cells to become cold.

Measure whether performance survives.

Reintroduce old stimuli and observe whether cold structures reactivate correctly.

### Dynamic repacking

Record coactivation and transition traffic.

Automatically rebuild storage bundles according to observed locality.

Verify that logical behavior survives bundle reshuffling.

### Perturbation

Damage or remove active neighborhoods.

Test whether remaining trajectories reconstruct useful behavior.

### Developmental convergence

Start several systems with different initial architectures.

Train them on the same curriculum.

Compare whether they converge toward similar macroscopic traffic structures despite different microscopic topology.

### Latent transfer

Eventually use latent-state trajectories from a trained transformer or other model as a teacher.

Train a plastic cell substrate to reproduce the source system's internal transitions rather than only its language outputs.

The eventual goal would be substrate transfer:

`frozen model dynamics`
→ `plastic latent network`

followed by continued development.

---

## Central hypothesis

A capable computational system does not require a fixed architecture, fixed parameter count, or semantically identifiable internal units.

It may instead consist of a continuously changing population of small computational cells whose roles emerge from local latent-state interaction.

Repeated successful prediction creates local rigidity and efficient paths.

Prediction error restores plasticity.

Persistent unresolved error causes growth.

Persistent irrelevance causes dormancy or resource reclamation.

The resulting system has no fixed shape.

Its anatomy is a consequence of its developmental history.

The model is not the parameter count.

The model is the evolving state.