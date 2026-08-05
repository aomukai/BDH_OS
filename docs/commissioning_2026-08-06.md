# Mission Hub commissioning record — 2026-08-06

## Result

The Mission Hub control plane and restricted trainbox execution boundary are commissioned. One bounded `system.healthcheck` completed end to end, maintenance mode was restored afterward, and training remains unauthorized.

Final readiness semantics are:

- `backend_ready=true`;
- `commissioning_ready=true`;
- `training_restart_ready=false`.

The last value is intentional. The trainbox is back in maintenance, checkpoint contents are not yet certified, live execution is false, and `model.train` and `model.evaluate` remain disabled.

## Commissioned boundary

- Mission Hub API and daemon are installed as enabled user services on the workstation.
- The API listens only on `127.0.0.1:8770`; its bearer token is stored with mode `0600` in `~/.config/ninereeds/mission-hub.env` and is not recorded here.
- The trainbox release is invoked through the dedicated `ninereeds-trainbox-agent` SSH identity and a forced command at `~/.local/bin/ninereeds-trainbox-agent`.
- The forced command pins the machine ID, configuration directory, deployment manifest, interpreter, and current verified release.
- The two legacy Ninereeds status/control SSH identities and authorized-key routes were retired after the new boundary passed `ping`. Their prior material is preserved in the physical-cleanup archive.
- The unrestricted trainbox SSH identity remains only for operator administration; Mission Hub transport does not use it.
- Hermes is unrelated and was not changed.

## Commissioning window

Maintenance mode is configuration-owned. The window was therefore represented by committed source and an immutable configuration snapshot rather than a database edit:

1. stopped configuration active;
2. clean role releases installed and verified;
3. Mission Hub services installed and locally checked;
4. services stopped;
5. commissioning configuration committed with trainbox maintenance off;
6. matching configuration and role deployments activated;
7. services restarted;
8. exactly one healthcheck created;
9. healthcheck allowed to reach a terminal state through the daemon;
10. services stopped;
11. maintenance restored in source configuration;
12. matching stopped configuration and role releases activated;
13. services restarted and audited.

No other job was queued before the window opened. Schedules and every non-healthcheck job definition remained disabled throughout.

## Healthcheck evidence

- Job: `job-eba6d323-49fa-437a-8276-e3aee138f78e`
- Run: `run-e88875b3-32e8-40fe-a814-fd032c2edbb7`
- Commissioning configuration: `cfg-dd0966ba6c36a734`
- Trainbox deployment: `dep-c96cb8add289c614`
- Attempt: `1`
- Result: `succeeded`
- Started: `2026-08-05T17:04:07.942856Z`
- Finished: `2026-08-05T17:04:08.393846Z`

The returned and schema-validated observation reported:

- hostname `ninereeds`;
- the expected `cortex`, `cuda`, `gpu_12gb_x2`, and `local_executor` capabilities;
- two NVIDIA GeForce RTX 3060 GPUs, each with 12,288 MiB total memory and 1 MiB used;
- GPU utilization of zero percent during the observation;
- approximately 211 GB free in the observed trainbox state filesystem;
- the exact active release, source, environment, and deployment identities;
- no output artifacts and no failure.

The authoritative database contains the complete `job.created`, `run.leased`, `run.started`, `run.succeeded`, and `machine.observed` event sequence. The full result envelope remains in the run record.

## Remaining boundary before training

Commissioning proves control transport and a safe deterministic handler. It does not authorize training. Before training can be considered, the operator runbook still requires:

1. content certification and registration of the selected checkpoint lineage;
2. immutable corpus selection/build and artifact registration;
3. one disposable non-model job through the artifact-transfer path;
4. one tiny disposable GPU job with explicit bounds;
5. review of all evidence and resource use;
6. a separate committed authorization that removes maintenance, enables live execution, and enables only the intended train/evaluate definitions.
