# Corpus, checkpoint, and critical-failure contract commissioning — 2026-08-06

## Result

The immutable corpus build contract and critical-job failure-log path are commissioned. The checkpoint byte-certification contract is implemented, packaged, and unit-tested without deserialization, but no production checkpoint lineage was selected or hashed. The trainbox remains in maintenance and training remains unauthorized.

Readiness after commissioning reports:

- `backend_ready=true`;
- `commissioning_ready=true`;
- `execution_paths_ready=true`;
- `training_restart_ready=false`.

The remaining failed training gates are trainbox maintenance, checkpoint content certification, disabled live execution, and disabled train/evaluate jobs.

## Contract ownership

The earlier placeholder assigned `corpus.build` to the trainbox. That contradicted the reconciled ownership model: the editable `training_data/` library is Mission Hub-only and must not be copied wholesale to the training environment. The version-2 job now executes locally on the Mission Hub and accepts only a unique list of clean paths relative to the configured library root.

For every selected UTF-8 file, the handler records path, byte size, and SHA-256; normalizes line endings; and emits one `ninereeds_document_v1` JSONL record. It produces exactly one candidate `corpus` and one candidate `corpus_manifest`, both content-addressed. The authoritative store rejects a successful result unless every job-declared required artifact type occurs exactly once.

`checkpoint.certify` executes where checkpoint bytes live. It accepts one explicit file under one of two configured trainbox checkpoint roots, enforces a byte bound, hashes the content, and emits exactly one checkpoint candidate plus one immutable certification manifest. It never calls `torch.load` or otherwise deserializes pickle. Its manifest states `certification_scope=byte_identity_only`, `deserialized=false`, and `compatibility_certified=false`; compatibility remains a separate probe gate.

## Corpus evidence

The bounded commissioning input was the existing 67-byte library document `kernel_identity/knowledge/no_weather.md`. The source file was read but not changed.

- Job: `job-fcc73bfe-cdeb-4676-b95e-27de05c15486`
- Run: `run-eda0e618-e46a-4866-a740-43314a8edd4c`
- Config: `cfg-86ab79982d0e9757`
- Mission Hub deployment: `dep-803c47437218c817`
- Result: `succeeded`
- Corpus artifact: `art-f18bfc6cf32f9126`
- Corpus SHA-256: `88562829b7538d0f911cfea8f94aadb70851d3151e1adb13f026cd587940af99`
- Corpus bytes: `333`
- Manifest artifact: `art-b9cf4fc8e10b35f4`
- Manifest SHA-256: `ae3be50b644988a64c8f56fc0f8c9702aacdd1dd55df2873fb3541e453bd5146`
- Manifest bytes: `658`

No material was copied to the trainbox, and no GPU, checkpoint, model, optimizer, provider, or training entry point was loaded.

## Critical-failure evidence

Every job definition now declares `critical`. A failed run or expired lease for a critical job produces a timestamped JSON incident under the configured Mission Hub root. Only those operational incident files have automatic retention, fixed at seven days. SQLite lifecycle records and hash-chained events remain permanent.

The first intentionally missing-source request exposed that `dispatch-once` did not share the daemon's terminal failure handling. It left run `run-3266d4cb-19b6-484e-9082-3b37201c8ff0` running after the handler refusal. The run was explicitly cancelled with a reason and preserved. Execution and terminal failure classification were then consolidated into one `MissionHubService.execute_and_record` boundary used by both daemon and CLI, and a regression test was added.

The repeated bounded failure commissioned the corrected path:

- Job: `job-51991233-be58-4925-b346-e40714e70788`
- Run: `run-f9518cb0-a7ef-4eb4-811c-93264dac30a0`
- Mission Hub deployment: `dep-287bbb8e5aeaba7e`
- Result: `failed`
- Failure class/code: `safety_policy` / `safety_policy_refused`
- Log mode: `0600`
- Emergency field: `{"invoked":false,"mode":"disabled"}`

The job did not retry and produced no artifacts.

## Emergency Sol authority

The legacy emergency subsystem was not restored. It could directly change campaigns and used a second provider fallback outside the new routing authority. The new emergency mode has only `disabled` and `sol_advisory` states, one exact configured executable/model, a read-only sandbox, a strict response schema, an incident-size bound, and a timeout.

When `sol_advisory` is explicitly activated, a critical failure asks `gpt-5.6-sol` for an assessment, likely cause, bounded operator actions, and a retry-safety opinion. The response is appended to the incident log. Sol has no code path to retry work, change lifecycle state, mutate files, wake campaigns, expand budgets, approve training, or use another provider. The stopped baseline keeps the mode disabled. The invocation path, schema rejection, read-only command, and advisory persistence were commissioned with a mocked process; no external call was made during this work.

## Verification

- strict configuration validation: passed, 33 documents and 14 jobs;
- Mission Hub test suite: 34 passed;
- Mission Hub release verification: passed;
- trainbox release verification: passed, 93 files;
- restricted trainbox agent `ping`: passed;
- SQLite integrity: `ok`;
- foreign-key errors: none;
- event chain: valid, 115 events at the contract-path audit (final release registration appends deployment events);
- Mission Hub API and daemon: active;
- trainbox maintenance: enabled;
- live execution: disabled;
- schedules and external calls: disabled;
- `model.train` and `model.evaluate`: disabled.
