# Ninereeds Lab Operations Audit and Rebuild Plan

**Purpose:** Audit the current lab, divide it cleanly into Mission Control and Training Environment, replace most roles with configurable jobs, remove uncontrolled duplication, and make failures, messaging, prompts, retries, schedules, and budgets visible and editable.

This document is designed as a working form for **Sol** to complete and for the human operator to review.

---

# 0. Audit rules

- Do not fix components during the first audit unless required to continue safely.
- Do not delete ambiguous files, services, or state.
- Record current behavior separately from intended behavior.
- Mark assumptions and unknowns explicitly.
- Every active component must eventually have exactly one authoritative owner.
- Treat source code, configuration, runtime state, logs, datasets, checkpoints, and artifacts as separate classes.
- Every automated path must end in a validated result, a structured failure, an escalation, or a deliberate stop.
- Every important decision must be reconstructable afterward.

## Audit metadata

| Field | Value |
|---|---|
| Audit ID | |
| Started | |
| Completed | |
| Auditor | Sol |
| Human reviewer | |
| Workstation hostname | |
| Training-box hostname | |
| Repository path on workstation | |
| Repository path on Ninereeds box | |
| Workstation branch and commit | |
| Ninereeds branch and commit | |
| Audit status | Not started / In progress / Blocked / Complete |

---

# 1. Target architecture

```text
                           HUMAN
                             │
                             ▼
                  ┌─────────────────────┐
                  │   MISSION CONTROL   │
                  │                     │
                  │  Lab UI             │
                  │  Sol                │
                  │  Job Registry       │
                  │  Scheduler          │
                  │  Threads            │
                  │  Prompt Editor      │
                  │  Policies           │
                  │  Budgets            │
                  │  Model Routing      │
                  │  Audit / History    │
                  └──────────┬──────────┘
                             │
                    Versioned job protocol
                             │
                             ▼
                  ┌─────────────────────┐
                  │ TRAINING ENVIRONMENT│
                  │                     │
                  │  Job Receiver       │
                  │  Workers            │
                  │  Trainers           │
                  │  Evaluators         │
                  │  Local Models       │
                  │  Datasets           │
                  │  Checkpoints        │
                  │  Artifacts          │
                  │  Telemetry          │
                  └──────────┬──────────┘
                             │
                   Events, results, failures
                             │
                             └──────────► Mission Control threads
```

## Durable entities

- Machine
- Job
- Run
- Thread
- Message
- Artifact
- Prompt
- Provider
- Model
- Policy
- Failure
- Budget
- Schedule
- Configuration version

## Architecture decisions

| Decision | Proposed answer | Final answer | Notes |
|---|---|---|---|
| One canonical repository | Yes | | |
| Separate deployment targets | Yes | | |
| Independent development branches per machine | Prefer no | | |
| Optional generated deployment branches | Yes | | |
| Mission Control owns strategy and scheduling | Yes | | |
| Training box owns execution and machine-local state | Yes | | |
| Sol remains a persistent role | Yes | | |
| Other roles become jobs | Usually | | |
| Threads replace inbox/outbox | Yes | | |
| Prompts are editable and versioned | Yes | | |
| Configuration supports rollback | Yes | | |
| Every run stores exact prompt/config versions | Yes | | |

---

# 2. Repository and filesystem audit

## 2.1 Repository inventory

Fill one row for every repository, worktree, checkout, or copied source tree.

| ID | Machine | Path | Git remote | Branch | Commit | Dirty? | Purpose | Canonical? | Action |
|---|---|---|---|---|---|---|---|---|---|
| REP-001 | | | | | | | | | |

Possible actions: keep as canonical, convert to deployment checkout, merge, archive, delete after verification, investigate.

## 2.2 Directory inventory

| ID | Machine | Path | Class | Intended owner | Source of truth | Synced? | Generated? | Backed up? | Action |
|---|---|---|---|---|---|---|---|---|---|
| DIR-001 | | | Source / Config / Runtime / Artifact / Dataset / Checkpoint / Log / Archive | | | | | | |

## 2.3 Duplicate audit

| Group | Copy A | Copy B | Identical? | Diverged? | Most recent | Current users | Canonical choice | Migration action |
|---|---|---|---|---|---|---|---|---|
| DUP-001 | | | | | | | | |

### Questions Sol must answer

- Which files exist on both machines?
- Which duplicates have diverged?
- Which duplicate copies are still imported or executed?
- Which files are generated but committed?
- Which runtime files are mistaken for configuration?
- Which paths are hard-coded?
- Which scripts copy files between machines?
- Which deployment steps are manual?
- Which obsolete implementations remain reachable by active code?
- Which state can be recreated safely?
- Which state must never be overwritten?

### Findings

