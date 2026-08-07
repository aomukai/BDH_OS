# Visual pipeline reconciliation

Status: recovered design and evidence; configuration and bounded deterministic/trainbox foundation implemented; live stages remain disabled pending commissioning.

## What survived

The visual work was deliberately archived during physical cleanup, not lost. The workstation archive contains the former `vision/` model registry, visual catalog and validation modules, generation/judging scripts, tests, plans, reports, and design documents. The trainingbox archive preserves projector artifacts. Runtime evidence records a separately installed trainbox vision environment and pinned FLUX, Gemma, and SigLIP2 revisions.

The archived code is evidence and a source of tested algorithms. It is not restored as an independent control plane. Mission Hub owns all new jobs, configuration, lifecycle state, approvals, logs, and artifact identities.

## Recovered model roles

| Configurable role | Recovered default | Authority |
|---|---|---|
| candidate image generator | FLUX.2 Klein 4B, revision `e7b7dc27f91deacad38e78976d1f2b499d76a294` | pixels only |
| blind observer | Gemma 4 E2B, revision `3e22461f65e89153144f8adb70e3b8c2cc9845a7` | structured visual evidence |
| caption proposer | Gemma 4 E2B | proposed caption; canonical text remains separate from pixels |
| evidence-policy decider | DeepSeek v4 Flash | `accept`, `check_again`, or `reject` proposal from textual evidence |
| final visual reviewer | Sol | final asset disposition after inspecting pixels and evidence |
| frozen learner receptor | SigLIP2 NaFlex, revision `b53b807d3a2d5e2b3911292f2d69e5341cdc064c` | derived learner features only |

These are role bindings, not hardcoded truths. Generator, observer, captioner, policy decider, final reviewer, and receptor must each be selectable in Lab settings with a primary and optional fallback where the role safely supports fallback. Exact model revision, runtime profile, prompt/rubric version, inputs, outputs, timestamps, and attempt history belong in every receipt.

Gemma is not an acceptance oracle. Mechanical hard gates override model opinions. Counts, spatial relations, edit preservation, disagreement, and `check_again` results require an independent pixel inspection. DeepSeek cannot repair facts absent from visual evidence. Sol cannot rewrite whether the original commission succeeded; it may only accept verified uses for the resulting pixels.

## Mission Hub job graph

The rebuilt pipeline uses bounded jobs rather than one long autonomous script:

1. `visual.plan` finalizes a versioned educational scene/pack specification.
2. `visual.generate` produces bounded candidates and generation receipts.
3. `visual.inspect` performs mechanical checks and blind visual observation.
4. `visual.caption` proposes accessible and teaching captions from accepted visual facts.
5. `visual.decide` assigns an evidence-policy bucket without pixel authority.
6. `visual.review` performs required independent pixel review and final disposition.
7. `visual.pack_finalize` atomically creates an immutable accepted pack manifest.
8. `visual.encode` derives content-keyed SigLIP2 features.
9. `visual.experience_compile` creates ordered image/text learner events.
10. `model.visual_train` runs the authorized projector/Cortex learning block.
11. `model.evaluate` measures grounding, transfer, contradiction sensitivity, and language retention.

Each heavyweight trainbox job uses the same global execution lease as Cortex training. Initial execution is serial. A stage unloads its model before the next stage can acquire the machine. Pack creation never authorizes weight updates, and training never publishes a checkpoint.

Generated candidates are ordered alternatives, not an all-or-nothing pack. Every candidate receives an independent review; the coordinator then admits usable alternatives in the plan's immutable item/seed order up to `max_pack_items`. Rejected and surplus usable candidates remain preserved as evidence but never enter the pack or encoder. The workflow fails only when no independently usable candidate remains. This deterministic admission rule does not rank model quality or promote a checkpoint.

The evidence-policy decision receives the immutable generation receipt as well as inspection and caption reports, but not candidate pixels. This lets it verify model revision, seed-to-hash mapping, dimensions, and generation limits without acquiring pixel authority. Any workflow-level terminal failure that is not already represented by a failed job creates its own unread Lab thread.

## Artifact and ownership boundary

Pixels live in the immutable artifact system, never Git or the control envelope. New artifact kinds cover visual plans, candidate images, inspection/caption/decision/review reports, accepted pack manifests, derived receptor features, and multimodal experience manifests. Mission Hub owns metadata and canonical accepted packs; the trainingbox owns execution caches and produces bytes under a lease. Every cross-machine artifact is hash verified.

The archived SQLite/JSONL visual catalog is preserved as evidence. Its content-addressing, path confinement, annotation history, disposition axes, and deterministic hard gates are promoted into new handlers and tests. Its former control ledger and worker locks are not restored.

## Pacing contract

The old 15-minute value was `strategic_boundary_interval_seconds`, not the daemon polling interval and not a delay between deterministic handoffs. It was anchored to the durable `completed_at` time of the terminal trainbox result that required a new strategic decision.

Mission Hub retains those semantics as a configurable `strategic_boundary_cooldown_seconds`, defaulting to 900 seconds:

- deterministic continuations may proceed immediately;
- only a new model-driven campaign decision waits;
- restarts cannot erase or shorten the wait because it is derived from durable timestamps;
- overlapping wakes are idempotent;
- zero may disable the wait only through an explicit reviewed configuration;
- the Lab presents the value in minutes while storing whole seconds;
- changing the value creates an inert draft and never wakes the pipeline by itself.

This is both a provider-budget pacer and a quiet-period safety buffer. Scheduler polling remains a separate operational setting.

## Commissioning order

1. **Implemented:** strict schemas, artifact types, model-role bindings, and hard limits.
2. **Implemented:** durable pacing enforcement and restart-safe timestamp tests.
3. **Implemented foundation:** bounded offline generation, inspection, caption, encoding, pack-admission, and experience-compilation handlers. Runtime fallback is explicit and tested without loading GPU models.
4. Commission generation, inspection, caption, decision, and review independently.
5. Commission pack finalization and artifact round trips.
6. Commission SigLIP2 feature extraction and cache identity.
7. Commission multimodal experience compilation.
8. Run Stage 0 interface probes and Stage 1 projector-only learning against the archived language baseline.
9. Keep autonomous modality choice and live visual training locked until matched-control and retention gates pass.
