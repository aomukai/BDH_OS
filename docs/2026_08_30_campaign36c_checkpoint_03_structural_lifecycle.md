# Campaign 36C Checkpoint 03: Structural Lifecycle

**Date:** 2026-08-30
**Status:** Design checkpoint; lifecycle semantics are settled, thresholds and storage layout remain experimental
**Depends on:** Checkpoint 01 — Cell and Thought Lifecycle; Checkpoint 02 — Patch Algebra and Delayed Credit
**Scope:** Reversible packing, rigidity-limited fusion and fission, diagnostic repair, capacity growth, senescence, quarantine, revival, and deliberate metabolism

## 1. Structural constitution

Campaign 36C must be able to change its structure without treating every novelty as a reason to grow, every disagreement as a reason to split, every co-activation as semantic identity, or every quiet period as permission to erase knowledge.

The governing lifecycle is:

```text
recurring coherent capacity failure -> grow or bud
repeated useful co-access             -> pack
repeated functional equivalence       -> semantic fusion candidate
composite prediction error            -> unpack and diagnose
persistent conditional interference   -> fission while separable; otherwise repair or bud
successful repair                      -> update and possibly repack
loss of rooted participation           -> senescence
deliberate hygiene                      -> quarantine
storage pressure or explicit decision  -> purge
recurring need                          -> revive before growing anew
```

The central rule is:

> Error opens a separable assembly. Persistent interference divides it only while an extractable seam remains; a healed rigid cell must instead be repaired, supplemented, or replaced.

And for removal:

> Senescence is automatic and local. Death is deliberate and organism-wide.

## 2. Structural action selector

The same prediction error can justify very different actions. Structural plasticity must first identify the kind of failure.

| Observed condition | Preferred response |
| --- | --- |
| One weak or unresolved novelty event | Return unresolved; seed a dossier if warranted |
| Existing cell can absorb a compatible correction without regression | Update the cell |
| A measurement or evidence source is faulty | Recalibrate or quarantine the source; mark dependants stale |
| Components remain useful but their combination failed | Unpack and repair the interaction |
| Same components must cooperate differently under different conditions | Create condition-scoped assembly recipes |
| Separable cell or young fusion contains supported regimes that damage each other | Fission into specialists |
| Mature healed fusion contains supported regimes that damage each other | Update the larger cell or bud a routed specialist |
| Compatible new knowledge is coherent but does not fit available local capacity | Bud an adjunct cell |
| Coherent residual has no existing owner | Grow a frontier cell |
| Cells repeatedly perform the same addressed effect | Consider semantic fusion |
| Complementary cells are repeatedly loaded and used together | Pack them for access and I/O efficiency |
| Cell has lost rooted participation | Mark senescent |
| Cell remains unreachable after deliberate tracing | Quarantine |
| Quarantined state is no longer worth its storage | Purge |

Structural action follows delayed, typed evidence. Mere activation does not authorise structural mutation.

## 3. Canonical identity, inherited addresses, residency, and storage are separate

Every independently created cell receives one UID. A merge of `N` cells creates one new canonical UID for the combined cell while retaining the `N` predecessor UIDs as inbound aliases. The merged cell is therefore addressable under `N + 1` UIDs but identifies itself under the new canonical UID for outgoing traffic.

There is no incarnation number and no identity tied to a physical tensor slot.

The following concerns must not be conflated:

- **canonical identity:** the UID emitted by the current cell;
- **inbound aliases:** predecessor UIDs that resolve to the current merged cell;
- **routability:** whether the active topology can select or reach the cell;
- **residency:** whether the sparse loader currently has the cell in VRAM or RAM;
- **storage:** whether the cell exists in active storage, quarantine, or has been deleted;
- **packing:** which other cell records are physically co-loaded with it.

Campaign 36C is a sparse-activation BDH system. All cells are never expected to reside in VRAM simultaneously. Quarantine therefore does not exist to free a dense live tensor slot. It removes a cell from active routing and allows later disk reclamation. VRAM residency remains an independent cache and sparse-execution concern.

