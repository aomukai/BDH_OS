# L001 handhold selection dry run

This fixture proves deterministic selection of conducted position 2 (`L001`) after the exact
prefix `[L000]`. Its learner state and evidence IDs are explicitly synthetic. It cannot authorize
a live lesson, pixel generation, cursor advancement, or training.

Generate the disposable selection packet outside this tracked directory:

```bash
python3 mission_hub/skills/compile-next-lesson/scripts/compile_lesson.py select-next \
  --curriculum docs/curriculum_v6_sol/curriculum_v6.json \
  --rehearsal-layer docs/curriculum_v6_sol/rehearsal_layer_v6.json \
  --cursor mission_hub/skills/compile-next-lesson/examples/l001-handhold/cursor.json \
  --known-closure mission_hub/skills/compile-next-lesson/examples/l001-handhold/known-closure.json \
  --output /tmp/ninereeds-l001-selection.json
```

The next manual gates are intentional: replace the fixture with actual learner evidence; let
Luna author the complete lesson; obtain an independent Sol pass; commission and verify every
required image; then freeze. No fixture pretends those gates have passed.
