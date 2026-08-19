# Ninereeds operations audit

**Audit date:** 2026-08-05 (Asia/Tokyo)

**Scope:** workstation, training box, repository, control plane, training pipeline, state, artifacts, configuration, services, documentation, and tests

**Operating constraint:** the training pipeline remained stopped; discovery was read-only except for this report

**Status:** forensic baseline for the backend rebuild, not a deployment specification

## Executive finding

Ninereeds does not currently have one backend. It has several overlapping generations of a backend sharing one repository and many of the same directories:

1. an older MSM phase/session/update pipeline;
2. a Cortex campaign/evaluation pipeline;
3. a file-ledger orchestration and remote-execution layer;
4. an LLM-driven strategic/executor/recovery layer;
5. a Lab server with its own scanning, Git, messaging, inference, and artifact actions;
6. historical campaign, corpus, repair, and monitoring scripts that remain beside production entry points.

The parts are individually more disciplined than the whole. The control ledger has atomic writes, leases, bounded envelopes, and restricted SSH entry points. Targeted tests pass. The current Cortex architecture and recent campaign records are recoverable. The main failure is authority: multiple files, branches, services, and derived views can each appear to answer the same operational question.

The pipeline should not be restarted from its present layout. The first rebuild milestone should establish:

- one canonical source revision deployed immutably to both roles;
- one owner for each kind of state and artifact;
- a small, explicit job catalog with executable handlers;
- a typed configuration registry containing every operational knob;
- a migration/snapshot of the current campaign before obsolete authorities are retired;
- backend APIs that expose those authorities without the Lab server independently inferring or mutating them.

## Severity summary

| Severity | Finding | Consequence |
|---|---|---|
| Restart blocker | Workstation and trainbox run divergent branches and dirty source trees | The same job can mean different code depending on the machine |
| Restart blocker | Campaign, phase, development, control, and status files disagree | Automation cannot reliably determine the next legal action |
| Restart blocker | Job kinds are declared that the trainbox worker cannot execute | Valid ledger envelopes can become guaranteed failures |
| Restart blocker | Automatic evolution/rollover and checkpoint pruning are enabled in tracked configuration | Restart can create work or delete artifacts before policy is reconciled |
| High | Executor choice is controlled by code and credential presence, not the nominal fixed configuration | Requested/provider routing is not transparent or reproducible |
| High | Stale `running` work and a failed emergency-recovery transition remain in live state | Resumption may reconcile against an invalid boundary |
| High | The trainbox contains a full working repository and the workstation contains training data/checkpoints | Machine separation is not enforced and accidental cross-role use remains possible |
| High | Lab is active on the LAN and owns background Git, filesystem inference, messaging, and artifact actions | A UI backend has independent operational authority before the backend contract exists |
| High | Hermes remains enabled on the workstation despite handoffs saying it was replaced | A stale gateway continues to run and retry network work |
| Medium | Test discovery and Python environments are not defined at repository level | Full test results depend on current interpreter and unrelated files |
| Medium | Hundreds of historical scripts and tracked generated artifacts obscure production reachability | Operators cannot tell supported tooling from archaeological residue |
| Medium | Documentation contains multiple incompatible “source of truth” descriptions | A human following a plausible document can operate the wrong system |

## 1. Audit baseline

### Workstation

- Host: `pop-os`
- Repository: `/home/aomukai/Ninereeds`
- Branch: `agent/play-control-lab`
- Commit: `fbf704386`
- Upstream: `origin/agent/play-control-lab`
- Relevant active user services:
  - `ninereeds-lab.service`, enabled and active, listening on `0.0.0.0:8765`;
  - `hermes-gateway.service`, enabled and active;
  - no active Ninereeds orchestrator timer/path;
  - the Lab message-worker source units exist but are not installed/enabled as a working path/timer pair.
- Disk: approximately 234 GiB total, 173 GiB used, 49 GiB available (78% used).

The repository is intentionally not clean. Approximately 57,000 status entries are present, dominated by tracked deletions under the former `training_data/pre_c16` layout and untracked top-level corpus directories. There are also dozens of non-corpus modifications and untracked files. This audit did not interpret those changes as disposable or attempt cleanup.

### Training box

- Host: `ninereeds`
- Repository: `/home/aomukai/Ninereeds`
- Branch: `trainbox/runtime`
- Commit: `24414eeed`
- Upstream: `origin/trainbox/runtime`
- GPUs: two RTX 3060 12 GiB devices; idle at audit time.
- Relevant active user services:
  - `ninereeds-heartbeat.timer`, enabled and active;
  - trainbox worker path/timer disabled;
  - Hermes disabled;
  - Lab absent/inactive.
- Disk: approximately 900 GiB total, 662 GiB used, 193 GiB available (78% used).

