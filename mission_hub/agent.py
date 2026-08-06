"""Stateless trainbox execution boundary."""

from __future__ import annotations

from typing import Any
from pathlib import Path
import hashlib

from .config import ConfigBundle
from .errors import SafetyError
from .protocol import build_result_envelope, validate_job_envelope
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
        job_type = envelope["job"]["type"]
        definition = self.registry.definition(job_type)
        if definition["requires_live_execution"] and not self.bundle.base["safety"]["live_execution"]:
            raise SafetyError("live execution is disabled")
        machine = self.bundle.machines[self.machine_id]
        if machine["maintenance_mode"] and job_type != "system.healthcheck":
            raise SafetyError("machine is in maintenance mode")
        schema = load_schema(self.bundle.root.parent.parent, definition["input_schema"])
        errors = validate(envelope["job"]["input"], schema)
        if errors:
            raise ValueError("invalid job input: " + "; ".join(errors))
        handler = self.registry.instantiate(job_type)
        route = self.bundle.routes[definition["provider_route"]]
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
                "artifacts": envelope["artifacts"],
                "timeout_seconds": definition["timeout_seconds"],
                "commissioning_limits": self.bundle.base["commissioning"],
                "contract_limits": self.bundle.contracts,
                "visual_limits": self.bundle.visual,
                "orchestration": self.bundle.orchestration,
                "route": route,
                "route_models": [self.bundle.models[model_id] for model_id in route["ordered_model_ids"]],
                "providers": self.bundle.providers,
                "prompt": self.bundle.prompts.get(definition["prompt_id"]) if definition["prompt_id"] else None,
            },
        )
        output_schema = load_schema(self.bundle.root.parent.parent, definition["output_schema"])
        errors = validate(output, output_schema)
        if errors:
            raise ValueError("invalid handler output: " + "; ".join(errors))
        self._validate_output_artifacts(output.get("artifacts", []), machine)
        return build_result_envelope(envelope, output)

    @staticmethod
    def _validate_output_artifacts(artifacts: list[dict[str, Any]], machine: dict[str, Any]) -> None:
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
