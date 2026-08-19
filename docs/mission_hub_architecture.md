# Mission Hub backend architecture

**Status:** commissioned; query authoritative Mission Hub state for current campaign and pipeline control

**Authority:** Mission Hub on the workstation

**Presentation:** the authenticated Lab is served by Mission Hub

**Architecture evidence ledger:** `docs/ninereeds_architecture_knowledge.md`

## Non-negotiable invariants

1. The `strategic-decision` and `on-call` roles are the project's principal decision tier and speak with the operator's standing authority. Every coordinator, reviewer, gate, scheduler, and worker is subordinate: it executes their directives when technically possible, preserves the evidence and audit trail, and may escalate only a genuinely external or physical impossibility. Machine review is evidence that these roles may accept, reject, recommission, or explicitly override.
2. Mission Hub is the only durable ledger and execution authority for configuration activation, campaigns, decisions, jobs, attempts, leases, events, artifact metadata, approvals, schedules, and deployment status. Its state machine records and carries out principal-tier decisions; it is not a competing decision-maker.
3. The trainbox does not maintain a competing job ledger. It receives one leased envelope, executes an allowlisted handler, and returns one result envelope.
4. A job references one immutable release configuration, one immutable runtime-settings snapshot, and one registered deployment. The trainbox rejects mismatched configuration, source, environment, machine, role, settings hash, input hash, or artifact references.
5. Source, configuration, the editable training library, immutable training shards, runtime state, artifact metadata, artifact bytes, evidence, and secrets are separate data classes with explicit owners.
6. No handler searches for a globally “latest” file. Inputs are artifact IDs resolved to content hashes and machine-local locations by Mission Hub.
7. Deterministic data work is a deterministic job. LLM jobs are reserved for bounded generation or decisions.
8. Destructive retention, external calls, live model execution, campaign rollover, and Git mutation fail closed unless the applicable principal-tier directive and executable contract explicitly authorize them.
9. The stopped legacy pipeline is evidence. Nothing imports legacy `running` state as schedulable work.

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
- schedule slots;
- paced visual-workflow state and its idempotent stage-to-job links;
- conservative external-provider budget reservations;
- durable material-workflow state and its ordered unit-to-job links;
- durable recovery incidents, bounded repair attempts, hashed action evidence,
  operational-thread links, and campaign blocks.

Foreign keys, lifecycle checks, unique idempotency keys, one-active-config, and one-active-deployment-per-machine constraints are enforced in the database. The event chain and SQLite integrity are independently verifiable.

### Mission Hub daemon

The daemon reads the activated configuration, then performs seven central operations:

1. expire abandoned leases;
2. materialize enabled schedule slots idempotently;
3. advance durable visual workflows by at most one immutable candidate-stage unit per wake, after its configured cooldown;
4. advance durable material-writing workflows by at most one stable unit per wake and assemble only after all units succeed;
5. advance one authorized Cortex workflow through train, cooldown, chat-and-MRI evaluation, and the next cooldown;
6. lease eligible jobs to active matching deployments;
7. dispatch one bounded envelope through either the local Mission Hub executor or the restricted SSH transport, according to machine configuration.

Visual workflow advancement never approves its own work. For new workflows it persists generation, inspection, caption, policy decision, and independent review as one job per immutable item/seed candidate. Stable `stage/NNNN` links are the restart cursor, so a process replacement repeats at most the leased unit rather than the entire pack. Caption, decision, and review receive only that candidate's commissioned item; deterministic packing is the fan-in. Legacy in-flight workflows retain their original graph so persisted work is not reinterpreted. Shadow mode still stops after review, and projector training requires a separately selected base checkpoint and explicit operator approval.

Material writing follows the same rule. A `material_workflow` stores ordered stable `unit_id` records and creates exactly one `executor.generate` job at `unit/NNNNNN`. A fresh process reads the linked jobs and continues at the first missing unit; successful units are never regenerated. Canonical unit input is limited to 64 KiB, nested repeated fields and generated repeated fields are capped by `max_output_items` (at most 16), and `corpus.assemble_generated` performs content-addressed deterministic fan-in. The Qwen route can therefore be enabled for many small calls without authorizing one long context-consuming generation.

