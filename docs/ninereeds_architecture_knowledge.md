# What we know about Ninereeds

**Status:** canonical, cumulative evidence ledger  
**Authority:** observations and immutable Mission Hub evidence, interpreted by humans  
**Started:** 2026-08-07

This file records what we have learned about Ninereeds, why we believe it, what
the finding changes, and where the evidence stops. It is not a design wishlist,
a list of conventional assumptions about language models, or a replacement for
the immutable evidence itself.

## How to use this ledger

- Add entries; do not rewrite an inconvenient result out of history.
- Give every claim a stable `NRK-` identifier.
- Link the exact campaign, checkpoint, evaluation, scan, or source-code evidence.
- Separate an observed fact from an interpretation.
- Record counterexamples and limitations with the claim.
- If later evidence changes a conclusion, mark the old entry `superseded` and
  add a new entry explaining why. Do not delete the old entry.
- Training loss may be mentioned as telemetry. It is never evidence that a
  checkpoint learned, forgot, recovered, or is better.
- Campaign closure is fail-closed on this ledger. Every campaign review must
  declare either `updated`, naming the new `NRK-` entries added here, or
  `no_new_findings`, with a substantive reason. The review records the exact
  SHA-256 of this file, and the CLI refuses closure if that hash is stale.
- Operational bugs belong in operational documentation unless they reveal
  something about Ninereeds itself. A campaign may therefore legitimately
  record `no_new_findings`; it may not silently omit the question.

Evidence strength has the following meanings:

- **Law:** a project invariant that every training path must enforce. A law is
  not necessarily a scientific finding.
- **Strong observation:** a controlled or especially clear result that has
  survived the relevant checks.
- **Observation:** directly supported, but limited in scope or confounded.
- **Working hypothesis:** a useful explanation that still needs a discriminating
  experiment.
- **Unknown:** an important unanswered question.
- **Superseded:** retained history whose conclusion was corrected by later evidence.

## Current findings

### NRK-0001 — Training order is immutable

- **Status:** law
- **Claim:** Ninereeds training examples and sessions are never shuffled. The
  declared order is part of the lesson and must be executed exactly.
- **Why:** early work repeatedly showed that order materially changes what the
  model expresses. Campaign 33 then produced a controlled ordering comparison:
  branches 3 and 4 used the same parent, seed, optimizer settings, block sizes,
  and per-block row multisets, but rotated the protected 50 rows from last to
  first. Their terminal behavior diverged sharply.
- **Operational consequence:** corpus validation, job admission, and the
  trainbox lease boundary must fail closed if exact order cannot be certified.
- **Limits:** the law protects reproducibility and known pedagogical behavior.
  It does not by itself explain the internal learning mechanism.
- **Evidence:** registered source `src-campaign33-findings-20260807`; training
  contract in `docs/mission_hub_architecture.md`.

### NRK-0002 — Semantic dependencies precede derived concepts

- **Status:** law, supported by repeated observation
- **Claim:** prerequisites must be known already or appear earlier in the same
  ordered lesson. Teach `bee` and `honey` before `beehive`; teach `dog` and
  `house` before `doghouse`.
- **Why:** Ninereeds does not reliably acquire a derived concept whose components
  have no established representation. Dependency-aware curricula were an early
  practical improvement and are consistent with the strong order sensitivity
  in NRK-0001.
- **Operational consequence:** each checkpoint owns a lineage-specific known
  closure. Every session must declare its concepts and prerequisites, and
  Mission Hub must produce a dependency certificate before the job exists.
- **Limits:** exposure is not proof of usable knowledge. The known ledger means
  “taught in this lineage”; behavioral chat and MRI test what is accessible.
- **Evidence:** append-only Mission Hub knowledge records and dependency
  admission contract in `docs/mission_hub_architecture.md`.

### NRK-0003 — Known prerequisites do not need to be taught again

- **Status:** law
- **Claim:** a compound's prerequisites may be satisfied by the exact parent
  checkpoint's inherited knowledge closure. A new session containing
  `doghouse` need not reteach `dog` and `house` if both were already taught in
  that lineage.
- **Why:** dependencies concern availability, not mandatory repetition.
  Unnecessary repetition can overweight a concept and introduces an avoidable
  confound.
