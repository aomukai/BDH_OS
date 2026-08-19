"""Stateless trainbox execution boundary."""

from __future__ import annotations

from typing import Any
from pathlib import Path
import hashlib

from .config import ConfigBundle
from .errors import SafetyError
from .protocol import build_result_envelope, validate_job_envelope
from .runtime_settings import bundle_with_settings, validate_settings_payload
from .registry import HandlerRegistry
from .schema import load_schema, validate


class TrainboxAgent:
    def __init__(self, bundle: ConfigBundle, *, machine_id: str, deployment: dict[str, Any]):
        self.bundle = bundle
        self.machine_id = machine_id
        self.deployment = deployment
        self.registry = HandlerRegistry(bundle)

    def execute(self, envelope: dict[str, Any]) -> dict[str, Any]:
        validate_job_envelope(self.bundle, envelope, machine_id=self.machine_id, deployment=self.deployment)
        runtime = envelope.get("runtime_settings")
        runtime_bundle = self.bundle
        if runtime is not None:
            normalized_settings = validate_settings_payload(self.bundle, runtime["payload"])
            runtime_bundle = bundle_with_settings(self.bundle, normalized_settings)
        job_type = envelope["job"]["type"]
        registry = HandlerRegistry(runtime_bundle)
        definition = registry.definition(job_type)
        if definition["requires_live_execution"] and not runtime_bundle.base["safety"]["live_execution"]:
            raise SafetyError("live execution is disabled")
        machine = runtime_bundle.machines[self.machine_id]
        if machine["maintenance_mode"] and definition["requires_live_execution"]:
            raise SafetyError("machine is in maintenance mode; live execution is held")
        schema = load_schema(self.bundle.root.parent.parent, definition["input_schema"])
        errors = validate(envelope["job"]["input"], schema)
        if errors:
            raise ValueError("invalid job input: " + "; ".join(errors))
        handler = registry.instantiate(job_type)
        route = runtime_bundle.routes[definition["provider_route"]]
        output = handler.execute(
            envelope["job"]["input"],
            {
                "machine_id": self.machine_id,
                "state_root": machine["state_root"],
                "artifact_roots": machine["artifact_roots"],
                "capabilities": machine["capabilities"],
                "deployment": envelope["deployment"],
                "deployment_environment": self.deployment.get("environment", {}),
                "release_root": self.deployment.get("release_root", "."),
                "run": envelope["run"],
                "campaign_id": envelope["job"].get("campaign_id"),
                "artifacts": envelope["artifacts"],
                "timeout_seconds": definition["timeout_seconds"],
                "commissioning_limits": runtime_bundle.base["commissioning"],
                "contract_limits": runtime_bundle.contracts,
                "visual_limits": runtime_bundle.visual,
                "orchestration": runtime_bundle.orchestration,
                "training_policy": runtime_bundle.training,
                "evaluation_policy": runtime_bundle.evaluation,
                "identity_policy": runtime_bundle.identity_policy,
                "route": route,
                "route_models": [runtime_bundle.models[model_id] for model_id in route["ordered_model_ids"]],
                "providers": runtime_bundle.providers,
                "prompt": runtime_bundle.prompts.get(definition["prompt_id"]) if definition["prompt_id"] else None,
            },
        )
        output_schema = load_schema(self.bundle.root.parent.parent, definition["output_schema"])
        errors = validate(output, output_schema)
        if errors:
            raise ValueError("invalid handler output: " + "; ".join(errors))
        self._validate_output_artifacts(output.get("artifacts", []), machine, definition)
        return build_result_envelope(envelope, output)

    @staticmethod
    def _validate_output_artifacts(
        artifacts: list[dict[str, Any]], machine: dict[str, Any], definition: dict[str, Any],
    ) -> None:
        if not isinstance(artifacts, list):
            raise ValueError("handler output artifacts must be an array")
        kinds = [artifact.get("kind") for artifact in artifacts if isinstance(artifact, dict)]
        for required in definition["required_artifact_types"]:
            if kinds.count(required) != 1:
                raise ValueError(f"handler output must contain exactly one {required} artifact")
        unexpected = sorted(set(kinds) - set(definition["artifact_types"]))
        if unexpected:
            raise ValueError("handler output contains unexpected artifact types: " + ", ".join(str(value) for value in unexpected))
        roots = [Path(machine["state_root"]).resolve(), *(Path(value).resolve() for value in machine["artifact_roots"])]
        for artifact in artifacts:
            path = Path(artifact["uri"]).resolve()
            if not path.is_file() or not any(path == root or root in path.parents for root in roots):
                raise SafetyError(f"output artifact is unavailable or outside configured roots: {path}")
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
            if digest.hexdigest() != artifact["sha256"] or path.stat().st_size != artifact["byte_size"]:
                raise SafetyError(f"output artifact declaration does not match bytes: {path}")
