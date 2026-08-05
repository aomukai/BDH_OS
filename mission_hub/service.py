"""Application service joining configuration, store, protocol, and agent results."""

from __future__ import annotations

import json
from typing import Any

from .config import ConfigBundle
from .artifacts import ArtifactFiles
from .errors import ConflictError, ProtocolError, SafetyError
from .jsonutil import content_hash
from .protocol import build_job_envelope
from .store import MissionHubStore
from .transport import SSHDispatcher


class MissionHubService:
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store = store
        self.bundle = bundle

    def lease_envelope(self, *, machine_id: str, deployment_id: str, actor: str) -> dict[str, Any] | None:
        leased = self.store.lease_next(
            self.bundle,
            machine_id=machine_id,
            deployment_id=deployment_id,
            actor=actor,
        )
        if leased is None:
            return None
        job, token = leased
        definition = self.bundle.jobs[job["job_type"]]
        artifacts = self.store.resolve_artifacts(
            definition,
            json.loads(job["input_json"]),
            machine_id=machine_id,
        )
        return build_job_envelope(self.bundle, job, token, artifacts)

    def accept_result(self, envelope: dict[str, Any], result: dict[str, Any], *, actor: str) -> None:
        required = {
            "schema_version", "protocol_version", "job_id", "run_id", "attempt",
            "deployment_id", "finished_at", "output", "output_sha256", "envelope_hash",
        }
        if set(result) != required or result["schema_version"] != "ninereeds_result_envelope_v1":
            raise ProtocolError("invalid result envelope fields")
        supplied = result["envelope_hash"]
        body = {key: value for key, value in result.items() if key != "envelope_hash"}
        if supplied != content_hash(body) or result["output_sha256"] != content_hash(result["output"]):
            raise ProtocolError("result envelope hash mismatch")
        if result["job_id"] != envelope["job"]["id"] or result["run_id"] != envelope["run"]["id"]:
            raise ProtocolError("result does not belong to leased job/run")
        if result["deployment_id"] != envelope["deployment"]["id"]:
            raise ProtocolError("result deployment mismatch")
        self.store.finish_run(
            self.bundle,
            result["run_id"],
            envelope["lease"]["token"],
            status="succeeded",
            output=result["output"],
            failure=None,
            actor=actor,
        )
        if envelope["job"]["type"] == "system.healthcheck":
            self.store.record_machine_observation(
                envelope["deployment"]["machine_id"],
                result["output"],
                actor=actor,
            )

    def record_transport_failure(self, envelope: dict[str, Any], *, message: str, actor: str) -> None:
        self.store.finish_run(
            self.bundle,
            envelope["run"]["id"],
            envelope["lease"]["token"],
            status="failed",
            output=None,
            failure={
                "class": "operational_transient",
                "code": "transport_unavailable",
                "message": message,
            },
            actor=actor,
        )

    def ingest_artifact(
        self,
        *,
        kind: str,
        source_path: str,
        lifecycle: str,
        manifest: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        self._require_active_config()
        if lifecycle not in {"observed", "candidate"}:
            raise SafetyError("artifact ingest lifecycle must be observed or candidate")
        destination, digest, byte_size = ArtifactFiles(self.bundle, "mission-hub").ingest(source_path)
        if kind == "commissioning_input" and byte_size > self.bundle.base["commissioning"]["max_artifact_input_bytes"]:
            raise SafetyError("commissioning artifact exceeds its configured input limit")
        artifact_id = self.store.register_artifact(
            self.bundle,
            kind=kind,
            sha256=digest,
            byte_size=byte_size,
            lifecycle=lifecycle,
            manifest=manifest,
            producing_run_id=None,
            machine_id="mission-hub",
            uri=str(destination),
            actor=actor,
        )
        return self.store.artifact_at(artifact_id, machine_id="mission-hub")

    def materialize_artifact(self, artifact_id: str, *, machine_id: str, actor: str) -> dict[str, Any]:
        self._require_active_config()
        artifact = self.store.artifact_at(artifact_id, machine_id="mission-hub")
        deployment = self.store.active_deployment(machine_id)
        uri = SSHDispatcher(self.bundle).put_artifact(machine_id, deployment, artifact)
        self.store.record_artifact_location(
            self.bundle, artifact_id, machine_id=machine_id, uri=uri,
            event_type="artifact.materialized", actor=actor,
        )
        return self.store.artifact_at(artifact_id, machine_id=machine_id)

    def retrieve_artifact(self, artifact_id: str, *, machine_id: str, actor: str) -> dict[str, Any]:
        self._require_active_config()
        artifact = self.store.artifact_at(artifact_id, machine_id=machine_id)
        deployment = self.store.active_deployment(machine_id)
        uri = SSHDispatcher(self.bundle).get_artifact(machine_id, deployment, artifact)
        self.store.record_artifact_location(
            self.bundle, artifact_id, machine_id="mission-hub", uri=uri,
            event_type="artifact.retrieved", actor=actor,
        )
        return self.store.artifact_at(artifact_id, machine_id="mission-hub")

    def _require_active_config(self) -> None:
        active = self.store.active_config()
        if active["sha256"] != self.bundle.sha256:
            raise ConflictError("loaded configuration is not the active configuration")
