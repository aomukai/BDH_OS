# Mission Hub operator runbook

The pipeline remains stopped. Commands below are grouped by whether they are safe now or require a later commissioning decision.

## Safe inspection

```bash
python3 -m mission_hub config-validate
python3 -m mission_hub status
python3 -m mission_hub list machines
python3 -m mission_hub list deployments
python3 -m mission_hub list campaigns
python3 -m mission_hub list evidence_sources
python3 -m mission_hub list events
python3 -m mission_hub readiness
```

`status` must report SQLite integrity `ok`, no foreign-key errors, and a valid event chain.

`readiness` separates the safe backend foundation from commissioning and training-restart gates. A healthy stopped rebuild should report `backend_ready=true`, `commissioning_ready=false`, and `training_restart_ready=false` until clean releases and explicit commissioning occur. After a successful commissioning healthcheck and restoration of maintenance mode, `commissioning_ready=true` and `training_restart_ready=false` is the intended stopped state.

## Configuration activation

Activation is a backend database operation, not service activation:

```bash
python3 -m mission_hub config-activate
```

It validates every document, relation, schema path, job route, retry policy, artifact type, machine, deployment role, ownership rule, and migration safety invariant. It then supersedes the previous snapshot atomically. It does not start a service or job.

## Evidence

Workstation evidence:

```bash
python3 -m mission_hub evidence-capture --machine-id mission-hub
```

Target-host capture uses `--no-import` so it cannot create a second Mission Hub database. Transfer the portable `evidence/` archive to the workstation, then import exact snapshot hashes:

```bash
python3 -m mission_hub evidence-import \
  --archive-root /path/to/copied/evidence \
  --snapshot-sha256 HASH
```

Never delete or mutate a legacy source merely because it has been captured. Verify archive blobs and backups first.

## Editable training library

The canonical human-editable library is `/home/aomukai/Ninereeds/training_data` on the Mission Hub workstation. Add and organize future source material there. The directory is intentionally ignored by Git and excluded from both role releases; ignoring it does not delete, hide, freeze, or relocate it.

Do not train directly from the mutable library and do not synchronize the whole directory into the trainbox source checkout. `corpus.build` takes an explicit list of library-relative UTF-8 files, records every source hash in an immutable manifest, and produces a content-hashed JSONL artifact under the Mission Hub store. Only a registered corpus artifact named by a later job may be materialized into the trainbox cache.

## Legacy campaign

```bash
python3 -m mission_hub legacy-migrate-current-campaign
```

This command is idempotent. It imports campaign 33 as `legacy_stopped`, links the preserved campaign snapshot, records boundary 68 as stale legacy evidence, forbids resumption, and executes a durable freeze decision. It does not change legacy files.

## Candidate releases

Mission Hub candidate:

```bash
python3 -m mission_hub deployment-register-current \
  --role-id mission-hub-release \
  --machine-id mission-hub \
  --archive-output /safe/path/mission-hub.tar.gz
```

Trainbox candidates require a target-host environment-attestation JSON:

```bash
python3 -m mission_hub deployment-register-current \
  --role-id trainbox-agent-release \
  --machine-id trainbox \
  --environment-json @/safe/path/trainbox-attestation.json \
  --archive-output /safe/path/trainbox-agent.tar.gz
```

Dirty source can be registered only as a candidate. Do not use `--allow-dirty-active` for commissioning; it exists solely for explicit forensic recovery and defeats a restart gate.

## Safe job creation

The safe healthcheck and the two non-training artifact contracts can be created. `corpus.build` requires operator approval and runs locally on the Mission Hub. `checkpoint.certify` requires operator approval and remains unable to lease while the trainbox is in maintenance:

```bash
python3 -m mission_hub job-create \
  --type system.healthcheck \
  --machine-id trainbox \
  --idempotency-key operator-health-001 \
  --input '{"include_disk":true,"include_gpu":true,"include_release":true}'
```

Creating the same idempotency key with identical input returns the original job. Reusing it for different work is rejected.

Example bounded corpus request:

```bash
python3 -m mission_hub job-create \
  --type corpus.build \
  --machine-id mission-hub \
  --idempotency-key corpus-example-001 \
  --input '{"corpus_name":"example","source_paths":["kernel_identity/knowledge/no_weather.md"],"normalization":"utf8_lf","record_format":"ninereeds_document_v1"}'
python3 -m mission_hub job-approve JOB_ID
python3 -m mission_hub dispatch-once --machine-id mission-hub
```

Example checkpoint byte-certification request (still maintenance-blocked today):

```bash
python3 -m mission_hub job-create \
  --type checkpoint.certify \
  --machine-id trainbox \
  --idempotency-key checkpoint-certify-001 \
  --input '{"checkpoint_path":"/home/aomukai/Ninereeds/checkpoints/SELECTED.pt","lineage_label":"selected-lineage","format":"pytorch_checkpoint","parent_checkpoint_artifact_id":null}'
```

Certification proves byte identity only. It does not load pickle, certify architecture compatibility, or publish/protect a candidate.

## Critical failures and emergency Sol

Every job declares `critical`. Failed critical runs and expired critical leases create timestamped JSON incidents under `/home/aomukai/.local/share/ninereeds/mission-hub/critical-failures/YYYY-MM-DD/`; the operational files roll off after exactly seven days, while SQLite failure rows and hash-chained events remain permanent.

