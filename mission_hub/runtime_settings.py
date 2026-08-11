"""Validated operator-facing runtime settings shared across the machine boundary."""

from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from .config import ConfigBundle, MODEL_KEYS, MODEL_MODALITIES, PROVIDER_KEYS, model_supports_route
from .errors import ConflictError, SafetyError


SETTINGS_ID = re.compile(r"[a-z0-9][a-z0-9._-]{1,62}")
ENVIRONMENT_NAME = re.compile(r"[A-Z][A-Z0-9_]*")


def bundle_with_settings(bundle: ConfigBundle, payload: dict[str, Any]) -> ConfigBundle:
    """Overlay validated operator settings without changing release identity."""
    return replace(
        bundle,
        jobs={item["id"]: dict(item) for item in payload["jobs"]},
        providers={item["id"]: dict(item) for item in payload["providers"]},
        models={item["id"]: dict(item) for item in payload["models"]},
        routes={item["id"]: dict(item) for item in payload["routes"]},
        prompts={item["id"]: dict(item) for item in payload["prompts"]},
        orchestration=dict(payload["orchestration"]),
        model_defaults=dict(payload["model_defaults"]),
        visual=dict(payload["visual"]),
        budget=dict(payload["budget"]),
    )


def settings_payload(bundle: ConfigBundle) -> dict[str, Any]:
    return {
        "schema_version": "ninereeds_lab_settings_v1",
        "base_config_sha256": bundle.sha256,
        "jobs": [dict(value) for value in sorted(bundle.jobs.values(), key=lambda item: item["id"])],
        "providers": [dict(value) for value in sorted(bundle.providers.values(), key=lambda item: item["id"])],
        "models": [dict(value) for value in sorted(bundle.models.values(), key=lambda item: item["id"])],
        "routes": [dict(value) for value in sorted(bundle.routes.values(), key=lambda item: item["id"])],
        "prompts": [dict(value) for value in sorted(bundle.prompts.values(), key=lambda item: item["id"])],
        "orchestration": dict(bundle.orchestration),
        "model_defaults": dict(bundle.model_defaults),
        "visual": dict(bundle.visual),
        "budget": dict(bundle.budget),
    }


