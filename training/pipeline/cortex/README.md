# Cortex 1.2B Training

This is the production Ninereeds training path. The earlier 25M byte-level MSM
campaign proved the control plane, receipts, gates, and autonomous recovery; it
is not the target model and its checkpoint is not a parent of the 1.2B model.

## Architecture

```text
text
  -> frozen LFM2.5-Encoder-230M
  -> trainable ingress projector
  -> trainable 1.208B-parameter Ninereeds core
  -> trainable intention head and expression projector
  -> frozen LFM2.5-230M
  -> response text
```

The source prompt is never passed to LFM. LFM receives only the learned
intention prefix, so the Ninereeds core cannot be bypassed.

The trainbox partitions the twelve core layers evenly across its two RTX 3060
cards. LFM2.5 Encoder and the ingress projector live with layers 0–5 on `cuda:0`;
layers 6–11, the intention head, projector, and frozen LFM live on `cuda:1`.

## Optimizer experiment

`FactoredAdamW` implements the controlled SkewAdam-derived experiment:

- full fp32 Adam momentum is retained;
- second moments are factored only for large matrices;
- RMS clipping is an independent optional switch;
- approximate stochastic bf16 rounding is an independent optional switch.

This separation is intentional. “SkewAdam” is a research direction, not a
single opaque optimizer recipe to adopt without measurement.

## Durable blocks

The trainbox worker accepts bounded `cortex_block` plans. A live block requires
explicit weight-update authorization, cannot promote its own checkpoint, reads
either a finalized MSM script inline or legacy commissioning JSONL below
`training/pipeline/cortex/`, and writes a new checkpoint only below
`core/cortex/`. Inline scripts are converted to prompt/teacher-answer pairs in
memory; no intermediate training file is required. Checkpoints contain both
trainable model state and optimizer state so the next block can resume
momentum.

The normal autonomous handoff is:

```text
training_data/ or training_material/ evidence
  -> read-only Ternary Bonsai executor job
  -> finalized and fingerprinted MSM script
  -> separately authorized Cortex block
  -> new non-promoted resumable checkpoint
```

Executor context may read `training/`, `training_data/`, and
`training_material/`. Executor artifacts remain confined to `training/`.
When repository material is insufficient, the executor harness can request
ephemeral teaching context from DeepSeek direct, OpenRouter, or NVIDIA NIM.
The three API keys are loaded from `.env` without being added to prompts,
reports, or artifacts. Generated text is wrapped as untrusted context and the
executor still authors the final validated MSM script.

`bootstrap_form_v1.jsonl` is a four-example commissioning fixture. It verifies
the complete path but is not a sufficient training corpus and its output must
not be treated as a useful model.

The active LFM Encoder lineage must begin with `--parent scratch`. Archived mBERT
schema-v1 checkpoints are controls only and are rejected by the schema-v2 loader.

## Context policy

The active foundational bootstrap keeps `encoder_max_length=512` for controlled
comparison with the archived mBERT lineage. LFM2.5 Encoder supports a trained
window up to 8,192 tokens, reserved for later full K–8 lessons. Do not send all
8,192 encoder states directly through the current quadratic BDH attention.
Commission learned compression or hierarchical chunking first, verify staged
lengths on the trainbox, and retain compatibility with the learned core
checkpoint.

Useful probes:

```bash
/home/aomukai/.venvs/ninereeds-cortex/bin/python \
  meta/scripts/cortex_runtime.py \
  meta/scripts/probe_cortex_1_2b_allocation.py

/home/aomukai/.venvs/ninereeds-cortex/bin/python \
  meta/scripts/cortex_runtime.py \
  meta/scripts/probe_cortex_checkpoint.py \
  core/cortex/cortex_bootstrap_block_0001.pt \
  --local-files-only
```