`[emergency].mode` is `disabled` in the stopped baseline. Setting it to `sol_advisory` is the only emergency enablement path. It invokes the configured `gpt-5.6-sol` command read-only with a strict response schema. Sol's assessment is appended to the incident log and has no transition, retry, approval, budget, campaign, or training authority. There is no hidden provider fallback.

## Service installation and initial commissioning

The Mission Hub API/daemon and dedicated trainbox forced command were installed and commissioned on 2026-08-06. See `commissioning_2026-08-06.md`. Reinstallation or replacement must still follow the release sequence below.

The complete sequence is:

1. merge/commit the canonical source;
2. build reproducible role archives;
3. attest each target environment;
4. register candidates and compare manifests;
5. install without enabling;
6. configure the restricted trainbox SSH key;
7. activate both deployments;
8. remove trainbox maintenance only for the healthcheck;
9. run one end-to-end healthcheck;
10. restore maintenance and review all events;
11. commission artifact transfer and one disposable non-model job;
12. commission a tiny disposable GPU job;
13. only then consider enabling `model.train` or `model.evaluate`.

Steps 1–12 are complete as of 2026-08-06. Step 13 remains prohibited until checkpoint/corpus certification, Lab configuration controls, and a separate operator authorization are complete.

## Test environments

The repository intentionally has two Python test environments. Mission Hub tests use the workstation's dependency-light system Python:

```bash
python3 -m pytest -q
```

Torch-dependent Cortex tests skip cleanly in that environment. The authoritative complete suite uses the isolated Cortex interpreter, which owns PyTorch and the training dependencies:

```bash
/home/aomukai/.venvs/ninereeds-cortex/bin/python -m pytest -q
```

Unsloth Studio is a separate environment at `/home/aomukai/.unsloth/studio/unsloth_studio`. Its installed PyTorch and Unsloth packages do not make those libraries part of Mission Hub's system Python. Do not install GPU dependencies into Mission Hub merely to eliminate an expected Cortex-test skip.

## Lab

The Lab is served by the Mission Hub API at `http://127.0.0.1:8770/`. On the first local visit it presents a one-time account setup screen. Complete that setup before publishing the listener through Tailscale Serve. Subsequent requests use an HttpOnly, SameSite session cookie; browser writes also require the per-session CSRF token.

The dashboard, operational threads, unread counts, campaign objective, configuration workspace, and Ninereeds chat records are all backed by the Mission Hub SQLite ledger. There is no separate Lab state directory or browser-visible Mission Hub bearer token.

Settings are saved as complete drafts against the displayed active configuration hash. A draft is review material only. It does not rewrite TOML, activate a snapshot, restart a service, authorize inference, or alter either machine's accepted deployment identity.

**Review draft** computes the full active-to-draft diff and separates semantic blockers from warnings caused by deliberately closed safety gates. **Request commissioning** requires an explicit acknowledgement and records an operational thread plus a hash-chained event. It does not activate the draft. The recorded request must still be reconciled into strict configuration source, validated, committed, built into clean role releases, installed with matching machine identities, and explicitly activated. Training authorization remains a later decision.

Ninereeds chats can be opened only against registered byte-certified checkpoint artifacts. A thread cannot change checkpoints. Until `model.chat_turn` inference is separately commissioned, recording a turn persists a `blocked` invocation with the exact checkpoint and settings rather than fabricating a response.

For private remote access, expose the existing loopback service with Tailscale **Serve**, not Funnel. The application remains usable on localhost or the LAN if the Tailscale control path is unavailable.

Maintenance mode is configuration-owned. Temporarily removing it therefore requires an explicit, committed configuration snapshot and matching role releases. Restoring it requires reactivating the stopped configuration and its matching releases; do not patch the database or deployed files in place.

## Artifact operations

Artifact ingest copies selected bytes from an allowed Mission Hub source root into its immutable content-addressed store and registers the resulting hash:

```bash
python3 -m mission_hub artifact-ingest \
  --kind commissioning_input \
  --path /allowed/source/file \
  --lifecycle observed \
  --manifest '{"purpose":"artifact-path-commissioning"}'
```

Materialization streams a registered Mission Hub artifact through restricted SSH and records its verified trainbox cache location:

```bash
python3 -m mission_hub artifact-materialize ARTIFACT_ID --machine-id trainbox
```

Retrieval streams a trainbox-produced artifact back into the Mission Hub content-addressed store and records the local location:

```bash
python3 -m mission_hub artifact-retrieve ARTIFACT_ID --machine-id trainbox
```

All three operations require the loaded configuration to be active. Transfer limits, chunk size, timeout, source/destination roots, deployment identity, and commissioning handler limits come from the activated configuration. The authenticated API exposes equivalent operations for the future Lab; it does not accept raw artifact bytes or arbitrary destination paths.

## Prohibited before training authorization

- leaving live execution enabled outside an explicit bounded commissioning or training-authorization snapshot;
- activating a dirty deployment;
- importing a legacy receipt as queued work;
- copying the Mission Hub database to the trainbox;
- pointing the new agent at the old trainbox ledger;
- using generic SSH as the normal job transport;
- enabling Lab/Hermes control actions;
- treating metadata-only checkpoint hashes as content certification;
- deleting legacy source, state, checkpoints, or corpora.
