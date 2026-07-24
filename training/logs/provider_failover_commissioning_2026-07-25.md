# Strategic Provider Failover Commissioning — 2026-07-25

## Outcome

The workstation now has a restart-safe Codex-to-Fugu handoff for fresh strategic
boundaries and Lab mailbox replies.

- Codex/Sol remains primary.
- The supervisor reads structured limits through the installed Codex app-server
  `account/rateLimits/read` method on every recovery-timer pass.
- A hard Codex limit routes the same exclusively leased, schema-bound call through the
  separately billed Sakana Fugu profile.
- A Codex invocation that itself returns a rate-limit response records that transition
  and retries the same boundary once through Fugu.
- If both providers report a limit, no child plan is created and the durable boundary is
  recorded as blocked.
- An unknown Codex status never causes speculative fallback or double spending.
- Provider calls run read-only, noninteractive, ephemeral, and against a strict response
  schema. A deterministic validator enforces the parent authorization ceiling before at
  most one child plan can be materialized.

Provider state is outside Git at:

`~/.local/state/ninereeds-orchestrator-control/provider/status.json`

The Fugu credential is outside Git in a mode-0600 user-service environment file:

`~/.config/ninereeds/provider.env`

## Notification Contract

Every newly observed Codex or Fugu limit event writes one idempotent `system_notice` to
the Lab inbox. The browser polls the inbox every ten seconds. Codex is monitored
continuously through its structured endpoint; a Fugu limit is observed when a Fugu call
returns a rate-limit response. The Lab control panel shows the selected provider and the
sanitized Codex/Fugu states.

No credentials, raw prompts, or provider response bodies are stored in public provider
status or limit notices.

## Commissioning Evidence

- The live Codex structured endpoint returned a valid Plus-plan snapshot and selected
  Codex while capacity remained.
- The user services saw Fugu as configured after loading the protected environment file.
- A live direct Fugu call completed through Sakana in read-only, schema-bound mode.
- Durable shadow boundary `plan-strategic-provider-commission-v1` was claimed once by the
  strategic worker, completed through `gpt-5.6-sol`, returned `wait`, and created no child
  plan.
- Synthetic failure tests covered pre-observed Codex limit, Codex command 429, Fugu
  fallback, both-providers-limited, unknown Codex status, duplicate notification
  suppression, one-boundary/one-child idempotency, and authorization escalation rejection.
- The workstation non-Torch suite passed 64 tests. The only full-suite collection
  exclusions remain tests that require PyTorch, which is commissioned on the trainbox.

## Service State

- `ninereeds-orchestrator-supervisor.path`: active
- `ninereeds-orchestrator-supervisor.timer`: active
- `ninereeds-lab-message-worker.path`: active
- `ninereeds-lab-message-worker.timer`: active
- `ninereeds-lab.service`: active

The handoff never transfers a running turn. It chooses a provider only at the start of a
new durable strategic boundary; already authorized local executor or trainer work may
finish independently.