Important storage consumers include roughly 115 GiB under `core`, 291 GiB in `~/.local/share/ninereeds-archives`, 62 GiB in the external executor tree, and 54 GiB in the Hugging Face cache. Sixty-five `.pt` files under `core` total approximately 123.4 GB in decimal units.

### Source divergence

The two checked-out branches diverge from `main` (`a62af9133`) by one commit on each side. Compared with the workstation branch, the trainbox branch removes or reduces ten control/Lab/test files by a net 1,542 lines, including complete removal of `training/pipeline/control/timing_log.py` and its test. Both worktrees also have overlapping dirty files, and at least seven overlapping paths have different content.

Installed unit files match the source tree on their respective host. This rules out “forgot to reinstall the unit” as the main explanation: the deployed source itself is split.

**Required invariant:** a run must record a single immutable source revision, configuration revision, and environment image; the worker must refuse a plan whose declared revisions do not match its deployment.

## 2. What exists

### 2.1 Active backend/control modules

Static entry-point and service tracing reaches roughly 47 relevant Python modules across these areas:

- Lab server: configuration, authentication, control status, Git status/pull, artifact scanning, chat/inference, messages, notifications, trainbox status, and orchestrator access;
- control plane: file ledger, SSH transport, remote command restriction, wake scheduler, supervisor, trainbox worker, campaign controller, strategic orchestration, provider failover, executor adapter, material generation, adversarial review, emergency recovery, experience ledger, and timing;
- Cortex: model core, training, evaluation, artifacts, development state, evolution policy, retention, foundation corpus, and visual components;
- legacy MSM: phase runner, session/update/finalization, grading, and phase status.

The principal control/model surface is about 23,600 lines. Concentration is high: `campaign_controller.py` is about 3,100 lines; the worker, experience ledger, supervisor, strategic orchestrator, and evaluation modules are each large independent state machines.

### 2.2 Script estate

`meta/scripts` contains 174 Python scripts, with additional workflow scripts elsewhere. They fall into four operational classes:

| Class | Examples | Disposition needed |
|---|---|---|
| Current runtime helpers | Cortex train/evaluate/runtime/probe, allowlist wave, visual commissioning | Promote behind registered job handlers |
| Legacy runtime helpers | MSM phase runner, micro-update, status/finalize helpers | Migrate required state, then quarantine or remove |
| Historical campaign tools | C13/C15/C17 builders, campaign runner/watchdogs | Archive outside the executable deployment |
| Corpus/repair/migration tools | generators, localizers, audits, annotation repair, one-time assembly | Keep as offline tooling with declared inputs/outputs, not on the worker path |

Static reachability is not sufficient because production modules launch several scripts dynamically. A job registry, not a directory scan, must declare which commands are supported.

### 2.3 Data and generated material in Git

Historically tracked content includes approximately:

- 244,365 paths under `training_data`;
- 34,769 under `archive`;
- 5,839 under `tmp`;
- 441 under `training/logs`;
- generated state under `training/pipeline/msm/state`.

Ignore rules do not untrack existing files. Git is therefore serving simultaneously as source control, corpus transport, report archive, and partial runtime-state store. This is the largest repository-level source of noise and accidental coupling.

## 3. Jobs and workflows

### 3.1 Declared control-plan kinds

The ledger accepts nine kinds in `training/pipeline/control/ledger.py`:

| Plan kind | Intended owner | Actual executor | Assessment |
|---|---|---|---|
| `strategic_decision` | Mission Control | workstation supervisor | Active; LLM output validated and materialized locally |
| `phase_block` | Training | trainbox worker | Legacy MSM handler; active code, not current Cortex centerline |
| `cortex_block` | Training | trainbox worker | Active parent/aggregate workflow |
| `cortex_corpus_chunk` | Training | trainbox worker | Active training unit |
| `cortex_evaluation` | Training | trainbox worker | Active evaluation unit |
| `executor_job` | Execution service | trainbox worker/external executor tree | Active; hides several workflow subtypes |
| `trainer_session` | Training | trainbox worker | Legacy session workflow |
| `micro_update` | Training | none in current trainbox dispatcher | Declared but unsupported |
| `status_refresh` | Control | none in current trainbox dispatcher | Declared but unsupported |

The trainbox dispatch function handles only six non-strategic kinds. `micro_update` and `status_refresh` can pass ledger validation but have no worker branch. This is a contract defect.

### 3.2 Hidden job subtypes

`executor_job` is not one job. The supervisor interprets workflow-specific payloads including:

- generic executor proposal/validation;
- `cortex_train`;
- `cortex_curriculum`;
- `msm_trainer`;
- `msm_grade`.

Those subtypes have distinct resource needs, validation, retry behavior, and artifact lifecycles but share one outer kind. They should be first-class registered job types or explicit steps in a versioned workflow definition.

### 3.3 Work performed outside the job model

The following operations are effectively jobs but lack durable run records of their own:

