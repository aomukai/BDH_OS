# Pipeline hardening audit — 2026-08-09

## Disposition

Mission Hub and the trainbox control plane were audited, changed, tested, deployed, and
exercised against live persisted state. This was not a static review. The final release
uses schema 18 and configuration
`550af3a8ee6f9437ab0d924f12f10cd76583605f5e976f5c70cbb118c1424646` (62 documents,
34 job definitions). Backend, commissioning, and execution-path readiness pass.
Training-restart readiness intentionally remains false because no configured training
campaign, certified campaign baseline, or authorized Cortex workflow currently exists.

## Architectural failures found and repaired

- On-call could describe a deterministic defect but had no executable repair, test,
  deployment, retry, or closure loop. A contradictory `no_action` response could be
  accepted. Recovery is now an explicit, budgeted state machine backed by authoritative
  incidents, attempts, actions, blockers, verification, and campaign-block records.
- A terminal job required a newer deployment before retry, while the recovery actor had
  no way to create that deployment. The repair driver can now produce a bounded source
  patch, capture test evidence, install an exact content-addressed release, and create a
  verified successor run. Operator cancellation and exhausted budgets close explicitly.
- Natural-language operational threads acted as practical authority. Threads are now a
  projection of hashed structured records. Prose alone cannot close an incident.
- Output declarations were validated too late. Typed construction and commit-time
  cardinality/type/hash validation now reject missing, duplicate, wrong, extra, corrupt,
  partial, empty, truncated, and invalid structured outputs while preserving evidence.
- Provider, transport, configuration, dependency, checkpoint, contract, and internal
  failures collapsed into coarse categories. Specific codes now drive retry, fallback,
  bounded repair, rollback, terminal rejection, or human blocking behavior.
- Configuration snapshots were not independently reconstructible and deployment
  rollback was not tied atomically to retained role releases. Complete snapshots and
  exact role/config/source identities are now required for activation and rollback.
- Failed successor work could leave a stale campaign block. Blocks now resolve only
  after the repaired successor and its artifacts verify; merely queuing a retry is not
  sufficient. Reconciliation reopens visual/Cortex workflow state without deleting the
  immutable failed run.
- Machine names, provider assumptions, endpoints, paths, and deployment details leaked
  into workflow logic. Generic workflows now use typed configuration, registries, role
  capabilities, and deployment manifests. Campaign 35 identifiers remain only in its
  explicitly campaign-specific recipe and UI projection.

## Task simplification and bounded loops

Every configured job was classified in
[`task_granularity_audit_2026-08-09.md`](task_granularity_audit_2026-08-09.md). The rule
is that repeated production is one durable item per job; only decisions that require
joint evidence and stateful optimizer execution remain whole.

- Visual work is now `generate/NNNN -> inspect/NNNN -> decide/NNNN`, with caption and
  feature encoding also performed per accepted candidate. Finalizers deterministically
  prove exact coverage, uniqueness, immutable order, artifact type, and content hash.
- Material generation persists one bounded `unit/NNNNNN` at a time and assembles only
  verified units in deterministic order. A restart cannot duplicate a completed unit.
- Provider output count is bounded and checked before artifact commit. Canonical unit
  input is limited to 64 KiB and repeated lists are bounded by configured limits.
- Training preparation and material creation are decomposed. The optimizer trajectory
  remains one stateful session because arbitrary chunking would change the experiment;
  failure replays from the immutable parent checkpoint.
- Campaign decisions and current evaluation comparisons remain bounded whole-evidence
  tasks. They are not bulk content-generation prompts. If evaluation fixtures grow past
  the audited bound, case inference should fan out while the deterministic whole-suite
  comparator remains joint.

Nineteen live legacy visual workflows were migrated at a paused, idle boundary. Sixteen
never-started batch-frontier jobs were cancelled with an explicit supersession reason;
completed batch artifacts and failed evidence were retained. Workflows with valid
generation evidence resumed at per-candidate inspection, while workflows without it
resumed at per-candidate generation. No queued legacy generation, inspection, or caption
batch remains.

Live proof after restart: three per-candidate inspections and three per-candidate
generations completed consecutively. Inspect inputs were 317 bytes, generation inputs
357 bytes, and individual executions took approximately 11–25 seconds. The scheduler
advanced to new small cursors after each success. A failure now loses one candidate,
not an hour-long batch.

