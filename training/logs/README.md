# Logs

This directory stores append-only histories and lightweight rollups for the training harness.

Recommended files:

- `round_index.jsonl` — one summary JSON object per round
- `intervention_history.jsonl` — intervention-level history
- `emergency_requests.jsonl` — proposed and approved/rejected emergency-exit requests

These files may start empty and be populated when the harness begins running real rounds.
