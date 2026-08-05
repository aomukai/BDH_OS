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

`readiness` separates the safe backend foundation from commissioning and training-restart gates. A healthy stopped rebuild should report `backend_ready=true`, `commissioning_ready=false`, and `training_restart_ready=false` until clean releases and explicit commissioning occur.

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

Do not train directly from the mutable library and do not synchronize the whole directory into the trainbox source checkout. A future `corpus.build` operation must select inputs, record a library snapshot/manifest, produce immutable content-hashed shards under the Mission Hub artifact store, and materialize only the shards named by a job into `/home/aomukai/.local/share/ninereeds/trainbox-agent/artifacts` on the trainbox.

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

At present only a healthcheck can be created, and trainbox maintenance mode prevents leasing it:

```bash
python3 -m mission_hub job-create \
  --type system.healthcheck \
  --machine-id trainbox \
  --idempotency-key operator-health-001 \
  --input '{"include_disk":true,"include_gpu":true,"include_release":true}'
```

Creating the same idempotency key with identical input returns the original job. Reusing it for different work is rejected.

## Service installation — not authorized yet

Do not install or enable `mission_hub/systemd` units until a clean Mission Hub release is active. Do not install the trainbox forced command until a clean target release and its deployment manifest are in place.

The future sequence is:

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

## Prohibited before commissioning

- enabling live execution, external calls, schedules, rollover, or pruning;
- activating a dirty deployment;
- importing a legacy receipt as queued work;
- copying the Mission Hub database to the trainbox;
- pointing the new agent at the old trainbox ledger;
- using generic SSH as the normal job transport;
- enabling Lab/Hermes control actions;
- treating metadata-only checkpoint hashes as content certification;
- deleting legacy source, state, checkpoints, or corpora.
