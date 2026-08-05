"""Versioned machine-boundary envelopes.

Transport authentication is supplied by the restricted SSH boundary. Envelope
hashes detect truncation/corruption; the lease token authenticates run updates
at the Mission Hub and is never echoed in result payloads.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from .config import ConfigBundle
from .errors import ProtocolError
from .jsonutil import canonical_json, content_hash


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def build_job_envelope(
    bundle: ConfigBundle,
    leased: dict[str, Any],
    lease_token: str,
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    deployment = leased["deployment"]
    body: dict[str, Any] = {
        "schema_version": "ninereeds_job_envelope_v1",
        "protocol_version": bundle.base["protocol"]["version"],
        "job": {
            "id": leased["id"],
            "type": leased["job_type"],
            "version": leased["job_version"],
            "input": json.loads(leased["input_json"]),
            "input_sha256": leased["input_sha256"],
        },
        "run": {"id": leased["run_id"], "attempt": leased["attempt"]},
        "lease": {"token": lease_token, "expires_at": leased["lease_expires_at"]},
        "deployment": {
            "id": deployment["id"],
            "machine_id": deployment["machine_id"],
            "role": deployment["role"],
            "release_id": deployment["release_id"],
            "source_sha256": deployment["source_sha256"],
            "environment_sha256": deployment["environment_sha256"],
        },
        "config_snapshot": {"id": leased["config_snapshot_id"], "sha256": bundle.sha256},
        "artifacts": artifacts,
        "issued_at": _utc_now(),
    }
    body["envelope_hash"] = content_hash(body)
    encoded = canonical_json(body).encode("utf-8")
    if len(encoded) > bundle.base["protocol"]["max_envelope_bytes"]:
        raise ProtocolError("job envelope exceeds configured maximum size")
    return body


def validate_job_envelope(bundle: ConfigBundle, envelope: dict[str, Any], *, machine_id: str, deployment: dict[str, Any]) -> None:
    required = {"schema_version", "protocol_version", "job", "run", "lease", "deployment", "config_snapshot", "artifacts", "issued_at", "envelope_hash"}
    if set(envelope) != required:
        raise ProtocolError("job envelope fields do not match protocol v1")
    if envelope["schema_version"] != "ninereeds_job_envelope_v1":
        raise ProtocolError("unsupported envelope schema")
    if envelope["protocol_version"] != bundle.base["protocol"]["version"]:
        raise ProtocolError("protocol version mismatch")
    supplied_hash = envelope["envelope_hash"]
    body = {key: value for key, value in envelope.items() if key != "envelope_hash"}
    if supplied_hash != content_hash(body):
        raise ProtocolError("job envelope hash mismatch")
    if envelope["deployment"]["machine_id"] != machine_id:
        raise ProtocolError("job envelope targets a different machine")
    for key in ("id", "release_id", "source_sha256", "environment_sha256"):
        if envelope["deployment"].get(key) != deployment.get(key):
            raise ProtocolError(f"deployment mismatch: {key}")
    if envelope["config_snapshot"]["sha256"] != bundle.sha256:
        raise ProtocolError("configuration snapshot hash mismatch")
    job_type = envelope["job"].get("type")
    definition = bundle.jobs.get(job_type)
    machine = bundle.machines.get(machine_id)
    if definition is None or not definition["enabled"]:
        raise ProtocolError(f"job type is not enabled: {job_type}")
    if machine is None or job_type not in machine["allowed_job_types"]:
        raise ProtocolError("job type is not allowed on this machine")
    if definition["executor_role"] != machine["role"]:
        raise ProtocolError("executor role mismatch")
    if content_hash(envelope["job"]["input"]) != envelope["job"]["input_sha256"]:
        raise ProtocolError("job input hash mismatch")
    for artifact in envelope["artifacts"]:
        if not isinstance(artifact, dict) or set(artifact) != {"id", "kind", "sha256", "byte_size", "lifecycle", "manifest", "uri"}:
            raise ProtocolError("invalid artifact reference")


def build_result_envelope(envelope: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    body = {
        "schema_version": "ninereeds_result_envelope_v1",
        "protocol_version": envelope["protocol_version"],
        "job_id": envelope["job"]["id"],
        "run_id": envelope["run"]["id"],
        "attempt": envelope["run"]["attempt"],
        "deployment_id": envelope["deployment"]["id"],
        "finished_at": _utc_now(),
        "output": output,
        "output_sha256": content_hash(output),
    }
    body["envelope_hash"] = content_hash(body)
    return body
