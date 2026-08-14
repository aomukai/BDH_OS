"""Operator and restricted-agent CLI for the Ninereeds Mission Hub."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

from .agent import TrainboxAgent
from .config import ConfigBundle, load_config_bundle, machine_id_for_role
from .deployment import DeploymentBuilder
from .evidence import EvidenceArchive
from .errors import MissionHubError
from .jsonutil import content_hash
from .store import MissionHubStore
from .service import MissionHubService
from .transport import SSHDispatcher
from .migration import LegacyMigrator
from .scheduler import Scheduler
from .api import serve
from .daemon import run_daemon
from .attest import environment_attestation
from .readiness import readiness_report
from .lab import LabStore
from .visual_workflow import VisualWorkflowCoordinator
from .material_workflow import MaterialWorkflowCoordinator
from .cortex_workflow import CortexWorkflowCoordinator
from .configured_campaign import ConfiguredCortexCampaign
from .configured_gate_credit import ConfiguredGateCreditCampaign
from .configured_campaign35 import ConfiguredCampaign35
from .retention import RetentionManager
from .recovery import RecoveryManager


def _json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _bundle(args: argparse.Namespace) -> ConfigBundle:
    return load_config_bundle(args.config)


def _store(args: argparse.Namespace, bundle: ConfigBundle) -> MissionHubStore:
    path = Path(args.database) if args.database else Path(bundle.base["hub"]["state_root"]) / bundle.base["hub"]["database_name"]
    return MissionHubStore(path, busy_timeout_ms=bundle.base["hub"]["busy_timeout_ms"])


def _environment(role: dict[str, Any]) -> dict[str, Any]:
    result = environment_attestation(
        role["python_site_paths"], role["auxiliary_python_executables"],
        role["required_model_paths"],
    )
    result["declared_python_executable"] = role["python_executable"]
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/mission_hub")
    parser.add_argument("--database")
    parser.add_argument("--actor", default=os.environ.get("USER", "operator"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("config-validate")
    commands.add_parser("initialize")
    commands.add_parser("config-activate")
    commands.add_parser("lab-draft-rebase")
    commands.add_parser("status")
    migrate = commands.add_parser("legacy-migrate-current-campaign")
    migrate.add_argument("--archive-root")
    campaign_create = commands.add_parser("campaign-create")
    campaign_create.add_argument("--specification", required=True, help="Campaign JSON object or @path")
    campaign_close = commands.add_parser("campaign-close")
    campaign_close.add_argument("campaign_id")
    campaign_close.add_argument("--review-artifact-id", required=True)

    deployment = commands.add_parser("deployment-register-current")
    deployment.add_argument("--role-id", required=True)
    deployment.add_argument("--machine-id", required=True)
    deployment.add_argument("--activate", action="store_true")
    deployment.add_argument("--archive-output")
    deployment.add_argument("--environment-json", help="Target-host attestation JSON or @path")
    reject_deployment = commands.add_parser("deployment-reject")
    reject_deployment.add_argument("deployment_id")
    reject_deployment.add_argument("--reason", required=True)

    evidence = commands.add_parser("evidence-capture")
    evidence.add_argument("--machine-id", required=True)
    evidence.add_argument("--archive-root")
    evidence.add_argument("--capture-id", action="append", default=[])
    evidence.add_argument("--no-import", action="store_true")

    evidence_import = commands.add_parser("evidence-import")
    evidence_import.add_argument("--archive-root", required=True)
    evidence_import.add_argument("--snapshot-sha256", action="append", required=True)

    ingest = commands.add_parser("artifact-ingest")
    ingest.add_argument("--kind", required=True)
    ingest.add_argument("--path", required=True)
    ingest.add_argument("--lifecycle", choices=["observed", "candidate"], default="observed")
    ingest.add_argument("--manifest", required=True, help="JSON object or @path")
    materialize = commands.add_parser("artifact-materialize")
    materialize.add_argument("artifact_id")
    materialize.add_argument("--machine-id", required=True)
    retrieve = commands.add_parser("artifact-retrieve")
    retrieve.add_argument("artifact_id")
    retrieve.add_argument("--machine-id", required=True)
    protect = commands.add_parser("artifact-protect")
    protect.add_argument("artifact_id")
    protect.add_argument("--key", default="operator-pin")
    protect.add_argument("--reason", required=True)
    release_protection = commands.add_parser("artifact-protection-release")
    release_protection.add_argument("protection_id")
    path_protect = commands.add_parser("path-protect")
    path_protect.add_argument("--machine-id", required=True)
    path_protect.add_argument("--path", required=True)
    path_protect.add_argument("--key", default="operator-pin")
    path_protect.add_argument("--reason", required=True)
    path_release = commands.add_parser("path-protection-release")
    path_release.add_argument("protection_id")
    commands.add_parser("retention-reconcile")
    retention_preview = commands.add_parser("retention-preview")
    retention_preview.add_argument("--machine-id", default="trainbox")
    retention_apply = commands.add_parser("retention-apply")
    retention_apply.add_argument("--machine-id", default="trainbox")
    retention_apply.add_argument("--plan-sha256", required=True)
    retention_apply.add_argument("--acknowledgement", required=True)
    retention_auto = commands.add_parser("retention-auto-tick")
    retention_auto.add_argument("--machine-id", default="trainbox")
    campaign_storage = commands.add_parser("campaign-storage-prepare")
    campaign_storage.add_argument("campaign_id")
    campaign_storage.add_argument("--required-free-bytes", type=int, required=True)
    campaign_storage.add_argument("--machine-id", default="trainbox")
    campaign_storage_declare = commands.add_parser("campaign-storage-declare")
    campaign_storage_declare.add_argument("campaign_id")
    campaign_storage_declare.add_argument("--required-free-bytes", type=int, required=True)
    campaign_storage_declare.add_argument("--estimated-build-count", type=int, required=True)
    order_certify = commands.add_parser("training-order-certify")
    order_certify.add_argument("--type", choices=["model.train", "model.visual_train", "model.multimodal_train"], required=True)
    order_certify.add_argument("--input", required=True, help="Prospective training input JSON object or @path")
    order_certify.add_argument("--campaign-id", required=True)
    knowledge_seed = commands.add_parser("checkpoint-knowledge-seed")
    knowledge_seed.add_argument("--checkpoint-artifact-id", required=True)
    knowledge_seed.add_argument("--campaign-id", required=True)
    knowledge_seed.add_argument("--session-id", required=True)
    knowledge_seed.add_argument("--concepts", required=True, help="JSON string array or @path")
    knowledge_seed.add_argument("--evidence", required=True, help="JSON string array or @path")

    job = commands.add_parser("job-create")
    job.add_argument("--type", required=True)
    job.add_argument("--input", required=True, help="JSON object or @path")
    job.add_argument("--idempotency-key", required=True)
    job.add_argument("--machine-id")
    job.add_argument("--campaign-id")

    approve = commands.add_parser("job-approve")
    approve.add_argument("job_id")
    cancel = commands.add_parser("job-cancel")
    cancel.add_argument("job_id")
    cancel.add_argument("--reason", required=True)
    expire = commands.add_parser("leases-expire")
    dispatch = commands.add_parser("dispatch-once")
    dispatch.add_argument("--machine-id", required=True)
    commands.add_parser("schedule-tick")
    visual_create = commands.add_parser("visual-workflow-create")
    visual_create.add_argument("--specification", required=True, help="JSON object or @path")
    commands.add_parser("visual-workflow-tick")
    visual_migrate = commands.add_parser("visual-workflow-migrate-fanout")
    visual_migrate.add_argument("workflow_id")
    visual_reauthorize = commands.add_parser("visual-workflows-reauthorize-queued")
    visual_reauthorize.add_argument("--campaign-id", required=True)
    visual_reauthorize.add_argument("--reason", required=True)
    material_create = commands.add_parser("material-workflow-create")
    material_create.add_argument("--specification", required=True, help="JSON object or @path")
    commands.add_parser("material-workflow-tick")
    cortex_create = commands.add_parser("cortex-workflow-create")
    cortex_create.add_argument("--specification", required=True, help="Cortex workflow JSON object or @path")
    commands.add_parser("cortex-workflow-tick")
    configured = commands.add_parser("configured-campaign-reconcile")
    configured.add_argument("--specification", required=True)
    configured.add_argument("--authorize-branch", action="append", default=[])
    configured_validate = commands.add_parser("configured-campaign-validate")
    configured_validate.add_argument("--specification", required=True)
    configured_validate.add_argument("--branch", required=True)
    gate_credit = commands.add_parser("configured-gate-credit-reconcile")
    gate_credit.add_argument("--specification", required=True)
    gate_credit.add_argument("--authorize-branch", action="append", default=[])
    commands.add_parser("campaign35-commission-real-run")
    campaign35_visual_recover = commands.add_parser("campaign35-visual-recover")
    campaign35_visual_recover.add_argument("--authorization-reference", required=True)
    campaign35_visual_recover.add_argument("--expected-exact-restarts", required=True, type=int)
    campaign35_visual_recover.add_argument("--expected-seed-replacements", required=True, type=int)
    campaign35_visual_recover.add_argument("--seed-offset", type=int, default=100_000_000)
    campaign35_visual_resume = commands.add_parser("campaign35-visual-resume-queue-expired")
    campaign35_visual_resume.add_argument("--reason", required=True)
    campaign35_visual_resume.add_argument("--expected-count", required=True, type=int)
    cortex_retry = commands.add_parser("cortex-workflow-retry")
    cortex_retry.add_argument("workflow_id")
    cortex_retry.add_argument("--reason", required=True)
    cortex_restart = commands.add_parser("cortex-workflow-restart")
    cortex_restart.add_argument("workflow_id")
    cortex_restart.add_argument("--reason", required=True)
    cortex_reauthorize = commands.add_parser("cortex-workflows-reauthorize-queued")
    cortex_reauthorize.add_argument("--campaign-id", required=True)
    cortex_reauthorize.add_argument("--reason", required=True)
    cortex_queue_recover = commands.add_parser("cortex-workflow-recover-queue-expired")
    cortex_queue_recover.add_argument("job_id")
    cortex_queue_recover.add_argument("--reason", required=True)
    cortex_retention_reopen = commands.add_parser("cortex-workflow-reopen-retention-repair")
    cortex_retention_reopen.add_argument("workflow_id")
    cortex_retention_reopen.add_argument("--reason", required=True)
    cortex_retention_continue = commands.add_parser("cortex-workflow-continue-retention-gap")
    cortex_retention_continue.add_argument("workflow_id")
    cortex_retention_continue.add_argument("--reason", required=True)
    commands.add_parser("serve")
    commands.add_parser("daemon")
    commands.add_parser("readiness")
    resource_restore = commands.add_parser("recovery-local-resource-restored")
    resource_restore.add_argument("--incident-id", action="append", required=True)
    resource_restore.add_argument("--machine-id", required=True)
    resource_restore.add_argument("--observed-free-bytes", required=True, type=int)
    resource_restore.add_argument("--required-free-bytes", required=True, type=int)
    resource_restore.add_argument("--observed-at", required=True)
    resource_restore.add_argument("--observation", required=True)
    resource_restore.add_argument("--expected-incident-count", required=True, type=int)

    listing = commands.add_parser("list")
    listing.add_argument("entity", choices=["config_snapshots", "machines", "deployments", "campaigns", "decisions", "jobs", "runs", "artifacts", "evidence_sources", "events", "knowledge_records", "training_session_plans", "cortex_workflows", "cortex_workflow_jobs", "visual_workflows", "visual_workflow_jobs", "material_workflows", "material_workflow_jobs", "recovery_incidents", "recovery_attempts", "recovery_actions", "campaign_blocks"])
    listing.add_argument("--limit", type=int, default=100)

    agent = commands.add_parser("agent-execute")
    agent.add_argument("--machine-id", required=True)
    agent.add_argument("--deployment-manifest", required=True)
    return parser


def _input_object(value: str) -> dict[str, Any]:
    text = Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("job input must be a JSON object")
    return parsed


def _input_string_array(value: str) -> list[str]:
    text = Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value
    parsed = json.loads(text)
    if not isinstance(parsed, list) or not parsed or not all(isinstance(item, str) and item for item in parsed):
        raise ValueError("input must be a non-empty JSON string array")
    return parsed


def run(args: argparse.Namespace) -> int:
    bundle = _bundle(args)
    if args.command == "config-validate":
        _json({"valid": True, "bundle_sha256": bundle.sha256, "documents": len(bundle.documents), "jobs": len(bundle.jobs)})
        return 0
    if args.command == "agent-execute":
        deployment = json.loads(Path(args.deployment_manifest).read_text(encoding="utf-8"))
        deployment["id"] = deployment.get("id") or f"dep-{content_hash(deployment)[:16]}"
        envelope = json.load(sys.stdin)
        _json(TrainboxAgent(bundle, machine_id=args.machine_id, deployment=deployment).execute(envelope))
        return 0

    if args.command == "evidence-capture" and args.no_import:
        archive_root = Path(args.archive_root or bundle.base["hub"]["state_root"]) / "evidence"
        archive = EvidenceArchive(archive_root)
        selected = [source for source in bundle.evidence_sources.values() if source["machine_id"] == args.machine_id]
        if args.capture_id:
            wanted = set(args.capture_id)
            selected = [source for source in selected if source["id"] in wanted]
            missing = wanted - {source["id"] for source in selected}
            if missing:
                raise MissionHubError(f"unknown capture ids for machine: {', '.join(sorted(missing))}")
        captured = []
        for source in selected:
            manifest, records = archive.capture(source)
            captured.append({"source_id": source["id"], "snapshot_sha256": manifest["snapshot_sha256"], "files": len(manifest["files"]), "records": len(records), "evidence_id": None})
        _json({"archive_root": str(archive_root), "captured": captured, "imported": False})
        return 0

    store = _store(args, bundle)
    store.initialize()
    if args.command == "initialize":
        _json({"initialized": True, "database": str(store.path)})
    elif args.command == "config-activate":
        snapshot_id = store.activate_config(bundle, actor=args.actor)
        _json({"active_config_snapshot_id": snapshot_id, "sha256": bundle.sha256})
    elif args.command == "lab-draft-rebase":
        active = store.active_config()
        if active["sha256"] != bundle.sha256:
            raise MissionHubError("loaded configuration must be active before rebasing the Lab draft")
        _json(LabStore(store).rebase_latest_draft(bundle, actor=args.actor))
    elif args.command == "status":
        with store._connect() as db:
            recovery = {
                "active_incidents": db.execute("SELECT COUNT(*) FROM recovery_incidents WHERE state NOT IN ('recovered','blocked','escalated')").fetchone()[0],
                "blocked_incidents": db.execute("SELECT COUNT(*) FROM recovery_incidents WHERE state IN ('blocked','escalated')").fetchone()[0],
                "active_campaign_blocks": db.execute("SELECT COUNT(*) FROM campaign_blocks WHERE state='active'").fetchone()[0],
            }
        _json({"database": str(store.path), "config": store.active_config(), "integrity": store.integrity_report(), "recovery": recovery})
    elif args.command == "recovery-local-resource-restored":
        _json(RecoveryManager(store, bundle).retry_after_local_resource_restoration(
            args.incident_id,
            machine_id=args.machine_id,
            observed_free_bytes=args.observed_free_bytes,
            required_free_bytes=args.required_free_bytes,
            observed_at=args.observed_at,
            observation=args.observation,
            expected_incident_count=args.expected_incident_count,
            actor=args.actor,
        ))
    elif args.command == "legacy-migrate-current-campaign":
        archive_root = Path(args.archive_root or bundle.base["hub"]["state_root"]) / "evidence"
        _json(LegacyMigrator(store, bundle, EvidenceArchive(archive_root)).migrate_current_campaign(actor=args.actor))
    elif args.command == "visual-workflow-create":
        _json(store.create_visual_workflow(bundle, _input_object(args.specification), actor=args.actor))
    elif args.command == "visual-workflow-tick":
        _json({"changes": VisualWorkflowCoordinator(store, bundle).tick(actor=args.actor)})
    elif args.command == "visual-workflow-migrate-fanout":
        _json(store.migrate_legacy_visual_workflow_to_fanout(args.workflow_id, actor=args.actor))
    elif args.command == "visual-workflows-reauthorize-queued":
        _json(store.reauthorize_queued_visual_workflows(
            bundle, campaign_id=args.campaign_id, reason=args.reason, actor=args.actor,
        ))
    elif args.command == "material-workflow-create":
        _json(store.create_material_workflow(bundle, _input_object(args.specification), actor=args.actor))
    elif args.command == "material-workflow-tick":
        _json({"changes": MaterialWorkflowCoordinator(store, bundle).tick(actor=args.actor)})
    elif args.command == "cortex-workflow-create":
        _json(store.create_cortex_workflow(bundle, _input_object(args.specification), actor=args.actor))
    elif args.command == "cortex-workflow-tick":
        _json({"changes": CortexWorkflowCoordinator(store, bundle).tick(actor=args.actor)})
    elif args.command == "cortex-workflow-retry":
        _json(store.retry_failed_cortex_stage(
            bundle, args.workflow_id, reason=args.reason, actor=args.actor,
        ))
    elif args.command == "cortex-workflow-restart":
        _json(store.restart_failed_cortex_workflow(
            bundle, args.workflow_id, reason=args.reason, actor=args.actor,
        ))
    elif args.command == "cortex-workflows-reauthorize-queued":
        _json(store.reauthorize_queued_cortex_stages(
            bundle, campaign_id=args.campaign_id, reason=args.reason, actor=args.actor,
        ))
    elif args.command == "cortex-workflow-recover-queue-expired":
        _json(store.recover_queue_expired_cortex_stage(
            bundle, args.job_id, reason=args.reason, actor=args.actor,
        ))
    elif args.command == "cortex-workflow-reopen-retention-repair":
        _json(store.reopen_cortex_workflow_after_retention_repair(
            args.workflow_id, reason=args.reason, actor=args.actor,
        ))
    elif args.command == "cortex-workflow-continue-retention-gap":
        _json(store.continue_cortex_workflow_after_retention_evaluation_gap(
            bundle, args.workflow_id, reason=args.reason, actor=args.actor,
        ))
    elif args.command == "configured-campaign-reconcile":
        configured_campaign = ConfiguredCortexCampaign(
            store, bundle, repo_root=Path.cwd(),
            specification_path=Path(args.specification),
        )
        _json(configured_campaign.reconcile(
            actor=args.actor, authorize_branches=args.authorize_branch,
        ))
    elif args.command == "configured-campaign-validate":
        configured_campaign = ConfiguredCortexCampaign(
            store, bundle, repo_root=Path.cwd(),
            specification_path=Path(args.specification),
        )
        jobs = configured_campaign.create_validation_jobs(args.branch, actor=args.actor)
        _json({"jobs": jobs, "count": len(jobs)})
    elif args.command == "campaign-close":
        review = store.artifact_at(
            args.review_artifact_id, machine_id=machine_id_for_role(bundle, "mission_hub"),
        )
        learning = review["manifest"].get("architecture_knowledge")
        ledger = Path.cwd() / "docs" / "ninereeds_architecture_knowledge.md"
        if not isinstance(learning, dict) or not ledger.is_file():
            raise MissionHubError("campaign closure requires the canonical architecture-knowledge ledger and disposition")
        ledger_sha256 = hashlib.sha256(ledger.read_bytes()).hexdigest()
        if learning.get("ledger_sha256") != ledger_sha256:
            raise MissionHubError("campaign review architecture-knowledge hash does not match the canonical ledger")
        if learning.get("disposition") == "updated":
            ledger_text = ledger.read_text(encoding="utf-8")
            missing = [
                entry_id for entry_id in learning.get("entry_ids", [])
                if f"### {entry_id} " not in ledger_text
            ]
            if missing:
                raise MissionHubError("campaign review names architecture-knowledge entries absent from the ledger: " + ", ".join(missing))
        _json(store.close_campaign(
            args.campaign_id, review_artifact_id=args.review_artifact_id, actor=args.actor,
        ))
    elif args.command == "configured-gate-credit-reconcile":
        configured_gate_credit = ConfiguredGateCreditCampaign(
            store, bundle, repo_root=Path.cwd(),
            specification_path=Path(args.specification),
        )
        _json(configured_gate_credit.reconcile(
            actor=args.actor, authorize_branches=args.authorize_branch,
        ))
    elif args.command == "campaign35-commission-real-run":
        if store.pipeline_control()["applied_state"] != "paused":
            raise MissionHubError("Campaign 35 commissioning requires the safely paused pipeline")
        _json(ConfiguredCampaign35(store, bundle, Path.cwd()).commission(actor=args.actor))
    elif args.command == "campaign35-visual-recover":
        _json(ConfiguredCampaign35(store, bundle, Path.cwd()).recover_visual_batches(
            actor=args.actor,
            authorization_reference=args.authorization_reference,
            expected_exact_restarts=args.expected_exact_restarts,
            expected_seed_replacements=args.expected_seed_replacements,
            seed_offset=args.seed_offset,
        ))
    elif args.command == "campaign35-visual-resume-queue-expired":
        _json(ConfiguredCampaign35(store, bundle, Path.cwd()).resume_queue_expired_visual_frontiers(
            actor=args.actor, reason=args.reason, expected_count=args.expected_count,
        ))
    elif args.command == "deployment-register-current":
        active = store.active_config()
        role = bundle.deployment_roles[args.role_id]
        machine = bundle.machines[args.machine_id]
        if args.environment_json:
            environment = _input_object(args.environment_json)
        elif machine["transport"] == "local":
            environment = _environment(role)
        else:
            raise MissionHubError("remote deployment registration requires --environment-json from the target host")
        manifest = DeploymentBuilder(Path.cwd(), bundle).deployment_manifest(
            args.role_id,
            machine_id=args.machine_id,
            config_snapshot_id=active["id"],
            environment=environment,
            allow_dirty_candidate=not args.activate,
        )
        deployment_id = store.register_deployment(manifest, actor=args.actor, activate=args.activate)
        manifest["id"] = deployment_id
        archive = None
        if args.archive_output:
            archive = DeploymentBuilder(Path.cwd(), bundle).build_archive(manifest, args.archive_output)
        _json({"deployment_id": deployment_id, "active": args.activate, "manifest": manifest, "archive": archive})
    elif args.command == "deployment-reject":
        store.reject_deployment(args.deployment_id, reason=args.reason, actor=args.actor)
        _json({"deployment_id": args.deployment_id, "status": "rejected"})
    elif args.command == "evidence-capture":
        archive_root = Path(args.archive_root or bundle.base["hub"]["state_root"]) / "evidence"
        archive = EvidenceArchive(archive_root)
        selected = [source for source in bundle.evidence_sources.values() if source["machine_id"] == args.machine_id]
        if args.capture_id:
            wanted = set(args.capture_id)
            selected = [source for source in selected if source["id"] in wanted]
            missing = wanted - {source["id"] for source in selected}
            if missing:
                raise MissionHubError(f"unknown capture ids for machine: {', '.join(sorted(missing))}")
        captured = []
        for source in selected:
            manifest, records = archive.capture(source)
            evidence_id = None if args.no_import else store.preserve_evidence(manifest, records, actor=args.actor)
            captured.append({"source_id": source["id"], "snapshot_sha256": manifest["snapshot_sha256"], "files": len(manifest["files"]), "records": len(records), "evidence_id": evidence_id})
        _json({"archive_root": str(archive_root), "captured": captured})
    elif args.command == "evidence-import":
        archive = EvidenceArchive(args.archive_root)
        imported = []
        for digest in args.snapshot_sha256:
            manifest, records = archive.load_capture(digest)
            imported.append(store.preserve_evidence(manifest, records, actor=args.actor))
        _json({"evidence_ids": imported})
    elif args.command == "artifact-ingest":
        _json(MissionHubService(store, bundle).ingest_artifact(
            kind=args.kind,
            source_path=args.path,
            lifecycle=args.lifecycle,
            manifest=_input_object(args.manifest),
            actor=args.actor,
        ))
    elif args.command == "campaign-create":
        specification = _input_object(args.specification)
        store.create_campaign(
            campaign_id=specification["id"], name=specification["name"],
            objective=specification["objective"], metadata=specification["metadata"],
            state=specification.get("state", "draft"), actor=args.actor,
        )
        _json({"campaign": specification["id"], "created": True})
    elif args.command == "artifact-materialize":
        _json(MissionHubService(store, bundle).materialize_artifact(
            args.artifact_id, machine_id=args.machine_id, actor=args.actor,
        ))
    elif args.command == "artifact-retrieve":
        _json(MissionHubService(store, bundle).retrieve_artifact(
            args.artifact_id, machine_id=args.machine_id, actor=args.actor,
        ))
    elif args.command == "artifact-protect":
        _json(store.protect_artifact(
            args.artifact_id, protection_key=args.key, reason=args.reason,
            actor=args.actor, source="operator",
        ))
    elif args.command == "artifact-protection-release":
        _json(store.release_artifact_protection(args.protection_id, actor=args.actor))
    elif args.command == "path-protect":
        _json(store.protect_path(
            args.machine_id, args.path, protection_key=args.key, reason=args.reason,
            actor=args.actor, source="operator",
        ))
    elif args.command == "path-protection-release":
        _json(store.release_path_protection(args.protection_id, actor=args.actor))
    elif args.command == "retention-reconcile":
        _json(store.reconcile_retention_protections(bundle, actor=args.actor))
    elif args.command == "retention-preview":
        _json(RetentionManager(store, bundle).preview(machine_id=args.machine_id, actor=args.actor))
    elif args.command == "retention-apply":
        _json(RetentionManager(store, bundle).apply(
            machine_id=args.machine_id, plan_sha256=args.plan_sha256,
            acknowledgement=args.acknowledgement, actor=args.actor,
        ))
    elif args.command == "retention-auto-tick":
        _json(RetentionManager(store, bundle).automatic_tick(
            machine_id=args.machine_id, actor=args.actor,
        ))
    elif args.command == "campaign-storage-prepare":
        _json(RetentionManager(store, bundle).prepare_campaign(
            args.campaign_id, required_free_bytes=args.required_free_bytes,
            machine_id=args.machine_id, actor=args.actor,
        ))
    elif args.command == "campaign-storage-declare":
        _json(store.declare_campaign_storage(
            args.campaign_id, required_free_bytes=args.required_free_bytes,
            estimated_build_count=args.estimated_build_count, actor=args.actor,
        ))
    elif args.command == "training-order-certify":
        _json(MissionHubService(store, bundle).certify_training_order(
            job_type=args.type, input_payload=_input_object(args.input),
            campaign_id=args.campaign_id, actor=args.actor,
        ))
    elif args.command == "checkpoint-knowledge-seed":
        created = store.append_checkpoint_knowledge(
            checkpoint_artifact_id=args.checkpoint_artifact_id,
            parent_checkpoint_artifact_id=None,
            campaign_id=args.campaign_id,
            session_id=args.session_id,
            concepts=_input_string_array(args.concepts),
            evidence=_input_string_array(args.evidence),
            actor=args.actor,
        )
        _json({"checkpoint_artifact_id": args.checkpoint_artifact_id, "records_created": len(created)})
    elif args.command == "job-create":
        row = store.create_job(
            bundle,
            job_type=args.type,
            input_payload=_input_object(args.input),
            idempotency_key=args.idempotency_key,
            created_by=args.actor,
            campaign_id=args.campaign_id,
            requested_machine_id=args.machine_id,
        )
        _json(row)
    elif args.command == "job-approve":
        store.approve_job(args.job_id, actor=args.actor)
        _json({"approved": args.job_id})
    elif args.command == "job-cancel":
        store.cancel_job(args.job_id, reason=args.reason, actor=args.actor)
        _json({"cancelled": args.job_id})
    elif args.command == "leases-expire":
        _json({"expired": store.expire_leases(bundle, actor=args.actor)})
    elif args.command == "dispatch-once":
        deployment = store.active_deployment(args.machine_id)
        service = MissionHubService(store, bundle)
        envelope = service.lease_envelope(
            machine_id=args.machine_id,
            deployment_id=deployment["id"],
            actor=args.actor,
        )
        if envelope is None:
            _json({"dispatched": False, "reason": "no eligible queued job"})
        else:
            store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor=args.actor)
            status = service.execute_and_record(args.machine_id, envelope, actor=args.actor)
            _json({
                "dispatched": True, "job_id": envelope["job"]["id"],
                "run_id": envelope["run"]["id"], "status": status,
            })
    elif args.command == "schedule-tick":
        _json({"created": Scheduler(store, bundle).tick(actor=args.actor)})
    elif args.command == "serve":
        serve(store, bundle)
    elif args.command == "daemon":
        run_daemon(store, bundle)
    elif args.command == "readiness":
        _json(readiness_report(
            store, bundle,
            repo_root=Path(bundle.recovery["source_repository_root"]),
        ))
    elif args.command == "list":
        _json(store.list_rows(args.entity, limit=args.limit))
    else:
        raise AssertionError(args.command)
    return 0


def main() -> int:
    parser = build_parser()
    try:
        return run(parser.parse_args())
    except (MissionHubError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"mission-hub: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
