# Campaign 36C local-propagation contract

**Status:** frozen before implementation
**Date:** 2026-08-30
**Purpose:** prevent Campaign 36C from becoming a dense cell bank or a sparse
mixture-of-experts system with a semantic router.

## Architectural invariant

Thought discovers its route through local interaction.

Campaign 36C must not contain a learned/global semantic router, expert selector,
or full-population scoring pass. Topology, arriving latent state, persistent cell
state, and local transmission history determine propagation. Infrastructure may
locate, load, prefetch, evict, and repack tissue, but it may not decide which
meaning or expert should process a thought.

## Four-pressure homeostasis

Campaign 36C tissue is governed by four distinct local structural pressures:

1. **Growth:** persistent relevant unresolved residual after available local
   alternatives have received bounded exposure indicates that existing tissue is
   insufficient. Provisional cells are born beside the unresolved frontier.
2. **Fusion:** repeated low-error co-participation, strong conductance, increasing
   rigidity, and measured execution benefit allow stable neighboring tissue to
   fuse losslessly into a cheaper composite.
3. **Fission:** repeated error implicating a fused structure lowers rigidity and
   reopens preserved internal fusion boundaries so the tissue can become plastic
   again.
4. **Metabolism:** prolonged absence of participation, contribution, and renewed
   local evidence makes dormant tissue eligible for deletion and physical reuse.

These pressures must remain distinguishable in telemetry and tests. Prediction
error in rigid fused tissue should ordinarily raise fission pressure before growth
pressure: the organism first regains flexibility it already owns, and grows only
if the reopened local tissue still cannot resolve the residual. New provisional
tissue cannot immediately fuse; it must first accumulate the declared minimum
developmental evidence. Metabolism applies only to inactive tissue and may not
erase a cell participating in a current or pending wave.

No central agent balances these pressures semantically. Each is computed from
local participation, conductance, error, lifecycle, and resource evidence. Their
long-run balance is the intended homeostasis: insufficient regions grow, stable
regions compile, wrong composites reopen, and irrelevant regions disappear.

## Entry and continuation

- A continuing computation resumes from its previous active frontier.
- A new episode enters through a small fixed, always-resident ingress/continuity
  tissue for the input modality.
- Ingress transforms and admits the latent state. It does not classify the input
  into a domain or select downstream experts.
- SigLIP2, the language-vector source, and their projectors remain shared organs;
  they are not replicated per cell.

## Cell and edge behavior

Each cell or small execution cohort has:

- stable identity independent of storage address;
- persistent local state;
- BDH-style multiplicative/sparse dynamics;
- directed local adjacency;
- local transmission and plasticity statistics;
- lifecycle and residency state.

For cell `i` receiving travelling state `z`:

`delta_i, transmit_i = f_i(z, s_i)`

Each cell has exactly two ordinary completion actions for a wave:

- `PROPAGATE(destination_uids, contributions)`;
- `TERMINATE(contribution)`.

Termination carries no claim of success, correctness, relevance, or finality. It
means only that this cell has no outgoing transmission for this wave. The cell
does not know whether it is the last active UID. Multiple outgoing transmissions
may conduct simultaneously and with graded strength. There is no global winner
and no global top-k.

## Persistent DNA and transient RNA

The persistent cell anatomy ("DNA") contains:

- stable UID;
- content-receptive parameters;
- latent transformation parameters;
- directed neighbor UIDs and learned edge conductances;
- learned expected-traffic or route-familiarity structure;
- plasticity, rigidity, usage, refractory, lifecycle, and metabolic state.

The per-wave message ("RNA") contains only bounded transient evidence:

- travelling latent state or contribution;
- signal amplitude;
- a bounded recent-provenance tail;
- the direct predecessor UID set needed to suppress immediate reversal.

RNA disappears when the cell propagates or terminates. Provenance is cognitive
input to cells, not completion bookkeeping for the mapper. Normal operation does
not retain a complete ancestry tree. Verbose diagnostic mode may journal complete
wave transitions, and training may retain the executed autograd or eligibility
trace until its update is complete.

## Frozen wave protocol v0