If a UID is purged, it is retired and not reused. A restored cell returns under the same UID. Alias mappings remain valid for as long as their successor exists or a rollback/fission transaction explicitly redirects them.

## 4. Co-activation is not semantic identity

Repeated co-firing proves that cells often participate in one useful organ or workflow. It does not by itself prove that they know the same thing.

For example:

- Bob contributes colour;
- Sabine contributes size;
- Billy contributes movement;
- Tom integrates these effects into a classification.

Their repeated cooperation supports physical packing as `BillySabineTomBob`, but their functions are complementary rather than equivalent.

Two distinct operations are therefore required.

### 4.1 Physical packing or assembly compilation

Complementary cells that are repeatedly selected together may be stored in one load unit so that one access pulls the related data.

Packing:

- preserves every cell UID;
- preserves internal weights, dependencies, typed credit, and behavioural seams;
- may expose one fast ingress/egress path;
- reduces storage I/O and repeated lookup work;
- does not require every co-loaded cell to execute;
- is reversible and may be reorganised as access patterns change.

The storage pack is not itself a semantic belief. It is an optimisation comparable to compiling or paging a frequent execution path.

A loader may batch or co-locate records without creating a new semantic cell or UID. A true model merge creates a successor cell and therefore a new canonical UID.

### 4.2 True semantic fusion

Semantic fusion is reserved for cells that repeatedly produce the same addressed effect and are functionally substitutable, not merely adjacent or cooperative.

Candidates must demonstrate:

- equivalent effect signatures under overlapping conditions;
- redundant rather than complementary contribution;
- no material independent residual owned by either cell;
- no evidence that their agreement comes from duplicated evidence lineage alone;
- retained performance after a shadow consolidation;
- enough access or storage benefit to justify the transaction.

The fused successor receives a new canonical UID. Every predecessor UID becomes an inbound alias to that successor. Parent state should remain recoverable during a probationary interval.

### 4.3 Healing creates rigidity

Campaign 35 established an important empirical precedent: two intact 1.2B Ninereeds models could be concatenated into one 2.4B M4 model with both parameter sets initially preserved. Training the combined model on a healing curriculum then allowed connections and joint behaviour to grow across the former boundary.

The schematic transition is:

```text
fresh concatenation:
  [ A   0 ]
  [ 0   B ]

after healing:
  [ A + delta_A     cross_AB ]
  [ cross_BA        B + delta_B ]
```

The exact BDH tensors need not literally have this matrix layout. The point is that the initially intact submodels acquire cross-boundary causal dependence. Shared normalisation, routing, decoding, or other collective effects can entangle them further.

At the fresh-concatenation stage, extracting `A` and `B` may reproduce the original cells exactly. After sustained healing, copying out only the old parameter regions no longer reproduces the current functions: each side may depend on the other, and its internal updates may have been learned only in the merged context.

This gives **rigidity** a concrete meaning:

```text
co-load pack       no learned cross-boundary dependence; exactly separable
provisional merge  original blocks intact; cross-links small or isolated
healing fusion     increasing cross-dependent updates
rigid mature cell  safe extraction no longer available
```

Rigidity increases with useful joint activation and cross-dependent learning. Time alone is only a proxy. The real test is whether masking or removing the former boundary causes material regression.

Packing cells into one file for I/O does not require healing them. File co-location and learned fusion are separate decisions.

### 4.4 Merge identity and trust continuity

If cells `A`, `B`, and `C` merge, the successor `M` is addressed as:

```text
inbound A -> M
inbound B -> M
inbound C -> M
inbound M -> M

outbound source UID = M
```

The merge is a structural transaction:

1. allocate and validate the successor UID and combined state;
2. create alias mappings from every predecessor UID to the successor;
3. union the predecessor neighbour sets without flattening their relationship profiles;
4. migrate the predecessors' egress-affinity histories into the successor;
5. notify every connected neighbour that the canonical peer is now the successor UID;
6. let neighbours attach their predecessor-specific trust profiles to the successor edge;
7. activate the successor only after the topology and alias update commits;
8. retain predecessor files during the provisional rollback interval.

This update prevents the successor from suffering a complete trust cold start. It must not grant universal inherited authority.