def validate_settings_payload(bundle: ConfigBundle, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema_version") != "ninereeds_lab_settings_v1":
        raise ValueError("invalid Lab settings schema")
    if payload.get("base_config_sha256") != bundle.sha256:
        raise ConflictError("settings draft is based on a stale configuration")
    expected = {"schema_version", "base_config_sha256", "jobs", "providers", "models", "routes", "prompts", "orchestration", "model_defaults", "visual", "budget"}
    if set(payload) != expected:
        raise ValueError("settings draft has unknown or missing sections")
    normalized = settings_payload(bundle)
    schemas = {
        "jobs": bundle.jobs, "providers": bundle.providers, "models": bundle.models,
        "routes": bundle.routes, "prompts": bundle.prompts,
    }
    mutable_fields = {
        "jobs": {"enabled", "priority", "timeout_seconds", "max_attempts", "approval", "provider_route", "prompt_id"},
        "providers": {"enabled", "endpoint", "timeout_seconds", "max_attempts", "concurrency"},
        "models": {"enabled", "provider", "exact_name", "context_tokens", "output_tokens", "structured_output", "modality", "revision"},
        "routes": {"enabled", "ordered_model_ids", "fallback_failure_classes", "max_total_tokens", "max_cost_usd"},
        "prompts": {"enabled", "system", "template"},
    }
    extensible_schemas = {"providers": PROVIDER_KEYS, "models": MODEL_KEYS}
    singleton_mutable = {
        "orchestration": {"strategic_boundary_cooldown_seconds"},
        "model_defaults": {"unlisted_context_tokens", "unlisted_output_tokens"},
        "visual": {
            "shadow_mode", "stage_cooldown_seconds", "max_pack_items", "max_candidates_per_item", "max_width", "max_height",
            "max_generation_steps", "max_stage_seconds", "max_pack_bytes", "minimum_free_bytes",
        },
        "budget": {
            "external_calls_enabled", "monthly_limit", "weekly_limit", "per_run_approval_above",
            "emergency_reserve", "warning_fraction", "restriction_fraction", "hard_stop_fraction",
        },
    }
    for section, mutable in singleton_mutable.items():
        candidate = payload.get(section)
        original = getattr(bundle, section)
        if not isinstance(candidate, dict) or set(candidate) != set(original):
            raise ValueError(f"settings {section} has unknown or missing fields")
        for key, original_value in original.items():
            value = candidate[key]
            if isinstance(original_value, float) and isinstance(value, int) and not isinstance(value, bool):
                candidate[key] = float(value)
                value = candidate[key]
            if type(value) is not type(original_value):
                raise ValueError(f"settings {section}.{key} has the wrong type")
            if key not in mutable and value != original_value:
                raise SafetyError(f"settings {section}.{key} is not an operator-facing knob")
        normalized[section] = dict(candidate)
    cooldown = normalized["orchestration"]["strategic_boundary_cooldown_seconds"]
    if not 0 <= cooldown <= 86400:
        raise ValueError("strategic decision cooldown must be between 0 and 86400 seconds")
    if any(normalized["model_defaults"][key] < 1 for key in ("unlisted_context_tokens", "unlisted_output_tokens")):
        raise ValueError("unlisted-model token defaults must be positive")
    if any(normalized["visual"][key] < 1 for key in singleton_mutable["visual"] if key not in {"shadow_mode", "stage_cooldown_seconds"}):
        raise ValueError("visual pipeline limits must be positive")
    if not 0 <= normalized["visual"]["stage_cooldown_seconds"] <= 86400:
        raise ValueError("visual stage cooldown must be between zero and one day")
    visual_ceilings = {
        "max_pack_items": 128, "max_candidates_per_item": 4,
        "max_width": 4096, "max_height": 4096, "max_generation_steps": 200,
        "max_stage_seconds": 86400, "max_pack_bytes": 107374182400,
        "minimum_free_bytes": 1099511627776,
    }
    if any(normalized["visual"][key] > ceiling for key, ceiling in visual_ceilings.items()):
        raise ValueError("visual pipeline limits exceed the hard safety envelope")
    budget = normalized["budget"]
    if any(budget[key] < 0 for key in ("monthly_limit", "weekly_limit", "per_run_approval_above", "emergency_reserve")):
        raise ValueError("budget amounts must not be negative")
    if not 0 <= budget["warning_fraction"] < budget["restriction_fraction"] < budget["hard_stop_fraction"] <= 1:
        raise ValueError("budget warning, restriction, and hard-stop fractions must be strictly ordered")
    active_budget_limits = [budget[key] for key in ("monthly_limit", "weekly_limit") if budget[key] > 0]
    if budget["external_calls_enabled"] and active_budget_limits and budget["emergency_reserve"] >= min(active_budget_limits):
        raise ValueError("emergency reserve must be smaller than every non-zero budget limit")
    for section, baseline in schemas.items():
        values = payload[section]
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise ValueError(f"settings {section} must be a list of objects")
        supplied = {item.get("id"): item for item in values}
        if len(supplied) != len(values):
            raise ValueError(f"settings {section} contains duplicate IDs")
        if any(not isinstance(item_id, str) or not SETTINGS_ID.fullmatch(item_id) for item_id in supplied):
            raise ValueError(f"settings {section} has an invalid ID")
        if section in extensible_schemas and not set(baseline).issubset(supplied):
            raise ValueError(f"settings {section} may not remove active catalog entries")
        if section not in extensible_schemas and set(supplied) != set(baseline):
            raise ValueError(f"settings {section} IDs do not match the active catalog")
        checked: list[dict[str, Any]] = []
        for item_id in sorted(supplied):
            candidate = supplied[item_id]
            original = baseline.get(item_id)
            field_schema = extensible_schemas.get(section)
            expected_fields = set(original) if original is not None else set(field_schema or {})
            if set(candidate) != expected_fields:
                raise ValueError(f"settings {section}/{item_id} has unknown or missing fields")
            type_contract = ({key: type(value) for key, value in original.items()} if original is not None else field_schema)
            candidate = dict(candidate)
            for key, required_type in type_contract.items():
                value = candidate[key]
                if original is not None and key not in mutable_fields[section] and value != original[key]:
                    raise SafetyError(f"settings {section}/{item_id}.{key} is not an operator-facing knob")
                if required_type is bool:
                    if not isinstance(value, bool):
                        raise ValueError(f"settings {section}/{item_id}.{key} must be boolean")
                elif required_type is float and isinstance(value, int) and not isinstance(value, bool):
                    # JSON and JavaScript have one number type, so an
                    # untouched 0.0 is serialized by the browser as 0.
                    candidate[key] = float(value)
                elif not isinstance(value, required_type):
                    raise ValueError(f"settings {section}/{item_id}.{key} has the wrong type")
            if section == "providers" and original is None:
                if candidate["kind"] not in {"openai_compatible", "local_openai_compatible"}:
                    raise ValueError(f"settings providers/{item_id}.kind is not supported by the custom-service form")
                if not re.fullmatch(r"https?://[^\s]+", candidate["endpoint"]):
                    raise ValueError(f"settings providers/{item_id}.endpoint must be an HTTP or HTTPS URL")
                if candidate["credential_env"] and not ENVIRONMENT_NAME.fullmatch(candidate["credential_env"]):
                    raise ValueError(f"settings providers/{item_id}.credential_env is invalid")
            if section == "models" and original is None:
                if not candidate["exact_name"].strip():
                    raise ValueError(f"settings models/{item_id}.exact_name must not be empty")
                if candidate["context_tokens"] < 1 or candidate["output_tokens"] < 1:
                    raise ValueError(f"settings models/{item_id} token limits must be positive")
                if candidate["modality"] not in MODEL_MODALITIES:
                    raise ValueError(f"settings models/{item_id}.modality is unsupported")
                if candidate["local"] and candidate["modality"] != "text" and not candidate["revision"]:
                    raise ValueError(f"local visual model {item_id} requires an immutable revision")
            checked.append(candidate)
        normalized[section] = checked
    provider_ids = {item["id"] for item in normalized["providers"]}
    model_ids = {item["id"] for item in normalized["models"]}
    for model in normalized["models"]:
        if model["provider"] not in provider_ids:
            raise ValueError(f"settings model {model['id']} names an unknown service")
    for route in normalized["routes"]:
        if any(model_id not in model_ids for model_id in route["ordered_model_ids"]):
            raise ValueError(f"settings route {route['id']} names an unknown model")
        if any(not model_supports_route(next(model for model in normalized["models"] if model["id"] == model_id)["modality"], route["model_modalities"]) for model_id in route["ordered_model_ids"]):
            raise ValueError(f"settings route {route['id']} contains a model with the wrong modality")
    providers_by_id = {item["id"]: item for item in normalized["providers"]}
    models_by_id = {item["id"]: item for item in normalized["models"]}
    routes_by_id = {item["id"]: item for item in normalized["routes"]}
    local_visual_jobs = {"visual.generate", "visual.encode"}
    recognition_jobs = {"visual.inspect", "visual.caption", "visual.review"}
    for job in normalized["jobs"]:
        if job["id"] not in local_visual_jobs | recognition_jobs:
            continue
        route = routes_by_id[job["provider_route"]]
        for model_id in route["ordered_model_ids"]:
            model = models_by_id[model_id]
            provider = providers_by_id[model["provider"]]
            if job["id"] in local_visual_jobs:
                allowed = {"local_subprocess"}
            elif job["executor_role"] == "mission_hub":
                allowed = {"codex_cli", "openai_compatible", "local_openai_compatible"}
            else:
                allowed = {"local_subprocess", "codex_cli"}
            if provider["kind"] not in allowed:
                raise ValueError(
                    f"settings {job['id']} cannot use {model['exact_name']}; "
                    "this step requires a commissioned visual provider"
                )
    selected_model_ids = {
        model_id for route in normalized["routes"] if route["enabled"]
        for model_id in route["ordered_model_ids"]
    }
    for model in normalized["models"]:
        if model["id"] in selected_model_ids:
            model["enabled"] = True
    return normalized
