# Visual lesson material

This directory turns the authoritative language lessons into auditable visual
material contracts.  It does not replace the lesson Markdown.

Each contract keeps three things separate:

1. **Presentation** uses a verified example and supplies the answer.
2. **Practice** asks the same controlled question form with the answer withheld.
3. **Performance** recombines learned material in a new world-bible scene and
   asks about a selected entity through a literal crop or highlight.

The scene is never allowed to determine its own teaching claim.  Every turn is
bound to a scene entity with a verified label and truth value.  In particular, a
negative question must focus an entity whose verified label differs from the
queried label.

## Asset families

- Generic photographs or simple renders teach concrete referents during
  Presentation and Practice.  They come from the reviewed image registry.
- Canonical references preserve recurring character and location identity.
  They are production inputs, not generic noun-teaching images.
- A Performance master is a newly composed, independently reviewed scene.
  Its crops and highlights are deterministic derivatives of that master.

All accepted masters and derivatives must be hash-addressed.  Metadata,
captions, prompts, and filenames are retrieval evidence only; they are not
pixel-level acceptance.

`contracts/L001.json` is the first worked contract.  It deliberately leaves
generic asset bindings and Performance pixels unresolved until the normal
review cascade has accepted them.

## Inventory

Run the read-only curriculum compiler to produce a machine-readable worklist:

```bash
python3 training_data/v8_curriculum/tools/build_visual_worklist.py \
  --output /tmp/v8-visual-worklist.json
```

Validate every checked-in visual contract with:

```bash
python3 training_data/v8_curriculum/tools/validate_visual_contracts.py
```