- **Operational consequence:** campaigns snapshot `known-at-start`, append
  `trained-during`, and derive each output checkpoint's closure without leaking
  knowledge across sibling branches.
- **Limits:** if behavioral evidence shows that a supposedly known prerequisite
  is inaccessible, a deliberate recovery lesson may still reteach it.
- **Evidence:** Mission Hub knowledge-ledger tests and architecture contract.

### NRK-0004 — Material placed last receives strong immediate protection

- **Status:** strong observation
- **Claim:** in Campaign 33 branches 3 and 4, placing the 50 protected examples
  at the end of every 500-row block preserved immediate protected behavior much
  better than placing those identical examples first.
- **Why:** branch 3 ended at overall `0.288889`, protected `0.75`, with 3
  pathologies. Branch 4 ended at overall `0.022222`, protected `0.0`, with 13
  pathologies. Across all 12 blocks, branch 3 also had better mean protected
  behavior (`0.5104` versus `0.2708`). In a later held-out paraphrase battery,
  branch 3 preserved 3/4 protected anchors with 8/28 pathological outputs;
  branch 4 preserved 0/4 with 19/28 pathologies. The order rotation was the
  controlled difference.
- **Interpretation:** immediate behavioral access is strongly recency-sensitive.
  “Protected-last” is a useful retention device for material that must remain
  accessible at the next checkpoint.
- **Operational consequence:** campaign design must explicitly declare which
  material, if any, is placed last for protection. It must never arise through
  shuffling or an undocumented mixer.
- **Limits:** this does not prove durable consolidation, broad capability gain,
  or semantic mastery. The current protected score is small and keyword-brittle.
- **Evidence:** registered sources `src-campaign33-findings-20260807` and
  `src-campaign33-posthoc-acquisition-20260807`, plus the linked terminal Mission
  Hub evaluation artifacts.

### NRK-0005 — Regression and recovery are oscillatory, not monotonic

- **Status:** strong observation for Campaign 33
- **Claim:** Ninereeds can lose and later re-express behavior over successive
  ordered blocks; neither regression nor recovery follows a smooth curve.
- **Why:** branch 3 moved from baseline `0.055556` to `0.222222`, later reached
  `0.0` at block 10, and recovered to `0.288889` at block 12. Branch 4 showed a
  partial block-11 state of `0.188889` and collapsed to `0.022222` at block 12.
- **Interpretation:** a single intermediate checkpoint can be badly misleading.
  Recovery may be renewed surface access rather than restoration of a stable,
  deep representation.
- **Operational consequence:** preserve every block checkpoint and its immediate
  chat/MRI evaluation. Do not stop or rank an experimental branch because one
  score rises or falls unless that was a predeclared validity gate.
- **Limits:** Campaign 33 does not yet distinguish relearning, unmasking,
  interference, and genuine consolidation.
- **Evidence:** Campaign 33 per-block evaluation trajectory.

### NRK-0006 — Severe behavioral change need not be structural collapse

- **Status:** observation
- **Claim:** Campaign 33 terminal behavioral collapse occurred while the coarse
  MRI health measures remained finite and active.
- **Why:** branch 3 and branch 4 scans showed no dead or saturated layers,
  co-firing density near `0.303–0.305`, and hidden-state standard deviation near
  `1`. Yet their terminal behavior differed drastically.
- **Interpretation:** the current MRI can rule out some catastrophic numerical
  failures, but it cannot explain or predict the behavioral state by itself.
- **Operational consequence:** evaluation always requires both behavioral chat
  and MRI. Neither may substitute for the other.
- **Limits:** the present MRI is coarse. A healthy aggregate does not mean that
  useful representations are separated or correctly routed.
- **Evidence:** Campaign 33 terminal evaluation artifacts and Observatory scans.

### NRK-0007 — Current pooled representation geometry is poorly separated

- **Status:** observation
- **Claim:** Campaign 33 pooled core representations were nearly collinear across
  evaluated concepts, with between-concept cosine close to `0.999`; reported
  concept separation was negative.
- **Why:** this pattern appears in the terminal Atlas/MRI evidence for the
  recommissioned branches. Both terminals also showed more-negative separation
  at ingress/intention stages than the common baseline.
