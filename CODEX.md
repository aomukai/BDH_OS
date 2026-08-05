# Codex operating contract

Mission Hub is the sole control authority for Ninereeds. Do not restore the legacy dual-ledger, supervisor, worker, MSM, or Lab control paths from `archive/` into live operation.

Before operational changes:

1. read `docs/mission_hub_architecture.md` and `docs/mission_hub_operator_runbook.md`;
2. run `python3 -m mission_hub status` and `python3 -m mission_hub readiness`;
3. verify the relevant role release and active configuration;
4. preserve the stopped state unless the operator explicitly authorizes the next commissioning gate.

Key boundaries:

- `training_data/` is the canonical, editable operator library on Mission Hub; it is ignored by Git and excluded from role releases.
- Training jobs consume only immutable, content-hashed artifacts selected by Mission Hub.
- `core/` and `checkpoints/` contain artifact bytes, not source.
- The trainbox is a stateless executor with machine-local spool/cache only.
- Git mutation, artifact deletion, retention, campaign rollover, external calls, and live training fail closed.
- Hermes is unrelated to Ninereeds and outside this repository's operational scope.
- Historical material under `archive/` is evidence. Do not execute it in place or delete it without a separate review.

The old Lab has been retired. Future Lab work must use the authenticated Mission Hub API and must not infer state from repository files or mutate Git directly.
