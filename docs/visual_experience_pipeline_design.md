# Visual Experience Pipeline Integration Design

Status: implementation contract; runtime commissioned, pipeline not yet enabled.

This document describes how NineReeds should gain a visual teaching tool after
the foundational bootstrap. It is intentionally specific enough that a future
implementation session can begin from repository changes rather than having to
reconstruct the design discussion.

The visual path is not a second curriculum whose purpose is merely to make
NineReeds multimodal. It is another way for the autonomous training system to
construct an experience. If the strategic orchestrator judges that a concept is
best taught through a picture, a sequence of cards, a picture book, or
kamishibai, it should be able to request that experience. The executor turns
that request into a bounded, machine-checkable specification; the trainbox
renders and validates the assets; the MSM presents them; Cortex learns from the
experience; and later evaluations tell the orchestrator whether the visual
choice actually helped.

The normal path must not require the user to write prompts, count anatomical
features, approve individual pictures, or choose a modality. Human involvement
is reserved for policy, licensing, safety, resource, and checkpoint-promotion
sentinels.

## Commissioning boundary

Do not start visual weight integration in the middle of the foundational
bootstrap. The heavy runtime may remain installed and offline-probed, but the
first visual learning experiment begins only after:

1. the foundational bootstrap is complete;
2. its language-only checkpoint and evaluation report are archived;
3. a reproducible language-retention suite is available; and
4. the control plane can run visual jobs without bypassing its global worker
   lock and renewable lease.

This gives every visual experiment a clean language-only baseline and makes
regressions attributable. The deployed models and trainbox evidence are
documented in `docs/visual_toolchain_bootstrap.md` and
`docs/visual_toolchain_trainbox_2026-07-29.md`.

## Ownership

The responsibilities are deliberately separated:

| Component | Responsibility |
|---|---|
| strategic orchestrator | chooses the teaching goal, modality, and reason for using it |
| executor | converts the request into a finalized, bounded experience plan |
| visual pack worker | generates candidates, validates them, and emits an immutable pack |
| MSM experience compiler | turns the accepted pack and teaching plan into ordered learner events |
| Cortex trainer | executes the authorized learning block |
| evaluator | measures learning, transfer, retention, and modality ownership |
| experience ledger | records which type of experience worked, independently of operational job state |
| control ledger | records plans, claims, leases, receipts, reports, and artifacts |

The orchestrator may choose among at least these presentation modes:

- text conversation;
- narrated observation;
- a single image;
- an image and separately supplied caption;
- a multi-card grounded sequence;
- a picture book;
- kamishibai;
- a mixed-modal episode with observation, dialogue, recall, and assessment.

Visual presentation should be chosen only when it has a plausible pedagogical
advantage. The experience ledger must eventually let the orchestrator learn
when that is true rather than developing a blanket preference for images.

## End-to-end flow

The intended control flow is:

```text
curriculum state + evaluations + experience ledger
                         |
                         v
              strategic orchestrator
        chooses goal, modality, and rationale
                         |
                         v
                     executor
         finalizes visual_experience_plan_v1
                         |
                         v
             visual_pack control plan
       FLUX candidates -> mechanical checks
            -> Gemma semantic validation
            -> pack-wide continuity audit
                         |
                         v
        immutable visual_pack_manifest_v1
                         |
                         v
              MSM experience compiler
             emits msm_experience_v1
                         |
                         v
             authorized Cortex block
                         |
                         v
      learning + transfer + retention evaluation
                         |
                         v
                 experience ledger
```

Asset generation, learner training, and evaluation are separate plans with
separate receipts. A completed image pack is an input to a later Cortex plan;
creating a pack never authorizes a weight update or checkpoint promotion.

## Contracts

The implementation should add versioned JSON Schemas and deterministic
finalizers. The names below are proposed contracts, not files that already
exist.

### `visual_experience_plan_v1`

This is the executor's finalized request. It describes educational intent, not
model-specific tensor details.

Required top-level fields should include:

