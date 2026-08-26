#!/usr/bin/env bash
set -euo pipefail

index=${1:?worker index required}
cd /home/aomukai/Ninereeds
python=/home/aomukai/.venvs/ninereeds-cortex/bin/python
db=training_data/image_registry/registry.sqlite3
meta=campaign36-visual-vocab-replacements-metadata-v1
localq=campaign36-visual-vocab-replacements-local-v1

semantic() {
  local pool=$1 worker=$2 backend=$3 endpoint=$4 model=$5 claims=$6
  shift 6
  exec "$python" -m image_benchmark.campaign35_word_worker \
    --db "$db" --queue "campaign36-visual-vocab-replacements-${pool}-v1-semantic" \
    --worker-id "$worker" --backend "$backend" --endpoint "$endpoint" \
    --model "$model" --max-claims "$claims" --max-attempts 6 \
    --attempt-family-marker=-v2 --disable-thinking --require-valid-schema "$@"
}

cascade() {
  local pool=$1 kind=$2
  local prefix="campaign36-visual-vocab-replacements-${pool}-v1"
  case "$kind" in
    watermark)
      exec "$python" -m image_benchmark.luna_watermark_worker \
        --db "$db" --source-queue "$prefix-semantic" --queue "$prefix-watermark-luna" \
        --worker-id "c36-${pool}-watermark-luna-v2-0" --lease-seconds 1800 --timeout 600 --poll-seconds 5
      ;;
    usability)
      exec "$python" -m image_benchmark.luna_usability_worker \
        --db "$db" --source-queue "$prefix-semantic" --queue "$prefix-usability-luna" \
        --watermark-queue "$prefix-watermark-luna" \
        --worker-id "c36-${pool}-usability-luna-v2-0" --lease-seconds 1800 --timeout 600 \
        --poll-seconds 5 --skip-quarantine
      ;;
    wordfit)
      exec "$python" -m image_benchmark.luna_word_fit_worker \
        --db "$db" --source-queue "$prefix-semantic" --queue "$prefix-word-fit-luna" \
        --worker-id "c36-${pool}-wordfit-luna-v2-0" --lease-seconds 1800 --timeout 600 \
        --poll-seconds 5 --max-attempts 6
      ;;
    sol)
      exec "$python" -m image_benchmark.sol_word_fit_worker \
        --db "$db" --semantic-source-queue "$prefix-semantic" \
        --luna-queue "$prefix-word-fit-luna" --queue "$prefix-word-fit-sol" \
        --worker-id "c36-${pool}-wordfit-sol-v2-0" --model gpt-5.6-sol \
        --lease-seconds 1800 --timeout 600 --poll-seconds 5 --max-attempts 6
      ;;
  esac
}

terminal_fallback() {
  local pool=$1
  local prefix="campaign36-visual-vocab-replacements-${pool}-v1"
  exec "$python" -m image_benchmark.luna_terminal_semantic_worker \
    --db "$db" --source-queue "$prefix-semantic" \
    --queue "$prefix-semantic-luna-fallback" \
    --worker-id "c36-${pool}-semantic-luna-fallback-v2-0" \
    --lease-seconds 1800 --timeout 600 --poll-seconds 5 --max-attempts 12
}

case "$index" in
  0) semantic metadata c36-metadata-gemma-gpu0-v2 llama.cpp-gpu0 http://127.0.0.1:8792/v1/chat/completions gemma-4-26b-a4b-it-q4km 4 --health-endpoint http://127.0.0.1:8792/health ;;
  1) semantic local c36-local-gemma-gpu1-v2 llama.cpp-gpu1 http://127.0.0.1:8793/v1/chat/completions gemma-4-26b-a4b-it-q4km 4 --health-endpoint http://127.0.0.1:8793/health ;;
  2) semantic metadata c36-metadata-openrouter-v2-0 openrouter https://openrouter.ai/api/v1/chat/completions google/gemma-4-26b-a4b-it 2 --token-env OPENROUTER_API_KEY ;;
  3) semantic metadata c36-metadata-openrouter-v2-1 openrouter https://openrouter.ai/api/v1/chat/completions google/gemma-4-26b-a4b-it 2 --token-env OPENROUTER_API_KEY ;;
  4) semantic local c36-local-openrouter-v2-0 openrouter https://openrouter.ai/api/v1/chat/completions google/gemma-4-26b-a4b-it 2 --token-env OPENROUTER_API_KEY ;;
  5) semantic local c36-local-openrouter-v2-1 openrouter https://openrouter.ai/api/v1/chat/completions google/gemma-4-26b-a4b-it 2 --token-env OPENROUTER_API_KEY ;;
  6) semantic local c36-local-nvidia-v2-0 nvidia-nim https://integrate.api.nvidia.com/v1/chat/completions google/gemma-4-31b-it 2 --token-env NVIDIA_API_KEY ;;
  7) semantic local c36-local-nvidia-v2-1 nvidia-nim https://integrate.api.nvidia.com/v1/chat/completions google/gemma-4-31b-it 2 --token-env NVIDIA_API_KEY ;;
  8) cascade metadata watermark ;;
  9) cascade metadata usability ;;
  10) cascade metadata wordfit ;;
  11) cascade metadata sol ;;
  12) cascade local watermark ;;
  13) cascade local usability ;;
  14) cascade local wordfit ;;
  15) cascade local sol ;;
  16) terminal_fallback metadata ;;
  17) terminal_fallback local ;;
  *) echo "worker index must be 0..17" >&2; exit 64 ;;
esac
