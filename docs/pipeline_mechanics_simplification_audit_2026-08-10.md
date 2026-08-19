# Pipeline mechanics simplification audit

Date: 2026-08-10

## Plain-English conclusion

The pipeline is generally careful about preserving work and refusing unsafe actions, but several mechanisms represent the same fact in different ways. Those copies can disagree. The M1 evaluation failure was one example: the job had not run, yet it was represented as a failed workflow; it had no recovery incident because incidents require a failed run; and its old configuration made it invisible to the dispatcher until a generic timer blocked it.

The best next step is not to add more instructions to Sol. It is to give the system fewer, clearer states and give Sol structured facts plus narrowly defined actions. Human messages should explain those facts, not carry machine commands.

## What was inspected

This pass traced configuration activation, job creation and leasing, queue expiry, machine dispatch, workflow coordinators, recovery incidents and attempts, campaign blocks, operational threads, Sol's responder, deployment identity, and the relevant tests and architecture documentation.

| Mechanic | Current authority | Main issue found |
| --- | --- | --- |
| Configuration | config snapshots and active deployments | activating a new snapshot can strand untouched queued jobs silently |
| Queueing | `jobs` plus lease-time filters | one generic timer covers several very different reasons a job cannot run |
| Dispatch | one daemon tick with per-machine futures | the tick still waits for its longest job before beginning another tick |
| Workflow state | separate visual, material, and Cortex coordinators | `blocked`, `failed`, and `cancelled` are translated differently |
| Recovery | run-backed incidents plus workflow-specific reopen methods | failures before a run do not fit the incident model |
| Campaign containment | campaign blocks plus workflow checks | held jobs keep aging while intentionally blocked |
| On-call | operational jobs and structured output | input facts are extracted from human prose with regular expressions |
| Operator messages | threads | every system notice invokes Sol, including informational notices |
| Deployment | role manifest and Git metadata | unrelated commits change role identity and can force needless redeployment |

## Highest-priority contradictions

### 1. Human prose is also a machine protocol

The architecture says an operational thread is a projection and never recovery authority. In practice, the on-call handler searches message text for lines such as `Job:` and `Recovery incident:` and uses those matches to approve or reject actions. Editing a message to make it clearer for a person can therefore change machine behavior.

Simplification: store an authoritative structured notice context with the operational response: notice kind, job ID, workflow ID, incident ID, state, failure code, and allowed actions. Give that object to Sol. Render a separate plain-English message from the same facts. Remove all identity and state parsing from message text.

### 2. Pre-run failures do not fit recovery

Recovery incidents require a `failed_run_id`. Queue expiry, stale configuration authorization, unavailable deployment, and some scheduler failures happen before a run exists. They therefore bypass the normal incident lifecycle and need special workflow-specific reopening methods.

Simplification: allow a recovery incident to originate from either a job or a run, with an explicit origin such as `dispatch`, `execution`, or `coordination`. A run ID should be optional for pre-run incidents. One incident model can then explain, contain, retry, and verify both kinds of failure.

### 3. Configuration changes can silently strand queued work

A queued job is tied to one exact configuration snapshot. This is a sound safety property. However, activating a replacement snapshot makes the old job ineligible without changing its visible `queued` state or immediately creating an incident. It can sit untouched until the queue timer blocks it. This was the direct cause of the M1 event.

Simplification: during configuration activation, atomically classify every untouched queued job. Revalidate and reauthorize it when its input and job definition are unchanged; otherwise place it immediately into a visible `needs_reauthorization` incident with the exact difference. Never leave an ineligible job looking normally queued.

### 4. Machine lanes were parallel only within one blocking tick

Per-machine dispatch was concurrent, so one machine no longer started only after another finished, but the daemon still waited for all machine futures before beginning its next tick. A long trainbox training run could therefore delay subsequent Mission Hub jobs, including on-call work, until training finished. Synchronous recovery work could also delay dispatch because it ran earlier in the same tick.

This pass gives each machine a persistent lease-and-execute loop and keeps coordination in a separate loop. Each machine now polls independently after its own job finishes. Slow repair work should still move out of the coordinator loop and execute as a job.

On-call work is also ordered ahead of equal-priority ordinary work. The next step is explicit, bounded preemption based on reversibility rather than a fixed list of job types. Sol should decide whether stopping current work helps recovery. The control plane should then verify that the exact input and dependencies are preserved, repetition is authorized, no unique evidence would be lost, and the interrupted process can be stopped cleanly. If those facts hold, it should cancel, preserve the partial attempt as evidence, queue the same work again, and let on-call proceed. A dedicated training run may therefore continue when it is useful, but it is not categorically immune from preemption when its work is safely reproducible.