New visual workflows also persist `encode/NNNN` per accepted image. `visual.features_finalize` verifies exact SHA-256 coverage and combines the feature shards in immutable pack order. Legacy workflows that already crossed the old frontier finish their preserved batch graph.

Transport failures become classified run evidence and can retry only when the selected retry policy permits it. A deterministic specification failure is never retried.

Every job definition declares whether it is critical. A failure or expired lease for a critical job writes a timestamped, mode-0600 JSON incident under the configured Mission Hub failure-log root. Only that root is automatically pruned, with a fixed rolling seven-day window; database rows and hash-chained events remain permanent. The same failure transaction creates a typed recovery incident and, for a terminal campaign job, an explicit campaign block. The operational thread is a projection linked to that incident; it is never recovery authority.

Atomic content jobs treat individual failure as experimental throughput. Their
failed runs remain durable, but provider, malformed-output, and other declared
retryable failures share one incident and stay out of the operational inbox
through a four-attempt budget. Candidate-level semantic rejection likewise
uses the next commissioned candidate silently. Sol and the operator are
notified only when the applicable atomic budget is exhausted, automatic
recovery cannot proceed, or a non-atomic invariant/safety boundary fails.

The unresolved-incident circuit breaker is global and durable. The first incident enters normal recovery. If a second incident is captured before the immediately preceding incident reaches `recovered`, the same transaction changes the pipeline's desired state to `paused`, records both incident identities in the event chain, and prevents any further ordinary lease. Already-live work may finish, and the new incident still queues its on-call response so Sol is explicitly told that the breaker stopped dispatch.

The on-call path is deliberately split. Sol inspects the notice and underlying evidence
with principal-tier authority and issues an exact action. Deterministic code executes it;
permission roots, immutable evidence, deployment identity, tests, retry identity, and
closure verification constrain execution but cannot downgrade the decision into a
proposal or abandon it. Autonomous attempt ceilings stop unattended repetition, not
principal authority: Sol may reopen a machine-repairable blocked or exhausted incident
as a new preserved attempt. A temporary failure while applying a valid action leaves
that exact action pending for a silent execution retry. Eligible bounded defects run in a detached worktree based on the
failed deployment's exact source identity. The repair driver may change only configured
source roots, refuses protected paths and oversized patches, runs configured targeted
and regression commands, creates a distinct release, installs/activates it through the
local or restricted-SSH release protocol, and retries the same immutable job input.
Configuration incidents use an atomic rollback to a retained, fully rehydratable
known-good snapshot and its role deployments instead of editing active state in place.

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

The restricted SSH wrapper accepts only exact protocol commands for ping, execution,
artifact transfer/deletion/inventory, and content-hashed release install/activation.
It never accepts an arbitrary shell command. Release extraction rejects absolute paths,
parent traversal, links, unexpected members, hash mismatches, and unmanaged active paths.
On failure, bounded JSON/log/text diagnostics from the exact remote run are bundled,
hashed, transferred over the authenticated response channel, and registered in Mission
Hub's content-addressed evidence store; a trainbox-local pathname is never the sole
recovery evidence.

### API and Lab

The loopback API is the integration boundary for the Lab. The browser never receives the internal bearer token. Mission Hub serves the static presentation and a separate cookie-authenticated Lab API from the same loopback listener. Passwords use salted scrypt hashes; server-side sessions are stored by token hash; state-changing requests require same-origin validation and a per-session CSRF token.

The Lab presents live status, current and last work, machine state, campaign objective, registered evidence, operational message threads, configuration drafts, checkpoint-pinned Ninereeds conversations, and a read-only Model Observatory. The Observatory derives MRI, Atlas, 3D representation maps, campaign timelines, knowledge counts, run attempts, and provider fallback rates from immutable Mission Hub evidence; its full contract is in `docs/model_observatory.md`. Operational threads and model chats use separate tables and semantics. Incoming Mission Hub, Codex, or Sol messages remain unread until their thread is opened. A critical incident also creates an unread operational notice after its required seven-day log has been committed.

