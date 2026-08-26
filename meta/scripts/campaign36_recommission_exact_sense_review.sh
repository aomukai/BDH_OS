#!/usr/bin/env bash
set -euo pipefail

repo=/home/aomukai/Ninereeds
state="$repo/config/mission_hub/campaign_material/campaign36/visual-vocabulary-replacement-v1"
archive="$state/superseded-word-only-review-v1"
timer=ninereeds-campaign36-image-goal-monitor.timer
cd "$repo"

systemctl --user stop "$timer"
trap 'systemctl --user start ninereeds-campaign36-image-goal-monitor.timer' EXIT

mkdir -p "$archive"
for file in summary.json candidate-decisions.jsonl selected-assets.jsonl surplus-accepted.jsonl generation-queue.jsonl; do
  source="$state/reconciliation-live-v1/$file"
  if [[ -f "$source" ]]; then
    cp -a "$source" "$archive/$file"
  fi
done

mapfile -t old_pids < <(
  pgrep -f -- '[c]ampaign36-visual-vocab-replacements-(metadata|local)-v1' || true
)
if ((${#old_pids[@]})); then
  kill -TERM "${old_pids[@]}"
  alive=("${old_pids[@]}")
  for _ in $(seq 1 30); do
    next=()
    for pid in "${alive[@]}"; do
      kill -0 "$pid" 2>/dev/null && next+=("$pid")
    done
    alive=("${next[@]}")
    ((${#alive[@]} == 0)) && break
    sleep 1
  done
  ((${#alive[@]} == 0)) || kill -KILL "${alive[@]}"
fi

/home/aomukai/.venvs/ninereeds-cortex/bin/python - "$state/exact-sense-recommission.json" <<'PY'
import json
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime, timezone

db_path = Path("training_data/image_registry/registry.sqlite3")
semantic = [
    f"campaign36-visual-vocab-replacements-{pool}-v1-semantic"
    for pool in ("metadata", "local")
]
downstream = [
    f"campaign36-visual-vocab-replacements-{pool}-v1-{stage}"
    for pool in ("metadata", "local")
    for stage in ("watermark-luna", "usability-luna", "word-fit-luna", "word-fit-sol")
]
now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
with sqlite3.connect(db_path, timeout=60) as db:
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("BEGIN IMMEDIATE")
    before = {}
    for queue in semantic + downstream:
        before[queue] = dict(db.execute(
            "SELECT status,COUNT(*) FROM review_queue WHERE queue_name=? GROUP BY status",
            (queue,),
        ))
        db.execute(
            """UPDATE review_attempt SET status='expired',finished_at=?,error_json=?
               WHERE queue_name=? AND status='leased'""",
            (now, json.dumps({"type": "SupersededReviewContract", "reason": "v1 prompt omitted fixed teaching sense"}), queue),
        )
    for queue in semantic:
        db.execute(
            """UPDATE review_queue SET status='pending',current_attempt_id=NULL,
                       completed_at=NULL,result_json=NULL WHERE queue_name=?""",
            (queue,),
        )
    for queue in downstream:
        db.execute("DELETE FROM review_queue WHERE queue_name=?", (queue,))
    if db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='campaign36_word_generation_attempt'"
    ).fetchone():
        db.execute("DELETE FROM campaign36_word_generation_attempt")
        db.execute("DELETE FROM campaign36_word_generation")
    db.commit()

report = {
    "schema_version": "ninereeds_campaign36_exact_sense_recommission_v1",
    "recommissioned_at": now,
    "reason": "The v1 semantic prompt supplied surface words but omitted immutable teaching senses, allowing homonym mismatches.",
    "superseded_prompt_version": "campaign35-word-review-v1",
    "replacement_prompt_version": "campaign35-word-review-v2-exact-sense",
    "preserved_attempt_evidence": True,
    "prior_queue_counts": before,
}
path = Path(sys.argv[1])
temporary = path.with_suffix(path.suffix + ".partial")
temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
os.replace(temporary, path)
PY

chmod +x meta/scripts/campaign36_replacement_review_worker.sh
mkdir -p ~/.config/systemd/user
install -m 0644 mission_hub/systemd/ninereeds-c36-replacement-review@.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ninereeds-c36-replacement-review@{0..17}.service

meta/scripts/campaign36_replacement_reconcile_live.sh
echo "Campaign 36 exact-sense review recommissioned under 18 supervised workers"