- stable plan and campaign identifiers;
- teaching goal and target concepts;
- assumed prerequisites;
- why the selected modality is expected to help;
- presentation format;
- learner language or languages;
- style and scene-complexity profiles;
- an ordered list of cards or pages;
- learner interactions and assessments;
- candidate, retry, wall-clock, GPU, and storage budgets;
- provenance and license requirements.

Each card or page should contain:

- a natural-language scene specification;
- the few visible facts essential to the lesson;
- forbidden *prominent* facts only when they could change the lesson;
- canonical narration or caption text;
- continuity references to recurring people, animals, objects, and locations;
- the intended observation, question, reveal, correction, or recall timing;
- accessibility text derived from the canonical specification.

Do not turn the schema into a universal anatomy ontology. A request for “a dog
running in the rain” does not need `heads: 1`, `legs: 4`, `tails: 1`, and an
ever-growing list of biological constraints. Normal-world correctness belongs
to an intelligent multimodal judge. Explicit counts belong in the plan only
when they are pedagogically or narratively material, such as “three apples in
Taro's basket.”

Canonical text is always stored separately from the pixels. Generated writing
inside an image is not a source of truth.

### `visual_pack_manifest_v1`

An accepted pack is immutable and content-addressed. Its manifest should record:

- plan ID, pack ID, status, and schema version;
- every asset's content hash, dimensions, media type, and relative store path;
- generator model ID, immutable revision, inference configuration, prompt,
  seed, and attempt history;
- validator model ID, immutable revision, rubric version, structured results,
  and rejection reasons;
- canonical captions, narration, and card order;
- continuity and pack-level audit results;
- source, license, attribution, and transformation history;
- creation time and control-plan receipt references.

Rejected candidates remain out of training inputs. Their compact reports may be
retained for generator and judge qualification; retaining their full pixels is
subject to a bounded debugging policy.

### `msm_experience_v1`

Do not silently stretch the current text-only `msm_script_v1` contract. Add a
versioned multimodal event envelope. Its ordered event types should initially
cover:

- `observe_image`;
- `hear_or_read_text`;
- `page_turn`;
- `ask`;
- `teacher_correction`;
- `delay`;
- `recall`.

Events reference an accepted asset hash or canonical text record. SigLIP
activations are derived data and are never embedded in the plan. This keeps the
experience reproducible when an encoder or preprocessing experiment changes.

## Asset store

Images do not belong in Git, inline control-plan payloads, or the control
ledger's 256 KiB JSON envelope. Add a safe, content-addressed trainbox store,
for example:

```text
/home/aomukai/.local/share/ninereeds/visual/
  objects/<sha256>
  packs/<pack_id>/manifest.json
  reports/<control_plan_id>.json
```

The actual root should be configured rather than assumed. The worker must
resolve all paths beneath that approved root, reject traversal and symlinks
that escape it, verify hashes on read, and write through temporary files plus
atomic rename. Plans and reports carry only identifiers, hashes, and bounded
metadata. Workstation previews are copies of accepted assets, not the
authoritative store.

Idempotency rules:

- replaying a completed request returns the existing verified manifest;
- an interrupted request resumes from verified completed items;
- the worker never overwrites an object with conflicting bytes;
- pack finalization is atomic;
- a manifest cannot become accepted until all required assets and audits pass.

Curated datasets and later Booksie material should enter through source
adapters that produce the same normalized manifest. Every imported item needs
item-level provenance, license, attribution, caption source, and validation
status. Availability on a website is not itself permission to copy or train on
the material.

## Trainbox scheduling and control-plane integration

Add a `visual_pack` plan kind to the durable control ledger and implement it in
the existing trainbox worker. Do not create an independent image-generation
daemon that can collide with Cortex training.

The visual worker path must:

1. use the same global trainbox worker lock;
2. claim a bounded plan and renew its lease during long inference;
3. support shadow mode before live mode;
4. validate a strict payload schema;
5. enforce per-item and per-pack candidate, retry, time, GPU, disk, and output
   limits;
