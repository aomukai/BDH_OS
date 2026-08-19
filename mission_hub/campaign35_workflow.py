"""Advance the fully authorized Campaign 35 five-build experiment."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from .campaign_contract import campaign_contract_sha256, expected_evaluation_context, validate_campaign_contract
from .config import ConfigBundle, machine_id_for_role
from .errors import MissionHubError, NotFoundError, SafetyError
from .service import MissionHubService
from .store import MissionHubStore, strategic_available_at, utc_now


TERMINAL_FAILURES = {"failed", "blocked", "cancelled"}
BRANCHES = ("m1-words", "m2-images", "m3-words-and-images", "m4-merged", "m5-healed")
STANDARD_EVALUATION_BRANCHES = ("m1-words", "m3-words-and-images", "m4-merged", "m5-healed")
M3_REPLAY_COUNTS = {
    "session_count": 51,
    "event_count": 22_288,
    "visual_event_count": 14_397,
    "text_event_count": 7_891,
    "concept_count": 2_500,
}


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

        prebranches_complete = all(
            workflows.get(branch, {}).get("status") == "succeeded"
            for branch in ("m2-images", "m3-words-and-images")
        )
        if prebranches_complete:
            # Completed workflows are the immutable source ledger. Historical
            # visual commissioning attempts may subsequently be cancelled as
            # cleanup and must not invalidate already-produced M2/M3 evidence.
            first_session = workflows["m2-images"]["specification"]["sessions"][0]
            probe_input = {
                "features": {"id": first_session["visual_features_artifact_id"]},
                "experience": {"id": first_session["visual_experience_artifact_id"]},
            }
        else:
            # Before M2/M3 exist, no visual branch may reuse the obsolete
            # sentence-matched material: its replacement curriculum must be
            # independently verified, frozen, and bound first.
            visual_curriculum = execution.get("visual_curriculum")
            if not isinstance(visual_curriculum, dict) or visual_curriculum.get("status") != "frozen":
                return None
            if (
                visual_curriculum.get("concept_count") != 2500
                or visual_curriculum.get("images_per_concept") != 10
                or visual_curriculum.get("event_count") != 25000
            ):
                raise SafetyError("Campaign 35 visual curriculum is not the exact 2,500 × 10 contract")
            visual = self._visual_batches()
            if any(item["status"] in TERMINAL_FAILURES for item in visual):
                return None
            if len(visual) != len(execution["batches"]) or any(item["status"] != "succeeded" for item in visual):
                return None
            batch_inputs = self._visual_batch_inputs(execution, visual)
            probe_input = batch_inputs[0]
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
        authorized_merge_id = metadata.get("campaign35_merge_checkpoint_artifact_id")
        if authorized_merge_id is None:
            self._bind_runtime_value("campaign35_merge_checkpoint_artifact_id", merged["id"], actor)
            self.store.inherit_merged_checkpoint_knowledge(
                checkpoint_artifact_id=merged["id"],
                source_checkpoint_artifact_ids=[terminals["m1-words"]["id"], terminals["m2-images"]["id"]],
                campaign_id=self._id(),
                evidence=[terminals["m1-words"]["id"], terminals["m2-images"]["id"], merge["id"]], actor=actor,
            )
            return {"status": "bound", "stage": "m4-merged"}
        if authorized_merge_id != merged["id"]:
            # A verified repair preserves the original failed M4 evidence and
            # explicitly rebinds this field to its repaired checkpoint. Follow
            # that durable binding instead of trying to overwrite it with v1.
            merged = self._successful_merge_checkpoint_for_artifact(
                jobs, authorized_merge_id,
            )

        m4_eval = self._successful_m4_evaluation(jobs, merged["id"])
        if m4_eval is None:
            original = jobs.get("campaign35:m4:evaluate:v1")
            if original is not None:
                # A preserved terminal failure needs an explicit verified
                # successor; it must never be silently recreated or bypassed.
                return None
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
        if "m5-healed" not in workflows:
            replay_source, replay_material = self._canonical_m3_replay_source(metadata)
            workflow = self.store.create_cortex_workflow(
                self.bundle,
                self._replay_multimodal_workflow(
                    execution,
                    replay_source,
                    replay_material,
                    merged["id"],
                    "m5-healed",
                ),
                actor=actor,
            )
            return {"status": workflow["status"], "stage": "m5-healed"}
        workflows = self._cortex_by_branch()
        if workflows["m5-healed"]["status"] != "succeeded":
            return None
        terminals.update({
            "m4-merged": merged,
            "m5-healed": self._workflow_terminal_checkpoint(workflows["m5-healed"]),
        })
        # A text chat/MRI scan cannot answer this campaign's central modality
        # question. Every one of the five terminal checkpoints therefore gets
        # the same read-only, deterministic cross-modal probe fixture.
        for branch in BRANCHES:
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
                        "parameters": {
                            "ingress_device": "cuda:0", "core_device": "cuda:1",
                            "max_new_tokens": 24,
                            "scan_mode": "visual_structure" if branch == "m2-images" else "crossmodal",
                        },
                    },
                    idempotency_key=key, created_by=actor, campaign_id=self._id(),
                    requested_machine_id=self.trainbox_machine, approved=True,
                )
                return {"status": job["status"], "stage": f"{branch}-crossmodal-evaluate"}
            if probe["status"] != "succeeded":
                return None
        # The strategic decision is created only after four language-capable
        # and five cross-modal evidence bundles exist. Its principal-tier direction
        # is accepted directly; subsequent physical work still emits its own
        # evidence and remains subject to ordinary execution verification.
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
                input_payload={"campaign_id": self._id(), "observation_ids": [], "evidence_ids": evidence_ids, "allowed_actions": ["authorize_next_campaign", "designate_foundational_base", "authorize_no_new_campaign"], "budget": {"authority": "principal_tier", "activation": "direction_is_immediate_execution_is_verified"}},
                idempotency_key="campaign35:post-campaign-recommendation:v1", created_by=actor,
                campaign_id=self._id(), requested_machine_id=self.hub_machine, approved=True,
                available_at=strategic_available_at(utc_now(), self.bundle.orchestration["strategic_boundary_cooldown_seconds"]),
            )
            return {"status": job["status"], "stage": "post-campaign-recommendation"}
        if recommendation["status"] == "succeeded" and execution.get("status") != "complete":
            proposal = self._one_job_artifact(recommendation["id"], "strategic_decision")
            local = self.store.artifact_at(proposal["id"], machine_id=self.hub_machine)
            recommendation_doc = json.loads(Path(local["uri"]).read_text(encoding="utf-8"))
            from .lab import LabStore
            LabStore(self.store).system_notice(
                "Campaign 35 complete · strategic direction recorded",
                "\n".join((
                    "M1 words, M3 words+images, M4 merged, and M5 healed have terminal language/MRI evidence; M2 has image-only structural evidence.",
                    f"Strategic decision: {proposal['id']}",
                    f"Authorized direction: {json.dumps(recommendation_doc.get('action', {}), ensure_ascii=False)}",
                    f"Rationale: {recommendation_doc.get('rationale', '')}",
                    "The strategic decision is authoritative and has been recorded as executed. Physical follow-up remains evidence-verified by Mission Hub.",
                )), actor="mission-hub:campaign35-completion",
            )
            standard = self._terminal_evaluation_artifacts_by_branch()
            crossmodal = self._crossmodal_evaluation_artifacts_by_branch()
            outputs = {
                branch: {
                    "checkpoint_artifact_id": terminals[branch]["id"],
                    "checkpoint_sha256": terminals[branch]["sha256"],
                    "evaluation_report_artifact_id": standard.get(branch),
                    "crossmodal_evaluation_report_artifact_id": crossmodal[branch],
                }
                for branch in BRANCHES
            }
            self._mark_complete(proposal["id"], outputs, actor)
            self.store.request_pipeline_state("paused", actor="mission-hub:campaign35-completion")
            return {"status": "complete", "stage": "five-build-campaign"}
        return None

    def _terminal_evaluation_artifacts(self):
        values = self._terminal_evaluation_artifacts_by_branch()
        return [values[branch] for branch in STANDARD_EVALUATION_BRANCHES]

    def _terminal_evaluation_artifacts_by_branch(self):
        with self.store._connect() as db:
            rows = db.execute("""SELECT j.input_json,a.id FROM jobs j JOIN runs r ON r.job_id=j.id AND r.status='succeeded' JOIN artifacts a ON a.producing_run_id=r.id AND a.kind='evaluation_report' WHERE j.campaign_id=? AND j.job_type='model.evaluate' ORDER BY r.finished_at""", (self._id(),)).fetchall()
        required = set(STANDARD_EVALUATION_BRANCHES)
        selected = {
            payload["evaluation_context"]["branch_id"]: row["id"]
            for row in rows
            if (payload := json.loads(row["input_json"]))["evaluation_context"].get("branch_complete") is True
            and payload["evaluation_context"].get("branch_id") in required
        }
        if set(selected) != required:
            raise SafetyError(f"Campaign 35 requires exactly four language-capable terminal evaluation bundles, found {len(selected)}")
        return selected

    def _crossmodal_evaluation_artifacts(self):
        values = self._crossmodal_evaluation_artifacts_by_branch()
        return [values[branch] for branch in BRANCHES]

    def _crossmodal_evaluation_artifacts_by_branch(self):
        with self.store._connect() as db:
            rows = db.execute("""SELECT j.input_json,a.id FROM jobs j JOIN runs r ON r.job_id=j.id AND r.status='succeeded' JOIN artifacts a ON a.producing_run_id=r.id AND a.kind='crossmodal_evaluation_report' WHERE j.campaign_id=? AND j.job_type='model.multimodal_evaluate' ORDER BY r.finished_at""", (self._id(),)).fetchall()
        by_branch = {json.loads(row["input_json"])["branch_id"]: row["id"] for row in rows}
        required = list(BRANCHES)
        if set(by_branch) != set(required):
            raise SafetyError(f"Campaign 35 requires exactly five cross-modal terminal reports, found {len(by_branch)}")
        return by_branch

    def _jobs(self) -> dict[str, dict[str, Any]]:
        with self.store._connect() as db:
            return {row["idempotency_key"]: dict(row) for row in db.execute("SELECT * FROM jobs WHERE campaign_id=?", (self._id(),))}

    def _successful_merge_checkpoint_for_artifact(self, jobs, artifact_id):
        matches = []
        for job in jobs.values():
            if job["job_type"] != "model.merge" or job["status"] != "succeeded":
                continue
            try:
                checkpoint = self._one_job_artifact(job["id"], "checkpoint")
            except SafetyError:
                continue
            if checkpoint["id"] == artifact_id:
                matches.append((job.get("created_at", ""), job["id"], checkpoint))
        if not matches:
            raise SafetyError(
                "Campaign 35 authorized repaired M4 checkpoint has no successful merge evidence"
            )
        return max(matches, key=lambda item: (item[0], item[1]))[2]

    @staticmethod
    def _successful_m4_evaluation(jobs, checkpoint_artifact_id):
        matches = []
        for job in jobs.values():
            if job["job_type"] != "model.evaluate" or job["status"] != "succeeded":
                continue
            payload = json.loads(job["input_json"])
            context = payload.get("evaluation_context", {})
            if (
                payload.get("candidate_artifact_id") == checkpoint_artifact_id
                and context.get("branch_id") == "m4-merged"
                and context.get("branch_complete") is True
            ):
                matches.append(job)
        if not matches:
            return None
        return max(matches, key=lambda job: (job.get("created_at", ""), job["id"]))

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
        if branch == "m2-images":
            value["evaluation_policy"] = "none"
        if starting_role:
            value["starting_checkpoint_role"] = starting_role
        sessions = []
        for item in inputs:
            batch, experience = item["batch"], item["experience"]
            observed = [event for event in experience["manifest"]["events"] if event["type"] == "observe_image"]
            captions = {
                (row["ordinal"], row["example_index"]): row["text"]
                for row in experience["manifest"]["events"]
                if row["type"] == "hear_or_read_text"
            }
            events = []
            for event in observed:
                key = (event["ordinal"], event["example_index"])
                caption = captions[key]
                word = event.get("word")
                if not isinstance(word, str) or not word or any(character.isspace() for character in word):
                    raise SafetyError(
                        "Campaign 35 M2 requires an explicit, non-empty one-word label "
                        f"for every visual event; invalid label at ordinal {event['ordinal']} "
                        f"example {event['example_index']}"
                    )
                events.append({
                    "type": "visual", "concept": event["concept"],
                    "ordinal": event["ordinal"],
                    "completion": caption if mode == "joint" else word,
                    "asset_sha256": event["asset_sha256"],
                })
            sessions.append({"id": f"{branch}-{batch['batch_id']}", "visual_features_artifact_id": item["features"]["id"], "visual_experience_artifact_id": experience["id"], "ordered_concepts": batch["ordered_concepts"], "events": events, "parameters": {"epochs": 1, "learning_rate": 0.0002, "weight_decay": 0.0, "seed": 35000000, "ingress_device": "cuda:0", "core_device": "cuda:1", "local_files_only": True, "rms_clip": 0.125, "stochastic_rounding": True}})
        value["sessions"] = sessions
        return value

    def _canonical_m3_replay_source(self, metadata):
        """Resolve the frozen full M3 ledger, never its restart continuation."""
        material = metadata.get("campaign35_m3_material")
        if not isinstance(material, dict) or material.get("status") != "frozen_for_m3":
            raise SafetyError("Campaign 35 M5 requires the frozen canonical M3 material record")
        mismatches = {
            key: (material.get(key), expected)
            for key, expected in M3_REPLAY_COUNTS.items()
            if material.get(key) != expected
        }
        if mismatches:
            raise SafetyError(f"Campaign 35 canonical M3 material counts changed: {mismatches}")
        if material.get("same_m2_assets_and_visual_order") is not True or material.get("same_m1_text_and_concept_order") is not True:
            raise SafetyError("Campaign 35 canonical M3 material lacks exact source-order attestations")
        workflow_id = material.get("workflow_id")
        if not isinstance(workflow_id, str) or not workflow_id:
            raise SafetyError("Campaign 35 canonical M3 material has no persisted workflow identity")
        return self.store.cortex_workflow(workflow_id), material

    def _replay_multimodal_workflow(self, execution, source_workflow, material, parent, branch):
        """Replay the persisted M3 session ledger exactly on the merged model."""
        specification = source_workflow["specification"]
        if specification.get("branch_id") != "m3-words-and-images":
            raise SafetyError("Campaign 35 M5 replay source is not the persisted M3 workflow")
        if specification.get("training_job_type") != "model.multimodal_train" or specification.get("multimodal_mode") != "joint":
            raise SafetyError("Campaign 35 M5 replay source is not the captioned-image M3 curriculum")
        sessions = specification.get("sessions")
        if not isinstance(sessions, list):
            raise SafetyError("Campaign 35 M5 replay source has no session ledger")
        events = [event for session in sessions for event in session.get("events", [])]
        observed = {
            "session_count": len(sessions),
            "event_count": len(events),
            "visual_event_count": sum(event.get("type") == "visual" for event in events),
            "text_event_count": sum(event.get("type") == "text" for event in events),
        }
        expected = {key: material.get(key) for key in observed}
        if observed != expected:
            raise SafetyError(
                f"Campaign 35 M5 replay source is a partial M3 ledger: observed={observed}, expected={expected}"
            )
        if any(event.get("type") not in {"visual", "text"} for event in events):
            raise SafetyError("Campaign 35 M5 replay source contains an unexpected event type")
        replay_sessions = deepcopy(sessions)
        for session in replay_sessions:
            source_id = session.get("id")
            if not isinstance(source_id, str) or not source_id:
                raise SafetyError("Campaign 35 M5 replay source contains an invalid session identity")
            session["id"] = f"m5-replay-{source_id}"
        value = self._base_workflow(execution, parent, branch)
        value.update({
            "training_job_type": "model.multimodal_train",
            "multimodal_mode": "joint",
            "starting_checkpoint_role": "authorized_merge",
            "sessions": replay_sessions,
        })
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
