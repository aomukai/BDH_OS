from __future__ import annotations

import argparse
import io
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, BinaryIO, Callable

from .ledger import ControlLedger, LedgerError, MAX_ENVELOPE_BYTES


DEFAULT_CONTROL_ROOT = Path("/home/aomukai/.local/state/ninereeds-control")
WORKER_SERVICE = "ninereeds-trainbox-worker.service"


def wake_worker() -> dict[str, Any]:
    completed = subprocess.run(
        ["/usr/bin/systemctl", "--user", "start", "--no-block", WORKER_SERVICE],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    return {
        "ok": completed.returncode == 0,
        "service": WORKER_SERVICE,
        "returncode": completed.returncode,
        "error": completed.stderr.strip()[:1000] or None,
    }


def read_limited_json(stream: BinaryIO) -> dict[str, Any]:
    body = stream.read(MAX_ENVELOPE_BYTES + 1)
    if len(body) > MAX_ENVELOPE_BYTES:
        raise LedgerError("remote envelope exceeds the size limit")
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LedgerError("remote envelope is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise LedgerError("remote envelope must be a JSON object")
    return value


def handle_command(
    original_command: str,
    *,
    ledger: ControlLedger,
    stdin: BinaryIO,
    wake: Callable[[], dict[str, Any]] = wake_worker,
) -> tuple[int, dict[str, Any]]:
    try:
        parts = shlex.split(original_command)
    except ValueError:
        return 126, {"ok": False, "error": "malformed remote command"}
    if parts == ["ping"]:
        return 0, {"ok": True, "role": "trainbox-control", "reply": "pong"}
    if parts in (["submit-plan"], ["submit-and-wake"]):
        plan = ledger.import_plan(read_limited_json(stdin))
        response: dict[str, Any] = {
            "ok": True,
            "plan_id": plan["plan_id"],
            "plan_sha256": plan["content_sha256"],
            "receipt": ledger.receipt(plan["plan_id"]),
        }
        if parts == ["submit-and-wake"]:
            response["wake"] = wake()
            if not response["wake"]["ok"]:
                response["ok"] = False
                return 1, response
        return 0, response
    if parts == ["snapshot"]:
        return 0, {"ok": True, "snapshot": ledger.snapshot()}
    if len(parts) == 2 and parts[0] == "show":
        plan_id = parts[1]
        plan = ledger.plan(plan_id)
        if plan is None:
            return 4, {"ok": False, "error": "unknown plan", "plan_id": plan_id}
        return 0, {
            "ok": True,
            "plan": plan,
            "receipt": ledger.receipt(plan_id),
            "report": ledger.report(plan_id),
        }
    return 126, {
        "ok": False,
        "error": "command not permitted",
        "allowed": ["ping", "submit-plan", "submit-and-wake", "snapshot", "show PLAN_ID"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Restricted Ninereeds trainbox control boundary.")
    parser.add_argument("command", choices=("restricted", "self-test"))
    parser.add_argument("--control-root", type=Path, default=DEFAULT_CONTROL_ROOT)
    args = parser.parse_args()
    ledger = ControlLedger(args.control_root)
    if args.command == "self-test":
        status, response = handle_command(
            "ping",
            ledger=ledger,
            stdin=io.BytesIO(),
            wake=lambda: {"ok": True, "service": "test"},
        )
        assert status == 0 and response["reply"] == "pong"
        status, _ = handle_command(
            "bash -c id",
            ledger=ledger,
            stdin=io.BytesIO(),
        )
        assert status == 126
        print("self-test: OK")
        return 0

    original = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    try:
        status, response = handle_command(
            original,
            ledger=ledger,
            stdin=sys.stdin.buffer,
        )
    except (LedgerError, OSError, subprocess.SubprocessError) as exc:
        status, response = 2, {"ok": False, "error": str(exc)}
    print(json.dumps(response, ensure_ascii=False, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