- campaign reconciliation, rollover, publication, and child-plan derivation;
- provider health monitoring/failover;
- adversarial review;
- emergency recovery;
- retention checks and pruning;
- development-state reconstruction;
- Lab filesystem scans and background Git pulls;
- Lab message processing;
- heartbeat/status publication.

This makes “what ran, under whose authority, with which configuration?” impossible to answer uniformly.

### 3.4 Current execution flow

1. The workstation ledger stores plans, claims, receipts, and reports as JSON files.
2. The supervisor scans the local ledger, executes strategic work locally, dispatches executable work over SSH, synchronizes reports, derives children, publishes evaluations, and reconciles campaigns.
3. The restricted trainbox control command accepts plan submission, ledger queries, snapshots, and worker wake-up.
4. The trainbox worker drains its own file ledger under a global lock and launches training, evaluation, executor, or legacy MSM subprocesses.
5. A wake scheduler can poll/synchronize and start the supervisor.

This is serviceable as a prototype but places policy, scheduling, transport, execution, state reconstruction, and recovery in one supervisor loop. Every scan revisits a large file tree, while causal relationships are inferred from envelopes and naming conventions.

### 3.5 Ledger snapshot

At audit time:

| Store | Plans | Receipts | Reports | Notable state |
|---|---:|---:|---:|---|
| Workstation `ninereeds-orchestrator-control` | 781 | 781 | 754 | 734 completed, 18 blocked, 28 dead-letter, 1 stale running |
| Trainbox `ninereeds-control` | 629 | 628 | 605 | snapshot: 589 completed, 15 blocked, 24 dead-letter |

The workstation also has a separate nearly empty `ninereeds-control` directory, which is a naming trap. The difference between the two real ledgers is partly intentional—strategic plans run locally—but their relationship is not represented as a single authoritative run graph.

Boundary 68 of campaign 33 remains `running` with an expired lease even though the pipeline is deliberately stopped. An emergency-recovery record proposed a recovery boundary and then failed because recovery required a blocked campaign while the campaign was still `running`. This state must be closed or migrated explicitly before resumption.

## 4. Ownership and machine placement

### 4.1 Target ownership model

| Concern | Canonical owner | Workstation / Mission Control | Trainbox / Training Environment |
|---|---|---|---|
| Source repository | source-control release process | authoring checkout allowed | immutable release checkout/image only |
| Job definitions and schemas | backend package | create/validate/schedule | validate declared version, execute only registered handlers |
| Job/run database | Mission Control | authoritative | no independent competing ledger; local execution spool/cache only |
| Campaign policy and decisions | Mission Control | authoritative | receive explicit resolved work |
| Secrets/provider credentials | host secret manager | strategic/API credentials needed locally | only credentials needed by trainbox handlers |
| Corpus catalog/metadata | Mission Control | authoritative catalog and manifests | materialized read-only shards/cache |
| Large corpus bytes | artifact/data store | optional working subset | required shards only |
| Training checkpoints | Training artifact store | metadata, selected exports, optional cache | authoritative bytes while training |
| Evaluation results | run/artifact database | authoritative indexed result | produce and upload/commit result atomically |
| Executor models/runtimes | Training Environment | model catalog metadata | model bytes and commissioned runtime images |
| Health/telemetry | each host produces, Mission Control aggregates | aggregate and alert | publish host facts only |
| Lab UI | presentation/API client | read/control through backend authority | absent |
| Git mutation | release/deployment workflow | explicit operator action | never from a web request or background worker |

### 4.2 Files that belong only on the workstation

- Lab frontend/backend and authentication/session state;
- campaign definitions, scheduling policy, strategic prompts, approvals, and operator notes;
- authoritative job/run database and audit log;
- deployment manifests and machine inventory;
- documentation and development/test tooling;
- provider integrations not required for training execution.

### 4.3 Files that belong only on the trainbox

- GPU training/evaluation handlers and pinned Python/runtime environments;
- local executor runtimes and model weights;
- materialized training shards and caches;
- in-progress optimizer/checkpoint state;
- host-local execution spool, logs, and telemetry;
- restricted remote-control command and narrowly scoped service account/key.

### 4.4 Files that should be shared by release, not by mutable checkout

- versioned schemas and job-handler contracts;
- model architecture/config definitions;
- deterministic curriculum manifests;
- evaluation suite definitions;
- artifact metadata formats;
- a generated, secret-free configuration schema/defaults package.

The trainbox currently contains the full repository, including Lab and historical tooling. The workstation contains large corpus/checkpoint material. The generic SSH alias also provides an unrestricted shell in addition to the well-designed forced-command status/control keys. The rebuild should deploy allowlisted packages/artifacts per role and make the restricted interface the normal operational path.

## 5. Configuration and “every knob” audit

### 5.1 Configuration sources

Operational behavior is currently selected by all of the following:

- tracked JSON configuration and policy files;
- environment variables in Python defaults and systemd units;
- host-local environment files;
- command-line arguments;
- constants embedded in modules;
- credential presence, which changes provider order;
- current branch and dirty worktree contents;
- filesystem naming/latest-file inference;
- mutable state files that double as configuration;
- prompts embedded in Python source.

There is no resolved configuration snapshot attached to a run.

### 5.2 Lab settings

`lab/backend/config.py` exposes environment knobs for:

- scan and serve roots;
- trusted origins and maximum request body;
- Git pull enablement, interval, dirty-tree policy, expected branch, and remote;
- orchestrator URL/API key/control root;
- auth password, signing secret, secure-cookie mode;
- trainbox status/control SSH targets, timeouts, caches, and stale threshold;
- control-status timeout/cache;
- message-worker executable, model, timeout, lease, and attempts.

The installed Lab unit sets only the expected Git branch and remote. Most behavior therefore comes from code defaults. The default signing secret is explicitly development-only, secure cookies default off, and the service binds to all interfaces. A password is configured in host state, but this remains an unsuitable place for hidden operational defaults.

The Lab background Git pull is enabled by default. It currently skips because the expected branch is `main` while the checkout is `agent/play-control-lab` and dirty. Git mutation should not be a responsibility of the Lab backend at all.

### 5.3 Orchestrator/worker environment settings

Important environment switches include:

- trainbox control target and control-root locations;
- strategic provider and Codex/Fugu executables/models;
- OpenRouter and emergency-model identifiers, token limits, and timeouts;
- adversarial-review interval;
- live-execution permission (`NINEREEDS_ALLOW_LIVE`);
- provider API-key variables;
- Cortex/torch/visual-cache paths.

The worker unit defaults live execution off and reads a host environment file that overrides runtime settings. Secret values were not recorded in this audit. The effective non-secret configuration should be inspectable without revealing secrets; a boolean “credential available” is sufficient for status.

### 5.4 Training/evaluation command knobs

The Cortex training CLI controls input JSONL/script source, output and parent checkpoint, epochs, batch size, sequence length, learning rate, weight decay, seed, devices, train scope, RMS clipping, stochastic rounding, locality, probe tokens, and source concept. Evaluation separately controls candidate/parent, suite, campaign, target/stage, devices, token limit, and output.

These knobs are legitimate experiment parameters. They should be schema-validated values in an immutable run specification, not reconstructed from a command string.

### 5.5 Embedded policy constants

Material behavior remains hardcoded in control modules: campaign intervals and budgets, block sizes and corpus mixes, provider order, URLs, model IDs, API-key names, timeouts, retry counts, maximum output sizes, CUDA assignments, checkpoint retention, and recovery limits. Prompt templates are primarily Python strings in the strategic orchestrator, executor adapter, provider failover, adversarial review, emergency recovery, material generator, campaign controller, and message worker.

The rebuild needs a typed registry with these categories:

| Category | Examples | Change authority |
|---|---|---|
| Deployment | host role, release ID, handler image, devices, paths | operator/release |
| Safety | live permission, deletion/pruning, external provider access | explicit operator approval |
| Workflow policy | budgets, retries, gates, rollover, concurrency | versioned policy |
| Experiment | LR, batch, length, scope, seed, parent, corpus manifest | run spec |
| Provider | ordered routes, model, context, price/timeout limits | versioned provider policy |
| Presentation | polling/cache/display choices | Lab configuration |

Every run should store the resolved values and hashes of referenced prompt, schema, corpus, model, and source artifacts.

### 5.6 Executor routing contradiction

The tracked MSM orchestrator configuration declares a fixed selection mode, defaults to DeepSeek Flash, and names several local executors with a `local:` prefix. `executor_adapter.py` uses unprefixed local IDs, declares Qwen TurboQuant as primary, and then states that the requested model is retained only for compatibility/auditing because the harness owns escalation order. If a DeepSeek credential is present, official DeepSeek becomes first, followed by local Qwen/Bonsai/Gemma and DeepSeek Pro; otherwise local models precede remote providers.

Thus there are at least three conflicting answers to “which model runs this job?”: configuration, selection validation, and credential-dependent ladder code. Provider order must become one explicit, resolved plan field.

### 5.7 Retention and autonomous evolution

`retention_policy.json` enables automatic pruning at 80% used, warns at 75%, and marks 85% critical, with a 25 GiB minimum-free threshold. The trainbox was at 78% used during this audit. `evolution_goal.json` is enabled and configures automatic 24-hour campaign rollover with nonzero strategic and executor budgets.

Even with timers stopped, these settings make a future service restart dangerous. Pruning and auto-rollover should require separately visible enablement, dry-run previews, and durable decisions. Destructive retention must never be an incidental side effect of a training handler.

## 6. State and artifact authority

### 6.1 Competing state stores

Current operational truth is distributed among:

- workstation and trainbox control ledgers;
- campaign registry and campaign directories;
- Cortex development/evaluation/artifact records;
- MSM phase registry, orchestrator status/config, session state, and sentinels;
- heartbeat state;
- emergency recovery/adversarial/provider state;
- Lab messages, receipts, auth, and caches;
- filenames and directory scans used to infer “latest.”

The status helper simultaneously reported a completed/current Cortex campaign checkpoint and old MSM phase fields. It also reported `latest_block_gate_status: met` and `next_safe_action: review_phase_gate` while `phase_gate_status` was `not_met`. The heartbeat considered the repository healthy when Git commands succeeded even though the checkout was dirty.

### 6.2 Required authority rules

- A run database owns lifecycle state; workers report facts and cannot rewrite campaign policy.
- A campaign record references runs; it does not duplicate their status.
- A checkpoint manifest owns lineage, hashes, architecture, training run, and disposition.
- An evaluation record owns suite results and admission decision inputs; a separate durable decision owns acceptance/rejection.
- Host heartbeat reports observed health only.
- “Latest” is a query over authoritative records with an explicit scope, never a filename heuristic.
- Derived status is rebuildable and carries `derived_at`, source IDs, and staleness.
- Legacy MSM phase state is either migrated into the new model or frozen read-only under a legacy namespace.

### 6.3 Artifact lifecycle gaps

Checkpoint bytes, development checkpoints, campaign winners, rejected candidates, reports, and archives live in several roots. Retention code interprets these locations, while Lab artifact scanning also infers records from paths. There is no single manifest transaction coupling a successful write, checksum, evaluation, publication, and retention eligibility.

A minimal artifact contract should include: artifact ID, kind, producing run/attempt, content hash, byte size, storage location, architecture/config hash, parent IDs, lifecycle state, protection reason, created time, and deletion decision. Only the artifact service should mutate lifecycle or delete bytes.

## 7. Concrete problems found

### 7.1 Deterministic work delegated to an LLM

Campaign 33 requested that an executor reproduce 500 existing examples within a 4,096-token output budget. The result was a one-item placeholder: structurally JSON-like but semantically unusable, recorded as `RETRYABLE_FORMAT_ERROR`. The system retried a transformation that should have been a deterministic copy/filter operation.

The same pattern appears in historical failures where fixed schema or byte-limit violations are retried three times without changing the constraint. Retry classification must distinguish transient infrastructure/provider errors, repairable model output, deterministic invalid specifications, and non-retryable safety/policy failures.

### 7.2 Status capability mismatch

The status helper advertises `training_dispatch: false` and `plan_claiming: false`, while the separate restricted control alias can submit plans and wake the worker. This is explainable as two endpoints but misleading as a machine capability statement. Capabilities should be endpoint-scoped and discovered from the handler registry.

### 7.3 Lab responsibilities exceed presentation

The active Lab backend can scan artifacts, infer current state, perform background Git operations, process messages through Codex/Fugu, invoke trainbox status/control, run chat/inference flows, and publish/copy build or checkpoint material. Meanwhile its message worker is not running, leaving approximately 102 inbox files with only five receipts at audit time.

The eventual Lab should call backend commands and queries. It should not contain alternative state inference or deployment logic.

### 7.4 Stale gateway

Hermes is active on the workstation although newer handoff material says Hermes is disabled/replaced. Journals show repeated Discord DNS failures; the process remains alive for its cron behavior. There is no workstation user crontab. Its remaining jobs should be inventoried and either moved to registered backend jobs or retired before the service is disabled.

### 7.5 Dependency and test discovery drift

No repository-level `pyproject.toml`, `pytest.ini`, `setup.cfg`, or root dependency lock defines the test environment. A bare `python3 -m pytest -q` collects an unrelated LoRA skill file and fails collection because the workstation system Python lacks Torch. In contrast:

- 161 targeted backend/control tests passed on the workstation;
- 127 tests present in the divergent trainbox checkout passed there.

Passing targeted tests support the local implementations, not cross-machine equivalence or full-pipeline correctness.

### 7.6 Environment fragmentation

The control/Lab services use system Python. Cortex and vision use separate virtual environments. The legacy trainer can use a separate Python path. Local executor models use multiple external llama.cpp/TurboQuant/Prism builds and Docker. None is identified by a single deployment manifest or lock.

Each registered handler needs a pinned runtime image/environment digest and a startup self-test.

## 8. Documentation audit

Documentation is not merely old; it describes incompatible architectures as current.