- **Interpretation:** the current pooled probe may reveal genuine representational
  crowding, or it may be too blunt for where Ninereeds encodes distinctions.
- **Operational consequence:** retain this as a diagnostic warning, not a
  checkpoint ranking metric. Design finer probes before making an architectural
  conclusion.
- **Limits:** pooled cosine geometry cannot establish that individual sparse
  gates or time/token-local states lack separable information.
- **Evidence:** Campaign 33 Atlas and MRI evidence.

### NRK-0008 — The existing Campaign 33 suite does not measure new-word acquisition

- **Status:** strong observation about the evaluator
- **Claim:** the 15-case suite primarily probes old anchors and epistemic
  boundaries. It does not adequately test whether the 1,500 campaign concepts
  were acquired.
- **Why:** inspection of the suite and training materials found little direct,
  held-out coverage of the newly introduced concepts. Its protected scoring can
  also award an irrelevant loop containing `I do not know`.
- **Operational consequence:** Campaign 33 conclusions must be limited to the
  behaviors actually probed. A held-out, paraphrased acquisition suite is
  required before claiming vocabulary learning.
- **Limits:** failure of evaluator coverage is not evidence that the concepts
  were or were not learned.
- **Evidence:** Campaign 33 suite/material audit and registered follow-up source
  `src-campaign33-posthoc-acquisition-20260807`.

### NRK-0009 — Loss is execution telemetry only

- **Status:** law
- **Claim:** training loss cannot admit, reject, rank, continue, promote, roll
  back, or declare learning in Ninereeds.
- **Why:** observed behavior and representation health have not tracked loss
  reliably in this architecture, and historical conducting models repeatedly
  substituted conventional loss reasoning for the declared experimental goal.
- **Operational consequence:** every run requires behavioral chat and MRI. An
  evaluation that gives loss decision authority is invalid.
- **Limits:** loss remains useful for detecting non-finite execution and for
  recording optimization telemetry.
- **Evidence:** project evaluation law and Campaign 33 history.

### NRK-0010 — The current sparse co-firing gate is not a separate Hebbian update

- **Status:** verified implementation fact
- **Claim:** the current `x_sparse × y_sparse` gate participates in the ordinary
  differentiable forward pass. Backpropagation plus `FactoredAdamW` is the only
  committed parameter-update mechanism.
- **Why:** source inspection shows no independent local Hebbian update tensor or
  optimizer path.
- **Operational consequence:** Campaign 34 may measure activation-credit and
  optimizer behavior, but must not describe a nonexistent
  `Hebbian-update/BP-update` alignment. Any local rule is a later, separately
  authorized mechanism.
- **Limits:** “Hebbian-shaped” remains a reasonable description of the co-firing
  form, not of the actual update rule.
- **Evidence:** `bdh.py`, `cortex/student.py`,
  `training/optim/factored_adamw.py`, and the reconciled gate-credit contract in
  `handoff/2026-07-25_ninereeds_sakana_error_diffusion_scratchpad.md`.

### NRK-0011 — Campaign 33 showed narrow held-out acquisition, not broad acquisition

- **Status:** observation
- **Claim:** every surviving trained terminal generalized `referring` to an
  unseen prompt, while none generalized the other 23 sampled new concepts well
  enough to pass the strict battery.
- **Why:** the common baseline passed 0/24 capability cases. Branches 2, 3, and 4
  each passed exactly `c33-b10-referring` and no other capability case under the
  same prompts and generation settings.
- **Interpretation:** Campaign 33 changed at least one newly taught concept in a
  way accessible through paraphrase, but it did not demonstrate broad
  vocabulary acquisition. Shared success across three different terminal
  trajectories makes `referring` a useful target for finer mechanistic study.
- **Operational consequence:** do not describe the campaign as having learned
  its 1,500-word curriculum. Future acquisition studies need broader held-out
  sampling, response-level human review, and delayed retesting.
- **Limits:** this is a 24-concept sample with brittle keyword scoring and one
  deterministic generation per prompt. A failure is not proof that no relevant
  representation exists.
- **Evidence:** registered source `src-campaign33-posthoc-acquisition-20260807`
  and its three linked immutable evaluation reports.

### NRK-0012 — Read-only gate-credit observation can preserve the exact trajectory

