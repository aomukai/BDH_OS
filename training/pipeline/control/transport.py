from __future__ import annotations

import json
import subprocess
from typing import Any, Callable

from .ledger import ControlLedger, LedgerError, canonical_json


class SshControlTransport:
    def __init__(
        self,
        ledger: ControlLedger,
        *,
        ssh_target: str = "ninereeds-trainbox-control",
        timeout_seconds: int = 30,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.ledger = ledger
        self.ssh_target = ssh_target
        self.timeout_seconds = timeout_seconds
        self.runner = runner

    def dispatch(self, plan_id: str, *, wake: bool = True) -> dict[str, Any]:
        plan = self.ledger.plan(plan_id)
        if plan is None:
            raise LedgerError(f"unknown local plan: {plan_id}")
        command = "submit-and-wake" if wake else "submit-plan"
        response = self._ssh(command, input_data=canonical_json(plan) + b"\n")
        if response.get("plan_id") != plan_id:
            raise LedgerError("trainbox acknowledged a different plan_id")
        if response.get("plan_sha256") != plan["content_sha256"]:
            raise LedgerError("trainbox acknowledged a different plan hash")
        return response

    def sync(self, plan_id: str) -> dict[str, Any]:
        response = self._ssh(f"show {plan_id}")
        local_plan = self.ledger.plan(plan_id)
        remote_plan = response.get("plan")
        if local_plan is None or remote_plan is None:
            raise LedgerError("plan is missing during synchronization")
        if canonical_json(local_plan) != canonical_json(remote_plan):
            raise LedgerError("remote plan differs from the local authoritative plan")
        receipt = response.get("receipt")
        report = response.get("report")
        if report is not None:
            if not isinstance(receipt, dict) or not isinstance(report, dict):
                raise LedgerError("remote terminal result is malformed")
            self.ledger.accept_remote_report(plan_id, receipt, report)
        elif isinstance(receipt, dict) and receipt.get("status") == "dead_letter":
            self.ledger.accept_remote_dead_letter(plan_id, receipt)
        return response

    def snapshot(self) -> dict[str, Any]:
        return self._ssh("snapshot")

    def _ssh(
        self,
        remote_command: str,
        *,
        input_data: bytes | None = None,
    ) -> dict[str, Any]:
        completed = self.runner(
            [
                "/usr/bin/ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                f"ConnectTimeout={self.timeout_seconds}",
                self.ssh_target,
                remote_command,
            ],
            input=input_data,
            capture_output=True,
            timeout=self.timeout_seconds + 5,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        try:
            response = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise LedgerError(
                f"trainbox returned invalid JSON: {(stderr or stdout)[-1000:]}"
            ) from exc
        if completed.returncode != 0 or not response.get("ok"):
            raise LedgerError(
                f"trainbox control command failed: {response.get('error') or stderr}"
            )
        return response
