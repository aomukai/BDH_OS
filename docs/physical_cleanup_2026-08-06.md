# Physical cleanup manifest — 2026-08-06

## Purpose

This cleanup reduces the live Ninereeds trees to the reconciled Mission Hub control plane, the trainbox runtime surface, canonical human data, and protected artifacts. It does not decide which historical material may eventually be destroyed.

## Live workstation surface

- `mission_hub/`, `config/mission_hub/`, and `schemas/mission_hub/`;
- `bdh.py`, `cortex/`, `training/optim/`, and the explicit trainbox runtime modules declared in `config/mission_hub/deployments.toml`;
- `meta/scripts/cortex_runtime.py`, `train_cortex.py`, `evaluate_cortex.py`, and `probe_cortex_checkpoint.py`;
- tests that exercise the retained Mission Hub, Cortex, BDH, optimizer, and release contracts;
- current architecture, audit, migration, operator, training-library, and core-model documentation;
- the canonical editable `training_data/` library;
- local checkpoint/artifact roots `core/` and `checkpoints/` pending content certification.

## Workstation archive destination

Obsolete live-tree material moves to `archive/workstation/cleanup-2026-08-06/` with its original repository-relative layout preserved. This includes the old Lab, legacy control/MSM pipeline, old executor and campaign tooling, historical assembled corpora and corpus administration, old visual pipeline, stale tests/docs, logs, run output, temp output, handoffs, and all `meta/scripts` entries except the four declared runtime entry points.

Nothing moved into this subtree is deleted during this cleanup. Existing contents elsewhere under `archive/` are not reorganized.

## Trainbox rule

The old mutable trainbox checkout is not an authority. Before removing anything from it:

1. compare the canonical training library by content, independently of paths;
2. transfer files missing or different at the corresponding Mission Hub path to `archive/trainingbox/cleanup-2026-08-06/`;
3. verify the transfer;
4. retain `core/` and `checkpoints/` in place for later checkpoint certification;
5. remove the redundant trainbox `training_data/` only after the content multiset is proven identical;
6. remove obsolete checkout files only after unique/different material has been preserved on Mission Hub.

The clean extracted trainbox role candidate under `~/.local/share/ninereeds/releases/` remains separate from the legacy checkout. No deployment is activated and no training service is enabled by this cleanup.

## Explicit exclusions

- Hermes is unrelated to Ninereeds and is not touched.
- Provider secrets and `.env` are not copied into archives.
- Checkpoint/model bytes are not deleted, moved, or content-certified here.
- Existing Mission Hub evidence archives are not modified.
- No remote branch is pushed and no service is commissioned.

## Completed result

The workstation archive initially received 9,885 files totaling approximately 1.7 GB. The live `meta/scripts` directory now contains four files instead of 199. Removal of the final legacy MSM script-input adapter and Lab-only test helper leaves 45 Python or shell source files outside tests, plus 12 focused test modules and their package marker.

The trainbox comparison transferred 318 missing or same-path-different files (approximately 7 MB) into `archive/trainingbox/cleanup-2026-08-06/`. A checksum dry run after transfer reported zero remaining unpreserved files within the comparison scope. The transfer includes the trainbox-only MSM phase-block/session evidence and `.codex-stage-c30` staging files.

The trainbox's 244,388-file `training_data/` tree was then removed because its complete content multiset had already been proven identical to the canonical Mission Hub library (`62f0a546f4979d484fa639429e5c4703510941ae636c6fbae6e7ef09cf394be5`). The legacy mutable checkout was reduced to `.env`, `core/` (612 files, approximately 115 GB), and `checkpoints/` (17 files, approximately 2.1 GB). Its clean extracted role candidate remains outside the checkout under `~/.local/share/ninereeds/releases/`.

`ninereeds-lab.service` was stopped and disabled before the Lab files moved. `hermes-gateway.service` remained active and enabled and was not otherwise touched.
