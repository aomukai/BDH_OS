# Ninereeds / BDH Cognitive OS

![BDH Cognitive OS](BDH.png)

This repository has two closely related goals:

1. **build the model itself** — a dragon-scale language model we are giving the proper name **Ninereeds**
2. **build the future OS around that model** — the BDH Cognitive OS runtime, LoRA harness, artifact system, and offline learning workflow that will come after the model is ready for it

Right now, the center of gravity is the **model and the data**: training corpus design, curriculum writing, wiki expansion, bridge material, and the groundwork needed to train Ninereeds from scratch into something coherent and teachable.

The OS/harness side is still important, but it is **not the current priority**. The long-term plan is to give Ninereeds a modular runtime with explicit routing, artifact logging, LoRA-based specialization, and offline consolidation. The near-term job is to make sure there is a real model worth building that system around.

## The Name

The model's proper name is **Ninereeds**.

The name comes from Terry Pratchett's *The Colour of Magic*: Ninereeds is the name of a dragon in the novel. That keeps the naming lineage intact with Pathway's **Baby Dragon** architecture while giving this project's model a proper individual name instead of calling the model by the architecture name.

## What We Are Building

### 1. The model

The intended model direction is:
- trained from scratch rather than treated as a thin wrapper around an existing assistant
- shaped through highly explicit curriculum design instead of broad noisy web-scale ingestion
- grounded in staged language learning: early curriculum → wiki knowledge → bridge material → story layers → later training infrastructure
- designed to become a boundary-aware, interest-forming, offline-capable core rather than a permanently internet-dependent chatbot

### 2. The training data

A large part of this repo is the construction of the training corpus itself.

That work currently includes:
- **Phase 1–5 rewritten curriculum** in `training_data/phase 1 to 5/rewritten/`
- **wiki corpus** in `training_data/wiki/`
- **Phase 6 bridge** material in `training_data/phase_6_bridge/`
- **story-layer planning and batches** in `training_data/triplet_stories/`

This data work is not secondary bookkeeping. It is part of the model-building process itself.

### 3. The future OS / harness

The repo also contains the planned and partially scaffolded path toward **BDH Cognitive OS**:
- a runtime around the model
- explicit session snapshots and disk artifacts
- future LoRA selection / routing
- specialist vs clean-core phases
- offline dream / consolidation workflows
- reproducible evaluation and verifier-style loops

That system matters, but it comes **after** the model is sufficiently real to justify it.

## Current Project State

At the moment, the repository is best understood as:
- **active model-and-corpus construction**, plus
- **early runtime / harness scaffolding for later stages**

Concretely:
- `bdh.py` and `core/` preserve the upstream BDH architecture/checkpoint artifacts and are treated as read-only ground truth here
- `training_data/` is the most actively evolving part of the repo
- the wiki, bridge, and story documents are being used to shape the actual educational/training pathway for Ninereeds
- runtime files like `harness.py`, `inference.py`, `prompt_shaper.py`, and `eval.py` represent the OS-side direction, but the repo should not be read as "mainly a harness project"

## Repository Map

```text
AGENTS.md                  implementation contract for coding agents
README.md                  repository overview
bdh.py                     upstream BDH architecture reference (read-only)
core/                      upstream checkpoint/model assets (read-only)
docs/                      design and planning documents
training_data/             curriculum, wiki, bridge, and story corpora
training/                  training-harness planning/docs
workflow/                  automation helpers and repo workflows
harness.py                 early runtime entry point / scaffold
inference.py               BDH loading and generation wrapper
prompt_shaper.py           prompt shaping layer
eval.py                    prompt-shaping evaluation harness
train.py                   training entry point
runs/                      timestamped run artifacts
sessions/                  session snapshots
loras/                     future skill/dream adapter area
dream_queue/               queued offline-consolidation items
knowledge/                 external memory / knowledge artifacts
```

## The Data Stack

### Phase 1–5 curriculum