6. unload one heavyweight model before loading the next;
7. write durable receipts, reports, and artifact hashes;
8. expose deterministic fake backends for tests;
9. fail closed on missing revisions, provenance, validators, or storage.

The trainbox has two 12 GB GPUs and Cortex uses both. The initial operational
profile is therefore serial:

1. load FLUX on the qualified device profile and generate candidates;
2. unload it;
3. run mechanical checks and the Gemma judge;
4. unload the judge;
5. extract or cache SigLIP features when requested;
6. unload it before a Cortex block acquires both GPUs.

The currently qualified Gemma smoke path is BF16 on CPU. A future GPU or
quantized judge profile must be separately qualified before it becomes the
production validator. Model residency is an optimization to consider only
after correctness and scheduling isolation are established.

## Candidate validation

Validation answers three distinct questions:

1. **Content:** does the image show what the plan requested?
2. **Correctness:** is the depicted world coherent rather than malformed?
3. **Cleanliness:** are irrelevant details and visual distractions appropriate
   to the requested complexity profile?

Style compliance is a fourth axis, not a substitute for the first three.
Photorealistic, clean educational illustration, watercolor picture-book art,
paper-cut collage, and other qualified profiles may all be useful. Each profile
needs its own acceptance examples because “clean” means something different in
a single-object probe and a detailed story scene.

### Per-candidate checks

The initial validator should perform:

1. decode, corruption, dimensions, aspect ratio, and gross blur checks;
2. duplicate and near-duplicate detection;
3. unwanted writing, watermark, logo, and border checks;
4. a blind Gemma description before showing Gemma the requested scene;
5. structured comparison of that description and the scene specification;
6. a second explicit judgement of content, correctness/malformation,
   cleanliness, and style;
7. a concise evidence-bearing rejection reason for every failed axis.

Use hard gates rather than averaging away a serious defect. A beautiful image
with a six-legged dog is rejected. A correct dog that is lost in irrelevant
clutter fails a low-complexity probe. Uncertainty is a rejection or bounded
secondary-review result, never an automatic pass.

An anatomical or structural defect normally triggers a fresh generation.
Editing is allowed only for qualified, localized repair cases and the repaired
image must pass the complete validation pipeline again.

### Pack-wide checks

Individually acceptable images can still make a bad lesson. Before finalizing a
pack, audit:

- identity and appearance continuity across cards;
- object counts and state transitions;
- spatial and temporal coherence;
- style, palette, and reading-order consistency;
- caption-image alignment;
- accidental answer leakage;
- duplicates and overly similar alternatives;
- visual shortcuts that let the learner guess without acquiring the concept;
- requested diversity across people, settings, viewpoints, and styles.

### Judge qualification

Gemma is a fallible component, not an oracle. Before autonomous use, qualify
the exact judge revision and rubric against a human-labelled set containing
clean examples, subtle semantic mismatches, malformed anatomy, count errors,
clutter, unwanted text, continuity failures, and multiple art styles.

Track false acceptance as the critical safety metric, along with false
rejection and accepted images per GPU-hour. Periodically send a bounded sample
to a second qualified judge or human audit to detect drift. SigLIP similarity
may be logged as a diagnostic or retrieval signal, but it must not be the main
acceptance judge for data that will train the SigLIP-facing learner; that would
make the gate too circular.

## How NineReeds receives images and text

SigLIP2 is a visual encoder, not an OCR transcript channel. It may encode some
visual evidence associated with writing, but it does not reliably emit the
exact sentence on a picture-book page. Text must therefore travel through the
existing text receptor as canonical text.

For generated lessons, compose the page from two independent sources:

- an accepted illustration supplied to SigLIP2;
- exact narration, caption, or dialogue supplied to mBERT.

If a later imported book contains baked-in text, OCR is an ingestion aid. Its
output must be checked against the source and stored as canonical text; the
learner still receives pixels and text as separate synchronized events. This
also enables multilingual editions to reuse an illustration without asking an
image generator to spell Japanese, Chinese, German, or English correctly.

