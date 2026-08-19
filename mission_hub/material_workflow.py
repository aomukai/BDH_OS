"""Restartable one-model-call-per-unit material production."""

from __future__ import annotations

from typing import Any

from .config import ConfigBundle, machine_id_for_role
from .errors import MissionHubError, NotFoundError, SafetyError
from .service import MissionHubService
from .store import MissionHubStore


TERMINAL_FAILURES = {"failed", "blocked", "cancelled"}


class MaterialWorkflowCoordinator:
    """Advance one persisted writing unit at a time, then assemble deterministically."""

    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store, self.bundle = store, bundle
        self.service = MissionHubService(store, bundle)

    def tick(self, *, actor: str) -> list[dict[str, str]]:
        changes: list[dict[str, str]] = []
        for workflow in self.store.active_material_workflows():
            try:
                change = self._advance(workflow, actor=actor)
                if change:
                    changes.append({"workflow_id": workflow["id"], **change})
            except (SafetyError, NotFoundError) as exc:
                self.store.finish_material_workflow(
                    workflow["id"], "blocked", actor=actor,
                    reason=f"{type(exc).__name__}: {exc}",
                )
                changes.append({"workflow_id": workflow["id"], "status": "blocked", "stage": "coordinator"})
            except MissionHubError:
                # Deployment/transport availability may recover on the next
                # wake without changing the immutable unit.
                continue
            except (KeyError, TypeError, ValueError) as exc:
                self.store.finish_material_workflow(
                    workflow["id"], "failed", actor=actor,
                    reason=f"deterministic coordinator error: {type(exc).__name__}: {exc}",
                )
                changes.append({"workflow_id": workflow["id"], "status": "failed", "stage": "coordinator"})
        return changes

    def _advance(self, workflow: dict[str, Any], *, actor: str) -> dict[str, str] | None:
        jobs = {item["stage_key"]: item for item in workflow["jobs"]}
        produced: list[dict[str, Any]] = []
        for ordinal, unit in enumerate(workflow["specification"]["units"]):
            key = f"unit/{ordinal:06d}"
            job = jobs.get(key)
            if job is None:
                if self.store.campaign_blocks(workflow["campaign_id"], active_only=True):
                    return None
                specification = dict(unit["specification"])
                specification["work_unit_id"] = unit["unit_id"]
                created = self.store.create_job(
                    self.bundle, job_type="executor.generate",
                    input_payload={
                        "specification": specification,
                        "input_artifact_ids": unit["input_artifact_ids"],
                        "output_contract": unit["output_contract"],
                        "limits": unit["limits"],
                    },
                    idempotency_key=f"material-workflow:{workflow['id']}:{key}",
                    created_by=workflow["created_by"], campaign_id=workflow["campaign_id"],
                    requested_machine_id=machine_id_for_role(self.bundle, "trainbox"), approved=True,
                )
                self.store.link_material_workflow_job(workflow["id"], key, created["id"], actor=actor)
                return {"status": created["status"], "stage": key, "job_id": created["id"]}
            if job["status"] in TERMINAL_FAILURES:
                return self._finish_failed(workflow, job, key, actor=actor)
            if job["status"] != "succeeded":
                return None
            result = self.store.workflow_job_artifacts(job["id"])
            produced.append(self._one(result[1], "generated_material"))

        assemble = jobs.get("assemble")
        if assemble is None:
            for artifact in produced:
                self._ensure_local(artifact["id"], actor)
            created = self.store.create_job(
                self.bundle, job_type="corpus.assemble_generated",
                input_payload={
                    "input_artifact_ids": [item["id"] for item in produced],
                    "unit_ids": [item["unit_id"] for item in workflow["specification"]["units"]],
                    "corpus_name": workflow["specification"]["corpus"]["corpus_name"],
                },
                idempotency_key=f"material-workflow:{workflow['id']}:assemble",
                created_by=workflow["created_by"], campaign_id=workflow["campaign_id"],
                requested_machine_id=machine_id_for_role(self.bundle, "mission_hub"), approved=True,
            )
            self.store.link_material_workflow_job(workflow["id"], "assemble", created["id"], actor=actor)
            return {"status": created["status"], "stage": "assemble", "job_id": created["id"]}
        if assemble["status"] in TERMINAL_FAILURES:
            return self._finish_failed(workflow, assemble, "assemble", actor=actor)
        if assemble["status"] == "succeeded":
            artifacts = self.store.workflow_job_artifacts(assemble["id"])[1]
            self._one(artifacts, "corpus")
            self._one(artifacts, "corpus_manifest")
            self.store.finish_material_workflow(workflow["id"], "succeeded", actor=actor)
            return {"status": "succeeded", "stage": "complete"}
        return None

    def _finish_failed(
        self, workflow: dict[str, Any], job: dict[str, Any], stage: str, *, actor: str,
    ) -> dict[str, str] | None:
        with self.store._connect() as db:
            incident = db.execute(
                "SELECT state,blocker_code FROM recovery_incidents WHERE job_id=? ORDER BY created_at DESC LIMIT 1",
                (job["id"],),
            ).fetchone()
        if incident is not None and incident["state"] not in {"recovered", "blocked", "escalated"}:
            return None
        status = "blocked" if job["status"] == "blocked" or (incident and incident["state"] in {"blocked", "escalated"}) else "failed"
        reason = f"{stage}:{job['status']}"
        if incident is not None and incident["blocker_code"]:
            reason += f":{incident['blocker_code']}"
        self.store.finish_material_workflow(workflow["id"], status, actor=actor, reason=reason)
        return {"status": status, "stage": stage}

    @staticmethod
    def _one(artifacts: list[dict[str, Any]], kind: str) -> dict[str, Any]:
        matches = [item for item in artifacts if item["kind"] == kind]
        if len(matches) != 1:
            raise SafetyError(f"material workflow stage requires exactly one {kind} artifact")
        return matches[0]

    def _ensure_local(self, artifact_id: str, actor: str) -> None:
        local = machine_id_for_role(self.bundle, "mission_hub")
        remote = machine_id_for_role(self.bundle, "trainbox")
        try:
            self.store.artifact_at(artifact_id, machine_id=local)
        except NotFoundError:
            self.service.retrieve_artifact(artifact_id, machine_id=remote, actor=actor)