For thought epoch `e`, the mapper holds one set `A_t` of active logical cell UIDs
for wave `t`. A UID appears at most once in a wave, but may reappear in a later
wave. There are no branch IDs.

1. Every UID in `A_t` receives one RNA value. Contributions with the same target
   UID are merged before that target executes.
2. Every cell in `A_t` performs its local transformation and returns either
   `PROPAGATE` or `TERMINATE` exactly once.
3. The cell's own UID and its immediate incoming predecessor UIDs are ineligible
   as outgoing destinations for that event. This prevents self-send and
   `A -> B -> A` ping-pong while permitting later recurrence such as
   `A -> B -> C -> A` after the latent has changed.
4. Outgoing transmissions are grouped by destination UID. Each group is reduced
   deterministically into one RNA value, so converging paths activate the target
   once and may interact compositionally there.
5. The next active set `A_(t+1)` is the unique set of destination UIDs. The
   frontier replacement is atomic: `A_t` is never observed empty between a
   parent's propagation and its children's activation.
6. A cold destination enters the active set before loading begins and remains
   active while the residency manager fetches it.
7. Natural quiescence occurs exactly when an atomic wave transition produces an
   empty active set.

The harness exposes `ready_for_next_turn = (active_uid_table is empty)`. No new
turn enters while it is false. Under atomic wave replacement, a closing wave may
contain one or many terminating UIDs; none is declared the correct or winning
cell. The readout uses the travelling state accumulated deterministically across
waves.

### Wave-convergence merge requirements

The v0 merge must be deterministic and invariant to arrival order. It must retain
both the combined latent condition and combined signal strength, so two weak
inputs can jointly change a target's response. Recent provenance remains bounded:
the implementation must predeclare the tail length `N`, maximum retained tails
`K`, deterministic truncation rule, and tie-breaking rule. The inspectable v0
representation uses literal UID tails rather than an opaque learned path vector.

When several paths converge, the target receives one merged RNA value and the
union of the direct predecessor UIDs for immediate-reversal suppression. Exact
merge and truncation formulas are experiment parameters and must be recorded in
the checkpoint and run manifest; they may not depend on nondeterministic message
arrival order.

### Bounded route memory

Two independent bounds must be declared:

- `H`: recent UID hops carried by one RNA provenance tail;
- `M`: recent thought-level provenance records retained by one cell as learned
  expected-traffic evidence.

The v0 cell uses a fixed-size ring of the last `M` thought-level route records.
There is no wall-clock timestamp decay and no background aging pass. A new thought
record overwrites the oldest record. If a cell reactivates several times during
the same thought epoch, it updates or merges the current epoch's record rather
than consuming several ring slots. Thus an oscillating thought cannot make one
route appear common merely by revisiting the cell.

Route familiarity is derived from this bounded recent sample, with a declared
smoothing rule for unseen and rare paths. A UID belonging to metabolized tissue
naturally disappears from neighboring route memory after `M` newer participating
thoughts. If a neighboring cell receives no new traffic, its stale record costs no
active compute and disappears only when experience replaces it or that neighbor
is itself metabolized.

## Local propagation regime

Route familiarity must not be a multiplicative veto. Each cell learns two kinds
of evidence:

- **content familiarity:** whether the incoming latent lies in territory where
  this cell usually produces meaningful change;
- **route familiarity:** whether traffic with this recent provenance normally
  reaches this cell in a useful context.

These jointly modulate the local propagation regime:

- familiar content and familiar route: narrow, strong propagation;
- unfamiliar content and familiar route: broad exploration;
- familiar content and unusual route: cautious propagation or exploration;
- unfamiliar content and unusual route: strong tendency to terminate, with a
  small bounded exploratory floor during learning.

The exploratory floor is part of tissue dynamics, not the mapper. It prevents a
rare useful route from being permanently excluded before it can acquire evidence.
It must be bounded and measured so that many low-probability cells cannot create
organism-wide activation. Raw traffic frequency alone is insufficient: route
expectations must be smoothed and eventually modulated by downstream learning
evidence.

Branch width emerges from local conductance. Several neighbor transmissions above
the local criterion create broad propagation; a mature concentrated prediction
creates narrow propagation; no outgoing transmission creates termination. A cell
does not select a semantic expert.

