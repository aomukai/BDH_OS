from __future__ import annotations

import json
import subprocess
import threading
import time
from typing import Any

from lab.backend.config import LabConfig
from training.pipeline.control.ledger import ControlLedger


SNAPSHOT_SCHEMA = "ninereeds_control_snapshot_v1"


class ControlStatusService:
    """Return bounded ledger metadata without exposing plan payloads."""

    def __init__(self, config: LabConfig) -> None:
        self.config = config
        self._lock = threading.Lock()
        self._cached: dict[str, Any] | None = None
        self._cached_at = 0.0

    def status(self, *, force: bool = False) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            if (
                not force
                and self._cached is not None
                and now - self._cached_at < self.config.control_status_cache_seconds
            ):
                result = dict(self._cached)
                result["cache_age_seconds"] = round(now - self._cached_at, 1)
                return result
            result = {
                "schema_version": "ninereeds_lab_control_status_v1",
                "observed_at": now,
                "local": self._local_snapshot(),
                "trainbox": self._remote_snapshot(),
                "services": {
                    "supervisor": self._service_active(
                        "ninereeds-orchestrator-supervisor.service"
                    ),
                    "supervisor_path": self._service_active(
                        "ninereeds-orchestrator-supervisor.path"
                    ),
                    "supervisor_timer": self._service_active(
                        "ninereeds-orchestrator-supervisor.timer"
                    ),
                },
            }
            result["ok"] = bool(
                result["local"]["ok"]
                and result["trainbox"]["ok"]
                and result["services"]["supervisor_path"]
                and result["services"]["supervisor_timer"]
            )
            result["cache_age_seconds"] = 0.0
            self._cached = result
            self._cached_at = now
            return dict(result)

    def _local_snapshot(self) -> dict[str, Any]:
        try:
            snapshot = ControlLedger(self.config.orchestrator_control_root).snapshot()
            return {"ok": True, **self._sanitize_snapshot(snapshot)}
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "counts": {}, "latest_receipts": []}

    def _remote_snapshot(self) -> dict[str, Any]:
        target = self.config.trainbox_control_ssh_target
        if not target:
            return {
                "ok": False,
                "reachable": False,
                "error": "Trainbox control target is not configured.",
                "counts": {},
                "latest_receipts": [],
            }
        started = time.monotonic()
        try:
            completed = subprocess.run(
                [
                    "/usr/bin/ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    f"ConnectTimeout={self.config.control_status_timeout_seconds}",
                    target,
                    "snapshot",
                ],
                text=True,
                capture_output=True,
                timeout=self.config.control_status_timeout_seconds + 2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "ok": False,
                "reachable": False,
                "error": str(exc),
                "counts": {},
                "latest_receipts": [],
            }
        latency_ms = round((time.monotonic() - started) * 1000)
        if completed.returncode != 0:
            return {
                "ok": False,
                "reachable": False,
                "latency_ms": latency_ms,
                "error": (completed.stderr.strip() or "Control snapshot failed.")[:500],
                "counts": {},
                "latest_receipts": [],
            }
        try:
            envelope = json.loads(completed.stdout)
            snapshot = envelope["snapshot"]
            sanitized = self._sanitize_snapshot(snapshot)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return {
                "ok": False,
                "reachable": True,
                "latency_ms": latency_ms,
                "error": f"Invalid control snapshot: {exc}",
                "counts": {},
                "latest_receipts": [],
            }
        return {
            "ok": bool(envelope.get("ok")),
            "reachable": True,
            "latency_ms": latency_ms,
            **sanitized,
        }

    @staticmethod
    def _sanitize_snapshot(snapshot: Any) -> dict[str, Any]:
        if not isinstance(snapshot, dict) or snapshot.get("schema_version") != SNAPSHOT_SCHEMA:
            raise ValueError("unexpected control snapshot schema")
        counts = snapshot.get("counts")
        receipts = snapshot.get("latest_receipts")
        if not isinstance(counts, dict) or not isinstance(receipts, list):
            raise ValueError("control snapshot fields are malformed")
        safe_counts: dict[str, int] = {}
        for key, value in counts.items():
            if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("control snapshot counts are malformed")
            safe_counts[key] = value
        safe_receipts = []
        allowed = {
            "plan_id",
            "status",
            "attempt_count",
            "created_at",
            "updated_at",
            "claimed_by",
            "lease_expires_at",
            "report_id",
            "last_error",
        }
        for receipt in receipts[:12]:
            if not isinstance(receipt, dict):
                raise ValueError("control receipt is malformed")
            safe_receipts.append({key: receipt.get(key) for key in allowed})
        return {
            "schema_version": SNAPSHOT_SCHEMA,
            "counts": safe_counts,
            "latest_receipts": safe_receipts,
        }

    @staticmethod
    def _service_active(unit: str) -> bool:
        try:
            result = subprocess.run(
                ["/usr/bin/systemctl", "--user", "is-active", "--quiet", unit],
                capture_output=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0