| Document | Problem |
|---|---|
| `README.md` | Describes MSM cold-start and a protected C17 checkpoint as current rather than the Play/Cortex campaign |
| `index.md` | Says the training machine is not assembled and centers phase-0/Hermes workflows |
| `todo.md` | Treats already implemented cold-start work as future design |
| `CLAUDE.md` and `CODEX.md` | Describe older architecture/workflows and point to nonexistent `docs/training.md`; `CODEX.md` also points to a nonexistent template log path |
| `training/pipeline/training.md` | Internally mixes an MSM cold-start runbook with newer Cortex autonomous-campaign material |
| `training/pipeline/runbook.md` | Cold-start-only operational instructions presented beside the current pipeline |
| `handoff/README.md` | More accurately identifies the LFM 1.2B architecture but its service/clean-branch snapshot is no longer current |
| `docs/visual_experience_pipeline_design.md` | Opens with the current LFM architecture but later retains mBERT receptor instructions |
| Hermes documentation | Some pages call it canonical and say the trainbox is unassembled while current service state says otherwise |

There are also overlapping “source of truth” claims for phase registry, orchestrator status, campaign state, Cortex development state, and report cards.

Documentation should be rebuilt into:

1. a current architecture/ownership document generated or verified against registered components;
2. an operator runbook containing only supported commands;
3. versioned design decisions;
4. historical campaign notes clearly marked archival;
5. generated job/config/schema reference;
6. a machine inventory and deployment record.

Old material should remain searchable but must be visibly outside the current runbook.

## 9. Simplification opportunities

### 9.1 Replace the supervisor megaloop with five explicit services

1. **API/control service:** validates commands and owns job/run/campaign records.
2. **Scheduler:** turns campaign policy into immutable job specs.
3. **Trainbox agent:** advertises registered handlers/resources, leases jobs, and reports attempts/artifacts.
4. **Artifact service:** owns manifests, uploads, protection, and retention decisions.
5. **Provider/executor service:** resolves a declared provider policy and records each attempt.

These can initially remain lightweight processes and a local database; the key is ownership, not infrastructure fashion.

### 9.2 Use a small relational database for control state

SQLite in WAL mode is sufficient for a single Mission Control host and removes directory-wide scans, partial cross-ledger synchronization, and ambiguous latest-file selection. Core entities:

- `machines`, `deployments`, `capabilities`;
- `job_definitions`, `jobs`, `attempts`, `events`;
- `campaigns`, `decisions`, `approvals`;
- `artifacts`, `artifact_locations`, `lineage`, `retention_decisions`;
- `config_revisions`, `prompt_revisions`, `schema_revisions`.

The existing JSON ledger can be imported as immutable history and retained as an export format.

### 9.3 Collapse job vocabulary

Use a registry such as:

- `corpus.build` / `corpus.transform` / `corpus.validate`;
- `model.train`;
- `model.evaluate`;
- `checkpoint.probe` / `checkpoint.publish`;
- `executor.generate`;
- `campaign.decide`;
- `maintenance.retain`;
- `system.healthcheck`.

Composition belongs in a workflow spec; legacy `phase_block`, `trainer_session`, and workflow-specific executor payloads should not remain parallel orchestration systems.

### 9.4 Make deterministic operations code

Copying, slicing, mixing, deduplicating, schema conversion, hashing, and report aggregation should be deterministic handlers. LLMs should propose content or decisions where uncertainty is intended, with bounded structured output. They should not serialize existing large datasets through a token budget.

### 9.5 Separate policy from observation

Observed GPU/disk/process facts, derived model metrics, campaign policy, and operator decisions currently meet in status files. Store them as different record types with explicit provenance. A dashboard can combine them without making the combination authoritative.

## 10. Proposed rebuild sequence

### Phase A — freeze and preserve

1. Keep all training/orchestrator timers and worker paths stopped.
2. Capture hashes/manifests for current campaign 33, boundary 68, accepted/development checkpoints, both ledgers, and relevant configuration.
3. Record the two dirty worktrees without cleaning or merging them.
4. Decide how the stale boundary is closed in the historical record.

### Phase B — define contracts

1. Write the canonical job registry and map every current plan/subtype/script to keep, migrate, archive, or delete-later.
2. Define machine roles and an allowlist deployment manifest.
3. Define job, attempt, event, artifact, campaign, decision, and configuration schemas.
4. Put prompts, provider ladders, retry classes, and safety switches under versioned configuration.

### Phase C — establish authority

1. Create the Mission Control database and import JSON ledger history read-only.
2. Implement the trainbox agent against job leases and registered handlers.
3. Implement artifact manifests and non-destructive retention previews.
4. Remove filename-based and legacy-status authority from live queries.

### Phase D — separate deployments

1. Produce one release revision and two role-specific manifests/images.
2. Move large bytes to declared artifact/data roots; remove them from normal source deployment.
3. Pin and self-test each runtime environment.
4. Use restricted transport as the normal interface; remove routine dependence on generic SSH.

### Phase E — compatibility and commissioning

1. Replay/import representative historical plans without executing model training.
2. Run deterministic handler and failure/retry tests.
3. Commission one dry-run job end to end, then a tiny disposable GPU job.
4. Verify cancellation, crash recovery, idempotency, artifact hashing, and retention dry-run.
5. Only then migrate/resume the intended campaign lineage.

