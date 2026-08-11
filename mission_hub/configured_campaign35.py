"""Commission Campaign 35's exact real five-build graph while remaining paused."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import re
from typing import Any

from .campaign_contract import validate_campaign_contract
from .config import ConfigBundle, machine_id_for_role
from .errors import ConflictError, SafetyError
from .jsonutil import canonical_json, content_hash
from .schema import load_schema, validate
from .service import MissionHubService
from .store import MissionHubStore, utc_now
from .retention import RetentionManager


CAMPAIGN_ID = "campaign-35-multimodal-foundation-v1"
VISUAL_CANDIDATE_ATTEMPTS = 4
VISUAL_RETRY_SEED_STRIDE = 10_000_000
VISUAL_IMAGE_CANDIDATES_PER_ATTEMPT = 2
VISUAL_CAPTION_CANDIDATES_PER_IMAGE = 2


class ConfiguredCampaign35:
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle, repo_root: Path):
        self.store, self.bundle = store, bundle
        self.root = repo_root.resolve()
        self.spec_path = self.root / "config/mission_hub/campaigns/campaign35-multimodal-foundation-v1.json"
        self.material_root = self.root / "config/mission_hub/campaign_material/campaign35"
        self.spec = json.loads(self.spec_path.read_text(encoding="utf-8"))
        self.material = json.loads((self.material_root / "manifest.json").read_text(encoding="utf-8"))
        self.service = MissionHubService(store, bundle)
        self.trainbox_machine = machine_id_for_role(bundle, "trainbox")

    def commission(self, *, actor: str) -> dict[str, Any]:
        authorization = self.spec["authorization"]
        required = {
            "mission_preparation", "bounded_stage0_fixture", "full_2500_concept_weight_updates",
            "merge", "healing", "real_five_build_execution", "all_five_terminal_scans",
            "post_campaign_recommendation_fixture",
        }
        if any(authorization.get(key) is not True for key in required):
            raise SafetyError("Campaign 35 is not fully authorized as a real five-build run")
        contract = validate_campaign_contract(self.spec["campaign"]["contract"], self.bundle.campaign_modes)
        if set(contract["branches"]) != {"m1-words", "m2-images", "m3-words-and-images", "m4-merged", "m4-healed"}:
            raise SafetyError("Campaign 35 completion contract does not name all five outputs")

        curriculum = [json.loads(line) for line in (self.material_root / "curriculum.jsonl").read_text(encoding="utf-8").splitlines() if line]
        batches = []
        for batch in self.material["batches"]:
            first, last = batch["ordinal_first"], batch["ordinal_last"]
            concepts = [{"concept": row["concept"], "depends_on": row["depends_on"]} for row in curriculum if first <= row["ordinal"] <= last]
            text_path = self.material_root / batch["text_path"]
            corpus = self.service.ingest_artifact(
                kind="corpus", source_path=str(text_path), lifecycle="candidate",
                manifest={
                    "schema_version": "ninereeds_ordered_training_corpus_v1", "campaign_id": CAMPAIGN_ID,
                    "branch_id": "m1-words", "batch_id": batch["batch_id"], "row_count": batch["text_examples"],
                    "ordered_concepts": concepts, "order_policy": "declared_only", "shuffle_allowed": False,
                    "dependency_order_required": True,
                }, actor=actor,
            )
            batches.append({**batch, "ordered_concepts": concepts, "corpus_artifact_id": corpus["id"]})

        suite_path = self.root / "config/mission_hub/evaluation_suites/campaign33-heldout-acquisition-v1.json"
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        suite_artifact = self.service.ingest_artifact(
            kind="evaluation_suite", source_path=str(suite_path), lifecycle="candidate",
            manifest={"schema_version": "ninereeds_campaign35_evaluation_suite_v1", "suite_id": suite["suite_id"], "case_count": len(suite["cases"]), "basis": ["behavioral_chat", "mri_activation"], "loss_role": "telemetry_only"},
            actor=actor,
        )
        execution = {
            "schema_version": "ninereeds_campaign35_execution_v1", "status": "authorized_paused",
            "material_manifest_sha256": self.material["files"]["curriculum.jsonl"],
            "evaluation_suite_artifact_id": suite_artifact["id"], "batches": batches,
            "required_outputs": ["m1-words", "m2-images", "m3-words-and-images", "m4-merged", "m4-healed"],
            "required_evidence": ["behavioral_chat", "mri_activation", "atlas", "three_d_map", "cross_modal_evaluation", "hashes", "logs", "receipts"],
            "recommendation_fixture_required": True,
        }
        now = utc_now()
        with self.store.transaction() as db:
            row = db.execute("SELECT metadata_json,state FROM campaigns WHERE id=?", (CAMPAIGN_ID,)).fetchone()
            if row is None or row["state"] != "active":
                raise SafetyError("Campaign 35 must exist and be active before commissioning")
            metadata = json.loads(row["metadata_json"])
            existing = metadata.get("campaign35_execution")
            # Upgrade the brief preparation-era execution record to the exact
            # scientific completion contract without changing any material ID.
            if isinstance(existing, dict) and "cross_modal_evaluation" not in existing.get("required_evidence", []):
                existing = {**existing, "required_evidence": execution["required_evidence"]}
            if existing is not None and existing != execution:
                trained = db.execute(
                    "SELECT COUNT(*) FROM jobs WHERE campaign_id=? AND job_type IN ('model.train','model.multimodal_train') AND status='succeeded'",
                    (CAMPAIGN_ID,),
                ).fetchone()[0]
                if trained:
                    raise ConflictError("Campaign 35 exact material cannot change after a successful weight update")
                self.store._event(db, "campaign", CAMPAIGN_ID, "campaign.pretraining_material_repaired", actor, {
                    "old_material_manifest_sha256": existing.get("material_manifest_sha256"),
                    "new_material_manifest_sha256": execution["material_manifest_sha256"],
                    "reason": "completion_bound_and_structural_speaker_marker_repair_before_first_weight_update",
                })
            metadata.update({
                "campaign_contract": contract, "authorization": authorization,
                "launch_stage": self.spec["launch_stage"], "campaign35_execution": execution,
            })
            storage = self.spec["storage"]
            metadata["storage"] = {
                "required_free_bytes": storage["required_free_bytes"],
                "estimated_build_count": storage["estimated_build_count"],
                "preflight_policy": storage["preflight_policy"],
            }
            if metadata.get("storage_preflight", {}).get("required_free_bytes") != storage["required_free_bytes"]:
                metadata.pop("storage_preflight", None)
            db.execute("UPDATE campaigns SET metadata_json=?,updated_at=? WHERE id=?", (canonical_json(metadata), now, CAMPAIGN_ID))
            self.store._event(db, "campaign", CAMPAIGN_ID, "campaign.real_five_build_authorized", actor, {"outputs": execution["required_outputs"], "batch_count": len(batches)})

        RetentionManager(self.store, self.bundle).prepare_campaign(
            CAMPAIGN_ID, required_free_bytes=self.spec["storage"]["required_free_bytes"],
            machine_id=self.trainbox_machine, actor=actor,
        )

        root_job = self.store.create_job(
            self.bundle, job_type="model.initialize", input_payload={"seed": 35000000, "local_files_only": True},
            idempotency_key="campaign35:neutral-root:v1", created_by=actor, campaign_id=CAMPAIGN_ID,
            requested_machine_id=self.trainbox_machine, approved=True,
        )
        with self.store._connect() as db:
            rows = db.execute(
                "SELECT id,specification_json FROM visual_workflows WHERE campaign_id=?",
                (CAMPAIGN_ID,),
            ).fetchall()
        existing_visual = {}
        for row in rows:
            value = json.loads(row["specification_json"])
            if value.get("plan", {}).get("authority", {}).get("exact_material") is True:
                existing_visual[value["plan"]["plan_id"]] = (row["id"], value)
        workflows = []
        for batch in batches:
            visual_rows = [json.loads(line) for line in (self.material_root / batch["visual_path"]).read_text(encoding="utf-8").splitlines() if line]
            plan = {
                "plan_id": f"campaign35-{batch['batch_id']}-visual-v1",
                "teaching_goal": "Create the exact image-only counterpart to the matched text exposures.",
                "canonical_text": [row["canonical_caption"] for row in visual_rows],
                "items": [{
                    "item_id": row["item_id"], "prompt": row["prompt"], "canonical_caption": row["canonical_caption"],
                    "seeds": [
                        row["seed"] + attempt * VISUAL_RETRY_SEED_STRIDE
                        for attempt in range(VISUAL_CANDIDATE_ATTEMPTS)
                    ],
                    "width": 512, "height": 512, "steps": 4, "guidance_scale": 3.5,
                } for row in visual_rows],
                "authority": {"campaign_id": CAMPAIGN_ID, "stage": "real-material", "exact_material": True, "weight_updates_authorized": True, "shadow_admission": False},
            }
            events = []
            for row in visual_rows:
                events.extend([
                    {"type": "observe_image", "asset_item_id": row["item_id"], "concept": row["concept"], "ordinal": row["ordinal"], "example_index": row["example_index"]},
                    {"type": "hear_or_read_text", "text": row["canonical_caption"], "concept": row["concept"], "ordinal": row["ordinal"], "example_index": row["example_index"]},
                ])
            specification = {
                "campaign_id": CAMPAIGN_ID, "plan": plan, "experience_events": events,
                "limits": {
                    "max_pack_items": len(visual_rows),
                    "max_candidates_per_item": VISUAL_CANDIDATE_ATTEMPTS,
                    "image_candidates_per_attempt": VISUAL_IMAGE_CANDIDATES_PER_ATTEMPT,
                    "caption_candidates_per_image": VISUAL_CAPTION_CANDIDATES_PER_IMAGE,
                    "max_width": 512, "max_height": 512, "max_generation_steps": 4,
                    "max_new_tokens": 512, "offload_profile": "sequential",
                },
            }
            existing_workflow = existing_visual.get(plan["plan_id"])
            if existing_workflow:
                previous_specification = copy.deepcopy(specification)
                previous_specification["limits"].pop("image_candidates_per_attempt")
                previous_specification["limits"].pop("caption_candidates_per_image")
                legacy_specification = copy.deepcopy(specification)
                for legacy_item in legacy_specification["plan"]["items"]:
                    legacy_item["seeds"] = legacy_item["seeds"][:1]
                legacy_specification["limits"]["max_candidates_per_item"] = 1
                previous_legacy_specification = copy.deepcopy(legacy_specification)
                previous_legacy_specification["limits"].pop("image_candidates_per_attempt")
                previous_legacy_specification["limits"].pop("caption_candidates_per_image")
                compatible = (
                    specification, previous_specification,
                    legacy_specification, previous_legacy_specification,
                )
                if existing_workflow[1] not in compatible:
                    raise ConflictError(f"Campaign 35 exact visual workflow changed: {plan['plan_id']}")
                workflows.append(self.store.visual_workflow(existing_workflow[0]))
            else:
                workflows.append(self.store.create_visual_workflow(self.bundle, specification, actor=actor))
        return {"campaign_id": CAMPAIGN_ID, "root_job_id": root_job["id"], "visual_workflows": len(workflows), "batches": len(batches), "pipeline_state": self.store.pipeline_control()}

    def recover_visual_batches(
        self, *, actor: str, authorization_reference: str,
        expected_exact_restarts: int, expected_seed_replacements: int,
        seed_offset: int = 100_000_000,
    ) -> dict[str, Any]:
        """Create audited successors for the exact authorized failed frontier.

        Control-plane stops are restarted without changing the specification.
        A review-exhausted batch receives only deterministic replacement seeds;
        prompts, captions, concepts, dimensions, generation settings, limits,
        and the stable Campaign 35 batch plan ID remain unchanged.
        """
        authorization_reference = authorization_reference.strip()
        if not authorization_reference or len(authorization_reference.encode("utf-8")) > 4096:
            raise ValueError("visual recovery requires a bounded authorization reference")
        if expected_exact_restarts < 0 or expected_seed_replacements < 0:
            raise ValueError("expected recovery counts must be non-negative")
        if seed_offset <= 0:
            raise ValueError("replacement seed offset must be positive")
        control = self.store.pipeline_control()
        if (
            control["desired_state"] != "paused"
            or control["applied_state"] != "paused"
            or control["effective_state"] != "paused"
            or control["live_runs"]
        ):
            raise SafetyError("Campaign 35 visual recovery requires a paused, globally quiet boundary")
        if self.store.active_config()["sha256"] != self.bundle.sha256:
            raise ConflictError("loaded configuration is not the active configuration")

        with self.store._connect() as db:
            campaign = db.execute(
                "SELECT state,metadata_json FROM campaigns WHERE id=?", (CAMPAIGN_ID,),
            ).fetchone()
            rows = db.execute(
                "SELECT id FROM visual_workflows WHERE campaign_id=? ORDER BY created_at,id",
                (CAMPAIGN_ID,),
            ).fetchall()
        if campaign is None or campaign["state"] != "active":
            raise SafetyError("Campaign 35 visual recovery requires the active Campaign 35 campaign")
        execution = json.loads(campaign["metadata_json"]).get("campaign35_execution")
        if not isinstance(execution, dict) or execution.get("status") not in {"authorized_paused", "running"}:
            raise SafetyError("Campaign 35 visual execution is not recoverable")

        all_workflows = [self.store.visual_workflow(row["id"]) for row in rows]
        exact_workflows = [
            item for item in all_workflows
            if item["specification"].get("plan", {}).get("authority", {}).get("exact_material") is True
        ]
        latest: dict[str, dict[str, Any]] = {}
        for workflow in exact_workflows:
            plan_id = workflow["specification"]["plan"]["plan_id"]
            latest[plan_id] = workflow
        expected_plan_ids = {
            f"campaign35-{batch['batch_id']}-visual-v1" for batch in execution["batches"]
        }
        if set(latest) != expected_plan_ids:
            raise SafetyError("Campaign 35 visual recovery requires exactly one known frontier for every commissioned batch")

        candidates: list[dict[str, Any]] = []
        for plan_id in sorted(latest):
            workflow = latest[plan_id]
            if workflow["status"] != "failed":
                continue
            with self.store._connect() as db:
                event = db.execute(
                    """SELECT payload_json FROM events
                       WHERE entity_type='visual_workflow' AND entity_id=?
                         AND event_type='visual_workflow.failed'
                       ORDER BY sequence DESC LIMIT 1""",
                    (workflow["id"],),
                ).fetchone()
            if event is None:
                raise SafetyError(f"failed visual workflow lacks durable failure evidence: {workflow['id']}")
            reason = json.loads(event["payload_json"]).get("reason")
            blocked_match = re.fullmatch(r"(plan|generate(?:/\d{4})?):blocked", str(reason))
            if blocked_match:
                failed_stage = blocked_match.group(1)
                failed_jobs = [
                    job for job in workflow["jobs"]
                    if job.get("stage_key") == failed_stage and job.get("status") == "blocked"
                ]
                if len(failed_jobs) != 1:
                    raise SafetyError(f"control-plane stop evidence is inconsistent: {workflow['id']}")
                with self.store._connect() as db:
                    run_count = db.execute(
                        "SELECT COUNT(*) FROM runs WHERE job_id=?", (failed_jobs[0]["id"],),
                    ).fetchone()[0]
                    queue_expired = db.execute(
                        """SELECT 1 FROM events WHERE entity_type='job' AND entity_id=?
                           AND event_type='job.queue_age_exceeded' LIMIT 1""",
                        (failed_jobs[0]["id"],),
                    ).fetchone()
                if run_count:
                    raise SafetyError(f"unchanged restart is limited to a never-run blocked frontier: {workflow['id']}")
                if queue_expired is None:
                    raise SafetyError(f"blocked visual frontier lacks queue-expiry evidence: {workflow['id']}")
                mode = "exact_restart"
                specification = copy.deepcopy(workflow["specification"])
            elif reason == "independent review found no usable candidate":
                mode = "replacement_seeds"
                specification = copy.deepcopy(workflow["specification"])
                for item in specification["plan"].get("items", []):
                    seeds = item.get("seeds", [])
                    if not seeds:
                        raise SafetyError(f"replacement batch has no declared seed: {workflow['id']}")
                    replaced = [seed + seed_offset for seed in seeds]
                    if any(seed > 2_147_483_647 for seed in replaced):
                        raise SafetyError("replacement seed exceeds the commissioned provider contract")
                    item["seeds"] = replaced
            else:
                raise SafetyError(f"unauthorized visual recovery reason: {reason!r}")
            candidates.append({
                "predecessor": workflow, "mode": mode, "reason": reason,
                "specification": specification,
                "old_plan_sha256": content_hash(workflow["specification"]["plan"]),
                "new_plan_sha256": content_hash(specification["plan"]),
            })

        exact_count = sum(item["mode"] == "exact_restart" for item in candidates)
        replacement_count = sum(item["mode"] == "replacement_seeds" for item in candidates)
        if (exact_count, replacement_count) != (expected_exact_restarts, expected_seed_replacements):
            raise SafetyError(
                "visual recovery frontier changed: "
                f"found {exact_count} exact restarts and {replacement_count} seed replacements; "
                f"authorized {expected_exact_restarts} and {expected_seed_replacements}"
            )

        created = []
        for item in candidates:
            successor = self.store.create_visual_workflow(
                self.bundle, item["specification"], actor=actor,
            )
            evidence = {
                "authorization_reference": authorization_reference,
                "predecessor_workflow_id": item["predecessor"]["id"],
                "successor_workflow_id": successor["id"],
                "plan_id": successor["specification"]["plan"]["plan_id"],
                "mode": item["mode"], "failure_reason": item["reason"],
                "old_plan_sha256": item["old_plan_sha256"],
                "new_plan_sha256": item["new_plan_sha256"],
                "seed_offset": seed_offset if item["mode"] == "replacement_seeds" else 0,
            }
            with self.store.transaction() as db:
                self.store._event(
                    db, "visual_workflow", successor["id"],
                    "visual_workflow.authorized_successor", actor, evidence,
                )
                self.store._event(
                    db, "campaign", CAMPAIGN_ID,
                    "campaign.visual_workflow_successor_authorized", actor, evidence,
                )
            created.append(evidence)
        return {
            "campaign_id": CAMPAIGN_ID,
            "authorization_reference": authorization_reference,
            "exact_restarts": exact_count,
            "seed_replacements": replacement_count,
            "successors": created,
            "pipeline_state": self.store.pipeline_control(),
        }

    def resume_queue_expired_visual_frontiers(
        self, *, actor: str, reason: str, expected_count: int,
    ) -> dict[str, Any]:
        """Immediately requeue exact never-run visual workflow frontiers.

        Queue expiry is a control-plane timer, not execution evidence.  This
        path therefore preserves the workflow, job, input hash, plan, seeds,
        and every successful predecessor instead of creating a replacement.
        """
        reason = reason.strip()
        if not reason or len(reason.encode("utf-8")) > 4096:
            raise ValueError("visual queue-expiry recovery requires a bounded reason")
        if expected_count < 1:
            raise ValueError("visual queue-expiry recovery requires a positive expected count")
        control = self.store.pipeline_control()
        if (
            control["desired_state"] != "paused"
            or control["applied_state"] != "paused"
            or control["effective_state"] != "paused"
            or control["live_runs"]
        ):
            raise SafetyError("visual queue-expiry recovery requires a paused, globally quiet boundary")
        active = self.store.active_config()
        if active["sha256"] != self.bundle.sha256:
            raise ConflictError("loaded configuration is not active")
        now = utc_now()
        with self.store.transaction() as db:
            campaign = db.execute(
                "SELECT state,metadata_json FROM campaigns WHERE id=?", (CAMPAIGN_ID,),
            ).fetchone()
            if campaign is None or campaign["state"] != "active":
                raise SafetyError("visual queue-expiry recovery requires active Campaign 35")
            execution = json.loads(campaign["metadata_json"]).get("campaign35_execution")
            if not isinstance(execution, dict) or execution.get("status") not in {
                "authorized_paused", "running",
            }:
                raise SafetyError("Campaign 35 visual execution is not recoverable")
            rows = db.execute(
                "SELECT * FROM visual_workflows WHERE campaign_id=? ORDER BY created_at,id",
                (CAMPAIGN_ID,),
            ).fetchall()
            latest: dict[str, Any] = {}
            for workflow in rows:
                specification = json.loads(workflow["specification_json"])
                plan = specification.get("plan", {})
                if plan.get("authority", {}).get("exact_material") is True:
                    latest[plan.get("plan_id") or workflow["id"]] = (workflow, specification)
            expected_plan_ids = {
                f"campaign35-{batch['batch_id']}-visual-v1" for batch in execution["batches"]
            }
            if set(latest) != expected_plan_ids:
                raise SafetyError("Campaign 35 visual recovery does not own every exact batch frontier")

            recoveries: list[dict[str, Any]] = []
            for plan_id in sorted(latest):
                workflow, specification = latest[plan_id]
                if workflow["status"] != "failed":
                    continue
                failure = db.execute(
                    """SELECT payload_json FROM events
                       WHERE entity_type='visual_workflow' AND entity_id=?
                         AND event_type='visual_workflow.failed'
                       ORDER BY sequence DESC LIMIT 1""",
                    (workflow["id"],),
                ).fetchone()
                failure_reason = None if failure is None else json.loads(failure[0]).get("reason")
                match = re.fullmatch(r"(plan|generate(?:/\d{4})?):blocked", str(failure_reason))
                if match is None:
                    raise SafetyError(f"latest visual failure is not queue-expiry-only: {workflow['id']}")
                stage_key = match.group(1)
                linked = db.execute(
                    """SELECT w.stage_key,j.* FROM visual_workflow_jobs w
                       JOIN jobs j ON j.id=w.job_id WHERE w.workflow_id=?
                       ORDER BY w.created_at,w.stage_key""",
                    (workflow["id"],),
                ).fetchall()
                blocked = [
                    job for job in linked
                    if job["stage_key"] == stage_key and job["status"] == "blocked"
                ]
                if len(blocked) != 1 or any(
                    job["id"] != blocked[0]["id"] and job["status"] != "succeeded"
                    for job in linked
                ):
                    raise SafetyError(f"visual queue-expiry frontier is not otherwise successful: {workflow['id']}")
                job = blocked[0]
                if db.execute("SELECT 1 FROM runs WHERE job_id=?", (job["id"],)).fetchone() is not None:
                    raise SafetyError(f"queue-expired visual frontier has run history: {job['id']}")
                if db.execute(
                    """SELECT 1 FROM events WHERE entity_type='job' AND entity_id=?
                       AND event_type='job.queue_age_exceeded' LIMIT 1""",
                    (job["id"],),
                ).fetchone() is None:
                    raise SafetyError(f"blocked visual frontier lacks queue-expiry evidence: {job['id']}")
                definition = self.bundle.jobs.get(job["job_type"])
                if definition is None or job["job_version"] != definition["version"]:
                    raise SafetyError("visual frontier job definition changed")
                payload = json.loads(job["input_json"])
                if content_hash(payload) != job["input_sha256"]:
                    raise SafetyError("visual frontier input hash is inconsistent")
                errors = validate(
                    payload,
                    load_schema(self.bundle.root.parent.parent, definition["input_schema"]),
                )
                if errors:
                    raise SafetyError("visual frontier is invalid under active configuration: " + "; ".join(errors))
                previous_config = job["config_snapshot_id"]
                db.execute(
                    """UPDATE jobs SET status='queued',config_snapshot_id=?,available_at=NULL,
                              updated_at=? WHERE id=?""",
                    (active["id"], now, job["id"]),
                )
                db.execute(
                    """UPDATE visual_workflows SET status='active',config_snapshot_id=?,updated_at=?
                       WHERE id=?""",
                    (active["id"], now, workflow["id"]),
                )
                evidence = {
                    "reason": reason,
                    "plan_id": plan_id,
                    "stage_key": stage_key,
                    "job_id": job["id"],
                    "input_sha256": job["input_sha256"],
                    "previous_config_snapshot_id": previous_config,
                    "active_config_snapshot_id": active["id"],
                    "retry_delay_seconds": 0,
                }
                self.store._event(
                    db, "job", job["id"], "job.requeued_after_queue_age_recovery", actor, evidence,
                )
                self.store._event(
                    db, "visual_workflow", workflow["id"],
                    "visual_workflow.reopened_after_queue_age_recovery", actor, evidence,
                )
                recoveries.append(evidence)
            if len(recoveries) != expected_count:
                raise SafetyError(
                    f"visual queue-expiry frontier changed: found {len(recoveries)}, expected {expected_count}"
                )
        return {
            "campaign_id": CAMPAIGN_ID,
            "recovered_count": len(recoveries),
            "recoveries": recoveries,
            "pipeline_state": self.store.pipeline_control(),
        }

    def recommission_visual_workflow(
        self, workflow_id: str, *, actor: str, authority_reference: str,
        seed_offset: int = 100_000_000,
        candidate_attempt_budget: int | None = None,
    ) -> dict[str, Any] | None:
        """Create one audited successor under Sol's standing editorial authority."""
        authority_reference = authority_reference.strip()
        if not authority_reference or seed_offset <= 0:
            raise ValueError("visual recommission requires authority evidence and a positive seed offset")
        if candidate_attempt_budget is not None and candidate_attempt_budget <= 0:
            raise ValueError("candidate attempt budget must be positive")
        predecessor = self.store.visual_workflow(workflow_id)
        if predecessor["campaign_id"] != CAMPAIGN_ID or predecessor["status"] != "failed":
            raise SafetyError("visual recommission requires a failed Campaign 35 workflow")
        plan = predecessor["specification"].get("plan", {})
        if plan.get("authority", {}).get("exact_material") is not True:
            raise SafetyError("visual recommission requires exact commissioned material")
        with self.store._connect() as db:
            failure = db.execute(
                """SELECT payload_json FROM events WHERE entity_type='visual_workflow' AND entity_id=?
                   AND event_type='visual_workflow.failed' ORDER BY sequence DESC LIMIT 1""",
                (workflow_id,),
            ).fetchone()
            peers = db.execute(
                "SELECT id,status,specification_json FROM visual_workflows WHERE campaign_id=? ORDER BY created_at,id",
                (predecessor["campaign_id"],),
            ).fetchall()
            review_failures = {
                row["entity_id"]
                for row in db.execute(
                    """SELECT entity_id,payload_json FROM events
                       WHERE entity_type='visual_workflow' AND event_type='visual_workflow.failed'""",
                ).fetchall()
                if json.loads(row["payload_json"]).get("reason") == "independent review found no usable candidate"
            }
        if failure is None or json.loads(failure["payload_json"]).get("reason") != "independent review found no usable candidate":
            raise SafetyError("visual recommission requires a preserved review-exhaustion failure")
        plan_id = plan.get("plan_id")
        latest = None
        for peer in peers:
            if json.loads(peer["specification_json"]).get("plan", {}).get("plan_id") == plan_id:
                latest = peer
        if latest is None or latest["id"] != workflow_id:
            raise ConflictError("visual workflow already has a newer successor")

        if candidate_attempt_budget is not None:
            attempts_used = 0
            for peer in peers:
                peer_specification = json.loads(peer["specification_json"])
                if (
                    peer["id"] not in review_failures
                    or peer_specification.get("plan", {}).get("plan_id") != plan_id
                ):
                    continue
                attempts_used += max(
                    (len(item.get("seeds", [])) for item in peer_specification["plan"].get("items", [])),
                    default=0,
                )
            if attempts_used >= candidate_attempt_budget:
                return None

        specification = copy.deepcopy(predecessor["specification"])
        specification["limits"].update({
            "image_candidates_per_attempt": VISUAL_IMAGE_CANDIDATES_PER_ATTEMPT,
            "caption_candidates_per_image": VISUAL_CAPTION_CANDIDATES_PER_IMAGE,
        })
        for item in specification["plan"].get("items", []):
            replacement = [seed + seed_offset for seed in item.get("seeds", [])]
            if not replacement or any(seed > 2_147_483_647 for seed in replacement):
                raise SafetyError("replacement visual seed is outside the provider contract")
            item["seeds"] = replacement
        successor = self.store.create_visual_workflow(self.bundle, specification, actor=actor)
        evidence = {
            "authorization_reference": authority_reference,
            "predecessor_workflow_id": workflow_id,
            "successor_workflow_id": successor["id"],
            "plan_id": plan_id,
            "mode": "replacement_seeds",
            "failure_reason": "independent review found no usable candidate",
            "old_plan_sha256": content_hash(predecessor["specification"]["plan"]),
            "new_plan_sha256": content_hash(specification["plan"]),
            "seed_offset": seed_offset,
            "candidate_attempt_budget": candidate_attempt_budget,
        }
        with self.store.transaction() as db:
            self.store._event(db, "visual_workflow", successor["id"], "visual_workflow.authorized_successor", actor, evidence)
            self.store._event(db, "campaign", CAMPAIGN_ID, "campaign.visual_workflow_successor_authorized", actor, evidence)
        return evidence