```text
[Sol fills this section]
```

## 2.4 Proposed ownership manifest

```yaml
ownership:
  mission_control:
    - apps/mission_control/**
    - packages/jobs/**
    - packages/messaging/**
    - packages/providers/**
    - packages/policies/**
    - packages/schemas/**
    - config/shared/**
    - config/mission_control/**
    - prompts/**
    - deployments/workstation/**

  training_environment:
    - apps/training_node/**
    - training/**
    - evaluators/**
    - config/training_node/**
    - deployments/ninereeds/**

  machine_local_runtime:
    workstation:
      - runtime/mission_control/**
      - logs/mission_control/**
    ninereeds:
      - runtime/training_node/**
      - logs/training_node/**
      - checkpoints/**
      - datasets/local/**
      - artifacts/local/**

  generated:
    - reports/generated/**
    - caches/**
    - temporary/**

  archived:
    - archive/**
```

## 2.5 Ownership enforcement

- [ ] CI rejects files outside allowed ownership paths
- [ ] Deployment copies only owned files
- [ ] Startup validates the ownership manifest
- [ ] Runtime directories are excluded from Git
- [ ] Generated artifacts are immutable or versioned
- [ ] Duplicate detection runs automatically
- [ ] Configuration rejects ownership conflicts
- [ ] UI displays component owner
- [ ] Unowned components trigger a visible warning

---

# 3. Process and service audit

## 3.1 Active processes

| Process ID | Name | Machine | Started by | Trigger | Command | Working directory | Owner | Restart policy | Logs | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| PROC-001 | | | systemd / cron / shell / user / another process | | | | | | | |

## 3.2 Timers and schedulers

| Timer ID | Machine | Mechanism | Schedule | Target | Overlap allowed? | Missed-run behavior | Purpose | Keep? |
|---|---|---|---|---|---|---|---|---|
| TIMER-001 | | cron / systemd / internal / manual | | | | | | |

## 3.3 Questions

- What starts each process?
- Which process supervises it?
- Can two processes start the same work simultaneously?
- Does it use a lock or idempotency key?
- What happens after reboot?
- Can it resume partial work?
- Where is its state stored?
- How is completion detected?
- How is failure detected?
- Who receives failure information?
- Is stopping it safe?
- Does stopping it leave ambiguous or corrupt state?

## 3.4 Hazards

| Hazard ID | Description | Severity | Evidence | Affected components | Immediate containment | Long-term fix |
|---|---|---|---|---|---|---|
| HAZ-001 | | Low / Medium / High / Critical | | | | |

---

# 4. Workflow audit

Create one copy of this section for every active workflow.

## Workflow template

| Field | Value |
|---|---|
| Workflow ID | |
| Name | |
| Purpose | |
| Current owner | |
| Intended owner | |
| Importance | Low / Medium / High / Critical |
| Trigger | |
| Frequency | |
| Current status | |

### Current control flow

```text
trigger
  →
  →
  →
result or failure
```

### Inputs

| Input | Source | Format | Required? | Validation | Owner |
|---|---|---|---|---|---|
| | | | | | |

### Outputs

| Output | Destination | Format | Immutable? | Validation | Retention |
|---|---|---|---|---|---|
| | | | | | |

### Models and providers

| Stage | Provider | Model | Why selected | Fallback | Local possible? |
|---|---|---|---|---|---|
| | | | | | |

### State and recovery

- Job state location:
- Partial-result location:
- Resume mechanism:
- Duplicate prevention:
- Reboot behavior:
- Cancellation behavior:
- Timeout behavior:
- Cleanup behavior:

### Current failure paths

| Stage | Failure | Current behavior | Understandable? | Safe? | Desired behavior |
|---|---|---|---|---|---|
| | | | | | |

### Migration decision

- [ ] Keep workflow structure
- [ ] Convert to one job
- [ ] Split into multiple jobs
- [ ] Merge with another workflow
- [ ] Replace
- [ ] Archive
- [ ] Remove

---

# 5. Roles and prompts

## 5.1 Current role inventory

Include named roles and hidden roles embedded in code.

| Role ID | Name | Persistent identity? | Provider | Model | Prompt location | Tools | Authority | Proposed disposition |
|---|---|---|---|---|---|---|---|---|
| ROLE-001 | Sol | Yes | OpenAI | | | | Lab manager | Keep as role |
| ROLE-002 | | | | | | | | Convert to job / Keep / Remove |

## 5.2 Role-to-job rule

A component should usually become a job when it has one bounded purpose, clear inputs and outputs, can be validated, and can be executed by interchangeable workers.

A component may remain a role when it has persistent authority, ongoing context, cross-job responsibility, or represents a stable participant in threads.

## 5.3 Prompt inventory