Bob may have been trusted for colour-like states while Billy was trusted for movement-like states. After merger, the successor inherits both conditional profiles:

```text
successor trust for state S
  = bounded trust from predecessor profiles that match S
  + separately learned trust for genuinely joint successor behaviour
```

Predecessor trust is not summed into one scalar. Multiple old identities cannot create `N` times the authority, and duplicated evidence lineage cannot reinforce itself. Rejection, contradiction, and poor calibration histories migrate alongside positive trust so fusion cannot launder reputation.

A genuinely novel joint output that matches no predecessor profile begins under probation even though it comes from the successor UID.

Historical transmission records retain the UID that actually emitted the event. The active routing view resolves that historical UID through the successor alias. This preserves provenance while allowing current trust lookup to recognise continuity. Destructive rewriting of every historical record would erase which predecessor earned which trust.

Pending receipts and delayed credit addressed to a predecessor UID follow the alias into the successor while retaining the original target UID as contribution lineage.

Repeated mergers should use a compact alias-resolution forest or lineage DAG with path compression rather than copying an ever-growing predecessor list into every packet. Known neighbours may be updated eagerly; a merge event identifier provides a lazy fallback for any stale relationship record.

## 5. Packs retain a slow path; mature fusions may not

A physical co-load pack behaves like a compiled fast path, not an irreversible organ.

```text
loose cooperation
  -> shadow pack
  -> packed fast path
  -> suspect after material composite error
  -> diagnostic unpacking
  -> repair, rewire, fission, or replacement
  -> probation
  -> possible repacking
```

The original component boundaries remain recoverable for as long as the operation is only packing or a provisional merge. Once healing is allowed to rewrite and connect the combined system, the design must stop promising exact recovery of the current components.

When a still-separable packed output develops a serious residual:

1. suppress authority of the fast path;
2. expose and run the implicated slow-path components;
3. follow the contribution and dependency DAG;
4. inspect only the participating cells and interaction edges;
5. test candidate repairs in shadow;
6. validate old and new regimes;
7. recompile only after probation.

This is bounded diagnosis. Ninereeds does not test every possible subset of an assembly.

When a rigid mature fused cell develops the residual, it remains one diagnostic and storage unit. Ninereeds may:

- update the larger cell in place;
- narrow its routing scope and bud an adjunct specialist for the new regime;
- grow extra capacity around it;
- retain an old merge snapshot only as historical rollback, not as a decomposition of the current knowledge;
- quarantine or replace the whole fused cell if it loses all remaining usefulness.

Cloning the entire fused cell and specialising both copies is possible in principle, but it is expensive duplication rather than clean fission and is not the default lifecycle operation.

## 6. Interaction rules are creditable structural objects

A wrong conclusion may belong to the way correct component effects were combined.

If mass, speed, and spatial measurements are individually useful but jointly support `Earth is the centre of the universe`, the faulty object may be the integration rule:

```text
apparent motion around the observer
  -> observer is the physical centre
```

This interaction is represented as a dependency or synergy hyperedge. Delayed credit can target that interaction without punishing every contributor by association.

An implementation that preserves cells but cannot address their interaction rule cannot localise this kind of error. Addressable binding or interaction traces are therefore required.

## 7. Composite errors trigger diagnosis before structural action

Learning that:

- Earth revolves around the Sun;
- the Sun orbits the galactic core;
- the galaxy moves within a cluster;

does not necessarily invalidate mass, speed, or spatial reasoning. It may reveal a missing frame or scale condition in the assembled inference.

The same cells may be reused in several overlapping recipes:

- terrestrial observation with Earth-centred coordinates;
- Solar-System dynamics with heliocentric relations;
- galactic dynamics with galactocentric relations;
- cluster-scale dynamics with another frame.

Assembly membership is not exclusive. Shared cells need not be duplicated merely because the integration recipe changes.

An Earth-centred coordinate transform may remain useful while the claim that Earth is the physical centre becomes refuted. Claim address, scope, and relation type prevent the descriptive frame from being confused with ontology.

## 8. Faulty measurements target provenance before knowledge

If instruments were faulty and distances were wrong, Ninereeds should first target the measurement lineage:

