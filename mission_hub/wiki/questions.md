<!-- ninereeds-wiki: {"schema_version":"ninereeds_research_wiki_page_v1","page_id":"wiki-questions","page_type":"question_catalogue","status":"active","updated":"2026-09-02","source_ids":["src-current-teaching-methodology-v1","src-bdh-cq-paper","src-current-evaluation-methodology-v1","src-campaign35-session20-reconstruction-20260819","src-campaign35-post-reconstruction-planning-20260819","src-c36c-checkpoint-01","src-c36c-checkpoint-02","src-c36c-checkpoint-03","src-c36c-checkpoint-04","src-c36c-local-propagation-v1","src-c36c-config-v0","src-c36c-wave-v0","src-c36c-learning-v0","src-c36c-development-v0","src-c36c-persistence-v0","src-c36c-structural-v0","src-c36c-hygiene-v0","src-c36c-organism-v1","src-c36c-visual-bootstrap-v1","src-cortex-lfm-config-v1","src-cortex-lfm-ingress-v1","src-cortex-student-v2","src-c36c-bootstrap-runner-v1"]} -->
# Research questions

Awaiting the first Luna librarian ingest. Questions will receive stable IDs, scope,
status, related findings, relevant campaigns, and preregistered yes/no criteria.

At each transition Sol gives every prior question one epistemic answer—`not tested`,
`insufficient evidence`, `conflicting evidence`, `yes`, `no`, `invalid`, or `other`—
and one independent lifecycle disposition. Rephrasing and splitting create successor
IDs; they never rewrite the original question.

## Teaching-system design questions

These are unresolved design or research questions, not implied implementation work.

### TQ-0001 — Answer validity

How should lesson contracts preregister acceptable semantic answers and invariants
without allowing the teacher to redefine success after seeing the response?

### TQ-0002 — Developmental evidence state

What is the minimal durable per-target record for teaching history, successes,
failures, scaffolding, modalities, boundaries, and scheduled revisits? Which records
are authoritative artifacts rather than summaries?

### TQ-0003 — Absence versus retrieval failure

Which observable history justifies retrieval-first scaffolding, and what experiment
can estimate whether that rule helps without wasting turns or reinforcing errors?

### TQ-0004 — Verifier independence

Which checks can be deterministic, when is a separate semantic verifier required, and
how do we prevent the teacher from grading its own intervention?

### TQ-0005 — Teacher benchmark and provider choice

Which model best diagnoses deliberate errors, uses minimal scaffolding, stays on
target, reduces support, and returns control within budget? Cost, latency,
availability, and complementary error patterns belong in the comparison.

### TQ-0006 — Spacing and mastery

What delayed-revisit schedule and evidence threshold should move a target among
presentation, controlled practice, mixed practice, transfer, retained, unstable, and
revisit states?

### TQ-0007 — Experience-to-weight update semantics

How do interactive lesson turns become an ordered Ninereeds update while preserving
prediction-before-correction, teacher feedback, provenance, optimizer semantics, and
reproducibility?

### TQ-0008 — Scaffolding measurement

How should assistance distributions and capability boundaries be compared across
checkpoints without collapsing them into a misleading scalar?

### TQ-0009 — Multimodal equivalence

What evidence establishes that a relation learned in text and recognized in images is
one transferable capability rather than two separately memorized behaviors?

### TQ-0010 — Tool-assisted internalization

Under which tasks, repetitions, and verification conditions does successful external
tool use later improve unaided performance, if at all?

### TQ-0011 — Adaptive state-transition calibration

What observable evidence should trigger presentation replay, acquisition, leech,
problem, backtrack, and lesson completion states? How sensitive are conclusions to
the provisional 3-failure, 75%, 24-episode, and four-later-lesson thresholds?

### TQ-0012 — Comparable adaptive control

How do we hold controller, teacher, verifier, randomness, and decision policy constant
across experimental arms while allowing legitimate response-dependent lesson paths?
Which decisions require blinded or deterministic adjudication?

### TQ-0013 — Repetition lesson update semantics

Is a repetition lesson an evaluation, an intervention that changes weights, or both?
What checkpointing and ordering preserve interpretable retention and reacquisition
evidence after presentation replay occurs inside it?

