# The Lab

The Lab is a workstation-side observer for Ninereeds training artifacts.
It is intentionally outside the training pipeline.

## High-Level Architecture

The training machine owns generation:

- corpus generation
- training and evaluation
- MRI, Atlas, trace, report, and checkpoint generation
- artifact publication by `git push`

The Lab owns observation:

- periodic `git pull` on the workstation clone
- artifact discovery and indexing
- read-only live trainbox telemetry through the restricted SSH status command
- browser UI and PWA shell
- local message files for Inbox / Outbox provenance
- checkpoint publication for chat selection
- orchestrator chat requests through a remote API

The training machine never serves UI, answers chat, exposes APIs, or accepts SSH
operations from The Lab beyond the separately provisioned forced-command status
key. Artifact views always work from local files after Git sync. Live telemetry
is explicitly non-authoritative and cannot dispatch training or claim plans.

## Critical Review And Refinement

The first risk is accidental coupling through repository writes. Messages are
intended to be provenance files, but writing them into the same git worktree can
make `git pull` unsafe. The implementation therefore confines Lab writes to
`lab/messages/outbox`, `lab/state`, and `lab/published`, and the git pull service
uses `git pull --ff-only` with a short timeout. By default it skips automatic
pulls when unrelated local changes exist.

The second risk is artifact format churn. Current artifacts are spread across
`training/logs`, `training/corpus`, `runs`, `checkpoints`, and `chat/logs`, with
names such as `c17_ladder_1200_e4.md` and `c16_e5_redesign_current_atlas.html`.
The Lab does not assume a single canonical campaign folder. It indexes files by
generic artifact traits: extension, filename hints, campaign id, epoch id, mtime,
and optional metadata files. If later campaigns publish `metadata.json` folders,
those can be folded into the same interface without changing page code.

The third risk is resource creep. The Lab must not consume GPU or training
capacity. The initial server uses only standard-library Python, never imports
training modules, never loads checkpoints into GPU memory, and treats published
chat builds as file references. Real local Ninereeds inference should remain an
adapter behind `backend/chat`, with CPU-only and explicit opt-in safeguards.

The fourth risk is remote-orchestrator ambiguity. The orchestrator is modeled as
an HTTP API client and receives context assembled from local artifacts. If no
remote endpoint is configured, the Lab returns a clear disabled response instead
of starting a local process or connecting to the training machine.

## Backend Architecture

`backend/git`
: guarded fast-forward pull service and status reporting.

`backend/artifacts`
: repository scanner, artifact classifier, campaign grouping, timeline builder,
search index, and raw artifact serving.

`backend/chat`
: published-build registry and chat-mode adapters. The initial Ninereeds adapter
is a safe stub that references checkpoints without loading them.

`backend/orchestrator`
: remote API client. It builds compact artifact context and calls the configured
endpoint.

The control dashboard also reads sanitized state from the local autonomous campaign
controller: campaign status, current durable plan, boundary index, and budget usage.

`backend/notifications`
: in-process event hub with Server-Sent Events and a minimal WebSocket broadcast
endpoint for browsers.

`backend/messages`
: Durable Inbox / Outbox envelopes under `lab/messages`, with atomic receipts,
claims/leases, retry state, correlated replies, and a read-only provider worker. Codex is
primary; at a machine-readable hard Codex limit the same schema-bound request is retried
through Fugu. Provider-limit transitions also arrive here as idempotent system notices.

`backend/api`
: HTTP route handlers. Route handlers depend on service interfaces rather than
artifact path conventions.

## Frontend Architecture

The frontend is a static PWA:

- `dashboard`: current campaign, latest report/MRI/Atlas, bottleneck, latest
  decision, published build, running jobs
- `timeline`: expandable event feed from the artifact index
- `campaigns`: campaign list and same-campaign navigation
- `reports`: markdown rendering
- `atlas` and `mri`: iframe/raw serving of existing HTML visualizations
- `chat`: mode switch for Ninereeds checkpoint references and remote
  orchestrator calls
- `messages`: Inbox / Outbox
- `settings`: sync status, notification state, API configuration visibility

Mobile priority order is Timeline, Dashboard, Messages, Notifications, Chat,
MRI, then Atlas. The desktop layout exposes more panels at once, but the same
routes and components are used.

