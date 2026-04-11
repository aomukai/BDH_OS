# BDH Cognitive OS

![BDH Cognitive OS](BDH.png)

BDH Cognitive OS is a modular runtime built around the **Baby Dragon Hatchling (BDH)** model.

The project is built around a simple discipline: keep the core model clean, route work through explicit phases, and write each important artifact to disk.

## What It Is

BDH Cognitive OS treats the model less like a single monolithic assistant and more like a small operating system with explicit boundaries.

The current design centers on:

- a **clean core model** for language and reasoning
- a **specialist phase** for task-specific work
- a **clean-core integration phase** after specialist work completes
- **explicit artifact logging** for reproducibility and inspection
- a future **Dream system** for offline consolidation only

The architecture reference lives in [docs/bdh_cognitive_os_design.md](docs/bdh_cognitive_os_design.md).

## Current Status

Milestone 1 runtime is implemented, and the repository now contains a working vertical slice of the live loop.

Current working pieces:

- `harness.py` runs the end-to-end live loop
- `inference.py` loads the BDH checkpoint and performs generation
- `prompt_shaper.py` reshapes prompts into completion-friendly forms
- `eval.py` compares raw prompts against shaped prompts
- `training_data/` contains the curriculum and wiki corpus work

Current active development is split between:

- OS infrastructure expansion: routing, LoRA registry plumbing, dream queue capture, chat ergonomics
- curriculum and wiki quality: extending and cleaning training data while preserving reproducibility

## Core Rules

- Never modify `bdh.py`
- Never modify anything in `core/`
- Never train during the live inference loop
- Never mutate model weights during a run
- Always write outputs to disk
- Always keep specialist and clean-core phases separate

The fuller agent-facing contract is in [AGENTS.md](AGENTS.md).

## Repository Map

```text
AGENTS.md                  implementation contract for coding agents
README.md                  repository overview
docs/
  bdh_cognitive_os_design.md
  wiki.md
  mommy_says_machine.md
bdh.py                     BDH architecture (read-only)
core/                      trained checkpoint(s) and model assets (read-only for runtime work)
harness.py                 top-level runtime entry point
inference.py               BDH loading and text generation wrapper
prompt_shaper.py           prompt shaping layer
eval.py                    prompt-shaping evaluation harness
train.py                   training entry point
training_data/             curriculum and wiki corpora
workflow/                  workflow helpers and future OS infrastructure
runs/                      timestamped run artifacts
sessions/                  session snapshots
loras/                     skill and dream adapter directories
knowledge/                 external memory / knowledge artifacts
dream_queue/               queued items for future offline consolidation
```

## Runtime Flow

The live loop follows this order:

1. request -> classify
2. snapshot session
3. run specialist phase
4. save artifact
5. reload clean core
6. read artifact
7. produce final output

In Milestone 1, LoRA selection is simulated only. The runtime writes a placeholder `selected_lora.json` rather than attaching a real adapter.

## Running The Harness

From the repo root:

```bash
python harness.py "What is a book?"
```

Or run interactively:

```bash
python harness.py
```

Each run creates a timestamped directory under `runs/` and writes:

- `request.json`
- `session_snapshot.json`
- `selected_lora.json`
- `specialist_output.md`
- `final_output.md`
- `metadata.json`
- `logs.txt`

## Evaluation

To compare raw prompts with shaped prompts:

```bash
python eval.py
```

This writes an eval run directory under `runs/` with scored outputs and a summary.

## Training Data

The corpus currently has two main layers:

- **Curriculum files** in `training_data/phase 1 to 5/rewritten/`
- **Wiki files** in `training_data/wiki/`

The wiki corpus teaches higher-level relational and conversational knowledge using grouped `what is X?` entries. The design notes are in [docs/wiki.md](docs/wiki.md), and the current category planning source of truth is [training_data/wiki/wiki_category_backlog.md](training_data/wiki/wiki_category_backlog.md).

## Training Scripts

Two helper scripts are currently present:

- `run_curriculum.sh` for phased curriculum training and eval gating
- `run_wiki_level2_foundation.sh` for building and training a merged wiki foundation corpus

These are training workflows, not part of the live runtime loop.

## Attribution

BDH architecture and the core model implementation in `bdh.py` are by Pathway Technology, Inc.

- Paper: <https://arxiv.org/abs/2509.26507>
- Repository: <https://github.com/pathwaycom/bdh>

## License

- BDH core: original upstream repository license
- BDH Cognitive OS harness and surrounding project files: MIT License

© Andi Omukai
