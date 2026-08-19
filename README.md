# Ninereeds

Ninereeds is a developmental-learning research system operated across two
machines. A single Mission Hub on the workstation owns configuration,
authorization, scheduling, evidence, and recovery. A restricted trainbox agent
executes only versioned, allowlisted releases dispatched by Mission Hub.

## Repository scope

This repository contains the executable system and its contracts:

```text
mission_hub/             authoritative workstation control plane
config/mission_hub/      strict runtime and deployment configuration
schemas/mission_hub/     job, workflow, evidence, and transport contracts
cortex/ and bdh.py       model architecture source
training/                optimizer, diagnostics, and runtime adapters
meta/scripts/            explicit model and service entry points
image_registry/          image-corpus indexing and review tooling
image_benchmark/         bounded image-review workers
tests/                   regression and safety tests
docs/                    architecture, operations, and research documentation
```

The deployment contract in `config/mission_hub/deployments.toml` defines
separate Mission Hub and trainbox release boundaries. The trainbox is not an
independent scheduler and does not own a competing job ledger.

## Deliberately excluded

Source control is not an artifact store. The following stay machine-local and
are backed up separately:

- model weights, checkpoints, and promoted builds;
- training corpora, images, captions, and frozen campaign payloads;
- Mission Hub databases, artifact objects, logs, and runtime evidence;
- generated feature arrays, caches, provider outputs, and credentials.

The editable training library lives under `training_data/` on Mission Hub.
Campaign material is registered by content hash and materialized on the
trainbox only when an authorized job requires it. Neither directory is shipped
in source releases.

## Safety boundary

Training and evaluation run only through Mission Hub authorization. The
trainbox accepts a release only when its source, configuration, required paths,
and model dependencies match the commissioned deployment manifest. Automatic
checkpoint promotion, branch ranking, and Git mutation remain disabled.

Start with:

- `docs/mission_hub_architecture.md`
- `docs/mission_hub_operator_runbook.md`
- `docs/training_library.md`
- `docs/operations_audit_2026-08-05.md`

The upstream BDH architecture in `bdh.py` originates from Pathway Technology,
Inc. Ninereeds and its control, curriculum, and evaluation systems are this
project's work.
