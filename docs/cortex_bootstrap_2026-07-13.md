# Cortex Bootstrap Report — 2026-07-13

This report records the first hardware-independent mBERT/LFM architecture milestone.
It is experimental work and does not alter the active MSM phase or checkpoint policy.

## Frozen checkpoints

Downloaded into the external Hugging Face cache:

| Role | Model | Resolved revision |
|---|---|---|
| receptive language | `google-bert/bert-base-multilingual-cased` | `3f076fdb1ab68d5b2880cb87a0886f315b8146f8` |
| expressive language | `LiquidAI/LFM2.5-230M` | `37b30cce3446f3f2e26a0d3f8c67c9167f5079d7` |

The initial mBERT snapshot command fetched all published framework variants. The checked-in
download helper now restricts future downloads to safetensors, tokenizer, configuration,
license, and documentation assets.

## Isolated runtime

Local environment: `~/.venvs/ninereeds-cortex` (not stored in the repository).

Verified versions:

- Python 3.13
- PyTorch 2.13.0+cu130
- Transformers 5.2.0
- Hugging Face Hub 1.23.0
- Safetensors 0.8.0

This environment is provisional. Recreate it against the assembled training machine's
actual NVIDIA driver rather than copying it blindly.

## Implemented seams

- Existing byte-token `BDH.forward` remains the baseline path.
- `BDH.encode` exposes contextual states before the byte LM head.
- `BDH.encode_embeds` accepts projected sensory observations at native Ninereeds width.
- `BDH.forward_embeds` supports controlled ingress-only comparison experiments.
- `MultilingualBertIngress` freezes mBERT and trains only its afferent projector.
- `IntentionHead` produces a fixed-length sequence through learned-query attention.
- `LFMExpressionCortex` freezes LFM and accepts only intention prefix embeddings.
- LFM has no API parameter through which the original user prompt is supplied.

## Verification

Baseline equivalence test:

- Byte IDs passed through `self.embed` and the new pre-embedded path produce exactly equal
  logits (`rtol=0`, `atol=0`) on a deterministic miniature BDH.

Real mBERT ingress test:

- mBERT BF16 states projected successfully into a miniature BDH.
- Gradients reached the afferent projector.
- Zero frozen mBERT parameters received gradients.

Representation probe:

- Layers 0, 4, 8, and 12 were compared on paraphrase, German/Japanese/Chinese translation,
  negation, and word-sense pairs.
- Middle layers showed substantially stronger multilingual sentence similarity than the
  embedding and final layers in this small mean-pooled probe.
- This supports testing middle layers first, but does not select a production layer; the
  corpus-derived token-level probe suite is still required.

Real LFM virtual-prefix test:

- Teacher-forced loss: `10.349591255187988` from a random intention prefix.
- Mean absolute intention gradient: `0.026978272944688797`.
- Mean absolute egress-projector gradient: `0.08241508714854717`.
- Frozen LFM parameters with gradients: `0`.
- Autoregressive generation from `inputs_embeds` completed without any original text prompt.
- Random-prefix output was nonsense, as expected before fitting the egress projector.

## Deferred until the training machine is ready

- Refactor per-layer BDH weights into an explicitly partitionable 12-layer 1.2B topology.
- Verify exact two-3060 topology, free VRAM, PCIe placement, BF16 behavior, and thermals.
- Implement 6+6 layer placement and compare it with per-layer FSDP.
- Add MSM plasticity scopes and changed-tensor receipts.
- Build a canonical bite-sized corpus/episode manifest.
- Fit cortex projectors and run ownership, cross-language transfer, and interference tests.
- Resume distributed pipeline, executor leasing, services, and Lab integration.
