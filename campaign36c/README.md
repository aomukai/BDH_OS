# Campaign 36C Stages 1–7

This package implements the first seven bounded experiments from the Campaign
36C handoff: independent cells, sparse waves, local plasticity, controlled
developmental birth, packed persistence/residency, and reversible structural
compilation, followed by deliberate organism-wide hygiene. The real bootstrap
and lesson curriculum remains the final unimplemented stage.

The model unit is `StandaloneBDHCell`, an independently stored width-512,
head-local cohort of aligned rotary pairs. It owns its content encoder, value
encoder, decoder, rotary buffer, stable UID, and UID-local full-moment AdamW
state. Its local operation follows the handoff contract:

```text
q       = ReLU(norm(z) @ encoder)
scores  = causal_rotary_attention_score(q)
context = norm(scores @ z)
r       = ReLU(context @ value_encoder)
gates   = q * r
delta   = gates @ decoder
z_next  = norm(z + residual_scale * delta)
```

`MaskedLocalBDHHeadControl` embeds the same cohort in a larger local-operator
gate bank and proves that unrelated masked slots do not alter it.
`MaskedDenseBDHHeadControl` keeps the existing dense BDH layer's normalization
and residual semantics, so its output and gradient differences quantify the
architecture change rather than being treated as a required invariant.
`LowRankResidualControl` is the parameter-nearest version of the Campaign 36B
residual cell.

The checkpoint is a single bounded laboratory artifact and atomically retains
the UID, ABI/config, parameters, rotary buffer, optimizer policy/state, RNG
state, and metadata. It is not the later packed segment store and must not be
scaled into one file per cell.

## Input bundle

A real experiment consumes a `LatentTask` saved with `save_latent_task`. It has
separate training and held-out evaluation splits, each containing:

- `root_state`: the continuity core's initial latent state;
- `target_state`: the matured or teacher target for that same thought;
- optional `attention_mask`.

An optional `extra_core_tick_evaluation` tensor supplies the equal-cost core
control. Without it, the report may name a provisional candidate but cannot
declare the Stage-1 exit gate met.

## Runner

The full declared cohort sweep is:

```bash
PYTHONPATH=. /path/to/ninereeds-cortex/bin/python \
  meta/scripts/run_campaign36c_cell_lab.py \
  --latent-bundle /path/to/continuity-core-latents.pt \
  --output /path/to/campaign36c-stage1.json \
  --pair-counts 1 2 4 8 16 32 \
  --devices cuda:0 cuda:1 \
  --dtype bfloat16
```

Independent cohort trials are divided deterministically across the requested
devices and their evidence is merged only after every shard completes. Trial
states and scores are never averaged across devices.

Omitting `--latent-bundle` generates a deterministic synthetic residual. That
mode verifies mechanics, gradients, restore, telemetry, and execution plumbing;
it is explicitly not behavioral evidence that the cell is useful.

The result records exact parameter/optimizer/checkpoint bytes, the handoff's
first-order MAC estimate, measured forward latency, no-cell and optional
extra-core-tick controls, the parameter-nearest 36B residual control,
batch-composition invariance, masked-dense equivalence, and cold-resume
equivalence.

Candidate selection requires at least the declared held-out improvement
fraction (1% by default), a better held-out result than the parameter-nearest
36B residual control, and all mechanical checks within the declared numeric
tolerance. The CLI defaults that tolerance to `1e-5` for float32 and `0.02` for
bfloat16; both values are written into the result rather than inferred later.

## Stage 2: fixed sparse-wave substrate

`SparseWaveSubstrate` is a fixed directed graph in RAM/VRAM. A thought enters
through an explicit bounded ingress UID; there is no global semantic router or
population-wide activation score. Only declared neighbors receive cheap,
vectorized receptor probes, and only `WRITE` admissions enter the vectorized
BDH transform. `ROUTE_ONLY` admissions can relay a known route without paying
for a full transform. Disconnected cells are never inspected during a thought.

The 36C-0 physical protocol includes:

- stable UIDs independent of module position;
- separate familiarity, coverage, residual, and route-familiarity measures;
- atomic frontier replacement and one execution per destination per wave;
- deterministic energy-weighted convergence relative to a common state;
- immediate-reversal suppression with bounded longer recurrence;
- conserved route energy, bounded fan-out, and hard governor limits;
- distinct `quiescent` and `exhausted` results;
- bounded provenance tails and diagnostic wave traces.

