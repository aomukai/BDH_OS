# AGENTS.md

## Mission

Implement **BDH Cognitive OS**, a modular runtime around the BDH model.

Follow the architecture defined in:

- `bdh_cognitive_os_design.md`
- `start_here.md`

Focus ONLY on **Milestone 1: minimal vertical slice**.

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

## Current Milestone (STRICT SCOPE)

Build a **minimal working pipeline**:

1. Load core model (`core/bdh_100m_final.pt`)
2. Accept a single request (CLI input is enough)
3. Run **core-only inference**
4. Simulate Skill_LoRA selection (no real LoRA math yet)
5. Produce a "specialist output"
6. Save full run artifact
7. Reload clean core state
8. Generate final output from clean core

DO NOT implement:
- Dream system
- LoRA training
- routing intelligence beyond placeholder logic

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
