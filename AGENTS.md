# AGENTS.md

## Mission

Implement **BDH Cognitive OS**, a modular runtime around the BDH model.

Follow the architecture defined in:

- `bdh_cognitive_os_design.md`
- `start_here.md`

Milestone 1 is complete. Current work should follow `start_here.md` priorities.

---

## Ground Truth Files

These define the system:

- `bdh_cognitive_os_design.md` — architecture
- `start_here.md` — evolving project guidance
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
