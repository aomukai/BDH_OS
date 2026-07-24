# Ninereeds / BDH Cognitive OS

![BDH Cognitive OS](docs/BDH.png)

This repository has two closely related goals:

1. **Build Ninereeds** — a small Developmental Learner Model trained through explicit curriculum, chat evidence, repair, and protected-anchor checks.
2. **Build the future BDH Cognitive OS around it** — a runtime with artifacts, routing, LoRA/specialist paths, notifications, and offline consolidation once the model is ready for that layer.

Current center of gravity: **Mommy Says Machine (MSM)**, a session-based training pipeline. The old broad `corpus -> epochs -> eval -> winner` campaign loop is now historical infrastructure, not the active procedure.

---

## What Kind Of Model Is This

Ninereeds is a **Developmental Learner Model (DLM)**, not a web-scale LLM.

The distinction matters:

- It is small, (around 25M, 150M, 604M, 1.2B parameters), so every malformed training example has outsized impact.
- The goal is not broad language coverage. The goal is stable concept identity, grounded contrasts, and reliable answers under retrieval pressure.
- Training is staged. Understanding, recalling, contrasting, and using a concept in richer contexts are treated as separate levels.
- Evaluation is evidence-driven: chat logs, report cards, protected anchors, grounding evals, and brain maps are used to decide the next intervention.

The model's proper name is **Ninereeds**, inspired by the dragon name in Terry Pratchett's *The Colour of Magic*. The architecture lineage comes from Pathway's Baby Dragon / BDH work, but Ninereeds is this project's individual model.

## Current State

Active regime as of 2026-07-01:

- **Training method:** MSM session training, not broad corpus pretraining.
- **Protected baseline:** `core/c17_contrast_angle_1200_e4.pt`.
- **Active work:** concept-card tutor loop, orchestration artifacts, schemas, sentinels, and the buffered micro-update backend.
- **Update backend:** `meta/scripts/msm_micro_update.py`.
- **Canonical runbook:** `training/pipeline/runbook.md`.
- **Historical campaign infrastructure:** archived under `archive/training_pipeline/`.

Do not continue from C17 repair branches unless an explicit recovery experiment chooses that path.

## Active MSM Pipeline

MSM is a closed-loop teaching pipeline, not one model:

```text
orchestrator plan
  -> executor script generation
  -> trainer fixed-script execution
  -> raw chat log
  -> executor per-item grading and report card
  -> executor auto-advance or orchestrator decision
  -> optional replay / repair / probe / brain scan / buffered micro-update
```

The atomic unit is a **scripted word/card session**. One session targets one concept or one repair objective. Raw chat logs are evidence only; they are never ingested directly as training data.

Roles:

- **Orchestrator** owns strategy, checkpoint protection, queue policy, update approval, and escalation.
- **Executor** runs on a capable local model, writes bounded scripts, grades raw logs, fills report cards, and proposes trainable turns.
- **Trainer** is a deterministic runner, usually a Python script, that executes fixed scripts against Ninereeds and writes raw logs.
- **The Lab** exposes machine health, durable control receipts, reports, messages, and human-attention sentinels.

The executor may auto-advance through the word queue only while policy allows it, at least one scripted item is correct or repaired by correction, and no answer is off-topic. If no item is correct or any answer is off-topic, the executor wraps the session and escalates to the orchestrator.

Only orchestrator-approved records copied into `approved_training.jsonl` may enter a micro-update.

## Repository Map

```text
README.md                  repository overview
index.md                   fresh-session index and current active pointers
todo.md                    active work queue
history.md                 completed work log
CLAUDE.md                  local operating constraints for agent sessions

bdh.py                     BDH architecture reference plus opt-in experiment variants
train.py                   training entry point used by legacy and MSM update paths
eval.py                    shaped/diagnostic evaluation entry point
harness.py                 early runtime / OS-side scaffold

core/                      local working checkpoints; includes protected baseline
checkpoints/               promoted checkpoint lineage
docs/                      long-term design docs and diagnostic manuals
inventory/                 word, concept, and dependency inventories
meta/scripts/              generators, evaluators, campaign tools, MSM update backend

training/pipeline/         active MSM docs, schemas, runbook, and contracts
training/msm/              planned runtime state: sessions, buffers, updates, logs
training/corpus/           generated campaign/update corpora
training/corpus_admin/     corpus manifests, ordering, probe sets, and admin files
training/logs/             campaign reports, grounding evals, brain maps, traces
training/harness/          older harness policy/templates
training_data/             generated curriculum/corpus source material

archive/training_pipeline/ archived epoch-campaign pipeline docs and configs
archive/                   other historical plans, scripts, reports, and queues
loras/                     future specialist / adapter area
```

## Architecture Experiment Mode