## SigLIP2-to-Cortex design

Add a frozen SigLIP2 NaFlex receptor analogous in ownership to the current
frozen mBERT receptor. Preserve spatial information instead of reducing every
image to one similarity vector:

- use patch-level hidden states;
- add a small trainable projector and bounded resampler;
- attach modality, two-dimensional position, card/page, and episode metadata;
- begin with a small fixed visual observation budget and increase it only with
  evidence;
- mask padding and preserve variable-aspect NaFlex preprocessing metadata.

Text continues through mBERT. The core receives synchronized but distinguishable
visual and textual observations. LFM continues to receive only NineReeds'
intentions; it must never receive the source image, caption, correct answer, or
teacher evidence directly. Otherwise a fluent response could hide that
NineReeds never learned the visual concept.

Cache frozen receptor activations under a key containing:

- asset content hash;
- SigLIP model ID and immutable revision;
- processor revision and preprocessing configuration;
- selected layer and resampling configuration.

Changing any part of that key creates new derived data rather than silently
reusing incompatible features.

## Learning progression after bootstrap

The first stages are interface and ownership tests, not a rush into elaborate
books:

### Stage 0 — Baseline archive and interface probes

Archive the final language-only checkpoint. Verify masks, shapes, projector
gradients, caching, replay, deterministic event ordering, and that LFM cannot
see source evidence.

Example experiences: a red ball versus a blue ball; one familiar dog; one
familiar cat; an object on versus under a table.

### Stage 1 — Grounded known concepts

Show concepts NineReeds already understands in language. Freeze the core at
first and train only the visual projector/resampler so vision learns to address
existing concepts rather than rewriting them.

Use image-only, text-only, image-plus-text, swapped-caption, and unseen-style
conditions. Examples include dogs and cats across photographs and illustrations,
colors, familiar household objects, and simple actions.

### Stage 2 — Simple captioned pages

Introduce one relation or event per page with exact separately supplied text.
Ask observation questions before giving corrections. Test delayed recall and
cross-style transfer.

Examples: “The monkey is sitting on a rope,” “The monkey is in an enclosure,”
and “The monkey is licking a stick,” while avoiding reliance on text rendered
inside the image.

### Stage 3 — Multi-card grounded stories

Teach state changes, causality, perspective, order, and small quantities across
cards. Gently unfreeze the core only after projector-only grounding works, and
mix language replay into every visual learning block.

The existing
`training_data/pre_c16/02_thinking/grounded_stories/` material is a natural
source. For example, `story_01` can become cards showing Biscuit at the old oak,
Taro climbing toward the squirrel hole, an acorn falling, Emma holding it,
Taro explaining that it is a seed, and the wind dropping another nut.

### Stage 4 — Picture books and kamishibai

Let the orchestrator choose a longer visual form when it adds leverage. These
experiences can combine narration, page turns, questions before reveals,
corrections, and later recall.

Example arithmetic kamishibai:

1. Taro places three apples in a basket for Gran's pie.
2. Emma arrives with two more apples.
3. The learner is asked how many apples Gran has before the answer page.
4. The next card reveals five apples and explains `3 + 2 = 5`.
5. A later scene changes order to test `2 + 3`, followed by delayed recall in a
   different visual style.

The important target is the arithmetic relation, not memorizing an apple
layout, character pose, caption, or art style.

## Evaluation and promotion gates

An asset passing validation means only that it is usable. It does not mean the
experience taught anything. Evaluate these independently.

Every visual campaign needs matched controls where practical:

- the same teaching content as text only;
- image only;
- aligned image and text;
- image with swapped or contradictory text;
- familiar content in an unseen style;
- delayed recall after intervening non-visual training;
- transfer to a novel object, arrangement, or wording.

Promotion gates should cover:

- above-chance known-concept grounding from image-only evidence;
- reliable caption-swap and contradiction sensitivity;
- cross-style rather than generator-style memorization;
- improved learning or retention relative to the matched text-only experience;
- no material loss on the archived language-retention suite;
- evidence that the Cortex core, not an LFM shortcut, owns the answer;
- acceptable visual-pack false-accept rate and generation yield;
- reproducible receipts, manifests, hashes, and model revisions.

