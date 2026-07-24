from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ledger import ControlLedger, LedgerError


DEFAULT_ROOT = Path("training/pipeline/msm/control")


def read_object(handle) -> dict:
    value = json.load(handle)
    if not isinstance(value, dict):
        raise LedgerError("input must contain a JSON object")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Ninereeds durable control ledger.")
    result.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    commands = result.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-plan")
    create.add_argument("--kind", required=True)
    create.add_argument("--mode", choices=("shadow", "live"), required=True)
    create.add_argument("--created-by", required=True)
    create.add_argument("--payload-file", type=Path)
    create.add_argument("--plan-id")
    create.add_argument("--max-attempts", type=int, default=3)
    create.add_argument("--allow-weight-updates", action="store_true")
    create.add_argument("--allow-checkpoint-promotion", action="store_true")
    create.add_argument("--allow-auto-advance", action="store_true")

    commands.add_parser("import-plan")
    commands.add_parser("snapshot")
    show = commands.add_parser("show")
    show.add_argument("plan_id")
    return result


def main() -> int:
    args = parser().parse_args()
    ledger = ControlLedger(args.root)
    try:
        if args.command == "create-plan":
            if args.payload_file:
                with args.payload_file.open(encoding="utf-8") as handle:
                    payload = read_object(handle)
            else:
                payload = read_object(sys.stdin)
            result = ledger.create_plan(
                kind=args.kind,
                mode=args.mode,
                payload=payload,
                created_by=args.created_by,
                plan_id=args.plan_id,
                max_attempts=args.max_attempts,
                authorization={
                    "allow_weight_updates": args.allow_weight_updates,
                    "allow_checkpoint_promotion": args.allow_checkpoint_promotion,
                    "allow_auto_advance": args.allow_auto_advance,
                },
            )
        elif args.command == "import-plan":
            result = ledger.import_plan(read_object(sys.stdin))
        elif args.command == "snapshot":
            result = ledger.snapshot()
        else:
            result = {
                "plan": ledger.plan(args.plan_id),
                "receipt": ledger.receipt(args.plan_id),
                "report": ledger.report(args.plan_id),
            }
    except (LedgerError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
