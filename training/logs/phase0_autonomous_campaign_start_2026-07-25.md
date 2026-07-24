# Phase 0 Autonomous Campaign Start — 2026-07-25

Campaign `phase0-form-autonomy-20260725-b` is running from terminal seed plan
`plan-auto-phase_0_form_block_0007`, whose report produced working checkpoint
`core/msm/phase_0_form_block_0008.pt`.

## Envelope

- mode: live
- deadline: eight hours after start
- strategic boundaries: 6
- Phase 0 blocks: 6
- executor jobs: 0
- trainer sessions: 0
- allowed phase: `phase_0_form`
- same-phase continuation per decision: 0
- checkpoint promotion: forbidden
- phase advancement: forbidden

The controller therefore returns to Codex/Fugu after every block and cannot spend the
remaining block budget as an unreviewed batch.

## First Closed Loop

Boundary 1 inspected block 0008 and changed exactly one parameter: learning rate from
`0.0005` to `0.00025`. The trainbox completed `phase_0_form_block_0009` from block 0008.

Block 0009 metrics:

- bounded output: 1.0
- printable text: 1.0
- sentence shape: 0.0
- word-form copy: 0.0
- repetition collapse: 0.667
- malformed fragments: 0.0
- speaker-tag corruption: 0.0

The controller mirrored the report, found no deterministic child, and created strategic
boundary 2 automatically. Boundary 2 compared the new report with block 0008, retained
the lower learning rate, increased frontload examples from 128 to 192, and dispatched one
new Phase 0 block from checkpoint 0009.

This is the commissioned continuous behavior: terminal block → mirrored report → new
strategic boundary → one validated live child → trainbox execution.

The campaign will stop automatically on the Phase 0 gate, budget/deadline exhaustion,
provider block, safety/lineage error, or a strategic request for human review. Each
non-running transition is delivered to the Lab inbox.