## Mapper and metabolic governor

The mapper has only two responsibilities:

- maintain the active UID table through atomic wave replacement;
- expose whether that table is empty.

It does not score content, choose destinations, own a propagation budget, decide
that an answer is correct, or reinterpret resource exhaustion as natural
quiescence.

A separate metabolic governor accounts for wave depth, active cell-time, signal
energy, paging, and other resource limits. If it exhausts a hard safety budget,
the harness records an explicit exhausted/aborted thought and drives active cells
to termination. The mapper merely observes the resulting empty table. Exhaustion
must never be reported as successful natural settlement.

The initial implementation must define explicitly:

- the contribution/transmission measure;
- local threshold and hysteresis;
- aggregation when several transmissions contribute;
- attenuation, propagation budget, and stopping conditions;
- cycle handling or refractory behavior;
- how persistent state changes during a wave and at episode boundaries.

## Physically sparse execution

Only the current frontier's neighbors may be loaded and evaluated in a propagation
step. Compact adjacency and residency metadata may remain resident. Cell weights
and full state may not be globally scanned to choose an active set.

Compute and I/O telemetry must report at least:

- cells and cohorts evaluated;
- cells changed and transmitted;
- frontier width and depth;
- propagation paths stopped and outgoing paths created;
- VRAM-resident, RAM-resident, and SSD-resident tissue;
- bytes promoted/demoted among tiers;
- useful active cell-time rather than only stored parameter count;
- wall-clock time spent computing, paging, and waiting for storage.

## Learning, growth, and metabolism

- Credit updates only the executed subgraph and the local transmission paths that
  participated in the outcome.
- The first propagation implementation may use backpropagation through the
  executed sparse wave graph to test the physical protocol without simultaneously
  replacing credit assignment. A later phase must separately test neighbor-local
  plasticity.
- A local future rule may use pre-cell activity, post-cell activity, and delayed
  outcome-error modulation. Traversal creates a temporary eligibility trace;
  later evidence consolidates, weakens, or reopens the implicated conductance.
- Prediction uncertainty available during a wave may broaden that current wave.
  Error learned only after the organism emits an answer changes future behavior
  unless an explicit later error wave is implemented.
- Repeated useful propagation strengthens or lowers resistance along local paths.
- Repeatedly unproductive paths weaken, become refractory, or become dormant
  without immediate deletion.
- Persistent unresolved residual may allocate provisional tissue adjacent to the
  unresolved frontier, subject to the Campaign 36B evidence lessons: minimum
  exposure age, cross-session evaluation, cooldown, reversible dormancy, and
  storage/compute budgets.
- Growth must not be the only response to novelty. Existing alternative paths must
  receive bounded opportunities so early routes do not permanently monopolize
  learning.
- Metabolism may demote, compact, dormancy-mark, or eventually reclaim tissue,
  while preserving auditability and reversible states wherever practical.

## Local birth, death, and derived inventory

There is no cognitive census and no organism-wide birth or death announcement.

Birth is local:

1. unresolved neighboring tissue requests provisional capacity;
2. the storage allocator assigns a never-reused logical UID and backing storage;
3. the newborn connects only to its local neighborhood;
4. neighboring traffic provides its developmental exposure;
5. its receptive behavior, transformation, and conductances differentiate through
   training rather than through an assigned semantic role.

Death is local:

1. a cell becomes metabolically eligible only while inactive, unloaded from all
   pending waves, and free of pending I/O obligations;
2. its stored state is removed and its physical slot becomes reusable;
3. its UID becomes permanently absent and is never reassigned;
4. there is no global reverse-edge scan;
5. stale neighboring references fail closed on lookup and disappear through the
   bounded `M`-thought route windows and ordinary local retraining.

The storage layer necessarily maps live UIDs to packed records, but this is an
allocator/lookup mechanism rather than a model-visible census. Cells should be
packed into page or segment files rather than represented as millions of tiny
filesystem files. Live cell count, lifecycle counts, serialized weight count, and
physical bytes are derived by inspecting packed record headers. They are telemetry,
not configured model dimensions. There is no preallocated empty cognitive
capacity; allocator slack or reusable deleted slots are physical fragmentation,
not unfilled model parameters.