```text
instrument
  -> observations
  -> distance estimates
  -> spatial claims
  -> composite predictions
```

The response is:

1. quarantine or recalibrate the source;
2. mark dependent claims `STALE`, not automatically `REFUTED`;
3. recalculate what retained evidence permits;
4. unpack still-separable assemblies, or update rigid fused units, that materially depended on the faulty estimates;
5. preserve unrelated spatial knowledge.

Cells therefore need a bounded evidence-influence sketch: which source families materially shaped their current behaviour. Full event retention is unnecessary, but no lineage at all would make source-fault repair impossible.

## 9. Fission requires both negative transfer and separability

Prediction error alone is not a split signal. Persistent negative transfer between coherent regimes establishes a functional need to separate them, but fission is technically available only if an extractable boundary still exists.

For regimes `A` and `B`:

```text
interference(A <- learn B)
  = error on A after learning B
  - error on A before learning B
```

If this value repeatedly remains positive, learning `B` damages `A`.

Fission eligibility requires:

- recurrent residual across independent evidence lineages;
- two or more coherent regimes rather than noise;
- persistent learning interference;
- continued predictive usefulness of the old regime;
- a young, packed, provisionally merged, or otherwise demonstrably separable parameter structure;
- a cheap ingress condition that can usually distinguish the regimes, or enough decision value to justify running bounded alternatives;
- shadow specialists that outperform the parent after structural and compute cost;
- sufficient traffic for the proposed children to mature.

These are gates rather than compensating terms in one scalar. High observation volume cannot compensate for the absence of coherent regimes or demonstrable interference.

If the old mapping is wrong everywhere, replace it rather than fissioning it. If the alternatives cannot be distinguished and running both has no decision value, return `UNRESOLVED` rather than growing permanent structure.

If functional separation is justified but the mature cell is rigid, Ninereeds must not pretend that extraction is safe. It updates the larger cell, buds a routed specialist, or replaces the larger unit. Functional need does not guarantee mechanical reversibility.

## 10. Exact fission is an early-life operation

During a mechanically valid fission:

- candidate children inherit useful parent structure;
- each child specialises on a supported regime in shadow mode;
- the parent may become a lightweight router or ancestry record;
- the parent does not continue as a full third authority indefinitely;
- route gates are calibrated before the children become authoritative;
- old and new prototype performance is checked during probation.

A counterfactual split test should mask the proposed cross-boundary paths and evaluate both candidate children. If either child depends materially on removed pathways, exact fission fails eligibility.

Examples:

- one universal correction that covers every speed regime -> update or replace;
- a cheap low-speed approximation and a high-speed relativistic regime that interfere -> gated specialists may be useful;
- one instrument-specific calibration and another incompatible calibration -> source-conditioned specialists;
- an absolute rule with no surviving valid scope -> retirement rather than fission.

After repair, specialists may repeatedly converge and become packing or semantic-fusion candidates again. Fission is reversible in function even when the exact previous weight state is not retained forever.

Once a fusion heals beyond the separability threshold, the old component snapshots describe its ancestry, not its current detachable contents. Restoring them would discard everything learned jointly since merger.

If a provisional merge fissions cleanly, predecessor UIDs may be redirected to their corresponding restored children. The merged successor UID cannot blindly alias to several children; it must either remain as a lightweight state-conditioned router during a transition or be retired after every connected neighbour updates its history and route profile. Pending traffic and delayed credit continue through the lineage mapping until the transition closes.

## 11. Growth is justified capacity, not fact counting

A neural cell is not full because it contains a fixed number of facts. Functional saturation is demonstrated behaviourally.

A relevant cell or neighbourhood is capacity-limited when repeated shadow learning shows that:

- the coherent residual cannot be reduced;
- reducing it causes regression on retained valid prototypes;
- routing coverage becomes confused or excessively multimodal;
- fixed gates or transforms repeatedly saturate while residual remains;
- no existing neighbouring cell can own the residual safely.

Gate utilisation may be a diagnostic, but the deciding evidence is failed residual reduction or harmful interference.

## 12. Two forms of growth