| Prompt ID | Name | Role/job | Location | Editable? | Versioned? | Variables | Output schema | Last successful version | Action |
|---|---|---|---|---|---|---|---|---|---|
| PROMPT-001 | | | | | | | | | |

## 5.4 Prompt checklist

- [ ] Stable ID
- [ ] Human-readable name
- [ ] Description
- [ ] Version
- [ ] Owner
- [ ] Associated role/job
- [ ] Required variables
- [ ] System section
- [ ] Task template
- [ ] Tool permissions
- [ ] Output contract
- [ ] Failure behavior
- [ ] Test examples
- [ ] Known failure examples
- [ ] Draft/active state
- [ ] Change history
- [ ] Rollback target
- [ ] Exact version recorded for every run

---

# 6. Job system

## 6.1 Job definition template

```yaml
id: JOB_ID
version: 1
name: Human-readable name
description: >
  One bounded responsibility.

owner:
  environment: mission_control | training_environment
  machine: workstation | ninereeds

enabled: true
priority: normal

trigger:
  type: manual | schedule | dependency | event | thread_action
  schedule_id: null
  dependency_job_ids: []
  event_types: []

inputs:
  schema: schemas/jobs/JOB_ID/input.schema.json
  artifacts: []
  parameters: {}

outputs:
  schema: schemas/jobs/JOB_ID/output.schema.json
  artifact_types: []
  create_thread_message: true

executor:
  primary:
    provider: PROVIDER_ID
    model: MODEL_ID
  fallback:
    provider: PROVIDER_ID
    model: MODEL_ID
  local_fallback: null

prompt:
  system_prompt_id: PROMPT_ID
  task_prompt_id: PROMPT_ID
  version_policy: pinned | active

tools:
  allowed: []
  denied: []

limits:
  execution_attempts: 2
  repair_attempts_per_execution: 1
  validation_retries: 1
  timeout_seconds: 1800
  max_input_tokens: null
  max_output_tokens: null
  max_cost_usd: null

validation:
  schema_required: true
  validators: []
  commands: []

retry_policy:
  operational_failures: retry
  task_failures: repair_then_retry
  capability_failures: escalate
  delay_seconds: 30
  backoff: fixed | exponential

escalation:
  first_target: strategist | lab_manager | human
  max_strategist_escalations: 0
  max_lab_manager_invocations: 1
  human_required_after_exhaustion: true
  immediate_human_conditions: []

budget:
  budget_policy_id: BUDGET_POLICY_ID

retention:
  logs_days: 30
  artifacts_days: null
  keep_failed_outputs: true
  keep_prompt_and_config_snapshot: true
```

## 6.2 Job inventory

| Job ID | Name | Owner | Trigger | Primary model | Fallback | Attempts | Validation | Escalation | Status |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |

## 6.3 Job conversion queue

| Priority | Current role/workflow | Target job(s) | Dependencies | Risk | Shadow run? | Owner |
|---|---|---|---|---|---|---|
| | | | | | | |

---

# 7. Provider and model registry

## 7.1 Providers

| Provider ID | Provider | Endpoint | Credential reference | Available? | Rate limit | Billing | Notes |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## 7.2 Models

| Model ID | Provider | Exact model name | Local/remote | Context | Output limit | Tool use | Structured output | Cost | Preferred jobs | Fallback |
|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | |

## 7.3 Capability assessment

Use actual lab evidence rather than reputation.

| Model ID | Planning | Coding | Repair | Diagnosis | Data generation | Schema compliance | Latency | Reliability | Cost efficiency | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| | Low/Med/High | | | | | | | | | |

---

# 8. Failure taxonomy and reporting

## 8.1 Failure classes

### Operational failure

Provider timeout, rate limit, machine offline, process crash, filesystem error, missing dependency, lock contention, network failure, disk pressure, GPU OOM.

Default: retry only when safe and policy permits.

### Task failure

Invalid schema, failed tests, incomplete artifact, threshold not met, output rejected by validator.

Default: bounded repair or retry.

### Capability failure

Repeated invalid solutions, inability to follow the contract, no improvement after repair, insufficient context/tools, or repeated strategist failure.

Default: stop automated looping and escalate for reassignment, redesign, or human assessment.

## 8.2 Failure codes

| Code | Class | Title | Meaning | Safe state? | Retry default | Escalation default | Implemented? |
|---|---|---|---|---|---|---|---|
| PROVIDER_TIMEOUT | Operational | Provider timed out | | Yes | Yes | After retries | |
| MACHINE_OFFLINE | Operational | Machine unavailable | | Unknown | Yes | Sol | |
| VALIDATION_SCHEMA_MISMATCH | Task | Result format invalid | | Yes | Repair | Sol | |
| TESTS_FAILED | Task | Validation tests failed | | Depends | Repair | Sol | |
| CAPABILITY_EXHAUSTED | Capability | Worker could not complete task | | Yes | No | Sol/human | |
| BUDGET_EXCEEDED | Policy | Budget limit reached | | Yes | No | Human | |
| CHECKPOINT_CORRUPTION_RISK | Operational | Checkpoint may be unsafe | | Unknown | No | Immediate human | |

