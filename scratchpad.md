# Ninereeds Pipeline Scratchpad — 2026-07-11

Purpose: handoff note for the next Codex session inside the live Ninereeds repository.

This records architectural conclusions from discussion on 2026-07-11. It is not an implementation specification and must not override the repository. Start by comparing every section against the current files, schemas, scripts, services, prompts, and actual machine layout. Preserve working implementation where it is better than these notes; identify assumptions that have changed; then propose the smallest coherent set of revisions.

## Immediate instruction for the next Codex session

1. Read this note.
2. Inspect the live repository before editing anything.
3. Locate and read at least:
   - `pipeline.md`
   - `runbook.md`
   - `cold_start_phases.md`
   - `training/pipeline/start.sh`
   - the current orchestrator configuration and schemas
   - the Qwen/Gemma executor prompts and wrappers, if they exist
   - `msm_phase_runner.py`
   - `msm_orchestrator_status.py`
   - `wake_msm_orchestrator.sh`
   - Codex brake/status scripts and schemas
   - the Lab README, server, message implementation, and orchestration adapter
   - existing systemd units or service scripts
4. Produce a gap analysis before making broad changes:
   - what already matches this design;
   - what is only a stub;
   - what was built under obsolete assumptions;
   - what is missing;
   - what should not be changed yet.
5. Keep the system recoverable and auditable. Prefer bounded changes with tests and machine-verifiable receipts.

## Current intended architecture

The active design now has two LLM roles, not three.

### 1. Orchestrator

The orchestrator is either:

- OpenAI Codex using GPT-5.6 Sol; or
- Sakana Fugu through the separate `codex-fugu` installation.

Sol is the preferred orchestrator. Fugu is the fallback when Codex is approaching or inside a rate-limit cooldown. Fugu may also invoke Codex/Sol when appropriate. Only one orchestrator may own a decision boundary at a time.

The orchestrator owns strategy and policy only. It should wake at explicit boundaries, read a small canonical state packet, decide the next bounded action, write instructions, dispatch the executor, and exit. It should not generate large corpora, grade every ordinary turn, or remain awake through the tactical loop.

### 2. Executor

The executor is a local model on the training machine. Current candidates:

- `Qwen3.6-35B-A3B` — approximately 35B total parameters and 3B active, using the bookmarked IQ4_XS/MTP GGUF;
- `Gemma-4-26B-A4B-it-QAT` — 25.2B total and approximately 3.8B active, using the bookmarked QAT GGUF.

Both will be installed and tested. Quality wins; speed is secondary. The executor will use one RTX 3060 12 GB with partial RAM/CPU offload as necessary and approximately 32K context. Qwen has already been observed around 22 tok/s in the intended general configuration, which is adequate. Do not plan to pool both RTX 3060s for executor inference: the other GPU must remain available to Ninereeds training.

Executor selection is fixed for v1 after a controlled comparison. Do not implement automatic bandit/UCB routing. Compare script quality, grading reliability, structured-output validity, multilingual behavior, escalation judgment, consistency across repeated cases, false passes, and protected-anchor mistakes. False passes and missed anchor escalations are more costly than unnecessary escalation.

### 3. Trainer

The trainer is no longer a small Gemma model. It should be deterministic machinery, probably Python.

It executes an already-written chat script mechanically against Ninereeds, records the raw exchange, applies scripted correction/teacher lines where specified, records follow-ups, and writes clean artifacts. It must not grade, summarize, choose the next question, modify the script, or make policy decisions.

### 4. Harnesses

There are two persistent harnesses:

- Training harness on the training machine.
- Orchestration harness on the main workstation.

Both should eventually run as services. The Lab server should also run as a service. `systemd --user` is a likely fit; the headless training machine may need user lingering enabled so services start after boot without an interactive login. Verify the desired boot/login behavior before implementing.

`training/pipeline/start.sh` currently exists primarily as manual ignition/recovery: start the pipeline for the first time, reconcile after reboot or failure, or manually wake the orchestrator. It is presently a one-shot dispatcher, not the permanent daemon. Preserve it as a useful recovery entrance while deciding which logic belongs in the orchestration supervisor.

## Intended tactical loop

One executor task should be one model call so Qwen's thinking tokens do not accumulate indefinitely.