## Recovery architecture and evidence

Failure capture and incident creation are transactional with run completion. Each repair
attempt preserves its immutable input evidence, actions, source patch identity, files and
hashes, targeted and regression test transcripts, deployment identity before and after,
reload receipt, retry/successor identity, artifact validation, downstream health, and
closure result. Claims are cross-checked against bytes, database rows, active deployment
state, and run/artifact records. Contradictory summaries fail schema validation.

The bounded loop is:

1. classify and preserve the failed run and output;
2. check category-specific permission and safety boundaries;
3. inspect and patch only configured source/configuration roots;
4. run targeted and regression validation;
5. install and activate an exact content-addressed role release;
6. reload the component and retry immutable work;
7. verify output artifacts, workflow/campaign continuation, and health;
8. close only with structured proof, otherwise iterate within budget or record a
   machine-readable blocker.

Transient provider and transport faults retry or fall back without source mutation.
Configuration faults retain or atomically restore a complete known-good snapshot and
matching deployments. Failed repair attempts remain evidence and consume the configured
budget.

## Tests and adversarial simulations

Final source test results:

- system environment: **200 passed, 9 skipped in 41.60 seconds**;
- Cortex/PyTorch environment: **222 passed in 44.73 seconds**;
- focused migration, recovery, and fault suite: **41 passed in 9.67 seconds**.

The suites cover deterministic producer repair through deployment/retry/unblock;
transient provider outage, timeout, and fallback without mutation; invalid configuration
rollback; failed first repair followed by a successful bounded attempt; fresh-store and
fresh-coordinator continuation; false repair/test/deployment claims; all required output
cardinality/type/corruption cases; disk, SSH, trainbox, stale deployment, checkpoint,
dependency, and runtime failures; process interruption at artifact/state boundaries;
lease expiry, stale workers, duplicate delivery, scheduler/Mission Hub/worker restart;
partial deployment receipts; cascading failure; and campaign block/recovery cycles.

Tests discovered and drove repairs for contradictory no-action conclusions, refused
actions reported as success, terminal retry dead ends, stale blocks, lost malformed
outputs, rollback identity gaps, coarse provider failures, cancelled retry ambiguity,
legacy batch migration gaps, duplicated work after restart, and feature-pack coverage and
ordering errors.

At the final live pre-release check SQLite integrity was `ok`, foreign-key and event-chain
validation passed, 13,740 events were present, no campaign block was active, and the only
non-recovered incident was an explicit `operator_cancelled` blocker. The pipeline was
`running/running`; legacy batch queues were empty.

## Safety boundaries and remaining limitations

Autonomous repair cannot change secrets, credentials, external provider policy, training
authorization, protected paths, immutable artifact/checkpoint evidence, destructive data
state, or budget ceilings. Missing authority or credentials, violated safety invariants,
non-repairable task outcomes, and exhausted budgets require a concrete blocker code.

Known non-autonomous or deliberate boundaries are:

1. The local Qwen route and generic model-generation job remain disabled until that
   provider is commissioned. The small-unit material workflow is implemented and tested,
   so enabling it will not reintroduce a monolithic prompt.
2. Stateful training restarts from an immutable parent checkpoint instead of resuming an
   unverified partial optimizer state.
3. A visual item with no usable candidate and a request for genuinely new research
   material or training authorization remain human/research-policy decisions.
4. Arbitrary coordinator defects outside a job/run fail closed and still require
   deployment-level supervision; ordinary producer, adapter, provider, transport,
   artifact-contract, dependency, and configuration failures are inside the demonstrated
   recovery boundary.
5. Disabled legacy job definitions remain as migration/compatibility stubs. Release
   validation prevents them from being used as active repetitive paths.

## Readiness assessment

The system now demonstrates machine-verifiable self-recovery across multiple bounded
software, configuration, provider, transport, and contract failures. It survives fresh
process/model context using persisted configuration snapshots, workflows, run state,
artifacts, lineage, events, incidents, actions, and deployment identities. Repetitive
work is restart-safe and cursor-based, while irreducible reasoning steps receive compact
validated evidence.

The control plane is hardened for continued research production. This does not grant
unbounded autonomy and does not claim that every possible defect is self-repairable; the
remaining boundaries above are explicit, machine-readable, and fail closed.
