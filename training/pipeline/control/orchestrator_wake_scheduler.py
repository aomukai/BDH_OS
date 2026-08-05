from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from .campaign_controller import CampaignStateStore, _parse_time
from .ledger import ControlLedger, LedgerError, TERMINAL_RECEIPT_STATUSES, utc_now
from .orchestrator_supervisor import DEFAULT_CONTROL_ROOT
from .transport import SshControlTransport


SUPERVISOR_SERVICE = "ninereeds-orchestrator-supervisor.service"
POST_TRAINING_DELAY_SECONDS = 15 * 60
RETRY_INTERVAL_SECONDS = 15 * 60


class OrchestratorWakeScheduler:
    """Lightweight clock that wakes the full supervisor only when work is due."""

    def __init__(
        self,
        ledger: ControlLedger,
        transport: SshControlTransport,
        *,
        delay_seconds: int = POST_TRAINING_DELAY_SECONDS,
        retry_seconds: int = RETRY_INTERVAL_SECONDS,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.ledger = ledger
        self.transport = transport
        self.delay_seconds = delay_seconds
        self.retry_seconds = retry_seconds
        self.runner = runner
        self.campaign_store = CampaignStateStore(ledger.root)
        self.state_path = ledger.root / "scheduler/state.json"
        self.status_path = ledger.root / "scheduler/status.json"

    def run_once(self, *, now: float | None = None) -> dict[str, Any]:
        timestamp = time.time() if now is None else now
        result = self._evaluate(timestamp)
        self._write_json(
            self.status_path,
            {"observed_at": timestamp, **result},
        )
        return result

    def _evaluate(self, timestamp: float) -> dict[str, Any]:
        campaign = self.campaign_store.read()
        if campaign is None or campaign["status"] not in {
            "running",
            "waiting",
            "blocked",
        }:
            return {"action": "idle", "next_wake_at": None}

        plan_id = campaign["current_plan_id"]
        plan = self.ledger.plan(plan_id)
        receipt = self.ledger.receipt(plan_id)
        if plan is None or receipt is None:
            return self._trigger(plan_id, "missing_local_state", timestamp)

        if (
            plan["kind"] != "strategic_decision"
            and receipt["status"] not in TERMINAL_RECEIPT_STATUSES
        ):
            try:
                self.transport.sync(plan_id)
            except LedgerError:
                return self._trigger(plan_id, "remote_sync_failed", timestamp)
            receipt = self.ledger.receipt(plan_id)

        if receipt is None:
            return self._trigger(plan_id, "missing_receipt", timestamp)
        if receipt["status"] not in TERMINAL_RECEIPT_STATUSES:
            if plan["kind"] == "strategic_decision":
                return self._trigger(plan_id, "strategic_plan_ready", timestamp)
            return {"action": "waiting_for_trainbox", "plan_id": plan_id}

        report = self.ledger.report(plan_id)
        if report is None:
            return self._trigger(plan_id, "terminal_report_missing", timestamp)
        next_wake_at = _parse_time(report["completed_at"]) + self.delay_seconds
        prior = self._read_state()
        if prior.get("plan_id") != plan_id:
            return self._trigger(
                plan_id,
                "terminal_plan_ready",
                timestamp,
                retry_at=next_wake_at,
            )
        if timestamp < next_wake_at:
            return {
                "action": "waiting_for_training_cooldown",
                "plan_id": plan_id,
                "next_wake_at": next_wake_at,
                "next_wake_in_seconds": max(1, int(next_wake_at - timestamp + 0.999)),
            }
        return self._trigger(plan_id, "training_cooldown_complete", timestamp)

    def _trigger(
        self,
        plan_id: str,
        reason: str,
        timestamp: float,
        *,
        retry_at: float | None = None,
    ) -> dict[str, Any]:
        prior = self._read_state()
        prior_retry_at = prior.get("next_retry_at_epoch")
        if not isinstance(prior_retry_at, (int, float)):
            prior_retry_at = (
                prior.get("triggered_at_epoch", 0) + self.retry_seconds
                if isinstance(prior.get("triggered_at_epoch"), (int, float))
                else 0
            )
        if (
            prior.get("plan_id") == plan_id
            and timestamp < prior_retry_at
        ):
            return {
                "action": "retry_throttled",
                "plan_id": plan_id,
                "reason": reason,
                "next_wake_at": prior_retry_at,
                "next_wake_in_seconds": max(
                    1, int(prior_retry_at - timestamp + 0.999)
                ),
            }
        completed = self.runner(
            [
                "/usr/bin/systemctl",
                "--user",
                "start",
                "--no-block",
                SUPERVISOR_SERVICE,
            ],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            self._record_timing(
                "orchestrator.wake_failed",
                timestamp,
                plan_id=plan_id,
                reason=reason,
                status="failed",
            )
            return {
                "action": "trigger_failed",
                "plan_id": plan_id,
                "reason": reason,
                "error": completed.stderr.strip()[:1000],
            }
        self._write_state(
            {
                "plan_id": plan_id,
                "reason": reason,
                "triggered_at": utc_now(timestamp),
                "triggered_at_epoch": timestamp,
                "next_retry_at_epoch": (
                    retry_at
                    if retry_at is not None and retry_at > timestamp
                    else timestamp + self.retry_seconds
                ),
            }
        )
        self._record_timing(
            "orchestrator.wake_requested",
            timestamp,
            plan_id=plan_id,
            reason=reason,
            status="requested",
        )
        return {
            "action": "supervisor_triggered",
            "plan_id": plan_id,
            "reason": reason,
            "next_wake_at": (
                retry_at
                if retry_at is not None and retry_at > timestamp
                else timestamp + self.retry_seconds
            ),
        }

    def _record_timing(
        self,
        event: str,
        timestamp: float,
        **fields: Any,
    ) -> None:
        try:
            self.ledger.timing.record(
                event,
                "wake-scheduler",
                timestamp=timestamp,
                **fields,
            )
        except (OSError, ValueError, TypeError):
            pass

    def _read_state(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _write_state(self, value: dict[str, Any]) -> None:
        self._write_json(self.state_path, value)

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=path.parent
        )
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Wake the Ninereeds orchestrator after the training cooldown."
    )
    parser.add_argument("--control-root", type=Path, default=DEFAULT_CONTROL_ROOT)
    parser.add_argument("--ssh-target", default="ninereeds-trainbox-control")
    args = parser.parse_args()
    ledger = ControlLedger(args.control_root)
    result = OrchestratorWakeScheduler(
        ledger,
        SshControlTransport(ledger, ssh_target=args.ssh_target),
    ).run_once()
    print(json.dumps(result, sort_keys=True))
    return 1 if result["action"] == "trigger_failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
