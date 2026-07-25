# Cortex Autonomous Campaign Policy

This policy governs the first unattended research campaign for the production
Ninereeds architecture:

```text
frozen mBERT -> trainable Ninereeds 1.2B core -> frozen LFM2.5-230M
```

The terminal seed is the commissioned multilingual `container` MSM checkpoint.
Every live Cortex block is followed by a deterministic `cortex_evaluation`
child. New weights remain quarantined until that child compares the candidate
with its parent on the fixed held-out language suite, protected anchors,
generation-pathology checks, and Cortex activation health. The evaluation
report's top-level `checkpoint_after` is the only permitted next parent: it is
the candidate after admission and the rollback parent after rejection.

The executor and strategic model cannot promote checkpoints. Admission is a
deterministic certificate, not a language-model decision.

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
- no executor-controlled checkpoint promotion or automatic phase transition

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

## Campaign publication and retention

The workstation assigns the campaign a monotonic number and publishes one
coherent artifact set below `training/logs/campaign_<number>_reports/`:

- manifest and human report
- machine-readable metrics and admission decision
- exact held-out transcripts
- Cortex MRI, 3D representation map, and atlas
- checkpoint retention manifest

These files are durable local Lab state and are intentionally ignored by Git so
an unattended campaign cannot dirty or block the code checkout.

Before every training block, the trainbox checks filesystem watermarks and
space for at least three expected full checkpoints. At the pruning watermark it
may delete only unpinned, registry-certified rejected/retired candidates or
superseded winners outside the rolling winner window. The active parent,
rollback targets, pinned milestones, latest five admitted winners, and two
recent rejected examples per campaign remain protected.
