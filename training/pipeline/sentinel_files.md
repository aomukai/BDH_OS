# Sentinel Files

This is the canonical sentinel list for MSM automation. The Lab and the orchestrator
must use these exact filenames.

Sentinel files may live anywhere under `training/pipeline/msm/`. Step 0 checks for them with:

```bash
find training/pipeline/msm \( \
  -name HUMAN_ATTENTION \
  -o -name BLOCKED \
  -o -name TRAINING_MACHINE_DOWN \
  -o -name API_CREDITS_EXHAUSTED \
  -o -name PROMOTION_REVIEW_REQUIRED \
\) 2>/dev/null
```

## Names

| File | Meaning | Required action |
|---|---|---|
| `HUMAN_ATTENTION` | A human decision or manual fix is required. | Lab reports it. Automation pauses for that branch. |
| `BLOCKED` | Automation cannot continue safely from available information. | Lab reports blocker; orchestrator waits. |
| `TRAINING_MACHINE_DOWN` | Local training/session machine or GPU worker is unavailable. | Lab reports it; do not retry in a tight loop. |
| `API_CREDITS_EXHAUSTED` | Optional remote/API worker cannot continue because key/credits/rate limit failed. | Lab reports it; executor stops remote calls. |
| `PROMOTION_REVIEW_REQUIRED` | An update candidate passed automatic gates but needs manual approval. | Lab reports it; do not promote automatically. |

## File Body

Sentinel files should contain a short JSON object when possible:

```json
{
  "created_at": "2026-07-01T00:00:00Z",
  "source": "orchestrator",
  "session_id": "optional",
  "update_id": "optional",
  "reason": "short human-readable reason",
  "requested_action": "what the user should fix or decide"
}
```

Plain text is acceptable during crashes.

## Codex Rate-Limit Blockers

Do not add a separate Codex rate-limit sentinel. If the Codex status watchdog cannot parse
the reset state or detects a condition that cannot safely auto-resume, use `BLOCKED` with
`source` set to `codex_status_watchdog` or `orchestrator`.