The v0 convergence rule is intentionally only a physical-protocol merge. It
does not claim to resolve contradictory patches; that remains governed by the
later patch-aware reducer.

The two-GPU trainbox smoke is:

```bash
PYTHONPATH=. /home/aomukai/.venvs/ninereeds-cortex/bin/python \
  meta/scripts/run_campaign36c_wave_lab.py \
  --output /path/to/campaign36c-stage2.json \
  --rotary-pairs 2 \
  --disconnected-cell-counts 0 256 4096 \
  --devices cuda:0 cuda:1 \
  --dtype bfloat16
```

The speed criterion is deliberately modest. Stage 2 must remain serviceable,
must not repeat 36B's all-cell execution, and must keep active work independent
of disconnected stored capacity. It does not need to beat a fully resident
transformer on tiny tasks. The architectural bet is useful long-horizon work
with a stored organism too large to execute densely on the available GPU.

## Stage 3: executed-subgraph learning

`ExecutedSubgraphTrainer` uses ordinary end-to-end backpropagation through the
executed wave graph. It is deliberately **not** described as Hebbian learning.
Persistent updates remain UID-local and follow typed thought-level credit:

- every transform emits an addressed latent patch and eligibility record;
- accepted and rejected handoffs produce explicit edge receipts;
- patch dependencies preserve and deduplicate shared ancestry;
- equivalent forked effects apply once and do not manufacture evidence;
- contradictory single-address writes remain unresolved hypotheses;
- only retained, sufficiently owned transforms may step;
- useful participating edges update route familiarity separately;
- low-ownership work resolved elsewhere narrows receptor calibration without
  rewriting cell content;
- unknown outcomes produce pending credit and no persistent update;
- declared-invalid dependencies receive no transform update even when the
  terminal answer is useful;
- retention probes can atomically roll back parameters, route/receptor state,
  and UID-local optimizer moments.

The synthetic Stage-3 laboratory trains a common route and a separate rare
route, while retaining a connected rejection case and disconnected tissue. It
checks held-out improvement, exact inactive-state preservation, typed credit,
unknown-outcome expiry, retention rollback, cross-domain isolation, and rare
route survival under subsequent common replay:

```bash
PYTHONPATH=. /home/aomukai/.venvs/ninereeds-cortex/bin/python \
  meta/scripts/run_campaign36c_learning_lab.py \
  --output /path/to/campaign36c-stage3.json \
  --rotary-pairs 2 \
  --devices cuda:0 cuda:1 \
  --dtype bfloat16
```

This is still a bounded synthetic containment experiment. It demonstrates
that useful sparse routes can learn without indiscriminate neighboring-domain
rewrite; it is not yet evidence of open-ended development or real-task
competence.

## Stage 4: diagnosis before birth

`DevelopmentController` distinguishes bad evidence, a bad route, and an
undertrained existing route from genuine capacity failure. Only persistent,
coherent capacity residuals spanning bounded epochs, lineages, and sources may
open a birth dossier. A newborn trains off graph under shadow exposure, must
show independent held-out value against ablation and receptor controls, and is
then admitted only at low contribution authority. Probationary harm rolls the
structural transaction back; mature authority requires additional live
evidence. Durable UIDs are monotonic and rejected births are never reused.

```bash
PYTHONPATH=. /home/aomukai/.venvs/ninereeds-cortex/bin/python \
  meta/scripts/run_campaign36c_development_lab.py \
  --output /path/to/campaign36c-stage4.json \
  --rotary-pairs 2 \
  --devices cuda:0 cuda:1 \
  --dtype bfloat16
```

## Stage 5: packed persistence and residency

`PackedCellStore` separates canonical cell identity from physical placement.
It writes multiple independently checksummed records into immutable pages,
publishes copy-on-write manifests through a journaled transaction, preserves
cell-local optimizer and anatomy state, supports snapshots and repacking, and
fails closed on corruption. A failed durable birth retires its UID.

`GraphResidencyManager` keeps only compact UID, location, adjacency, and
lifecycle metadata resident. It loads the active graph halo, never treats page
co-location as a cognitive edge, refuses to activate dormant tissue, and does
not write persistent state during inference. `DirtyCellBuffer` coalesces
repeated local updates before a durable flush.

The Stage-5 laboratory injects failures after prepare, write, validate, commit,
and publish; compares page capacities against access sets of 2, 20, and 200
cells; verifies exact cold output/optimizer/RNG/anatomy restore; and checks that
adding disconnected capacity does not increase route I/O:

