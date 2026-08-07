"""Durable, paced orchestration for one visual learning workflow."""

from __future__ import annotations

from typing import Any

from .config import ConfigBundle
from .errors import MissionHubError, NotFoundError
from .service import MissionHubService
from .store import MissionHubStore, strategic_available_at


TERMINAL_FAILURES = {"failed", "blocked", "cancelled"}


class VisualWorkflowCoordinator:
    """Create each visual stage from immutable predecessor artifacts.

    Creating the exact immutable workflow authorizes its bounded derived
    stages, just as it does for a Cortex workflow. Standalone jobs retain the
    catalog's approval policy. Every stage key is unique, making repeated
    daemon wakes and restarts idempotent.
    """

    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store = store
        self.bundle = bundle
        self.service = MissionHubService(store, bundle)

    def tick(self, *, actor: str) -> list[dict[str, str]]:
        changes: list[dict[str, str]] = []
        for workflow in self.store.active_visual_workflows():
            try:
                change = self._advance(workflow, actor=actor)
                if change:
                    changes.append({"workflow_id": workflow["id"], **change})
            except MissionHubError:
                # Transport/configuration unavailability is retryable at the
                # next daemon wake. Authoritative job failures are handled in
                # _advance and terminate the workflow with durable evidence.
                continue
            except (KeyError, TypeError, ValueError) as exc:
                self.store.finish_visual_workflow(
                    workflow["id"], "failed", actor=actor,
                    reason=f"deterministic coordinator error: {type(exc).__name__}: {exc}",
                )
                changes.append({"workflow_id": workflow["id"], "status": "failed", "stage": "coordinator"})
        return changes

    def _advance(self, workflow: dict[str, Any], *, actor: str) -> dict[str, str] | None:
        with self.store._connect() as db:
            campaign = db.execute(
                "SELECT state FROM campaigns WHERE id=?", (workflow["campaign_id"],),
            ).fetchone()
        if campaign is None:
            raise NotFoundError(workflow["campaign_id"])
        if campaign["state"] != "active":
            return None
        jobs = {item["stage_key"]: item for item in workflow["jobs"]}
        if "plan" not in jobs:
            return self._create(workflow, "plan", "visual.plan", [], workflow["specification"]["plan"], None, actor)

        for stage, job in jobs.items():
            if job["status"] in TERMINAL_FAILURES:
                self.store.finish_visual_workflow(workflow["id"], "failed", actor=actor, reason=f"{stage}:{job['status']}")
                return {"status": "failed", "stage": stage}

        plan = self._succeeded(jobs, "plan")
        if plan and "generate" not in jobs:
            return self._next(workflow, "generate", "visual.generate", self._ids(plan, "visual_plan"), plan, actor)
        generated = self._succeeded(jobs, "generate")
        if generated and "inspect" not in jobs:
            return self._next(workflow, "inspect", "visual.inspect", self._ids(generated, "visual_candidate", "visual_generation_report"), generated, actor)
        inspected = self._succeeded(jobs, "inspect")
        if generated and inspected and "caption" not in jobs:
            inputs = self._ids(generated, "visual_candidate") + self._ids(inspected, "visual_inspection_report")
            return self._next(
                workflow, "caption", "visual.caption", inputs, inspected, actor,
                specification={"workflow_id": workflow["id"], "commission": workflow["specification"]["plan"]},
            )
        captioned = self._succeeded(jobs, "caption")
        if inspected and captioned and "decide" not in jobs:
            inputs = self._ids(inspected, "visual_inspection_report") + self._ids(captioned, "visual_caption_report")
            return self._next(
                workflow, "decide", "visual.decide", inputs, captioned, actor,
                specification={"workflow_id": workflow["id"], "commission": workflow["specification"]["plan"]},
            )
        decided = self._succeeded(jobs, "decide")
        if generated and inspected and decided:
            candidates = self._artifacts(generated, "visual_candidate")
            for candidate in candidates:
                key = f"review:{candidate['id']}"
                if key not in jobs:
                    inputs = [candidate["id"], *self._ids(inspected, "visual_inspection_report"), *self._ids(decided, "visual_decision_report")]
                    return self._next(
                        workflow, key, "visual.review", inputs, decided, actor,
                        specification={"workflow_id": workflow["id"], "commission": workflow["specification"]["plan"]},
                    )
            review_keys = [f"review:{item['id']}" for item in candidates]
            reviews = [self._succeeded(jobs, key) for key in review_keys]
            if all(reviews):
                review_artifacts = [artifact for result in reviews for artifact in self._artifacts(result, "visual_review_report")]
                if any(item["manifest"].get("asset_status") != "usable" for item in review_artifacts):
                    self.store.finish_visual_workflow(workflow["id"], "failed", actor=actor, reason="independent review rejected one or more candidates")
                    return {"status": "failed", "stage": "review"}
                if self.bundle.visual["shadow_mode"]:
                    self.store.finish_visual_workflow(workflow["id"], "shadow_complete", actor=actor, reason="review evidence complete; admission remains locked")
                    return {"status": "shadow_complete", "stage": "review"}
                if "pack" not in jobs:
                    inputs = [item["id"] for item in candidates + review_artifacts]
                    latest = max((result for result in reviews if result), key=lambda result: result[2] or "")
                    return self._next(workflow, "pack", "visual.pack_finalize", inputs, latest, actor)
        packed = self._succeeded(jobs, "pack")
        if packed and generated and "encode" not in jobs:
            inputs = self._ids(packed, "visual_pack") + self._ids(generated, "visual_candidate")
            return self._next(workflow, "encode", "visual.encode", inputs, packed, actor)
        encoded = self._succeeded(jobs, "encode")
        if packed and encoded and "experience" not in jobs:
            return self._next(
                workflow, "experience", "visual.experience_compile", self._ids(packed, "visual_pack"), encoded, actor,
                specification={"events": workflow["specification"]["experience_events"]},
            )
        experienced = self._succeeded(jobs, "experience")
        if experienced:
            self.store.finish_visual_workflow(workflow["id"], "succeeded", actor=actor)
            return {"status": "succeeded", "stage": "experience"}
        return None

    def _succeeded(self, jobs: dict[str, dict[str, Any]], key: str) -> tuple[dict[str, Any], list[dict[str, Any]], str | None] | None:
        job = jobs.get(key)
        return self.store.workflow_job_artifacts(job["id"]) if job and job["status"] == "succeeded" else None

    @staticmethod
    def _artifacts(result: tuple[dict[str, Any], list[dict[str, Any]], str | None], kind: str) -> list[dict[str, Any]]:
        return [item for item in result[1] if item["kind"] == kind]

    def _ids(self, result: tuple[dict[str, Any], list[dict[str, Any]], str | None], *kinds: str) -> list[str]:
        selected = [item["id"] for item in result[1] if item["kind"] in kinds]
        if any(not any(item["kind"] == kind for item in result[1]) for kind in kinds):
            raise NotFoundError("visual predecessor omitted a required artifact")
        return selected

    def _next(
        self, workflow: dict[str, Any], key: str, job_type: str, artifact_ids: list[str],
        predecessor: tuple[dict[str, Any], list[dict[str, Any]], str | None], actor: str,
        *, specification: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        finished_at = predecessor[2]
        available_at = strategic_available_at(finished_at, self.bundle.visual["stage_cooldown_seconds"]) if finished_at else None
        return self._create(workflow, key, job_type, artifact_ids, specification or {"workflow_id": workflow["id"]}, available_at, actor)

    def _create(
        self, workflow: dict[str, Any], key: str, job_type: str, artifact_ids: list[str],
        specification: dict[str, Any], available_at: str | None, actor: str,
    ) -> dict[str, str]:
        definition = self.bundle.jobs[job_type]
        machine_id = "trainbox" if definition["executor_role"] == "trainbox" else "mission-hub"
        self._place(artifact_ids, machine_id, actor)
        job = self.store.create_job(
            self.bundle, job_type=job_type,
            input_payload={"input_artifact_ids": artifact_ids, "specification": specification, "limits": workflow["specification"]["limits"]},
            idempotency_key=f"visual-workflow:{workflow['id']}:{key}", created_by=actor,
            campaign_id=workflow["campaign_id"], requested_machine_id=machine_id,
            available_at=available_at, approved=True,
        )
        self.store.link_visual_workflow_job(workflow["id"], key, job["id"], actor=actor)
        return {"status": job["status"], "stage": key, "job_id": job["id"]}

    def _place(self, artifact_ids: list[str], machine_id: str, actor: str) -> None:
        for artifact_id in artifact_ids:
            try:
                self.store.artifact_at(artifact_id, machine_id=machine_id)
                continue
            except NotFoundError:
                pass
            if machine_id == "mission-hub":
                self.service.retrieve_artifact(artifact_id, machine_id="trainbox", actor=actor)
            else:
                self.service.materialize_artifact(artifact_id, machine_id="trainbox", actor=actor)
