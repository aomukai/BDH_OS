#!/usr/bin/env bash
set -euo pipefail

audit_root=/home/aomukai/Ninereeds/config/mission_hub/campaign_material/campaign36/visual-vocabulary-replacement-v1/reconciliation-live-v1
mkdir -p "$audit_root"
if ! /home/aomukai/Ninereeds/meta/scripts/campaign36_replacement_reconcile_live.sh \
    >"$audit_root/last-20-minute-audit.log" 2>&1; then
  touch "$audit_root/last-20-minute-audit.failed"
else
  rm -f "$audit_root/last-20-minute-audit.failed"
fi

# Review remains the only active phase until all semantic and escalation queues
# close.  Thereafter this idempotent controller starts and supervises the ten
# requested generation workers without requiring a human to catch the boundary.
/home/aomukai/Ninereeds/meta/scripts/campaign36_advance_image_goal.sh

exec /home/aomukai/.local/bin/codex queue \
  --thread 019ff661-9d32-7e90-9009-84f98b85f32d \
  --message "Campaign 36 image-corpus 20-minute cache-preservation tick. The deterministic reconciliation audit ran first; inspect config/mission_hub/campaign_material/campaign36/visual-vocabulary-replacement-v1/reconciliation-live-v1/summary.json and last-20-minute-audit.log, then check every worker heartbeat and queue delta. Continue the active goal autonomously: finish reviews; activate 2 Flux and 8 GPT Image workers only after review closes; preserve partial successes; cross providers after failure; revise prompts after both fail; record irreducible words in handoff/2026_08_22_image_representation_ideas_needed.md; repeat until complete. Report only material progress, faults, recoveries, or completion."
