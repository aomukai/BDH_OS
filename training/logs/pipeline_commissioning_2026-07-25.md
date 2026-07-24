# Autonomous Pipeline Commissioning — 2026-07-25

## Outcome

The two-machine Ninereeds control plane is commissioned and restart-safe.

- Workstation: durable authoritative plan ledger, restricted SSH transport,
  reconciliation supervisor, Lab visibility, and user messaging.
- Trainbox: forced-command control key, filesystem ledger, bounded worker, local executor,
  deterministic trainer, deterministic grade finalizer, and Phase 0/1 block runner.
- Executor routing: Gemma 4 26B A4B by default, Ternary Bonsai 27B above 32K context,
  Qwen3.6-35B-A3B as bounded fallback.
- GPU isolation: executor jobs use GPU 0; Ninereeds training uses GPU 1.
- Live work requires both an explicit plan authorization and the external trainbox machine
  gate. Checkpoint promotion remains separately forbidden.

## Recovery Evidence

- Shadow phase, executor, script-author, and trainer transactions completed.
- A simulated trainer transcript flowed through real Gemma grading and deterministic
  JSON/JSONL/Markdown finalization in one model attempt.
- Re-delivery of a completed plan left its attempt count unchanged at one.
- A worker terminated after claim was reclaimed after its 10-second lease and completed
  one terminal report on attempt two.
- The headless trainbox rebooted with a queued shadow plan; its enabled user services
  recovered and completed the plan after boot with attempt count one.
- The non-Torch workstation suite passed 55 tests. Trainbox Cortex and control tests passed
  in the commissioned PyTorch environment.

## Live Phase 0 Evidence

The first successful bounded block was `phase_0_form_block_0006`: scratch parent, 64
examples, one epoch, eight updates, bf16 on `cuda:1`, checkpoint written, and probes run.
Its phase gate was not met, so no promotion occurred.

The bounded autonomous continuation proof then ran exactly two blocks:

1. `phase_0_form_block_0007`, resuming block 0006.
2. `phase_0_form_block_0008`, created automatically from block 0007's
   `run_next_block_same_phase` result.

The child budget reached zero and no grandchild plan was created.

Latest block 0008 metrics:

- bounded output rate: 1.0
- printable text rate: 1.0
- sentence shape rate: 1.0
- word-form copy rate: 0.0
- repetition-collapse rate: 0.833
- malformed-fragment rate: 0.0
- speaker-tag corruption rate: 0.0

The working parent is `core/msm/phase_0_form_block_0008.pt`. It is not an accepted or
promoted checkpoint. Phase 0 remains active and its gate remains unmet.

## Recorded Commissioning Failures

Two early live attempts trained checkpoints but failed during probes because the runner
used system Python without PyTorch. Live phase blocks now use the commissioned
Unsloth/PyTorch interpreter. A later attempt was interrupted by the commissioning operator
before producing a checkpoint and was closed as a blocked receipt. None of these artifacts
is a working parent or promoted checkpoint.

## Current Safe State

- No plan is running or queued.
- Both GPUs are idle.
- Workstation supervisor and trainbox worker recovery units are active.
- Trainbox Git is clean; mutable working-parent state and checkpoints are untracked.
- The live gate is enabled in
  `/home/aomukai/.config/ninereeds/trainbox-worker.env`.
- No phase or checkpoint promotion is authorized.

The next strategic action is to revise the Phase 0 dose/data shape to improve direct word
copy while reducing repetition, then queue another explicitly budgeted same-phase block
from block 0008. Phase 1 is unsafe until all Phase 0 gates pass and a separate promotion
decision is recorded.