### 12.1 Frontier growth

A recurring coherent residual has no existing owner. A new cell grows at the frontier and forms relationships through shadow participation.

### 12.2 Adjunct growth or budding

The appropriate neighbourhood exists and remains useful, but compatible additional knowledge requires more capacity. The parent remains intact and a child learns the additive residual.

This differs from fission:

| Budding | Fission |
| --- | --- |
| Adds compatible capacity | Separates interfering regimes |
| Parent retains its function | Parent function is partitioned or becomes routing |
| Child owns an additional concern | Children specialise inherited concerns |
| No old regime must be displaced | At least two old/new regimes remain useful |

A growth commitment requires:

```text
recurring coherent residual
AND no existing cell can absorb it safely
AND the residual has enough expected utility
AND a shadow child reduces it without merely duplicating a neighbour
AND storage and routing budgets permit admission
```

One important event may seed an embryonic dossier, especially if its blast radius is high. It does not immediately create a mature authoritative cell.

## 13. Swan-kingdom growth and scoped classification

In the hypothetical discovery that swans are not birds but form a separate kingdom, the existing swan and bird knowledge is not destroyed.

The old neighbourhood may still correctly represent:

- swan colour distributions;
- movement through water, air, and land;
- size and morphology;
- strong resemblance to birds;
- historical and ordinary treatment as birds.

Strict taxonomy changes. If a new coherent body of swan-kingdom knowledge exceeds available local capacity, it buds as an adjunct cell. The child learns primarily the residual instead of copying every existing swan property.

Addressed relations may include:

- `resembles bird`;
- `shares bird-like morphology`;
- `is conventionally treated as bird`;
- `was historically classified as bird`;
- `is not a bird under taxonomy X`;
- `belongs to swan kingdom under taxonomy X`.

The bird assembly may continue to route swan-related thoughts while the new taxonomy cell supplies the strict qualification.

The tomato analogy has the same structure: botanical fruit and culinary vegetable answer different scoped category systems. Scope prevents useful everyday classification from becoming a false strict-taxonomy claim.

## 14. Growth remains sparse

Adding stored cells must not grant every new cell participation in every thought.

- newborn receptors begin narrow and conservative;
- the thought energy budget remains fixed;
- offers and activations still consume energy;
- fan-out remains bounded;
- packing reduces I/O for cells that are commonly co-accessed;
- irrelevant cells remain unloaded and inactive;
- failed embryos are dissolved rather than accumulating.

Sparse activation bounds inference compute. Deliberate quarantine and purging bound active topology and storage.

## 15. Senescence is not immediate death

A cell becomes senescent after an extended loss of rooted participation. Relevant signals include:

- no rooted ingress for a configured interval;
- no rooted egress for a configured interval;
- no useful delayed content, routing, calibration, inquiry, or protective credit;
- disappearance from neighbours' bounded transmission histories;
- expiry of active assembly or rollback obligations.

`Rooted` means participation in a real externally initiated thought, retained result, legitimate assembly operation, or other authorised process. Mutual meaningless traffic among obsolete cells cannot keep an island alive.

Senescence places the UID on a candidate list. It does not alter weights or delete storage during ordinary thought propagation.

## 16. Transmission history is evidence, not topology

The bounded recent history answers what happened. A bounded neighbour/edge manifest answers what can still happen.

Each edge may retain:

```text
peer UID
directed conductance
last rooted send
last rooted receive
last useful credit
strong | weak | expired state
assembly or rollback obligations
```

Falling out of transmission history weakens or expires an edge. It does not itself erase a cell.

Use the last `N` relevant opportunities rather than only the last `N` unrelated messages. High traffic in another domain must not instantly erase a rare but coherent relationship. A slower general inactivity rent may still make never-used knowledge a later hygiene candidate.

Packed assemblies must pass typed vitality credit to their internal contributors. Otherwise packing would make useful internal cells appear absent from external histories and accidentally render them senescent.

## 17. Deliberate organism-wide pruning

Active pruning occurs during a hygiene cycle, not inside a live thought.

If no edge metadata existed, exact disconnection would require scanning every transmission history. Campaign 36C already needs bounded neighbour relationships, so hygiene instead scans the cell and edge manifests.