## 8.3 Every failure report must answer

- What was attempted?
- Which job and run failed?
- At which stage?
- What is the failure code?
- What is the plain-language explanation?
- What evidence supports it?
- What changed before failure?
- Is the state safe?
- Were partial artifacts produced?
- Can retry happen safely?
- How many attempts were used and remain?
- Was repair attempted?
- Is this operational, task-level, or capability-level?
- What action is recommended?
- Who decides next?
- Which thread contains the full history?

## 8.4 Failure event template

```json
{
  "event_version": 1,
  "event_id": "EVENT_ID",
  "timestamp": "ISO-8601",
  "job_id": "JOB_ID",
  "run_id": "RUN_ID",
  "thread_id": "THREAD_ID",
  "machine_id": "MACHINE_ID",
  "event": "failed",
  "failure_class": "operational | task | capability",
  "failure_code": "FAILURE_CODE",
  "title": "Human-readable title",
  "summary": "Clear explanation of what failed.",
  "stage": "execution | validation | repair | transfer | cleanup",
  "attempt": 1,
  "max_attempts": 2,
  "repair_attempts_used": 0,
  "state_safe": true,
  "changes_made": [],
  "partial_artifacts": [],
  "evidence_artifacts": [],
  "retry_safe": true,
  "recommended_next_action": "retry | repair | fallback | escalate_lab_manager | escalate_human | stop",
  "required_decision": null
}
```

---

# 9. Retry, repair, and escalation

## 9.1 Values to decide

| Setting | Default | Per-job override? |
|---|---|---|
| Maximum execution attempts | | Yes |
| Repair attempts per execution | | Yes |
| Validation retries | | Yes |
| Provider-level retries | | Yes |
| Maximum fallback models | | Yes |
| Maximum strategist attempts | | Yes |
| Maximum strategist calls to Sol | | Yes |
| Maximum Sol interventions before human | | Yes |
| Maximum total runtime | | Yes |
| Maximum total model cost | | Yes |
| Maximum automated thread depth | | Yes |
| Cooldown after repeated failure | | Yes |

## 9.2 Proposed defaults

```yaml
retry_policy:
  execution_attempts: 2
  repair_attempts_per_execution: 1
  validation_retries: 1
  provider_retries: 2
  retry_delay_seconds: 30
  backoff: exponential

escalation_policy:
  operational_failure_after_retries: lab_manager
  task_failure_after_repairs: fallback_then_lab_manager
  capability_failure: lab_manager
  strategist_lab_manager_calls: 2
  lab_manager_interventions_before_human: 2

  immediate_human_conditions:
    - data_loss_risk
    - checkpoint_corruption_risk
    - unexpected_cost_overrun
    - security_boundary_violation
    - conflicting_ownership
    - repeated_capability_failure
    - destructive_action_required
```

## 9.3 Escalation ladder

```text
Worker attempt
  → validation
  → bounded repair
  → bounded retry
  → fallback worker/model
  → strategist assessment
  → Sol assessment
  → human capability or policy decision
```

## 9.4 Loop prevention

- [ ] Counters are stored durably
- [ ] Every retry has an idempotency key
- [ ] Total attempts remain capped across restarts
- [ ] Repeated identical failures are detected
- [ ] Capability failure stops automatic retries
- [ ] Sol cannot recursively invoke itself
- [ ] A thread records every transition
- [ ] Human escalation contains a concise summary
- [ ] Budget exhaustion overrides retry policy
- [ ] Unsafe state overrides fallback policy

---

# 10. Mission Control environment

## Responsibilities

Mission Control owns the lab UI, Sol, job registry, scheduler, provider/model registry, prompts, retry/escalation policies, budgets, threads, approvals, machine overview, deployment controls, audit history, and configuration versions.

It must not claim remote success until the Training Environment returns a validated result.

## Component inventory

| Component | Current implementation | Target implementation | Data store | Dependencies | Migration status |
|---|---|---|---|---|---|
| Lab UI | | | | | |
| Sol | | | | | |
| Job registry | | | | | |
| Scheduler | | | | | |
| Threads | | | | | |
| Prompt editor | | | | | |
| Provider/model registry | | | | | |
| Budget manager | | | | | |
| Configuration manager | | | | | |
| Machine monitor | | | | | |
| Deployment controls | | | | | |