Operator-facing settings are validated and saved as immutable runtime snapshots separate from release configuration. Save is authoritative: with no active step, the snapshot becomes active immediately and queued work is rebound to it. If a step is leased or running, the Lab requires an explicit choice. **Stop, apply, and resume** cancels the current attempt, activates the snapshot, requeues the same immutable job input, and resumes the pipeline from the beginning of that step. **Apply after this step** durably binds the snapshot to the exact current run and activates it as soon as that run becomes terminal, before workflow advancement can create or lease the next step. **Cancel** performs no write and restores the displayed active values. Validation failure leaves active and pending settings unchanged and is reported directly in the Settings view.

Runtime settings may change only the allowlisted job, route, provider, model, prompt, pacing, visual-limit, and budget fields exposed by the Lab. They do not change handlers, schemas, machine roles, release contents, source identity, safety locks, or deployment identity. Each job pins the runtime-settings snapshot it will execute, and the signed machine envelope carries the complete validated payload and hash. The trainbox revalidates the settings against its commissioned release before executing. Local visual-runtime jobs accept only models backed by that commissioned runtime; catalog text models cannot be saved onto those routes.

The Lab treats headless Codex as its own provider kind. It uses the workstation's existing ChatGPT-authenticated Codex CLI and discovers the current account-scoped selectable model catalog through Codex itself; it does not copy account credentials into the browser or reinterpret Codex login as a generic OpenAI API key. Only safe display metadata reaches the browser. Choosing a newly discovered model adds its exact Codex slug to the unsaved settings form; Save validates whether the selected job path can actually execute that provider before activating it.

Chat records pin checkpoint artifact ID and SHA-256, prompt-format identity, generation settings, context message IDs, rendered prompt fields, job/run, immutable output, and timestamps. The bounded `model.chat` job performs deterministic inference on the trainbox. It is the only job class that may dispatch while the campaign pipeline is paused, because it is operator-requested, read-only model use and cannot schedule campaign work. Prior messages are rendered again for every turn; Ninereeds has no external persistent conversation-memory mechanism. Every saved checkpoint remains selectable, with certification and compatibility displayed as evidence rather than used as a listing filter.

The API refuses startup without its configured bearer-token environment variable. It binds to `127.0.0.1` by default, returns `Cache-Control: no-store`, and applies a restrictive browser content-security policy. Tailscale Serve may publish this loopback listener privately; Tailscale is transport, not an application dependency.

## Job catalog

