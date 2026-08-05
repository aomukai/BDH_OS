# Ninereeds

Ninereeds is a developmental learner model controlled by a single Mission Hub on the workstation and executed through a narrow, stateless trainbox agent.

## Current state

- The legacy dual-ledger/MSM pipeline is stopped and archived.
- Mission Hub is the sole authority for configuration, jobs, runs, decisions, artifact metadata, schedules, deployments, and evidence.
- The trainbox executes only versioned, allowlisted role releases. It has no competing job ledger.
- The Mission Hub backend and restricted trainbox boundary are commissioned; the commissioning healthcheck succeeded on 2026-08-06.
- Mission Hub API and dispatcher services are enabled, while trainbox maintenance mode prevents further leases.
- Training and evaluation jobs, schedules, external calls, automatic rollover, pruning, and live execution are disabled.
- The old Lab is stopped and archived. A new Lab will be built last against the Mission Hub API.

Start with:

- `docs/mission_hub_architecture.md`
- `docs/mission_hub_operator_runbook.md`
- `docs/training_library.md`
- `docs/operations_audit_2026-08-05.md`
- `docs/physical_cleanup_2026-08-06.md`
- `docs/commissioning_2026-08-06.md`

## Live repository map

```text
mission_hub/             authoritative control-plane implementation
config/mission_hub/      strict operational configuration
schemas/mission_hub/     job and transport contracts
cortex/                  current Cortex model implementation
bdh.py                   BDH architecture used by Cortex
training/optim/          retained optimizer
training/pipeline/cortex retained runtime evaluation/script adapters
meta/scripts/            four explicit Cortex runtime entry points
tests/                   tests for the retained system
docs/                    current architecture and model references
```

Human data and machine artifacts are deliberately outside source releases:

```text
training_data/           canonical editable training-material library on Mission Hub
core/                    local checkpoint/artifact root
checkpoints/             promoted checkpoint lineage
archive/                 historical material awaiting later review
```

`training_data/` is not obsolete. It is the operator-maintained source library. Mission Hub will turn selected material into immutable, content-hashed shards; only job-referenced shards are materialized on the trainbox.

## Safety

Do not start training from the legacy checkout or run archived scripts in place. The backend transport is commissioned, but checkpoint content certification, disposable job commissioning, and explicit operator authorization remain required before any training restart.

The upstream BDH architecture in `bdh.py` originates from Pathway Technology, Inc. Ninereeds and its surrounding control, curriculum, and evaluation systems are this project's work.