## Proposed repository layout

```text
apps/
  mission_control/
    api/
    ui/
    scheduler/
    lab_manager/
    thread_service/
    budget_service/
    config_service/
    machine_service/

packages/
  jobs/
  messaging/
  providers/
  policies/
  schemas/
  observability/

config/
  shared/
  mission_control/

prompts/
  sol/
  jobs/

deployments/
  workstation/
```

## Acceptance criteria

- [ ] Human can see all active and recent jobs
- [ ] Exact provider/model is visible
- [ ] Job configuration is editable
- [ ] Prompts are editable
- [ ] Prompt/config history is visible
- [ ] Rollback exists
- [ ] Jobs can be paused or disabled
- [ ] Models/providers can be disabled
- [ ] Budgets are visible
- [ ] Unresolved threads are visible
- [ ] “Open with Sol” works
- [ ] Failures are understandable without raw logs
- [ ] Raw logs remain available as evidence
- [ ] Machine status is visible
- [ ] Configuration is validated before activation

---

# 11. Training Environment

## Responsibilities

The Ninereeds box owns job reception, execution, training, evaluation, datasets, checkpoints, local models, GPU-aware scheduling, machine-local artifacts, telemetry, validation, resume, and recovery.

It must not own strategic planning, global schedules, global budgets, canonical prompts, cross-machine orchestration, or human-facing conversation state.

## Component inventory

| Component | Current implementation | Target implementation | Owner | Inputs | Outputs | Migration status |
|---|---|---|---|---|---|---|
| Job receiver | | | | | | |
| Worker supervisor | | | | | | |
| Trainer | | | | | | |
| Evaluator | | | | | | |
| Local model server | | | | | | |
| Dataset manager | | | | | | |
| Checkpoint manager | | | | | | |
| Artifact manager | | | | | | |
| Telemetry agent | | | | | | |
| Recovery service | | | | | | |

## Proposed layout

```text
apps/
  training_node/
    receiver/
    supervisor/
    telemetry/
    recovery/

training/
  trainers/
  curricula/
  pipelines/

evaluators/

config/
  shared/
  training_node/

deployments/
  ninereeds/
```

Machine-local rather than canonical source:

```text
datasets/
checkpoints/
artifacts/
runtime/
logs/
local_models/
caches/
```

## Acceptance criteria

- [ ] Receives versioned job requests
- [ ] Rejects unsupported versions clearly
- [ ] Validates inputs before execution
- [ ] Prevents duplicate execution
- [ ] Reports progress events
- [ ] Reports structured failures
- [ ] Records machine/GPU telemetry
- [ ] Resumes supported jobs safely
- [ ] Cancels jobs safely
- [ ] Preserves partial artifacts when required
- [ ] Cannot edit canonical Mission Control configuration
- [ ] Cannot make global scheduling decisions
- [ ] Returns only validated results
- [ ] Reports disk, memory, and temperature hazards
- [ ] Survives reboot without losing job history

---

# 12. Machine-to-machine protocol

## Requirements

- Versioned
- Authenticated
- Idempotent
- Replay-safe
- Durable
- Observable
- Schema-validated
- Supports artifact references
- Distinguishes acknowledgement, progress, completion, and failure
- Recovers after either machine restarts

## Job request example

```json
{
  "protocol_version": 1,
  "job_id": "job-20260804-0042",
  "job_version": 3,
  "job_type": "bootstrap_evaluation",
  "run_id": "run-20260804-0042-01",
  "thread_id": "thread-0192",
  "requested_by": "sol",
  "target_machine": "ninereeds",
  "parameters": {},
  "input_artifacts": [],
  "policy_id": "evaluation-standard-v2",
  "prompt_versions": {},
  "config_snapshot_id": "config-0142",
  "idempotency_key": "job-20260804-0042-run-01"
}
```

## Event types

| Event | Meaning |
|---|---|
| accepted | Training node accepted responsibility |
| rejected | Request invalid or unsupported |
| queued | Waiting for resources |
| started | Execution began |
| progress | Structured progress update |
| validation_started | Validation began |
| repair_started | Bounded repair began |
| retrying | Another attempt will begin |
| fallback_selected | Fallback chosen |
| completed | Validated result available |
| failed | Terminal structured failure |
| cancelled | Cancelled safely |
| paused | Paused |
| resumed | Resumed |
| artifact_created | Artifact registered |
| heartbeat | Run and machine health update |

## Decisions

| Question | Decision |
|---|---|
| Transport | |
| Authentication | |
| Queue implementation | |
| Artifact transfer method | |
| Maximum message size | |
| Offline buffering | |
| Retry interval | |
| Event retention | |
| Clock synchronization | |
| Schema compatibility policy | |

