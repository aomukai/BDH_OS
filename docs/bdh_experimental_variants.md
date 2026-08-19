# BDH Experimental Variants

This note documents opt-in alternatives implemented in `bdh.py`.

The baseline `BDHConfig()` remains the upstream-style BDH reference used by
existing checkpoints and training paths. The variants below are deliberately
controlled: each one is enabled through config fields saved into checkpoints,
and the default import path still constructs `BDH(config)`.

## Variant 1: `bdh_v1`

Factory: `bdh_v1_config()`

This is the unchanged reference behavior:

- no activation history
- no attention distance decay
- one compute tick
- no adaptive generation

Use this as the control for every architecture experiment.

## Variant 2: `temporal_decay`

Factory: `bdh_temporal_decay_config()`

This enables only causal attention distance decay:

```python
from bdh import BDH, bdh_temporal_decay_config

config = bdh_temporal_decay_config()
model = BDH(config)
```

Purpose:

- test explicit forgetting of distant attention interactions
- reduce stale long-context state effects
- keep the rest of BDH unchanged

Primary knobs:

- `attention_decay`: non-negative decay rate; `None` disables the path
- `attention_half_life_tokens`: trainer CLI convenience value converted as
  `decay = ln(2) / half_life`
- `learned_attention_decay`: when true, learns one decay rate per head

Recommended first experiment:

- `--attention-half-life-tokens 512`
- `learned_attention_decay=False`

Training entry point:

```bash
python train.py \
  --architecture-variant temporal_decay \
  --attention-half-life-tokens 512 \
  --eval-corpus-file path/to/heldout.txt \
  ...
```

## Variant 3: `ctm_lite`

Factory: `bdh_ctm_lite_config()`

This is the CTM-inspired exploratory variant. It combines:

- causal attention decay
- sparse activation history mixing

It does not automatically enable adaptive generation. Treat adaptive compute as
an inference policy, not part of the saved training architecture, unless that is
the explicit experiment.

```python
from bdh import BDH, bdh_ctm_lite_config

config = bdh_ctm_lite_config()
model = BDH(config)
```

Primary knobs:

- `activation_history_mix`: how much causal sparse activation history is added
- `activation_history_decay`: EMA decay for that history
- `activation_history_target`: `x`, `y`, `both`, or `pre_gate`; start with `x`
- `activation_history_max_mix`: positive upper bound for learned mix values
- `learned_activation_history`: learns per-head mix and decay values
- `compute_ticks`: fixed whole-stack recurrent passes during training/inference

Recommended first experiment:

- keep `compute_ticks=1` during training
- keep `activation_history_target=x`
- select checkpoints from behavioral chat and MRI/activation evidence; retain held-out loss as telemetry only

Training entry point:

```bash
python train.py \
  --architecture-variant ctm_lite \
  --eval-corpus-file path/to/heldout.txt \
  ...
```

For a stricter ablation, spell out the knobs instead of using the convenience
defaults:

```bash
python train.py \
  --architecture-variant ctm_lite \
  --attention-half-life-tokens 512 \
  --activation-history-mix 0.1 \
  --activation-history-decay 0.5 \
  --activation-history-target x \
  --compute-ticks 1
```

## Eval And Diagnostics

Architecture experiments should use held-out evaluation data:

```bash
python train.py \
  --phase 0 \
  --corpus-file path/to/train.txt \
  --eval-corpus-file path/to/eval.txt \
  --architecture-variant temporal_decay \
  --attention-half-life-tokens 512
```

The trainer may record held-out loss when an eval source is provided, but loss must
never select or rank a checkpoint. Checkpoint judgment uses behavioral chat and
MRI/activation evidence. Metadata includes command-line args, seed, git commit,
corpus hashes, size/training settings, loss telemetry, and the latest diagnostics.

Diagnostics print compact sparse-state measurements:

- logit entropy
- mean delta between compute-tick logits
- `x_sparse`, `y_sparse`, and `xy_sparse` density
- sparse activation magnitudes
- effective attention half-life

Use `--diagnostics-interval 0` to disable diagnostics.

Adaptive compute remains available for generation policy experiments:

```bash
python train.py \
  --architecture-variant ctm_lite \
  --adaptive-compute \
  --adaptive-max-ticks 3 \
  --adaptive-logit-delta-threshold 0.01 \
  ...
```

## Suggested Experiment Ladder

1. Train/evaluate `bdh_v1_config()` as control.
2. Train/evaluate temporal decay with `--attention-half-life-tokens 512`.
3. Repeat temporal decay with half-lives in `{256, 1024}`.
4. Train/evaluate `bdh_ctm_lite_config()` with fixed `compute_ticks=1`.
5. Test activation history targets in order: `x`, `y`, `both`, `pre_gate`.
6. Only after those results, test `compute_ticks=2`.

Avoid changing multiple knobs at once until the temporal-decay-only result is
understood.