Conceptual loop:

```text
orchestrator writes bounded policy/plan
  -> training harness claims plan
  -> executor call: write one script
  -> deterministic trainer runs script against Ninereeds
  -> executor call: grade the result
  -> deterministic harness validates artifacts and transition
  -> executor may continue only within explicit auto-advance policy
  -> on failure or authority boundary, harness writes escalation report and stops
  -> orchestrator is awakened
```

The executor must not run an entire campaign inside one context. It receives only the relevant policy, vocabulary item, bounded attempt history, raw result, and exact schema for the current task.

## Communication channels

There are two distinct kinds of communication and they must not be conflated.

### Orchestrator ↔ executor

The orchestrator dispatches the executor through SSH or a script that uses SSH. The training harness runs executor jobs and the deterministic trainer. When local training for the current vocabulary item fails or reaches a policy boundary, the executor produces a structured report and stops. The harness captures/validates the output, creates the authoritative report artifact, and signals the orchestration side.

Preferred division:

- Durable state, plans, reports, hashes, and provenance travel through versioned files, probably Git/GitHub unless live testing shows a simpler reliable transport.
- SSH carries a small wake signal or plan/report ID, not the only copy of important content.
- A timer/poller is a recovery path if the wake signal is lost.

Potential symmetric handoff:

```text
orchestrator:
  write plan -> push durable plan -> SSH `ninereeds-run PLAN_ID`

training harness:
  pull/verify plan -> run bounded local loop -> write/push report
  -> SSH `ninereeds-wake REPORT_ID`
```

Do not lock this in without checking the existing Git topology and machine roles. Git push/pull may or may not be the most efficient final transport. The invariant is more important: the wake signal is disposable, while the plan/report is durable and idempotently recoverable.

Use restricted SSH keys/forced commands for autonomous signalling rather than unrestricted shells. A lost SSH signal should be recovered by a cheap deterministic timer that checks for unprocessed events without invoking an LLM during idle polls.

### Andi ↔ orchestrator

The Lab website replaces Hermes as the human communication surface.

- A message from Andi lands in the orchestrator inbox and wakes the orchestration harness.
- A message from the orchestrator lands in Andi's inbox and triggers a push notification.
- The Lab also provides chat when direct interaction is useful.

The Lab is the observer and human control plane: dashboard, timeline, reports, MRI, Atlas, decisions, messages, notifications, published checkpoint selection, and chat. It must not silently approve training updates or mutate training policy.

Hermes can be removed from the final architecture. It is one more model/daemon and potential failure point now that the Lab provides visibility, messaging, and notifications. Find and carefully retire obsolete Hermes assumptions only after the Lab communication path works.

## Wake, synchronization, and idempotency

The smooth handoff should behave as follows:

```text
primary wake: restricted SSH command or Lab message event
fallback wake: deterministic systemd timer/poller
source of truth: durable versioned artifacts
```

The orchestration entry point should eventually:

1. acquire a single-instance lock;
2. synchronize authoritative state;
3. validate the named event/boundary;
4. check provider rate limits and the Codex/Fugu brake;
5. claim the boundary atomically;
6. invoke the appropriate orchestrator at the appropriate reasoning effort;
7. validate the structured decision;
8. write/push the next plan or a blocked/human-attention state;
9. dispatch the training harness;
10. acknowledge the event and release the lock.

Every event/boundary needs a stable ID. Duplicate SSH calls, timer overlap, service restarts, delayed Git visibility, and rate-limit handoff must reduce to safe no-ops.

Suggested claim/receipt fields, subject to existing schemas:

```text
boundary_id
event_type
created_by
artifact_path
artifact_hash
parent_plan_id
claimed_by
claim_timestamp
lease_expiry
decision_status
decision_artifact
```

Sol and Fugu must never apply decisions to the same boundary concurrently. A rate-limit handoff should persist state, release or transfer the lease, and allow the fallback to claim the same boundary without repeating an already-applied update.

## Rate-limit monitoring and provider handoff

Codex 0.144.1 exposes machine-readable ChatGPT limits through `codex app-server` JSON-RPC:

```json
{"method":"account/rateLimits/read","id":6}
```

