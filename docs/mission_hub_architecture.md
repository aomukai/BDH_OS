# Mission Hub backend architecture

**Status:** backend foundation implemented; pipeline remains stopped

**Authority:** Mission Hub on the workstation

**Presentation:** the authenticated Lab is served by Mission Hub

## Non-negotiable invariants

1. Mission Hub is the only authority for configuration activation, campaigns, decisions, jobs, attempts, leases, events, artifact metadata, approvals, schedules, and deployment status.
2. The trainbox does not maintain a competing job ledger. It receives one leased envelope, executes an allowlisted handler, and returns one result envelope.
3. A job references one immutable configuration snapshot and one registered deployment. The trainbox rejects mismatched configuration, source, environment, machine, role, input hash, or artifact references.
4. Source, configuration, the editable training library, immutable training shards, runtime state, artifact metadata, artifact bytes, evidence, and secrets are separate data classes with explicit owners.
5. No handler searches for a globally “latest” file. Inputs are artifact IDs resolved to content hashes and machine-local locations by Mission Hub.
6. Deterministic data work is a deterministic job. LLM jobs are reserved for bounded generation or proposed decisions.
7. Destructive retention, external calls, live model execution, campaign rollover, and Git mutation fail closed.
8. The stopped legacy pipeline is evidence. Nothing imports legacy `running` state as schedulable work.

## Components

### Mission Hub store

SQLite in WAL mode owns the durable model:

- activated configuration snapshots and job definitions;
- machines and content-addressed deployments;
- campaigns and separately approved decisions;
- jobs, attempts, leases, heartbeats, cancellations, failures, and retry availability;
- artifacts, locations, lineage manifests, and lifecycle state;
- evidence sources and lossless legacy JSON records;
- immutable, hash-chained events;
- schedule slots.

Foreign keys, lifecycle checks, unique idempotency keys, one-active-config, and one-active-deployment-per-machine constraints are enforced in the database. The event chain and SQLite integrity are independently verifiable.

### Mission Hub daemon

The daemon reads the activated configuration, then performs only four central operations:

1. expire abandoned leases;
2. materialize enabled schedule slots idempotently;
3. lease eligible jobs to active matching deployments;
4. dispatch one bounded envelope through either the local Mission Hub executor or the restricted SSH transport, according to machine configuration.

Transport failures become classified run evidence and can retry only when the selected retry policy permits it. A deterministic specification failure is never retried.

Every job definition declares whether it is critical. A failure or expired lease for a critical job writes a timestamped, mode-0600 JSON incident under the configured Mission Hub failure-log root. Only that root is automatically pruned, with a fixed rolling seven-day window; database rows and hash-chained events remain permanent. Optional `sol_advisory` emergency mode invokes the exact configured Sol model through a read-only, schema-bound process. Sol can diagnose and recommend operator actions, but cannot retry jobs, mutate state, wake campaigns, change budgets, approve training, or fall back to another provider.

### Trainbox agent

The agent is stateless with respect to authoritative lifecycle. It validates:

- protocol and envelope hash;
- target machine and role;
- deployment ID, release ID, source hash, and environment hash;
- activated configuration hash;
- enabled and allowed job type;
- machine capabilities;
- job input hash and schema;
- artifact IDs, content hashes, sizes, manifests, and local URI;
- live-execution and maintenance gates.

The restricted SSH wrapper accepts only `ping` or `execute`. No arbitrary shell command is part of the protocol.

### API and Lab

The loopback API is the integration boundary for the Lab. The browser never receives the internal bearer token. Mission Hub serves the static presentation and a separate cookie-authenticated Lab API from the same loopback listener. Passwords use salted scrypt hashes; server-side sessions are stored by token hash; state-changing requests require same-origin validation and a per-session CSRF token.