---

# 13. Threaded messaging

## Thread fields

| Field | Description |
|---|---|
| Thread ID | Stable identifier |
| Subject | Human-readable title |
| Type | Job / Failure / Decision / Discussion / Alert / Report |
| Status | Open / Waiting / Blocked / Resolved / Archived |
| Severity | Info / Low / Medium / High / Critical |
| Participants | Human, Sol, strategist, workers, system |
| Assignee | Responsible for next action |
| Related jobs/runs | IDs |
| Related machine | Machine ID |
| Related artifacts | Artifact IDs |
| Resolution | Structured outcome |

## Message fields

| Field | Description |
|---|---|
| Message ID | Stable identifier |
| Thread ID | Parent thread |
| Sender | Participant ID |
| Recipient scope | All or named participants |
| Reply-to | Parent message |
| Type | Human / Model / System / Event |
| Body | Human-readable content |
| Structured payload | Optional machine data |
| Attachments | Artifacts, logs, reports |
| Read state | Per participant |
| Action or decision requested | Optional |

## UI requirements

- [ ] Unread indicator on dashboard
- [ ] Severity indicator
- [ ] Click opens thread
- [ ] Messages reply to messages
- [ ] Threads link to other threads
- [ ] Jobs/runs visible in context
- [ ] Artifacts visible
- [ ] “Open with Sol” loads thread context
- [ ] Sol replies directly in thread
- [ ] Human can assign next action
- [ ] Human can resolve/reopen
- [ ] Automated events look distinct from conversation
- [ ] Search and filters
- [ ] Legacy inbox/outbox import

## Legacy migration

| Source | Count | Import strategy | Grouping rule | Preserve raw file? |
|---|---|---|---|---|
| | | | | |

---

# 14. Configuration system

## Principles

- Schema-validated
- Versioned
- Draft and active states separated
- Activation creates a snapshot
- Every run references its snapshot
- Rollback supported
- Secrets referenced, not stored in editable plain text
- Global defaults and per-job overrides distinguished
- Effective value and source visible in UI

Recommended precedence:

```text
safe built-in defaults
  < shared configuration
  < environment configuration
  < machine configuration
  < job configuration
  < approved run override
```

## Machine settings

- Machine ID and display name
- Environment type
- Hostname and paths
- GPUs, VRAM, CPU, RAM
- Available local models
- Maximum concurrent jobs
- Allowed job types
- Disk, memory, and temperature thresholds
- Heartbeat and offline thresholds
- Maintenance mode
- Auto-start and restart policy
- Artifact/log retention
- Backup policy

## Provider settings

- Provider ID
- Endpoint
- Credential reference
- Enabled/disabled
- Timeout
- Rate limit
- Retry count/backoff
- Billing mode
- Health state
- Provider budget
- Emergency-disable switch

## Model settings

- Model ID and exact name
- Provider
- Local/remote
- Context/output limits
- Tool and structured-output support
- Reasoning/sampling controls
- Timeout and concurrency
- Cost estimates
- Preferred/prohibited jobs
- Fallback
- Capability notes
- Availability and recent failure rate

## Job settings

- Enabled/disabled
- Owner and machine
- Trigger/schedule/priority
- Provider/model/fallback
- Prompt versions
- Tool permissions
- Input/output schemas
- Validators
- Execution/repair/validation attempts
- Timeout/token/cost limits
- Concurrency
- Artifact policy
- Failure routing
- Escalation policy
- Human approval requirements

## Scheduler settings

- Fixed schedules
- Dependency/event triggers
- Poll intervals
- Cooldowns and jitter
- Missed-run and catch-up behavior
- Overlap policy
- Quiet periods and pause windows
- Priority queues
- Per-machine/provider concurrency
- Maximum queue age
- Stale-job behavior

## Budget settings

Budgets should exist globally, per provider, per model, per job type, per run, and by day/week/month, with an emergency reserve.

```yaml
budget_thresholds:
  70:
    action: warn
  85:
    action: restrict_nonessential_jobs
  95:
    action: emergency_jobs_only
  100:
    action: stop_external_model_calls
```

| Setting | Value |
|---|---|
| Global monthly budget | |
| Global weekly budget | |
| Emergency reserve | |
| Warning threshold | |
| Restriction threshold | |
| Emergency-only threshold | |
| Hard stop threshold | |
| Human approval above per-run cost | |
| Essential job categories | |
| Nonessential job categories | |

## Prompt settings

- Prompt ID
- Name and description
- Associated role/job
- Version
- Draft/active state
- System and task sections
- Variables
- Tool instructions
- Output contract
- Test cases and failure examples
- Change notes and author
- Last successful version
- Rollback target

---

# 15. Observability

For every run, show:

- Job and run ID
- Owner and machine
- Trigger
- Start/end time and stage
- Provider/model
- Fallback transitions
- Prompt version
- Configuration snapshot
- Attempts and repairs
- Validation results
- Budget used
- Artifacts
- Warnings and failure code
- Related thread
- Final decision

## Machine telemetry

| Metric | Warning threshold | Critical threshold | Action |
|---|---|---|---|
| Disk free | | | |
| RAM usage | | | |
| GPU VRAM | | | |
| GPU temperature | | | |
| CPU temperature | | | |
| Load average | | | |
| Process heartbeat | | | |
| Queue age | | | |
| Artifact backlog | | | |

## Audit events

Record configuration activation/rollback, prompt/model/budget changes, job enable/disable, manual starts, cancellations, approvals, escalations, thread resolution/reopen, deployments, and ownership changes.

---

# 16. Security and destructive actions

| Action | Always approve? | Conditional approval? | Automatic allowed? |
|---|---|---|---|
| Delete checkpoint | | | |
| Delete dataset | | | |
| Delete artifact | | | |
| Rewrite Git history | | | |
| Force-push branch | | | |
| Change credentials | | | |
| Increase budget | | | |
| Deploy to both machines | | | |
| Stop active training | | | |
| Replace canonical config | | | |
| Remove legacy system | | | |
| Run unreviewed migration | | | |

## Safety checklist

- [ ] Destructive actions are explicit
- [ ] Dry-run mode exists
- [ ] Backups are verified before migration
- [ ] Checkpoints are immutable by default
- [ ] Dataset provenance is retained
- [ ] Credentials remain outside repository
- [ ] Logs do not expose secrets
- [ ] Remote commands are allowlisted
- [ ] Training worker cannot change global policy
- [ ] Mission Control cannot silently overwrite machine-local state
- [ ] Human approval is recorded in the thread

---

# 17. Migration phases

## Phase A: Freeze and audit

- [ ] Create audit snapshot
- [ ] Record Git state on both machines
- [ ] Record active services and timers
- [ ] Inventory repositories and directories
- [ ] Compare duplicates
- [ ] Inventory roles and prompts
- [ ] Inventory provider/model calls
- [ ] Inventory hard-coded limits
- [ ] Inventory message formats
- [ ] Inventory failure modes
- [ ] Verify critical backups

**Exit:** every active component is listed, every unknown is documented, and no ambiguous deletion occurred.

## Phase B: Define ownership

- [ ] Approve ownership manifest
- [ ] Assign every active component
- [ ] Separate source/config/runtime/artifacts
- [ ] Define canonical repository structure
- [ ] Define deployment method
- [ ] Define synchronization rules
- [ ] Add ownership validation
- [ ] Add duplicate detection

**Exit:** no active component is unowned or has two authoritative owners.

## Phase C: Define schemas

Create schemas for machines, jobs, runs, events, threads, messages, artifacts, failures, providers, models, prompts, retry policies, escalation policies, budgets, schedules, and configuration snapshots.

- [ ] Version schemas
- [ ] Add example payloads
- [ ] Add clear validation errors
- [ ] Define compatibility policy

## Phase D: Build one vertical job slice

| Field | Selection |
|---|---|
| Pilot workflow | |
| Why selected | |
| Risk | |
| Primary model | |
| Fallback | |
| Validation | |
| Escalation | |

- [ ] Convert workflow to job
- [ ] Add prompt versioning
- [ ] Add model routing
- [ ] Add validation
- [ ] Add retries and structured failures
- [ ] Add escalation to Sol
- [ ] Add thread creation
- [ ] Record all events
- [ ] Shadow-run against old path
- [ ] Human approves activation

## Phase E: Build machine boundary

- [ ] Mission Control submits job
- [ ] Training node accepts/rejects
- [ ] Progress events work
- [ ] Completion/failure works
- [ ] Disconnects are survivable
- [ ] Duplicate requests are safe
- [ ] Reboots are tested
- [ ] Cancellation is tested
- [ ] Artifact transfer is tested
- [ ] Failure thread is tested

## Phase F: Replace inbox/outbox with threads

- [ ] Implement thread/message schemas
- [ ] Import legacy messages
- [ ] Associate jobs and runs
- [ ] Add replies and thread links
- [ ] Add “Open with Sol”
- [ ] Add unread notifications
- [ ] Add resolution/reopen
- [ ] Add filters/search
- [ ] Retire old readers/writers

## Phase G: Add configuration UI

Editors:

- [ ] Jobs
- [ ] Prompts
- [ ] Providers/models
- [ ] Fallback routes
- [ ] Retries/repairs
- [ ] Escalations
- [ ] Timers/schedules
- [ ] Budgets
- [ ] Ownership
- [ ] Enable/disable controls
- [ ] Failure messages