The response provides `usedPercent`, `windowDurationMins`, `resetsAt`, bucket IDs, and reached-limit state. Use the structured API as the eventual authority rather than scraping the `/status` TUI. The existing passive tmux/capture-pane watcher may remain as a temporary fallback while migration is tested.

Do not assume `primary` always means five hours and `secondary` always means weekly. Preserve `limitId` and classify windows by returned duration/metadata. `/status` displays remaining percentage; the API reports used percentage.

The harness should record, for each orchestration boundary:

- provider (`codex` or `fugu`);
- model;
- reasoning effort;
- boundary/failure type;
- starting and ending limit percentages;
- reset timestamps;
- wall time;
- token usage when available;
- whether effort escalation occurred;
- whether the higher-effort decision changed the action;
- executor work authorized and eventual outcome.

Start with conservative static brake thresholds, then calibrate from actual burn. The five-hour window naturally spaces work; the weekly window requires stronger protection. Eventually estimate the cost of the next boundary from rolling history before starting it.

Conceptual provider selection:

```text
Sol healthy -> run Codex/Sol
Sol constrained and Fugu healthy -> run codex-fugu
both constrained -> persist WAITING_FOR_ORCHESTRATOR and sleep
```

Do not treat hitting a limit as an exceptional crash. Finish only already-authorized safe local work, persist a clean boundary, and wait.

## Adaptive orchestrator reasoning effort

Executor reports should contain structured failure codes. The orchestration harness maps those codes to an initial Sol reasoning effort. Qwen may recommend an effort, but the local executor must not directly control expensive subscription consumption.

Possible initial mapping, to be revised from evidence:

```text
ROUTINE_POLICY_BOUNDARY       -> medium
REPEATED_SEMANTIC_FAILURE     -> medium
OFF_TOPIC_RESPONSE            -> medium
GRADING_UNCERTAINTY           -> high
ARTIFACT_CONFLICT             -> high
PROTECTED_ANCHOR_FAILURE      -> high
UPDATE_OR_PROMOTION_READY     -> high
PHASE_GATE_AMBIGUITY          -> high
POLICY_OR_ARCHITECTURE_CHANGE -> max
```

Most orchestration boundaries probably begin at medium. Higher effort is for ambiguous causal diagnosis or decisions with a large blast radius, not merely because the executor lacked authority.

Scripted Codex invocation is supported. Current intended shape:

```bash
codex exec \
  -C ~/Ninereeds \
  -m gpt-5.6-sol \
  -c 'model_reasoning_effort="medium"' \
  --output-schema training/pipeline/orchestrator_decision_schema.json \
  -o training/pipeline/msm/state/latest_orchestrator_decision.json \
  "Process the pending orchestration boundary."
```

Verify exact effort spellings against the installed CLI/schema before implementation.

The decision schema should permit a no-mutation escalation result:

```json
{
  "action": "ESCALATE_EFFORT",
  "requested_effort": "high",
  "reason": "The evidence supports multiple incompatible explanations.",
  "missing_or_conflicting_evidence": [],
  "state_changes_applied": false
}
```

The harness must verify that escalation applied no state change, check the provider brake, and start a fresh invocation on the same immutable boundary packet. Suggested strict ladder:

```text
medium -> high -> max -> human
```

No repeated attempt at the same effort, no downward retry, and no unbounded self-escalation. Ultra is probably inappropriate for ordinary Ninereeds decisions because it introduces automatic subagent delegation and higher burn; reconsider only if real evidence shows a suitable class of tasks.

The higher-effort pass should receive the original evidence and a concise statement of why the lower-effort pass could not decide, not a long speculative chain that anchors the stronger run.

Initially log the proposed effort mapping without necessarily activating it. After sufficient boundaries, compare failure code, initial effort, escalation rate, quota cost, decision changes, and eventual training outcome. Allocate cognition empirically.

## Current `start.sh` observations

The attached/current version seen during discussion:

- calculates status through `msm_orchestrator_status.py`;
- creates a default config if required;
- runs one phase block or wakes the orchestrator based on `next_safe_action`;
- exits after one action.

This is useful manual ignition but is not yet a persistent supervisor. When auditing it, check for:

