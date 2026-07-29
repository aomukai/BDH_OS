# Cortex LFM Encoder Scratch Restart

**Decision date:** 2026-07-29
**Status:** Active architecture boundary

## Decision

The mBERT Cortex lineage is archived. The new Ninereeds 1.2B Cortex starts from
random core weights with this anatomy:

```text
frozen LiquidAI/LFM2.5-Encoder-230M
  -> trainable 1024-to-512 afferent projector
  -> trainable Ninereeds 1.2B core
  -> trainable intention head and 512-to-1024 expression projector
  -> frozen LiquidAI/LFM2.5-230M causal expression model
```

The 230M encoder is the production starting point because it has the smaller
memory and throughput cost on the two RTX 3060 12 GB cards. The 350M encoder is
retained as a later controlled comparison:

- `LiquidAI/LFM2.5-Encoder-230M`
  revision `0b649ad0c684378b03d4d8304f7577a662ab89bc`
- `LiquidAI/LFM2.5-Encoder-350M`
  revision `b886781f7c6f10ca9b7096e21b83e30a073c2f39`

## Lineage boundary

The new checkpoint schema is `ninereeds_cortex_checkpoint_v2`. It rejects the
archived mBERT schema-v1 checkpoints as parents. The first live training block
must use `--parent scratch`; no core, projector, intention, expression-projector,
or optimizer state is inherited.

The pre-change source is preserved by Git commit `cc67dbaeb` and local annotated
tag `archive/mbert-cortex-2026-07-29`. The workstation and trainbox durable
control ledgers were copied to:

```text
~/.local/share/ninereeds-archives/cortex-mbert-2026-07-29/
```

All 49 mBERT Cortex checkpoints on the trainbox were hard-linked beneath that
archive. Retention may remove their original `core/cortex/` names without
removing the archived weights. The paused generation-6 block completed before
the boundary as:

```text
core/cortex/cortex-evolution-foundational-bootstrap-g0006-foundation-replay-0005.pt
```

It remains an archived developmental checkpoint, not a parent or admitted model.

## Runtime safety

Liquid's published bidirectional model implementation patches process-global
LFM2 attention and convolution functions. Ninereeds loads a causal LFM in the
same process, so leaving those patches installed would corrupt the speech model.
The ingress therefore installs the bidirectional functions only for a locked,
frozen encoder forward pass and restores the native causal functions in a
`finally` block before response loss or generation.

The published checkpoint stores encoder tensors beneath an `lfm2.*` prefix.
Transformers 5.2 does not correctly strip that prefix through the advertised
direct `AutoModel` path and reports a randomly initialized body. Ninereeds loads
`AutoModelForMaskedLM` and then retains its trained `.lfm2` body instead.

The scratch restart is not authorized for live training until model download,
representation, allocation, causal-restoration, gradient-ownership, save/load,
and one-step probes pass on the trainbox.
