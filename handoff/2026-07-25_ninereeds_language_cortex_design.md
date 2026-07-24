# Ninereeds Language Cortex Design

**Date:** 2026-07-25
**Status:** Architectural direction and experiment plan; not yet assumed to be implemented
**Purpose:** Preserve the language-cortex discussion in a form that can be placed in the Ninereeds repository and checked against the actual codebase by Codex.

## Executive summary

Ninereeds should not have to learn language from raw token IDs while also learning cognition, memory, identity, and continual adaptation. Instead, it can grow up with specialized frozen modules as ordinary parts of its anatomy:

- **mBERT** is the leading choice for its permanent receptive language cortex.
- **Ninereeds/BDH** remains the plastic cognitive core: memory, identity, belief revision, integration, intention, and continual learning.
- **LFM2.5-230M** is the leading provisional speech generator, converting Ninereeds' intended response states into fluent text.
- **SigLIP2** remains the corresponding frozen visual cortex.
- Small learned projections connect unlike tensor widths, but a permanent mBERT-to-Ninereeds projection is an afferent pathway, not a replaceability adapter.

The desired anatomy is:

```text
text
  ↓
frozen mBERT
  ↓ contextual token activations
permanent afferent projection
  ↓
Ninereeds / BDH
  ↓ intention state
replaceable egress adapter
  ↓
frozen LFM2.5-230M
  ↓
generated speech
```

And, in parallel:

```text
image
  ↓
frozen SigLIP2
  ↓ visual features
visual projection
  ↓
same Ninereeds / BDH
```

This is a multi-cortex developmental architecture, not a collection of skills bolted onto an already complete language model.

## Core architectural principle

Ninereeds should be the locus of:

- persistent memory;
- identity and personal continuity;
- belief formation and revision;
- cross-modal integration;
- uncertainty and provenance;
- response intention;
- plasticity and lifelong development.

Attached modules may perceive, transform, calculate, retrieve, or verbalize. They must not quietly become substitute thinkers.

The system should learn from the beginning that experience arrives through specialized organs. Later modules for sound, arithmetic, spatial processing, tabular data, formal reasoning, or control should therefore feel anatomically normal rather than externally bolted on.

## Why mBERT is now the leading receptive language cortex

### Bidirectional linguistic perception

mBERT contextualizes every token using the complete utterance. This is a better fit for receptive language than a causal generator whose earlier token states cannot see later qualifications or negations.

For example:

```text
I thought the chair was wooden, but it is not.
```

mBERT can represent `chair`, `wooden`, and `not` in light of the whole utterance. A causal model would initially form partial states and revise them as the remaining words arrive.

### Useful scale and coverage

mBERT is approximately 178M parameters, produces 768-dimensional hidden states, and covers 104 languages. It includes all four initial Ninereeds languages:

- English;
- German;
- Japanese;
- Traditional Chinese.

At this scale, reducing the receptor further with a distilled sentence encoder would save relatively little while introducing another architectural choice. Declaring mBERT permanent anatomy is acceptable.

Its broad language coverage may also become valuable later, even if Ninereeds is initially trained primarily in four languages.

### Token-level detail

mBERT naturally exposes contextual token states:

```text
[batch, token_count, 768]
```

This preserves more linguistic structure than relying only on a pooled sentence vector. Ninereeds can receive an utterance as a sequence of contextual observations rather than one compressed semantic summary.

### Important limitation

mBERT's multilingual spaces are not perfectly language-neutral. Cross-lingual convergence must be measured rather than assumed. The four-language corpus, translations, paraphrases, and structural contrasts are therefore still essential teaching material.

## Why LaBSE and LEALLA are not the default

LaBSE and its smaller LEALLA descendants are attractive because they were trained explicitly to align translations across many languages. They may be useful as:

- diagnostic controls;
- cross-lingual alignment teachers;
- comparison models;
- sources of optional auxiliary losses.

They are not the default receptive cortex because:

- mBERT is already small enough for the hardware;
- mBERT provides a straightforward token-level linguistic stream;
- sentence-alignment objectives may compress away distinctions involving negation, speaker, quotation, evidence, emphasis, or clause structure;
- beginning with two receptive encoders would complicate the first experiment unnecessarily.

Full LaBSE is also much larger than needed for the initial system. LEALLA remains an interesting experimental control, not required anatomy.

## Why LFM2.5-230M remains useful

mBERT cannot generate text. Ninereeds still needs a small, fluent, multilingual decoder capable of expressing an internally chosen intention.

LFM2.5-230M is the leading provisional speech centre because it is:

- small;
- fast;
- multilingual;
- autoregressive;
- compatible with projected virtual tokens or embeddings in principle;
- large enough to provide surface fluency without being asked to own cognition.

The canonical scientific checkpoint should be the original LiquidAI BF16 model:

- <https://huggingface.co/LiquidAI/LFM2.5-230M>

The Unsloth repository may be useful for optimized loading, fine-tuning infrastructure, or deployment:

- <https://huggingface.co/unsloth/LFM2.5-230M>

For activation and interface experiments, begin with the official LiquidAI weights and configuration. An optimized Unsloth loading path is acceptable only after verifying that it exposes equivalent hidden states and does not alter the behaviour relevant to the experiment.

LFM is provisional and replaceable. Ninereeds should not encode its identity or memory in LFM-specific geometry.

## Permanent receptor versus replaceable voice

The current design is intentionally asymmetric.

### Receptive side

mBERT is allowed to become a fixture of the system. Ninereeds may grow up interpreting its activation patterns directly through a permanent learned projection.

If mBERT emits width 768 and Ninereeds consumes a different width, a learned transformation is still necessary:

```text
mBERT [tokens, 768]
  ↓ LayerNorm / linear or small MLP / optional resampler
Ninereeds [observations, core_width]
```

This is not an adapter whose purpose is to make arbitrary language models interchangeable. It is the permanent afferent connection between a fixed receptor and the cognitive core.

### Expressive side

The speech generator should remain replaceable:

```text
Ninereeds intention protocol
  ↓ model-specific egress adapter
current speech generator
```

A future generator should be attachable by training a new egress adapter without retraining Ninereeds' identity, memories, or cognitive structure from scratch.

## Relationship to SigLIP2

Teaching Ninereeds to interpret mBERT is the same general principle as teaching it to interpret SigLIP2:

```text
SigLIP2:
image → frozen visual processing → visual activations → projection → Ninereeds

mBERT:
text → frozen linguistic processing → contextual activations → projection → Ninereeds
```

The frozen module performs specialized perception. Ninereeds learns what those signals mean, relates them to prior experience, and integrates them into its own developing structure.

The important distinction is:

```text
The receptor supplies evidence.
Ninereeds learns, remembers, interprets, and decides.
```

## Training data and MSM

MSM (Mommy-Says machinery) should become the developmental environment that presents teaching episodes rather than merely replaying question-answer pairs.

It should control:

- curriculum and dependency order;
- speakers and turn boundaries;
- language;
- paraphrases and translations;
- delayed recall;
- corrections and belief revision;
- misleading similarities and boundary cases;
- observations that require no immediate response;
- uncertainty and clarification;
- cross-modal pairings;
- recurrence of people, places, and concepts;
- consequences of earlier decisions;
- consolidation or reflection periods.

Ordinary QA logs are useful but insufficient. A pure prompt-answer diet risks defining cognition as chat performance.

One source item should be transformable into several developmental episodes:

```text
Episode A: original statement and response
Episode B: paraphrase
Episode C: translation
Episode D: delayed recall after unrelated material
Episode E: analogous structure in a different domain
Episode F: misleading similarity where the old answer is wrong
Episode G: observation with no requested response
```

## Staged experiment plan

Do not train the complete perception–cognition–speech loop first. Establish each interface separately.

### Phase 0: repository audit

Before implementation, Codex should inspect the actual repository and identify:

- the current Ninereeds input representation and dimensionality;
- where token embeddings enter the BDH core;
- current sequence and batch shapes;
- existing projection or modality interfaces;
- current objectives and evaluation hooks;
- MSM's real implementation and data format;
- MRI and shaped-evaluation entry points;
- whether SigLIP2 work already establishes reusable conventions;
- GPU and cache assumptions in training scripts.

Do not assume the terminology in this note exactly matches current class or file names.

### Phase 1: frozen mBERT activation extraction

Run complete utterances through frozen mBERT without any text generation:

```python
with torch.no_grad():
    outputs = mbert(
        input_ids=input_ids,
        attention_mask=attention_mask,
        output_hidden_states=True,
        return_dict=True,
    )

language_states = outputs.hidden_states[selected_layer].detach()
```

Collect candidate representations from:

- embeddings;
- an early layer;
- a middle layer;
- a late layer;
- the final hidden layer.

Store speaker, language, utterance boundary, and episode metadata outside the encoder rather than hoping mBERT infers all of it.

### Phase 2: matched ingress campaigns