Safety:

- [ ] Draft state
- [ ] Validation
- [ ] Diff preview
- [ ] Activation approval
- [ ] Snapshot creation
- [ ] Rollback

## Phase H: Migrate remaining workflows

```text
inventory
  → job definition
  → local tests
  → shadow run
  → compare
  → activate
  → monitor
  → retire old path
  → remove verified duplicates
```

| Order | Workflow | New job(s) | Shadow period | Activation criterion | Old path retired? |
|---|---|---|---|---|---|
| 1 | | | | | |

## Phase I: Cleanup and enforcement

- [ ] Remove verified dead code
- [ ] Remove verified duplicates
- [ ] Archive historical implementations
- [ ] Enforce ownership in CI
- [ ] Enforce config schemas
- [ ] Enforce failure contracts
- [ ] Test disaster recovery
- [ ] Document restore procedure
- [ ] Produce final architecture map
- [ ] Produce operator handbook

---

# 18. Findings summary

## Critical findings

| ID | Finding | Impact | Recommended action | Human decision? |
|---|---|---|---|---|
| | | | | |

## Duplicate summary

| Category | Count | Safe to remove | Needs review | Diverged |
|---|---|---|---|---|
| Source files | | | | |
| Config files | | | | |
| Runtime state | | | | |
| Prompts | | | | |
| Scripts | | | | |
| Artifacts | | | | |

## Ownership summary

| Owner | Components | Unresolved conflicts |
|---|---|---|
| Mission Control | | |
| Training Environment | | |
| Shared package | | |
| Generated/runtime | | |
| Archive | | |

## Highest-risk areas

1.
2.
3.
4.
5.

## Human decisions required

| ID | Question | Options | Sol recommendation | Human decision |
|---|---|---|---|---|
| DEC-001 | | | | |

---

# 19. Final acceptance checklist

## Repository and ownership

- [ ] One canonical source tree
- [ ] Explicit deployment targets
- [ ] Every component has one owner
- [ ] No uncontrolled duplicates
- [ ] Runtime state separated from source
- [ ] Generated files classified
- [ ] Ownership enforced

## Jobs and roles

- [ ] Sol is the persistent lab manager
- [ ] Replaceable workers are jobs
- [ ] Every job has explicit inputs/outputs
- [ ] Every job has primary provider/model
- [ ] Every job has fallback or deliberate no-fallback
- [ ] Every job has validation
- [ ] Retry and escalation limits exist
- [ ] Every run records prompt/config versions

## Failures

- [ ] Stable failure codes
- [ ] Human-readable explanations
- [ ] Safe-state declaration
- [ ] Evidence attached
- [ ] Capability failures stop loops
- [ ] Sol receives sufficient context
- [ ] Human escalation is actionable
- [ ] No terminal failure is only an exit code

## Messaging

- [ ] Inbox/outbox replaced
- [ ] Threads preserve context
- [ ] Participants can reply
- [ ] Jobs/runs/artifacts linked
- [ ] Sol works inside threads
- [ ] Unread notifications visible
- [ ] Resolve/reopen supported
- [ ] Legacy messages retained

## Configuration

- [ ] Prompts editable/versioned
- [ ] Jobs editable
- [ ] Model routes/fallbacks editable
- [ ] Retry/repair limits editable
- [ ] Escalation thresholds editable
- [ ] Timers/schedules editable
- [ ] Budgets editable
- [ ] Configuration validated
- [ ] Rollback supported

## Environments

- [ ] Mission Control owns coordination
- [ ] Training box owns execution
- [ ] Protocol is versioned/idempotent
- [ ] Reboots are safe
- [ ] Offline delivery handled
- [ ] Duplicate jobs prevented
- [ ] Artifact ownership clear
- [ ] Machine telemetry visible

---

# 20. Sol completion report

## Audit conclusion

```text
[Sol writes a concise overall assessment]
```

## Recommended target architecture

```text
[Sol records any changes from this proposal]
```

## Recommended implementation order

1.
2.
3.
4.
5.

## Work that should not begin yet

```text
[Dependencies, unresolved decisions, or unsafe work]
```

## Immediate safe cleanup

```text
[Only verified safe actions]
```

## Human decisions required before migration

```text
[Policy, budget, architecture, or destructive decisions]
```

## Estimated complexity

| Area | Complexity | Risk | Notes |
|---|---|---|---|
| Repository cleanup | | | |
| Mission Control | | | |
| Training Environment | | | |
| Job conversion | | | |
| Thread system | | | |
| Configuration UI | | | |
| Protocol | | | |
| Legacy migration | | | |

## Final recommendation

```text
[Sol writes the recommended next action]
```
