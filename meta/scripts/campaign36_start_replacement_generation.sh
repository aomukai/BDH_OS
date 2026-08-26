#!/usr/bin/env bash
set -euo pipefail

cd /home/aomukai/Ninereeds
python_bin=/home/aomukai/.venvs/ninereeds-cortex/bin/python

"$python_bin" - <<'PY'
import sqlite3
from image_registry.review_queue import queue_status
from image_benchmark.luna_watermark_worker import sync_alarm_queue
from image_benchmark.luna_usability_worker import sync_unusable_queue
from image_benchmark.luna_word_fit_worker import sync_word_fit_queue
from image_benchmark.sol_word_fit_worker import sync_queue as sync_sol_queue

db = sqlite3.connect("training_data/image_registry/registry.sqlite3")
db.row_factory = sqlite3.Row
queues = [
    f"campaign36-visual-vocab-replacements-{pool}-v1-{stage}"
    for pool in ("metadata", "local")
    for stage in (
        "semantic", "watermark-luna", "usability-luna",
        "word-fit-luna", "word-fit-sol",
    )
]
for pool in ("metadata", "local"):
    source = f"campaign36-visual-vocab-replacements-{pool}-v1-semantic"
    watermark = f"campaign36-visual-vocab-replacements-{pool}-v1-watermark-luna"
    usability = f"campaign36-visual-vocab-replacements-{pool}-v1-usability-luna"
    word_fit = f"campaign36-visual-vocab-replacements-{pool}-v1-word-fit-luna"
    sol = f"campaign36-visual-vocab-replacements-{pool}-v1-word-fit-sol"
    sync_alarm_queue(db, source, watermark)
    sync_unusable_queue(db, source, usability)
    sync_word_fit_queue(db, source, word_fit)
    sync_sol_queue(db, word_fit, sol)
unfinished = {}
for queue in queues:
    counts = queue_status(db, queue)["counts"]
    remaining = sum(counts.get(key, 0) for key in ("pending", "leased", "failed"))
    if remaining:
        unfinished[queue] = counts
if unfinished:
    raise SystemExit("review/adjudication is not complete: " + repr(unfinished))
semantic_queues = [
    "campaign36-visual-vocab-replacements-metadata-v1-semantic",
    "campaign36-visual-vocab-replacements-local-v1-semantic",
]
for queue in semantic_queues:
    bad = db.execute(
        """SELECT COUNT(*) FROM review_queue
           WHERE queue_name=? AND (
             status!='completed' OR
             COALESCE(json_extract(result_json,'$.prompt_version'),'')
               !='campaign35-word-review-v2-exact-sense'
           )""",
        (queue,),
    ).fetchone()[0]
    missing_senses = db.execute(
        """SELECT COUNT(*) FROM campaign35_word_review_slot_binding
           WHERE queue_name=? AND trim(COALESCE(teaching_sense,''))=''""",
        (queue,),
    ).fetchone()[0]
    if bad or missing_senses:
        raise SystemExit(
            f"exact-sense review provenance gate failed for {queue}: "
            f"bad_results={bad}, missing_senses={missing_senses}"
        )
PY

meta/scripts/campaign36_replacement_reconcile_live.sh --reviews-complete

# Review is terminal at this point.  Retire only processes whose command line is
# bound to these two exact Campaign 36 replacement queue prefixes, then release
# the trainbox review API's GPU allocations for Flux.
systemctl --user disable --now ninereeds-c36-replacement-review@{0..17}.service 2>/dev/null || true
mapfile -t review_pids < <(
  pgrep -f -- '[c]ampaign36-visual-vocab-replacements-(metadata|local)-v1' || true
)
if ((${#review_pids[@]})); then
  kill -TERM "${review_pids[@]}"
  for _ in $(seq 1 30); do
    alive=()
    for pid in "${review_pids[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        alive+=("$pid")
      fi
    done
    ((${#alive[@]} == 0)) && break
    sleep 1
  done
  if ((${#alive[@]})); then
    kill -KILL "${alive[@]}"
  fi
fi

rsync -a --relative \
  image_registry/campaign36_replacement_flux_remote.py \
  mission_hub/systemd/ninereeds-c36-replacement-flux@.service \
  ninereeds-trainbox:/home/aomukai/Ninereeds/

ssh -o BatchMode=yes ninereeds-trainbox '
  set -e
  mkdir -p ~/.config/systemd/user
  cp /home/aomukai/Ninereeds/mission_hub/systemd/ninereeds-c36-replacement-flux@.service ~/.config/systemd/user/
  systemctl --user daemon-reload
  systemctl --user stop ninereeds-image-review-api.service
  for try in $(seq 1 30); do
    used=$(nvidia-smi --query-compute-apps=used_memory --format=csv,noheader,nounits 2>/dev/null | awk "{s+=\$1} END {print s+0}")
    if [ "$used" -lt 2048 ]; then break; fi
    sleep 2
  done
  systemctl --user start ninereeds-c36-replacement-flux@0.service ninereeds-c36-replacement-flux@1.service
'

mkdir -p ~/.config/systemd/user
install -m 0644 mission_hub/systemd/ninereeds-c36-replacement-imagegen@.service ~/.config/systemd/user/
install -m 0644 mission_hub/systemd/ninereeds-c36-replacement-flux-dispatcher@.service ~/.config/systemd/user/
install -m 0644 mission_hub/systemd/ninereeds-c36-replacement-prompt-reviser.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user start \
  ninereeds-c36-replacement-imagegen@{0..7}.service \
  ninereeds-c36-replacement-flux-dispatcher@{0..1}.service \
  ninereeds-c36-replacement-prompt-reviser.service

echo "Campaign 36 replacement generation activated: 8 ImageGen + 2 Flux + prompt reviser"