- single-instance `flock`;
- synchronization before state inspection;
- event/plan IDs and duplicate detection;
- expected-artifact verification rather than exit-code-only success;
- safe behavior for unknown actions;
- post-action reconciliation;
- whether silent default-config recreation is acceptable after commissioning;
- clean interaction with systemd services;
- compatibility with the new two-model architecture and Lab messaging.

Unknown actions should probably block with a report rather than automatically spending orchestrator tokens, unless explicitly classified as safe orchestration boundaries.

## Likely services

Names are placeholders; compare with existing implementation.

```text
Training machine:
  ninereeds-trainbox.service
  ninereeds-heartbeat.timer

Main workstation:
  ninereeds-orchestrator-supervisor.service
  ninereeds-orchestrator-fallback.timer
  ninereeds-lab.service
```

The persistent supervisor should own waiting, wake reception, restart recovery, and process lifetime. One-shot scripts should own bounded state transitions. Do not hide business logic inside systemd unit files.

## Lab audit points

The current Lab design is a workstation-side observer that pulls training artifacts and serves a local PWA. Verify and complete:

- Dashboard, timeline, campaigns, reports, MRI, Atlas, search, messages, notifications, chat, and published builds.
- Inbox/outbox transport and acknowledgement semantics.
- Andi-message -> orchestrator wake.
- Orchestrator-message -> Lab push notification.
- Guarded Git synchronization without dirty-worktree conflicts.
- Clear separation between artifact observation and human control messages.
- Authentication for trusted-LAN access.
- No GPU use and no load on the training machine.
- No direct public exposure.
- Removal of obsolete Hermes dependencies only after replacement paths work.

The Lab being offline during construction is not currently a blocker.

## Major conceptual update: Ninereeds as a cognitive cortex

Discussion later on 2026-07-11 changed a major assumption about the model itself.
The original plan required Ninereeds to learn language from scratch, then learn basic
facts, and only later become capable of deliberate conversation. The concern behind
that plan remains valid: a system that can emit `I go home` without representations
of self, movement, intention, and home may be producing fluent but unowned language.

The revised hypothesis separates linguistic competence from cognition:

```text
frozen mBERT               -> permanent receptive language cortex
frozen LFM2.5-230M         -> provisional expressive/speech cortex
SigLIP2                     -> visual cortex
Ninereeds                   -> processing, memory, identity, learning, and thought
```

Ninereeds is not merely an external memory attached to an otherwise intelligent
language model. It remains the cognitive core. It should interpret experience,
maintain and revise models, reason through objections, track uncertainty, remember
Andi and previous interactions, preserve a self-model, choose what it intends to say,
and change through experience. The language model should recognize and express
language, not decide what Ninereeds believes or impersonate the entity.

The whole coupled system may be called the entity, but personal continuity should be
centered in Ninereeds. A useful identity criterion is:

```text
same frozen cortexes + different Ninereeds               -> different individual
same Ninereeds + replacement compatible speech generator -> same individual adapting
```

This does not invalidate the existing curriculum work. It changes the primary object
being taught. Instead of forcing Ninereeds to discover word form, syntax, grounding,
concepts, memory, and reasoning simultaneously, the language center can supply rich
contextual observations. Ninereeds must still learn the stable concepts and cognitive
operations behind them.

Examples:

- `I` should become a persistent pointer to Ninereeds' own state and history.
- `go` should become a family of agent/location state transitions.
- `home` should become a stable place related to self, departure, return, safety, and
  experience.
- The philosophy corpus should teach operations such as concession, distinction,
  counterfactual reasoning, epistemic humility, model maintenance versus revision,
  second-order preference, and treating surprise as information.
- Four-language parallel material should help different linguistic surfaces converge
  on common Ninereeds structures.

The existing from-scratch line should be preserved as a scientific baseline. It asks
how language and concepts self-organize in BDH from deliberately shaped teaching. The
multi-cortex line asks a different and more practical question: can a plastic BDH mind
develop behind inherited, frozen perceptual and linguistic organs?

## Permanent receptive language cortex: multilingual BERT

Revised leading decision: use Google's cased multilingual BERT as a permanent part of
Ninereeds' anatomy for linguistic perception.

- Canonical checkpoint:
  `https://huggingface.co/google-bert/bert-base-multilingual-cased`