Located under:
- `training_data/phase 1 to 5/rewritten/`

This is the early foundation layer: tightly controlled, concrete, dependency-shaped language learning material.

Key companion files include:
- `training_sequence.txt`
- `concept_index.md`
- `dependency_graph.json`
- `missing_curriculum_terms.md`

### Wiki corpus

Located under:
- `training_data/wiki/`

The wiki layer teaches grouped concept knowledge in a question-answer style and is being actively expanded, audited, and reorganized for dependency clarity.

Start with:
- `training_data/wiki/01_CORPUS_STATUS.md`
- `training_data/wiki/02_wiki_implementation_todo.md`
- `training_data/wiki/wiki_category_backlog.md`

Design notes:
- `docs/wiki.md`

### Phase 6 bridge

Located under:
- `training_data/phase_6_bridge/`

This is the connective layer between the strict early curriculum and later story/dialogue material. It introduces more abstract scaffold words and proposition-like forms in a controlled sequence.

Start with:
- `training_data/phase_6_bridge/README.md`
- `training_data/phase_6_bridge/phase_6_bridge_spec.md`
- `training_data/phase_6_bridge/phase_6_bridge_manifest.md`
- `training_data/phase_6_bridge/story_dialogue_progression.md`

### Story layers

Located under:
- `training_data/triplet_stories/`

These files are meant to follow the wiki/bridge rather than replace them. The goal is staged contextualization, not early collapse into free-form prose.

Start with:
- `training_data/triplet_stories/story_tier_specs.md`
- `training_data/triplet_stories/review_queue.md`
- `training_data/triplet_stories/review_notes.md`

## OS / Harness Direction

The long-term system design lives in:
- `docs/bdh_cognitive_os_design.md`

That design describes a future runtime with:
- core model + selected specialist path
- artifact-first execution
- clean-core reintegration
- future LoRA routing / registry
- offline dream-style consolidation

Important clarification: this design is the **target architecture**, not the best one-line summary of the repo's present focus.

A better present-tense summary is:

> We are building Ninereeds first, and building BDH Cognitive OS around Ninereeds second.

## Core Rules

- Never modify `bdh.py`
- Never modify anything in `core/`
- Never train during the live inference loop
- Never silently mutate model weights during a run
- Always write important outputs to disk
- Keep specialist and clean-core phases separate once the OS-side runtime is active

The fuller agent-facing contract is in [AGENTS.md](AGENTS.md).

## Useful Entry Points

If you are trying to understand the repo quickly, start here:

1. `README.md`
2. `AGENTS.md`
3. `docs/bdh_cognitive_os_design.md`
4. `docs/wiki.md`
5. `training_data/wiki/02_wiki_implementation_todo.md`
6. `training_data/wiki/01_CORPUS_STATUS.md`
7. `training_data/phase_6_bridge/phase_6_bridge_spec.md`
8. `training_data/triplet_stories/story_tier_specs.md`

## Training / Runtime Scripts Present In Repo

These files exist, but should be interpreted in context:
- `train.py`
- `harness.py`
- `inference.py`
- `prompt_shaper.py`
- `eval.py`
- `run_curriculum.sh`
- `run_wiki_level2_foundation.sh`

They show the repo's runtime/training direction, but they are not the whole story. The corpus and planning work under `training_data/` is just as central.

## Attribution

The upstream **BDH** architecture and the core implementation in `bdh.py` come from Pathway Technology, Inc.

- Paper: <https://arxiv.org/abs/2509.26507>
- Repository: <https://github.com/pathwaycom/bdh>

This repository builds a broader project around that base: curriculum creation, wiki growth, bridge/story planning, and the eventual OS/harness intended to support Ninereeds.

**Ninereeds is a name inspired by Terry Pratchett’s Discworld. This project is not affiliated with or endorsed by the Pratchett estate.**

## License

- Upstream BDH core: original upstream repository license
- Surrounding project files in this repo: MIT License unless noted otherwise

© Andi Omukai
