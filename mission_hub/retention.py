"""Protection-led, exact-plan checkpoint retention."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ConfigBundle
from .errors import ConflictError, SafetyError
from .jsonutil import canonical_json
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
        report_root = Path(self.bundle.machines["mission-hub"]["state_root"]) / "retention-reports"
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
