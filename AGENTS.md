# AGENTS.md

## Mission

Implement **BDH Cognitive OS**, a modular runtime around the BDH model.

Follow the architecture defined in:

- `docs/bdh_cognitive_os_design.md` — full architecture reference
- `docs/start_here.md` — evolving project guidance
- `docs/wiki.md` — wiki corpus design notes

Milestone 1 is complete.

---

## Ground Truth Files

These define the system:

- `docs/bdh_cognitive_os_design.md` — architecture
- `docs/start_here.md` — evolving project guidance
- `bdh.py` — model implementation (READ-ONLY)
- `core/bdh_100m_final.pt` — trained checkpoint (READ-ONLY)

---

## HARD CONSTRAINTS (DO NOT VIOLATE)

### Never modify:

- `bdh.py`
- anything in `core/`

### Never do:

- train during inference
- modify model weights during live loop
- auto-create or activate Dream_LoRAs
- silently mutate session state
- create hidden/global state

### Always:

- write outputs to disk
- keep runs reproducible
- separate specialist and clean-core phases

---

## Current Scope

Milestone 1 runtime is already implemented (`inference.py`, `harness.py`, `prompt_shaper.py`, `eval.py`).

Current active tracks:

1. **OS infrastructure expansion** (design doc §§3-9)
   - LoRA registry/index and selection plumbing
   - classification and routing logic
   - dream queue capture
   - chat/runtime ergonomics

2. **Curriculum/data quality**
   - maintain and extend training corpora in `training_data/`
   - keep story format reproducible and parser-friendly where possible
   - preserve strict no-pronoun, concrete-language constraints in curriculum phases

---

## Training Data — Current State

### Directory layout

```
training_data/
  phase 1 to 5/
    rewritten/          ← canonical curriculum (use this)
      phase_1/          ← 129 files: phase_1_001.md … phase_1_129.md
      phase_2/          ← 68 files:  phase_2_01.md  … phase_2_68.md
      phase_3/          ← 40 files:  phase_3_01.md  … phase_3_40.md
      phase_4/          ← files:     phase_4_01.md  …
      phase_5/          ← files:     phase_5_01.md  …
      training_sequence.txt   ← flat ordered list of all 352 files
      concept_index.md        ← per-phase table + dependency annotations
      dependency_graph.json   ← machine-readable graph {files, sequence}
    deprecated/         ← old/superseded files, do not use for training
  wiki/                 ← wiki-style concept entries (higher register)
```

### File naming convention

All phase files use numeric-only names: `phase_N_NNN.md`. No slugs, no infixes.
Phase 1 uses 3-digit padding (001–129). Other phases use 2-digit (01–NN).

### Curriculum format (phase 1–5)

Each file is exactly 4 `[user]`/`[assistant]` blocks. Each block has:
- A question prompt (`[user]`)
- `[assistant]` response: 5 lines — 4 body lines + 1 summary definition on line 5

**Hard constraints:**
- No pronouns anywhere
- No vocab in a summary word that hasn't appeared in the body of that block or
  any body line in any earlier file (cumulative vocab bank)
- Body lines are concrete and affirmative — no negation, no speculation
- The 4 questions per file follow a standard arc: appearance → location → behaviour → use/effect

### Dependency ordering

The training sequence is NOT file-number order. Always use `training_sequence.txt`
as the authoritative order. The sequence was topologically sorted so that every
concept appears before any file that references it. Key chains:

- bee (pos 123) → honey (pos 124) → beehive → jar of honey
- tree → wood → woodland → block of wood
- finger → thumb

### Phase 5 — animal × state grid

Phase 5 combines 5 animals (bunny, bird, frog, fish, duck) × 3 states
(hungry, sleepy, thirsty) = 45 files, balanced at 3 files per animal per state.
Exception: no thirsty-fish entries (fish live in water; concept doesn't hold).

### Wiki format

Wiki files use a question-answer format but at a higher register — full prose,
longer answers, contrast statements at the end (`A X is not a Y`).
Wiki entries are grouped by domain (e.g. `places_and_landforms_entries.md`).
Do not apply the phase 1–5 vocab constraints to wiki files.

---

## Definition of Done

A correct implementation must:

- run end-to-end from a single command
- create a folder under `runs/<timestamp>/`
- write ALL of:

```text
request.json
session_snapshot.json
selected_lora.json
specialist_output.md
final_output.md
metadata.json
logs.txt
```

- produce consistent results across runs
- leave core model unchanged

---

## Required Directory Structure

Create if missing:

```text
workflow/
runs/
sessions/
loras/skills/
loras/dreams/
dream_queue/
knowledge/
```

No random files in root.

---

## Implementation Rules

- Python only
- minimal dependencies
- no frameworks unless necessary
- explicit over implicit
- readable > clever

---

## Execution Model (MANDATORY)

Follow this EXACT order:

1. request → classify
2. snapshot session
3. run specialist phase
4. save artifact
5. reload clean core
6. read artifact
7. produce final output

No shortcuts.

---

## LoRA Handling (Milestone 1)

- simulate only
- use placeholder JSON like:

```json
{
  "lora": "none",
  "type": "core-only"
}
```

Do NOT implement real LoRA logic yet.

For future milestones, any real LoRA attachment/training must remain offline and explicitly approved.

---

## Error Handling

- fail loudly
- never silently skip steps
- log everything to `logs.txt` inside run folder

---

## If Something Is Unclear

Default to:

> simplest implementation that preserves architecture

Do NOT expand scope.
