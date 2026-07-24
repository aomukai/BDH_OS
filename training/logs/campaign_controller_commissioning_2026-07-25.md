# Autonomous Campaign Controller Commissioning — 2026-07-25

## Outcome

The workstation now closes the loop between terminal bounded workflows and new strategic
decisions. A campaign can start once, follow its single durable child lineage, re-enter
Codex/Fugu strategy after each terminal leaf, and stop without operator polling.

Campaign state is restart-safe and external to Git:

`~/.local/state/ninereeds-orchestrator-control/campaign/state.json`

## Safety Envelope

Every campaign fixes:

- a terminal seed plan
- an objective and wall-clock deadline
- strategic-boundary, phase-block, executor-job, and trainer-session budgets
- allowed child kinds and phase IDs
- a mutation authorization ceiling

Checkpoint promotion is never permitted by autonomous campaign state. Phase and executor
continuation are set to zero for the initial controller, so strategy observes every
terminal block/session rather than spending the remaining campaign budget in an opaque
batch.

The controller stops or waits on:

- current phase `gate_status=met`
- strategic `wait` or `request_human`
- provider block
- budget or deadline exhaustion
- missing plan/receipt
- branching lineage
- completed strategic decision without its expected child

Each such transition is durable and emits one idempotent Lab inbox notice.

## Recovery and Failure Evidence

Automated tests cover:

- exactly-one boundary creation across repeated reconciliation
- child-lineage following and strategic re-entry after a terminal child
- `wait` transition and Lab notification
- phase-gate completion
- child-budget exhaustion
- parent-authorization escalation rejection
- phase continuation exceeding the remaining campaign budget

The non-Torch workstation suite passes 70 tests.

## Live Shadow Trial

Campaign `commission-loop-20260725` began from completed Phase 0 block plan
`plan-auto-phase_0_form_block_0007`.

It created one durable strategic boundary:

`plan-campaign-commission-loop-20260725-b0001`

Codex claimed it once, returned `wait` as explicitly requested, and created no child. The
controller observed the terminal strategic leaf and moved the campaign to `waiting`
without a duplicate boundary. The operator then closed the completed commissioning
campaign cleanly.

This demonstrates the full supervisor-to-strategy-to-controller return path before live
training is enabled under the new controller.

## Seed-Isolation Correction

The first live campaign start reused the same terminal seed as the shadow trial. Initial
reconciliation incorrectly followed the older campaign's already completed strategic
child and entered `waiting`. No live child or training plan was created.

Campaign initialization now ignores pre-existing seed children until its own root boundary
has been recorded. A regression test constructs an older completed campaign child under
the same seed and verifies that a new campaign creates its own boundary exactly once.
