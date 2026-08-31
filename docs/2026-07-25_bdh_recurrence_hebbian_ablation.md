# Ninereeds Research Note: Recurrence, Hebbian State, and the CoT Scaling-Trap Discussion

**Date:** 2026-07-25
**Status:** Experiment proposed; design must be reconciled with the actual Ninereeds code before implementation
**Context:** Follow-up to a Reddit discussion of chain-of-thought, recurrent latent computation, and BDH

## Purpose

This note preserves the useful conclusions from the discussion and provides a starting brief for a controlled Ninereeds experiment. It is meant to be dropped into the repository and read by Codex after the training machine and pipeline are operational.

The immediate research question is:

> What does Ninereeds' Hebbian component actually contribute, independently of repeated shared computation and curriculum design?

The experiment should distinguish gains caused by:

1. applying shared computation repeatedly;
2. updating and recycling Hebbian state;
3. the interaction between recurrence and Hebbian state;
4. the curriculum or data ordering rather than either architectural mechanism.

## Source discussion

- Reddit thread: [“Chain of Thought is a Scaling Trap — The Next Wave of AI Will Think in Latent Space”](https://old.reddit.com/r/MachineLearning/comments/1uviru5/chain_of_thought_is_a_scaling_trap_the_next_wave/)
- Related controlled COCONUT discussion: [small ProsQA experiment separating sequential processing from latent-state recycling](https://www.reddit.com/r/MachineLearning/comments/1rt4lyd/d_ran_controlled_experiments_on_metas_coconut_and/)
- BDH paper: [arXiv:2509.26507](https://arxiv.org/abs/2509.26507)
- Position paper on generated reasoning traces and faithfulness: [Kambhampati et al., arXiv:2504.09762](https://arxiv.org/abs/2504.09762)
- Pathway’s Sudoku report: [Beyond Transformers: Sudoku Bench](https://pathway.com/research/beyond-transformers-sudoku-bench)

These sources motivate the experiment; they should not be treated as independent proof that BDH provides interpretable reasoning or solved lifelong memory.

## Main conceptual distinction

The Reddit discussion usefully separates two forms of recurrence:

- **Depth recurrence:** process the current problem through additional sequential or shared computation before answering.
- **Time recurrence:** preserve and update state while additional input arrives.

This maps naturally onto the current Ninereeds direction:

- shared BDH computation may supply additional processing depth;
- Hebbian state may provide an overwriteable latent workspace across token time;
- a fixed multilingual language centre such as mBERT can serve as the linguistic interface;
- Ninereeds can remain the recurrent memory/identity/cognition cortex;
- SigLIP2 can serve as an analogous visual interface.

This supports the architectural separation of language from cognition, but it does **not** by itself decide mBERT versus LFM or prove that the Hebbian state is functioning as a useful workspace.

## Why CoT is an incomplete comparison

Chain-of-thought can provide extra sequential computation and an external scratchpad, but it is largely append-only. Its cost grows as the model rereads an expanding trace, and obsolete intermediate conclusions are difficult to replace cleanly.

A recurrent latent state can, in principle, overwrite and reorganize its contents. Its corresponding risks are:

- interference between stored features;
- saturation at long carry lengths;
- destructive overwriting;
- confidently wrong attractor states;
- hidden dependence on resets or curriculum ordering.

Generated CoT also should not be treated as a faithful transcript of internal computation. For the Ninereeds pipeline, explicit goals, deterministic checks, structured reports, and failure codes belong in the outer orchestration layer even if the inner cognition remains latent.

## Key experimental precedent

The linked small COCONUT/ProsQA experiment attempted to separate:

1. the benefit of additional sequential processing;
2. the benefit of recycling a meaningful previous hidden state.

In that limited experiment, sequential processing improved out-of-distribution generalization, while recycled hidden state sometimes harmed extrapolation and increased confidence in wrong answers. The result is not directly transferable: it used a small GPT-2-scale setup, one task, and one seed. The important contribution is the experimental separation, not the numerical result.

## Proposed factorial ablation

The initial design is a 2×2 experiment:

| Condition | Processing depth | Hebbian state |
| --- | --- | --- |
| **A — Minimal baseline** | One effective processing pass | Disabled or held fixed |
| **B — Recurrence only** | Repeated shared passes | Disabled or held fixed |
| **C — State only** | One effective processing pass | Normal updates |
| **D — Full Ninereeds** | Repeated shared passes | Normal updates |

The phrases “one effective processing pass,” “repeated shared passes,” and “disabled or held fixed” are placeholders until the repository is inspected. Codex must map them to real controls in the current implementation without accidentally changing parameter count, tensor shapes, initialization, optimizer behaviour, or training budget.

### Primary hypotheses

- **B > A:** repeated shared computation supplies useful processing depth even without state updates.
- **C > A:** Hebbian updates supply useful short-term state even without additional depth.
- **D > max(B, C):** the two mechanisms interact constructively.
- **D ≈ B or D < B on extrapolation:** recycled Hebbian state contributes little or creates interference.
- **All conditions move together:** curriculum/data construction is responsible for most observed gains.

## Evaluation matrix

Every condition should be evaluated on the same frozen suites:

1. **In-distribution competence**
   - familiar concepts and relation types;
   - held-out examples from trained distributions.

2. **Paraphrase and angle generalization**
   - unseen wording;
   - changed surface order;
   - known concepts approached through unseen semantic angles.

3. **Structural extrapolation**
   - dependency chains longer than those seen during training;
   - longer sequences or delayed dependencies;
   - distractors inserted between relevant facts.

4. **Cross-lingual transfer**
   - matched EN/DE/JP/ZH probes;
   - train-language versus transfer-language comparisons;
   - controls for translation difficulty and tokenization differences.

5. **Retention and interference**
   - evaluate before and after a subsequent campaign;
   - re-test old anchors after learning unrelated material;
   - distinguish transient Hebbian-state effects from changes in trained weights.

6. **Error calibration**
   - output entropy or another confidence proxy;
   - accuracy-confidence relationship;
   - confidently wrong answers under longer dependencies;
   - sensitivity to resetting versus carrying state.

## State-specific probes

If implementation permits, add controlled inference-time probes without retraining:

- sweep carry length;
- sweep reset frequency;
- compare clean resets with carried state from related and unrelated sequences;
- inject distractor sequences before a probe;
- measure recovery after state contamination;
- log Hebbian-state norms, sparsity, update magnitude, and saturation proxies by layer and time;
- compare which concepts or features dominate state occupancy;
- test whether a reset restores performance after a confidently wrong trajectory.

These measurements concern fast recurrent/Hebbian state. They must not be conflated with long-term forgetting or overwriting in trained weights, though their interaction is itself a future research target.

## Experimental controls

Before training, fix:

- dataset snapshots and splits;
- curriculum order and shuffle policy;
- token or example budget;
- optimizer and learning-rate schedule;
- initialization policy;
- checkpoint intervals;
- evaluation cadence;
- number of seeds;
- stopping rule;
- hardware and precision settings where feasible.

Report wall-clock time, update count, tokens/examples consumed, peak memory, and any condition-specific numerical instability. Equal wall-clock time and equal update count answer different questions; choose a primary compute-matching rule and report the other as a secondary measurement.

At least three seeds would be preferable. If compute makes that impractical, run a cheap smoke test across all four conditions first, then allocate replicated full runs only after verifying that the ablation controls are real and stable.

## Implementation cautions for Codex

Before modifying anything:

1. Read the current model, trainer, evaluation, and configuration code.
2. Locate exactly where shared layers are reapplied and where Hebbian state is created, updated, carried, detached, and reset.
3. Determine whether processing depth and token-time recurrence are actually independently controllable.
4. Check whether disabling state changes effective capacity or removes an input pathway in a way that makes the comparison unfair.
5. Prefer configuration flags and a common execution path over four divergent code branches.
6. Add assertions and logs that prove each condition is doing what its label claims.
7. Run tiny deterministic tests before committing GPU time.

Do not assume the conceptual 2×2 maps cleanly onto the current code. If the architecture couples repeated computation and state updates, document that coupling and design the closest valid ablation rather than forcing a misleading one.

## Recommended execution sequence

### Phase 1 — Repository audit

- map the conceptual variables to concrete code paths;
- document current recurrence and state lifetimes;
- identify existing tests, checkpoints, and evaluation harnesses;
- estimate compute for a minimal and full run.

### Phase 2 — Instrumentation

- introduce the smallest necessary configuration controls;
- log condition identity into every run and report;
- add state/reset diagnostics;
- build a frozen evaluation manifest.

### Phase 3 — Smoke test

- run all four conditions on a tiny fixed subset;
- verify comparable budgets and expected state behaviour;
- confirm that checkpoints and reports are reproducible.

### Phase 4 — Main ablation

- run the agreed seeds;
- evaluate every checkpoint on the frozen suites;
- preserve raw metrics, configs, commit hash, and environment information.

### Phase 5 — Interpretation

- estimate main effects of repeated processing and Hebbian state;
- inspect their interaction;
- separate accuracy gains from calibration failures;
- compare in-distribution improvement with extrapolation and retention;
- decide whether the next experiment should target state capacity, reset policy, curriculum interactions, or architectural coupling.

## Decisions already made

- The experiment waits until the training machine and pipeline are stable.
- We will design against the actual repository, not an abstract reconstruction of BDH.
- The outer orchestrator remains responsible for explicit goals, reports, failure codes, and deterministic checks.
- The Reddit post is useful primarily as vocabulary and experimental motivation, not as authoritative evidence.
- The most valuable next step is to isolate processing depth from Hebbian-state recycling.

## Open questions

- What is the cleanest operational definition of “one pass” in the current shared-layer implementation?
- Can Hebbian updates be disabled while preserving the same forward pathway and parameterization?
- Should state be fixed at zero, initialized once and frozen, or replaced with a non-updating control state?
- What state carry/reset policy is currently used between examples, batches, and campaigns?
- Which existing MRI probes can be reused as frozen evaluation suites?
- What budget permits a meaningful number of seeds?
- Which confidence proxy is valid for the current output mechanism?
- Can transient state occupancy be related to known curriculum concepts without pretending that graph visibility equals human-readable explanation?

## Expected deliverable from the weekend session

After inspecting the repository, Codex should produce:

1. a code-grounded experiment specification;
2. a mapping from A/B/C/D to exact configuration values and code paths;
3. a frozen evaluation manifest;
4. an estimated compute budget;
5. a smoke-test plan;
6. only then, the minimal implementation changes required to run the ablation.
