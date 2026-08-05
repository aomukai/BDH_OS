"""Mission Hub-owned restricted SSH dispatch transport."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Callable

from .artifacts import ArtifactFiles
from .config import ConfigBundle
from .errors import ProtocolError, SafetyError
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

    def put_artifact(self, machine_id: str, deployment: dict[str, Any], artifact: dict[str, Any]) -> str:
        machine = self._restricted_machine(machine_id)
        source = ArtifactFiles(self.bundle, "mission-hub").verified_source(
            artifact["uri"], sha256=artifact["sha256"], byte_size=artifact["byte_size"]
        )
        command = [
            "ssh", "--", machine["ssh_target"], "artifact-put",
            artifact["id"], artifact["kind"], artifact["sha256"], str(artifact["byte_size"]),
            self.bundle.sha256, deployment["id"],
        ]
        with source.open("rb") as handle:
            completed = self.runner(
                command, stdin=handle, capture_output=True, text=False,
                timeout=machine["artifact_transfer_timeout_seconds"], check=False,
            )
        try:
            response = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolError(f"trainbox returned invalid artifact response (exit {completed.returncode})") from exc
        if completed.returncode != 0 or not isinstance(response, dict) or not response.get("ok"):
            message = response.get("message", "unknown trainbox error") if isinstance(response, dict) else "unknown trainbox error"
            raise ProtocolError(f"trainbox refused artifact: {message}")
        response_uri = response.get("uri")
        if not isinstance(response_uri, str):
            raise ProtocolError("trainbox artifact receipt has no URI")
        response_path = Path(os.path.normpath(response_uri))
        allowed_roots = [Path(machine["state_root"]), *(Path(value) for value in machine["artifact_roots"])]
        if not response_path.is_absolute() or not any(response_path == root or root in response_path.parents for root in allowed_roots):
            raise ProtocolError("trainbox artifact receipt URI is outside configured roots")
        expected = {
            "ok": True, "artifact_id": artifact["id"], "kind": artifact["kind"],
            "sha256": artifact["sha256"], "byte_size": artifact["byte_size"],
            "uri": response_uri, "config_sha256": self.bundle.sha256,
            "deployment_id": deployment["id"],
        }
        if response != expected:
            raise ProtocolError("trainbox artifact receipt does not match the request")
        return response["uri"]

    def get_artifact(self, machine_id: str, deployment: dict[str, Any], artifact: dict[str, Any]) -> str:
        machine = self._restricted_machine(machine_id)
        if any(character.isspace() for character in artifact["uri"]):
            raise SafetyError("restricted artifact export URI may not contain whitespace")
        files = ArtifactFiles(self.bundle, "mission-hub")
        destination = files.object_path(artifact["sha256"])
        if destination.exists():
            files.verify(destination, artifact["sha256"], artifact["byte_size"])
            return str(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".retrieve-", dir=destination.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            completed = self.runner(
                [
                    "ssh", "--", machine["ssh_target"], "artifact-get",
                    artifact["id"], artifact["kind"], artifact["sha256"], str(artifact["byte_size"]),
                    self.bundle.sha256, deployment["id"], artifact["uri"],
                ],
                stdout=temporary, stderr=subprocess.PIPE, text=False,
                timeout=machine["artifact_transfer_timeout_seconds"], check=False,
            )
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            if completed.returncode != 0:
                message = completed.stderr.decode("utf-8", errors="replace").strip()
                raise ProtocolError(f"trainbox artifact export failed: {message}")
            files.verify(temporary_path, artifact["sha256"], artifact["byte_size"])
            os.chmod(temporary_path, 0o440)
            os.replace(temporary_path, destination)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        return str(destination)

    def _restricted_machine(self, machine_id: str) -> dict[str, Any]:
        machine = self.bundle.machines.get(machine_id)
        if machine is None or machine["transport"] != "restricted_ssh" or not machine["ssh_target"]:
            raise ProtocolError(f"machine {machine_id} has no restricted SSH transport")
        return machine