Add the smallest viable learned projection from mBERT states into the existing Ninereeds input width. Keep the rest of the training objective as unchanged as possible.

Run matched 25M experiments:

| Run | Ninereeds input |
|---|---|
| Baseline | Existing token representation |
| mBERT early | Early-layer contextual states |
| mBERT middle | Middle-layer contextual states |
| mBERT late | Late-layer contextual states |
| Optional control | LFM2.5 middle-layer causal states |
| Optional control | LEALLA token states and/or pooled anchor |

Use the same corpus, curriculum, initialization policy, training budget, and evaluation schedule wherever possible.

### Phase 3: establish an internal intention protocol

Once mBERT ingress clearly helps, train Ninereeds to produce a compact response-intention sequence:

```text
Ninereeds state
  ↓
K × core_width intention vectors
```

These vectors must not simply encode one memorized answer string. Train with:

- multiple acceptable paraphrases;
- four-language equivalents;
- explicit contrast cases;
- speech-act or task-state auxiliaries where useful;
- delayed and cross-context application.

The intended protocol should belong to Ninereeds, not to LFM.

### Phase 4: frozen LFM egress

Project Ninereeds' intention vectors into virtual LFM inputs:

```text
Ninereeds intention vectors
  ↓ egress adapter
virtual LFM embeddings or prefix states
  ↓ frozen LFM2.5-230M
generated response
```

During the decisive test, LFM must not receive the original user utterance. It may receive only:

- minimal role or generation markers;
- projected Ninereeds intention vectors;
- previously generated response tokens during autoregressive decoding.

This prevents an easy cognitive bypass in which LFM answers the question independently.

Verify:

- support for `inputs_embeds` or an equivalent injection route;
- correct convolutional and attention cache behaviour;
- gradient flow through the frozen network into the egress adapter and Ninereeds;
- successful expression of arbitrary new information not contained in LFM's prompt;
- language selection controlled by Ninereeds or explicit metadata.

### Phase 5: vision and cross-modal integration

After the language ingress is understood, align the SigLIP2 pathway with the same cognitive core. Test whether Ninereeds—not an external language model—forms the connection between visual and linguistic experience.

## Candidate objectives

The initial ingress experiment should retain the existing Ninereeds objective. Later stages may combine:

\[
\mathcal{L} =
\lambda_{\text{core}}\mathcal{L}_{\text{BDH}}
+
\lambda_{\text{text}}\mathcal{L}_{\text{text}}
+
\lambda_{\text{invariance}}\mathcal{L}_{\text{invariance}}
+
\lambda_{\text{memory}}\mathcal{L}_{\text{memory}}
+
\lambda_{\text{ownership}}\mathcal{L}_{\text{ownership}}
\]

Where:

- **BDH/core loss:** preserves existing sparsity, Hebbian, and structural behaviour;
- **text loss:** measures whether the frozen speech centre expresses the intended response;
- **invariance loss:** aligns translations and paraphrases without erasing meaningful differences;
- **memory loss:** requires information from earlier experiences rather than only the current utterance;
- **ownership loss or tests:** pressure the cognitive state to reside in Ninereeds rather than an attached module.

Do not activate every objective in the first experiment.

## Evaluation questions

### Ingress usefulness

- Does mBERT input improve Tier-1 concept formation?
- Do weak spines such as food, nature, emotion, and action improve?
- Are negation, reference, and clause relations learned more reliably?
- Does dependency order still matter?
- Does training converge faster or to better MRI structure?

### Cross-language structure

- Do EN/DE/JP/ZH equivalents activate compatible Ninereeds structures?
- Can knowledge taught in one language be recalled in another?
- Does mBERT's broad multilingual pretraining help without collapsing language-specific nuance?
- Does an optional LEALLA alignment target improve transfer enough to justify its complexity?

### Cognitive ownership

- Can Ninereeds answer when LFM never sees the original question?
- Can the speech generator be replaced while memories and identity remain intact?
- Can Ninereeds retain information across episodes where mBERT is stateless?
- Can it disagree with, qualify, or revise information encoded in the current utterance?
- Do nonverbal experiences affect later responses?
- Does removing the speech generator leave a coherent intention state?

### Generalization

- Do paraphrases converge without exact sentence memorization?
- Can a learned relation transfer to a new subject domain?
- Can Ninereeds reject a superficially similar but structurally different case?
- Can it preserve speaker and provenance distinctions?

## Caching and hardware

Frozen mBERT activations for a fixed corpus can be cached so repeated Ninereeds campaigns do not rerun the encoder.

