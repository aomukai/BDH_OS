# Campaign 30 optimizer-resume diagnosis — 2026-08-01

## Decision

Campaign 30 does not show that the 1,500-concept wave is too broad. The wave is
already divided into twelve guarded 500-example blocks, with only 125 new concepts
per block and 375 replay, identity, boundary, German, and Japanese anchors.

The two attempted learning-rate variants were not real update-recipe variants.
Both resumed the retained parent's optimizer state after constructing the requested
optimizer. PyTorch optimizer restoration replaced the newly commissioned parameter
group settings with the parent's settings. Consequently:

- both attempts had exactly the same 500 step losses;
- both produced exactly the same candidate evaluation summary;
- the requested learning rates were recorded in run metadata but were overwritten in
  the live optimizer parameter group;
- the requested RMS clip of 1.0 was reported as `null`; and
- requested stochastic rounding was reported as `false`.

The immutable retained parent remains:

`core/cortex/baselines/foundation-language-only-20260731.pt`

Neither rejected child is an acceptable continuation parent.

## Corrective change

`FactoredAdamW.load_state_dict` now supports restoring accumulated optimizer
statistics while preserving the hyperparameters of the newly commissioned optimizer.
The Cortex trainer uses that mode for full-core continuation blocks. This preserves
momentum and factored second moments while making a deliberate learning-rate, clipping,
or rounding experiment genuine.

The regression test constructs a parent optimizer at `1e-5`, resumes it into a newly
commissioned optimizer at `3e-6` with RMS clipping and stochastic rounding, and verifies
that the new recipe survives while the optimizer step state is retained.

## Next strategic boundary

Start a fresh bounded campaign from the unchanged retained parent. Give the strategic
orchestrator the Campaign 30 manifest, both evaluations, this diagnosis, the Cortex
development policy, and the normal autonomous campaign contract. The orchestrator
should choose the smallest decisive foundation-style experiment using concepts from
`allowlist-0501-2000-v1`, explicitly distinguish curriculum breadth from optimizer
recipe, and require the normal deterministic evaluation before any continuation.

The first revised child must report an effective optimizer policy matching its plan.
Any mismatch between requested and effective learning rate, RMS clipping, or stochastic
rounding is an infrastructure failure, not a model-learning result.
