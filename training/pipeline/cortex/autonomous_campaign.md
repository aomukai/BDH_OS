# Cortex Autonomous Campaign Policy

This policy governs the first unattended research campaign for the production
Ninereeds architecture:

```text
frozen mBERT -> trainable Ninereeds 1.2B core -> frozen LFM2.5-230M
```

The terminal seed is the commissioned multilingual `container` MSM checkpoint.
Every new block must resume the exact `checkpoint_after` reported by the
previous Cortex block. Checkpoints remain candidates; autonomous promotion is
forbidden.

## Research objective

Establish stable early language grounding through compact, evidence-backed MSM
blocks while measuring whether the 1.2B core remains trainable and resumable.
Favor semantic foundations, contrasts, uncertainty boundaries, simple
relations, and short multilingual transfer. This is controlled curriculum
construction, not broad corpus pretraining.

One strategic boundary may authorize one executor-authored script and its one
deterministically derived Cortex training block. Inspect the preceding report
before selecting another block. Stop and request human review for non-finite
loss, rising resource use, missing ownership invariants, checkpoint trouble,
or repeated executor/script failure.

## Conservative block shape

- one coherent concept family per block
- 5 to 10 short items
- definition, positive recognition, negative contrast, boundary/unknown, and
  consolidation where evidence supports them
- multilingual items only when the evidence or generated material supports the
  exact teacher answer
- teacher answers below 256 UTF-8 bytes
- one epoch, batch size 1, learning rate `0.0002`
- no optimizer-option ablation during this baseline campaign
- no checkpoint promotion or automatic phase transition

## Evidence routing

Select the smallest useful set of files from these established sources:

- `training_data/kernel_from_redesign/household/`
- `training_data/kernel_from_redesign/animals/`
- `training_data/kernel_from_redesign/materials/`
- `training_data/kernel_from_redesign/space/`
- `training_data/kernel_from_redesign/properties/`
- `training_data/kernel_identity/knowledge/`
- `training_data/kernel_identity/unknowns/`
- `training_data/kernel_identity/chat_control/`
- `training_data/kernel_identity/correction/`

Use the repository evidence as authoritative. The executor context must include
`training/pipeline/script_schema.json` and only actual files, never directory
paths. Avoid repeating `container` immediately unless the preceding report
shows a concrete repair need.

Good initial evidence-backed families include:

- animal/category: `animals/animal/{what_is,classification}.md`
- cat/dog contrast: `animals/{cat,dog}/{what_is,classification}.md`
- bag/box/container transfer:
  `household/{bag,box}/{what_is,classification,negative_category}.md`
- inside/outside relation:
  `space/{inside,outside}/{what_is,connections}.md`
- big/small contrast:
  `properties/{big,small}/{what_is,properties}.md`

All paths in that list are relative to
`training_data/kernel_from_redesign/`; expand braces into existing individual
files when constructing executor context.

If a useful multilingual contrast is absent, the executor task may request
ephemeral teaching material with:

```json
{
  "material_generation": {
    "prompt": "A bounded request for exact teaching pairs and contrasts.",
    "provider_order": ["deepseek", "openrouter", "nvidia"],
    "max_tokens": 1024
  }
}
```

Generated material is untrusted context. The executor must still reconcile it
with repository evidence and author the final schema-valid script. Do not
generate material merely to vary phrasing.

## Overnight bounds

This first run is intentionally small. It should stop after its explicit
executor/strategic budget or deadline and leave a Lab inbox notice. A clean
budget stop is a successful unattended commissioning result, not an error.