### Phase F — Lab redesign

Build the Lab against stable query/command APIs. It should display resolved configuration, ownership, provenance, run graphs, artifacts, and approvals; it should not scan repository internals or mutate Git.

## 11. Restart gates

Training must remain stopped until all of these are true:

- [ ] One approved source revision is deployed to both machine roles.
- [ ] Dirty runtime checkouts are replaced by reproducible deployments or formally snapshotted.
- [ ] Campaign 33/boundary 68 has one explicit migrated lifecycle state.
- [ ] Every accepted job kind has a registered executable handler; unsupported kinds are rejected at submission.
- [ ] Mission Control is the sole lifecycle authority; trainbox state is an execution spool, not a competing ledger.
- [ ] Current checkpoint lineage and protected artifacts have verified hashes/manifests.
- [ ] Automatic pruning is disabled or separately approved after a dry-run report.
- [ ] Automatic campaign rollover/evolution is disabled until commissioning completes.
- [ ] Provider/model routing is explicit in each resolved run spec.
- [ ] Retry classification prevents deterministic invalid work from looping.
- [ ] Runtime environments and GPU/resource assignments are pinned and self-tested.
- [ ] The current runbook names only supported services, commands, paths, and authorities.
- [ ] End-to-end dry run and tiny GPU commissioning job pass on the new backend.
- [ ] Lab and Hermes cannot independently schedule, deploy, prune, or infer authoritative state.

## 12. Decisions still requiring the operator

These cannot be safely inferred from the filesystem alone:

1. Whether campaign 33 should eventually resume, be superseded by a migrated campaign, or remain a historical stopped campaign.
2. Which current dirty changes are intentional source work versus generated/runtime residue.
3. Which checkpoints/corpora must exist on both machines for interactive research, versus only in the artifact store/trainbox cache.
4. Whether external strategic/executor providers are desired in the rebuilt default policy and under what cost/privacy limits.
5. What retention actions may ever run automatically; the safe initial answer is “none.”
6. Which Hermes cron responsibilities, if any, remain valuable.

## 13. Active knob register

This register covers the reachable backend/control/training surface. Offline corpus generators have many additional command-line options; they are part of the script-disposition audit and must not be promoted automatically into production configuration.

### Lab environment variables

`LAB_SCAN_ROOTS`, `LAB_SERVE_ROOTS`, `LAB_TRUSTED_ORIGINS`, `LAB_GIT_PULL_INTERVAL`, `LAB_GIT_PULL`, `LAB_GIT_ALLOW_DIRTY`, `LAB_GIT_EXPECTED_BRANCH`, `LAB_GIT_EXPECTED_REMOTE`, `LAB_ORCHESTRATOR_URL`, `LAB_ORCHESTRATOR_API_KEY`, `LAB_AUTH_PASSWORD`, `LAB_AUTH_SECRET`, `LAB_AUTH_COOKIE_SECURE`, `LAB_MAX_REQUEST_BODY`, `LAB_TRAINBOX_SSH_TARGET`, `LAB_TRAINBOX_STATUS_TIMEOUT`, `LAB_TRAINBOX_STATUS_CACHE`, `LAB_TRAINBOX_STATUS_STALE`, `LAB_TRAINBOX_CONTROL_SSH_TARGET`, `LAB_ORCHESTRATOR_CONTROL_ROOT`, `LAB_CONTROL_STATUS_TIMEOUT`, `LAB_CONTROL_STATUS_CACHE`, `LAB_MESSAGE_CODEX_EXECUTABLE`, `LAB_MESSAGE_CODEX_MODEL`, `LAB_MESSAGE_CODEX_TIMEOUT`, `LAB_MESSAGE_LEASE_SECONDS`, and `LAB_MESSAGE_MAX_ATTEMPTS`.

### Control/provider environment variables

`NINEREEDS_ALLOW_LIVE`, `NINEREEDS_ORCHESTRATOR_CONTROL_ROOT`, `NINEREEDS_TRAINBOX_CONTROL_TARGET`, `NINEREEDS_CODEX_EXECUTABLE`, `NINEREEDS_CODEX_MODEL`, `NINEREEDS_FUGU_EXECUTABLE`, `NINEREEDS_STRATEGIC_PROVIDER`, `NINEREEDS_STRATEGIC_TIMEOUT_SECONDS`, `NINEREEDS_OPENROUTER_STRATEGIC_MODEL`, `NINEREEDS_OPENROUTER_STRATEGIC_MAX_TOKENS`, `NINEREEDS_OPENROUTER_SOL_MODEL`, `NINEREEDS_EMERGENCY_SOL_MODEL`, `NINEREEDS_EMERGENCY_SOL_TIMEOUT_SECONDS`, `NINEREEDS_ADVERSARIAL_REVIEW_INTERVAL`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `SAKANA_API_KEY`, and `SSH_ORIGINAL_COMMAND`.

