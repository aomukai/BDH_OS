"""Operator and restricted-agent CLI for the Ninereeds Mission Hub."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from .agent import TrainboxAgent
from .config import ConfigBundle, load_config_bundle
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


def _json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _bundle(args: argparse.Namespace) -> ConfigBundle:
    return load_config_bundle(args.config)


def _store(args: argparse.Namespace, bundle: ConfigBundle) -> MissionHubStore:
    path = Path(args.database) if args.database else Path(bundle.base["hub"]["state_root"]) / bundle.base["hub"]["database_name"]
    return MissionHubStore(path, busy_timeout_ms=bundle.base["hub"]["busy_timeout_ms"])


def _environment(role: dict[str, Any]) -> dict[str, Any]:
    result = environment_attestation(role["python_site_paths"])
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
    commands.add_parser("status")
    migrate = commands.add_parser("legacy-migrate-current-campaign")
    migrate.add_argument("--archive-root")

    deployment = commands.add_parser("deployment-register-current")
    deployment.add_argument("--role-id", required=True)
    deployment.add_argument("--machine-id", required=True)
    deployment.add_argument("--activate", action="store_true")
    deployment.add_argument("--allow-dirty-active", action="store_true")
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
    commands.add_parser("serve")
    commands.add_parser("daemon")
    commands.add_parser("readiness")

    listing = commands.add_parser("list")
    listing.add_argument("entity", choices=["config_snapshots", "machines", "deployments", "campaigns", "decisions", "jobs", "runs", "artifacts", "evidence_sources", "events"])
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
    elif args.command == "status":
        _json({"database": str(store.path), "config": store.active_config(), "integrity": store.integrity_report()})
    elif args.command == "legacy-migrate-current-campaign":
        archive_root = Path(args.archive_root or bundle.base["hub"]["state_root"]) / "evidence"
        _json(LegacyMigrator(store, bundle, EvidenceArchive(archive_root)).migrate_current_campaign(actor=args.actor))
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
            allow_dirty_candidate=not args.activate or args.allow_dirty_active,
        )
        if args.activate and not manifest["source"]["git_clean"] and not args.allow_dirty_active:
            raise MissionHubError("dirty source cannot be activated")
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
        _json({"expired": store.expire_leases(actor=args.actor)})
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
            result = SSHDispatcher(bundle).execute(args.machine_id, envelope)
            service.accept_result(envelope, result, actor=args.actor)
            _json({"dispatched": True, "job_id": envelope["job"]["id"], "run_id": envelope["run"]["id"]})
    elif args.command == "schedule-tick":
        _json({"created": Scheduler(store, bundle).tick(actor=args.actor)})
    elif args.command == "serve":
        serve(store, bundle)
    elif args.command == "daemon":
        run_daemon(store, bundle)
    elif args.command == "readiness":
        _json(readiness_report(store, bundle, repo_root=Path.cwd()))
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