## Rigidity, fusion, and fission

Rigidity is a graded, participation-conditioned property. It increases only when
a cell actually participates in eligible thoughts without being implicated in
prediction error. Mere inactivity must not make a cell rigid. Repeated implicated
error lowers rigidity and increases plasticity.

Fusion evidence is edge-specific. Two neighboring cells become fusion candidates
only when all declared conditions hold, including:

- both cells exceed the rigidity threshold;
- their connecting conductance is strong;
- they activate together or sequentially with high conditional frequency;
- neither commonly performs independently of the other;
- recent traversals across the connection are low-error;
- a bounded pre-fusion behavior-preservation audit passes.

Fusion is strictly pairwise and sequential. `Jim + Bob` may become `JimBob`, and
`Dan + Harry` may become `DanHarry`; a later qualified fusion may create
`JimBobDanHarry`. There is no bulk semantic clustering pass. Every composite is
therefore represented by a binary fusion tree with an individually auditable and
reversible boundary at each historical merge.

"Similarity" for fusion is similarity of use, never a domain label. It is derived
from overlapping recent provenance, conditional co-participation, mutual
conductance, correlated low-error traffic, and measured independence. Tissue used
for Japanese grammar should not fuse with tissue used for D&D lore merely because
it is physically nearby. Their ordinary arrival paths and co-participation evidence
will differ. If exploratory fan-out reaches unrelated stable tissue, unfamiliar
content combined with unfamiliar provenance should normally produce local
termination rather than recruiting that expert further.

The first fusion mechanism is lossless and concatenative rather than averaging
the cells into one opaque tensor. This is motivated by Campaign 35's
architecture-specific BDH neuron merge, which preserved source material by
concatenating sparse-neuron dimensions while handling shared bridges explicitly.
A fused cell retains both constituent transformations and their trained coupling.
Fusion initially preserves approximately the sum of constituent parameters; its
benefit is removing a recurrent wave, dispatch, and possible paging boundary.

A fused cell has one canonical active UID. Constituent UIDs remain as local entry
aliases so old neighboring paths can reach the fused tissue without global
rewiring. Alias resolution must deduplicate to one canonical UID in the active
table while retaining entry provenance in RNA. Aliases are never reused for
unrelated tissue.

Every reversible fusion retains an internal fusion tree, constituent parameter
and optimizer partitions, entry aliases, and sufficient local topology to undo
the fusion. Repeated prediction error or newly divergent use may trigger fission
along a preserved boundary, restoring independently active constituent cells and
their UIDs. Permanent lossy consolidation, if ever attempted, is a separate later
experiment and not part of initial fusion.

Fusion must not recursively create an unbounded dense supercell. A candidate is
admitted only while measured saved handoff/paging cost exceeds added indivisible
execution cost and while a frozen maximum fused execution/page budget is respected.
A composite may fuse again only within that bound. This lets repeated reliable
thought compile into cheaper tissue while prediction error can decompile it back
into plastic parts.

## Expected mature morphology

The intended mature organism is not a uniform bag of equal cells. If the four
pressures reach useful homeostasis, its stored anatomy may become heterogeneous:

- a small number of large, rigid, hierarchically fused domain regions containing
  stable and repeatedly useful behavior;
- many medium-sized reusable structures shared across recurring kinds of thought;
- distributed frontiers of small, plastic, provisional, or recently differentiated
  tissue where novelty is being absorbed;
- cold or dormant remnants awaiting reactivation or metabolism.

A large stored composite is evidence of repeated stable co-use, not a semantic
label. An external observer may make educated guesses from size, rigidity, traffic,
and provenance statistics, but the organism does not name the composite and the
storage layout need not reveal what it "means." Large residency regions may be
loaded together while retaining bounded internal execution units and sparse local
wave behavior.

Anatomy audits must therefore report distributions rather than only totals:
logical/composite size, binary fusion depth, rigidity, lifecycle, residency,
recent traffic, fission rate, and active-compute contribution. Physical file size
alone is only a proxy because packing, dtype, optimizer state, and fragmentation
also affect bytes.

