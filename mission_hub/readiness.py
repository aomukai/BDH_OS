"""Evidence-backed commissioning and training restart gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ConfigBundle, machine_id_for_role
from .deployment import DeploymentBuilder
from .store import MissionHubStore
from .campaign_contract import validate_campaign_contract


def readiness_report(store: MissionHubStore, bundle: ConfigBundle, *, repo_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(check_id: str, passed: bool, detail: str, *, gate: str) -> None:
        checks.append({"id": check_id, "passed": passed, "detail": detail, "gate": gate})

    integrity = store.integrity_report()
    check("database_integrity", integrity["sqlite_integrity"] == "ok" and not integrity["foreign_key_errors"], json.dumps(integrity, sort_keys=True), gate="backend")
    check("event_chain", integrity["event_chain_ok"], f"events={integrity['event_count']}", gate="backend")
    active = store.active_config()
    check("active_config_matches", active["sha256"] == bundle.sha256, f"active={active['sha256']} loaded={bundle.sha256}", gate="backend")

    evidence = store.list_rows("evidence_sources", limit=1000)
    preserved_source_ids = {
        json.loads(row["manifest_json"]).get("source_id")
        for row in evidence
    }
    required_sources = {source["id"] for source in bundle.evidence_sources.values() if source["required"]}
    missing_sources = sorted(required_sources - preserved_source_ids)
    check("required_evidence", not missing_sources, f"missing={missing_sources}", gate="backend")

    campaigns = {row["id"]: row for row in store.list_rows("campaigns", limit=1000)}
    legacy_id = "play-word-evolution-0501-2000-v1"
    frozen = campaigns.get(legacy_id)
    check("legacy_campaign_frozen", frozen is not None and frozen["state"] == "legacy_stopped", f"state={None if frozen is None else frozen['state']}", gate="backend")

    safety = bundle.base["safety"]
    protected_retention = (
        safety["automatic_pruning"]
        and bundle.retention["mode"] == "protected_registry_automatic"
        and not bundle.retention["deletion_requires_decision"]
        and bool(bundle.retention["build_roots"])
    )
    locks = protected_retention and not safety["automatic_campaign_rollover"] and not safety["allow_git_mutation"]
    check("backend_safety_locks", locks, json.dumps(safety, sort_keys=True), gate="backend")
    enabled_remote_models = [
        model["id"] for model in bundle.models.values()
        if model["enabled"] and not model["local"]
        and bundle.providers[model["provider"]]["enabled"]
    ]
    external_policy_consistent = (
        not bundle.budget["external_calls_enabled"] or bool(enabled_remote_models)
    )
    check(
        "external_call_policy",
        external_policy_consistent,
        f"external_calls_enabled={bundle.budget['external_calls_enabled']} enabled_remote_models={enabled_remote_models}",
        gate="backend",
    )
    check("schedules_disabled", not any(item["enabled"] for item in bundle.schedules.values()), "all schedules must remain disabled before commissioning", gate="backend")
    check(
        "critical_failure_logging",
        bundle.failure_logging["enabled"] and bundle.failure_logging["retention_days"] == 7,
        f"enabled={bundle.failure_logging['enabled']} retention_days={bundle.failure_logging['retention_days']}",
        gate="backend",
    )
    check(
        "emergency_authority_bounded",
        bundle.emergency["mode"] in {"disabled", "sol_advisory"},
        f"mode={bundle.emergency['mode']} (Sol output is advisory only)",
        gate="backend",
    )

    builder = DeploymentBuilder(repo_root, bundle)
    source_manifests = {role_id: builder.source_manifest(role_id) for role_id in bundle.deployment_roles}
    clean_roles = sorted(role_id for role_id, manifest in source_manifests.items() if manifest["git_clean"])
    check("clean_role_sources", len(clean_roles) == len(source_manifests), f"clean={clean_roles} required={sorted(source_manifests)}", gate="commissioning")

    deployments = store.list_rows("deployments", limit=1000)
    active_deployments = [row for row in deployments if row["status"] == "active"]
    active_roles = {row["role"] for row in active_deployments}
    stale_roles = sorted(
        row["role"] for row in active_deployments
        if row.get("config_snapshot_id") != active.get("id")
    )
    current_source_by_role = {
        manifest["role"]: manifest["source_sha256"]
        for manifest in source_manifests.values()
    }
    stale_source_roles = sorted(
        row["role"] for row in active_deployments
        if row.get("source_sha256") != current_source_by_role.get(row["role"])
    )
    required_roles = {machine["role"] for machine in bundle.machines.values() if machine["enabled"]}
    check(
        "active_role_deployments",
        active_roles == required_roles and not stale_roles and not stale_source_roles,
        (
            f"active_roles={sorted(active_roles)} stale_config_roles={stale_roles} "
            f"stale_source_roles={stale_source_roles}"
        ),
        gate="commissioning",
    )
    # A completed commissioning healthcheck remains evidence after the trainbox is
    # returned to maintenance.  Leaving maintenance is a training-restart
    # prerequisite, not a condition for remembering that commissioning succeeded.
    executor_machine = machine_id_for_role(bundle, "trainbox")
    check(
        "trainbox_out_of_maintenance",
        not bundle.machines[executor_machine]["maintenance_mode"],
        f"maintenance_mode={bundle.machines[executor_machine]['maintenance_mode']}",
        gate="training_restart",
    )

    completed_health = any(
        row["job_type"] == "system.healthcheck" and row["status"] == "succeeded"
        for row in store.list_rows("jobs", limit=1000)
    )
    check("commissioning_healthcheck", completed_health, f"completed={completed_health}", gate="commissioning")

    completed_job_types = {
        row["job_type"]
        for row in store.list_rows("jobs", limit=1000)
        if row["status"] == "succeeded"
    }
    check(
        "artifact_path_commissioned",
        "system.artifact_roundtrip" in completed_job_types,
        f"completed={'system.artifact_roundtrip' in completed_job_types}",
        gate="execution_paths",
    )
    check(
        "bounded_gpu_commissioned",
        "system.gpu_probe" in completed_job_types,
        f"completed={'system.gpu_probe' in completed_job_types}",
        gate="execution_paths",
    )

    artifacts = store.list_rows("artifacts", limit=10000)
    certified_checkpoints = [
        row for row in artifacts
        if row["kind"] == "checkpoint"
        and json.loads(row["manifest_json"]).get("certification_scope") == "byte_identity_only"
        and row["lifecycle"] != "deleted"
    ]
    built_corpora = [
        row for row in artifacts
        if row["kind"] == "corpus"
        and json.loads(row["manifest_json"]).get("schema_version") in {
            "ninereeds_corpus_artifact_v1", "ninereeds_ordered_training_corpus_v1",
        }
        and row["lifecycle"] != "deleted"
    ]
    check("checkpoint_content_certification", bool(certified_checkpoints), f"certified_checkpoint_artifacts={len(certified_checkpoints)}", gate="training_restart")
    check("immutable_corpus_registered", bool(built_corpora), f"contract_corpus_artifacts={len(built_corpora)}", gate="training_restart")

    configured_campaigns: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for row in campaigns.values():
        try:
            metadata = json.loads(row.get("metadata_json") or "{}")
            contract = validate_campaign_contract(metadata.get("campaign_contract"), bundle.campaign_modes)
        except (ValueError, TypeError, KeyError, RuntimeError) as exc:
            # Legacy and unrelated draft campaigns are not training-restart
            # candidates. Safety validation is repeated below for the selected
            # configured campaign only.
            del exc
            continue
        if row["state"] == "active" and metadata.get("schema_version") == "ninereeds_configured_campaign_reconciliation_v1":
            configured_campaigns.append((row, metadata | {"campaign_contract": contract}))
    check(
        "configured_training_campaign", len(configured_campaigns) == 1,
        f"active_configured_campaigns={[row['id'] for row, _ in configured_campaigns]}",
        gate="training_restart",
    )
    selected_metadata = configured_campaigns[0][1] if len(configured_campaigns) == 1 else {}
    starting_checkpoint_id = selected_metadata.get("starting_checkpoint_artifact_id")
    certified_ids = {row["id"] for row in certified_checkpoints}
    check(
        "campaign_baseline_certified", starting_checkpoint_id in certified_ids,
        f"starting_checkpoint_artifact_id={starting_checkpoint_id}", gate="training_restart",
    )
    probe_reports = [
        json.loads(row["manifest_json"])
        for row in artifacts if row["kind"] == "probe_report" and row["lifecycle"] != "deleted"
    ]
    compatible = any(
        item.get("checkpoint_artifact_id") == starting_checkpoint_id
        and item.get("compatibility_certified") is True
        for item in probe_reports
    )
    check("campaign_baseline_compatible", compatible, f"compatible_probe={compatible}", gate="training_restart")
    evaluation_suites = [row for row in artifacts if row["kind"] == "evaluation_suite" and row["lifecycle"] != "deleted"]
    check("evaluation_suite_registered", bool(evaluation_suites), f"evaluation_suites={len(evaluation_suites)}", gate="training_restart")

    workflows = store.list_rows("cortex_workflows", limit=1000) if configured_campaigns else []
    active_workflows = [
        row for row in workflows
        if row["status"] == "active"
        and row["campaign_id"] == configured_campaigns[0][0]["id"]
        and (row.get("reauthorized_config_snapshot_id") or row.get("config_snapshot_id")) == active["id"]
    ] if configured_campaigns else []
    check("authorized_cortex_workflow", len(active_workflows) == 1, f"active_workflows={len(active_workflows)}", gate="training_restart")
    workflow_specification = json.loads(active_workflows[0]["specification_json"]) if len(active_workflows) == 1 else {}
    sessions = workflow_specification.get("sessions", [])
    workflow_corpus_ids = {
        item.get("corpus_artifact_id") for item in sessions if isinstance(item, dict)
    }
    ordered_corpus_ids = {
        row["id"] for row in built_corpora
        if json.loads(row["manifest_json"]).get("schema_version") == "ninereeds_ordered_training_corpus_v1"
    }
    workflow_corpora_ready = bool(sessions) and workflow_corpus_ids <= ordered_corpus_ids
    check(
        "workflow_ordered_corpora", workflow_corpora_ready,
        f"sessions={len(sessions)} registered={len(workflow_corpus_ids & ordered_corpus_ids)}",
        gate="training_restart",
    )
    validated_corpus_ids = {
        json.loads(row["input_json"]).get("corpus_artifact_id")
        for row in store.list_rows("jobs", limit=10000)
        if row["job_type"] == "corpus.validate" and row["status"] == "succeeded"
    }
    check(
        "workflow_corpora_validated",
        bool(workflow_corpus_ids) and workflow_corpus_ids <= validated_corpus_ids,
        f"required={len(workflow_corpus_ids)} validated={len(workflow_corpus_ids & validated_corpus_ids)}",
        gate="training_restart",
    )
    knowledge_count = 0
    if starting_checkpoint_id in certified_ids:
        knowledge_count = len(store.checkpoint_knowledge(starting_checkpoint_id))
    check(
        "baseline_knowledge_snapshot", knowledge_count > 0,
        f"known_concepts={knowledge_count}", gate="training_restart",
    )
    check("live_execution_authorized", safety["live_execution"], f"live_execution={safety['live_execution']}", gate="training_restart")
    check("train_jobs_enabled", bundle.jobs["model.train"]["enabled"] and bundle.jobs["model.evaluate"]["enabled"], "train/evaluate jobs remain disabled", gate="training_restart")

    return {
        "schema_version": "ninereeds_readiness_report_v1",
        "backend_ready": all(item["passed"] for item in checks if item["gate"] == "backend"),
        "commissioning_ready": all(item["passed"] for item in checks if item["gate"] in {"backend", "commissioning"}),
        "execution_paths_ready": all(item["passed"] for item in checks if item["gate"] in {"backend", "commissioning", "execution_paths"}),
        "training_restart_ready": all(item["passed"] for item in checks),
        "checks": checks,
    }
