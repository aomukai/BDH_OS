from __future__ import annotations

import json
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any

from lab.backend.config import LabConfig


class TrainboxStatusService:
    """Fetch and validate the trainbox's restricted read-only status document."""

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
                and now - self._cached_at < self.config.trainbox_status_cache_seconds
            ):
                return self._with_cache_age(self._cached, now)

            result = self._fetch(now)
            self._cached = result
            self._cached_at = now
            return self._with_cache_age(result, now)

    def _fetch(self, observed_at: float) -> dict[str, Any]:
        target = self.config.trainbox_ssh_target
        if not target:
            return self._error("disabled", "Trainbox status target is not configured.", observed_at)

        started = time.monotonic()
        try:
            completed = subprocess.run(
                [
                    "/usr/bin/ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    f"ConnectTimeout={self.config.trainbox_status_timeout_seconds}",
                    target,
                    "status",
                ],
                text=True,
                capture_output=True,
                timeout=self.config.trainbox_status_timeout_seconds + 2,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return self._error("timeout", "Trainbox status request timed out.", observed_at)
        except OSError as exc:
            return self._error("ssh_error", str(exc), observed_at)

        latency_ms = round((time.monotonic() - started) * 1000)
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "restricted SSH status command failed"
            return self._error(
                "unreachable",
                detail[:500],
                observed_at,
                latency_ms=latency_ms,
            )
        if len(completed.stdout) > 1024 * 1024:
            return self._error(
                "invalid_status",
                "Trainbox status document exceeds one megabyte.",
                observed_at,
                latency_ms=latency_ms,
            )
        try:
            document = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return self._error(
                "invalid_json",
                "Trainbox returned invalid JSON.",
                observed_at,
                latency_ms=latency_ms,
            )

        validation_error = self._validate(document)
        if validation_error:
            return self._error(
                "invalid_status",
                validation_error,
                observed_at,
                latency_ms=latency_ms,
            )

        generated_at_epoch = self._timestamp(document["generated_at"])
        age_seconds = max(0.0, observed_at - generated_at_epoch)
        return {
            "ok": bool(document.get("ok")),
            "reachable": True,
            "observed_at": observed_at,
            "latency_ms": latency_ms,
            "generated_at": document["generated_at"],
            "age_seconds": round(age_seconds, 1),
            "stale": age_seconds > self.config.trainbox_status_stale_seconds,
            "stale_after_seconds": self.config.trainbox_status_stale_seconds,
            "error": None,
            "status": document,
        }

    @staticmethod
    def _validate(document: Any) -> str | None:
        if not isinstance(document, dict):
            return "Trainbox status must be a JSON object."
        if document.get("schema_version") != "ninereeds_trainbox_status_v1":
            return "Unexpected trainbox status schema."
        if document.get("role") != "trainbox":
            return "Status role is not trainbox."
        if not isinstance(document.get("generated_at"), str):
            return "Trainbox status has no generated_at timestamp."
        try:
            TrainboxStatusService._timestamp(document["generated_at"])
        except ValueError:
            return "Trainbox generated_at timestamp is invalid."
        capabilities = document.get("capabilities")
        if not isinstance(capabilities, dict):
            return "Trainbox status has no capability boundary."
        if capabilities.get("read_only_status") is not True:
            return "Trainbox status is not marked read-only."
        if capabilities.get("training_dispatch") is not False:
            return "Trainbox status unexpectedly permits training dispatch."
        for section in ("repo", "pipeline", "gpu", "services", "system"):
            if not isinstance(document.get(section), dict):
                return f"Trainbox status is missing the {section} section."
        return None

    @staticmethod
    def _timestamp(value: str) -> float:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()

    def _error(
        self,
        code: str,
        message: str,
        observed_at: float,
        *,
        latency_ms: int | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "reachable": False,
            "observed_at": observed_at,
            "latency_ms": latency_ms,
            "generated_at": None,
            "age_seconds": None,
            "stale": True,
            "stale_after_seconds": self.config.trainbox_status_stale_seconds,
            "error": {"code": code, "message": message},
            "status": None,
        }

    @staticmethod
    def _with_cache_age(result: dict[str, Any], now: float) -> dict[str, Any]:
        copy = dict(result)
        copy["cache_age_seconds"] = round(max(0.0, now - float(result["observed_at"])), 1)
        return copy
