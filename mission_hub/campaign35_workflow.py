"""Advance the fully authorized Campaign 35 five-build experiment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .campaign_contract import campaign_contract_sha256, expected_evaluation_context, validate_campaign_contract
from .config import ConfigBundle, machine_id_for_role
from .errors import MissionHubError, NotFoundError, SafetyError
from .service import MissionHubService
from .store import MissionHubStore, strategic_available_at, utc_now


TERMINAL_FAILURES = {"failed", "blocked", "cancelled"}


class Campaign35Coordinator:
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store, self.bundle = store, bundle
        self.service = MissionHubService(store, bundle)
        self.campaign_id: str | None = None
        self.trainbox_machine = machine_id_for_role(bundle, "trainbox")
        self.hub_machine = machine_id_for_role(bundle, "mission_hub")

    def tick(self, *, actor: str) -> list[dict[str, str]]:
        try:
            change = self._advance(actor=actor)
            return [change] if change else []
        except (NotFoundError, SafetyError, ValueError, KeyError, TypeError) as exc:
            self._block(f"{type(exc).__name__}: {exc}", actor)
            return [{"status": "blocked", "stage": "campaign35-coordinator"}]
        except MissionHubError:
            return []

    def _campaign(self) -> tuple[dict[str, Any], dict[str, Any]] | None:
        with self.store._connect() as db:
            rows = db.execute("SELECT * FROM campaigns WHERE state='active' ORDER BY id").fetchall()
        matches = []
        for row in rows:
            metadata = json.loads(row["metadata_json"])
            execution = metadata.get("campaign35_execution")
            if isinstance(execution, dict):
                matches.append((row, metadata, execution))
        if len(matches) > 1:
            raise SafetyError("multiple active campaigns claim the five-build coordinator capability")
        if not matches:
            return None
        row, metadata, execution = matches[0]
        self.campaign_id = row["id"]
        if self.store.campaign_blocks(self.campaign_id, active_only=True):
            return None
        if execution.get("status") not in {"authorized_paused", "running"}:
            return None
        return metadata, execution

    def _id(self) -> str:
        if self.campaign_id is None:
            raise SafetyError("five-build coordinator has no selected campaign")
        return self.campaign_id

    def _advance(self, *, actor: str) -> dict[str, str] | None:
        campaign = self._campaign()
        if campaign is None:
            return None
        metadata, execution = campaign
        jobs = self._jobs()
        root = jobs.get("campaign35:neutral-root:v1")
        if root is None or root["status"] != "succeeded":
            return None
        root_checkpoint = self._one_job_artifact(root["id"], "checkpoint")
        if metadata.get("starting_checkpoint_artifact_id") != root_checkpoint["id"]:
            self._bind_runtime_value("starting_checkpoint_artifact_id", root_checkpoint["id"], actor)
            return {"status": "bound", "stage": "neutral-root"}

        workflows = self._cortex_by_branch()
        if workflows.get("m1-words", {}).get("status") in TERMINAL_FAILURES:
            # A replacement is authorized only by the verified recovery state
            # machine. Campaign orchestration must not silently route around a
            # terminal failed workflow.
            return None
        if "m1-words" not in workflows:
            workflow = self.store.create_cortex_workflow(self.bundle, self._text_workflow(execution, root_checkpoint["id"]), actor=actor)
            return {"status": workflow["status"], "stage": "m1-words"}

        visual = self._visual_batches()
        if any(item["status"] in TERMINAL_FAILURES for item in visual):
            return None
        if len(visual) != len(execution["batches"]) or any(item["status"] != "succeeded" for item in visual):
            return None
        batch_inputs = self._visual_batch_inputs(execution, visual)
        for branch, mode in (("m2-images", "visual"), ("m3-words-and-images", "joint")):
            if branch not in workflows:
                workflow = self.store.create_cortex_workflow(
                    self.bundle, self._multimodal_workflow(execution, batch_inputs, root_checkpoint["id"], branch, mode),
                    actor=actor,
                )
                return {"status": workflow["status"], "stage": branch}

        workflows = self._cortex_by_branch()
        if any(workflows.get(branch, {}).get("status") != "succeeded" for branch in ("m1-words", "m2-images", "m3-words-and-images")):
            return None
        terminals = {branch: self._workflow_terminal_checkpoint(workflows[branch]) for branch in ("m1-words", "m2-images", "m3-words-and-images")}
        merge = jobs.get("campaign35:m4:merge:v1")
        if merge is None:
            for artifact in (terminals["m1-words"], terminals["m2-images"]):
                self._ensure_trainbox(artifact["id"], actor)
            job = self.store.create_job(
                self.bundle, job_type="model.merge",
                input_payload={"input_artifact_ids": [terminals["m1-words"]["id"], terminals["m2-images"]["id"]], "merge_policy": "concatenate_bdh_sparse_neurons_average_shared_bridges", "output_branch_id": "m4-merged"},
                idempotency_key="campaign35:m4:merge:v1", created_by=actor, campaign_id=self._id(),
                requested_machine_id=self.trainbox_machine, approved=True,
            )
            return {"status": job["status"], "stage": "m4-merged"}
        if merge["status"] != "succeeded":
            return None
        merged = self._one_job_artifact(merge["id"], "checkpoint")
        if metadata.get("campaign35_merge_checkpoint_artifact_id") != merged["id"]:
            self._bind_runtime_value("campaign35_merge_checkpoint_artifact_id", merged["id"], actor)
            self.store.inherit_merged_checkpoint_knowledge(
                checkpoint_artifact_id=merged["id"],
                source_checkpoint_artifact_ids=[terminals["m1-words"]["id"], terminals["m2-images"]["id"]],
                campaign_id=self._id(),
                evidence=[terminals["m1-words"]["id"], terminals["m2-images"]["id"], merge["id"]], actor=actor,
            )
            return {"status": "bound", "stage": "m4-merged"}

        m4_eval = jobs.get("campaign35:m4:evaluate:v1")
        if m4_eval is None:
            contract = validate_campaign_contract(metadata["campaign_contract"], self.bundle.campaign_modes)
            payload = {
                "candidate_artifact_id": merged["id"],
                "parent_artifact_id": terminals["m1-words"]["id"],
                "suite_artifact_id": execution["evaluation_suite_artifact_id"],
                "evaluation_context": expected_evaluation_context(
                    contract, self.bundle.campaign_modes, phase="evolutionary_branch",
                    branch_id="m4-merged", branch_complete=True,
                    all_required_branches_complete=False,
                ),
                "parameters": {"ingress_device": "cuda:0", "core_device": "cuda:1", "max_new_tokens": 128},
            }
            for artifact_id in (merged["id"], terminals["m1-words"]["id"], execution["evaluation_suite_artifact_id"]):
                self._ensure_trainbox(artifact_id, actor)
            job = self.store.create_job(
                self.bundle, job_type="model.evaluate", input_payload=payload,
                idempotency_key="campaign35:m4:evaluate:v1", created_by=actor,
                campaign_id=self._id(), requested_machine_id=self.trainbox_machine, approved=True,
            )
            return {"status": job["status"], "stage": "m4-evaluate"}
        if m4_eval["status"] != "succeeded":
            return None

        if "m4-healed" not in workflows:
            workflow = self.store.create_cortex_workflow(
                self.bundle, self._multimodal_workflow(execution, batch_inputs, merged["id"], "m4-healed", "visual", starting_role="authorized_merge"),
                actor=actor,
            )
            return {"status": workflow["status"], "stage": "m4-healed"}
        workflows = self._cortex_by_branch()
        if workflows["m4-healed"]["status"] != "succeeded":
            return None
        terminals.update({
            "m4-merged": merged,
            "m4-healed": self._workflow_terminal_checkpoint(workflows["m4-healed"]),
        })
        # A text chat/MRI scan cannot answer this campaign's central modality
        # question. Every one of the five terminal checkpoints therefore gets
        # the same read-only, deterministic cross-modal probe fixture.
        probe_input = batch_inputs[0]
        for branch in ("m1-words", "m2-images", "m3-words-and-images", "m4-merged", "m4-healed"):
            key = f"campaign35:{branch}:crossmodal-evaluate:v1"
            probe = jobs.get(key)
            if probe is None:
                checkpoint = terminals[branch]
                for artifact_id in (checkpoint["id"], probe_input["features"]["id"], probe_input["experience"]["id"]):
                    self._ensure_trainbox(artifact_id, actor)
                job = self.store.create_job(
                    self.bundle, job_type="model.multimodal_evaluate",
                    input_payload={
                        "input_artifact_ids": [checkpoint["id"], probe_input["features"]["id"], probe_input["experience"]["id"]],
                        "branch_id": branch,
                        "parameters": {"ingress_device": "cuda:0", "core_device": "cuda:1", "max_new_tokens": 24},
                    },
                    idempotency_key=key, created_by=actor, campaign_id=self._id(),
                    requested_machine_id=self.trainbox_machine, approved=True,
                )
                return {"status": job["status"], "stage": f"{branch}-crossmodal-evaluate"}
            if probe["status"] != "succeeded":
                return None
        # The recommendation fixture is deliberately created only after all
        # five text/MRI and five cross-modal evidence bundles exist. Campaign
        # closure happens only after the proposal is surfaced to the operator.
        jobs = self._jobs()
        recommendation = jobs.get("campaign35:post-campaign-recommendation:v1")
        if recommendation is None:
            evidence_ids = self._terminal_evaluation_artifacts() + self._crossmodal_evaluation_artifacts()
            for artifact_id in evidence_ids:
                try:
                    self.store.artifact_at(artifact_id, machine_id=self.hub_machine)
                except NotFoundError:
                    self.service.retrieve_artifact(artifact_id, machine_id=self.trainbox_machine, actor=actor)
            job = self.store.create_job(
                self.bundle, job_type="campaign.decide",
                input_payload={"campaign_id": self._id(), "observation_ids": [], "evidence_ids": evidence_ids, "allowed_actions": ["recommend_next_campaign", "recommend_foundational_base_candidate", "recommend_no_action"], "budget": {"authority": "recommendation_only", "activation": False}},
                idempotency_key="campaign35:post-campaign-recommendation:v1", created_by=actor,
                campaign_id=self._id(), requested_machine_id=self.hub_machine, approved=True,
                available_at=strategic_available_at(utc_now(), self.bundle.orchestration["strategic_boundary_cooldown_seconds"]),
            )
            return {"status": job["status"], "stage": "post-campaign-recommendation"}
        if recommendation["status"] == "succeeded" and execution.get("status") != "complete":
            proposal = self._one_job_artifact(recommendation["id"], "decision_proposal")
            local = self.store.artifact_at(proposal["id"], machine_id=self.hub_machine)
            recommendation_doc = json.loads(Path(local["uri"]).read_text(encoding="utf-8"))
            from .lab import LabStore
            LabStore(self.store).system_notice(
                "Campaign 35 complete · five builds and recommendation ready",
                "\n".join((
                    "M1 words, M2 images, M3 words+images, M4 merged, and M4 healed all have terminal chat/MRI and cross-modal evidence.",
                    f"Post-campaign recommendation: {proposal['id']}",
                    f"Recommendation: {json.dumps(recommendation_doc.get('action', {}), ensure_ascii=False)}",
                    f"Rationale: {recommendation_doc.get('rationale', '')}",
                    "The recommendation is nonbinding. No checkpoint was promoted automatically.",
                )), actor="mission-hub:campaign35-completion",
            )
            standard = self._terminal_evaluation_artifacts_by_branch()
            crossmodal = self._crossmodal_evaluation_artifacts_by_branch()
            outputs = {
                branch: {
                    "checkpoint_artifact_id": terminals[branch]["id"],
                    "checkpoint_sha256": terminals[branch]["sha256"],
                    "evaluation_report_artifact_id": standard[branch],
                    "crossmodal_evaluation_report_artifact_id": crossmodal[branch],
                }
                for branch in ("m1-words", "m2-images", "m3-words-and-images", "m4-merged", "m4-healed")
            }
            self._mark_complete(proposal["id"], outputs, actor)
            self.store.request_pipeline_state("paused", actor="mission-hub:campaign35-completion")
            return {"status": "complete", "stage": "five-build-campaign"}
        return None

    def _terminal_evaluation_artifacts(self):
        values = self._terminal_evaluation_artifacts_by_branch()
        return [values[branch] for branch in ("m1-words", "m2-images", "m3-words-and-images", "m4-merged", "m4-healed")]

    def _terminal_evaluation_artifacts_by_branch(self):
        with self.store._connect() as db:
            rows = db.execute("""SELECT j.input_json,a.id FROM jobs j JOIN runs r ON r.job_id=j.id AND r.status='succeeded' JOIN artifacts a ON a.producing_run_id=r.id AND a.kind='evaluation_report' WHERE j.campaign_id=? AND j.job_type='model.evaluate' ORDER BY r.finished_at""", (self._id(),)).fetchall()
        selected = {json.loads(row["input_json"])["evaluation_context"]["branch_id"]: row["id"] for row in rows if json.loads(row["input_json"])["evaluation_context"].get("branch_complete") is True}
        required = {"m1-words", "m2-images", "m3-words-and-images", "m4-merged", "m4-healed"}
        if set(selected) != required:
            raise SafetyError(f"Campaign 35 requires exactly five terminal evaluation bundles, found {len(selected)}")
        return selected

    def _crossmodal_evaluation_artifacts(self):
        values = self._crossmodal_evaluation_artifacts_by_branch()
        return [values[branch] for branch in ("m1-words", "m2-images", "m3-words-and-images", "m4-merged", "m4-healed")]

    def _crossmodal_evaluation_artifacts_by_branch(self):
        with self.store._connect() as db:
            rows = db.execute("""SELECT j.input_json,a.id FROM jobs j JOIN runs r ON r.job_id=j.id AND r.status='succeeded' JOIN artifacts a ON a.producing_run_id=r.id AND a.kind='crossmodal_evaluation_report' WHERE j.campaign_id=? AND j.job_type='model.multimodal_evaluate' ORDER BY r.finished_at""", (self._id(),)).fetchall()
        by_branch = {json.loads(row["input_json"])["branch_id"]: row["id"] for row in rows}
        required = ["m1-words", "m2-images", "m3-words-and-images", "m4-merged", "m4-healed"]
        if set(by_branch) != set(required):
            raise SafetyError(f"Campaign 35 requires exactly five cross-modal terminal reports, found {len(by_branch)}")
        return by_branch

    def _jobs(self) -> dict[str, dict[str, Any]]:
        with self.store._connect() as db:
            return {row["idempotency_key"]: dict(row) for row in db.execute("SELECT * FROM jobs WHERE campaign_id=?", (self._id(),))}

    def _cortex_by_branch(self) -> dict[str, dict[str, Any]]:
        result = {}
        with self.store._connect() as db:
            rows = db.execute("SELECT id,specification_json FROM cortex_workflows WHERE campaign_id=? ORDER BY created_at", (self._id(),)).fetchall()
        for row in rows:
            workflow = self.store.cortex_workflow(row["id"])
            result[workflow["specification"]["branch_id"]] = workflow
        return result

    def _visual_batches(self) -> list[dict[str, Any]]:
        with self.store._connect() as db:
            rows = db.execute("SELECT id FROM visual_workflows WHERE campaign_id=? AND json_extract(specification_json,'$.plan.authority.exact_material')=1 ORDER BY created_at", (self._id(),)).fetchall()
        workflows = [self.store.visual_workflow(row[0]) for row in rows]
        return self._latest_visual_attempts(workflows)

    @staticmethod
    def _latest_visual_attempts(workflows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Select one authoritative attempt for each immutable batch plan.

        Failed commissioning attempts remain evidence, but must not keep a
        campaign blocked after an explicitly created successor for the same
        plan. Creation order is authoritative because workflow IDs are random.
        """
        latest: dict[str, dict[str, Any]] = {}
        for workflow in workflows:
            plan_id = workflow["specification"]["plan"]["plan_id"]
            previous = latest.get(plan_id)
            if previous is None or (workflow["created_at"], workflow["id"]) > (
                previous["created_at"], previous["id"],
            ):
                latest[plan_id] = workflow
        return [latest[plan_id] for plan_id in sorted(latest)]

    def _visual_batch_inputs(self, execution, workflows):
        indexed = {item["specification"]["plan"]["plan_id"].split("campaign35-", 1)[1].rsplit("-visual-v1", 1)[0]: item for item in workflows}
        result = []
        for batch in execution["batches"]:
            workflow = indexed[batch["batch_id"]]
            jobs = {item["stage_key"]: item for item in workflow["jobs"]}
            result.append({
                "batch": batch,
                "features": self._one_job_artifact(jobs["encode"]["id"], "visual_features"),
                "experience": self._one_job_artifact(jobs["experience"]["id"], "visual_experience"),
            })
        return result

    def _base_workflow(self, execution, parent, branch):
        return {
            "campaign_id": self._id(), "branch_id": branch, "starting_checkpoint_artifact_id": parent,
            "evaluation_suite_artifact_id": execution["evaluation_suite_artifact_id"],
            "architecture": "lfm2_5_encoder_230m_frozen__ninereeds_1_2b__lfm2_5_230m_frozen",
            "identity_scope": "identity_and_integrity",
            "evaluation_parameters": {"ingress_device": "cuda:0", "core_device": "cuda:1", "max_new_tokens": 128},
            "authorization": {"exact_workflow_reviewed": True, "allow_weight_updates": True, "allow_checkpoint_promotion": False, "allow_automatic_branch_ranking": False, "allow_pipeline_continue_after_completion": True},
        }

    def _text_workflow(self, execution, parent):
        value = self._base_workflow(execution, parent, "m1-words")
        value["training_job_type"] = "model.train"
        value["sessions"] = [{
            "id": f"m1-{batch['batch_id']}", "corpus_artifact_id": batch["corpus_artifact_id"],
            "ordered_concepts": batch["ordered_concepts"],
            "parameters": {"epochs": 1, "batch_size": 1, "max_examples": batch["text_examples"], "learning_rate": 0.0002, "weight_decay": 0.0, "seed": 35000000, "ingress_device": "cuda:0", "core_device": "cuda:1", "train_scope": "full", "rms_clip": 0.125, "stochastic_rounding": True, "local_files_only": True, "probe_max_new_tokens": 16, "source_concept": f"campaign35-{batch['batch_id']}"},
        } for batch in execution["batches"]]
        return value

    def _multimodal_workflow(self, execution, inputs, parent, branch, mode, starting_role=None):
        value = self._base_workflow(execution, parent, branch)
        value.update({"training_job_type": "model.multimodal_train", "multimodal_mode": mode})
        if starting_role:
            value["starting_checkpoint_role"] = starting_role
        sessions = []
        for item in inputs:
            batch, experience = item["batch"], item["experience"]
            observed = [event for event in experience["manifest"]["events"] if event["type"] == "observe_image"]
            visual_events = [{"type": "visual", "concept": event["concept"], "ordinal": event["ordinal"], "completion": next(row["text"] for row in experience["manifest"]["events"] if row["type"] == "hear_or_read_text" and row["ordinal"] == event["ordinal"] and row["example_index"] == event["example_index"]), "asset_sha256": event["asset_sha256"]} for event in observed]
            if mode == "joint":
                corpus = self.store.artifact_at(batch["corpus_artifact_id"], machine_id=self.hub_machine)
                text_rows = [json.loads(line) for line in Path(corpus["uri"]).read_text(encoding="utf-8").splitlines() if line]
                events = []
                for text, visual in zip(text_rows, visual_events, strict=True):
                    events.extend([{"type": "text", "concept": text.get("concept", text.get("lesson_concept")), "ordinal": text["ordinal"], "prompt": text["prompt"], "completion": text["completion"]}, visual])
            else:
                events = visual_events
            sessions.append({"id": f"{branch}-{batch['batch_id']}", "visual_features_artifact_id": item["features"]["id"], "visual_experience_artifact_id": experience["id"], "ordered_concepts": batch["ordered_concepts"], "events": events, "parameters": {"epochs": 1, "learning_rate": 0.0002, "weight_decay": 0.0, "seed": 35000000, "ingress_device": "cuda:0", "core_device": "cuda:1", "local_files_only": True, "rms_clip": 0.125, "stochastic_rounding": True}})
        value["sessions"] = sessions
        return value

    def _workflow_terminal_checkpoint(self, workflow):
        jobs = {item["stage_key"]: item for item in workflow["jobs"]}
        index = len(workflow["specification"]["sessions"]) - 1
        return self._one_job_artifact(jobs[f"s{index:02d}:train"]["id"], "checkpoint")

    def _one_job_artifact(self, job_id, kind):
        artifacts = [item for item in self.store.workflow_job_artifacts(job_id)[1] if item["kind"] == kind]
        if len(artifacts) != 1:
            raise SafetyError(f"job {job_id} does not have exactly one {kind}")
        return artifacts[0]

    def _ensure_trainbox(self, artifact_id, actor):
        try: return self.store.artifact_at(artifact_id, machine_id=self.trainbox_machine)
        except NotFoundError: return self.service.materialize_artifact(artifact_id, machine_id=self.trainbox_machine, actor=actor)

    def _bind_runtime_value(self, key, value, actor):
        with self.store.transaction() as db:
            row = db.execute("SELECT metadata_json FROM campaigns WHERE id=?", (self._id(),)).fetchone()
            metadata = json.loads(row[0]); existing = metadata.get(key)
            if existing is not None and existing != value: raise SafetyError(f"Campaign 35 {key} changed")
            metadata[key] = value
            db.execute("UPDATE campaigns SET metadata_json=?,updated_at=? WHERE id=?", (json.dumps(metadata, sort_keys=True, separators=(",", ":")), utc_now(), self._id()))
            self.store._event(db, "campaign", self._id(), "campaign.runtime_artifact_bound", actor, {"field": key, "artifact_id": value})

    def _mark_complete(self, recommendation_artifact_id, outputs, actor):
        with self.store.transaction() as db:
            row = db.execute("SELECT metadata_json FROM campaigns WHERE id=?", (self._id(),)).fetchone()
            metadata = json.loads(row[0]); execution = metadata["campaign35_execution"]
            execution.update({"status": "complete", "completed_at": utc_now(), "recommendation_artifact_id": recommendation_artifact_id, "terminal_outputs": outputs})
            db.execute("UPDATE campaigns SET metadata_json=?,updated_at=? WHERE id=?", (json.dumps(metadata, sort_keys=True, separators=(",", ":")), utc_now(), self._id()))
            self.store._event(db, "campaign", self._id(), "campaign.five_build_evidence_complete", actor, {"recommendation_artifact_id": recommendation_artifact_id, "output_count": 5})

    def _block(self, reason, actor):
        campaign = self._campaign()
        if campaign is None: return
        with self.store.transaction() as db:
            row = db.execute("SELECT metadata_json FROM campaigns WHERE id=?", (self._id(),)).fetchone()
            metadata = json.loads(row[0]); metadata["campaign35_execution"].update({"status": "blocked", "blocked_reason": reason, "blocked_at": utc_now()})
            db.execute("UPDATE campaigns SET metadata_json=?,updated_at=? WHERE id=?", (json.dumps(metadata, sort_keys=True, separators=(",", ":")), utc_now(), self._id()))
            self.store._event(db, "campaign", self._id(), "campaign.coordinator_blocked", actor, {"reason": reason})
        self.store.block_campaign(
            self._id(), source_id="five-build-coordinator", code="coordinator_invariant_failed",
            detail=reason, actor=actor,
        )
        from .lab import LabStore
        LabStore(self.store).system_notice("Campaign 35 coordinator blocked", f"The real five-build graph stopped safely.\nReason: {reason}\nNo unchanged retry was started.", actor="mission-hub:campaign35-coordinator")
        self.store.request_pipeline_state("paused", actor="mission-hub:campaign35-coordinator")
