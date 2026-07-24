# Cortex MSM Kickoff — 2026-07-25

## Result

The first executor-authored 1.2B Cortex block completed through the durable
pipeline without an intermediate training dataset:

```text
selected training_data evidence
  -> Ternary Bonsai executor
  -> finalized MSM script
  -> in-memory prompt/teacher pairs
  -> resumable Cortex checkpoint
```

- authoring plan: `plan-executor-cortex-container-20260725-0002b`
- training plan: `plan-cortex-cortex-container-multilingual-0002`
- parent: `core/cortex/cortex_bootstrap_block_0001.pt`
- output: `core/cortex/cortex_msm_container_block_0002.pt`
- output SHA-256:
  `7b011983516c63eed52019b2996f0b8f7eb29ec37f863de3f9394e459221d4e7`
- script examples: `5`
- initial loss: `7.946269989013672`
- final loss: `6.882298183441162`
- trainer duration: `27.097 s`
- optimizer state: `4,844,151,840` bytes, fp32
- frozen mBERT/LFM parameters with gradients: `0 / 0`
- peak VRAM: `6,293,523,456 / 6,401,866,240` bytes

The checkpoint is non-promoted.

## Authored script

The finalized script covered:

- English definition
- German recognition
- Japanese contents boundary
- Chinese unknown-specific-contents contrast
- English consolidation

The Japanese correction was structurally valid but semantically weaker than
the source boundary: it said that things are inside rather than preserving the
important “specific contents are unknown” distinction. This is a curriculum
quality finding. The block is commissioning evidence, not an accepted
promotion.

## Executor protocol finding

The first authoring plan (`...0002`) correctly blocked after two attempts. The
old protocol required a complete JSON script to be escaped inside a JSON
string, and Bonsai reached the 8192-token ceiling without closing that string.
No weight update occurred.

The executor envelope now permits JSON artifact content as an object. The
harness serializes it deterministically before schema and semantic validation.
With that repair and a 4096-token ceiling, Bonsai produced a valid artifact on
attempt 1 in 2214 completion tokens. Cortex authoring jobs are now hard-capped
at 4096 output tokens.

## Material boundary

Executor context may read existing evidence under `training/`,
`training_data/`, and `training_material/`. It cannot write into the evidence
libraries or read `.env`.

When evidence is missing, the harness can obtain ephemeral material from:

- DeepSeek direct
- DeepSeek V4 Flash through OpenRouter
- DeepSeek V4 Flash through NVIDIA NIM

Keys are loaded from `.env`, never placed in prompts or reports, and generated
text is explicitly wrapped as untrusted context. The local executor still
authors the final MSM script.