## Structural interpretability and verbose tracing

36C interpretability is structural evidence, not semantic file labeling. A large
rigid composite is evidence of repeated stable co-use; broad plastic propagation
is evidence of internal uncertainty or unresolved interaction. Neither proves the
truth or falsity of the final output.

Normal execution records bounded aggregate telemetry. An explicitly enabled
verbose diagnostic mode records the wave-by-wave execution trace, including:

- thought epoch and wave index;
- canonical active UIDs and constituent/alias identities where fused;
- bounded incoming provenance tails and immediate predecessor masks;
- propagation destinations, amplitudes, merges, and terminations;
- unique logical composites activated;
- total activations including recurrence;
- underlying constituent leaf cells and active parameter/cell-time equivalents;
- peak and mean frontier width, propagation depth, and fan-out distribution;
- convergence/merge rate and repeated-route rate;
- rigidity and lifecycle distribution of participating tissue;
- cold loads, bytes moved, and residency wait time;
- growth, fusion, fission, metabolism, natural quiescence, and forced exhaustion
  events.

Counting only logical UIDs is insufficient because one fused composite may contain
substantially more tissue than one plastic cell. Storage or paging latency is also
not epistemic uncertainty. Interpretation must consider the trace as a vector of
evidence: width, depth, recurrence, plasticity, structural events, active tissue,
and completion mode.

Verbose traces may support statements such as "this task recruited unusually
broad and plastic tissue" or "this prompt followed a narrow mature route." They
must not automatically claim that the answer is correct. Trustworthiness must be
calibrated empirically by comparing trace features with held-out outcomes, and
effort should be interpreted relative to prompt length, task family, and the
organism's own prior traces. Inherently complex but well-learned work may activate
substantial tissue without being uncertain.

Verbose mode is diagnostic and potentially high-volume. Its events must be
buffered and written in batches or retained in RAM for bounded capture; it may not
force a synchronous SSD write for every cell interaction. Normal training uses
compact aggregate counters unless an experiment explicitly freezes verbose
capture.

## Residency and locality

- **Hot:** executing frontier in VRAM.
- **Warm:** immediate graph halo and recently active tissue, in VRAM or pinned
  host memory.
- **Cool:** reachable tissue in RAM.
- **Cold:** full cell state on SSD.
- **Dormant:** preserved tissue that is excluded from ordinary propagation unless
  a defined reactivation condition is met.

The system prefetches by graph distance and observed co-activation, not by semantic
classification. Frequently co-active tissue may be physically repacked together.
The cognitive graph remains authoritative; physical placement is only a cache.

## Required acceptance tests

Before a full bootstrap or v8 run, a bounded 36C smoke test must demonstrate:

1. **No dense population pass:** instrumentation and code inspection show that
   forward execution touches only ingress/frontier neighborhoods.
2. **Size independence:** adding disconnected cold tissue does not materially
   change output or forward cost.
3. **Path termination:** an unreceptive neighbor stops propagation without
   evaluating its descendants.
4. **Branching:** two receptive neighbors may both continue and influence the
   result.
5. **Directionality:** reversing or removing a directed edge changes only paths
   reachable through that edge.
6. **Deterministic replay:** identical checkpoint, input, topology, and seed
   reproduce the same visited subgraph and result.
7. **Tier movement:** cold reachable tissue is loaded, becomes hot/warm, and is
   later demoted under pressure without changing its identity.
8. **Cold resume:** checkpoint reload restores topology, lifecycle, persistent
   state, optimizer state, and residency metadata sufficiently for equivalent
   continuation.
9. **Bounded exploration:** an unresolved input can widen its search without a
   global semantic scan or uncontrolled organism-wide activation.
10. **Local growth:** when enabled, a birth attaches beside the unresolved active
    frontier and does not require a central expert catalogue.
11. **Mapper minimality:** completion depends only on the atomically maintained
    active UID table; route provenance is not used for quiescence detection.
12. **Wave merge:** two transmissions to the same UID produce one deterministic
    activation whose result is invariant to arrival order and can differ from
    either input alone.
