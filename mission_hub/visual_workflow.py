"""Durable, paced orchestration for one visual learning workflow."""

from __future__ import annotations

from typing import Any

from .config import ConfigBundle, machine_id_for_role
from .errors import MissionHubError, NotFoundError, SafetyError
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
                self._fail_without_job(
                    workflow, actor=actor,
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
        if self.store.campaign_blocks(workflow["campaign_id"], active_only=True):
            return None
        jobs = {item["stage_key"]: item for item in workflow["jobs"]}
        preserved_generation_fanout = getattr(
            self.store, "visual_workflow_uses_preserved_generation_fanout", lambda _workflow_id: False,
        )(workflow["id"])
        if "plan" not in jobs:
            job_type = (
                "visual.plan_exact"
                if workflow["specification"]["plan"].get("authority", {}).get("exact_material") is True
                else "visual.plan"
            )
            return self._create(workflow, "plan", job_type, [], workflow["specification"]["plan"], None, actor)

        for stage, job in jobs.items():
            superseded_legacy = (
                preserved_generation_fanout
                and stage in {"generate", "inspect", "caption", "decide", "review", "pack", "encode", "experience"}
                and (
                    (stage == "generate" and job["status"] in {"failed", "blocked"})
                    or (
                        job["status"] == "cancelled"
                        and job.get("cancel_reason") == "superseded by verified per-candidate workflow migration"
                    )
                )
            )
            if job["status"] in TERMINAL_FAILURES and not superseded_legacy:
                self.store.finish_visual_workflow(workflow["id"], "failed", actor=actor, reason=f"{stage}:{job['status']}")
                return {"status": "failed", "stage": stage}

        plan = self._succeeded(jobs, "plan")
        if plan and "generate" not in jobs:
            return self._advance_incremental(workflow, jobs, plan, actor=actor)
        generated = self._succeeded(jobs, "generate")
        if plan and preserved_generation_fanout:
            return self._advance_incremental(
                workflow, jobs, plan, actor=actor, preserved_generation=generated,
            )
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
        if generated and inspected and captioned and "decide" not in jobs:
            # The policy decider does not receive candidate pixels, but it
            # must receive the generation receipt. Otherwise it is asked to
            # enforce revision, seed, dimension, step, and hash provenance
            # without being given that evidence.
            inputs = (
                self._ids(generated, "visual_generation_report")
                + self._ids(inspected, "visual_inspection_report")
                + self._ids(captioned, "visual_caption_report")
            )
            return self._next(
                workflow, "decide", "visual.decide", inputs, captioned, actor,
                specification={"workflow_id": workflow["id"], "commission": workflow["specification"]["plan"]},
            )
        decided = self._succeeded(jobs, "decide")
        if generated and inspected and decided:
            candidates = self._artifacts(generated, "visual_candidate")
            if "review" not in jobs:
                inputs = [item["id"] for item in candidates] + self._ids(inspected, "visual_inspection_report") + self._ids(decided, "visual_decision_report")
                return self._next(
                    workflow, "review", "visual.review", inputs, decided, actor,
                    specification={"workflow_id": workflow["id"], "commission": workflow["specification"]["plan"]},
                )
            review = self._succeeded(jobs, "review")
            if review:
                review_artifacts = self._artifacts(review, "visual_review_report")
                selected_candidates, selected_reviews = self._selected_usable_candidates(
                    workflow, candidates, review_artifacts,
                )
                if not selected_candidates:
                    review_detail = self._review_outcome_detail(candidates, review_artifacts)
                    return self._handle_review_exhaustion(
                        workflow, actor=actor, detail=review_detail,
                    )
                if self.bundle.visual["shadow_mode"]:
                    self.store.finish_visual_workflow(
                        workflow["id"], "shadow_complete", actor=actor,
                        reason=(
                            f"review evidence selected {len(selected_candidates)} usable candidate(s) "
                            f"from {len(candidates)}; admission remains locked"
                        ),
                    )
                    return {"status": "shadow_complete", "stage": "review"}
                if "pack" not in jobs:
                    # Generated images are alternatives. Only independently
                    # usable candidates, capped by the declared pack limit in
                    # plan/seed order, enter the immutable pack. Rejected and
                    # unselected alternatives remain preserved as evidence.
                    inputs = [item["id"] for item in selected_candidates + selected_reviews]
                    return self._next(workflow, "pack", "visual.pack_finalize", inputs, review, actor)
        packed = self._succeeded(jobs, "pack")
        if packed and generated and "encode" not in jobs:
            pack_artifacts = self._artifacts(packed, "visual_pack")
            if len(pack_artifacts) != 1:
                raise ValueError("visual pack stage did not produce exactly one pack")
            selected_ids = [item.get("asset_artifact_id") for item in pack_artifacts[0]["manifest"].get("items", [])]
            generated_by_id = {item["id"]: item for item in self._artifacts(generated, "visual_candidate")}
            if not selected_ids or any(item_id not in generated_by_id for item_id in selected_ids):
                raise ValueError("visual pack names a candidate outside the generation result")
            inputs = self._ids(packed, "visual_pack") + selected_ids
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

    def _advance_incremental(
        self, workflow: dict[str, Any], jobs: dict[str, dict[str, Any]],
        plan: tuple[dict[str, Any], list[dict[str, Any]], str | None], *, actor: str,
        preserved_generation: tuple[dict[str, Any], list[dict[str, Any]], str | None] | None = None,
    ) -> dict[str, str] | None:
        """Persist each independent candidate as its own bounded job chain.

        The workflow row and stage links are the aggregation cursor. Repeated
        wakes recreate no completed work, and a crash loses at most the one
        candidate job that held a lease.
        """
        units = self._candidate_units(workflow)
        results: dict[str, dict[int, tuple[dict[str, Any], list[dict[str, Any]], str | None]]] = {
            stage: {} for stage in ("generate", "inspect", "caption", "decide", "review")
        }
        plan_id = self._one_id(plan, "visual_plan")

        if preserved_generation is not None:
            report = self._one_artifact(preserved_generation, "visual_generation_report")
            candidates = self._artifacts(preserved_generation, "visual_candidate")
            by_identity: dict[tuple[str, int], dict[str, Any]] = {}
            for candidate in candidates:
                identity = (candidate["manifest"].get("item_id"), candidate["manifest"].get("seed"))
                if identity in by_identity:
                    raise ValueError("preserved generation repeats an item/seed identity")
                by_identity[identity] = candidate
            expected = {(unit["item_id"], unit["seed"]) for unit in units}
            if set(by_identity) != expected:
                raise ValueError("preserved generation does not exactly cover the immutable candidate units")
            results["generate"] = {
                unit["ordinal"]: (
                    preserved_generation[0],
                    [by_identity[(unit["item_id"], unit["seed"])], report],
                    preserved_generation[2],
                )
                for unit in units
            }

        # Traverse candidate-first, not stage-first.  A candidate must reach an
        # authoritative review before the next candidate is generated.  This
        # keeps provider failures and content rejections local instead of
        # accumulating a whole generation/inspection wave first.
        selected_candidates: list[dict[str, Any]] = []
        selected_reviews: list[dict[str, Any]] = []
        completed_candidates: list[dict[str, Any]] = []
        completed_reviews: list[dict[str, Any]] = []
        cursor = plan
        exact_material = workflow["specification"]["plan"].get("authority", {}).get("exact_material") is True
        pack_limit = workflow["specification"]["limits"]["max_pack_items"]
        units_by_item: dict[str, list[dict[str, Any]]] = {}
        for unit in units:
            units_by_item.setdefault(unit["item_id"], []).append(unit)

        for item in workflow["specification"]["plan"]["items"]:
            item_id = item["item_id"]
            accepted = False
            for unit in units_by_item[item_id]:
                ordinal = unit["ordinal"]
                for stage in ("generate", "inspect", "caption", "decide", "review"):
                    if stage == "generate" and ordinal in results["generate"]:
                        continue
                    key = f"{stage}/{ordinal:04d}"
                    job = jobs.get(key)
                    if job is None:
                        if stage == "generate":
                            return self._next(
                                workflow, key, "visual.generate", [plan_id], cursor, actor,
                                specification={"workflow_id": workflow["id"], "selection": unit},
                            )
                        predecessor = results[self._previous_stage(stage)][ordinal]
                        if stage == "inspect":
                            inputs = [
                                self._one_id(results["generate"][ordinal], "visual_candidate"),
                                self._one_id(results["generate"][ordinal], "visual_generation_report"),
                            ]
                            specification = {"workflow_id": workflow["id"]}
                        elif stage == "caption":
                            inputs = [
                                self._one_id(results["generate"][ordinal], "visual_candidate"),
                                self._one_id(results["inspect"][ordinal], "visual_inspection_report"),
                            ]
                            specification = {
                                "workflow_id": workflow["id"],
                                "commission": self._commission_for_unit(workflow, unit),
                            }
                        elif stage == "decide":
                            inputs = [
                                self._one_id(results["generate"][ordinal], "visual_generation_report"),
                                self._one_id(results["inspect"][ordinal], "visual_inspection_report"),
                                self._one_id(results["caption"][ordinal], "visual_caption_report"),
                            ]
                            specification = {
                                "workflow_id": workflow["id"],
                                "commission": self._commission_for_unit(workflow, unit),
                            }
                        else:
                            inputs = [
                                self._one_id(results["generate"][ordinal], "visual_candidate"),
                                self._one_id(results["inspect"][ordinal], "visual_inspection_report"),
                                self._one_id(results["decide"][ordinal], "visual_decision_report"),
                            ]
                            specification = {
                                "workflow_id": workflow["id"],
                                "commission": self._commission_for_unit(workflow, unit),
                            }
                        return self._next(
                            workflow, key, f"visual.{stage}", inputs, predecessor, actor,
                            specification=specification,
                        )
                    if job["status"] != "succeeded":
                        return None
                    results[stage][ordinal] = self.store.workflow_job_artifacts(job["id"])

                candidate = self._one_artifact(results["generate"][ordinal], "visual_candidate")
                review = self._one_artifact(results["review"][ordinal], "visual_review_report")
                completed_candidates.append(candidate)
                completed_reviews.append(review)
                cursor = results["review"][ordinal]
                if self._candidate_is_usable(candidate, review):
                    selected_candidates.append(candidate)
                    selected_reviews.append(review)
                    accepted = True
                    break

            if exact_material and not accepted:
                return self._handle_review_exhaustion(
                    workflow, actor=actor,
                    detail=self._review_outcome_detail(completed_candidates, completed_reviews),
                )
            if not exact_material and len(selected_candidates) >= pack_limit:
                break

        if not selected_candidates:
            return self._handle_review_exhaustion(
                workflow, actor=actor,
                detail=self._review_outcome_detail(completed_candidates, completed_reviews),
            )
        if self.bundle.visual["shadow_mode"]:
            self.store.finish_visual_workflow(
                workflow["id"], "shadow_complete", actor=actor,
                reason=(
                    f"review evidence selected {len(selected_candidates)} usable candidate(s) "
                    f"from {len(completed_candidates)} completed attempt(s); admission remains locked"
                ),
            )
            return {"status": "shadow_complete", "stage": "review"}
        if "pack" not in jobs:
            predecessor = max(results["review"].values(), key=lambda value: value[2] or "")
            return self._next(
                workflow, "pack", "visual.pack_finalize",
                [item["id"] for item in selected_candidates + selected_reviews], predecessor, actor,
            )
        packed = self._succeeded(jobs, "pack")
        if packed is None:
            return None
        pack_artifact = self._one_artifact(packed, "visual_pack")
        selected_ids = [item.get("asset_artifact_id") for item in pack_artifact["manifest"].get("items", [])]
        generated_by_id = {item["id"]: item for item in selected_candidates}
        if not selected_ids or any(item_id not in generated_by_id for item_id in selected_ids):
            raise ValueError("visual pack names a candidate outside the generation result")
        # A workflow that already created the pre-fanout encode stage retains
        # that immutable frontier. New frontiers encode one accepted image per
        # job and combine the shards deterministically.
        if "encode" in jobs:
            encoded = self._succeeded(jobs, "encode")
        else:
            encoded_shards = []
            predecessor = packed
            for index, artifact_id in enumerate(selected_ids):
                key = f"encode/{index:04d}"
                job = jobs.get(key)
                candidate = generated_by_id[artifact_id]
                if job is None:
                    return self._next(
                        workflow, key, "visual.encode", [pack_artifact["id"], artifact_id],
                        predecessor, actor,
                        specification={
                            "workflow_id": workflow["id"],
                            "selection": {"ordinal": index, "asset_sha256": candidate["sha256"]},
                        },
                    )
                if job["status"] != "succeeded":
                    return None
                predecessor = self.store.workflow_job_artifacts(job["id"])
                self._one_artifact(predecessor, "visual_features")
                encoded_shards.append(predecessor)
            if "features" not in jobs:
                return self._next(
                    workflow, "features", "visual.features_finalize",
                    [pack_artifact["id"], *[self._one_id(item, "visual_features") for item in encoded_shards]],
                    predecessor, actor,
                )
            encoded = self._succeeded(jobs, "features")
        if encoded is None:
            return None
        if "experience" not in jobs:
            return self._next(
                workflow, "experience", "visual.experience_compile", [self._one_id(packed, "visual_pack")], encoded, actor,
                specification={"events": workflow["specification"]["experience_events"]},
            )
        if self._succeeded(jobs, "experience"):
            self.store.finish_visual_workflow(workflow["id"], "succeeded", actor=actor)
            return {"status": "succeeded", "stage": "experience"}
        return None

    @staticmethod
    def _previous_stage(stage: str) -> str:
        return {"inspect": "generate", "caption": "inspect", "decide": "caption", "review": "decide"}[stage]

    @staticmethod
    def _candidate_units(workflow: dict[str, Any]) -> list[dict[str, Any]]:
        units: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()
        for item in workflow["specification"]["plan"]["items"]:
            item_id = item.get("item_id")
            seeds = item.get("seeds", [item.get("seed", 0)])
            if not isinstance(item_id, str) or not item_id or not isinstance(seeds, list) or not seeds:
                raise ValueError("visual plan has an invalid candidate identity")
            for seed in seeds:
                identity = (item_id, seed)
                if isinstance(seed, bool) or not isinstance(seed, int) or identity in seen:
                    raise ValueError("visual plan has a duplicate or invalid item/seed candidate identity")
                seen.add(identity)
                units.append({"ordinal": len(units), "item_id": item_id, "seed": seed})
        if not units:
            raise ValueError("visual plan has no candidate units")
        limits = workflow["specification"]["limits"]
        maximum = limits.get("max_pack_items", 0) * limits.get("max_candidates_per_item", 0)
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1 or len(units) > maximum:
            raise ValueError("visual plan candidate units exceed the declared workflow bound")
        return units

    @staticmethod
    def _commission_for_unit(workflow: dict[str, Any], unit: dict[str, Any]) -> dict[str, Any]:
        commission = workflow["specification"]["plan"]
        matches = [item for item in commission["items"] if item.get("item_id") == unit["item_id"]]
        if len(matches) != 1:
            raise ValueError("incremental visual unit does not resolve to exactly one commissioned item")
        subset = {key: value for key, value in commission.items() if key not in {"items", "canonical_text"}}
        selected = dict(matches[0])
        selected["seeds"] = [unit["seed"]]
        subset["items"] = [selected]
        if "canonical_text" in commission:
            caption = selected.get("canonical_caption")
            subset["canonical_text"] = [caption] if caption is not None else []
        return subset

    @staticmethod
    def _one_artifact(
        result: tuple[dict[str, Any], list[dict[str, Any]], str | None], kind: str,
    ) -> dict[str, Any]:
        matches = [item for item in result[1] if item["kind"] == kind]
        if len(matches) != 1:
            raise ValueError(f"incremental visual stage requires exactly one {kind} artifact")
        return matches[0]

    def _one_id(self, result: tuple[dict[str, Any], list[dict[str, Any]], str | None], kind: str) -> str:
        return self._one_artifact(result, kind)["id"]

    @staticmethod
    def _candidate_is_usable(candidate: dict[str, Any], review: dict[str, Any]) -> bool:
        """Return one candidate's disposition from its immutable review evidence."""
        from .handlers.visual import _review_evidence

        matching = [
            evidence["manifest"] for evidence in _review_evidence(review)
            if evidence["manifest"].get("asset_sha256") == candidate.get("sha256")
        ]
        if len(matching) != 1:
            raise ValueError("candidate does not have exactly one matching independent review")
        return matching[0].get("asset_status") == "usable"

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

    @staticmethod
    def _selected_usable_candidates(
        workflow: dict[str, Any], candidates: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Select acceptable alternatives without ranking model quality.

        Selection follows the immutable item/seed order declared by the plan
        and stops at ``max_pack_items``. Every review and rejected candidate
        remains in the evidence ledger.
        """
        from .handlers.visual import _review_evidence

        review_by_digest: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for review in reviews:
            try:
                evidence_rows = _review_evidence(review)
            except SafetyError as exc:
                raise ValueError(f"invalid visual review evidence: {exc}") from exc
            for evidence in evidence_rows:
                digest = evidence["manifest"].get("asset_sha256")
                if not isinstance(digest, str) or digest in review_by_digest:
                    raise ValueError("visual review evidence is missing or duplicates an asset hash")
                review_by_digest[digest] = (evidence["artifact"], evidence["manifest"])

        declared_order: dict[tuple[str, int], int] = {}
        ordinal = 0
        for item in workflow["specification"]["plan"]["items"]:
            for seed in item["seeds"]:
                key = (item["item_id"], seed)
                if key in declared_order:
                    raise ValueError("visual plan repeats an item/seed candidate identity")
                declared_order[key] = ordinal
                ordinal += 1

        ordered: list[tuple[dict[str, Any], dict[str, Any]]] = []
        seen_order: set[int] = set()
        for candidate in candidates:
            manifest = candidate.get("manifest", {})
            key = (manifest.get("item_id"), manifest.get("seed"))
            if key not in declared_order or declared_order[key] in seen_order:
                raise ValueError("generated candidate is absent from or duplicated in the declared plan order")
            seen_order.add(declared_order[key])
            review_evidence = review_by_digest.get(candidate.get("sha256"))
            if review_evidence is None:
                raise ValueError("a generated candidate lacks its independent review")
            review, manifest = review_evidence
            if manifest.get("asset_status") == "usable":
                ordered.append((candidate, review))

        ordered.sort(key=lambda pair: declared_order[(pair[0]["manifest"]["item_id"], pair[0]["manifest"]["seed"])])
        limit = workflow["specification"]["limits"]["max_pack_items"]
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("visual workflow has an invalid max_pack_items limit")
        if workflow["specification"]["plan"].get("authority", {}).get("exact_material") is True:
            chosen = []
            for item in workflow["specification"]["plan"]["items"]:
                alternatives = [pair for pair in ordered if pair[0]["manifest"].get("item_id") == item["item_id"]]
                if not alternatives:
                    return [], []
                chosen.append(alternatives[0])
            if len(chosen) > limit:
                raise ValueError("exact visual material exceeds the pack limit")
        else:
            chosen = ordered[:limit]
        selected_reviews = list({review["id"]: review for _, review in chosen}.values())
        return [pair[0] for pair in chosen], selected_reviews

    @staticmethod
    def _review_outcome_detail(candidates: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> str:
        """Explain a partial exact-pack rejection using the preserved review evidence."""
        from .handlers.visual import _review_evidence

        candidate_by_digest = {item["sha256"]: item for item in candidates}
        usable = 0
        rejected: list[str] = []
        for review in reviews:
            for evidence in _review_evidence(review):
                manifest = evidence["manifest"]
                candidate = candidate_by_digest.get(manifest.get("asset_sha256"), {})
                item_id = candidate.get("manifest", {}).get("item_id", "unknown-item")
                if manifest.get("asset_status") == "usable":
                    usable += 1
                else:
                    rejected.append(f"- {item_id}: {manifest.get('reason') or 'reviewer supplied no reason'}")
        lines = [
            f"Review result: {usable} of {len(candidates)} candidates were usable; {len(rejected)} were rejected.",
            "The exact pack is incomplete because every commissioned item needs a usable candidate.",
        ]
        if rejected:
            lines.extend(["Rejected candidates:", *rejected])
        return "\n".join(lines)

    def _fail_without_job(
        self, workflow: dict[str, Any], *, actor: str, reason: str, detail: str = "",
        notify: bool = True,
    ) -> None:
        """Close and surface a workflow failure not represented by a job."""
        self.store.finish_visual_workflow(workflow["id"], "failed", actor=actor, reason=reason)
        if notify:
            self._notify_workflow_failure(workflow, reason=reason, detail=detail)

    def _handle_review_exhaustion(
        self, workflow: dict[str, Any], *, actor: str, detail: str,
    ) -> dict[str, str]:
        """Retry an ordinary rejection silently; surface only exhausted recovery."""
        reason = "independent review found no usable candidate"
        self._fail_without_job(workflow, actor=actor, reason=reason, detail=detail, notify=False)
        try:
            from .configured_campaign35 import CAMPAIGN_ID, VISUAL_CANDIDATE_ATTEMPTS, ConfiguredCampaign35

            if workflow["campaign_id"] == CAMPAIGN_ID:
                successor = ConfiguredCampaign35(
                    self.store, self.bundle, self.bundle.root.parent.parent,
                ).recommission_visual_workflow(
                    workflow["id"], actor=actor,
                    authority_reference=f"automatic-candidate-retry:{workflow['id']}",
                    candidate_attempt_budget=VISUAL_CANDIDATE_ATTEMPTS,
                )
                if successor is not None:
                    return {
                        "status": "retrying", "stage": "review",
                        "successor_workflow_id": successor["successor_workflow_id"],
                    }
        except Exception:
            # The preserved failure remains authoritative. If bounded
            # replacement cannot be created, the human-facing path below is
            # required rather than silently abandoning the exact pack.
            pass
        self._notify_workflow_failure(workflow, reason=reason, detail=detail)
        return {"status": "failed", "stage": "review"}

    def _notify_workflow_failure(
        self, workflow: dict[str, Any], *, reason: str, detail: str = "",
    ) -> None:
        """Open an operational thread only when automatic recovery is exhausted."""
        try:
            from .lab import LabStore
            LabStore(self.store).system_notice(
                "Visual workflow needs attention",
                "\n".join([
                    "A visual workflow stopped after its jobs completed.",
                    f"Workflow: {workflow['id']}",
                    f"Campaign: {workflow['campaign_id']}",
                    f"Reason: {reason}",
                    *([detail] if detail else []),
                    "The immutable jobs and review evidence were preserved. Do not retry unchanged until the workflow-level cause is reviewed.",
                ]),
                sender="mission_hub", actor="mission-hub:visual-workflow-failure",
            )
        except Exception:
            # The workflow event is authoritative. Presentation failure must
            # not undo or reopen its committed terminal transition.
            pass

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
        machine_id = machine_id_for_role(self.bundle, definition["executor_role"])
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
        control_id = machine_id_for_role(self.bundle, "mission_hub")
        executor_id = machine_id_for_role(self.bundle, "trainbox")
        for artifact_id in artifact_ids:
            try:
                self.store.artifact_at(artifact_id, machine_id=machine_id)
                continue
            except NotFoundError:
                pass
            if machine_id == control_id:
                self.service.retrieve_artifact(artifact_id, machine_id=executor_id, actor=actor)
            else:
                self.service.materialize_artifact(artifact_id, machine_id=executor_id, actor=actor)