Related legacy/tooling variables found outside the main service path include `MSM_TRAIN_PYTHON`, `NINEREEDS_TORCH_SITE`, `NINEREEDS_VISUAL_MODEL_CACHE`, `NVIDIA_API_KEY`, `OPENAI_API_KEY`, and `WORKER_API_KEY`. Their presence is evidence that offline tools also need an explicit environment and secret policy.

### Active command-line interfaces

| Entry point | Knobs/commands |
|---|---|
| `train_cortex.py` | `--jsonl`, `--script-stdin`, `--output`, `--parent`, `--epochs`, `--batch-size`, `--max-examples`, `--lr`, `--weight-decay`, `--seed`, `--ingress-device`, `--core-device`, `--train-scope`, `--rms-clip`, `--stochastic-rounding`, `--local-files-only`, `--probe-max-new-tokens`, `--source-concept` |
| `evaluate_cortex.py` | `--candidate`, `--parent`, `--suite`, `--campaign-id`, `--target-concept`, `--development-stage`, `--ingress-device`, `--core-device`, `--max-new-tokens`, `--output` |
| `trainbox_worker.py` | `--control-root`, `--repo`, `--max-plans`, `--lease-seconds` |
| `orchestrator_supervisor.py` | `--control-root`, `--repo`, `--ssh-target` |
| `orchestrator_wake_scheduler.py` | `--control-root`, `--ssh-target` |
| `campaign_cli.py` | `start`, `status`, `pause`, `resume`, `extend-budget`, `recover`, `close`, `reconcile`, with campaign/budget arguments on mutating commands |
| control-ledger CLI | `create-plan`, `import-plan`, `snapshot`, `show`, with plan kind/mode/payload/attempt/deadline/root fields |
| remote boundary | restricted `submit`, `show`, `snapshot`, and wake/status operations selected from `SSH_ORIGINAL_COMMAND` |
| experience CLI | `record`, `assess`, `rule`, `promote`, `search`, `acknowledge`, `digest` |

### Tracked configuration/policy files

| File | Operational knobs |
|---|---|
| `training/executor/models.trainbox.json` | executor root, visible CUDA devices, runtime kind/image/binary, model path, context/fallbacks, GPU layers, server arguments |
| `training/pipeline/msm/state/orchestrator_config.json` | buffer thresholds, checkpoint parent policy, deduplication, prompt context, executor list/default/mode, scheduler weights, phase thresholds, schema/sentinel paths |
| `training/pipeline/cortex/development_policy.json` | architecture, stage order, readiness step/block/concept/example floors, policy notes |
| `training/pipeline/cortex/evolution_goal.json` | master enable, north star, rollover duration and job budgets, stage objectives, escalation/non-blocker policy |
| `training/pipeline/cortex/retention_policy.json` | warning/prune/critical disk fractions, minimum free bytes, checkpoint headroom, winner/development/rejected retention counts, automatic-pruning enable |
| phase/campaign/evaluation JSON | current phase, gates, campaign budgets/status, parent/candidate IDs, suite thresholds and decisions; currently a mixture of policy, input, and mutable state |

### Important constants still outside configuration

The exact list changes between the two deployed branches, which is itself a finding. Material examples include the Qwen/DeepSeek/Bonsai/Gemma ladder, provider endpoints and request options, 32K context boundary, 60-second remote heartbeat, 256 KiB ledger envelope limit, phase support allowlist, campaign block/corpus budgets, recovery and retry caps, status/cache intervals, file-size limits, checkpoint headroom behavior, and hardcoded repository/executor/state paths in service helpers.

The rebuild should generate this register from typed settings and handler manifests. A CI check should reject new operational environment reads, CLI options, or policy-like constants that are absent from the registry.

## 14. Validation performed

- Inspected Git status, refs, divergence, tracked-content distribution, and repository sizes on both hosts.
- Inspected user services, timers, paths, installed unit/source equivalence, journals, listening service, and host status.
- Inspected trainbox GPUs, storage, runtime/model roots, SSH forced commands, and control/status endpoints.
- Counted and classified control ledgers, plans, receipts, reports, messages, checkpoints, scripts, schemas, and source modules.
- Traced service entry points, plan dispatch, workflow derivation, provider routing, state reconstruction, retention, and Lab responsibilities.
- Compared current documentation claims with deployed state and recent campaign artifacts.
- Ran targeted tests without starting pipeline services:
  - workstation: 161 passed;
  - trainbox: 127 passed.
- Confirmed that an unrestricted root pytest run is not currently a valid test command because discovery includes unrelated code and the workstation system interpreter lacks training dependencies.

No services were enabled, started, stopped, or restarted. No plans were submitted, claimed, retried, or reconciled. No checkpoints, corpora, state, branches, or user changes were cleaned or modified.
