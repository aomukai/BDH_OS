# Pipeline hardening audit — 2026-08-09

## Scope and disposition

This pass audited Mission Hub state, jobs/runs, configuration snapshots, deployment and
transport identities, providers, artifacts, schedules, workflows, campaigns, critical
notices, retry rules, and restart behavior. Static inspection was followed by fault
injection and end-to-end recovery simulations. The checked-out hardening release is
test-ready; it has intentionally not been activated against the live Mission Hub.

## Principal defects found and repaired

- On-call could diagnose deterministic defects but ran read-only and had no repair,
  test, deployment, or verified retry mechanism. Its “no action” path could contradict
  its own diagnosis, and refused actions could be recorded as successful responses.
- Terminal job retry required a newer deployment that on-call could not create. Normal
  attempt limits also made verified post-repair retry impossible.
- Operational prose was treated as the practical incident record. There was no durable
  incident state, attempt budget, action ledger, blocker code, or closure proof.
- Critical failure, campaign blocking, repair, retry, and unblocking were not one
  coherent state machine. A repaired successor could leave stale blocking state.
- Result artifacts were checked mainly at final commit; zero, duplicate, wrong, or
  unexpected declarations could travel too far through the execution boundary.
- Malformed successful remote output could be lost while being converted to failure.
- Provider empty/truncated/invalid structured responses and timeouts collapsed into
  coarse errors, weakening routing and retry behavior.
- Configuration rollback was not an atomic operation tied to retained deployments, and
  persisted snapshots could not independently reconstruct the full effective bundle.
- Local/remote role activation lacked a bounded, content-hashed release install protocol.
- Multiple generic workflows embedded concrete machine IDs; role lookup now comes from
  the machine registry. Remaining Campaign 35 identifiers are confined to its explicit,
  specialized recipe and UI projection. Host paths, model revisions, endpoints, and SSH
  targets remain deployment configuration rather than implementation logic.

## Recovery architecture delivered

`recovery_incidents`, `recovery_attempts`, `recovery_actions`, and `campaign_blocks` are
authoritative SQLite records. Failure capture is transactional with run completion.
Actions are structured and hashed; source patches and test transcripts additionally
require on-disk bytes, sizes, and SHA-256 under the Mission Hub state root. A closure
claim cannot pass without the category-specific mutation, both test scopes, a distinct
active deployment, retry identity, exact output artifact validation, and a healthy
successor run.

The bounded software loop checks out the failed release identity, permits edits only in
configured roots, rejects protected/oversized changes, runs targeted and regression
tests, commits a repair release, installs and activates it locally or through exact
restricted-SSH commands, retries the immutable work, and reconciles health. Failed
attempts remain immutable and consume budget. Configuration defects roll back to one
complete retained snapshot and matching deployments in a single transaction. Transient
provider/transport faults use retry/fallback without software mutation.

Campaign jobs create explicit root-cause blocks on terminal failure. Queuing a retry is
not enough to unblock; only verified successor output resolves the block. Visual and
Cortex workflow state is reopened for the repaired job without deleting the failed run.

## Simulations and results

The new recovery and fault-injection suites exercise:

- deterministic required-artifact producer failure, repair, tests, deployment, retry,
  artifact verification, campaign unblock, and incident closure;
- transient provider/transport retry with no source or deployment mutation;
- invalid configuration rollback to known-good configuration and both role deployments;
- a first repair that fails validation followed by a successful bounded second attempt;
- fresh `MissionHubStore`/coordinator continuation with no conversational state;
- false source/test/deployment claims rejected before retry or closure;
- missing, duplicate, wrong, extra, corrupt, partial, and malformed outputs;
- empty, truncated, invalid structured, timed-out, and fallback provider behavior;
- disk/SSH/trainbox/deployment/checkpoint/dependency/process categories;
- transaction interruption, lease expiry, duplicate delivery, scheduler/store restart,
  partial deployment receipts, and campaign block/recovery cycles.

Final executed results:

- focused recovery/provider/transport/workflow suite: **43 passed**;
- full dependency-light suite: **175 passed, 8 skipped** in 36.39 seconds;
- full Cortex/PyTorch environment: **196 passed** in 39.79 seconds.

The system-Python skips are the expected Torch-dependent cases; they execute in the
Cortex environment. SQLite integrity/event-chain checks are included in recovery
scenarios. No live campaign or training work was started.

## Safety and remaining boundaries

Autonomous repair cannot change secrets, credentials, training authorization, external
provider policy, protected paths, destructive artifact/checkpoint state, or exhausted
budget. Missing credentials, safety invariants, non-repairable task outcomes, and budget
exhaustion end in a machine-readable block/escalation. Repair cannot activate dirty
source, mismatched environment/configuration identities, or an unverifiable deployment.

Two limitations remain deliberate or operational:

1. The hardening snapshot and matching role releases must be activated through the
   normal commissioning path; the current live state is paused and predates this schema.
2. Arbitrary coordinator-logic defects that occur outside a job/run do not yet have a
   synthetic replay/health-check subject. They fail closed and require deployment-level
   supervision. Job producer/adapter, provider, transport, artifact-contract, dependency,
   and configuration incidents are inside the demonstrated autonomous boundary.

## Readiness assessment

The checked-out release demonstrates self-recovery for multiple distinct bounded defect
classes and prevents prose-only or malformed evidence from claiming success. It is ready
for controlled release commissioning. It is not evidence that the currently installed
live release has these capabilities until configuration migration, role installation,
activation, daemon restart, and a post-deployment healthcheck are completed.

The final live read-only audit found SQLite integrity `ok`, a valid 12,285-event chain,
no live runs, and no recovery incidents/blocks. It also found the control state
`running/running`, Campaign 35 active, 97 queued jobs, 96 active visual workflows, and one
active Cortex workflow. The active configuration (`3f18c095...`) differs from this
checkout (`7e64ec34...`), and both active role deployments are stale relative to the
checkout. Accordingly backend, commissioning, execution-path, and training-restart
readiness are false. No queued work was dispatched, cancelled, or altered during this
audit. Running the status check advanced the additive database schema marker from 14 to
17 and created only the empty recovery/block tables and thread-link column; configuration,
deployments, campaigns, jobs, and pipeline control were not activated or rewritten.