With maximum degree `d`:

```text
E <= d * V
```

Tracing is therefore `O(V + E)`, effectively linear in the number of cells. It may run infrequently, incrementally, or while the organism is otherwise idle.

A central housekeeping pass does not centralise cognition. It is storage and topology infrastructure. Cells locally generate the evidence; the hygiene process reconciles it and reclaims resources without deciding semantic truth.

## 18. Reachability requires tracing, not reference counts alone

A zero-degree cell is an obvious candidate, but obsolete cells may form a mutually referenced island:

```text
A <-> B <-> C
```

Reference counts would keep the island alive even if no functioning part of the organism can reach it.

The pruning cycle therefore performs mark and sweep:

1. finish or snapshot active structural work;
2. mark live roots;
3. traverse valid routing and assembly edges;
4. classify unmarked cells and islands;
5. quarantine candidates rather than deleting them immediately.

Roots include:

- cells currently seedable by ingress;
- protected identity or foundational cells;
- participants in unresolved thoughts or pending delayed credit;
- active assembly entry points and their required internals;
- cells with recent rooted useful contribution;
- explicitly pinned cells.

If an isolated cell can still be selected directly by ingress, ingress itself is a live relationship and the cell is not unreachable.

Newborns, recently unpacked cells, and structural rollback state receive grace leases so hygiene cannot remove them before probation completes.

## 19. Quarantine is recoverable removal

The structural lifecycle is:

```text
ACTIVE
  -> SENESCENT LIST
  -> QUARANTINED
  -> PURGED
```

| State | Routable | Ordinary activation | Stored | Recoverable |
| --- | --- | --- | --- | --- |
| Active | Yes | Sparse/on demand | Yes | Not applicable |
| Senescent | Weakly or still routable | Rare | Yes | Immediate |
| Quarantined | No | No | Yes, outside active topology | Yes |
| Purged | No | No | No | No |

During pruning, a confirmed unreachable cell is cut from the active topology and moved under `quarantine/` using its existing UID. Quarantine does not change the UID and does not create an incarnation.

The cell's retained state may include its weights, receptor and route prototypes, behavioural summaries, former relationships, evidence influence, and reason for quarantine. Exact serialisation belongs to implementation.

## 20. Revive before birth

When a coherent residual requests new capacity, Ninereeds checks quarantine before creating a new cell.

1. compare the residual with quarantined cells;
2. select at most a small bounded number of plausible candidates;
3. restore a candidate under its original UID in shadow mode;
4. test it against the current residual and current neighbourhood;
5. require current neighbours to accept new relationships;
6. restore authority only after useful present-day contribution;
7. if no candidate fits, permit a genuinely new birth.

Old edges are hints, not automatically reinstated trust. The world and neighbouring cells may have changed during quarantine.

Because both growth and revival should be rare, an initial implementation may scan quarantine directly. A compact index should be added only if measurement shows that scanning is expensive. This recovery mechanism restores an endogenous learned cell; it is not document retrieval or context-injection RAG.

## 21. Quarantine reason affects revival

| Quarantine reason | Revival policy |
| --- | --- |
| Disuse | Normal shadow-revival candidate |
| Subsumed by fusion | Useful for rollback or if the successor later splits/fails |
| Obsolete after model change | May seed relearning; old claims begin unresolved or refuted as recorded |
| Repeated contradiction or harmful calibration | Diagnostic only; never immediate authority |
| Corruption | Prefer purging after evidence is retained elsewhere |

Revival is reconsideration, not blind reversion.

## 22. Purging is true death

If storage is needed, a deliberate hygiene cycle may delete quarantined contents. Candidate priority may consider:

- corruption or invalidity;
- complete functional redundancy;
- age since last useful contribution;
- repeated failed revival attempts;
- low expected future value;
- archive size and current storage pressure.

Deletion does not occur incidentally during inference. Once purged, the UID is retired and the detailed knowledge must be relearned if it becomes relevant again.

Surviving neighbouring knowledge may still make relearning easier by turning recurrence into a well-shaped residual rather than entirely unstructured novelty.