## Directory Layout

```text
lab/
  backend/
    api/
    artifacts/
    chat/
    git/
    messages/
    notifications/
    orchestrator/
    server.py
    config.py
    models.py
  frontend/
    dashboard/
    timeline/
    campaigns/
    reports/
    atlas/
    mri/
    chat/
    messages/
    settings/
    index.html
    app.js
    styles.css
    manifest.webmanifest
    service-worker.js
  messages/
    inbox/
    outbox/
  published/
  state/
```

## Artifact Interfaces

```text
Artifact
  id: stable sha1 of repository-relative path
  path: repository-relative path
  type: report | mri | graph | atlas | trace | hub | checkpoint | metrics |
        decision | message | image | html | json | markdown | other
  title: display title derived from metadata or filename
  campaign_id: optional string
  epoch: optional integer
  media_type: browser content type
  size: bytes
  mtime: unix timestamp

Campaign
  id: string
  title: display title
  artifacts: Artifact[]
  latest_event_at: unix timestamp
  summary: optional text

Event
  id: stable id
  timestamp: unix timestamp
  campaign_id: optional string
  kind: artifact_detected | campaign_started | epoch | report | mri |
        atlas | checkpoint | message | decision
  title: display title
  artifact_id: optional string
  details: JSON object

Message
  id: stable id
  box: inbox | outbox
  path: repository-relative path
  title: string
  body: markdown text
  timestamp: unix timestamp

PublishedBuild
  id: string
  label: Latest | Latest Winner | Campaign N Epoch M | Baseline | custom
  checkpoint_artifact_id: string
  path: repository-relative checkpoint path
  published_at: unix timestamp
```

## REST API

- `GET /api/status`
- `GET /api/trainbox/status`
- `POST /api/git/pull`
- `GET /api/artifacts`
- `GET /api/artifacts/{id}`
- `GET /api/artifacts/{id}/content`
- `GET /api/campaigns`
- `GET /api/campaigns/{id}`
- `GET /api/timeline`
- `GET /api/search?q=...`
- `GET /api/messages?box=inbox|outbox`
- `GET /api/messages/{message_id}/receipt`
- `POST /api/messages/outbox`
- `GET /api/builds`
- `POST /api/builds/publish`
- `POST /api/chat/ninereeds`
- `POST /api/chat/orchestrator`
- `GET /api/events` for Server-Sent Events
- `GET /repo/{repo_relative_path}` for safe raw artifact serving

## WebSocket API

`GET /ws` upgrades to a WebSocket. Broadcast messages use this shape:

```json
{"type":"artifact_indexed","payload":{"artifact_id":"...","title":"..."}}
```

The PWA uses Server-Sent Events first because they are sufficient for Lab-side
notifications and simpler to proxy. WebSocket support is present for future
bidirectional features.

## PWA Design

The PWA shell is static and cacheable. Dynamic data comes from API calls.
Notification permission is requested by the user from Settings. Push-like
browser notifications are generated from the event stream when the page is open;
true background push can be added later with a VAPID-backed push service.

The app remains useful offline for previously cached shell assets, but artifact
content requires local server access.

## Implementation Plan

1. Build the artifact indexer and campaign/timeline abstractions.
2. Add guarded git pull and scan scheduling.
3. Add message file store and event notifications.
4. Add published build registry and chat stubs.
5. Add remote orchestrator adapter with local artifact context.
6. Build the PWA shell around Dashboard, Timeline, Campaigns, Messages, Search,
   Artifact viewer, Chat, and Settings.
7. Add tests for classifier/indexer behavior and API smoke paths.

## Running

```bash
python3 -m lab.backend.server --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`.

The server refuses a non-loopback bind unless either `LAB_AUTH_PASSWORD` is set
or a stored password has first been configured from localhost. Raw
`/repo/...` access is limited to `LAB_SERVE_ROOTS`, which defaults to the same
comma-separated roots as `LAB_SCAN_ROOTS`; `lab/state`, Git internals, and other
repository files are not served.

The server also enforces bounded request bodies, login throttling, same-origin
checks for browser POST requests, browser security headers, and serialized
fast-forward pulls pinned to `LAB_GIT_EXPECTED_REMOTE` and
`LAB_GIT_EXPECTED_BRANCH`.