- **Status:** strong observation for the Phase 1 configuration
- **Claim:** the Campaign 34 observer recorded layerwise activation credit and
  optimizer movement without changing any trained tensor or optimizer-state
  leaf in the paired 16-step run.
- **Why:** the control and observed branches shared exact parent, ordered bytes,
  seed, optimizer, and settings. A streaming comparison found all 358 learned
  and optimizer leaves bit-identical. Their step telemetry, generated text,
  behavioral outputs, scores, and MRI results were also identical.
- **Operational consequence:** this observer configuration may be used in a
  longer observational experiment. Any modification requires the same
  diagnostics-off equivalence check before its evidence is trusted.
- **Limits:** this proves transparency for one 16-step, batch-size-1 run on the
  current hardware and software release. It does not prove every future observer
  or workload is transparent.
- **Evidence:** registered source `src-campaign34-gate-credit-phase1-20260807`,
  gate-credit artifact `art-9c2b9e2533608409`, and comparison artifact
  `art-eb987fa8de23951b`.

### NRK-0013 — Sparse-gate credit is mixed; global alignment cancels

- **Status:** observation
- **Claim:** active sparse-gate units received both strengthening and suppressing
  pressure throughout the 16-step lesson, while whole-vector
  `cos(h, -dL/dh)` remained effectively zero.
- **Why:** most layer aggregates placed both active strengthening and active
  suppressing fractions near `0.43–0.50`; global cosines were around `10^-17`.
  All measurements were finite and effective gate density remained roughly
  `0.20–0.26`, ruling out a simply dead gate.
- **Interpretation:** the global cosine discards useful signed local structure.
  The result does not support a simple local rule that reinforces every active
  co-firing unit.
- **Operational consequence:** retain layer-, step-, and active-unit-resolved
  sign evidence. Do not use global gate-credit cosine to evaluate checkpoints or
  control training.
- **Limits:** the lesson was deliberately tiny and contains only four replayed
  concepts. Other curricula may produce different pressure patterns.
- **Evidence:** registered source `src-campaign34-gate-credit-phase1-20260807` and
  immutable gate-credit artifact `art-9c2b9e2533608409`.

### NRK-0014 — Interface parameters moved more per unit norm than core tensors

- **Status:** observation
- **Claim:** in Campaign 34 Phase 1, normalized intended optimizer movement was
  several times larger in ingress, intention, and expression components than in
  the three large core parameter families.
- **Why:** mean update-to-parameter-norm ratios were approximately `2.17e-4` to
  `3.06e-4` for interfaces and `1.73e-5` to `4.29e-5` for core families.
- **Interpretation:** the interfaces adapted faster relative to their parameter
  scale during this lesson. That may matter for encoder/core/expression
  coordination, but relative movement is not importance or learning success.
- **Operational consequence:** future mechanistic studies should separate
  interface and core movement rather than reporting one model-wide optimizer
  norm.
- **Limits:** optimizer preconditioning, tensor size, and parameterization all
  affect this comparison. It needs replication across longer and contrasting
  lessons.
- **Evidence:** registered source `src-campaign34-gate-credit-phase1-20260807` and
  immutable gate-credit artifact `art-9c2b9e2533608409`.

## Open questions

### NRK-U001 — What exactly is protected-last preserving?

Does recency preserve a representation, an output-routing state, a prompt-format
habit, or only a short-lived expression tendency? Campaign 34 and later delayed
reevaluation should distinguish these possibilities.

### NRK-U002 — Where are usable distinctions represented?

The pooled Atlas is crowded, but behavior can still differ. Token-local, layerwise,
sparse-unit, and backward-credit evidence may locate distinctions hidden by pooling.

### NRK-U003 — Did Campaign 33 teach its new concepts?

**Resolved in part by NRK-0011.** The surviving terminals show narrow transfer
for one sampled concept, not broad acquisition. The complete 1,500-concept
curriculum, delayed retention, and alternative elicitation remain unknown.

### NRK-U004 — Does gate activity agree with backward teaching pressure?

**Resolved in part by NRK-0013.** Global alignment was effectively null, while
active-unit pressure was mixed and locally structured. Whether repeatable
concept-, token-, or phase-specific patterns exist remains unknown.