## 23. Pluto: relation update and access reorganisation

When Pluto is no longer included in a current strict list of Solar-System planets, the cell representing Pluto is not necessarily wrong or obsolete.

The addressed relations change:

- current strict planet-list membership is removed or refuted under the applicable classification;
- historical planet status remains time-scoped;
- dwarf-planet membership becomes supported;
- Pluto-specific properties remain available.

The old planet pack may be unpacked or repaged. Repeated dwarf-planet questions may make Pluto, Ceres, Haumea, Makemake, and Eris good physical packing partners so that one storage load retrieves the related cells.

They do not become one semantic object. Each retains its UID and properties. Their merger is an I/O and access optimisation driven by repeated co-use.

This shows that the organism does not organise knowledge into permanent taxonomic folders. It reorganises access according to current addressed truth and actual use.

## 24. Planet X: hypothesis support and gradual fading

A Planet-X-like cell is justified only while the hypothesis explains a real residual, has some grounding, makes relevant predictions, or guides useful inquiry. It remains `UNRESOLVED`, not asserted fact, until discriminating evidence arrives.

If decisive evidence refutes that hypothesis:

1. the addressed hypothesis becomes `REFUTED`;
2. its support and routing authority decrease;
3. inquiry and prediction paths stop selecting it unless historical context calls for it;
4. loss of rooted participation makes it senescent;
5. hygiene may quarantine it;
6. later storage pressure may purge it.

The system does not need to erase it at the instant of refutation. A refuted hypothesis may still explain historical reasoning or why an investigation was performed. If that function also disappears, the cell naturally fades from the active organism.

## 25. Complete structural loop

The four requested capabilities now form one adaptive lifecycle:

### Growth

Persistent coherent residual that cannot be absorbed safely buds or grows capacity.

### Merge

Repeated related access physically packs complementary cells when measurements show an I/O benefit. If loading two or even hundreds of separate records is not materially worse than one co-load, batching without structural fusion is sufficient. Repeated functional equivalence may justify learned fusion, but healing progressively sacrifices exact splitability.

### Split

Composite error first deoptimises a separable assembly. Persistent negative transfer between supported regimes justifies fission only while a usable seam remains. A mature healed cell is repaired as a larger unit or supplemented through budding.

### Death

Loss of rooted usefulness produces senescence. Deliberate tracing produces quarantine. Explicit storage hygiene produces true deletion.

Repair closes the loop: a corrected or specialised cell may again co-activate reliably, repack, or fuse. A now-unused branch may instead senesce and disappear. The loop is behaviourally reversible, but a mature healed fusion is not assumed to be parameter-wise reversible.

## 26. Settled invariants

- Every independently created cell receives one UID; a merged successor has one canonical UID plus every predecessor UID as an inbound alias.
- Merged cells emit their new canonical UID; predecessor aliases preserve addressability, pending credit, and trust continuity.
- Historical provenance retains the UID that emitted the event even when the active view resolves it to a successor.
- Trust migrates as state-conditioned predecessor profiles, never as an unbounded summed scalar.
- Sparse activation, not quarantine, controls per-thought VRAM and compute.
- Co-firing supports physical packing before it supports semantic fusion.
- Physical packs preserve cell identities and internal seams.
- File co-location, initial parameter concatenation, and learned healing are three distinct operations.
- Campaign 35 M4 demonstrates that intact concatenated models can later acquire cross-boundary connections through a healing curriculum.
- Healing produces rigidity: repeated joint learning can make the former cells causally inseparable.
- Interactions and binding rules receive their own dependency and credit traces.
- Prediction error triggers investigation and unpacking, not automatic fission.
- Fission requires persistent negative transfer between coherent supported regimes and a mechanically valid seam.
- Exact fission is normally restricted to packs, provisional merges, or architectures whose cross-links remain detachable.
- Mature rigid cells are updated in place, supplemented through budding, cloned only exceptionally, or abandoned as a whole.
- A universally wrong mapping is replaced, not preserved through pointless fission.
- Growth responds to demonstrated capacity failure, not each new fact.
- Budding adds a compatible concern; fission separates interfering inherited concerns.
- Newborn and revived cells pass through shadow/probation before authority.
- Transmission history is behavioural evidence, not the authoritative topology.
- Senescence is automatic; structural removal is a deliberate hygiene action.
- Mark-and-sweep is required to detect unreachable cycles and islands.
- Quarantine removes routability while preserving recoverability.
- Revival is attempted before new birth, under a bounded search and shadow test.
- Purging is true death and retires the UID.
- Typed contribution includes routing, abstention, error detection, inquiry, and prevented harm, not only content patches.
- Packing must propagate vitality credit to internal members.
- Structural mutation is versioned or staged so active thoughts and delayed credit are not orphaned.

