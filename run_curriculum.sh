#!/usr/bin/env bash
# Set PYTHON to the interpreter that has torch if not already set
PYTHON="${PYTHON:-/home/aomukai/.unsloth/studio/unsloth_studio/bin/python}"

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
START_PHASE=1
END_PHASE=5
PASS_THRESHOLD=0.55
TRAIN_ARGS=()
CHECKPOINT_DIR="core"
EVAL_SCRIPT="eval.py"

# ---------------------------------------------------------------------------
# Help / args
# ---------------------------------------------------------------------------
usage() {
  cat <<'EOF'
BDH Curriculum Training Pipeline

Runs train phase N -> eval -> (pass? next phase : stop and report)

Usage:
  ./run_curriculum.sh
  ./run_curriculum.sh --start-phase 3
  ./run_curriculum.sh --start-phase 3 --end-phase 5
  ./run_curriculum.sh --start-phase 5 --end-phase 5 --epochs 10 --batch-size 8 --lr 3e-4
  ./run_curriculum.sh --scale --seed 1337

Options:
  --start-phase N   Start phase (1-5, default: 1)
  --end-phase N     End phase (1-5, default: 5)
  --threshold X     Eval pass threshold (default: 0.55)
  --epochs N        Forwarded to train.py
  --batch-size N    Forwarded to train.py
  --lr X            Forwarded to train.py
  --seed N          Forwarded to train.py
  --device NAME     Forwarded to train.py (cpu/cuda/mps)
  --scale           Forwarded to train.py
  --help            Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)      usage; exit 0 ;;
    --start-phase)  START_PHASE="$2"; shift 2 ;;
    --end-phase)    END_PHASE="$2";   shift 2 ;;
    --threshold)    PASS_THRESHOLD="$2"; shift 2 ;;
    --scale)        TRAIN_ARGS+=("--scale"); shift ;;
    --epochs)       TRAIN_ARGS+=("--epochs" "$2"); shift 2 ;;
    --batch-size)   TRAIN_ARGS+=("--batch-size" "$2"); shift 2 ;;
    --lr)           TRAIN_ARGS+=("--lr" "$2"); shift 2 ;;
    --seed)         TRAIN_ARGS+=("--seed" "$2"); shift 2 ;;
    --device)       TRAIN_ARGS+=("--device" "$2"); shift 2 ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() { echo "[$(date '+%H:%M:%S')] $*"; }

die() { echo ""; echo "ERROR: $*" >&2; exit 1; }

if [[ ! -x "$PYTHON" ]]; then
  die "Python runtime not found or not executable: $PYTHON"
fi

"$PYTHON" -c "import torch" >/dev/null 2>&1 \
  || die "Python runtime cannot import torch: $PYTHON"

if [[ "$START_PHASE" -lt 1 || "$START_PHASE" -gt 5 ]]; then
  die "--start-phase must be in [1, 5], got ${START_PHASE}."
fi
if [[ "$END_PHASE" -lt 1 || "$END_PHASE" -gt 5 ]]; then
  die "--end-phase must be in [1, 5], got ${END_PHASE}."
fi
if [[ "$START_PHASE" -gt "$END_PHASE" ]]; then
  die "--start-phase (${START_PHASE}) cannot be greater than --end-phase (${END_PHASE})."
fi

run_eval_get_score() {
  local checkpoint="$1"
  # Run eval.py, capture shaped avg score from output line:
  #   "  SHAPED avg: 0.612   (delta +0.041)"
  "$PYTHON" "$EVAL_SCRIPT" --checkpoint "$checkpoint" 2>&1 | tee /tmp/bdh_eval_out.txt \
    | grep "SHAPED avg:" \
    | sed 's/.*SHAPED avg:[[:space:]]*//' \
    | awk '{print $1}'
}

passes_threshold() {
  local score="$1"
  # Python-based float comparison (bc may not be available)
  "$PYTHON" -c "import sys; sys.exit(0 if float('$score') >= $PASS_THRESHOLD else 1)"
}

checkpoint_for_phase() {
  echo "${CHECKPOINT_DIR}/phase_${1}.pt"
}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
echo ""
echo "============================================================"
echo "  BDH Curriculum Training Pipeline"
echo "  Phases ${START_PHASE}–${END_PHASE}  |  Pass threshold: ${PASS_THRESHOLD}"
echo "  Python: ${PYTHON}"
echo "============================================================"
echo ""

PREV_CHECKPOINT=""

for PHASE in $(seq "$START_PHASE" "$END_PHASE"); do
  OUTPUT=$(checkpoint_for_phase "$PHASE")

  # Build resume arg
  RESUME_ARGS=()
  if [[ -n "$PREV_CHECKPOINT" ]]; then
    RESUME_ARGS=("--resume" "$PREV_CHECKPOINT")
  elif [[ "$PHASE" -gt 1 ]]; then
    # Auto-detect prior phase checkpoint
    PRIOR=$(checkpoint_for_phase $((PHASE - 1)))
    if [[ -f "$PRIOR" ]]; then
      RESUME_ARGS=("--resume" "$PRIOR")
    else
      die "Cannot start phase ${PHASE}: required prior checkpoint is missing: ${PRIOR}. For phase 5 this is usually core/phase_4.pt. Run ./run_curriculum.sh --start-phase $((PHASE-1)) --end-phase $((PHASE-1)) first."
    fi
  fi

  echo ""
  log "============================================================"
  log "  PHASE ${PHASE}: Training"
  log "============================================================"

  "$PYTHON" train.py \
    --phase "$PHASE" \
    --output "$OUTPUT" \
    "${RESUME_ARGS[@]}" \
    "${TRAIN_ARGS[@]}"

  echo ""
  log "============================================================"
  log "  PHASE ${PHASE}: Eval"
  log "============================================================"

  SCORE=$(run_eval_get_score "$OUTPUT")

  echo ""
  log "  Phase ${PHASE} shaped avg score: ${SCORE}"
  log "  Pass threshold:                  ${PASS_THRESHOLD}"

  if passes_threshold "$SCORE"; then
    log "  PASS ✓ — proceeding to next phase."
    PREV_CHECKPOINT="$OUTPUT"
  else
    echo ""
    echo "============================================================"
    echo "  FAIL — Phase ${PHASE} score ${SCORE} < threshold ${PASS_THRESHOLD}"
    echo "============================================================"
    echo ""
    echo "Full eval output:"
    cat /tmp/bdh_eval_out.txt
    echo ""
    echo "Suggestions:"
    echo "  - Increase epochs:      --epochs 60"
    echo "  - Lower learning rate:  add --lr 2e-4 to train.py args"
    echo "  - Check training data for phase ${PHASE}"
    echo "  - Re-run this phase:    ./run_curriculum.sh --start-phase ${PHASE} --end-phase ${PHASE}"
    exit 1
  fi

done

echo ""
echo "============================================================"
echo "  ALL PHASES COMPLETE (${START_PHASE}–${END_PHASE})"
echo "  Final checkpoint: $(checkpoint_for_phase $END_PHASE)"
echo "============================================================"
echo ""