### TQ-0014 — Pack-size response

How do acquisition, interference, mixed-practice discrimination, retention, and
teaching cost change with pack size? Is four, seven, or another size preferable by
developmental stage or Point family?

### TQ-0015 — Whole-lesson replay response

How many frozen lesson epochs continue to produce durable gains, where do they
plateau, and when do gains become cadence- or scene-specific rather than transferable?

### TQ-0016 — Multilingual visual lexicon alignment

How should the M2-derived 2,500 concepts be assigned natural English, German,
Japanese, and Chinese visual captions while preserving one grounded sense? Which
frequency, age, part-of-speech, ambiguity, image-fit, tokenizer, and downstream
teaching-utility evidence should control synonym selection?

### TQ-0017 — Separate monolingual visual births

If four 150M branches share exact initialization, images, ordering, architecture, and
optimizer policy but receive separate monolingual captions, how much coordinate
compatibility, visual grounding, and language-specific divergence results? What
control distinguishes caption-language effects from nondeterministic training paths?

### TQ-0018 — Luna-conducted role reversal and visual reference

How should Luna conduct open but prerequisite-safe Ask me dialogue, interpret
Ninereeds' questions, maintain or clarify visual reference, select prepared crops or
highlights, and return auditable evidence without a deterministic script conducting
the conversation or Luna redefining the lesson Point?

### TQ-0019 — Developmental identity thread

What ordered, grounded lessons should introduce Ninereeds' name, `I`/`you`, asking,
knowing, remembering, people, minds, named interlocutors, source boundaries, and
autobiographical continuity? How can identity be reinforced continuously while
remaining evidence-based, correctable, and distinct from unsupported consciousness
or substrate claims?

## Evaluation-system questions

### EQ-0001 — Boundary-ladder construction

Which deterministic or frozen generators can vary one Ninereeds-relevant demand while
holding the learned rule, surface difficulty, and answer contract fixed?

### EQ-0002 — Support versus execution

For which failure families does byte-identical matched-complexity support restore
performance, and which failures persist after support coverage is equalized?

### EQ-0003 — Strict consistency

Which item groupings legitimately share one inferred rule, and what strict all-item
criterion distinguishes stable acquisition from partial success without making the
groups artificially brittle?

### EQ-0004 — Composition prerequisites

Which atomic capabilities must pass, under which representations, before a combined
lesson or evaluation can make a defensible claim about compositional behavior?

### EQ-0005 — Freshness and contamination

What post-freeze generation, overlap detection, opaque-identifier, batch-mixing,
cadence, and near-duplicate controls are sufficient for each evaluation family?

### EQ-0006 — Failure morphology

Which observable language, image, activation, and output-structure errors can be
classified reproducibly without pretending they reveal Ninereeds' latent reasoning
path?

### EQ-0007 — Teaching-efficiency comparability

How should Points be matched across arms and curriculum-age bands so fewer exposures,
replays, interventions, or compute can be attributed to improved acquisition rather
than easier later material, richer support, or controller drift?

### EQ-0008 — Incidental-exposure controls

Which scene metadata, exposure counts, matched concept sets, and held-out conditions
can test whether earlier unscored Topic exposure changes later explicit acquisition
without assuming that co-occurrence produced learning?

### EQ-0009 — Experimental-arm stopping

What preregistered evidence constitutes a substantial, stable, compounding advantage
that justifies stopping the weaker arm without converting ordinary short-term variance
into a campaign-level decision?

## Mycelium architecture questions

### MYQ-0001 — Text-ingress integration

Can the frozen LFM2.5 Encoder and its trainable 1024-to-512 projector be attached to
the integrated Mycelium student, persisted, restored, and trained end to end through
the same continuity core and sparse tissue as visual ingress? Which tests prove that
text and vision reach one shared organism rather than two modality-specific paths?

### MYQ-0002 — Training order, replay, and recovery

How do shuffled, dependency-ordered, blocked, interleaved, and repeated text streams
change acquisition, regression, recovery, route formation, and structural development?
When an epoch recovers behavior, does it restore an earlier route or construct a new
one with a different continuation phenotype?

### MYQ-0003 — Continuity-core size

