from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .campaign_controller import CampaignController, CampaignError, CampaignStateStore
from .ledger import ControlLedger, LedgerError


DEFAULT_REPO = Path("/home/aomukai/Ninereeds")
DEFAULT_ROOT = Path("/home/aomukai/.local/state/ninereeds-orchestrator-control")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the autonomous Ninereeds campaign.")
    parser.add_argument("--control-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("--spec-file", type=Path)
    commands.add_parser("status")
    pause = commands.add_parser("pause")
    pause.add_argument("--reason", default="Paused by the operator.")
    resume = commands.add_parser("resume")
    resume.add_argument("--reason", default="Resumed by the operator.")
    commands.add_parser("recover")
    close = commands.add_parser("close")
    close.add_argument("--reason", default="Closed by the operator.")
    commands.add_parser("reconcile")
    args = parser.parse_args()

    ledger = ControlLedger(args.control_root)
    controller = CampaignController(ledger, repo_root=args.repo)
    try:
        if args.command == "start":
            raw = (
                json.loads(args.spec_file.read_text(encoding="utf-8"))
                if args.spec_file
                else json.load(sys.stdin)
            )
            if not isinstance(raw, dict):
                raise CampaignError("campaign spec must be an object")
            duration = raw.pop("duration_hours", None)
            if duration is not None:
                if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration <= 0:
                    raise CampaignError("duration_hours must be positive")
                raw["deadline_at"] = (
                    datetime.now(timezone.utc) + timedelta(hours=float(duration))
                ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            result = controller.start(**raw)
        elif args.command == "status":
            result = CampaignStateStore(args.control_root).read()
        elif args.command == "pause":
            result = controller.set_status("paused", args.reason)
        elif args.command == "resume":
            result = controller.set_status("running", args.reason)
        elif args.command == "recover":
            result = controller.recover_repairable_blocker()
        elif args.command == "close":
            result = controller.close(args.reason)
        else:
            result = controller.reconcile()
    except (CampaignError, LedgerError, OSError, json.JSONDecodeError, TypeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
