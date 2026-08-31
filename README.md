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

## Campaign 36C laboratories

`campaign36c/` now contains seven independently gated experiments:

- a standalone width-512 BDH-derived cell with UID-local optimizer ownership;
- a sparse, router-less wave substrate whose cost follows recruited tissue;
- executed-subgraph learning with eligibility, receipts, terminal reduction,
  retention rollback, and black-swan survival;
- developmental diagnosis and controlled growth, where persistent coherent
  capacity failure may allocate an off-graph shadow cell and one-off novelty,
  bad evidence, route errors, and harmful candidates may not;
- copy-on-write packed persistence and graph-halo residency, with stable UIDs,
  exact cold restore, crash-consistent commits, dirty-write coalescing, and I/O
  that follows touched tissue rather than total stored capacity;
- reversible structural compilation: measured co-access repacking, pairwise
  behavior-preserving fusion, canonical aliases with bounded trust continuity,
  explicit healing seams, rigidity audits, and mechanically gated early fission.
- deliberate metabolism: rooted vitality accounting, bounded-degree hygiene
  tracing, recoverable quarantine, same-UID shadow revival, and pressure-only
  purge with permanent UID retirement.

The Stage 1–6 Mission Hub jobs remain disabled and operator-approved. The
Stage-7 hygiene lab is enabled for bounded commissioning and still requires
explicit operator approval.
Stage 4 is packaged as `model.development_lab`; it performs shadow ablation,
low-authority probation, live retention checks, and structural rollback before
granting a newborn normal bounded propagation.
Stage 5 is packaged as `model.persistence_lab`; it measures page sizes rather
than assuming one, injects crashes at every commit boundary, and verifies that
inference remains read-only.
Stage 6 is packaged as `model.structural_lab`; it keeps physical packing,
execution fusion, and semantic healing distinct and refuses exact fission after
the preserved boundary becomes causally rigid.
Stage 7 is packaged as `model.hygiene_lab`; it protects useful routing and
abstention tissue, quarantines unreachable islands only at an idle lifecycle
boundary, checks bounded revival candidates before birth, and requires explicit
measured storage pressure before irreversible deletion.

## Deliberately excluded

Source control is not an artifact store. The following stay machine-local and
are backed up separately:

- model weights, checkpoints, and promoted builds;
- training corpora, images, captions, and frozen campaign payloads;
- Mission Hub databases, artifact objects, logs, and runtime evidence;
- generated feature arrays, caches, provider outputs, and credentials.

The editable training library lives under `training_data/` on Mission Hub.
`training_data/v8_curriculum/` is the sole authoritative lesson curriculum and
is version-controlled as an explicit exception to the general training-data
ignore rule. No lesson, render, handoff, or campaign payload outside that
directory is a valid curriculum source. Other campaign material is registered
by content hash and materialized on the trainbox only when an authorized job
requires it.

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