This preserves the useful division of responsibility: Sol exercises judgment about priority and operational value; deterministic checks prevent an incorrect judgment from destroying something irrecoverable. The eventual action should be named explicitly, for example `preempt_and_repeat`, and its result should explain what was stopped, why it was repeatable, and what was requeued.

## Important simplifications

### Unify resume and retry

There are separate methods for failed Cortex retry, workflow restart, queued-stage reauthorization, queue-expiry recovery, repaired-job retry, and corresponding visual cases. Each encodes a slightly different subset of the same safety checks.

Replace these with one transition service driven by evidence:

- `resume_untouched`: no run exists, input hash is unchanged, and the active definition still accepts it.
- `retry_transient`: a run exists, policy permits another identical attempt, and budget remains.
- `retry_repaired`: a verified repair and newer deployment exist.
- `supersede`: intent or immutable input changed, so create a new job and preserve the old one.

Workflow coordinators should ask for one of these transitions rather than reopen their own state independently.

### Give terminal states one meaning

Today a blocked job may make a Cortex workflow `failed`, a material workflow `blocked`, and a visual workflow `failed`. Recovery incidents also have `blocked` and `escalated`, while campaigns have separate active blocks.

Use three concepts consistently:

- `failed`: an execution produced terminal failure evidence.
- `held`: execution is intentionally prevented pending a condition.
- `cancelled`: authorized work was deliberately abandoned or superseded.

Keep the cause as a typed reason instead of adding more status words. Derive workflow and campaign presentation from the authoritative job or incident state.

### Make queue time explicit

The queue timer used the general `updated_at` field, which can change for reasons unrelated to waiting. This pass corrected the immediate bug where deliberate `available_at` cooldown counted toward queue age. A later schema migration should add `eligible_at` and `queue_wait_started_at`. Campaign holds and maintenance should either pause that clock or move jobs into an explicit held state.

### Do not invoke Sol for every notice

Every system-originated message currently creates an on-call response unless it was written by the on-call actor itself. Informational completion messages therefore consume the same mechanism as actionable failures.

Add a notice purpose such as `informational`, `assessment_requested`, or `recovery_required`. Only the latter two should enqueue Sol. This reduces load and makes an on-call request meaningful.

### Make on-call actions say what they do

`allow_automatic_recovery` originally meant that no state change was requested. It now also reauthorizes and requeues a terminal Cortex job. That is too much hidden meaning for one action.

Replace it with explicit actions such as `observe_existing_recovery` and `resume_untouched_job`. The action validator should compare these against the structured notice context, not prose.

### Narrow deployment identity

Role manifests include Git HEAD and branch in their content hash. As a result, a Mission Hub-only commit can change the trainbox release identity even when every trainbox file is byte-for-byte unchanged. The trainbox package also starts with most of `mission_hub` and removes files through a long exclusion list.

Keep Git revision as audit evidence, but base executable compatibility on the role's included file hashes and configuration. Replace the trainbox include-all/exclude-many pattern with an allowlist of the agent modules it actually runs.

## Corrections made during this pass

1. When Sol's own response job fails, Mission Hub now posts a short explanation of what failed, states that no pipeline change was made, and includes the response run and failure code when available.
2. That failure is no longer falsely labeled `operator_required`; only a real human-only authority boundary may use that disposition.
3. Queue expiry now starts no earlier than a job's deliberate availability time, so cooldown does not consume the waiting allowance.
4. The contradictory `--allow-dirty-active` option was removed. Dirty source may be recorded as a candidate but cannot become active.

## Recommended sequence

1. Add structured operational notice context and split `observe_existing_recovery` from `resume_untouched_job`.
2. Generalize recovery incidents to cover pre-run control-plane failures.
3. Reconcile queued jobs atomically on configuration activation.
4. Add Sol-directed, deterministically verified `preempt_and_repeat` and move repair execution to an asynchronous lane.
5. Normalize terminal-state semantics and consolidate workflow-specific resume/retry methods.
6. Narrow notice triggering and deployment role manifests.

Each change should include migration tests for existing database rows and a replay test for the M1 scenario: completed training, untouched evaluation, configuration activation, cooldown, dispatch, recovery, and human-facing explanation.