| Job type | Executor | Initial state | Purpose |
|---|---|---|---|
| `system.healthcheck` | trainbox | enabled, safe | Read-only deployment, disk, GPU, and capability observation |
| `system.artifact_roundtrip` | trainbox | disabled | Bounded artifact-path and hash commissioning receipt |
| `system.gpu_probe` | trainbox | disabled | Bounded CUDA arithmetic commissioning probe without model loading |
| `corpus.build` | Mission Hub | enabled, operator approval | Deterministic immutable corpus construction from explicit library-relative files |
| `corpus.assemble_generated` | Mission Hub | enabled | Deterministic ordered fan-in of one-unit generated material artifacts |
| `corpus.transform` | trainbox | disabled | Deterministic filter/mix/deduplicate/convert |
| `corpus.validate` | trainbox | enabled | Contract, dependency order, and identity-policy validation |
| `model.train` | trainbox | enabled, operator approval | One immutable, purpose-bound Cortex training session |
| `model.evaluate` | trainbox | enabled, operator approval | One purpose-aware candidate/parent/suite chat-and-MRI evaluation |
| `model.chat` | trainbox | enabled | One deterministic, checkpoint-pinned Lab conversation turn |
| `checkpoint.probe` | trainbox | enabled, operator approval | Non-mutating checkpoint compatibility probe |
| `checkpoint.compare` | trainbox | enabled, operator approval | Bitwise learned-state and optimizer-state comparison excluding run metadata |
| `checkpoint.certify` | trainbox | enabled, operator approval | SHA-256 byte certification and lineage manifest without checkpoint deserialization |
| `checkpoint.publish` | Mission Hub | disabled | Explicit publication decision and manifest |
| `executor.generate` | trainbox | disabled until the local Qwen route is commissioned | Exactly one bounded structured material unit; repeated production uses `material_workflows` |
| `campaign.decide` | Mission Hub | disabled | Evidence-linked decision proposal, never implicit activation |
| `maintenance.retention_preview` | Mission Hub | disabled | Report-only retention proposal |
| `visual.plan` | Mission Hub | disabled | Versioned educational scene and pack proposal |
| `visual.generate` | trainbox | disabled | Bounded pinned-FLUX candidate generation |
| `visual.inspect` | trainbox | disabled | Mechanical checks and blind pinned-Gemma observation |
| `visual.caption` | trainbox | disabled | Evidence-grounded caption proposals |
| `visual.decide` | Mission Hub | disabled | Text-evidence policy bucket without pixel authority |
| `visual.review` | Mission Hub | disabled | Required independent Sol pixel review and disposition |
| `visual.pack_finalize` | Mission Hub | disabled | Immutable pack admission after complete usable reviews |
| `visual.encode` | trainbox | enabled | Pinned SigLIP2 feature derivation for one accepted candidate in new workflows |
| `visual.features_finalize` | trainbox | enabled | Deterministic exact-coverage fan-in of one-candidate feature shards |
| `visual.experience_compile` | Mission Hub | disabled | Ordered image/text learner-event compilation |
| `model.visual_train` | trainbox | disabled | Explicit projector or authorized Cortex visual update |

The old `phase_block`, `cortex_block`, `cortex_corpus_chunk`, `cortex_evaluation`, `executor_job`, `trainer_session`, `micro_update`, and `status_refresh` kinds are not accepted by the new registry. Their records remain in the evidence archive.

Cortex evaluation is always based on behavioral chat probes and MRI/activation
evidence. Loss remains useful execution telemetry, but it has no authority to rank,
admit, reject, continue, promote, or roll back a checkpoint.

Experimental gate-credit diagnostics are an optional `model.train` input and
are disabled unless an exact workflow enables them. Phase 1 observes the raw
and post-dropout sparse gate, `-dL/dh`, parameter gradients, and intended
optimizer movement as bounded scalar evidence. It adds no learning rule. A
paired control/observed smoke test must pass the bitwise `checkpoint.compare`
gate before any representative diagnostic block is authorized. Diagnostic
scalars are mechanistic evidence only and cannot replace chat or MRI.

Training order is an immutable law across language and visual training: declared
order is executed exactly and shuffling is forbidden. Every runnable training job
belongs to an explicit campaign and carries an ordered session list whose entries
declare their semantic prerequisites. Mission Hub resolves only the exact parent
checkpoint's inherited knowledge closure, walks the proposed list in order, and
rejects the first prerequisite that is neither inherited nor earlier in that same
session. A dependency certificate binds the exact subject bytes, parent checkpoint,
parent-knowledge snapshot, and session-list hash. Job creation and admission of that
immutable list are one transaction; failure of either means no job exists, and the
lease boundary independently refuses legacy or damaged training jobs without an
admitted list.

Successful training atomically attaches the admitted session list to the one output
checkpoint and appends its teaching events to the hash-chained knowledge ledger.
Each checkpoint materializes its own lineage-specific closure, so sibling branches
never leak knowledge into one another. Each campaign snapshots `known-at-start` once
and appends `trained-during` records with campaign, session, job, run, checkpoint,
parent, and evidence provenance. Grep-friendly JSONL projections live beside the
Mission Hub database under `knowledge/`; they are append-only views of SQLite, not a
second authority. These records describe training exposure, while behavioral chat
and MRI remain the evidence for what the model can actually do.

