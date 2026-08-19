# Campaign 33 training-readiness record — 2026-08-06

## Outcome

Campaign 33 branch 3 is training-ready through Mission Hub. `readiness` reports `backend_ready`, `commissioning_ready`, `execution_paths_ready`, and `training_restart_ready` as `true`. The global pipeline remains paused, has zero live runs, and has no queued training job. Branch 4 is not authorized.

## Bound purpose

- Campaign: `campaign-33-play-recovery-recommissioned-v1`
- Mode: `evolutionary`
- Developmental stage: `foundational bootstrap: early encoder and expression coordination`
- Purpose: observe regression, recovery, and protected-material placement; immediate loss or parent improvement is not a success criterion.
- Evaluation: behavioral chat and MRI activation after every training session; loss is telemetry only.
- Pacing: 15 minutes after each train or evaluation boundary.
- Order: declared order only, no shuffle, with every unresolved dependency before its compound concept.
- Promotion and automatic branch ranking: forbidden.

Branch 3 uses the protected-last corpus variant. Branch 4 uses protected-first, is registered for later comparison, and must not be authorized before branch 3 completes.

## Exact commissioned identities

- Active configuration: `cfg-2b5b861f1a3eb2b3`
- Compatibility-tested Mission Hub deployment: `dep-c46d7dc0e0ff20a7` / `release-01663d8df8cb-ad421ccb1803`
- Compatibility-tested trainbox deployment: `dep-cdf07bbbad0c5d31` / `release-5eea522f0f24-594a0e9342e8`
- Baseline artifact: `art-7fbe08028b3f2430`
- Baseline SHA-256: `76c1ba33c935a61557caf39a4886669f4833458671d4e909dc40adb96b2b81a9`
- Baseline bytes: `7,265,464,584`
- Compatibility report: `art-15e3363ab851ac50`
- Evaluation suite: `art-941de2e6a0583002`
- Branch 3 workflow: `cortex-84bb04d2-48ca-48b5-a8a6-66d1cbd169c4`

The two compatibility-tested deployments were retired only by later clean releases containing the same runtime plus this documentation. Active deployment IDs are deliberately not embedded in a source-controlled document, because committing such an ID changes the source identity and therefore creates the next release. Query them with `python3 -m mission_hub list deployments`; readiness independently requires both active releases to match the current source and configuration hashes.

The baseline knowledge snapshot contains the preserved first 500 ranked concepts. Branch 3 contains twelve immutable 500-row corpus artifacts. All twelve passed byte, row-count, exact concept-sequence, dependency-order, no-shuffle, lesson-policy, and identity-policy validation on the trainbox.

## Commissioning leak found and repaired

The first checkpoint compatibility probe failed before mutation because a resolved Python symlink bypassed the Cortex virtual environment and allowed Unsloth's Transformers 4.57.6 to shadow the required Cortex Transformers 5.2.0. The critical job produced the required timestamped incident record:

`critical-failures/2026-08-06/20260806T130841.499535Z--run-b730b791-6b33-40b2-9f08-18984249a028.json`

All Cortex train, probe, and evaluation subprocesses now preserve the declared Cortex venv and enter through `meta/scripts/cortex_runtime.py`, which adds the commissioned Unsloth Torch site after interpreter startup. The repeated read-only probe succeeded, loaded the exact checkpoint locally, retained a frozen 229,693,184-parameter encoder, found 1,210,068,480 trainable parameters, and split twelve core layers evenly across GPUs 0 and 1.

The full declared Cortex environment test suite passed: `113 passed`.

## Start boundary

The next authorized state change is the operator's Start action in Lab. At the daemon's next safe boundary, the Cortex coordinator may create branch 3 block 1's training job. It cannot skip corpus validation, bypass operator approval, shuffle examples, train a later dependency first, omit chat or MRI evaluation, promote a checkpoint, rank branches automatically, or authorize branch 4.
