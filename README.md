# Ninereeds

Ninereeds is a developmental learner model controlled by a single Mission Hub on the workstation and executed through a narrow, stateless trainbox agent.

## Current state

- The legacy dual-ledger/MSM pipeline is stopped and archived.
- Mission Hub is the sole authority for configuration, jobs, runs, decisions, artifact metadata, schedules, deployments, and evidence.
- The trainbox executes only versioned, allowlisted role releases. It has no competing job ledger.
- The Mission Hub backend and restricted trainbox boundary are commissioned; the commissioning healthcheck succeeded on 2026-08-06.
- Restricted artifact ingest/materialization/retrieval and bounded non-model GPU execution are commissioned.
- Mission Hub API and dispatcher services are enabled; the authenticated Lab is served privately through Tailscale.
- Campaign 33 is reconciled as an evolutionary regression/recovery experiment. Its certified baseline, evaluation suite, 500-concept knowledge snapshot, and branch 3's 12 ordered corpora are commissioned.
- Training and evaluation handlers are commissioned, but the global pipeline is paused with no training job queued. Branch 3 alone is authorized; branch 4 remains unauthorized until branch 3 completes.
- Automatic campaign rollover, Git mutation, checkpoint promotion, and automatic branch ranking remain disabled. Protected-registry storage cleanup is commissioned: it may remove only unprotected build bytes at a globally quiet boundary while retaining immutable lineage and deletion receipts.

Start with:

- `docs/mission_hub_architecture.md`
- `docs/mission_hub_operator_runbook.md`
- `docs/training_library.md`
- `docs/operations_audit_2026-08-05.md`
- `docs/physical_cleanup_2026-08-06.md`
- `docs/commissioning_2026-08-06.md`
- `docs/execution_path_commissioning_2026-08-06.md`
- `docs/campaign33_training_readiness_2026-08-06.md`

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

Do not start training from the legacy checkout or run archived scripts in place. Campaign 33 branch 3 is training-ready only through its authorized Mission Hub workflow. Use the Lab Start control to release it at the next safe daemon boundary; do not invoke the archived trainer directly.

The upstream BDH architecture in `bdh.py` originates from Pathway Technology, Inc. Ninereeds and its surrounding control, curriculum, and evaluation systems are this project's work.