The Lab presents live status, current and last work, machine state, campaign objective, registered evidence, operational message threads, configuration drafts, and checkpoint-pinned Ninereeds conversations. Operational threads and model chats use separate tables and semantics. Incoming Mission Hub, Codex, or Sol messages remain unread until their thread is opened. A critical incident also creates an unread operational notice after its required seven-day log has been committed.

Configuration edits are complete drafts rooted in one active configuration hash. Saving a draft never mutates deployed TOML or activates a snapshot. The Lab review contract reports every changed value, semantic blockers, closed safety gates, and the required commissioning sequence. An acknowledged commissioning request creates a durable operational thread and hash-chained event but still performs no activation. Activation remains an explicit source-reconciliation, clean-release, deployment, and configuration operation because it changes the identity accepted by both machines.

The Lab treats headless Codex as its own provider kind. It uses the workstation's existing ChatGPT-authenticated Codex CLI and discovers the current account-scoped selectable model catalog through Codex itself; it does not copy account credentials into the browser or reinterpret Codex login as a generic OpenAI API key. Only safe display metadata reaches the browser. Choosing a newly discovered model adds its exact Codex slug to the inert configuration draft. Provider activation and a bounded job executor remain separate commissioning work.

Chat records pin checkpoint artifact ID and SHA-256, prompt-format identity, generation settings, context message IDs, rendered prompt fields, outputs, and timestamps. Until the bounded trainbox inference job is commissioned, turns create truthful `blocked` invocation records that can later be replayed; the Lab never pretends an output was generated.

The API refuses startup without its configured bearer-token environment variable. It binds to `127.0.0.1` by default, returns `Cache-Control: no-store`, and applies a restrictive browser content-security policy. Tailscale Serve may publish this loopback listener privately; Tailscale is transport, not an application dependency.

## Job catalog

| Job type | Executor | Initial state | Purpose |
|---|---|---|---|
| `system.healthcheck` | trainbox | enabled, safe | Read-only deployment, disk, GPU, and capability observation |
| `system.artifact_roundtrip` | trainbox | disabled | Bounded artifact-path and hash commissioning receipt |
| `system.gpu_probe` | trainbox | disabled | Bounded CUDA arithmetic commissioning probe without model loading |
| `corpus.build` | Mission Hub | enabled, operator approval | Deterministic immutable corpus construction from explicit library-relative files |
| `corpus.transform` | trainbox | disabled | Deterministic filter/mix/deduplicate/convert |
| `corpus.validate` | trainbox | disabled | Contract and content validation |
| `model.train` | trainbox | disabled | One immutable Cortex training specification |
| `model.evaluate` | trainbox | disabled | One explicit candidate/parent/suite evaluation |
| `checkpoint.probe` | trainbox | disabled | Non-mutating checkpoint probe |
| `checkpoint.certify` | trainbox | enabled, operator approval; maintenance-blocked | SHA-256 byte certification and lineage manifest without checkpoint deserialization |
| `checkpoint.publish` | Mission Hub | disabled | Explicit publication decision and manifest |
| `executor.generate` | trainbox | disabled | Bounded structured material generation through one route |
| `campaign.decide` | Mission Hub | disabled | Evidence-linked decision proposal, never implicit activation |
| `maintenance.retention_preview` | Mission Hub | disabled | Report-only retention proposal |

The old `phase_block`, `cortex_block`, `cortex_corpus_chunk`, `cortex_evaluation`, `executor_job`, `trainer_session`, `micro_update`, and `status_refresh` kinds are not accepted by the new registry. Their records remain in the evidence archive.

## Configuration model

All operational policy lives under `config/mission_hub` as strict TOML documents. Unknown and missing keys fail validation. Activation creates a complete resolved snapshot with a bundle hash and per-document hashes.

Configuration covers:

- global safety, database, API, protocol, scheduler, artifact-transfer, and commissioning safety settings;
- machine roles, maintenance, concurrency, capabilities, paths, and transport;
- exact role-specific release contents and Python environments;
- job schemas, handlers, ownership, criticality, timeouts, attempts, approvals, capabilities, allowed/required artifacts, routes, and prompts;
- providers, exact models, and explicit ordered routes;
- retry policies and failure-code taxonomy;
- schedules, budgets, retention, artifact types, and ownership;
- critical-failure log location/retention and bounded advisory Sol emergency mode;
- legacy evidence sources and migration policy.

Secrets are referenced only by environment-variable name. Values are neither checked into TOML nor included in configuration/evidence snapshots.

## Artifact transaction

Mission Hub ingests selected operator-owned files into its content-addressed store after checking configured source roots, byte limits, and SHA-256. Materialization streams exact bytes through the same forced-command SSH identity used for jobs. The trainbox derives the destination from the content hash, refuses stale configuration/deployment identities, enforces size limits, writes atomically, and returns a machine-local URI. Mission Hub records that location only after the receipt matches the request.

Mission Hub resolves job artifact fields before leasing. A job is not eligible on a machine until each artifact has a verified available location there. The envelope carries the exact ID, kind, SHA-256, size, lifecycle, manifest, and URI. The agent verifies file content before a handler can run.

Successful result acceptance validates all output artifact declarations and commits the terminal run, job state, artifact metadata, locations, and events in one transaction. Job outputs may initially register only `observed` or `candidate` artifacts. Publication, protection, rejection, and deletion require separate decisions.

Retrieval is also explicit. Mission Hub requests one artifact ID, hash, size, deployment, and validated trainbox URI through the restricted boundary, streams the bytes into a temporary local object, verifies them, atomically commits the content-addressed object, and then records the Mission Hub location. Operator `scp` is not part of the job artifact path.

## Retry semantics

Failure codes declare a class and whether retry is ever valid. A job’s retry policy further limits allowed classes, attempts, repair attempts, backoff, and escalation. Both must permit retry.

- transient transport/resource failures may retry;
- bounded model-output repair is separate from execution retry;
- invalid job specifications, unmet evaluation thresholds, safety refusals, and operator cancellation do not retry;
- queue-age expiry blocks a job instead of silently running stale work.

## Machine separation

The Mission Hub release contains the store, API, scheduler, dispatcher, evidence/migration tooling, configuration, and schemas.

The trainbox release contains only the stateless agent boundary, safe handlers, shared contracts, Cortex model code, optimizer, and exact training/evaluation/probe entry points. It explicitly excludes:

- Mission Hub database/API/scheduler/migration code;
- Lab and Hermes;
- documentation and historical campaign scripts;
- repository archives, `training_data`, checkpoints, and runtime state;
- legacy auto-evolution and automatic-retention policy files;
- prepared legacy allowlist campaign blocks.

The canonical editable training library stays at `/home/aomukai/Ninereeds/training_data` on the Mission Hub. It is operator-owned data, not a source release and not an immutable corpus artifact. Mission Hub catalogs it and builds explicitly selected material into immutable, content-hashed shards. Only those job-referenced shards are materialized in the trainbox artifact cache. The old trainbox `training_data` copy is non-authoritative legacy evidence.

`corpus.build` accepts only a sorted, unique list of paths relative to that library root. It normalizes UTF-8 line endings, emits one versioned JSONL document per source, hashes every source, and produces both a corpus object and a full immutable source manifest. No directory scan or implicit “all files” behavior exists.

Checkpoint bytes and immutable training shards are mounted/materialized as artifacts, never bundled as source. `checkpoint.certify` hashes one explicit file under the configured checkpoint roots and emits a content-addressed manifest. It never deserializes the checkpoint; compatibility, architecture, and behavioral fitness remain separate probe/evaluation gates.

## Activation state

The Mission Hub services, restricted trainbox agent, artifact path, and bounded GPU probe were commissioned on 2026-08-06. The trainbox is back in maintenance, and training remains disabled. Corpus construction and checkpoint byte-certification contracts now exist; their selected production artifacts, compatibility probe, Lab controls, and explicit training authorization remain later gates.