- Approximate size: 178M parameters
- Hidden width: 768
- Layers: 12 bidirectional Transformer encoder layers
- Maximum sequence length: 512 tokens
- Training objective: masked-language modelling on Wikipedia in 104 languages
- Coverage includes English, German, Japanese, and Chinese, plus 100 other languages.

mBERT is smaller than LFM2.5-230M and, unlike a causal generator, every token can
condition on the complete utterance. This makes it a more natural receptive language
cortex: its job is to represent what was said, not to predict what an assistant should
say next. Its broad multilingual coverage is an architectural benefit rather than
unwanted excess. It provides room for future languages without changing Ninereeds.

mBERT is deliberately a fixture, like SigLIP2. The system does not need a
model-replaceability abstraction between mBERT and Ninereeds. If Ninereeds' native
input width is not 768, a learned `768 -> Ninereeds width` projection may still be
required. Treat that projection as a permanent afferent connection which develops
with Ninereeds, not as a detachable compatibility adapter designed for model swaps.
If a future project deliberately replaces mBERT, that should be treated as major
neurological surgery and rehabilitation rather than routine plugin replacement.

LaBSE and LEALLA remain useful research controls. LaBSE explicitly aligns translations
across 109 languages but is approximately 471M parameters and optimized for pooled
sentence similarity. LEALLA distils that alignment into 69M/107M/147M variants. The
smaller size does not currently justify replacing mBERT's simpler, detailed token-level
bidirectional input. They may later serve as auxiliary alignment teachers or diagnostic
baselines, not as the default cortex.

## Provisional expressive cortex: LFM2.5-230M

LFM2.5-230M remains the leading candidate for turning Ninereeds' chosen intentions
into fluent text. It is no longer the default language-perception model.

- Official post-trained checkpoint:
  `https://huggingface.co/LiquidAI/LFM2.5-230M`
- Official base checkpoint/control:
  `https://huggingface.co/LiquidAI/LFM2.5-230M-Base`
- Unsloth mirror/tooling checkpoint:
  `https://huggingface.co/unsloth/LFM2.5-230M`
- Liquid announcement:
  `https://www.liquid.ai/blog/lfm2-5-230m`

Use the official LiquidAI BF16 checkpoint as the canonical scientific source. Unsloth
is useful for optimized loading, fine-tuning, and later quantized deployment, but do
not make a downstream conversion the only preserved reference checkpoint.

LFM is provisional and may later be replaced by a faster/lighter omnilingual
generator. Its egress connection should therefore remain fitted to a stable Ninereeds
intention interface. "Liquid" does not mean that it learns online; its weights remain
frozen and Ninereeds remains the plastic thinker.

## Language perception: intercept mBERT activations

Language input should be processed analogously to SigLIP2 vision input:

```text
SigLIP2:
  image -> frozen visual encoder -> patch tensors -> visual adapter -> Ninereeds

mBERT:
  utterance -> frozen bidirectional encoder -> token tensors -> permanent connection -> Ninereeds
```

mBERT does not generate. Run one frozen encoder pass with hidden-state output enabled
and detach the chosen activations.

Conceptual PyTorch/Transformers shape:

```python
with torch.no_grad():
    outputs = mbert(
        input_ids=input_ids,
        attention_mask=attention_mask,
        output_hidden_states=True,
        return_dict=True,
    )

language_states = outputs.hidden_states[selected_layer].detach()
# [batch, token_count, 768]
```

Every token representation can see the complete utterance. Useful interception points
include embeddings and early, middle, and final encoder layers. Middle-layer states
are the leading hypothesis for detailed linguistic interpretation, but compare layers
empirically. Initially preserve the full token sequence rather than collapsing the
utterance into one pooled sentence vector.

The permanent afferent path might begin as:

```text
[tokens, 768]
  -> LayerNorm
  -> optional trainable linear/MLP projection if widths differ
  -> optional gate or resampler
  -> Ninereeds linguistic observations
```

Add explicit role and boundary metadata rather than relying entirely on mBERT to infer
it: speaker, turn boundary, statement/question/quotation when known, language,
episode boundary, and relevant provenance. A representation of a claim must not be
silently converted into belief that the claim is true.

## Permanent ingress, replaceable egress