Lesson generation is additionally governed by the versioned Ninereeds identity
and integrity policy. Conducting models receive neutral learner framing rather
than AI/model classifications. Ordinary lessons exclude incidental Ninereeds
identity claims; explicit identity lessons teach stable selfhood, calibrated
knowledge, provenance, authorship, and evidence-based belief revision. Claims or
questions classifying Ninereeds by consciousness, sentience, implementation,
substrate, embodiment, or obsolete assistant-denial formulas are outside the
curriculum. The vocabulary itself remains teachable when it is not being applied
to Ninereeds. Generated material and every training certificate bind the exact
active identity-policy hash and declared identity scope.

## Configuration model

All operational policy lives under `config/mission_hub` as strict TOML documents. Unknown and missing keys fail validation. Activation creates a complete resolved snapshot with a bundle hash and per-document hashes.

Configuration covers:

- global safety, database, API, protocol, scheduler, artifact-transfer, and commissioning safety settings;
- machine roles, maintenance, concurrency, capabilities, paths, and transport;
- exact role-specific release contents and Python environments;
- job schemas, handlers, ownership, criticality, timeouts, attempts, approvals, capabilities, allowed/required artifacts, routes, and prompts;
- providers, exact models, and explicit ordered routes;
- retry policies and failure-code taxonomy;
- schedules, strategic-decision cooldown, rolling external-call budget ceilings and reservations, retention, artifact types, and ownership;
- visual shadow mode, inter-stage cooldown, immutable store, pack/dimension/step/time/disk limits, and mandatory independent review;
- critical-failure log location/retention and bounded advisory Sol emergency mode;
- autonomous-recovery enablement, attempt/change/patch/time budgets, allowed and
  protected source roots, and exact targeted/regression test commands;
- legacy evidence sources and migration policy.

Secrets are referenced only by environment-variable name. Values are neither checked into TOML nor included in configuration/evidence snapshots.

## Artifact transaction

Mission Hub ingests selected operator-owned files into its content-addressed store after checking configured source roots, byte limits, and SHA-256. Materialization streams exact bytes through the same forced-command SSH identity used for jobs. The trainbox derives the destination from the content hash, refuses stale configuration/deployment identities, enforces size limits, writes atomically, and returns a machine-local URI. Mission Hub records that location only after the receipt matches the request.

Mission Hub resolves job artifact fields before leasing. A job is not eligible on a machine until each artifact has a verified available location there. The envelope carries the exact ID, kind, SHA-256, size, lifecycle, manifest, and URI. The agent verifies file content before a handler can run.

Successful result acceptance validates all output artifact declarations and commits the terminal run, job state, artifact metadata, locations, and events in one transaction. Job outputs may initially register only `observed` or `candidate` artifacts. Publication, protection, rejection, and deletion require separate decisions.

Retrieval is also explicit. Mission Hub requests one artifact ID, hash, size, deployment, and validated trainbox URI through the restricted boundary, streams the bytes into a temporary local object, verifies them, atomically commits the content-addressed object, and then records the Mission Hub location. Operator `scp` is not part of the job artifact path.

## Retry semantics

Failure codes declare a class and whether retry is ever valid. A job’s retry policy further limits allowed classes, attempts, repair attempts, backoff, and escalation. Both must permit retry.

- transient transport/provider/resource failures retry under the configured execution
  budget without source mutation and remain under a monitoring incident until a
  successor output verifies health;
- bounded model-output repair is separate from execution retry;
- invalid job specifications, unmet evaluation thresholds, safety refusals, and operator cancellation do not retry;
- queue-age expiry blocks a job instead of silently running stale work.

A terminal job can be reopened only by a recovery attempt that already contains the
required successful mutation, both test scopes, and a distinct active deployment. The
retry carries the attempt ID and preserves the original failed run. This avoids the old
circular rule where a newer deployment was required but on-call had no machinery to
create one. Operator restart count is separate from the ordinary execution-attempt
budget so a verified repair can supersede a terminal attempt without erasing it.

