#!/usr/bin/env bash
set -euo pipefail

repo=/home/aomukai/Ninereeds
state_root="$repo/config/mission_hub/campaign_material/campaign36/visual-vocabulary-replacement-v1"
marker="$state_root/generation-activated.json"
completion_marker="$state_root/corpus-complete.json"
log="$state_root/generation-controller.log"
lock="$state_root/generation-controller.lock"

mkdir -p "$state_root"
exec 9>"$lock"
if ! flock -n 9; then
  exit 0
fi

timestamp() {
  date --utc +%Y-%m-%dT%H:%M:%SZ
}

if [[ ! -f "$marker" ]]; then
  summary="$state_root/reconciliation-live-v1/summary.json"
  if [[ ! -f "$summary" ]]; then
    printf '%s waiting: reconciliation summary does not exist\n' "$(timestamp)" >>"$log"
    exit 0
  fi
  if ! /home/aomukai/.venvs/ninereeds-cortex/bin/python - "$summary" <<'PY'
import json
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(
    0
    if int(summary.get("semantic_unfinished_claims", 1)) == 0
    and int(summary.get("cascade_unfinished_claims", 1)) == 0
    else 1
)
PY
  then
    exit 0
  fi

  # The activation script performs a fresh cascade sync and refuses to proceed
  # if that sync exposes any pending, leased, or failed adjudication work.
  if "$repo/meta/scripts/campaign36_start_replacement_generation.sh" >>"$log" 2>&1; then
    /home/aomukai/.venvs/ninereeds-cortex/bin/python - "$marker" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
temporary = path.with_suffix(path.suffix + ".partial")
temporary.write_text(
    json.dumps(
        {
            "schema_version": "ninereeds_campaign36_generation_activation_v1",
            "activated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "imagegen_workers": 8,
            "flux_workers": 2,
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
os.replace(temporary, path)
PY
  else
    # A just-created cascade claim is an expected race.  Leave the marker absent
    # so the next 20-minute audit tries again after adjudication catches up.
    printf '%s activation deferred after fresh readiness check\n' "$(timestamp)" >>"$log"
  fi
  exit 0
fi

if [[ -f "$completion_marker" ]]; then
  exit 0
fi

# Rebuild the human representation-ideas ledger from authoritative queue state.
# This also repairs any last-writer race between generators finishing together.
/home/aomukai/.venvs/ninereeds-cortex/bin/python \
  -m image_registry.campaign36_replacement_generation_queue \
  --db "$repo/training_data/image_registry/registry.sqlite3" \
  write-handoff \
  --path "$repo/handoff/2026_08_22_image_representation_ideas_needed.md" \
  >>"$log" 2>&1

# Once activated, persistent workers should remain up through transient failures.
# Their queue claims are atomic, so restarting a missing service is safe.
local_units=(
  ninereeds-c36-replacement-imagegen@{0..7}.service
  ninereeds-c36-replacement-flux-dispatcher@{0..1}.service
  ninereeds-c36-replacement-prompt-reviser.service
)
for unit in "${local_units[@]}"; do
  if ! systemctl --user is-active --quiet "$unit"; then
    printf '%s recovering local worker %s\n' "$(timestamp)" "$unit" >>"$log"
    systemctl --user start "$unit"
  fi
done

ssh -o BatchMode=yes ninereeds-trainbox '
  set -e
  for unit in ninereeds-c36-replacement-flux@0.service ninereeds-c36-replacement-flux@1.service; do
    if ! systemctl --user is-active --quiet "$unit"; then
      systemctl --user start "$unit"
    fi
  done
' >>"$log" 2>&1

# Full hashing of 25,000 files is intentionally deferred until all cheap terminal
# indicators agree that no work remains.  A successful audit publishes the frozen
# combined manifest; only then are idle generator services stopped.
summary="$state_root/reconciliation-live-v1/summary.json"
if /home/aomukai/.venvs/ninereeds-cortex/bin/python - "$summary" "$repo/training_data/image_registry/registry.sqlite3" <<'PY'
import json
import sqlite3
import sys

summary = json.load(open(sys.argv[1], encoding="utf-8"))
if any(int(summary.get(key, -1)) != 0 for key in (
    "semantic_unfinished_claims", "cascade_unfinished_claims", "residual_images"
)):
    raise SystemExit(1)
with sqlite3.connect(sys.argv[2]) as db:
    counts = dict(db.execute(
        "SELECT status,COUNT(*) FROM campaign36_word_generation GROUP BY status"
    ))
    totals = db.execute(
        "SELECT COUNT(*),COALESCE(SUM(remaining_count),0) FROM campaign36_word_generation"
    ).fetchone()
raise SystemExit(0 if counts == {"complete": totals[0]} and totals[1] == 0 else 1)
PY
then
  final_root=/media/aomukai/FILES/Ninereeds/image-corpus/exports/campaign36-foundation-preparation-v1/visual-vocabulary-replacement-v1/final-v1
  mkdir -p "$final_root"
  if /home/aomukai/.venvs/ninereeds-cortex/bin/python -m image_registry.campaign36_replacement_completion_audit \
      --db "$repo/training_data/image_registry/registry.sqlite3" \
      --requirements "$state_root/revised-requirements.jsonl" \
      --retained /media/aomukai/FILES/Ninereeds/image-corpus/exports/campaign36-foundation-preparation-v1/lexicon-revision-v1/corrected-manifest-v1/frozen-ordinary-still-v1/accepted-assets.jsonl \
      --replacements "$state_root/reconciliation-live-v1/selected-assets.jsonl" \
      --reconciliation-summary "$summary" \
      --output "$final_root/completion-audit.json" \
      --final-manifest "$final_root/accepted-assets.jsonl" \
      --verify-content-hashes >>"$log" 2>&1
  then
    systemctl --user stop "${local_units[@]}"
    ssh -o BatchMode=yes ninereeds-trainbox \
      'systemctl --user stop ninereeds-c36-replacement-flux@0.service ninereeds-c36-replacement-flux@1.service' \
      >>"$log" 2>&1
    /home/aomukai/.venvs/ninereeds-cortex/bin/python - "$completion_marker" "$final_root" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
root = Path(sys.argv[2])
audit = json.loads((root / "completion-audit.json").read_text(encoding="utf-8"))
value = {
    "schema_version": "ninereeds_campaign36_replacement_completion_v1",
    "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "completion_audit": str(root / "completion-audit.json"),
    "final_manifest": audit["final_manifest"],
    "final_manifest_sha256": audit["final_manifest_sha256"],
    "assets": audit["combined_assets"],
    "words": audit["words"],
}
temporary = path.with_suffix(path.suffix + ".partial")
temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(temporary, path)
PY
    printf '%s corpus completion audit passed; generation workers stopped\n' "$(timestamp)" >>"$log"
  fi
fi
