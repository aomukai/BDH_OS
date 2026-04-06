I'm building a cognitive OS for a small language model called BDH.  
Read `bdh_cognitive_os_design.md` for the full architecture and `bdh.py` for the model implementation.

The trained model is at `core/bdh_100m_final.pt`.  
Do not modify `bdh.py` or anything in `core/`.

## Project Status

### Milestone 1 — complete (runtime vertical slice)
- `inference.py`: loads checkpoint, byte-level tokenization, seeded generation
- `harness.py`: classify -> shape -> specialist -> reload -> final output -> save artifacts
- `prompt_shaper.py`: routes input to completion-friendly shapes (definition, qa, story, passthrough, fill)
- `eval.py`: comparative eval with scoring and failure-mode detection
- generation settings locked (`temperature=0.8`, `top_k=None`)

### Milestone 2 — LoRA research complete

What we built:
- HebbianLoRA on `encoder` + `encoder_v` (design spec), ~540K trainable params (~2.09%)
- SurfaceLoRA on `lm_head` for output shaping
- Three-layer training data strategy:
  - short anchor
  - expanded Q/A
  - subject repetition
- contrastive concept adjacency
- `train_lora.py` + `test_lora.py` for training/eval

Core finding:
- HebbianLoRA on shared encoder creates global bias, not local concept routing.
- Surface shaping works, but robust routing remains unsolved.
- Root cause: the model needs a stronger world model, not more tiny LoRA cycles.

Conclusion:
- OS infrastructure + richer curriculum is the right path.

## Curriculum Status

The curriculum uses short, concrete 6-sentence stories for world-model grounding.

Core parser:
- `workflow/parse_stories.py` -> `knowledge/curriculum/pairwise.jsonl` and `sliding.jsonl`

Current data files:
- `training_data/phase 1.md`
- `training_data/phase 2.md`
- `training_data/phase 3.md`
- `training_data/phase_4.md`
- `training_data/phase_4_ext.md`
- `training_data/phase_5_v1.md` (30 stories, core state->goal set)
- `training_data/phase_5_v1_1.md` (10 stories, speed/size extension)

Planning/design docs for Phase 5:
- `phase_5_plan.md`
- `phase_5_blueprint.md`
- `phase_5_v1_1_extension.md`

Notes:
- Phase 5 intentionally uses action-purpose recap in sentence 6 (for example, "The bird flies to the nest to sleep.").
- `parse_stories.py` currently warns on these recaps because validator expects category-like sentence 6 (`is/are` style).  
  This warning is expected for Phase 5 format.

## Current Priority

Two active tracks:

1. OS infrastructure from design doc sections 3-9:
- `loras/index.json` (registry + metadata + centroids)
- latent similarity classification -> LoRA selection
- dream queue candidate capture
- chat interface over harness loop

2. Curriculum maturation:
- train/eval with `phase_5_v1.md`
- ablate impact of `phase_5_v1_1.md`
- keep vocabulary concrete, repetitive, and compositional

## Working Principles

- No training in live inference loop.
- Keep core model clean between specialist and final phases.
- Persist artifacts and keep runs reproducible.
- Prefer simple, explicit implementation over cleverness.

Update this file whenever scope, priorities, or data assets change.