What is the smallest always-active core that preserves identity, context, latent-ABI
stability, and action selection without absorbing knowledge that should live in sparse
tissue? How do core size and tissue recruitment trade off at matched behavior?

### MYQ-0004 — Cell granularity and temporal operator

Which aligned rotary-pair cohort size is the smallest useful and economical local
operator under realistic text sequence lengths? If repeated full-sequence attention
dominates microscopic cells, which cheaper BDH-derived temporal operator preserves the
multiplicative learning behavior and latent ABI?

### MYQ-0005 — Receptor calibration and exploration

Which familiarity, coverage, residual, route-history, and writing thresholds produce
useful local routing without false rejection, indiscriminate writing, or population-
wide exploration? How should calibration change across cell development stages?

### MYQ-0006 — Energy and recurrence

How should route energy, probe and transform tolls, branch floors, frontier limits,
recurrence limits, and a possible second latent pass vary with task novelty and
difficulty? Which settings truncate useful thought, and which create compute-expensive
loops without additional evidence?

### MYQ-0007 — Backpropagation versus local plasticity

What capabilities of executed-subgraph backpropagation can be reproduced by genuinely
cell-local or neighbour-local learning? Which credit dimensions require delayed global
reduction, and which can be learned from local receipts without damaging rare or
minority hypotheses?

### MYQ-0008 — Birth sensitivity and useful capacity

How sensitive are missed births, duplicate births, harmful admissions, and tissue
growth to evidence counts, source diversity, residual coherence, shadow duration,
improvement thresholds, regression limits, probation authority, cooldown, and
maturation requirements? Which observations distinguish capacity failure from a bad
route or undertrained existing tissue in natural corpora?

### MYQ-0009 — Topology formation

How should an embryo's initial ingress topology form and adapt when no global semantic
router is allowed? Which local histories create reliable bridges, prevent isolated
specialists, and preserve access to rare knowledge as the organism grows?

### MYQ-0010 — Packing, fusion, and rigidity

When does physical co-packing provide enough measured benefit to matter, when does a
reversible composite preserve function across real learned routes, and which healing
conditions produce useful causal integration rather than irreversible interference?
What counterfactual test detects the last safe fission boundary?

### MYQ-0011 — Residency and storage crossover

At what tissue size and access distribution do page capacity, warm residency,
prefetch halo, compression, and dirty flush cadence dominate latency or storage wear?
Does the useful-byte optimum change between familiar text routes and broad novelty
routes?

### MYQ-0012 — Senescence and revival

Which rooted-use windows and hygiene cadence remove genuinely obsolete islands without
quarantining rare but useful routing, abstention, or identity tissue? How often does
revival outperform birth, and when does old calibration make revival harmful?

### MYQ-0013 — Shared multimodal tissue

After text ingress is connected, do text and image experiences produce shared routes,
transferable addressed patches, or only neighbouring modality-specific tissue? Which
matched controls distinguish shared grounding from common expression-side behavior?

## Merge, healing, and successor-planning questions

### MQ-0001 — Operational healing criterion

Which combination of reduced pathological output, task capability, retention,
transfer, representation health, and retrieval justifies calling a merge healed?
Which observations mean only transient suppression of one failure mode?

### MQ-0002 — Frozen continuation challenge

What smallest fixed experience reliably distinguishes checkpoints that look similar
now but differ in stability, plasticity, interference response, or readiness for a
later graft? Which path and endpoint artifacts must it preserve?

### MQ-0003 — Basin repeatability

Across repeated reconstructions or seeds, how many distinct behavioral,
representational, and continuation profiles appear after the same merge and healing
curriculum? Which properties are stable enough to guide selection?

### MQ-0004 — Multi-axis checkpoint selection

How should Sol compare current capability, stability, plasticity, interference
resistance, reacquisition cost, and continuation response without hiding tradeoffs in
one weighted score?

### MQ-0005 — Modular merge order

For language or subject specialists sharing one architecture, how do pairwise merge
order, healing order, translation bridges, and source balance affect retention and
later graft readiness? Does linguistic relatedness predict anything about coordinate
compatibility?

### MQ-0006 — Next-question choice

Does a bounded latent-iteration feasibility study or the four-language 150M visual-
birth preparation answer the more valuable next uncertainty? What prerequisite work
is required before either direction is scientifically commissionable?