```bash
PYTHONPATH=. /home/aomukai/.venvs/ninereeds-cortex/bin/python \
  meta/scripts/run_campaign36c_persistence_lab.py \
  --output /path/to/campaign36c-stage5.json \
  --page-capacities 2 20 200 \
  --access-set-sizes 2 20 200 \
  --devices cuda:0 cuda:1 \
  --dtype bfloat16
```

These remain bounded synthetic mechanisms. Passing Stage 5 establishes that a
large sparse organism can be represented and brought into memory safely; it
does not establish useful real-world competence or unbounded lifecycle safety.

## Stage 6: packing, fusion, rigidity, and fission

Stage 6 preserves three separate claims. `CoAccessTracker` may reorder packed
records without changing any UID or cognitive edge. `StructuralController` may
compile one qualified neighboring pair into a `ReversibleCompositeCell` with a
new canonical UID, predecessor aliases, retained constituent transforms and
optimizer partitions, conditional trust profiles, and a binary fusion tree.
Semantic healing remains an explicit boundary whose causal effect is measured
by counterfactual masking.

The composite charges every constituent transform in effort telemetry even
though it removes a logical wave/dispatch boundary. Alias traffic deduplicates
to one active canonical UID while retaining the historical entry UID for
receptor selection, provenance, trust, and delayed credit. Recursive fusion is
bounded by leaf count, depth, and physical parameter bytes.

Prediction error first deoptimizes the composite. Exact fission requires
repeated negative transfer, two supported useful regimes, calibrated routing,
shadow value, a counterfactually valid seam, and closed successor obligations.
It restores the predecessor UIDs and retires the fused successor. If healing
has made the seam causally necessary, the controller refuses extraction and
selects in-place repair or budding instead.

```bash
PYTHONPATH=. /home/aomukai/.venvs/ninereeds-cortex/bin/python \
  meta/scripts/run_campaign36c_structural_lab.py \
  --output /path/to/campaign36c-stage6.json \
  --maximum-composite-leaves 2 \
  --devices cuda:0 cuda:1 \
  --dtype bfloat16
```

The Stage-6 laboratory measures packed-page benefit, pre/post fusion behavior,
logical versus constituent effort, cold structural restore, trust and credit
continuity, valid fission, rigid-fission refusal, development and recursive
fusion bounds, and old-or-new recovery at every structural commit boundary.

## Stage 7: senescence, quarantine, revival, and purge

`RootedParticipationLedger` distinguishes participation in a real externally
initiated thought from self-sustaining chatter inside an obsolete island. It
retains typed content, routing, calibration, inquiry, protective, and
abstention vitality, plus bounded edge history, grace leases, pending credit,
pins, protection, and structural obligations. Senescence is only a candidate
state; it changes neither weights nor storage during ordinary propagation.

At a fully quiescent lifecycle boundary, `HygieneController` traces enabled
routing from ingress, recent useful participation, protected tissue, pending
work, active assemblies, and explicit pins. Confirmed unmarked islands move to
recoverable quarantine under their existing UIDs. Stale neighbour references
fail closed without an immediate organism-wide reverse-edge rewrite.

Before a capacity residual may authorize birth, a bounded quarantine scan may
restore one plausible cell in off-topology shadow mode. Present-day value,
independent evidence, retention safety, and new neighbour acceptance are all
required before the same UID returns at probationary authority. Historical
edges remain hints and are not reinstated automatically.

Purge is a separate operator-authorized storage-pressure transaction. It
removes quarantine bytes, retires the UID permanently, and cannot run inside a
thought or while delayed-credit/structural obligations remain. Packed
quarantine membership, revival, and purge use the same old-or-new commit
boundaries as growth, fusion, and fission.

```bash
PYTHONPATH=. /home/aomukai/.venvs/ninereeds-cortex/bin/python \
  meta/scripts/run_campaign36c_hygiene_lab.py \
  --output /path/to/campaign36c-stage7.json \
  --maximum-revival-candidates 2 \
  --devices cuda:0 cuda:1 \
  --dtype bfloat16
```

The Stage-7 laboratory verifies that routing-only and abstention tissue
survives, mutually referenced unreachable islands quarantine, cold revival
returns unchanged learned content under the same UID, old trust is not blindly
restored, unauthorized purge is refused, pressure purge reclaims quarantine
pages, and every quarantine/purge fault exposes a coherent old or new state.
