"""Typed, versioned Mission Hub configuration loader.

Configuration is intentionally fail-closed: unknown keys are rejected, every
document is hashed, and activation stores the complete resolved bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tomllib
from typing import Any, Iterable

from .errors import ConfigError
from .jsonutil import content_hash


ROOT_FILES = ("base.toml", "providers.toml", "models.toml")


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
            },
        }


BASE_SCHEMA = {
    "schema_version": int,
    "hub": dict,
    "safety": dict,
    "scheduler": dict,
    "artifacts": dict,
    "protocol": dict,
    "api": dict,
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
    "artifacts": {
        "manifest_algorithm": str,
        "deletion_requires_approval": bool,
        "retention_mode": str,
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
    "priority": int,
    "timeout_seconds": int,
    "max_attempts": int,
    "retry_policy": str,
    "input_schema": str,
    "output_schema": str,
    "artifact_types": list,
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
        for schema_key in ("input_schema", "output_schema"):
            schema_path = (repo_root / job[schema_key]).resolve()
            if not schema_path.is_file() or repo_root.resolve() not in schema_path.parents:
                raise ConfigError(f"job {job_id} has unavailable {schema_key}: {job[schema_key]}")
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
    for route_id, route in bundle.routes.items():
        unknown_models = sorted(set(route["ordered_model_ids"]) - set(bundle.models))
        if unknown_models:
            raise ConfigError(f"route {route_id} names unknown models: {', '.join(unknown_models)}")
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
    documents.append(_document(root_path, retention_path, "retention", retention_doc))
    ownership = _records(root_path, root_path / "ownership.toml", "ownership", OWNERSHIP_KEYS, documents)

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
        sha256=content_hash(snapshot_payload),
    )
    _validate_relations(bundle)
    return bundle


def config_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*.toml")):
        if path.is_file():
            yield path
