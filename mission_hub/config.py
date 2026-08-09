"""Typed, versioned Mission Hub configuration loader.

Configuration is intentionally fail-closed: unknown keys are rejected, every
document is hashed, and activation stores the complete resolved bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import tomllib
from typing import Any, Iterable

from .errors import ConfigError
from .jsonutil import content_hash
from .schema import load_schema


ROOT_FILES = ("base.toml", "providers.toml", "models.toml")

MODEL_MODALITIES = {"text", "image_generation", "vision_language", "vision_encoder"}


def model_supports_route(model_modality: str, route_modalities: Iterable[str]) -> bool:
    """Whether a catalog model is a plausible choice for a route."""
    required = set(route_modalities)
    if not required:
        return True
    compatible = {
        "text": {"text", "vision_language"},
        "vision_language": {"vision_language"},
        "image_generation": {"image_generation"},
        "vision_encoder": {"vision_encoder"},
    }
    return any(model_modality in compatible.get(value, {value}) for value in required)


def machine_id_for_role(bundle: "ConfigBundle", role: str) -> str:
    matches = [machine_id for machine_id, machine in bundle.machines.items() if machine["enabled"] and machine["role"] == role]
    if len(matches) != 1:
        raise ConfigError(f"role {role} must map to exactly one enabled machine, found {len(matches)}")
    return matches[0]


@dataclass(frozen=True)
class ConfigDocument:
    relative_path: str
    kind: str
    data: dict[str, Any]
    sha256: str


@dataclass(frozen=True)
class ConfigBundle:
    root: Path
    documents: tuple[ConfigDocument, ...]
    base: dict[str, Any]
    machines: dict[str, dict[str, Any]]
    jobs: dict[str, dict[str, Any]]
    providers: dict[str, dict[str, Any]]
    models: dict[str, dict[str, Any]]
    prompts: dict[str, dict[str, Any]]
    evidence_sources: dict[str, dict[str, Any]]
    deployment_roles: dict[str, dict[str, Any]]
    migration: dict[str, Any]
    retry_policies: dict[str, dict[str, Any]]
    failure_codes: dict[str, dict[str, Any]]
    routes: dict[str, dict[str, Any]]
    schedules: dict[str, dict[str, Any]]
    artifact_types: dict[str, dict[str, Any]]
    budget: dict[str, Any]
    retention: dict[str, Any]
    ownership: dict[str, dict[str, Any]]
    failure_logging: dict[str, Any]
    emergency: dict[str, Any]
    recovery: dict[str, Any]
    contracts: dict[str, Any]
    orchestration: dict[str, Any]
    model_defaults: dict[str, Any]
    visual: dict[str, Any]
    training: dict[str, Any]
    evaluation: dict[str, Any]
    identity_policy: dict[str, Any]
    campaign_modes: dict[str, dict[str, Any]]
    sha256: str

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema_version": "ninereeds_config_snapshot_v1",
            "bundle_sha256": self.sha256,
            "documents": [
                {"path": doc.relative_path, "kind": doc.kind, "sha256": doc.sha256}
                for doc in self.documents
            ],
            "resolved": {
                "base": self.base,
                "machines": self.machines,
                "jobs": self.jobs,
                "providers": self.providers,
                "models": self.models,
                "prompts": self.prompts,
                "evidence_sources": self.evidence_sources,
                "deployment_roles": self.deployment_roles,
                "migration": self.migration,
                "retry_policies": self.retry_policies,
                "failure_codes": self.failure_codes,
                "routes": self.routes,
                "schedules": self.schedules,
                "artifact_types": self.artifact_types,
                "budget": self.budget,
                "retention": self.retention,
                "ownership": self.ownership,
                "failure_logging": self.failure_logging,
                "emergency": self.emergency,
                "recovery": self.recovery,
                "contracts": self.contracts,
                "orchestration": self.orchestration,
                "model_defaults": self.model_defaults,
                "visual": self.visual,
                "training": self.training,
                "evaluation": self.evaluation,
                "identity_policy": self.identity_policy,
                "campaign_modes": self.campaign_modes,
            },
        }


BASE_SCHEMA = {
    "schema_version": int,
    "hub": dict,
    "safety": dict,
    "scheduler": dict,
    "artifacts": dict,
    "commissioning": dict,
    "protocol": dict,
    "api": dict,
    "failure_logging": dict,
    "emergency": dict,
    "recovery": dict,
    "contracts": dict,
    "orchestration": dict,
    "model_defaults": dict,
    "visual": dict,
    "training": dict,
    "evaluation": dict,
}
BASE_SECTIONS = {
    "hub": {
        "state_root": str,
        "database_name": str,
        "busy_timeout_ms": int,
        "event_chain": bool,
    },
    "safety": {
        "live_execution": bool,
        "automatic_pruning": bool,
        "automatic_campaign_rollover": bool,
        "allow_git_mutation": bool,
        "require_release_match": bool,
        "require_config_match": bool,
    },
    "scheduler": {
        "poll_seconds": int,
        "lease_seconds": int,
        "heartbeat_seconds": int,
        "stale_after_seconds": int,
        "max_attempts_default": int,
        "max_queue_age_seconds": int,
    },
    "training": {
        "order_policy": str,
        "shuffle_allowed": bool,
        "dependency_order_required": bool,
        "max_examples_per_session": int,
        "max_completion_utf8_bytes": int,
        "observer_fixture": dict,
    },
    "evaluation": {
        "basis": list,
        "loss_role": str,
    },
    "orchestration": {
        "strategic_boundary_cooldown_seconds": int,
    },
    "model_defaults": {
        "unlisted_context_tokens": int,
        "unlisted_output_tokens": int,
    },
    "visual": {
        "shadow_mode": bool,
        "stage_cooldown_seconds": int,
        "store_root": str,
        "max_pack_items": int,
        "max_candidates_per_item": int,
        "max_width": int,
        "max_height": int,
        "max_generation_steps": int,
        "max_stage_seconds": int,
        "max_pack_bytes": int,
        "minimum_free_bytes": int,
        "independent_review_required": bool,
    },
    "artifacts": {
        "manifest_algorithm": str,
        "deletion_requires_approval": bool,
        "retention_mode": str,
        "max_transfer_bytes": int,
        "transfer_chunk_bytes": int,
    },
    "commissioning": {
        "max_artifact_input_bytes": int,
        "gpu_max_devices": int,
        "gpu_max_matrix_size": int,
        "gpu_max_iterations": int,
        "gpu_max_duration_seconds": int,
        "gpu_max_allocated_bytes": int,
        "gpu_max_start_temperature_c": int,
    },
    "protocol": {
        "version": int,
        "max_envelope_bytes": int,
        "clock_skew_seconds": int,
    },
    "api": {
        "host": str,
        "port": int,
        "auth_token_env": str,
        "max_request_bytes": int,
    },
    "failure_logging": {
        "enabled": bool,
        "root": str,
        "retention_days": int,
        "max_message_characters": int,
    },
    "emergency": {
        "mode": str,
        "invoke_on_critical_failure": bool,
        "executable": str,
        "model": str,
        "timeout_seconds": int,
        "max_incident_bytes": int,
        "response_schema": str,
    },
    "recovery": {
        "enabled": bool,
        "source_repository_root": str,
        "max_repair_attempts": int,
        "max_changed_files": int,
        "max_patch_bytes": int,
        "attempt_timeout_seconds": int,
        "allowed_source_roots": list,
        "protected_paths": list,
        "targeted_test_commands": list,
        "regression_test_commands": list,
    },
    "contracts": {
        "training_library_root": str,
        "corpus_max_source_files": int,
        "corpus_max_source_bytes": int,
        "checkpoint_max_bytes": int,
        "checkpoint_roots": list,
    },
}
MACHINE_KEYS = {
    "id": str,
    "display_name": str,
    "role": str,
    "hostname": str,
    "enabled": bool,
    "maintenance_mode": bool,
    "max_concurrent_jobs": int,
    "allowed_job_types": list,
    "state_root": str,
    "artifact_roots": list,
    "capabilities": list,
    "transport": str,
    "ssh_target": str,
    "dispatch_timeout_seconds": int,
    "artifact_transfer_timeout_seconds": int,
    "release_install_root": str,
    "active_release_link": str,
}
JOB_KEYS = {
    "id": str,
    "version": int,
    "description": str,
    "owner": str,
    "executor_role": str,
    "handler": str,
    "enabled": bool,
    "requires_live_execution": bool,
    "critical": bool,
    "priority": int,
    "timeout_seconds": int,
    "max_attempts": int,
    "retry_policy": str,
    "input_schema": str,
    "output_schema": str,
    "artifact_types": list,
    "required_artifact_types": list,
    "artifact_input_fields": list,
    "required_capabilities": list,
    "approval": str,
    "provider_route": str,
    "prompt_id": str,
}
PROVIDER_KEYS = {
    "id": str,
    "kind": str,
    "enabled": bool,
    "endpoint": str,
    "credential_env": str,
    "timeout_seconds": int,
    "max_attempts": int,
    "concurrency": int,
}
MODEL_KEYS = {
    "id": str,
    "provider": str,
    "exact_name": str,
    "enabled": bool,
    "local": bool,
    "context_tokens": int,
    "output_tokens": int,
    "structured_output": bool,
    "runtime": str,
    "weights": str,
    "device": str,
    "modality": str,
    "revision": str,
}
PROMPT_KEYS = {
    "id": str,
    "version": int,
    "job_type": str,
    "enabled": bool,
    "system": str,
    "template": str,
    "variables": list,
    "output_schema": str,
}
IDENTITY_POLICY_KEYS = {
    "id": str,
    "version": int,
    "learner_name": str,
    "default_identity_scope": str,
    "consciousness_policy": str,
    "identity_axioms": list,
    "revision_capabilities": list,
    "obsolete_assumptions": list,
    "forbidden_patterns": list,
}
CAMPAIGN_MODE_KEYS = {
    "id": str,
    "display_name": str,
    "purpose": str,
    "improvement_required": bool,
    "allows_expected_regression": bool,
    "comparison_scope": str,
    "candidate_disposition": str,
    "minimum_branches": int,
    "minimum_merge_sources": int,
    "required_evidence": list,
}
EVIDENCE_SOURCE_KEYS = {
    "id": str,
    "machine_id": str,
    "source_kind": str,
    "path": str,
    "required": bool,
    "hash_content": bool,
    "copy_bytes": bool,
    "import_json": bool,
    "max_import_bytes": int,
    "include_suffixes": list,
    "exclude_names": list,
}
DEPLOYMENT_ROLE_KEYS = {
    "id": str,
    "role": str,
    "include_roots": list,
    "exclude_globs": list,
    "required_paths": list,
    "python_executable": str,
    "python_site_paths": list,
    "auxiliary_python_executables": list,
    "required_model_paths": list,
}
MIGRATION_KEYS = {
    "campaign_source_id": str,
    "active_legacy_campaign_number": int,
    "import_state": str,
    "resumption_allowed": bool,
    "stale_legacy_plan_id": str,
    "freeze_reason": str,
}
RETRY_POLICY_KEYS = {
    "id": str,
    "max_execution_attempts": int,
    "max_repair_attempts": int,
    "retryable_failure_classes": list,
    "backoff_seconds": list,
    "operator_after_exhaustion": bool,
}
FAILURE_CODE_KEYS = {
    "id": str,
    "failure_class": str,
    "retryable": bool,
    "description": str,
}
ROUTE_KEYS = {
    "id": str,
    "enabled": bool,
    "ordered_model_ids": list,
    "fallback_failure_classes": list,
    "max_total_tokens": int,
    "max_cost_usd": float,
    "model_modalities": list,
}
SCHEDULE_KEYS = {
    "id": str,
    "job_type": str,
    "enabled": bool,
    "trigger": str,
    "interval_seconds": int,
    "overlap_policy": str,
    "catch_up": bool,
    "machine_id": str,
    "input": dict,
}
ARTIFACT_TYPE_KEYS = {
    "id": str,
    "owner": str,
    "immutable": bool,
    "content_hash_required": bool,
    "retention_policy": str,
}
BUDGET_KEYS = {
    "currency": str,
    "external_calls_enabled": bool,
    "monthly_limit": float,
    "weekly_limit": float,
    "per_run_approval_above": float,
    "emergency_reserve": float,
    "warning_fraction": float,
    "restriction_fraction": float,
    "hard_stop_fraction": float,
}
RETENTION_KEYS = {
    "mode": str,
    "scan_interval_seconds": int,
    "inventory_timeout_seconds": int,
    "build_roots": list,
    "build_file_suffixes": list,
    "warning_used_fraction": float,
    "proposal_used_fraction": float,
    "critical_used_fraction": float,
    "minimum_free_bytes": int,
    "keep_campaign_winners": int,
    "keep_developmental_checkpoints": int,
    "keep_rejected_per_campaign": int,
    "deletion_requires_decision": bool,
}
OWNERSHIP_KEYS = {
    "id": str,
    "data_class": str,
    "canonical_owner": str,
    "deployed_roles": list,
    "mutable_by": list,
    "legacy_disposition": str,
}


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            value = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"{path} must contain a TOML table")
    return value


def _reject_unknown(value: dict[str, Any], allowed: dict[str, type], label: str) -> None:
    unknown = sorted(set(value) - set(allowed))
    if unknown:
        raise ConfigError(f"{label} has unknown keys: {', '.join(unknown)}")
    missing = sorted(set(allowed) - set(value))
    if missing:
        raise ConfigError(f"{label} is missing keys: {', '.join(missing)}")
    for key, expected in allowed.items():
        actual = value[key]
        if expected is int and isinstance(actual, bool):
            raise ConfigError(f"{label}.{key} must be int, not bool")
        if not isinstance(actual, expected):
            raise ConfigError(f"{label}.{key} must be {expected.__name__}")


def _document(root: Path, path: Path, kind: str, data: dict[str, Any]) -> ConfigDocument:
    return ConfigDocument(
        relative_path=path.relative_to(root).as_posix(),
        kind=kind,
        data=data,
        sha256=content_hash(data),
    )


def _records(
    root: Path,
    path: Path,
    table_name: str,
    key_schema: dict[str, type],
    documents: list[ConfigDocument],
) -> dict[str, dict[str, Any]]:
    data = _load_toml(path)
    if set(data) != {"schema_version", table_name}:
        raise ConfigError(f"{path} must contain only schema_version and [[{table_name}]]")
    if data["schema_version"] != 1 or not isinstance(data[table_name], list):
        raise ConfigError(f"{path} has an unsupported schema or invalid record list")
    documents.append(_document(root, path, table_name, data))
    result: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(data[table_name]):
        if not isinstance(record, dict):
            raise ConfigError(f"{path}:{table_name}[{index}] must be a table")
        _reject_unknown(record, key_schema, f"{path}:{table_name}[{index}]")
        record_id = record["id"]
        if record_id in result:
            raise ConfigError(f"duplicate {table_name} id: {record_id}")
        result[record_id] = record
    return result


def _directory_records(
    root: Path,
    directory: str,
    table_name: str,
    key_schema: dict[str, type],
    documents: list[ConfigDocument],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    paths = sorted((root / directory).glob("*.toml"))
    if not paths:
        raise ConfigError(f"no configuration documents found in {root / directory}")
    for path in paths:
        data = _load_toml(path)
        if set(data) != {"schema_version", table_name} or data["schema_version"] != 1:
            raise ConfigError(f"{path} must contain schema_version=1 and [{table_name}]")
        record = data[table_name]
        if not isinstance(record, dict):
            raise ConfigError(f"{path} [{table_name}] must be a table")
        _reject_unknown(record, key_schema, f"{path} [{table_name}]")
        record_id = record["id"]
        if record_id in result:
            raise ConfigError(f"duplicate {table_name} id: {record_id}")
        result[record_id] = record
        documents.append(_document(root, path, table_name, data))
    return result


def _validate_relations(bundle: ConfigBundle) -> None:
    roles = {machine["role"] for machine in bundle.machines.values() if machine["enabled"]}
    repo_root = bundle.root.parent.parent
    artifact_settings = bundle.base["artifacts"]
    if artifact_settings["transfer_chunk_bytes"] < 4096 or artifact_settings["max_transfer_bytes"] < artifact_settings["transfer_chunk_bytes"]:
        raise ConfigError("artifact transfer limits are invalid")
    commissioning = bundle.base["commissioning"]
    if any(value < 1 for value in commissioning.values()):
        raise ConfigError("commissioning limits must be positive")
    if commissioning["max_artifact_input_bytes"] > artifact_settings["max_transfer_bytes"]:
        raise ConfigError("commissioning artifact limit exceeds the transport limit")
    logging_config = bundle.failure_logging
    if not logging_config["enabled"]:
        raise ConfigError("critical-job failure logging must remain enabled")
    if logging_config["retention_days"] != 7 or logging_config["max_message_characters"] < 256:
        raise ConfigError("critical-job failure logs require seven-day retention and a useful message bound")
    log_root = Path(logging_config["root"]).resolve()
    state_root = Path(bundle.base["hub"]["state_root"]).resolve()
    if log_root != state_root and state_root not in log_root.parents:
        raise ConfigError("critical-job failure log root must be inside the Mission Hub state root")
    emergency = bundle.emergency
    if emergency["mode"] not in {"disabled", "sol_advisory"}:
        raise ConfigError("emergency mode must be disabled or sol_advisory")
    if emergency["timeout_seconds"] < 1 or emergency["max_incident_bytes"] < 1024:
        raise ConfigError("emergency invocation limits are invalid")
    response_schema = (repo_root / emergency["response_schema"]).resolve()
    if not response_schema.is_file() or repo_root.resolve() not in response_schema.parents:
        raise ConfigError("emergency response schema is unavailable")
    load_schema(repo_root, emergency["response_schema"])
    recovery = bundle.recovery
    source_repository_root = Path(recovery["source_repository_root"])
    if not source_repository_root.is_absolute():
        raise ConfigError("recovery source repository root must be absolute")
    if recovery["max_repair_attempts"] < 1 or recovery["max_repair_attempts"] > 5:
        raise ConfigError("recovery repair attempts must be between one and five")
    if recovery["max_changed_files"] < 1 or recovery["max_patch_bytes"] < 1024:
        raise ConfigError("recovery source-change bounds are invalid")
    if not 1 <= recovery["attempt_timeout_seconds"] <= 7200:
        raise ConfigError("recovery attempt timeout must be between one second and two hours")
    for key in ("allowed_source_roots", "protected_paths"):
        values = recovery[key]
        if not values or not all(isinstance(value, str) and value and not Path(value).is_absolute() and ".." not in Path(value).parts for value in values):
            raise ConfigError(f"recovery {key} must contain clean repository-relative paths")
    if any(
        not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command)
        for key in ("targeted_test_commands", "regression_test_commands")
        for command in recovery[key]
    ):
        raise ConfigError("recovery tests must be non-empty argument-vector lists")
    contracts = bundle.contracts
    library_root = Path(contracts["training_library_root"]).resolve()
    control_machine = bundle.machines[machine_id_for_role(bundle, "mission_hub")]
    executor_machine = bundle.machines[machine_id_for_role(bundle, "trainbox")]
    mission_roots = [Path(value).resolve() for value in control_machine["artifact_roots"]]
    if not any(library_root == root or root in library_root.parents for root in mission_roots):
        raise ConfigError("training library root must be a configured Mission Hub artifact root")
    if any(contracts[key] < 1 for key in ("corpus_max_source_files", "corpus_max_source_bytes", "checkpoint_max_bytes")):
        raise ConfigError("artifact contract limits must be positive")
    immutable_training_policy = {
        "order_policy": "declared_only",
        "shuffle_allowed": False,
        "dependency_order_required": True,
    }
    if any(bundle.training.get(key) != value for key, value in immutable_training_policy.items()):
        raise ConfigError("training order is an immutable declared dependency-order contract")
    if any(bundle.training[key] < 1 for key in ("max_examples_per_session", "max_completion_utf8_bytes")):
        raise ConfigError("training material limits must be positive")
    observer = bundle.training["observer_fixture"]
    _reject_unknown(observer, {
        "id": str, "version": int, "required": bool,
        "log_every_n_steps": int, "max_sampled_steps": int,
    }, "training.observer_fixture")
    if observer["id"] != "gate-credit-v1" or observer["version"] != 1 or not observer["required"]:
        raise ConfigError("the versioned gate-credit observer is a required training fixture")
    if observer["log_every_n_steps"] < 1 or observer["max_sampled_steps"] < 1:
        raise ConfigError("observer fixture sampling bounds must be positive")
    if bundle.evaluation != {
        "basis": ["behavioral_chat", "mri_activation"],
        "loss_role": "telemetry_only",
    }:
        raise ConfigError("Cortex evaluation requires behavioral chat and MRI; loss is telemetry only")
    orchestration = bundle.orchestration
    cooldown = orchestration["strategic_boundary_cooldown_seconds"]
    if isinstance(cooldown, bool) or not 0 <= cooldown <= 86400:
        raise ConfigError("strategic boundary cooldown must be between zero and one day")
    if any(bundle.model_defaults[key] < 1 for key in ("unlisted_context_tokens", "unlisted_output_tokens")):
        raise ConfigError("unlisted-model token defaults must be positive")
    visual = bundle.visual
    if not visual["independent_review_required"]:
        raise ConfigError("visual pipeline independent review may not be disabled")
    if any(visual[key] < 1 for key in (
        "max_pack_items", "max_candidates_per_item", "max_width", "max_height",
        "max_generation_steps", "max_stage_seconds", "max_pack_bytes", "minimum_free_bytes",
    )):
        raise ConfigError("visual pipeline limits must be positive")
    if isinstance(visual["stage_cooldown_seconds"], bool) or not 0 <= visual["stage_cooldown_seconds"] <= 86400:
        raise ConfigError("visual stage cooldown must be between zero and one day")
    visual_ceilings = {
        "max_pack_items": 128, "max_candidates_per_item": 4,
        "max_width": 4096, "max_height": 4096, "max_generation_steps": 200,
        "max_stage_seconds": 86400, "max_pack_bytes": 107374182400,
        "minimum_free_bytes": 1099511627776,
    }
    if any(visual[key] > ceiling for key, ceiling in visual_ceilings.items()):
        raise ConfigError("visual pipeline limits exceed the hard safety envelope")
    budget = bundle.budget
    if any(budget[key] < 0 for key in ("monthly_limit", "weekly_limit", "per_run_approval_above", "emergency_reserve")):
        raise ConfigError("budget amounts must not be negative")
    if not 0 <= budget["warning_fraction"] < budget["restriction_fraction"] < budget["hard_stop_fraction"] <= 1:
        raise ConfigError("budget fractions must be strictly ordered")
    active_budget_limits = [budget[key] for key in ("monthly_limit", "weekly_limit") if budget[key] > 0]
    if budget["external_calls_enabled"] and active_budget_limits and budget["emergency_reserve"] >= min(active_budget_limits):
        raise ConfigError("emergency reserve must be smaller than every non-zero budget limit")
    visual_root = Path(visual["store_root"]).resolve()
    visual_machine_roots = [Path(value).resolve() for value in executor_machine["artifact_roots"]]
    if not any(visual_root == root or root in visual_root.parents for root in visual_machine_roots):
        raise ConfigError("visual store must be inside a configured trainbox artifact root")
    trainbox_roots = [Path(value).resolve() for value in executor_machine["artifact_roots"]]
    if not contracts["checkpoint_roots"] or any(
        not isinstance(value, str) or Path(value).resolve() not in trainbox_roots
        for value in contracts["checkpoint_roots"]
    ):
        raise ConfigError("checkpoint roots must be explicit configured trainbox artifact roots")
    for job_id, job in bundle.jobs.items():
        if job["executor_role"] not in roles:
            raise ConfigError(f"job {job_id} names unavailable executor role {job['executor_role']}")
        if job["max_attempts"] < 1 or job["timeout_seconds"] < 1:
            raise ConfigError(f"job {job_id} has invalid attempt or timeout limits")
        route = job["provider_route"]
        if route and route not in bundle.routes:
            raise ConfigError(f"job {job_id} names unknown provider route {route}")
        retry = job["retry_policy"]
        if retry not in bundle.retry_policies:
            raise ConfigError(f"job {job_id} names unknown retry policy {retry}")
        if job["max_attempts"] > bundle.retry_policies[retry]["max_execution_attempts"]:
            raise ConfigError(f"job {job_id} max_attempts exceeds retry policy {retry}")
        unknown_artifacts = sorted(set(job["artifact_types"]) - set(bundle.artifact_types))
        if unknown_artifacts:
            raise ConfigError(f"job {job_id} names unknown artifact types: {', '.join(unknown_artifacts)}")
        if not set(job["required_artifact_types"]).issubset(set(job["artifact_types"])):
            raise ConfigError(f"job {job_id} requires artifact types it is not allowed to produce")
        if len(set(job["required_artifact_types"])) != len(job["required_artifact_types"]):
            raise ConfigError(f"job {job_id} repeats a required artifact type")
        for schema_key in ("input_schema", "output_schema"):
            schema_path = (repo_root / job[schema_key]).resolve()
            if not schema_path.is_file() or repo_root.resolve() not in schema_path.parents:
                raise ConfigError(f"job {job_id} has unavailable {schema_key}: {job[schema_key]}")
            load_schema(repo_root, job[schema_key])
        prompt = job["prompt_id"]
        if prompt and prompt not in bundle.prompts:
            raise ConfigError(f"job {job_id} names unknown prompt {prompt}")
        if job["enabled"] and prompt and not bundle.prompts[prompt]["enabled"]:
            raise ConfigError(f"enabled job {job_id} uses disabled prompt {prompt}")
        if job["enabled"] and not bundle.routes[route]["enabled"]:
            raise ConfigError(f"enabled job {job_id} uses disabled route {route}")
    for model_id, model in bundle.models.items():
        if model["provider"] not in bundle.providers:
            raise ConfigError(f"model {model_id} names unknown provider {model['provider']}")
        if model["modality"] not in MODEL_MODALITIES:
            raise ConfigError(f"model {model_id} has unsupported modality {model['modality']}")
        if model["local"] and model["modality"] != "text" and not model["revision"]:
            raise ConfigError(f"local visual model {model_id} requires an immutable revision")
    for route_id, route in bundle.routes.items():
        unknown_models = sorted(set(route["ordered_model_ids"]) - set(bundle.models))
        if unknown_models:
            raise ConfigError(f"route {route_id} names unknown models: {', '.join(unknown_models)}")
        allowed_modalities = route["model_modalities"]
        if any(value not in MODEL_MODALITIES for value in allowed_modalities):
            raise ConfigError(f"route {route_id} has an unsupported model modality")
        if any(not model_supports_route(bundle.models[model_id]["modality"], allowed_modalities) for model_id in route["ordered_model_ids"]):
            raise ConfigError(f"route {route_id} contains a model with the wrong modality")
        if route["enabled"]:
            for model_id in route["ordered_model_ids"]:
                model = bundle.models[model_id]
                if not model["enabled"]:
                    raise ConfigError(f"enabled route {route_id} uses disabled model {model_id}")
                if not bundle.providers[model["provider"]]["enabled"]:
                    raise ConfigError(f"enabled route {route_id} uses disabled provider {model['provider']}")
    for prompt_id, prompt in bundle.prompts.items():
        if prompt["job_type"] not in bundle.jobs:
            raise ConfigError(f"prompt {prompt_id} names unknown job {prompt['job_type']}")
        if not (repo_root / prompt["output_schema"]).is_file():
            raise ConfigError(f"prompt {prompt_id} has unavailable output schema")
    for source_id, source in bundle.evidence_sources.items():
        if source["machine_id"] not in bundle.machines:
            raise ConfigError(f"evidence source {source_id} names unknown machine {source['machine_id']}")
    for role_id, deployment in bundle.deployment_roles.items():
        if deployment["role"] not in roles:
            raise ConfigError(f"deployment role {role_id} names unavailable machine role {deployment['role']}")
        auxiliary_ids: set[str] = set()
        for runtime in deployment["auxiliary_python_executables"]:
            if not isinstance(runtime, dict) or set(runtime) != {"id", "path", "required_packages"}:
                raise ConfigError(f"deployment role {role_id} has an invalid auxiliary Python declaration")
            if not all(isinstance(runtime[key], str) and runtime[key] for key in ("id", "path")):
                raise ConfigError(f"deployment role {role_id} has an invalid auxiliary Python identity")
            if runtime["id"] in auxiliary_ids or not all(isinstance(item, str) and item for item in runtime["required_packages"]):
                raise ConfigError(f"deployment role {role_id} has duplicate runtime IDs or invalid package names")
            auxiliary_ids.add(runtime["id"])
        model_ids: set[str] = set()
        for model_path in deployment["required_model_paths"]:
            if not isinstance(model_path, dict) or set(model_path) != {"id", "path", "revision", "marker"}:
                raise ConfigError(f"deployment role {role_id} has an invalid required model path")
            if not all(isinstance(model_path[key], str) and model_path[key] for key in model_path):
                raise ConfigError(f"deployment role {role_id} has an incomplete required model path")
            if model_path["id"] in model_ids or Path(model_path["path"]).name != model_path["revision"]:
                raise ConfigError(f"deployment role {role_id} has duplicate or unpinned required model paths")
            model_ids.add(model_path["id"])
    if bundle.migration["campaign_source_id"] not in bundle.evidence_sources:
        raise ConfigError("migration campaign_source_id does not name a configured evidence source")
    if bundle.migration["import_state"] != "legacy_stopped" or bundle.migration["resumption_allowed"]:
        raise ConfigError("initial legacy migration must remain stopped and non-resumable")
    for schedule_id, schedule in bundle.schedules.items():
        if schedule["job_type"] not in bundle.jobs:
            raise ConfigError(f"schedule {schedule_id} names unknown job {schedule['job_type']}")
        if schedule["machine_id"] not in bundle.machines:
            raise ConfigError(f"schedule {schedule_id} names unknown machine {schedule['machine_id']}")
    for machine_id, machine in bundle.machines.items():
        if machine["artifact_transfer_timeout_seconds"] < 1:
            raise ConfigError(f"machine {machine_id} has invalid artifact transfer timeout")
        machine_state = Path(machine["state_root"]).resolve()
        install_root = Path(machine["release_install_root"]).resolve()
        active_link = Path(machine["active_release_link"])
        if not active_link.is_absolute():
            raise ConfigError(f"machine {machine_id} active release link must be absolute")
        active_link = active_link.absolute()
        managed_root = machine_state.parent
        if (
            install_root == managed_root
            or managed_root not in install_root.parents
            or active_link.parent != install_root
        ):
            raise ConfigError(
                f"machine {machine_id} release root must be a bounded sibling under {managed_root} "
                "and its active link must be a direct child"
            )
        unknown_jobs = sorted(set(machine["allowed_job_types"]) - set(bundle.jobs))
        if unknown_jobs:
            raise ConfigError(f"machine {machine_id} allows unknown jobs: {', '.join(unknown_jobs)}")
    for policy_id, policy in bundle.retry_policies.items():
        if len(policy["backoff_seconds"]) > max(0, policy["max_execution_attempts"] - 1):
            raise ConfigError(f"retry policy {policy_id} has too many backoff values")
        unknown_classes = sorted(set(policy["retryable_failure_classes"]) - {item["failure_class"] for item in bundle.failure_codes.values()})
        if unknown_classes:
            raise ConfigError(f"retry policy {policy_id} names unknown failure classes: {', '.join(unknown_classes)}")
    valid_owners = {"mission_hub", "trainbox", "release_process", "operator"}
    for ownership_id, ownership in bundle.ownership.items():
        if ownership["canonical_owner"] not in valid_owners:
            raise ConfigError(f"ownership {ownership_id} has unknown canonical owner")
        unknown_roles = sorted(set(ownership["deployed_roles"]) - roles)
        if unknown_roles:
            raise ConfigError(f"ownership {ownership_id} names unavailable roles: {', '.join(unknown_roles)}")


def load_config_bundle(root: Path | str | None = None) -> ConfigBundle:
    root_path = Path(root or os.environ.get("NINEREEDS_MISSION_HUB_CONFIG", "config/mission_hub")).resolve()
    documents: list[ConfigDocument] = []
    base_path = root_path / "base.toml"
    base = _load_toml(base_path)
    _reject_unknown(base, BASE_SCHEMA, str(base_path))
    if base["schema_version"] != 1:
        raise ConfigError("unsupported base configuration schema_version")
    for section, keys in BASE_SECTIONS.items():
        _reject_unknown(base[section], keys, f"{base_path} [{section}]")
    documents.append(_document(root_path, base_path, "base", base))

    machines = _directory_records(root_path, "machines", "machine", MACHINE_KEYS, documents)
    jobs = _directory_records(root_path, "jobs", "job", JOB_KEYS, documents)
    providers = _records(root_path, root_path / "providers.toml", "providers", PROVIDER_KEYS, documents)
    models = _records(root_path, root_path / "models.toml", "models", MODEL_KEYS, documents)
    prompts = _directory_records(root_path, "prompts", "prompt", PROMPT_KEYS, documents)
    evidence_sources = _records(
        root_path,
        root_path / "legacy_sources.toml",
        "evidence_sources",
        EVIDENCE_SOURCE_KEYS,
        documents,
    )
    deployment_roles = _records(
        root_path,
        root_path / "deployments.toml",
        "deployment_roles",
        DEPLOYMENT_ROLE_KEYS,
        documents,
    )
    migration_path = root_path / "migration.toml"
    migration_doc = _load_toml(migration_path)
    if set(migration_doc) != {"schema_version", "migration"} or migration_doc["schema_version"] != 1:
        raise ConfigError(f"{migration_path} must contain schema_version=1 and [migration]")
    migration = migration_doc["migration"]
    if not isinstance(migration, dict):
        raise ConfigError(f"{migration_path} [migration] must be a table")
    _reject_unknown(migration, MIGRATION_KEYS, f"{migration_path} [migration]")
    documents.append(_document(root_path, migration_path, "migration", migration_doc))
    retry_policies = _records(root_path, root_path / "retry_policies.toml", "retry_policies", RETRY_POLICY_KEYS, documents)
    failure_codes = _records(root_path, root_path / "failure_codes.toml", "failure_codes", FAILURE_CODE_KEYS, documents)
    routes = _records(root_path, root_path / "routes.toml", "routes", ROUTE_KEYS, documents)
    schedules = _records(root_path, root_path / "schedules.toml", "schedules", SCHEDULE_KEYS, documents)
    artifact_types = _records(root_path, root_path / "artifact_types.toml", "artifact_types", ARTIFACT_TYPE_KEYS, documents)
    budget_path = root_path / "budgets.toml"
    budget_doc = _load_toml(budget_path)
    if set(budget_doc) != {"schema_version", "budget"} or budget_doc["schema_version"] != 1:
        raise ConfigError(f"{budget_path} must contain schema_version=1 and [budget]")
    budget = budget_doc["budget"]
    if not isinstance(budget, dict):
        raise ConfigError(f"{budget_path} [budget] must be a table")
    _reject_unknown(budget, BUDGET_KEYS, f"{budget_path} [budget]")
    documents.append(_document(root_path, budget_path, "budget", budget_doc))
    retention_path = root_path / "retention.toml"
    retention_doc = _load_toml(retention_path)
    if set(retention_doc) != {"schema_version", "retention"} or retention_doc["schema_version"] != 1:
        raise ConfigError(f"{retention_path} must contain schema_version=1 and [retention]")
    retention = retention_doc["retention"]
    if not isinstance(retention, dict):
        raise ConfigError(f"{retention_path} [retention] must be a table")
    _reject_unknown(retention, RETENTION_KEYS, f"{retention_path} [retention]")
    if retention["mode"] not in {"report_only", "protected_registry_automatic"}:
        raise ConfigError(f"{retention_path} has an unsupported retention mode")
    if retention["scan_interval_seconds"] < 60:
        raise ConfigError(f"{retention_path} scan interval must be at least 60 seconds")
    if not 60 <= retention["inventory_timeout_seconds"] <= 21600:
        raise ConfigError(f"{retention_path} inventory timeout must be between one minute and six hours")
    if not retention["build_roots"] or not all(isinstance(value, str) and Path(value).is_absolute() for value in retention["build_roots"]):
        raise ConfigError(f"{retention_path} build roots must be non-empty absolute paths")
    if not retention["build_file_suffixes"] or not all(isinstance(value, str) and value.startswith(".") for value in retention["build_file_suffixes"]):
        raise ConfigError(f"{retention_path} build suffixes must be dot-prefixed strings")
    if not (0 < retention["warning_used_fraction"] <= retention["proposal_used_fraction"] <= retention["critical_used_fraction"] < 1):
        raise ConfigError(f"{retention_path} disk thresholds must be ordered fractions")
    automatic = retention["mode"] == "protected_registry_automatic"
    if automatic != bool(base["safety"]["automatic_pruning"]):
        raise ConfigError("automatic pruning and protected-registry retention mode must agree")
    if automatic == bool(retention["deletion_requires_decision"]):
        raise ConfigError("automatic retention cannot also require a per-run deletion decision")
    documents.append(_document(root_path, retention_path, "retention", retention_doc))
    ownership = _records(root_path, root_path / "ownership.toml", "ownership", OWNERSHIP_KEYS, documents)
    identity_path = root_path / "identity_policy.toml"
    identity_doc = _load_toml(identity_path)
    if set(identity_doc) != {"schema_version", "identity_policy"} or identity_doc["schema_version"] != 1:
        raise ConfigError(f"{identity_path} must contain schema_version=1 and [identity_policy]")
    identity_policy = identity_doc["identity_policy"]
    if not isinstance(identity_policy, dict):
        raise ConfigError(f"{identity_path} [identity_policy] must be a table")
    _reject_unknown(identity_policy, IDENTITY_POLICY_KEYS, f"{identity_path} [identity_policy]")
    if identity_policy["consciousness_policy"] != "excluded_from_ninereeds_identity":
        raise ConfigError("Ninereeds identity policy must exclude consciousness claims and denials")
    if identity_policy["default_identity_scope"] != "excluded":
        raise ConfigError("ordinary lessons must exclude incidental Ninereeds identity classification")
    for field in ("identity_axioms", "revision_capabilities", "obsolete_assumptions", "forbidden_patterns"):
        values = identity_policy[field]
        if not values or not all(isinstance(value, str) and value.strip() for value in values):
            raise ConfigError(f"identity policy {field} must be a non-empty string list")
    try:
        for pattern in identity_policy["forbidden_patterns"]:
            re.compile(pattern)
    except re.error as exc:
        raise ConfigError(f"identity policy contains an invalid exclusion pattern: {exc}") from exc
    documents.append(_document(root_path, identity_path, "identity_policy", identity_doc))
    campaign_modes = _records(
        root_path, root_path / "campaign_modes.toml", "campaign_modes", CAMPAIGN_MODE_KEYS, documents,
    )
    required_modes = {"bootstrap", "advancement", "experimental", "evolutionary", "merge"}
    if set(campaign_modes) != required_modes:
        raise ConfigError("campaign modes must define exactly bootstrap, advancement, experimental, evolutionary, and merge")
    for mode_id, mode in campaign_modes.items():
        if mode["required_evidence"] != ["behavioral_chat", "mri_activation"]:
            raise ConfigError(f"campaign mode {mode_id} must require behavioral chat and MRI activation evidence")
        if mode["comparison_scope"] not in {"milestone", "candidate_vs_parent", "observational", "branches_after_completion", "merged_system"}:
            raise ConfigError(f"campaign mode {mode_id} has an invalid comparison scope")
        if mode["minimum_branches"] < 0 or mode["minimum_merge_sources"] < 0:
            raise ConfigError(f"campaign mode {mode_id} has invalid source/branch bounds")
    if campaign_modes["evolutionary"]["minimum_branches"] < 2:
        raise ConfigError("evolutionary campaigns must require at least two branches")
    if campaign_modes["merge"]["minimum_merge_sources"] < 2:
        raise ConfigError("merge campaigns must require at least two source lineages")

    snapshot_payload = {
        doc.relative_path: {"kind": doc.kind, "sha256": doc.sha256, "data": doc.data}
        for doc in sorted(documents, key=lambda item: item.relative_path)
    }
    bundle = ConfigBundle(
        root=root_path,
        documents=tuple(sorted(documents, key=lambda item: item.relative_path)),
        base=base,
        machines=machines,
        jobs=jobs,
        providers=providers,
        models=models,
        prompts=prompts,
        evidence_sources=evidence_sources,
        deployment_roles=deployment_roles,
        migration=migration,
        retry_policies=retry_policies,
        failure_codes=failure_codes,
        routes=routes,
        schedules=schedules,
        artifact_types=artifact_types,
        budget=budget,
        retention=retention,
        ownership=ownership,
        failure_logging=base["failure_logging"],
        emergency=base["emergency"],
        recovery=base["recovery"],
        contracts=base["contracts"],
        orchestration=base["orchestration"],
        model_defaults=base["model_defaults"],
        visual=base["visual"],
        training=base["training"],
        evaluation=base["evaluation"],
        identity_policy=identity_policy,
        campaign_modes=campaign_modes,
        sha256=content_hash(snapshot_payload),
    )
    _validate_relations(bundle)
    return bundle


def config_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.toml")):
        if path.is_file():
            yield path


def bundle_from_snapshot(root: Path | str, payload: dict[str, Any]) -> ConfigBundle:
    """Rehydrate the exact persisted configuration without repository memory.

    Schema and handler files still come from the active role release; all
    operational values and identities come from the authoritative snapshot.
    """
    if payload.get("schema_version") != "ninereeds_config_snapshot_v1":
        raise ConfigError("persisted configuration snapshot has an unsupported schema")
    resolved = payload.get("resolved")
    if not isinstance(resolved, dict):
        raise ConfigError("persisted configuration snapshot has no resolved values")
    root_path = Path(root).resolve()
    documents = tuple(
        ConfigDocument(
            relative_path=item["path"], kind=item["kind"], data={}, sha256=item["sha256"],
        )
        for item in payload.get("documents", [])
    )
    required = {
        "base", "machines", "jobs", "providers", "models", "prompts", "evidence_sources",
        "deployment_roles", "migration", "retry_policies", "failure_codes", "routes", "schedules",
        "artifact_types", "budget", "retention", "ownership", "failure_logging", "emergency",
        "recovery", "contracts", "orchestration", "model_defaults", "visual", "training",
        "evaluation", "identity_policy", "campaign_modes",
    }
    missing = sorted(required - set(resolved))
    if missing:
        raise ConfigError("persisted configuration snapshot is incomplete: " + ", ".join(missing))
    bundle = ConfigBundle(
        root=root_path, documents=documents,
        base=resolved["base"], machines=resolved["machines"], jobs=resolved["jobs"],
        providers=resolved["providers"], models=resolved["models"], prompts=resolved["prompts"],
        evidence_sources=resolved["evidence_sources"], deployment_roles=resolved["deployment_roles"],
        migration=resolved["migration"], retry_policies=resolved["retry_policies"],
        failure_codes=resolved["failure_codes"], routes=resolved["routes"], schedules=resolved["schedules"],
        artifact_types=resolved["artifact_types"], budget=resolved["budget"], retention=resolved["retention"],
        ownership=resolved["ownership"], failure_logging=resolved["failure_logging"], emergency=resolved["emergency"],
        recovery=resolved["recovery"], contracts=resolved["contracts"], orchestration=resolved["orchestration"],
        model_defaults=resolved["model_defaults"], visual=resolved["visual"], training=resolved["training"],
        evaluation=resolved["evaluation"], identity_policy=resolved["identity_policy"],
        campaign_modes=resolved["campaign_modes"], sha256=payload["bundle_sha256"],
    )
    _validate_relations(bundle)
    return bundle