`bdh.py` preserves the upstream-style BDH baseline by default. Experimental
architecture changes are opt-in through `BDHConfig` and `train.py` flags, and
are documented in `docs/bdh_experimental_variants.md`.

Current controlled variants:

- `bdh_v1`: baseline behavior; no temporal additions.
- `temporal_decay`: causal attention distance decay, preferably configured by
  `--attention-half-life-tokens`.
- `ctm_lite`: CTM-inspired sparse activation history plus attention decay.
  Adaptive compute is not enabled automatically; treat it as a separate
  generation/eval policy experiment.

Architecture experiments should use held-out eval data:

```bash
python train.py \
  --phase 0 \
  --corpus-file path/to/train.txt \
  --eval-corpus-file path/to/eval.txt \
  --architecture-variant temporal_decay \
  --attention-half-life-tokens 512
```

When eval data is provided, checkpoints are selected by eval loss. Checkpoint
metadata records command-line args, seed, git commit, corpus/eval hashes,
training settings, train/eval loss, and sparse-state diagnostics. Diagnostics
track logit entropy, compute-tick deltas, sparse activation density/magnitude,
and effective attention half-life.

## Active Pipeline References

Start here for current training work:

| Need | File |
|---|---|
| Fresh-session orientation | `index.md` |
| BDH architecture variants | `docs/bdh_experimental_variants.md` |
| Active work queue | `todo.md` |
| Executable MSM steps | `training/pipeline/runbook.md` |
| MSM doctrine and constraints | `training/pipeline/training.md` |
| Pipeline/dataflow map | `training/pipeline/pipeline.md` |
| Mommy Says system boundary | `training/pipeline/mommy_says_machine.md` |
| Concept-card tutor method | `training/pipeline/tutor_loop.md` |
| Session/update decision semantics | `training/pipeline/iteration_schema.md` |
| Script/raw-log contract | `training/pipeline/script_and_raw_log_schema.md` |
| Sentinel contract | `training/pipeline/sentinel_files.md` |
| Config contract | `training/pipeline/msm_config.md` |
| Report-card schema | `training/pipeline/session_report_schema.md` and `.json` |
| Training-turn schema | `training/pipeline/training_turn_schema.json` |
| Update artifact contract | `training/pipeline/update_artifact_schema.md` |
| Micro-update backend | `meta/scripts/msm_micro_update.py` |

When markdown and JSON disagree for a session, `report_card.json` is authoritative.

## Corpus And History

The completed corpus work still matters, but it is no longer the main active loop.

- `training_data/` contains generated curriculum sources: phases, language material, wiki-style knowledge, stories, identity/boundary material, and reasoning data.
- `training/corpus/` contains assembled campaign and update corpora.
- `training/corpus_admin/` contains manifests, probe sets, kernel format notes, and ordering files.
- `training/logs/` contains historical campaign reports, grounding evals, brain maps, and trace reports.
- `archive/training_pipeline/` contains the deprecated epoch-campaign flow and C17 campaign configs.

Use historical campaign files for evidence and comparison experiments. Do not treat them as the active training procedure.

## Core Rules

- Do not casually modify `bdh.py`.
- Do not casually modify checkpoint files in `core/`.
- Do not continue from C17 repair branches unless an explicit experiment chooses that path.
- Never train from raw chat logs.
- Never silently mutate weights during a run.
- Always write important outputs to disk.
- Keep report generation, orchestration decisions, and update approval as separate gates.
- Protected-anchor regression blocks promotion.

## Long-Term OS Direction

The future BDH Cognitive OS design lives in `docs/bdh_cognitive_os_design.md`.

That target architecture includes:

- core model plus specialist paths
- explicit routing and artifact-first execution
- future LoRA routing / registry
- clean-core reintegration
- offline consolidation workflows

Present-tense summary: **build Ninereeds first, then build BDH Cognitive OS around Ninereeds.**

## Attribution

The upstream **BDH** architecture and the core implementation in `bdh.py` come from Pathway Technology, Inc.
I implemented improvements to the architecture, inspired by Sakana AI's Continuous Thought Machines paper.

- BDH Paper: <https://arxiv.org/abs/2509.26507>
- CTM Paper: <https://arxiv.org/abs/2505.05522>
- Repository: <https://github.com/pathwaycom/bdh>

This repository builds a broader project around that base: curriculum creation, active MSM training, diagnostic tooling, and the eventual OS/harness intended to support Ninereeds.

**Ninereeds is a name inspired by Terry Pratchett's Discworld. This project is not affiliated with or endorsed by the Pratchett estate.**

## License

- Upstream BDH core: original upstream repository license.
- Surrounding project files in this repo: MIT License unless noted otherwise.

© Andi Omukai
