#!/usr/bin/env bash
set -euo pipefail

cd /home/aomukai/Ninereeds
python_bin=/home/aomukai/.venvs/ninereeds-cortex/bin/python
material=config/mission_hub/campaign_material/campaign36/visual-vocabulary-replacement-v1
output="$material/reconciliation-live-v1"
generated=/media/aomukai/FILES/Ninereeds/image-corpus/exports/campaign36-foundation-preparation-v1/visual-vocabulary-replacement-v1/generation-v1/accepted-generated.jsonl
generation_root=/media/aomukai/FILES/Ninereeds/image-corpus/exports/campaign36-foundation-preparation-v1/visual-vocabulary-replacement-v1/generation-v1
reviews_complete_args=()
activation_marker="$material/generation-activated.json"
if [[ "${1:-}" == "--reviews-complete" || -f "$activation_marker" ]]; then
  reviews_complete_args=(--reviews-complete)
fi

"$python_bin" -m image_registry.campaign36_replacement_generated_recover \
  --db training_data/image_registry/registry.sqlite3 \
  --root "$generation_root"

generated_args=()
if [[ -f "$generated" ]]; then
  generated_args=(--generated-accepted "$generated")
fi

"$python_bin" -m image_registry.campaign36_replacement_reconcile \
  --db training_data/image_registry/registry.sqlite3 \
  --local-bindings "$material/local-review-preparation-v1/bindings.jsonl" \
  --metadata-candidates "$material/metadata-candidate-pool-v1/candidates.jsonl" \
  --replacement-map "$material/replacement-map.jsonl" \
  --requirements "$material/revised-requirements.jsonl" \
  --baseline-accepted /media/aomukai/FILES/Ninereeds/image-corpus/exports/campaign36-foundation-preparation-v1/lexicon-revision-v1/corrected-manifest-v1/frozen-ordinary-still-v1/accepted-assets.jsonl \
  "${generated_args[@]}" \
  --local-queue campaign36-visual-vocab-replacements-local-v1-semantic \
  --local-watermark-queue campaign36-visual-vocab-replacements-local-v1-watermark-luna \
  --local-usability-queue campaign36-visual-vocab-replacements-local-v1-usability-luna \
  --local-word-fit-queue campaign36-visual-vocab-replacements-local-v1-word-fit-luna \
  --local-sol-queue campaign36-visual-vocab-replacements-local-v1-word-fit-sol \
  --metadata-queue campaign36-visual-vocab-replacements-metadata-v1-semantic \
  --metadata-watermark-queue campaign36-visual-vocab-replacements-metadata-v1-watermark-luna \
  --metadata-usability-queue campaign36-visual-vocab-replacements-metadata-v1-usability-luna \
  --metadata-word-fit-queue campaign36-visual-vocab-replacements-metadata-v1-word-fit-luna \
  --metadata-sol-queue campaign36-visual-vocab-replacements-metadata-v1-word-fit-sol \
  --output "$output"

"$python_bin" -m image_registry.campaign36_replacement_generation_queue \
  --db training_data/image_registry/registry.sqlite3 sync \
  --replacement-map "$material/replacement-map.jsonl" \
  --selected-assets "$output/selected-assets.jsonl" \
  "${reviews_complete_args[@]}"
