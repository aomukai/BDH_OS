"""Configuration-backed handler registry."""

from __future__ import annotations

import importlib
from typing import Any

from .config import ConfigBundle
from .errors import ConfigError, SafetyError


class HandlerRegistry:
    def __init__(self, bundle: ConfigBundle):
        self.bundle = bundle

    def definition(self, job_type: str) -> dict[str, Any]:
        try:
            return self.bundle.jobs[job_type]
        except KeyError as exc:
            raise ConfigError(f"unknown job type: {job_type}") from exc

    def instantiate(self, job_type: str) -> Any:
        definition = self.definition(job_type)
        if not definition["enabled"]:
            raise SafetyError(f"job type is disabled: {job_type}")
        module_name, separator, class_name = definition["handler"].partition(":")
        if not separator or not module_name.startswith("mission_hub.handlers."):
            raise ConfigError(f"job {job_type} has a non-allowlisted handler path")
        try:
            module = importlib.import_module(module_name)
            handler_type = getattr(module, class_name)
            handler = handler_type()
        except (ImportError, AttributeError, TypeError) as exc:
            raise ConfigError(f"cannot load handler for {job_type}: {exc}") from exc
        if not callable(getattr(handler, "execute", None)):
            raise ConfigError(f"handler for {job_type} has no execute method")
        return handler
