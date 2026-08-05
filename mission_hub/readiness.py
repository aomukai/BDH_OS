"""Evidence-backed commissioning and training restart gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ConfigBundle
from .deployment import DeploymentBuilder
from .store import MissionHubStore


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
    locks = not safety["live_execution"] and not safety["automatic_pruning"] and not safety["automatic_campaign_rollover"] and not safety["allow_git_mutation"]
    check("initial_safety_locks", locks, json.dumps(safety, sort_keys=True), gate="backend")
    check("external_calls_disabled", not bundle.budget["external_calls_enabled"], f"external_calls_enabled={bundle.budget['external_calls_enabled']}", gate="backend")
    check("schedules_disabled", not any(item["enabled"] for item in bundle.schedules.values()), "all schedules must remain disabled before commissioning", gate="backend")

    builder = DeploymentBuilder(repo_root, bundle)
    source_manifests = {role_id: builder.source_manifest(role_id) for role_id in bundle.deployment_roles}
    clean_roles = sorted(role_id for role_id, manifest in source_manifests.items() if manifest["git_clean"])
    check("clean_role_sources", len(clean_roles) == len(source_manifests), f"clean={clean_roles} required={sorted(source_manifests)}", gate="commissioning")

    deployments = store.list_rows("deployments", limit=1000)
    active_roles = {row["role"] for row in deployments if row["status"] == "active"}
    check("active_role_deployments", active_roles == {"mission_hub", "trainbox"}, f"active_roles={sorted(active_roles)}", gate="commissioning")
    # A completed commissioning healthcheck remains evidence after the trainbox is
    # returned to maintenance.  Leaving maintenance is a training-restart
    # prerequisite, not a condition for remembering that commissioning succeeded.
    check("trainbox_out_of_maintenance", not bundle.machines["trainbox"]["maintenance_mode"], f"maintenance_mode={bundle.machines['trainbox']['maintenance_mode']}", gate="training_restart")

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

    checkpoint_sources = [
        json.loads(row["manifest_json"])
        for row in evidence
        if json.loads(row["manifest_json"]).get("source_id") == "trainbox-checkpoint-index"
    ]
    checkpoint_content_hashed = bool(checkpoint_sources) and any(item.get("hash_content") for item in checkpoint_sources)
    check("checkpoint_content_certification", checkpoint_content_hashed, "selected lineage checkpoints require content hashes, not metadata hashes", gate="training_restart")
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