## 27. Remaining implementation questions

The lifecycle contract is settled, but these mechanisms require experiments:

- exact mapping from BDH gates and parameter slices to independently stored cells;
- canonical UID and alias-resolution data structure across repeated mergers;
- atomic neighbour-notification and history-view update protocol;
- bounded state-conditioned trust migration and conflict handling;
- treatment of the merged successor UID after an early fission;
- physical pack/page format and target load size;
- measured filesystem, page-cache, decompression, and transfer cost of loading 2, 20, or 200 related cell records versus one pack;
- co-access statistics and packing/repacking thresholds;
- semantic-fusion equivalence estimator;
- rigidity estimator based on cross-boundary causal dependence rather than merge age alone;
- whether healing cross-links should be unconstrained, separately addressable, or adapter-like;
- counterfactual split test and acceptable regression threshold;
- shadow consolidation and rollback duration;
- negative-transfer thresholds and bounded replay prototypes;
- regime-separability estimator and route-gate calibration;
- cell saturation diagnostics beyond observed regression;
- sponsor selection and initial connectivity for frontier growth;
- active-topology root definition under the final ingress mechanism;
- senescence interval, relevant-opportunity clock, and grace leases;
- pruning cadence and incremental tracing strategy;
- quarantine file format and integrity checks;
- whether quarantine scanning ever requires a compact index;
- purge budget and protection policy for identity/foundational cells;
- structural transaction safety while delayed credit remains pending;
- prevention of merge/split and grow/quarantine oscillation through hysteresis;
- measurable compute, I/O, storage, and prediction-quality criteria for accepting each structural operation.

These values should be learned from instrumentation and adversarial lifecycle experiments rather than fixed from intuition.

## 28. Required validation experiments

At minimum, the implementation should test:

1. benchmark separate, batched, and physically packed cell loads on target hardware;
2. complementary co-access packing without semantic collapse;
3. freshly concatenated cells that can be extracted exactly before healing;
4. progressive healing that measures when extraction ceases to reproduce current behaviour;
5. merge of many cells under one new canonical UID with every predecessor UID remaining addressable;
6. neighbour trust continuity without scalar trust inflation or reputation laundering;
7. delayed credit sent to a predecessor UID after merge and correctly attributed through the successor;
8. one-component correction followed by successful unpack, repair, and repack while still separable;
9. coherent dual regimes that require and permit early fission;
10. early fission that correctly redirects predecessor and merged-successor UIDs;
11. coherent dual regimes in a rigid cell that correctly trigger in-place repair or budding rather than destructive extraction;
12. universal invalidation that correctly replaces rather than fissions;
13. additive novelty that buds without damaging its parent;
14. one-off novelty that does not grow permanent capacity;
15. dormant isolated cells and mutually referenced obsolete islands;
16. preservation of useful routing-only and abstention cells during hygiene;
17. quarantine, successful revival under the same UID, and relationship renegotiation;
18. failed revival followed by justified new birth;
19. deliberate purge followed by relearning from surviving neighbourhood context;
20. bounded thought compute as total stored cell count grows;
21. reduced I/O from packing under realistic sparse access traces;
22. no structural oscillation under alternating old/new evidence.

## 29. Next checkpoint

The structural lifecycle is now complete at the semantic-contract level. The next checkpoint should return to the remaining organism-level control questions, especially topology formation, connectivity and bridge preservation, structural transaction coordination, or the concrete BDH mapping and experiment plan.
