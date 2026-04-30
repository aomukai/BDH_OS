# AGENTS.md

## Mission

Implement **BDH Cognitive OS**, the future modular runtime around **Ninereeds**, the model being built in this repository on top of the BDH architecture.

Follow the architecture defined in:

- `docs/bdh_cognitive_os_design.md` — full architecture reference
- `README.md` — current repository overview and status
- `docs/wiki.md` — wiki corpus design notes

Milestone 1 is complete.

---

## Ground Truth Files

These define the system:

- `docs/bdh_cognitive_os_design.md` — architecture
- `README.md` — current repository overview and status
- `bdh.py` — model implementation (READ-ONLY)
- `core/phase_5.pt` — trained checkpoint (READ-ONLY)

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
- use `todo.md` at repo root as the single active task source
- move completed work into `history.md` at repo root instead of leaving it in the active todo

---

## Task Tracking

- `todo.md` at repo root is the single source of unfinished work.
- `history.md` at repo root is the completed-work log.
- Legacy queue/status docs live under `archive/` for reference only.

## Current Scope

Milestone 1 runtime scaffolding is already implemented (`inference.py`, `harness.py`, `prompt_shaper.py`, `eval.py`), but the current repo priority is still Ninereeds itself: corpus construction, curriculum shaping, wiki growth, bridge material, and the groundwork for later training.

Current active tracks:

1. **Model-and-corpus building for Ninereeds**
   - maintain and extend training corpora in `training_data/`
   - keep story format reproducible and parser-friendly where possible
   - preserve strict no-pronoun, concrete-language constraints in curriculum phases
   - manually polish wiki Level 1 files for simple child-facing language
   - prefer clear concept ownership across wiki categories to avoid duplicate anchors
   - clean and normalize existing wiki files before adding large amounts of new content

2. **Future OS infrastructure expansion** (design doc §§3-9)
   - LoRA registry/index and selection plumbing
   - classification and routing logic
   - dream queue capture
   - chat/runtime ergonomics

---

## Training Data — Current State

### Directory layout

```
training_data/
  phases/               ← canonical curriculum + bridge sequence
    phase_1/            ← 130 files: phase_1_001.md … phase_1_130.md
    phase_2/            ← 68 files:  phase_2_01.md  … phase_2_68.md
    phase_3/            ← 40 files:  phase_3_01.md  … phase_3_40.md
    phase_4/            ← files:     phase_4_01.md  …
    phase_5/            ← files:     phase_5_01.md  …
    phase_6/            ← bridge curriculum and phase-6 planning docs
    training_sequence.txt   ← flat ordered list of all active phase files
    concept_index.md        ← per-phase table + dependency annotations
    dependency_graph.json   ← machine-readable graph {files, sequence}
    missing_curriculum_terms.md ← curriculum/wiki gap ledger
  wiki/
    wiki_1/             ← Level 1 wiki corpus files (`*_entries*.md`)
    wiki_2/             ← Level 2 article files
    wiki_3/             ← Level 3 article files as they are created
    wiki_4/             ← Level 4 article files as they are created
    ...planning/index docs live at wiki root
```

### File naming convention

All phase files use numeric-only names: `phase_N_NNN.md`. No slugs, no infixes.
Phase 1 uses 3-digit padding (001–129). Other phases use 2-digit (01–NN).

### Curriculum format (phase 1–5)

Each file is exactly 4 `[user]`/`[Ninereeds]` blocks. Each block has:
- A question prompt (`[user]`)
- `[Ninereeds]` response: 5 lines — 4 body lines + 1 summary definition on line 5

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

Wiki files use a question-answer format with simple child-facing prose.
Current Level 1 target is usually 5 short sentences: identity, a few concrete
facts, then a final contrast (`A X is not a Y`).
Level-specific corpus layout now lives under:
- `training_data/wiki/wiki_1/` = Level 1 files
- `training_data/wiki/wiki_2/` = Level 2 article files
- `training_data/wiki/wiki_3/` = Level 3 article files
- `training_data/wiki/wiki_4/` = Level 4 article files

General terms should usually come before narrower terms inside a file.
Avoid duplicate `what is X?` anchors across files unless the duplication is
intentional and clearly justified.
Do not apply the phase 1–5 vocab constraints to wiki files.

`archive/training_data/wiki/` holds old aggregate/schema files and legacy task docs that are not active planning sources.

### Wiki category backlog

`training_data/wiki/wiki_category_backlog.md` — canonical list of 88 wiki
categories to write, in priority order. Each entry has status (MISSING /
PARTIAL / COVERED), sequence (early / middle / late), examples, dependencies,
and coverage notes. Use this as the source of truth when deciding what to write
next.

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