## Recovery and restart contract

The persisted state machine is:

`detected -> classified -> repairing -> verifying -> recovered`

Transient failures use `detected -> monitoring -> verifying -> recovered`. Failed
repair attempts return to `classified` while budget remains; exhaustion becomes
`escalated`. Safety and genuine external boundaries become `blocked` with a required
machine-readable blocker code. A terminal state cannot be inferred from prose. A
principal-authorized re-entry adds a distinct attempt, preserves all earlier attempts,
and increases the recorded execution budget only enough to represent the newly
authorized work; it does not waive validation or let a failed outcome be called success.

Successful software/contract/infrastructure recovery requires immutable action rows for
evidence preservation, a source patch, targeted and regression tests, deployment,
job retry, artifact validation, and health check. Configuration recovery substitutes a
configuration-change record for the source patch. Every action record hashes its kind,
status, sequence, and structured evidence. Patch/test files must exist under the
configured state root with matching bytes and SHA-256; deployment and retry evidence
must match current database rows. The incident closes only after a distinct successful
run emits the exact required artifacts. Only then are associated campaign blocks
resolved and a concise projection appended to the operational thread.

Configuration snapshots now contain the complete resolved recovery policy and can be
rehydrated without reading current TOML. Jobs pin configuration/runtime/input/deployment
identities. Leases, partial runs, failed outputs, recovery attempts, and blocks are all
durable. A new Mission Hub process or fresh model invocation needs only the database,
activated snapshot, source/release records, artifacts, evidence files, and logs; no
conversation or prior Codex session is an input to lifecycle decisions. Expired leases
become typed incidents, duplicate results are idempotently rejected, and transactional
state changes roll back on interruption.

Operational-responder attempts are retries of an existing trigger, not new research
incidents. Their provider failures are retained silently and requeued without pausing
unrelated work or recursively invoking on-call. Once an assessment succeeds, stale
responder incidents created by older releases are closed as superseded evidence.
Post-campaign strategic decisions have the same principal tier: their direction is
recorded immediately as an executed decision, while any physical follow-up must still
produce ordinary deployment, artifact, and run evidence.

To add a recoverable job type, define strict input/output schemas, exact required and
allowed artifact kinds, executor capabilities, a retry policy with repair budget, and
specific failure codes. Its handler must construct exactly the declared outputs. Add a
targeted repair test and at least one fault-matrix entry proving its classification and
recovery or its explicit blocker boundary.

## Machine separation

The Mission Hub release contains the store, API, scheduler, dispatcher, evidence/migration tooling, configuration, and schemas.

The trainbox release contains only the stateless agent boundary, safe handlers, shared contracts, Cortex model code, optimizer, and exact training/evaluation/probe entry points. Its environment attestation separately records the Cortex interpreter, the vision interpreter and required package versions, and each exact pinned visual-model snapshot revision, marker hash, file count, byte count, and broken-link check. It explicitly excludes:

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

The Mission Hub services, restricted trainbox agent, artifact path, bounded GPU probe, Cortex composite runtime, production baseline, ordered-corpus validation, and purpose-bound train/evaluate workflow were commissioned on 2026-08-06. Campaign 33 completed all four declared branch evidence paths on 2026-08-07. Its final interpretation is in `docs/campaign33_findings_2026-08-07.md`; reusable findings are in the canonical architecture knowledge ledger. Campaign 34 Phase 1 is a separately configured paired observational experiment and does not alter Campaign 33 evidence.
## Training purpose is immutable

Every non-legacy campaign must carry the versioned contract described in `docs/ninereeds_training_modes.md`. Training-session plans bind its hash and mode. Evaluation context is generated from it, and evolutionary completeness is derived from succeeded branch evaluations rather than accepted from a caller. Behavioral chat and MRI remain the only evaluation basis; loss remains telemetry only.