Do not impose one replaceability policy on every cortex. The current anatomy is
asymmetric by design:

```text
permanent mBERT -> permanent learned afferent path -> Ninereeds
Ninereeds -> stable intention space -> model-specific egress -> replaceable generator
```

Train Ninereeds and its mBERT afferent path together until linguistic representations
become native sensory input. Preserve explicit role, confidence, turn, modality, and
provenance markers. Equivalent meanings across paraphrases and languages should form
related structures inside Ninereeds, but no separate universal ingress bus is required.

Keep a stable output/intention interface because the speech generator is peripheral
and replaceable. When replacing the generator later:

1. Freeze Ninereeds and all persistent memory/identity pathways.
2. Train a new egress connection to express recorded Ninereeds intention vectors.
3. Validate identity, autobiographical anchors, concept behavior, epistemic behavior,
   cross-language transfer, and arbitrary novel facts.
4. Allow only bounded, low-rate output co-adaptation if required.

Preserve a compact speech-fitting set containing Ninereeds intention vectors and
multiple acceptable multilingual realizations. A second generator should eventually
be fitted as an early portability proof. If the same frozen Ninereeds cannot speak
through two independently fitted egress paths, the output abstraction has leaked.

## Prevent the language center from becoming the thinker

This is the main architectural failure mode. If LFM sees the full question during
generation, it may answer while Ninereeds becomes decorative memory. The expression
pass must not receive enough original context to bypass Ninereeds.

Intended flow:

```text
Andi's utterance
  -> frozen mBERT receptive pass
  -> permanent afferent linguistic observations
  -> Ninereeds interpretation, memory, reasoning, and response selection
  -> short sequence of Ninereeds intention vectors
  -> egress adapter to LFM-compatible virtual tokens/prefix
  -> separate frozen LFM expression pass
  -> fluent utterance
```

The expression pass should receive the intended state and only the minimal role/style
control required to speak. It should not receive the original question. LFM decides
how to phrase; Ninereeds decides what is said.

Ownership tests must include:

- remove/reset Ninereeds while preserving LFM and adapters;
- arbitrary invented entities and relations introduced after LFM was frozen;
- counterfactual worlds that contradict LFM's pretrained priors;
- delayed recall across unrelated episodes;
- teach in one language and ask through another;
- visual teaching followed by linguistic recall and the reverse;
- paraphrases and new surface forms;
- cases where the correct response is uncertainty or clarification;
- verify that removing Ninereeds removes the newly learned answer.

## Staged multi-cortex training plan

Do not attempt full bidirectional language grafting first.

### Stage 0: representation probes

- Capture mBERT hidden states at embeddings and selected encoder layers.
- Compare paraphrases, negation, word-sense differences, speaker/turn roles, and all
  four primary languages; use some additional supported languages as out-of-curriculum
  probes.
- Fit small probes for language, question type, reference, and category only as
  diagnostics.
- Compare mBERT against current token input. Keep LFM causal states and LEALLA as
  optional controls rather than required campaign branches.

### Stage 1: ingress-only controlled campaigns

- Freeze mBERT.
- Feed its 768-wide token states directly if Ninereeds can adopt that native input
  width; otherwise add the smallest permanent `768 -> Ninereeds input width`
  afferent projection.
- Change as little else as possible in the current training loop.
- Run matched 25M campaigns using existing token input, mBERT embeddings,
  middle-layer states, and final-layer states.
- Compare shaped evaluation, MRI topology/strength, cross-language transfer,
  paraphrase robustness, interference, and dependency-order effects.
- Start with direct token sequences; add a resampler only after a benefit is clear.

For the fixed corpus, selected hidden states can be cached. Do not cache every layer
for the whole corpus. A 768-dimensional BF16 vector is about 1.5 KiB per token per
layer. Cache only controlled candidates, or compute on the fly during probes.

### Stage 2: cognitive episodes through MSM

MSM becomes the developmental classroom. It presents bounded teaching episodes, not
only QA imitation:

- observations that require no immediate response;
- statements, objections, corrections, and counterexamples;
- delayed memory tests;
- paraphrase and cross-language application;
- grounded stories and SigLIP2 pairings;
- distinction between what Andi said and what Ninereeds believes;
- appropriate uncertainty and requests for clarification;
- recurring people, places, consequences, and relationship continuity;
- reflective/consolidation phases where models may be revised.

