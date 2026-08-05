"""Mission Hub-owned restricted SSH dispatch transport."""

from __future__ import annotations

import json
import subprocess
from typing import Any, Callable

from .config import ConfigBundle
from .errors import ProtocolError
from .jsonutil import canonical_json


Runner = Callable[..., subprocess.CompletedProcess[str]]


class SSHDispatcher:
    def __init__(self, bundle: ConfigBundle, *, runner: Runner = subprocess.run):
        self.bundle = bundle
        self.runner = runner

    def execute(self, machine_id: str, envelope: dict[str, Any]) -> dict[str, Any]:
        machine = self.bundle.machines.get(machine_id)
        if machine is None or machine["transport"] != "restricted_ssh" or not machine["ssh_target"]:
            raise ProtocolError(f"machine {machine_id} has no restricted SSH transport")
        completed = self.runner(
            ["ssh", "--", machine["ssh_target"], "execute"],
            input=canonical_json(envelope),
            capture_output=True,
            text=True,
            timeout=machine["dispatch_timeout_seconds"],
            check=False,
        )
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProtocolError(f"trainbox returned invalid JSON (exit {completed.returncode})") from exc
        if completed.returncode != 0:
            message = response.get("message", "unknown trainbox error") if isinstance(response, dict) else "unknown trainbox error"
            raise ProtocolError(f"trainbox refused execution: {message}")
        if not isinstance(response, dict):
            raise ProtocolError("trainbox result must be a JSON object")
        return response
