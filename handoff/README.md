# Handoff Reconciliation

**Reviewed:** 2026-07-25
**Scope:** All seven chat exports in this directory, the live repository at
`b3d5bbe63`, and the restricted trainbox status interface.

The source handoffs are research and decision records. They do not override
executable code, current schemas, measured hardware, or later decisions. This
file records the reconciled state.

## Settled operational decisions

- The trainbox is a headless training/executor worker. The Lab runs only on the
  main workstation.
- Automation access to the trainbox remains read-only until durable envelopes,
  claims/leases, receipts, and idempotent recovery are implemented and tested.
- The local executor never owns a shell. A deterministic harness validates model
  output and performs every filesystem, Git, test, and training operation.
- Ternary Bonsai 27B is the primary executor candidate. Qwen3.6-35B-A3B is the
  fallback/comparison candidate. Gemma and binary Bonsai are not v1 candidates.
- Wait for ordinary upstream `llama.cpp` support for Bonsai's custom quantization.
  Do not make Prism's temporary fork, MTP, or DSpark a system dependency.
- Begin executor evaluation at 64K context and test 96K/128K only after measuring
  memory use and effective long-context retrieval.
- Frozen mBERT is the leading receptive-language cortex. Ninereeds/BDH remains
  the plastic cognitive core. Frozen LFM2.5-230M is a provisional expression
  cortex and must not receive the original prompt.
- Preserve AdamW as the optimizer baseline. Factored second moments are a future
  controlled memory experiment, not a general optimizer replacement.

## Corrections discovered in the live repository

### BDH is not presently an online Hebbian learner

`train.py` uses backpropagation with AdamW or optional bitsandbytes AdamW8bit.
`xy_sparse` is described as a Hebbian co-firing signal, but there is no explicit
online Hebbian weight update or persistent Hebbian state in the active model.

Consequences:

- The Sakana Phase 1 request to compare an “actual Hebbian update” with the
  backpropagation gradient cannot be implemented against the current code.
- The proposed recurrence × Hebbian-state 2x2 is not currently a literal
  ablation. The existing mechanisms are shared-weight `compute_ticks` and
  optional within-forward activation-history mixing.
- Hebbian routing, centered local teaching, E/I structure, update normalization,
  and persistent-state reset/carry probes remain future architecture work.
- Documentation should distinguish Hebbian-inspired sparse co-firing and
  curriculum considerations from the optimizer that actually changes weights.

### The Cortex is already partially implemented

The language-cortex handoff predates commit `5ec04b469`. The repository already
contains:

- frozen mBERT activation extraction and a trainable afferent projector;
- `BDH.encode_embeds` and `BDH.forward_embeds`;
- a learned-query intention head;
- frozen LFM virtual-prefix loss and generation with no original-prompt input;
- interface tests and hardware-independent probe scripts.

This is an interface/probe milestone, not an integrated training system. The
next Cortex task is the smallest matched 25M ingress experiment, not another
architecture scaffold and not full egress training.

### The autonomous pipeline is still a partial prototype

- The cold-start phase runner implements only Phase 0 and Phase 1 frontloads.
- Status currently infers `run_phase_block` because no block exists. That is a
  state-machine result, not authorization to begin training.
- Executor configuration still names only Qwen and there is no real
  `llama.cpp` executor adapter or validated one-call protocol.
- Active runbooks still assign notification and wake responsibilities to
  Hermes, although Hermes is disabled on the trainbox.
- The Lab now has a durable workstation-local JSON envelope transaction with a
  read-only ephemeral Codex worker, claims/leases, retries, correlated Inbox
  replies, and receipts. It is not yet cross-machine training transport.

### The checked-in Lab was not ready for LAN exposure

The audit found these blockers:

1. fail-closed authentication;
2. artifact/safe-root restrictions for `/repo`;
3. request-size limits, login throttling, origin/CSRF checks, and security
   headers;
4. serialized Git pulls with expected branch/remote validation;
5. API and service tests.

The accompanying worktree changes implement this first security slice and add
coverage. They must be reviewed and committed before the Lab is treated as
LAN-ready.

Its message path then needs atomic structured envelopes, stable IDs,
correlation, claims/leases, acknowledgements, deduplication, retry state, and a
durable single-instance worker.

## Dependency-ordered implementation path

1. **Make the Lab safe locally.** The first security implementation and tests
   are present in this worktree; review, commit, and deploy them.
2. **Implement one complete workstation transaction.** Completed in the
   worktree: Lab outbox envelope → Codex worker claim → correlated response →
   persisted receipt visible in the Lab.
3. **Generalize the envelope for two machines.** Store durable plans/reports in
   an explicit transport location; use restricted SSH only for disposable wake
   hints. Add leases, recovery timers, and idempotency tests before enabling
   dispatch.
4. **Replace active Hermes contracts.** Point current runbooks, sentinels,
   service names, and notifications to the Lab/orchestrator supervisor while
   preserving historical Hermes records.
5. **Build the model-independent executor harness.** Strict stdout schema,
   bounded jobs, repetition detection, repair/continuation calls, patch
   allowlists, deterministic validation, and structured failure codes.
6. **Benchmark executor candidates.** When upstream support lands, evaluate
   Ternary Bonsai and Qwen on one RTX 3060 using the frozen multilingual,
   coding, schema, injection, recovery, and long-context suite.
7. **Run shadow pipeline trials.** No autonomous weight update or checkpoint
   promotion until receipts, reboot recovery, locking, failure injection, and
   human stop controls pass.
8. **Run the matched Cortex ingress experiment.** Compare the byte baseline
   with selected early/middle/late frozen mBERT layers at 25M under equal data,
   optimizer, update, and evaluation budgets.

## Deferred research queue

| Handoff | Current disposition | Revisit trigger |
| --- | --- | --- |
| Language Cortex | Active after automation foundation; ingress first | Reliable harness and matched 25M run capacity |
| Bonsai executor | Active harness work; model install waits upstream | Upstream `llama.cpp` kernel support |
| Recurrence/Hebbian ablation | Re-specification required | A real Hebbian/state mechanism exists, or explicitly redefine the study around activation history |
| Sakana error diffusion | Observational idea blocked by absent local update | Explicit local plasticity is implemented |
| SkewAdam | Controlled optimizer research only | Baseline memory accounting and stable 25M/150M runs |
| Introspection/identity | Staged research, not immediate curriculum | Internal intervention instrumentation and delayed localization probes |
| Dendritron | Governance vocabulary only | A real module registry, adapters, pruning, rollback, or localized repair |

## Current machine boundary

The restricted status check reports a clean `main` at `b3d5bbe63`, two idle
RTX 3060 12 GB cards with persistence enabled, healthy heartbeat/SMART/SSH
services, and no Lab or Hermes service. No training should start merely because
the pipeline status says its next mechanically possible action is
`run_phase_block`.

Physical follow-ups remain outside the repository:

- reserve `192.168.3.12` for MAC `70:85:c2:c7:59:ed` in the router;
- verify BIOS restore-after-power-loss behavior.