No visual campaign automatically promotes its checkpoint. It produces an
evaluation report for the existing checkpoint decision path.

## Experience-ledger feedback

The experience ledger should record pedagogical outcomes separately from
control-plane success:

- teaching goal and prerequisite state;
- selected modality and the orchestrator's rationale;
- format, style, scene-complexity, and language;
- generator and judge revisions;
- candidate count, acceptance yield, and failure categories;
- matched-control results;
- immediate acquisition, transfer, delayed recall, and retention effects;
- whether the modality should be reused, revised, or avoided for similar goals.

This lets the orchestrator learn that a five-card spatial story may help one
concept while a short conversation works better for another. Operational
lessons are promoted only after repeated evidence, following the general rules
in `docs/experience_ledger.md`.

## Failure and escalation policy

The autonomous path stops safely when:

- retry or resource budgets are exhausted;
- validators disagree beyond the allowed policy;
- a required fact cannot be depicted reliably;
- unsafe, malformed, or provenance-free content appears;
- a model or rubric revision differs from the qualified revision;
- disk headroom crosses the configured floor;
- leases cannot be renewed or the worker loses its global lock;
- pack continuity fails after bounded regeneration;
- language retention or ownership tests regress.

These are machine-readable failed reports, not invitations to keep generating
indefinitely. Routine failures return to the orchestrator for a different scene,
style, modality, or teaching strategy. The user is brought into the loop only
for a policy decision, new license, changed resource ceiling, unresolved safety
case, or checkpoint promotion that already requires human authority.

## Implementation sequence

Implementation should proceed in this order after the commissioning boundary:

1. add the three schemas, deterministic finalizers, and fixture examples;
2. add the safe content-addressed store and resolver;
3. add `visual_pack` to the control-plan kinds and worker in shadow mode;
4. implement fake generator and fake judge backends with failure injection;
5. test claims, renewable leases, interruption/resume, idempotency, storage
   limits, and receipts without loading models;
6. wire the pinned FLUX and Gemma backends and qualify the validation rubric;
7. add frozen SigLIP2 extraction, cache keys, projector, and resampler;
8. add `msm_experience_v1` compilation and event execution;
9. run Stage 0 and Stage 1 shadow experiments against the archived baseline;
10. enable bounded live Cortex blocks only after retention and ownership gates;
11. enable autonomous orchestrator modality selection only after matched
    experience evidence exists.

Likely repository touchpoints include:

```text
training/pipeline/visual/visual_experience_plan_schema.json
training/pipeline/visual/visual_pack_manifest_schema.json
training/pipeline/visual/msm_experience_schema.json
training/pipeline/visual/store.py
training/pipeline/visual/generate.py
training/pipeline/visual/validate.py
training/pipeline/control/ledger.py
training/pipeline/control/trainbox_worker.py
training/pipeline/control/orchestrator_supervisor.py
training/pipeline/cortex/siglip2.py
training/pipeline/cortex/student.py
training/pipeline/cortex/config.py
tests/test_visual_experience_schema.py
tests/test_visual_store.py
tests/test_visual_pack_worker.py
tests/test_visual_validation.py
tests/test_cortex_siglip2.py
```

Names may be adjusted to the repository layout at implementation time, but the
separation of contracts, immutable assets, validation, scheduling, learner
events, and educational evaluation should remain.

## Definition of done

The visual tool is integrated when the orchestrator can autonomously choose a
visual experience for a teaching goal; the executor can finalize it without
unbounded prose; the trainbox can produce a fully validated, reproducible pack
under the shared worker lease; the MSM can present synchronized images and
canonical text; NineReeds can demonstrate ownership and transfer; and the
experience ledger can tell the orchestrator whether the visual choice was
educationally worthwhile.

Installed models and a successful red-ball render are prerequisites. They are
not, by themselves, completion of this pipeline.
