# Allowlist wave handoff — 2026-08-01

## Running text curriculum

The autonomous wave `allowlist-0501-2000-v1` teaches 1,500 unique concepts from
frequency ranks 501 through 2,000 of
`training/corpus_admin/kernel/kernel_full_words.jsonl`. It reuses already curated
material and makes no model-provider calls.

- 12 sequential blocks
- 500 examples per block
- 125 new concepts, 325 foundation replay examples, and 50 identity/German/Japanese
  anchors per block
- 6,000 total training examples
- one held-out rephrasing for every fifth new concept (25 per block), evaluated
  together with the existing 15-case behavioral suite
- immutable starting point:
  `core/cortex/baselines/foundation-language-only-20260731.pt`

The manifest, exact word ranks, source files, corpus hashes, and evaluation hashes
are in:

`training/pipeline/cortex/allowlist_waves/allowlist-0501-2000-v1/manifest.json`

## Autonomous control and safety

`ninereeds-allowlist-wave.timer` advances the wave once per minute. It creates one
durable control-ledger plan at a time, so the Lab's control activity shows the live
training and evaluation plans. The next block is not commissioned until the current
candidate has a deterministic admission certificate.

The persistent timer survives workstation reboot and user logout. Once the wave
reaches `completed`, or reaches a durable safety `blocked` state that requires human
intervention, the controller disables and stops its own timer. Re-enable the timer
only after deliberately resolving a blocked handoff.

The Lab indexes the wave as Campaign 30 (`allowlist-0501-2000-v1`). Its ordinary
campaign manifest and, after each gate, evaluation, transcript, metrics, decision,
MRI, map, and atlas artifacts live under `training/logs/campaign_30_reports`. The
live campaign card also reports the current block, phase, admitted-block count, and
admitted-concept count from the resumable wave state.

The first attempt uses full-scope training at learning rate `3e-6`, RMS clipping at
1.0, and stochastic rounding. A rejected candidate is never made the parent. One
more conservative `1e-6` attempt is allowed from the unchanged parent; if that also
fails, the wave stops safely for intervention. Neither the controller nor a training
block promotes the archived foundation checkpoint.

Exact resumable state:

`/home/aomukai/.local/state/ninereeds-orchestrator-control/derived/allowlist-0501-2000-v1-state.json`

Useful checks:

```bash
systemctl --user status ninereeds-allowlist-wave.timer
jq . /home/aomukai/.local/state/ninereeds-orchestrator-control/derived/allowlist-0501-2000-v1-state.json
python3 -m training.pipeline.control.cli \
  --root /home/aomukai/.local/state/ninereeds-orchestrator-control snapshot
```

To stop further automatic transitions without interrupting an already running
trainbox job:

```bash
systemctl --user disable --now ninereeds-allowlist-wave.timer
```

## Next intervention after completion

Read the state file's `handoff.text_checkpoint` and inspect all twelve admission
certificates. Treat that checkpoint as a candidate until the aggregate wave result
has been reviewed; the original language foundation remains the rollback target.

The visual bootstrap already produced the accepted 96-image foundation pack and a
SigLIP2 projector trained against the pre-wave language checkpoint. Once the text
checkpoint is accepted, re-evaluate and retrain/re-align the SigLIP2 projector
against the new language checkpoint before continuing with FLUX commissioning or a
larger visual curriculum. The prior visual results and asset locations are recorded
in `docs/foundational_visual_bootstrap_2026-08-01.md`.