Live trainbox telemetry defaults to the SSH alias
`ninereeds-trainbox-status`. The backend invokes only its forced `status`
command, validates `ninereeds_trainbox_status_v1`, and rejects any document that
claims training-dispatch authority. Useful overrides are:

```bash
export LAB_TRAINBOX_SSH_TARGET='ninereeds-trainbox-status'
export LAB_TRAINBOX_STATUS_TIMEOUT='8'
export LAB_TRAINBOX_STATUS_CACHE='5'
export LAB_TRAINBOX_STATUS_STALE='180'
```

The dashboard refreshes live telemetry every 15 seconds. It labels unreachable
and stale results independently from the historical artifact index.

The workstation user service installed for this deployment is mirrored at
`lab/systemd/ninereeds-lab.service`. It is intentionally a workstation service;
do not enable it on the trainbox.

For access from another device on the same trusted LAN:

```bash
LAB_AUTH_PASSWORD='choose-a-long-password' \
LAB_AUTH_SECRET='choose-a-random-cookie-signing-secret' \
LAB_GIT_EXPECTED_REMOTE='origin' \
LAB_GIT_EXPECTED_BRANCH='main' \
python3 -m lab.backend.server --host 0.0.0.0 --port 8765
```

Then open `http://WORKSTATION_LAN_IP:8765` from the phone.

For access away from home, do not expose the raw server directly to the public
internet. Put it behind a private VPN or an HTTPS tunnel/reverse proxy, and keep
`LAB_AUTH_PASSWORD` enabled. If HTTPS terminates in front of The Lab, set
`LAB_AUTH_COOKIE_SECURE=1`.

The UI has an explicit Phone/Desktop display toggle. The choice is stored in the
browser's `localStorage`, so each phone or desktop browser can keep its own view.

## Durable Inbox / Outbox

New messages use the versioned `lab_message_v1` JSON envelope. Sending from the
Lab performs one local durable transaction:

```text
authenticated POST
  -> atomic Outbox envelope + queued receipt
  -> systemd path wakes one Codex worker
  -> worker acquires the global lock and a per-message lease
  -> codex exec runs ephemeral, read-only, never-approve, schema-constrained
  -> deterministic correlated Inbox envelope
  -> completed receipt
  -> browser polling displays the reply
```

Receipts preserve transition history through `queued`, `claimed`,
`processing`, `retry_wait`, `completed`, or `dead_letter`. Failed attempts use
bounded exponential retry and a one-minute recovery timer. Reply IDs are
deterministic from request IDs, so a crash between reply persistence and receipt
completion does not duplicate the response. Content hashes detect envelope
drift.

The worker is deliberately a separate ephemeral Codex session, not this
interactive conversation. It may answer or inspect the repository read-only.
Requests for edits, training, service changes, Git changes, external messages,
secrets, approvals, or other consequential actions must return
`needs_interactive`; the mailbox worker cannot perform them.

Runtime state remains local and ignored:

```text
lab/messages/
  outbox/      immutable request envelopes
  inbox/       correlated response envelopes
  claims/      active leases
  receipts/    lifecycle state and history
  worker/      single-worker lock
```

The tracked schemas are:

- `lab/schemas/lab_message_v1.schema.json`
- `lab/schemas/lab_message_receipt_v1.schema.json`
- `lab/schemas/codex_mailbox_reply_v1.schema.json`

The workstation runs:

- `ninereeds-lab-message-worker.path` for immediate wake;
- `ninereeds-lab-message-worker.timer` for crash/lost-wake recovery;
- `ninereeds-lab-message-worker.service` as the bounded one-shot worker.

Relevant overrides:

```bash
export LAB_MESSAGE_CODEX_EXECUTABLE='/home/aomukai/.local/bin/codex'
export LAB_MESSAGE_CODEX_MODEL='gpt-5.6-sol'
export LAB_MESSAGE_CODEX_TIMEOUT='900'
export LAB_MESSAGE_LEASE_SECONDS='1200'
export LAB_MESSAGE_MAX_ATTEMPTS='3'
```

This completes the workstation-local human → Codex → human transaction. It is
not yet the cross-machine training transport. Trainbox plans and reports must
reuse the envelope principles only after separate authority, claim, receipt,
and idempotency tests are defined for that boundary.