The philosophy corpus is especially important because it teaches cognitive dynamics,
not merely facts. Evaluate transfer of the operation to unfamiliar subject matter;
do not count reproduction of the philosophical prose as understanding.

### Stage 3: intention interface

- Train Ninereeds to produce a short sequence of stable intention vectors.
- Use multiple paraphrases and all four languages as acceptable realizations of the
  same underlying cognitive act.
- Optionally use mBERT-encoded target-response representations as an auxiliary latent
  target, but do not allow latent matching alone to become response imitation.
- Preserve current BDH sparsity/Hebbian/structural objectives and MRI observability.

### Stage 4: egress through frozen LFM

- Project Ninereeds intention vectors into LFM's 1024-dimensional virtual-token or
  prefix space.
- Run a separate frozen LFM expression pass.
- Compute language-model loss against acceptable teaching responses; gradients may
  flow through frozen LFM operations into the egress adapter and Ninereeds, but LFM
  parameters remain frozen.
- Verify `inputs_embeds`, convolution-cache behavior, gradient passage, and generation
  control experimentally. Use layer hooks/prefix injection only if the ordinary input
  embedding path is inadequate.
- Enforce the no-original-prompt bypass rule.

### Stage 5: vision and language convergence

- Connect SigLIP2 and mBERT through their permanent modality-specific afferent paths
  into Ninereeds.
- Teach shared referents from rotating visual views, descriptions, actions, and
  subsequent memory.
- Test whether modality-specific observations converge on persistent Ninereeds
  concepts without collapsing evidential provenance.

## Multi-cortex hardware hypothesis

On the two-RTX-3060 training station, likely initial division during experiments:

```text
GPU 1: frozen mBERT, LFM2.5-230M, and/or SigLIP2 feature production
GPU 2: Ninereeds training
CPU/RAM/disk: MSM, harnesses, orchestration, and selected activation cache
```

mBERT and LFM2.5-230M are small enough that alternate placements or co-location with
a 25M or 150M Ninereeds should also be tested. This experimental allocation conflicts
with the original steady-state assumption that GPU 1 is always reserved for the local
Qwen/Gemma executor. The harness must schedule executor inference and frozen-cortex
feature production rather than assume simultaneous exclusive ownership. Training
performance remains sacred; measure contention before selecting a schedule.

Keep this multi-cortex work behind explicit experimental flags until representation
probes and ingress-only campaigns justify integration into the main autonomous loop.

## Changed assumptions to search for in the repository

Look explicitly for code/docs that still assume any of the following:

1. Three LLM roles: orchestrator, executor, and Gemma trainer.
2. Gemma generates or executes the training conversation autonomously.
3. DeepSeek writes scripts/reports as a separate model role.
4. Hermes is required for notification or user communication.
5. The orchestrator remains continuously alive through tactical work.
6. One executor call runs a full campaign or long multi-job loop.
7. Both RTX 3060s are available to the executor.
8. TUI scraping is the only way to observe Codex limits.
9. Sol and Fugu can operate without a shared lease/idempotency protocol.
10. The Lab is merely a passive dashboard and not the human communication surface.
11. Ninereeds must learn fluent surface language from raw tokens before it can develop
    concepts, memory, identity, or deliberate thought.
12. SigLIP2 will be the only frozen perceptual cortex/projector.
13. Every cortex must be treated as a replaceable plugin. mBERT is now intended as
    permanent receptive anatomy; replaceability remains important for egress models.
14. A language model may see the original prompt during the expression pass without
    creating a cognitive bypass around Ninereeds.
15. The second RTX 3060 can be assigned permanently to the local executor even during
    frozen-cortex representation experiments.

Do not mechanically replace every historical reference. Preserve historical campaign records and documents where the old architecture is part of the record. Update active design, executable code, current schemas, and operational instructions.

## Recommended implementation order after the machine is ready