13. **Recurrence without ping-pong:** immediate edge reversal is suppressed, while
    a UID may legally reactivate in a later wave through a longer route.
14. **Route-conditioned novelty:** controlled probes distinguish unfamiliar
    content arriving by a familiar route from unfamiliar content arriving by an
    unfamiliar route.
15. **Exploration floor:** a rare useful route can acquire evidence without
    allowing low-relevance traffic to cause unbounded fan-out.
16. **Governor separation:** budget exhaustion is reported as exhaustion and does
    not cause the mapper to label the thought naturally settled.
17. **Bounded route replacement:** exactly one provenance record per participating
    thought epoch occupies the cell's `M`-record ring, and old routes disappear
    through replacement without timestamp decay or a cleanup scan.
18. **Local death healing:** deleting an inactive test cell performs no global
    reverse-edge rewrite; stale local references fail closed and are displaced by
    subsequent bounded route history.
19. **Derived inventory:** live cells, lifecycle states, serialized weights, and
    bytes are reconstructed from packed storage headers without model-visible
    fixed capacity or one-file-per-cell storage.
20. **Participation-conditioned rigidity:** unrelated thoughts and inactivity do
    not increase a cell's rigidity; repeated low-error participation does.
21. **Lossless fusion:** a qualified rigid neighboring pair fuses with pre/post
    behavior within declared tolerance, retains both constituents, and removes a
    measured wave or dispatch boundary.
22. **Alias deduplication:** traffic through either constituent UID reaches the
    same fused cell and produces only one active-table entry in a wave.
23. **Reversible fission:** induced repeated error can split a reversible composite
    along its preserved fusion tree and restore independently active constituents.
24. **Fusion bound:** recursive fusion cannot exceed the declared indivisible
    execution/page budget or recreate an unbounded dense supercell.
25. **Pressure attribution:** every structural change is journalled as growth,
    fusion, fission, or metabolism with its local evidence; one category may not
    silently stand in for another.
26. **Fission before growth:** controlled error in a reversible rigid composite
    first exercises its preserved fission path; growth becomes eligible only if
    the reopened tissue remains persistently unresolved.
27. **Development before fusion:** newborn provisional tissue cannot satisfy the
    fusion gate before its minimum exposure and evaluation requirements.
28. **Pairwise fusion history:** every composite is produced by one qualified
    pairwise fusion at a time and retains a binary, reversible fusion tree; no
    semantic bulk-clustering operation exists.
29. **Use-defined domain separation:** matched probes show that strongly distinct
    provenance and co-participation distributions do not fuse merely because the
    cells are neighbors, and exploratory spill into unrelated stable tissue
    terminates locally.
30. **Morphology audit:** inspection reports composite-size and fusion-depth
    distributions against rigidity, lifecycle, residency, traffic, fission, and
    active-compute evidence; it does not reduce the organism to one total cell or
    parameter count.
31. **Verbose structural trace:** a bounded diagnostic run reconstructs every
    wave's active UIDs, provenance, propagation, convergence, recurrence, and
    termination while agreeing with aggregate active-compute counters.
32. **Fusion-aware effort:** effort reporting distinguishes logical composite
    count from constituent leaf-cell/parameter cell-time so a large fused region
    cannot appear artificially cheap by counting as one UID.
33. **Outcome calibration:** held-out probes measure how structural trace features
    correlate with correctness and do not promote raw activation count to an
    unvalidated confidence score.
34. **Bounded logging overhead:** verbose capture is buffered and bounded, while
    ordinary execution performs no synchronous per-cell persistent write.

## Questions to resolve during implementation, not conceal in a router

- What is the smallest useful execution unit: cell, micro-cohort, or page-aligned
  cohort?
- How do BDH multiplicative dynamics map onto `delta_i` and `transmit_i`?
- How far can differentiable credit travel through a paged propagation trace?
- What local exploration rule prevents useful cold paths from starving?
- What metadata must remain resident so adjacency lookup is cheap but cognition
  is not accidentally centralized?
- Which events justify SSD writes, and which state can remain journaled in batches
  to protect storage endurance?

These are engineering and experimental questions. None may be answered by adding
a hidden semantic router.
