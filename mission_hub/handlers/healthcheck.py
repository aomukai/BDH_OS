"""Bounded read-only commissioning handler."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class HealthcheckHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "succeeded",
            "hostname": socket.gethostname(),
            "observed_at": _utc_now(),
            "capabilities": sorted(set(context.get("capabilities", []))),
            "release": None,
            "disk": None,
            "gpu": None,
            "artifacts": [],
        }
        if payload.get("include_release", True):
            result["release"] = context.get("deployment")
        if payload.get("include_disk", True):
            root = Path(context.get("state_root", "/"))
            existing = root if root.exists() else root.parent
            usage = shutil.disk_usage(existing)
            result["disk"] = {
                "path": str(existing),
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
            }
        if payload.get("include_gpu", True):
            result["gpu"] = self._gpu_observation()
        return result

    @staticmethod
    def _gpu_observation() -> list[dict[str, Any]] | None:
        executable = shutil.which("nvidia-smi")
        if executable is None:
            return None
        command = [
            executable,
            "--query-gpu=index,name,memory.total,memory.used,temperature.gpu,utilization.gpu",
            "--format=csv,noheader,nounits",
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=5, check=True)
        except (OSError, subprocess.SubprocessError):
            return None
        result = []
        for line in completed.stdout.splitlines():
            fields = [field.strip() for field in line.split(",")]
            if len(fields) != 6:
                continue
            result.append(
                {
                    "index": int(fields[0]),
                    "name": fields[1],
                    "memory_total_mib": int(fields[2]),
                    "memory_used_mib": int(fields[3]),
                    "temperature_c": int(fields[4]),
                    "utilization_percent": int(fields[5]),
                }
            )
        return result
