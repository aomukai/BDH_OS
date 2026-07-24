# SkewAdam and Ninereeds: Optimizer-State Allocation and the 1.2B Training Path

**Date:** 2026-07-25
**Status:** Research note / experiment proposal
**Primary sources:**

- Paper: [SkewAdam: Memory-Efficient Optimization for Sparse Mixture-of-Experts](https://arxiv.org/abs/2607.19058)
- Reference implementation: [nuemaan/skewadam](https://github.com/nuemaan/skewadam)

## Executive summary

SkewAdam is not a general successor to AdamW. It is a topology-aware optimizer designed for an extremely sparse Mixture-of-Experts model, where most parameters belong to experts that receive only a small fraction of the tokens. Its main contribution is to stop allocating identical optimizer state to model components with radically different update patterns.

The published SkewAdam recipe does not directly map onto the current dense/recurrent BDH architecture. Ninereeds has neither a conventional expert bank nor a router. Nevertheless, two ideas are highly relevant:

1. **Factored second moments may roughly halve optimizer-state memory for matrix-heavy Ninereeds models.**
2. **Optimizer state should eventually follow functional use, activation frequency, and consolidation status rather than raw parameter count.**

The first idea may be enough to change the planned 1.2B training strategy. Combined with two-GPU sharding, it may permit one coherent 1.2B Ninereeds model across the two RTX 3060 12 GB cards. That would remove the memory-driven need to train two separate 604M regions and later make them cooperate.

This should be tested first at 25M or 150M, then measured at 604M, before attempting a 1.2B allocation and training smoke test.

## What SkewAdam actually does

AdamW normally stores a full-size first moment and second moment for every trainable parameter. With both states held in fp32, this costs approximately 8 bytes per parameter in optimizer state alone.

SkewAdam assigns different state policies to different functional parts of a sparse MoE:

- **Dense backbone:** momentum plus an Adafactor-style factored second moment.
- **Expert bank:** factored second moment without momentum.
- **Router:** exact second moment because it is small but consequential.

In the paper's 6.78B model, roughly 95% of the parameters are located in 128 experts, while each expert sees only about 1/64 of the tokens. This deliberately skewed topology allows the optimizer to remove the most expensive state from the least frequently updated part of the model.

Reported results include:

- optimizer-state reduction from approximately **50.6 GB to 1.29 GB**;
- measured peak-memory reduction from approximately **81.4 GB to 31.3 GB**;
- little apparent benefit from restoring expert momentum: state rises to approximately **25.29 GB**, while perplexity changes only from about **108.9 to 108.7**.

The defensible conclusion is narrow but useful:

> In this unusually sparse, short-horizon MoE experiment, momentum for the enormous and infrequently selected expert bank costs a great deal of memory and contributes almost nothing measurable.

This is evidence for allocating optimizer state according to functional topology. It is not evidence that momentum is generally unnecessary or that SkewAdam should replace AdamW for ordinary dense models.

## Evidence limitations

The result is promising but should be treated as an early, architecture-specific finding.

- The experimental model is deliberately extreme: two transformer blocks, 128 large experts, and about 95% of all parameters concentrated in the sparse expert bank.
- Training covers only about 82 million tokens, which is a very short horizon for a 6.78B-parameter model.
- The principal comparisons are not supported by broad multi-seed validation across architectures and scales.
- Downstream zero-shot performance remains close to chance for all tested optimizers.
- Effective weight decay is absent because the bf16 decay update rounds away; the author acknowledges this.
- SkewAdam changes several things simultaneously: state allocation, factored variance, RMS clipping, epsilon behavior, and bf16 update rounding.
- Its approximate stochastic rounding uses uniform noise based on an estimated bf16 ULP. This is better described as dithered approximate stochastic rounding than exact unbiased selection between adjacent representable values.

Consequently, any Ninereeds experiment must separate the effects of factorization, momentum removal, clipping, rounding, and weight decay instead of treating “SkewAdam” as a single indivisible intervention.

## Direct relevance to the current Ninereeds trainer

If the reference implementation were applied to the existing dense BDH trainer without special parameter groups, most matrices would receive:

- full fp32 momentum;
- factored row/column second moments;
- RMS update clipping;
- approximate bf16 stochastic rounding.

There is no expert bank from which to remove nearly all state, so Ninereeds should not expect the paper's 97% optimizer-state saving. For a matrix-heavy model, however, replacing a full second moment with row and column factors should still approximately halve optimizer-state memory.

### Rough optimizer-state estimates

These values are planning estimates, not measured peaks. Exact consumption depends on tensor shapes, vector/scalar parameters, state dtype, framework overhead, temporary tensors, and which parameters can be factorized.

| Model size | AdamW fp32 moments | Momentum + factored second moment | Approximate saving |
|---|---:|---:|---:|
| 25M | 191 MiB | ~95 MiB | ~96 MiB |
| 150M | 1.12 GiB | ~0.56 GiB | ~0.56 GiB |
| 604M | 4.50 GiB | ~2.25 GiB | ~2.25 GiB |
| 1.2B | 8.94 GiB | ~4.47 GiB | ~4.47 GiB |

The 604M model currently peaks at roughly 9.7 GB with AdamW. Releasing around 2.2 GB would create useful headroom for batch size, sequence length, diagnostics, activation storage, or simply a safer operating margin on a 12 GB card.

For 1.2B, factorization alone is unlikely to make single-GPU training practical. Its importance is that it reduces the persistent state that must be sharded across the two GPUs.

## Consequence for the 1.2B architecture

The previous hardware-driven possibility was to place a separately trained 604M region on each RTX 3060 and design a mechanism through which the two regions cooperate. That could still become an interesting multi-cortex experiment, but it should not be forced on the architecture merely because AdamW consumes too much VRAM.

A naïvely doubled 1.2B run would be expected to require roughly 19–20 GB in aggregate if the 604M measurement scales approximately linearly. The two cards provide 24 GB of aggregate VRAM, but the training state must be distributed correctly.

With factored optimizer state and FSDP- or ZeRO-style sharding, a coherent 1.2B model may be feasible:

- approximately 4.5 GB less optimizer state across the complete model;
- persistent state plausibly reduced to a range that fits across both GPUs;
- activation checkpointing available if activations or temporary update buffers remain the limiting factor;
- slower inter-GPU synchronization accepted in exchange for avoiding architectural distortion.

The second GPU occupies the motherboard's x4 electrical slot. This will make some sharding patterns slower, especially those that repeatedly gather parameters. Wall-clock time is secondary here; memory feasibility, training correctness, and architectural coherence matter more.

The desired outcome is therefore:

> Train one coherent 1.2B Ninereeds across both GPUs, and reserve separately developing cortices as an intentional research direction rather than a memory workaround.

## The deeper BDH-native idea

Ninereeds contains a conceptual analogue to underused experts: the weakly connected or rarely activated “primordial soup” from which useful pathways can later emerge.

This suggests a future optimizer that assigns state according to measured functional status:

- frequently activated, identity-bearing, or heavily consolidated pathways retain richer optimizer state;
- weakly used reserve regions receive reduced or lower-precision state;
- newly recruited regions can be promoted when activation or gradient statistics cross defined thresholds;
- regions that become dormant can be demoted without immediately deleting their learned weights.

The published SkewAdam implementation cannot do this. It assigns policies to entire named parameter tensors, such as expert or router tensors. A BDH-native implementation would require one of two designs:

1. **Structural separation:** active and reserve populations live in separate parameter tensors and therefore separate optimizer groups.
2. **Blockwise or masked state:** optimizer state is allocated and updated at a finer granularity according to measured activation, gradient frequency, or consolidation metrics.

The second option is more faithful to Ninereeds but is a new optimizer research project inspired by SkewAdam, not an adoption of SkewAdam itself.

Dynamic state allocation also introduces hazards that must be designed explicitly:

- promotion and demotion thresholds may oscillate;
- newly promoted blocks need well-defined moment initialization;
- removing momentum may harm long-timescale consolidation even when short validation loss appears unaffected;
- state changes can interact with recurrent continuity and Hebbian gating;
- optimizer policy must not make dormant regions impossible to recruit later;
- checkpoint format and resumption must preserve the topology and lifecycle of optimizer state.

This research direction should remain separate from the initial factored-moment feasibility experiment.

## Proposed experiment ladder

### Phase 0 — Integrate a controlled optimizer family

Implement a common optimizer interface with explicit, independently switchable features:

- full versus factored second moments;
- momentum enabled or disabled;
- RMS clipping enabled or disabled;
- approximate stochastic rounding enabled or disabled;
- correct, measurable weight decay;
- logged state-memory accounting.

Do not fold all SkewAdam behaviors into one opaque configuration. Each run must record the exact policy.

### Phase 1 — Small-model controlled comparison

Run first at 25M or 150M with identical:

- initialization;
- corpus and curriculum version;
- sample order and batching;
- learning-rate schedule;
- number of optimizer steps;
- evaluation checkpoints;
- precision settings;
- weight-decay behavior.

Minimum comparison:

| Run | First moment | Second moment | Rounding / clipping |
|---|---|---|---|
| A: Baseline | Full momentum | Full | Current trainer behavior |
| B: Factored | Full momentum | Factored | Matched to baseline where possible |
| C: SkewAdam-like | Full momentum | Factored | SkewAdam-style clipping and rounding |
| D: No-momentum boundary | None | Factored | Matched to B |

Run B is the most important test because it isolates the likely memory benefit without assuming that momentum is unnecessary for BDH.

If resources permit, use multiple seeds for the strongest candidates rather than interpreting a single favorable run as optimizer superiority.

### Phase 2 — Ninereeds-specific evaluation

Validation loss alone is insufficient. Record:

- peak allocated and reserved VRAM;
- optimizer-state bytes by tensor class;
- step time and synchronization overhead;
- loss curve, spikes, NaNs, and recovery behavior;
- existing MRI bucket scores;
- retention of earlier hard edges;
- damage caused while incorporating new material;
- activation sparsity and distribution changes;
- gradient norms and update-to-weight ratios;
- ability to recruit previously dormant regions;
- state after checkpoint save and resume.

Learning-rate sweeps may be necessary. AdamW's established learning rate should not automatically be assumed optimal for the factored variants.

### Phase 3 — Measure the 604M model

After a factored configuration matches or acceptably approaches the AdamW baseline at smaller scale:

1. run a short 604M allocation and training smoke test;
2. measure actual peak VRAM rather than relying on estimates;
3. identify whether activations, gradients, optimizer state, or temporary update tensors are now dominant;
4. confirm throughput and checkpoint integrity;
5. run a sufficiently long comparison to expose delayed instability or retention damage.

This phase determines whether the expected ~2.2 GB saving exists in the real trainer.

### Phase 4 — Two-GPU sharding

Add FSDP, ZeRO-style sharding, or a narrowly tailored equivalent. Compare candidate sharding strategies with the x16/x4 PCIe asymmetry in mind.

Measure:

- static VRAM per GPU after initialization;
- peak VRAM during forward, backward, optimizer step, and checkpointing;
- volume and timing of inter-GPU transfers;
- idle time caused by the x4 slot;
- numerical equivalence to a smaller unsharded reference run;
- restart behavior from a distributed checkpoint.

Prefer a strategy that minimizes repeated full-parameter gathers if the x4 link becomes the primary bottleneck.

### Phase 5 — 1.2B feasibility gate

Before starting a full campaign:

1. instantiate the full 1.2B topology;
2. run forward and backward passes;
3. complete optimizer steps;
4. save and restore a checkpoint;
5. run long enough to observe stable memory and loss behavior;
6. leave a safety margin rather than treating an out-of-memory boundary as usable capacity.

Only proceed to full training if the model survives all of these steps reproducibly.

## Promotion criteria

A factored optimizer should replace AdamW in the main recipe only if it provides a material measured memory benefit and meets all of the following:

- stable training across more than a trivial smoke test;
- comparable or better convergence after appropriate learning-rate tuning;
- no meaningful regression in MRI bucket scores;
- no increased forgetting or hard-edge damage;
- no impairment of dormant-region recruitment;
- correct checkpoint/resume behavior;
- effective weight decay or an explicit decision to train without it;
- acceptable step-time cost.

For the 1.2B route, success means more than “it fits once.” The distributed run must retain enough VRAM margin for realistic sequence lengths, evaluation, diagnostics, and transient allocations.

## Implementation notes for the future Codex session

Before editing the trainer:

1. inspect the current optimizer construction and parameter grouping;
2. record the exact dtype of parameters, gradients, and AdamW states;
3. locate current mixed-precision, clipping, weight-decay, checkpoint, and scheduler behavior;
4. produce a tensor-shape inventory to estimate which second moments can actually be factorized;
5. confirm whether the reported 9.7 GB peak includes evaluation or only training;
6. inspect the planned distributed-training support already present in the repository.

Keep the optimizer experiment configuration-driven and reversible. Preserve AdamW as the known-good baseline. Checkpoints should include an optimizer-policy/version identifier so incompatible state layouts cannot be loaded silently.

## Current decision

SkewAdam should enter the Ninereeds roadmap as:

- **near term:** a controlled test of momentum plus factored second moments;
- **medium term:** a possible enabler for coherent two-GPU 1.2B training;
- **long term:** inspiration for BDH-native, activity-aware optimizer-state allocation.

It should not yet be described as the new default optimizer, and expert momentum removal should not be copied blindly. The most valuable immediate hypothesis is simpler:

> Factoring the second moment may recover enough VRAM to make a properly sharded, coherent 1.2B Ninereeds feasible on the two 12 GB GPUs without compromising the architecture for hardware reasons.
