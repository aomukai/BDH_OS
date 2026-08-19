"""Protection-led, exact-plan checkpoint retention."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ConfigBundle, machine_id_for_role
from .errors import ConflictError, SafetyError
from .jsonutil import canonical_json
from .recovery import RecoveryManager
from .service import MissionHubService
from .store import MissionHubStore, utc_now
from .transport import SSHDispatcher


RETENTION_ACKNOWLEDGEMENT = "delete-unprotected-exact-plan"


class RetentionManager:
    """Preview and execute cleanup without making artifact history disappear."""

    def __init__(
        self, store: MissionHubStore, bundle: ConfigBundle,
        *, dispatcher: SSHDispatcher | None = None,
    ):
        self.store = store
        self.bundle = bundle
        self.dispatcher = dispatcher or SSHDispatcher(bundle)

    def preview(self, *, machine_id: str, actor: str) -> dict[str, Any]:
        derived = self.store.reconcile_retention_protections(self.bundle, actor=actor)
        return {
            **self.store.retention_inventory(
                machine_id=machine_id, roots=self.bundle.retention["build_roots"],
            ),
            "derived": derived,
        }

    def apply(
        self, *, machine_id: str, plan_sha256: str,
        acknowledgement: str, actor: str, automatic: bool = False,
    ) -> dict[str, Any]:
        if not automatic and acknowledgement != RETENTION_ACKNOWLEDGEMENT:
            raise SafetyError(
                f"retention cleanup requires acknowledgement {RETENTION_ACKNOWLEDGEMENT!r}"
            )
        control = self.store.pipeline_control()
        if control["live_runs"]:
            raise SafetyError("retention cleanup requires a globally quiet run boundary")
        if not automatic and control["effective_state"] != "paused":
            raise SafetyError("operator retention cleanup requires a fully paused pipeline")
        plan = self.store.retention_inventory(
            machine_id=machine_id, roots=self.bundle.retention["build_roots"],
        )
        if plan["plan_sha256"] != plan_sha256:
            raise ConflictError("retention plan is stale or does not match the supplied SHA-256")
        intents = {
            (row["artifact_id"], row["uri"]): row
            for row in self.store.authorize_retention_plan(plan, actor=actor)
        }
        deployment = self.store.active_deployment(machine_id)
        deleted: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for item in plan["eligible"]:
            intent = intents[(item["id"], item["uri"])]
            try:
                receipt = self.dispatcher.delete_artifact(
                    machine_id, deployment, item, plan_sha256=plan_sha256,
                )
                self.store.record_retention_deletion(
                    artifact_id=item["id"], machine_id=machine_id, uri=item["uri"],
                    expected_sha256=item["sha256"], plan_sha256=plan_sha256, actor=actor,
                )
                deleted.append({**item, "receipt": receipt})
            except Exception as exc:
                self.store.fail_retention_deletion(
                    intent["id"], failure=f"{type(exc).__name__}: {exc}", actor=actor,
                )
                failed.append({**item, "failure": f"{type(exc).__name__}: {exc}"})
                break
        report = {
            "schema_version": "ninereeds_retention_report_v1",
            "plan_sha256": plan_sha256,
            "machine_id": machine_id,
            "finished_at": utc_now(),
            "deleted": deleted,
            "failed": failed,
            "deleted_bytes": sum(item["byte_size"] for item in deleted),
            "metadata_preserved": True,
            "unattempted": len(plan["eligible"]) - len(deleted) - len(failed),
        }
        report_root = Path(
            self.bundle.machines[machine_id_for_role(self.bundle, "mission_hub")]["state_root"]
        ) / "retention-reports"
        report_root.mkdir(parents=True, exist_ok=True)
        report_path = report_root / f"{plan_sha256}.json"
        report_path.write_text(canonical_json(report) + "\n", encoding="utf-8")
        artifact = MissionHubService(self.store, self.bundle).ingest_artifact(
            kind="retention_report", source_path=str(report_path), lifecycle="observed",
            manifest={
                "plan_sha256": plan_sha256, "machine_id": machine_id,
                "deleted_count": len(deleted), "failed_count": len(failed),
                "deleted_bytes": report["deleted_bytes"],
            },
            actor=actor,
        )
        report["report_artifact_id"] = artifact["id"]
        if failed:
            raise SafetyError(
                f"retention cleanup stopped after {len(deleted)} deletions; report {artifact['id']} records the failure"
            )
        return report

    def automatic_tick(self, *, machine_id: str = "trainbox", actor: str) -> dict[str, Any]:
        """Run one configured, no-live-work storage check and cleanup if needed."""
        policy = self.bundle.retention
        if (
            not self.bundle.base["safety"]["automatic_pruning"]
            or policy["mode"] != "protected_registry_automatic"
        ):
            return {"checked": False, "reason": "automatic retention is disabled"}
        if not self.store.retention_auto_due(policy["scan_interval_seconds"]):
            return {"checked": False, "reason": "retention interval has not elapsed"}
        if self.store.pipeline_control()["live_runs"]:
            return {"checked": False, "reason": "live work owns the storage boundary"}
        deployment = self.store.active_deployment(machine_id)
        inventory = self.dispatcher.build_inventory(machine_id, deployment)
        discovered = self._reconcile_inventory(machine_id, inventory, actor=actor)
        self.store.reconcile_retention_protections(self.bundle, actor=actor)
        plan = self.store.retention_inventory(
            machine_id=machine_id, roots=policy["build_roots"],
        )
        result = None
        if inventory["triggered"] and plan["eligible"]:
            result = self.apply(
                machine_id=machine_id, plan_sha256=plan["plan_sha256"],
                acknowledgement="automatic-policy", actor=actor, automatic=True,
            )
        summary = {
            "checked": True, "triggered": inventory["triggered"],
            "used_fraction": inventory["used_fraction"], "free_bytes": inventory["free_bytes"],
            "files_seen": len(inventory["files"]), "artifacts_reconciled": len(set(discovered)),
            "eligible_count": len(plan["eligible"]),
            "deleted_count": 0 if result is None else len(result["deleted"]),
            "report_artifact_id": None if result is None else result["report_artifact_id"],
        }
        self.store.record_retention_auto_check(summary, actor=actor)
        return summary

    def prune_checkpoint_frontier(
        self, *, machine_id: str = "trainbox", actor: str,
    ) -> dict[str, Any]:
        """Delete superseded checkpoint bytes immediately after a successful stage.

        Unlike periodic inventory this uses already verified artifact locations,
        so the normal training cadence pays no full-filesystem hashing cost.
        The caller owns a globally quiet, dispatch-blocking maintenance boundary.
        """
        request = self.store.checkpoint_frontier_prune_request()
        if request is None:
            return {"requested": False, "deleted_count": 0, "deleted_bytes": 0}
        if self.store.pipeline_control()["live_runs"]:
            raise SafetyError("checkpoint frontier pruning requires a globally quiet run boundary")
        if not self.store.checkpoint_frontier_prune_ready(request):
            return {
                "requested": True, "deferred": True, "request": request,
                "reason": "waiting for the comparison evaluation to own the new checkpoint and its parent",
                "deleted_count": 0, "deleted_bytes": 0,
            }
        self.store.reconcile_retention_protections(self.bundle, actor=actor)
        plan = self.store.retention_inventory(
            machine_id=machine_id, roots=self.bundle.retention["build_roots"],
        )
        cleanup = None
        if plan["eligible"]:
            cleanup = self.apply(
                machine_id=machine_id, plan_sha256=plan["plan_sha256"],
                acknowledgement="checkpoint-frontier-prune", actor=actor, automatic=True,
            )
        if not self.store.clear_checkpoint_frontier_prune_request(request["token"], actor=actor):
            raise ConflictError("checkpoint frontier prune request changed during maintenance")
        return {
            "requested": True, "request": request,
            "eligible_count": len(plan["eligible"]),
            "deleted_count": 0 if cleanup is None else len(cleanup["deleted"]),
            "deleted_bytes": 0 if cleanup is None else cleanup["deleted_bytes"],
            "report_artifact_id": None if cleanup is None else cleanup["report_artifact_id"],
        }

    def automatic_scan_due(self) -> bool:
        """Return whether this tick will start the potentially long remote inventory."""
        policy = self.bundle.retention
        return bool(
            self.bundle.base["safety"]["automatic_pruning"]
            and policy["mode"] == "protected_registry_automatic"
            and self.store.retention_auto_due(policy["scan_interval_seconds"])
            and not self.store.pipeline_control()["live_runs"]
        )

    def restore_capacity(
        self, *, machine_id: str, required_free_bytes: int, actor: str,
    ) -> dict[str, Any]:
        """Force registry cleanup at a quiet boundary and report proven capacity."""
        if required_free_bytes < 1:
            raise ValueError("required free bytes must be positive")
        if self.store.pipeline_control()["live_runs"]:
            raise SafetyError("disk recovery cleanup requires a globally quiet run boundary")
        deployment = self.store.active_deployment(machine_id)
        inventory = self.dispatcher.build_inventory(machine_id, deployment, force=True)
        discovered = self._reconcile_inventory(machine_id, inventory, actor=actor)
        self.store.reconcile_retention_protections(self.bundle, actor=actor)
        plan = self.store.retention_inventory(
            machine_id=machine_id, roots=self.bundle.retention["build_roots"],
        )
        cleanup = None
        if plan["eligible"]:
            cleanup = self.apply(
                machine_id=machine_id, plan_sha256=plan["plan_sha256"],
                acknowledgement="disk-capacity-recovery", actor=actor, automatic=True,
            )
        status = self.dispatcher.build_inventory(machine_id, deployment)
        summary = {
            "machine_id": machine_id,
            "required_free_bytes": required_free_bytes,
            "free_bytes": status["free_bytes"],
            "files_seen": len(inventory["files"]),
            "artifacts_reconciled": len(set(discovered)),
            "eligible_count": len(plan["eligible"]),
            "deleted_count": 0 if cleanup is None else len(cleanup["deleted"]),
            "deleted_bytes": 0 if cleanup is None else cleanup["deleted_bytes"],
            "report_artifact_id": None if cleanup is None else cleanup["report_artifact_id"],
            "restored": status["free_bytes"] >= required_free_bytes,
        }
        self.store.record_retention_auto_check({**summary, "trigger": "disk_failure"}, actor=actor)
        return summary

    def prepare_campaign(
        self, campaign_id: str, *, required_free_bytes: int,
        machine_id: str = "trainbox", actor: str,
    ) -> dict[str, Any]:
        """Perform rolling cleanup, then prove the next campaign fits before it starts."""
        if required_free_bytes < 1:
            raise ValueError("campaign storage requirement must be positive")
        if self.store.pipeline_control()["live_runs"]:
            raise SafetyError("campaign storage preparation requires a globally quiet run boundary")
        deployment = self.store.active_deployment(machine_id)
        inventory = self.dispatcher.build_inventory(machine_id, deployment, force=True)
        discovered = self._reconcile_inventory(machine_id, inventory, actor=actor)
        self.store.reconcile_retention_protections(self.bundle, actor=actor)
        plan = self.store.retention_inventory(
            machine_id=machine_id, roots=self.bundle.retention["build_roots"],
        )
        cleanup = None
        if plan["eligible"]:
            cleanup = self.apply(
                machine_id=machine_id, plan_sha256=plan["plan_sha256"],
                acknowledgement="campaign-rollover-policy", actor=actor, automatic=True,
            )
        status = self.dispatcher.build_inventory(machine_id, deployment)
        if status["free_bytes"] < required_free_bytes:
            raise SafetyError(
                f"campaign {campaign_id} requires {required_free_bytes} free bytes but only {status['free_bytes']} are available"
            )
        self.store.record_campaign_storage_preflight(
            campaign_id, required_free_bytes=required_free_bytes,
            free_bytes=status["free_bytes"], machine_id=machine_id,
            config_sha256=self.bundle.sha256, actor=actor,
        )
        summary = {
            "campaign_id": campaign_id, "prepared": True,
            "required_free_bytes": required_free_bytes, "free_bytes": status["free_bytes"],
            "files_seen": len(inventory["files"]), "artifacts_reconciled": len(set(discovered)),
            "deleted_count": 0 if cleanup is None else len(cleanup["deleted"]),
            "deleted_bytes": 0 if cleanup is None else cleanup["deleted_bytes"],
            "report_artifact_id": None if cleanup is None else cleanup["report_artifact_id"],
        }
        self.store.record_retention_auto_check({**summary, "trigger": "campaign_start"}, actor=actor)
        return summary

    def _reconcile_inventory(
        self, machine_id: str, inventory: dict[str, Any], *, actor: str,
    ) -> list[str]:
        discovered: list[str] = []
        for item in inventory.get("files", []):
            run_id = next((part for part in Path(item["uri"]).parts if part.startswith("run-")), None)
            artifact_id = self.store.register_artifact(
                self.bundle, kind="checkpoint", sha256=item["sha256"],
                byte_size=item["byte_size"], lifecycle="rejected",
                manifest={
                    "status": "storage_inventory_discovery",
                    "reason": "Build bytes were present in a declared root and reconciled by retention.",
                    "run_id": run_id, "discovered_uri": item["uri"],
                },
                producing_run_id=None, machine_id=machine_id, uri=item["uri"], actor=actor,
            )
            discovered.append(artifact_id)
        return discovered


class DiskCapacityRecoveryCoordinator:
    """Clean protected-registry storage before escalating disk failures."""

    def __init__(
        self, store: MissionHubStore, bundle: ConfigBundle,
        *, retention: RetentionManager | None = None,
    ):
        self.store = store
        self.bundle = bundle
        self.retention = retention or RetentionManager(store, bundle)

    def has_pending(self) -> bool:
        machine_id = machine_id_for_role(self.bundle, "trainbox")
        with self.store._connect() as db:
            return db.execute(
                """SELECT 1 FROM recovery_incidents i JOIN jobs j ON j.id=i.job_id
                   WHERE i.state IN ('classified','escalated') AND i.failure_code='disk_write_failed'
                     AND i.operational_thread_id IS NULL AND j.status='failed'
                     AND j.requested_machine_id=? LIMIT 1""",
                (machine_id,),
            ).fetchone() is not None

    def tick(self, *, actor: str) -> int:
        machine_id = machine_id_for_role(self.bundle, "trainbox")
        with self.store._connect() as db:
            incidents = db.execute(
                """SELECT i.id,EXISTS(
                         SELECT 1 FROM recovery_attempts a
                         WHERE a.incident_id=i.id AND a.strategy='local_resource_restored_retry'
                       ) AS cleanup_retry_attempted
                   FROM recovery_incidents i JOIN jobs j ON j.id=i.job_id
                   WHERE i.state IN ('classified','escalated') AND i.failure_code='disk_write_failed'
                     AND i.operational_thread_id IS NULL AND j.status='failed'
                     AND j.requested_machine_id=? ORDER BY i.created_at,i.id""",
                (machine_id,),
            ).fetchall()
        if not incidents:
            return 0
        control = self.store.pipeline_control()
        if control["effective_state"] != "paused" or control["live_runs"]:
            self.store.request_pipeline_state("paused", actor=actor)
            return 1
        attempted = [row["id"] for row in incidents if row["cleanup_retry_attempted"]]
        pending = [row["id"] for row in incidents if not row["cleanup_retry_attempted"]]
        if attempted:
            self._notify_on_call(
                attempted,
                SafetyError("the exact job still reported disk exhaustion after cleanup and retry"),
                actor=actor,
            )
        if not pending:
            return 1
        # The visual runtime may refuse a small image at its lower admission
        # floor, but cleanup should restore the broader retention reserve so a
        # subsequent checkpoint (the largest normal artifact) also fits.
        required = int(self.bundle.retention["minimum_free_bytes"])
        try:
            result = self.retention.restore_capacity(
                machine_id=machine_id, required_free_bytes=required, actor=actor,
            )
            if not result["restored"]:
                raise SafetyError(
                    f"registry cleanup left {result['free_bytes']} free bytes; {required} are required"
                )
            RecoveryManager(self.store, self.bundle).retry_after_local_resource_restoration(
                pending, machine_id=machine_id,
                observed_free_bytes=result["free_bytes"], required_free_bytes=required,
                observed_at=utc_now(), observation=canonical_json(result),
                expected_incident_count=len(pending), actor=actor,
            )
            self.store.request_pipeline_state("running", actor=actor)
        except Exception as exc:
            self._notify_on_call(pending, exc, actor=actor)
        return 1

    def _notify_on_call(self, incident_ids: list[str], failure: Exception, *, actor: str) -> None:
        from .lab import LabStore
        detail = f"{type(failure).__name__}: {failure}"
        for incident_id in incident_ids:
            incident = RecoveryManager(self.store, self.bundle).get(incident_id)
            body = "\n".join([
                "Disk-capacity cleanup did not restore the required safety margin.",
                f"Job: {incident['job_id']}",
                f"Recovery incident: {incident_id}",
                f"Recovery state: {incident['state']} (infrastructure)",
                "Deterministic protected-registry cleanup: failed",
                f"Detail: {detail}",
                "Sol: assess the preserved cleanup evidence and choose the next bounded recovery action.",
            ])
            thread_id = LabStore(self.store).system_notice(
                "Disk cleanup needs on-call", body, sender="mission_hub", actor=actor,
            )
            with self.store.transaction() as db:
                db.execute(
                    "UPDATE recovery_incidents SET operational_thread_id=?,updated_at=? WHERE id=? AND operational_thread_id IS NULL",
                    (thread_id, utc_now(), incident_id),
                )
