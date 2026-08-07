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
        return {**self.store.retention_inventory(machine_id=machine_id), "derived": derived}

    def apply(
        self, *, machine_id: str, plan_sha256: str,
        acknowledgement: str, actor: str,
    ) -> dict[str, Any]:
        if acknowledgement != RETENTION_ACKNOWLEDGEMENT:
            raise SafetyError(
                f"retention cleanup requires acknowledgement {RETENTION_ACKNOWLEDGEMENT!r}"
            )
        control = self.store.pipeline_control()
        if control["effective_state"] != "paused" or control["live_runs"]:
            raise SafetyError("retention cleanup requires a fully paused pipeline with no live runs")
        plan = self.store.retention_inventory(machine_id=machine_id)
        if plan["plan_sha256"] != plan_sha256:
            raise ConflictError("retention plan is stale or does not match the supplied SHA-256")
        intents = {
            row["artifact_id"]: row
            for row in self.store.authorize_retention_plan(plan, actor=actor)
        }
        deployment = self.store.active_deployment(machine_id)
        deleted: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for item in plan["eligible"]:
            intent = intents[item["id"]]
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
