# Cortex 1.2B Commissioning — 2026-07-25

## Outcome

The assembled Cortex path completed a real bounded training block on the
headless trainbox:

```text
frozen mBERT
  -> trainable Ninereeds 1.2B core
  -> frozen LFM2.5-230M
```

This supersedes the 25M byte-level model as the intended training architecture.
The 25M campaign remains useful evidence that the autonomous control plane and
phase gates work, but it is not a production parent.

## Model ownership

- trainable parameters: `1,209,936,896`
- frozen mBERT parameters: `177,853,440`
- frozen LFM parameters: `229,693,184`
- mBERT parameters with gradients: `0`
- LFM parameters with gradients: `0`
- core partition: layers 0–5 on `cuda:0`, layers 6–11 on `cuda:1`

The prompt is encoded only by mBERT. LFM receives the trainable intention
prefix and never receives the original prompt.

## Optimizer

Policy: `ninereeds_factored_adamw_v1`

- full momentum: enabled
- second moment: factored for large matrices
- optimizer state: fp32
- optimizer state bytes: `4,844,151,840`
- RMS clipping: disabled for this control run
- stochastic rounding: disabled for this control run

This is the controlled “SkewAdam B” experiment: only second-moment allocation
changes from the full-momentum design. Optional mechanisms remain separable for
later ablation.

## Live block

- plan: `plan-cortex-bootstrap-20260725-b0001`
- input: `training/pipeline/cortex/bootstrap_form_v1.jsonl`
- checkpoint: `core/cortex/cortex_bootstrap_block_0001.pt`
- artifact SHA-256:
  `0d5d7328380c495b9013d44fbe72935eb3fa2f0acdcc04bde92bcb291c7a06a6`
- examples: `4`
- steps: `4`
- duration reported by trainer: `20.259 s`
- initial loss: `9.603782176971436`
- final loss: `6.882227003574371`
- peak VRAM GPU 0: `6,293,261,312` bytes
- peak VRAM GPU 1: `6,403,308,032` bytes
- checkpoint size on disk: approximately `6.8 GiB`

The generated probe (`川.......`) is expectedly meaningless after four examples.
This block demonstrates wiring, gradients, memory fit, serialization, and
durable execution—not learned language or cognition. The checkpoint was not
promoted.

## Resume verification

The saved checkpoint was loaded independently after the worker completed:

- parent recognized as `cortex`
- all optimizer tensors restored as fp32
- optimizer-state byte count exactly matched the live run
- layer partition reproduced exactly
- allocation after load was `3,992,680,960` bytes on GPU 0 and
  `4,098,911,744` bytes on GPU 1

The checkpoint is therefore resumable, not merely serializable.

## Control-plane incident

Attempt 1 stopped before training because the worker waited for process exit
before draining captured model-loader output. The full pipe blocked the child.
No checkpoint was written. The lease runner now spools stdout and stderr to
temporary files while renewing the durable claim, and a regression test emits
more than a pipe buffer on both streams. The same plan then completed on
attempt 2.

## Next training boundary

Do not promote or build a long campaign from the four-example fixture. The next
boundary is to freeze a real multilingual curriculum and evaluation set, then
run measured resumable Cortex blocks with explicit optimizer ablations and
promotion gates.
