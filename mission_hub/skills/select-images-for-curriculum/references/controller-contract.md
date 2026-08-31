# Autonomous controller contract

Use the bundled controller for Campaign 35-style word/image corpora. Sol freezes one JSON
configuration and starts one durable service. The controller owns phase transitions and writes
an atomic `state.json`, append-only `events.jsonl`, per-round artifacts, and one terminal handoff.

## Guarantees

- Resume the recorded phase after process or machine restart.
- Hold an exclusive run lock; refuse a second controller.
- Preserve accepted slots and exclude every prior word/asset attempt.
- Prefer least-used suitable assets and enforce the frozen reuse cap.
- Search the reviewed registry before external metadata on every iteration.
- Download bounded metadata candidates, inspect pixels, and exclude mechanical failures.
- Target two distinct external candidates per residual slot by default; later metadata faucets
  fill only positions left by earlier faucets in that wave.
- Consider 80% of the two-candidate target sufficient for review. Do not widen into lower-quality
  sources solely to close the final 20%; reassess after reconciliation against the smaller
  residual.
- After the first complete configured metadata-source wave, stop broad external acquisition when
  at least 500 reviewed candidates yield fewer than 15% newly accepted curriculum slots. Emit the
  residual for representation triage and Flux routing rather than commissioning another broad
  dataset wave.
- Keep a persistent per-concept target-fit ledger. Route a concept to the specialist residual
  after at least eight reviewed claims across two rounds yield less than 15%, even when aggregate
  wave yield remains above the floor. Key this by `concept_id`, not only the surface word.
- Run Gemma in bulk, Luna only for escalations, and Sol only for Luna uncertainty.
- Materialize escalation queues before declaring a review round complete.
- Rotate worker identities after retryable provider/schema failures.
- Retry a failing controller phase across service restarts, then emit a blocker after five
  consecutive failures instead of restarting forever.
- Promote generally usable external images and reviewed captions into the registry even when
  they miss the original target, enabling later cross-concept reuse.
- Preserve accepted candidates not selected for their original slot as searchable surplus bank
  assets rather than discarding them.
- Emit the specialist residual separately so compatible concrete needs can be deliberately
  produced together and assigned under the same frozen reuse cap.
- Return to Sol only with `task_complete`, `deterministic_sources_exhausted`, or a concrete
  blocker artifact.

## Terminal meanings

- `task_complete`: every required slot is validated and the completion artifact is frozen.
- `deterministic_sources_exhausted`: configured registry and metadata sources produced no new
  candidates, or two fully reviewed rounds added no accepted slots. Sol receives the complete
  residual once to choose a genuinely new dataset, representation, rewrite, or Flux plan.
- `blocked`: a non-retryable integrity failure or five consecutive failures in one phase.

Neither exhaustion nor blocked is `task_complete`.
