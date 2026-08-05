# Artifact and GPU execution-path commissioning — 2026-08-06

## Result

The content-addressed artifact path and bounded non-model GPU path are commissioned. Final stopped readiness is expected to report:

- `backend_ready=true`;
- `commissioning_ready=true`;
- `execution_paths_ready=true`;
- `training_restart_ready=false`.

Maintenance is restored, `live_execution=false`, both disposable commissioning jobs are disabled, and `model.train` and `model.evaluate` were never enabled.

## Backend added

Artifact bytes now have an explicit lifecycle:

1. Mission Hub ingests an allowed source file into its immutable content-addressed store.
2. Mission Hub registers the artifact ID, kind, hash, byte size, manifest, lifecycle, and local location.
3. Restricted SSH `artifact-put` streams the exact bytes to a trainbox path derived from the hash.
4. The trainbox enforces active config/deployment identity, byte limit, declared size, SHA-256, allowed roots, and atomic mode-`0440` placement.
5. Mission Hub records the remote location only after an exact receipt.
6. A job is lease-eligible only after its referenced artifacts have verified locations on the target machine.
7. Restricted SSH `artifact-get` streams a produced artifact back to a temporary Mission Hub object.
8. Mission Hub verifies and atomically commits the returned bytes before recording its local location.

No operator `scp`, trainbox ledger, filename inference, or arbitrary destination path participates in this flow. CLI and authenticated API operations expose the same backend for the future Lab.

Configuration now owns transfer maximum, chunk size, per-machine timeout, commissioning input size, GPU count, matrix size, iteration count, duration, allocation, and starting-temperature bounds.

## Artifact-path evidence

Input artifact:

- ID: `art-a3994e75d8f2449b`
- Kind: `commissioning_input`
- SHA-256: `92b4870331ed8a4e38751bf3d55d1d064617f0c9a836a707df09a9d988156c5e`
- Bytes: `275`
- Trainbox cache mode: `0440`

The first v1 attempt failed safely:

- Job: `job-71970860-2dbd-4a19-ba01-55ff3cdb7e9c`
- Run: `run-04085dc6-bd71-4225-8471-0bc7fa368255`
- Result: `failed`
- Cause: the output schema used `$defs`, which the deliberately small validator did not support.

No output was accepted, no retry occurred, and services were stopped. The correction made configuration loading validate every referenced schema recursively, added explicit `minItems`/`maximum` support, removed `$defs`, bumped both commissioning job contracts to version 2, and deployed new immutable releases.

Successful v2 roundtrip:

- Job: `job-95e478c4-a5dd-4fe3-90ad-f8dc07444262`
- Run: `run-65196f1f-17f9-4289-86ea-5bb88a2c4fe9`
- Config: `cfg-cf452e8366330985`
- Trainbox deployment: `dep-5395f4d67cc7c3fd`
- Attempt: `1`
- Result: `succeeded`
- Receipt artifact: `art-5e8f10d7d86f532d`
- Receipt SHA-256: `b114f5d2cd6e022c5adb1493b1b21c4b11012deae1710eace1a7210651295269`
- Receipt bytes: `407`

The receipt was retrieved through `artifact-get`, rehashed locally, and confirmed the exact input ID, kind, SHA-256, and 275-byte size.

## Bounded GPU evidence

- Job: `job-d209dc79-34e0-4c13-be8e-1db9b61190bb`
- Run: `run-1df159aa-1e70-4230-9925-85e4c9c3fcb9`
- Config: `cfg-cf452e8366330985`
- Trainbox deployment: `dep-5395f4d67cc7c3fd`
- Attempt: `1`
- Result: `succeeded`
- Report artifact: `art-26bf99986a03f72d`
- Report SHA-256: `a8383d80d98590d9c418781108441d54738c329b0d21fff4dc1c24f474e32d3f`
- Report bytes: `1290`

Explicit job input:

- devices: `[0, 1]`, executed sequentially;
- matrix: `512 × 512`, float32;
- iterations: `3` per device;
- wall bound: `15` seconds;
- seed: `20260806`.

Observed result:

- total elapsed: `0.3656` seconds;
- GPU 0: RTX 3060, `12,713,984` peak allocated bytes, start temperature `57°C`;
- GPU 1: RTX 3060, `12,713,984` peak allocated bytes, start temperature `39°C`;
- configured allocation cap: `67,108,864` bytes;
- model loaded: `false`.

The report was retrieved through the restricted artifact path and its local bytes matched the registered hash. No checkpoint, corpus, optimizer, model, external provider, or training entry point was loaded.

## Remaining work before training

The next backend/data work is checkpoint content certification and immutable corpus construction/registration. Before training authorization, the future Lab must expose the versioned configuration, bounds, artifact selection, approval, maintenance, and readiness controls transparently. Training remains deliberately out of scope until those controls and a separate authorization snapshot exist.
