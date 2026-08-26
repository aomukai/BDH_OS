#!/usr/bin/env bash
set -euo pipefail

cd /home/aomukai/Ninereeds
set -a
source /home/aomukai/Ninereeds/.env
set +a

exec /usr/bin/python3 meta/scripts/build_m2_teaching_lexicon.py \
    --curriculum config/mission_hub/campaign_material/campaign35/curriculum.jsonl \
    --text-lessons config/mission_hub/campaign_material/campaign35/text-lessons.jsonl \
    --source-root . \
    --endpoint https://api.deepseek.com/chat/completions \
    --model deepseek-v4-flash \
    --token-env DEEPSEEK_API_KEY \
    --json-mode json_object \
    --thinking \
    --reasoning-effort max \
    --max-tokens 32768 \
    --order descending \
    --worker-id deepseek-descending \
    --ssh-ledger-host ninereeds-trainbox \
    --ssh-ledger-helper /home/aomukai/.local/share/ninereeds/curriculum-design/campaign36/job/meta/scripts/m2_teaching_lexicon_ledger.py \
    --ssh-ledger-output /home/aomukai/.local/share/ninereeds/curriculum-design/campaign36/m2-teaching-lexicon.jsonl
