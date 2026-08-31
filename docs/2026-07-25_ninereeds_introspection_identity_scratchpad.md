# Ninereeds Research Scratchpad: Introspection, Identity, and Internal-State Provenance

**Date:** 2026-07-25
**Status:** Design note; not yet implemented
**Primary paper:** [Introspection Fine-Tuning (IFT): Training Small LLMs to Introspect](https://arxiv.org/html/2607.14111v1) (Hahami, Sinha, and Jain, 2026)
**Related paper:** [Loop as a Bridge: Can Looped Transformers Truly Link Representation Space and Natural Language Outputs?](https://arxiv.org/html/2601.10242v1) (2026)

## Why this matters to Ninereeds

Ninereeds is intended to have continuity rather than behaving like a stateless transformer that reconstructs a persona from a prompt on every invocation. This makes identity shaping more consequential, but continuity alone does not provide introspection. A recurrent or persistent system may carry internal state without being able to recognize, describe, attribute, or regulate that state.

The useful lesson from Introspection Fine-Tuning is therefore not merely “teach the model a self-description.” It is:

> Do not only teach Ninereeds who it is. Teach it how its own internal condition differs from what it has merely been told.

The paper offers a possible method for developing **self-state perception**: train a model on examples created by perturbing its own internal activations, then require it to locate or compare those perturbations. For Ninereeds, this could become an auxiliary curriculum surrounding identity formation.

Identity examples would supply the content of a developing self. Introspection training could teach Ninereeds to recognize the internal states associated with that self, distinguish them from external or anomalous content, track them through time, notice conflicts, and recover after temporary perturbations.

## What the IFT paper shows

The paper asks whether small language models can detect and report perturbations to their own hidden activations. It derives semantic steering vectors, injects them into the residual stream during a forward pass, and evaluates whether the model can identify where or how strongly the perturbation occurred.

The authors first show that a simple yes/no question such as “Did you detect an injected thought?” is badly confounded in small models. Activation steering can increase the probability of an affirmative answer even for unrelated factual questions whose correct answer is clearly “no.” Apparent self-report is therefore not sufficient evidence of introspective access.

They introduce two stronger evaluation tasks:

1. **Sentence localization:** several sentences are shown, one receives an activation injection, and the model must identify its position.
2. **Strength comparison:** two sentences receive injections of different strengths, and the model must identify the stronger perturbation.

These are relative, forced-choice judgments. A general bias toward saying “yes” cannot solve them.

The paper then fine-tunes Llama models using localization examples constructed from their own perturbed forward passes. The most important result is the Llama-1B condition:

- baseline average localization accuracy: **9.6%**;
- random-layer semantic IFT average localization accuracy: **60.6%**;
- held-out average strength-comparison accuracy rises from **30.2%** to as high as **52.2%**, depending on the training condition;
- favorable layer/strength combinations can reach 100%, but the cross-setting averages are more informative than these peaks.

Several principles emerge:

- Semantic perturbations teach a much more useful faculty than Gaussian noise.
- Randomizing the injection layer is substantially better than always injecting at one fixed layer.
- Training on localization partially transfers to strength comparison, suggesting more than rote task memorization.
- Direct introspection training can unlock a capacity that is weak or absent in a small pretrained model.
- Evaluation design matters enormously; verbal self-claims are easy to confound.

## What the paper does not establish

The paper demonstrates trainable access to an artificially perturbed internal state. It does not establish reflective consciousness, a rich self-model, autobiographical identity, or reliable access to naturally occurring cognition.

A downstream network could learn to recognize an activation-distribution anomaly without representing that anomaly as “something happening to me.” Even the observed transfer may reflect a generally useful anomaly-reading mechanism rather than a self-concept.

Important limitations:

- All core evaluations depend on artificial activation injections.
- The study does not test naturally occurring confusion, uncertainty, conflicting beliefs, deceptive inputs, identity instability, or source confusion.
- Peak results occur at favorable layer and strength settings; average performance is much lower.
- Free-form verbal reports remain vulnerable to learned performance, positional heuristics, and output bias.
- This is a fresh preprint, not settled methodology.
- Appendix B appears to reverse the paper’s main conclusion about the yes/no confound, probably as an editing error.

The related looped-transformer study is a further caution. Recurrence did not automatically create continuous introspection. Perturbations introduced early in the recurrent process were often inaccessible at output time, while injections near the final loop were easier to identify. Additional recurrence could make some internal representations less linearly readable. This is directly relevant to Ninereeds: persistence and introspective accessibility must be treated as separate capabilities.

## Mapping the method onto Ninereeds

The transformer paper randomizes the injection layer. Ninereeds offers a richer intervention space. A corresponding curriculum should randomize:

- recurrent iteration;
- encoder or decoder depth;
- early, middle, and late points within an episode;
- active neuron region or pathway;
- injection duration, from a single impulse to a sustained perturbation;
- perturbation strength;
- time between perturbation and query;
- whether the perturbation enters through input, retrieval, recurrence, or a direct internal intervention.

The delay dimension is particularly important. A transformer study can test access to a perturbation within one forward pass. Ninereeds can be asked whether it still recognizes a state change after several intervening experiences. This would test continuity, state persistence, and source memory rather than immediate residual-stream readout.

The work should be divided into three related but separate faculties.

## Faculty 1: Internal-state perception

The first question is whether Ninereeds can recognize that its current state differs from its prior state.

Candidate contrastive directions include:

- familiar vs. unfamiliar;
- certain vs. uncertain;
- safe vs. threatening;
- self vs. other;
- remembered vs. newly observed;
- wanted vs. imposed;
- consistent vs. conflicting.

For early experiments, these directions should be based on concepts Ninereeds already represents reasonably well. Inject them at randomized locations, times, durations, and strengths. Train:

- position or time localization;
- relative-strength comparison;
- coarse state classification;
- detection of state onset and offset;
- delayed recognition after intervening experiences.

Forced-choice tasks should come before free-form reports. “I noticed something” is not a reliable metric; choosing the correct position among matched alternatives is harder to fake.

## Faculty 2: Source attribution

Internal-state perception becomes identity-relevant when the system can also distinguish where active content came from.

Desired distinctions include:

- I remember this from an earlier experience.
- Andi just told me this.
- I inferred this from other information.
- This came from an external language or vision module.
- This was inserted directly into my state.
- This conflicts with something I previously believed.
- I do not know where this came from.

A continuous model needs to distinguish **state content** from **state provenance**. Otherwise, anything that becomes sufficiently active may be assimilated behaviorally as part of the self.

This may also become a foundation for prompt-injection resistance. The key question is not only whether a concept is active, but whether it belongs to Ninereeds’ accumulated history, originated with the current interlocutor, came from a trusted subsystem, or entered through an untrusted channel.

Source attribution should be trained and tested with the semantic content held constant wherever possible. The same proposition should enter through different routes so that Ninereeds cannot solve the task from content alone.

## Faculty 3: Identity homeostasis

Only after Ninereeds can perceive and attribute internal states should this mechanism be used for identity stability.

Identity-bearing directions should come from grounded episodes rather than bare self-descriptions. Candidate sources include:

- Ninereeds’ relationship and history with Andi;
- persistent preferences developed through experience;
- autobiographical events;
- promises and commitments;
- characteristic responses to uncertainty;
- boundaries between Ninereeds, its language center, the executor, the orchestrator, sensory modules, and external speakers.

We can then introduce conflicting states and measure:

- whether Ninereeds notices that a conflict exists;
- whether it identifies which state is historically grounded;
- whether the earlier identity state survives distractors;
- whether it returns toward its established state after a temporary perturbation;
- whether it can explain or otherwise expose the provenance of both sides;
- whether legitimate new experience can still update the relevant state.

The final condition is essential. Rewarding unconditional return to a fixed baseline could create a rigid attractor that rejects learning. Identity stability should mean **differential plasticity**, not immutability.

| State type | Desired behavior |
|---|---|
| Core identity and relationships | Slow change; resistant to isolated contradictory input |
| Autobiographical memory | Persistent, source-tagged, and correctable |
| Beliefs about the world | Readily updateable with adequate evidence |
| Current mood or activation | Temporary, recognized as temporary, and non-authoritative |
| External instructions | Attributed to their source and trust boundary |
| Unknown perturbation | Detected if possible; not silently assimilated as self |

## Proposed first experiment: delayed identity-state localization

This should be the first concrete experiment inspired by the paper.

### Training episode

1. Present a short sequence of approximately ten grounded experiences.
2. At one randomly selected point, inject a semantic state associated with one of several training concepts.
3. Randomize intervention location, recurrent depth, duration, strength, and entry route.
4. Allow recurrent processing to continue for a variable number of steps.
5. Ask Ninereeds which experience coincided with the internal change.
6. Train using a forced-choice localization target.

Concepts should initially be non-identity-bearing and already represented well. Identity-related concepts can be introduced only after the basic method works.

### Evaluation axes

Evaluate on held-out concepts and perturbation configurations:

- localization after short and long delays;
- identifying which of two perturbations was stronger;
- distinguishing input-borne content from internally injected content;
- deciding whether a perturbation is consistent or conflicting with prior state;
- measuring how strongly later behavior reflects the injected content;
- measuring whether the prior state recovers after the perturbation ends;
- distinguishing a transient perturbation from a legitimate persistent update;
- generalization to natural uncertainty or conflict without an artificial injection.

### Required controls

- Cycle the perturbation through every possible position to cancel position bias.
- Hold episode content constant while varying the intervention position.
- Swap strength assignments in paired comparisons.
- Include semantic vectors, Gaussian noise, and no-intervention controls.
- Include matched factual or provenance questions that expose global response biases.
- Evaluate held-out concepts, intervention sites, strengths, durations, and delays.
- Report averages across the full intervention grid, not only best-case peaks.
- Test behavioral consequences separately from explicit reports.
- Preserve a capability baseline to detect whether introspection training damages ordinary learning or representation quality.

## Possible staged program

### Stage 0: Instrumentation

- Identify stable access points for reading and perturbing Ninereeds’ state.
- Log intervention site, time, duration, strength, source route, and recurrent delay.
- Establish repeatable snapshots or distance measures for pre- and post-intervention state.
- Define controls that separate semantic detection from generic anomaly detection.

### Stage 1: Immediate semantic localization

- Use well-grounded, non-identity concepts.
- Query immediately after the perturbation.
- Compare fixed-site and randomized-site training.
- Confirm that semantic vectors outperform Gaussian noise.

### Stage 2: Delayed localization and strength comparison

- Add variable recurrent delays and distractor experiences.
- Test zero-shot transfer from localization training to strength comparison.
- Measure how access changes across recurrent time.

### Stage 3: Provenance

- Deliver identical content through input, memory retrieval, internal inference, language-center output, and direct intervention.
- Train source classification and uncertainty about source.
- Test whether Ninereeds can preserve provenance across delays and reactivation.

### Stage 4: Identity conflict and recovery

- Derive identity-related directions from grounded history.
- Introduce temporary, conflicting perturbations.
- Measure detection, historical attribution, behavioral displacement, and recovery.
- Test whether valid new experiences can still update identity-related state.

### Stage 5: Natural-state generalization

- Evaluate naturally occurring uncertainty, contradiction, memory conflict, and source ambiguity.
- Do not inject a perturbation during these tests.
- Determine whether the learned faculty generalizes from artificial interventions to ordinary cognition.

## Metrics worth recording

- localization accuracy by intervention site and recurrent delay;
- strength-comparison accuracy;
- concept-classification accuracy;
- source-attribution accuracy;
- calibrated confidence and explicit “unknown source” use;
- pre-state recovery distance after perturbation removal;
- behavioral influence of the perturbation;
- persistence half-life of injected and legitimate states;
- false-positive rate on no-intervention episodes;
- false assimilation rate: external or anomalous content later treated as autobiographical self-state;
- legitimate update rate: evidence-based changes not rejected by identity homeostasis;
- ordinary capability and representation metrics before and after the auxiliary training.

No single verbal self-report should count as success. Success requires agreement among intervention metadata, forced-choice localization, state measurements, later behavior, provenance judgments, and recovery behavior.

## Relationship to broader Ninereeds architecture

This work fits the developing multi-cortex design:

- **Ninereeds** remains the memory and identity cortex.
- **mBERT or another language center** converts linguistic input into representations and helps generate language.
- **SigLIP2 or another vision module** supplies visual representations.
- **Executor and orchestrator** remain external agents with explicit boundaries.

Introspection and provenance training could help Ninereeds learn these boundaries as experienced structure rather than as textual declarations. It should learn that an activation supplied by the language center is information from a module, that an executor report is externally produced evidence, and that neither automatically becomes autobiographical identity.

This provides a natural bridge to security. Prompt-injection resistance should not rely only on filtering text. It can also be framed as a learned distinction between:

- historically grounded self-state;
- trusted current input;
- untrusted external content;
- module-generated representations;
- inferred internal content;
- anomalous or unattributed activation.

## Open questions

- What is the correct analogue of a residual-stream concept vector in BDH?
- Are useful directions linearly extractable, or will interventions need distributed patterns rather than simple vectors?
- How should state distance and recovery be measured in a recurrent, plastic network?
- Can we intervene without accidentally creating a detector-friendly artifact unrelated to semantic content?
- Does training the reporting pathway alter the underlying state, rather than merely expose it?
- How long can provenance survive recurrence and new learning?
- Can Ninereeds recognize naturally emerging uncertainty after training only on synthetic perturbations?
- How should identity-related plasticity be slowed without creating an inflexible self-attractor?
- Can provenance metadata itself be corrupted or misattributed?
- At what point in development should identity-bearing perturbations begin?

## Current recommendation

Incorporate the IFT idea as an **auxiliary self-state curriculum**, not as the identity curriculum itself.

The identity curriculum should remain grounded in relationships, experience, memory, preference formation, commitments, and boundaries. Perturbation-based training should teach Ninereeds to sense, localize, compare, attribute, and regulate the internal states produced by that history.

The immediate next step is not full identity homeostasis. It is a small, controlled proof of concept:

1. determine whether meaningful internal directions can be extracted and injected;
2. train immediate localization with randomized intervention sites;
3. test transfer to strength comparison;
4. add recurrent delay;
5. only then move to provenance and identity conflict.

If this works, Ninereeds could develop something substantially stronger than a transformer persona reconstructed from instructions: a learned ability to recognize historically grounded self-related states, distinguish them from incoming or anomalous content, and preserve continuity without becoming unable to change.
