#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONTROL_ROOT="${NINEREEDS_ORCHESTRATOR_CONTROL_ROOT:-/home/aomukai/.local/state/ninereeds-orchestrator-control}"
SSH_TARGET="${NINEREEDS_TRAINBOX_CONTROL_TARGET:-ninereeds-trainbox-control}"

cd "$ROOT"

case "${1:-}" in
  --status-only)
    echo "== Workstation control ledger =="
    python3 -m training.pipeline.control.cli --root "$CONTROL_ROOT" snapshot
    echo
    echo "== Trainbox control ledger =="
    /usr/bin/ssh -o BatchMode=yes -o ConnectTimeout=8 "$SSH_TARGET" snapshot
    ;;
  ""|--orchestrator)
    python3 -m training.pipeline.control.orchestrator_supervisor \
      --control-root "$CONTROL_ROOT" \
      --repo "$ROOT" \
      --ssh-target "$SSH_TARGET"
    ;;
  *)
    echo "Usage: training/pipeline/start.sh [--status-only|--orchestrator]" >&2
    exit 2
    ;;
esac