Cache only selected layers or compressed states. Retaining every layer for the whole corpus would be wasteful.

The dual-RTX-3060 station should be capable of flexible scheduling:

- one GPU for frozen cortex inference or cached-activation production;
- one GPU for Ninereeds training;
- CPU, RAM, and disk for orchestration and caches.

Because mBERT, LFM2.5-230M, and the smaller Ninereeds variants are modest, some stages may share a GPU. This must be benchmarked rather than assumed, especially once optimizer state, activation retention, and longer sequences are included.

The executor model also competes for GPU capacity. Training runs and orchestration/executor inference may need explicit scheduling instead of permanent simultaneous residency.

## Safeguards against the attached model becoming the thinker

The architecture should enforce:

1. **Frozen receptor and generator weights.**
   Plasticity belongs primarily to Ninereeds and the connecting pathways.

2. **No original question at egress.**
   LFM receives only Ninereeds' intention, not the linguistic evidence from which that intention was formed.

3. **Persistent-state tests.**
   Tasks must require earlier experience unavailable to the stateless cortex modules.

4. **Cross-modal tests.**
   Answers should sometimes depend on information that never passed through the language receptor.

5. **Counterfactual module replacement.**
   Refit a second speech generator without retraining Ninereeds from scratch.

6. **Provenance metadata.**
   Ninereeds should distinguish Andi's statement, quoted material, external evidence, inference, and its own current belief.

7. **Calibration and uncertainty.**
   Specialist outputs are evidence, not unquestioned truth.

## Developmental interpretation

This architecture is not merely an efficiency trick.

A conventional foundation model begins as a text predictor and later receives tools or modalities. Ninereeds can instead develop with the expectation that cognition is distributed across specialized organs while identity and integration remain in a persistent plastic core.

A newly attached module should be experienced as a new sense or instrument. Ninereeds must learn:

- what its signals mean;
- when it is reliable;
- how it relates to existing experience;
- whether it conflicts with another source;
- what transformations it can perform;
- what conclusions remain Ninereeds' responsibility.

The philosophy of partial models is therefore embodied in the anatomy: no single cortex is the whole mind, including the language cortex.

## Current decisions

Treat these as the working direction unless repository evidence forces revision:

1. mBERT is the leading permanent receptive language cortex.
2. Use contextual token activations, not only pooled sentence embeddings.
3. A width-changing learned projection is expected and is considered permanent anatomy.
4. LFM2.5-230M is retained as the provisional replaceable speech centre.
5. Use the official LiquidAI BF16 checkpoint as the canonical LFM source.
6. Treat Unsloth as optional optimized tooling pending equivalence checks.
7. LaBSE/LEALLA are controls or optional teachers, not default cortexes.
8. SigLIP2 and mBERT follow the same frozen-perceptor principle.
9. Prove ingress usefulness before building egress.
10. Keep MSM broader than QA replay.
11. Ensure LFM never receives the original prompt in cognitive-ownership tests.
12. Do not assume every module must share one universal replaceability interface.

## Open questions for Codex

When this note is placed in the repository, Codex should answer these from the actual code:

1. Where is the least invasive insertion point for `[batch, tokens, 768]` mBERT states?
2. What is the current Ninereeds input width for 25M, 150M, and 604M configurations?
3. Can the existing token pathway remain available for matched baselines?
4. Does the BDH core consume token sequences directly, pooled units, or fixed-length chunks?
5. What metadata embeddings already exist?
6. What cache format best fits the present corpus tooling?
7. Which MRI and shaped-evaluation scripts can compare ingress runs automatically?
8. Can MSM already emit episode boundaries, speaker roles, translations, and delayed tests?
9. Is there existing SigLIP2 projector code worth generalizing?
10. Does the selected LFM implementation support virtual embeddings and frozen-model gradient flow?
11. How should GPU ownership be scheduled alongside the local executor?
12. What is the smallest experiment that can falsify the claim that mBERT improves Ninereeds' conceptual learning?

## Recommended first Codex task

Do not implement the full architecture immediately.

First:

1. audit the repository against this note;
2. map each concept here to actual files and classes;
3. identify incorrect assumptions;
4. propose the smallest mBERT-ingress experiment;
5. estimate cache size and GPU memory;
6. preserve the current token-input baseline;
7. define matched evaluation criteria before training.

The immediate research question is:

> Does a 25M Ninereeds form stronger, more transferable, and more multilingual conceptual structure when its language experience arrives as frozen bidirectional mBERT activations rather than through its current token representation?

Only a positive result justifies proceeding to intention states and LFM speech generation.