1. Boot and stabilize the cloned Linux installation on the training machine.
2. Verify storage, network identity, SSH, Git, two GPUs, drivers, thermals, and reboot recovery.
3. Assign one GPU to Ninereeds training and one to the local executor; confirm no accidental contention.
4. Install and benchmark both executor candidates under the real one-GPU-plus-RAM-offload configuration.
5. Choose one fixed v1 executor from a frozen, repeatable evaluation suite.
6. Make the deterministic trainer and one-job executor calls reliable locally.
7. Build the persistent training harness and artifact/escalation contracts.
8. Build the orchestration supervisor, locking, durable boundary claims, and restricted wake commands.
9. Integrate machine-readable Codex rate limits and Fugu's equivalent mechanism.
10. Implement clean Sol/Fugu handoff and waiting behavior.
11. Finish Lab Inbox/Outbox, chat, wake events, notifications, and service management.
12. Run shadow/dry runs before allowing autonomous updates or checkpoint promotion.
13. Measure real token burn and gradually enable adaptive pacing and reasoning effort.

The multi-cortex research track should proceed in parallel only after basic machine
stability, beginning with representation probes and matched 25M ingress-only runs. Do
not block completion of the reliable automation harness on an unproven model graft.

## Design principles retained

- Automate anything deterministic.
- Spend orchestrator cognition only at strategic boundaries.
- Keep executor calls bounded and disposable.
- Store state in explicit artifacts, not terminal context.
- Make every handoff idempotent and recoverable.
- Treat wake signals as hints and durable files as truth.
- Require machine-verifiable receipts before claiming completion.
- Preserve protected anchors and promotion gates.
- Prefer waiting safely over improvising during rate limits.
- Change one policy at a time, observe, and iterate.
- Optimize for low cognitive load, low context bloat, low token burn, and low noise.
- Training performance is sacred; the Lab and orchestration machinery must not consume training GPU capacity.

## Open questions for the live-repo audit

1. Where exactly will Codex/Sol run: persistent app-server integration, short-lived `codex exec`, tmux TUI, or a hybrid during transition?
2. What is the current Fugu programmatic invocation and rate-limit API/output?
3. Where should the canonical boundary/event queue live?
4. Should plans/reports use the main repository, a dedicated branch, or a small message/control repository?
5. Which machine initiates each Git pull/push, and how are dirty worktrees prevented?
6. What is the exact restricted-SSH command interface in both directions?
7. How does the training harness wake the workstation after a report if SSH is unavailable?
8. How are executor reports validated before becoming authoritative artifacts?
9. Which failure-code taxonomy best matches actual MSM failure modes?
10. Which operations may Qwen auto-advance without waking the orchestrator?
11. Which decisions require a verifier or human confirmation?
12. How should a partially completed plan recover after reboot?
13. What are the initial conservative five-hour and weekly brake thresholds?
14. How much executor work can one orchestration decision safely authorize?
15. Which Lab components already work, and which are currently only stubs?
16. Which mBERT layer best provides detailed linguistic interpretation and
    cross-language convergence for Ninereeds?
17. Can Ninereeds adopt 768-wide mBERT observations directly, or is a smaller permanent
    afferent projection better for BDH learning and memory capacity?
18. What is the stable Ninereeds output-intention width and number of intention vectors?
19. Can direct token-state input beat the current tokenizer baseline before adding a
    learned resampler?
20. Do mBERT's English, German, Japanese, and Chinese representations converge enough
    through ordinary curriculum training, or is auxiliary LaBSE/LEALLA alignment useful?
21. Can LFM generation be driven reliably from projected `inputs_embeds` without the
    original prompt and without convolution-cache failure?
22. What permanent calibration set is sufficient to fit a replacement speech generator
    without modifying identity or consolidated memory?
23. How should executor jobs and frozen-cortex feature production share the non-training
    RTX 3060 without reducing training throughput?

## Desired outcome

The finished system should feel like a perpetuum mobile without depending on a monolithic immortal process:

```text
wake
  -> synchronize
  -> read a few canonical files
  -> make one bounded decision
  -> write a durable plan
  -> dispatch
  -> sleep
```

The training side performs bounded local work until it either succeeds within policy or emits a durable escalation. The Lab makes the entire process visible and lets Andi and the orchestrator communicate without terminal archaeology or an additional Hermes agent. Rate limits slow the system down cleanly rather than breaking it. Every component is boring, restartable, inspectable, and replaceable.
