"""Commission Campaign 35's exact real five-build graph while remaining paused."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .campaign_contract import validate_campaign_contract
from .config import ConfigBundle
from .errors import ConflictError, SafetyError
from .jsonutil import canonical_json
from .service import MissionHubService
from .store import MissionHubStore, utc_now
from .retention import RetentionManager


CAMPAIGN_ID = "campaign-35-multimodal-foundation-v1"


class ConfiguredCampaign35:
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle, repo_root: Path):
        self.store, self.bundle = store, bundle
        self.root = repo_root.resolve()
        self.spec_path = self.root / "config/mission_hub/campaigns/campaign35-multimodal-foundation-v1.json"
        self.material_root = self.root / "config/mission_hub/campaign_material/campaign35"
        self.spec = json.loads(self.spec_path.read_text(encoding="utf-8"))
        self.material = json.loads((self.material_root / "manifest.json").read_text(encoding="utf-8"))
        self.service = MissionHubService(store, bundle)

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
            "required_evidence": ["behavioral_chat", "mri_activation", "atlas", "three_d_map", "hashes", "logs", "receipts"],
            "recommendation_fixture_required": True,
        }
        now = utc_now()
        with self.store.transaction() as db:
            row = db.execute("SELECT metadata_json,state FROM campaigns WHERE id=?", (CAMPAIGN_ID,)).fetchone()
            if row is None or row["state"] != "active":
                raise SafetyError("Campaign 35 must exist and be active before commissioning")
            metadata = json.loads(row["metadata_json"])
            existing = metadata.get("campaign35_execution")
            if existing is not None and existing != execution:
                raise ConflictError("Campaign 35 was already commissioned with different exact material")
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
            machine_id="trainbox", actor=actor,
        )

        root_job = self.store.create_job(
            self.bundle, job_type="model.initialize", input_payload={"seed": 35000000, "local_files_only": True},
            idempotency_key="campaign35:neutral-root:v1", created_by=actor, campaign_id=CAMPAIGN_ID,
            requested_machine_id="trainbox", approved=True,
        )
        workflows = []
        for batch in batches:
            visual_rows = [json.loads(line) for line in (self.material_root / batch["visual_path"]).read_text(encoding="utf-8").splitlines() if line]
            plan = {
                "plan_id": f"campaign35-{batch['batch_id']}-visual-v1",
                "teaching_goal": "Create the exact image-only counterpart to the matched text exposures.",
                "canonical_text": [row["canonical_caption"] for row in visual_rows],
                "items": [{
                    "item_id": row["item_id"], "prompt": row["prompt"], "canonical_caption": row["canonical_caption"],
                    "seeds": [row["seed"]], "width": 512, "height": 512, "steps": 4, "guidance_scale": 3.5,
                } for row in visual_rows],
                "authority": {"campaign_id": CAMPAIGN_ID, "stage": "real-material", "exact_material": True, "weight_updates_authorized": True, "shadow_admission": False},
            }
            events = []
            for row in visual_rows:
                events.extend([
                    {"type": "observe_image", "asset_item_id": row["item_id"], "concept": row["concept"], "ordinal": row["ordinal"], "example_index": row["example_index"]},
                    {"type": "hear_or_read_text", "text": row["canonical_caption"], "concept": row["concept"], "ordinal": row["ordinal"], "example_index": row["example_index"]},
                ])
            workflows.append(self.store.create_visual_workflow(self.bundle, {
                "campaign_id": CAMPAIGN_ID, "plan": plan, "experience_events": events,
                "limits": {"max_pack_items": len(visual_rows), "max_candidates_per_item": 1, "max_width": 512, "max_height": 512, "max_generation_steps": 4, "max_new_tokens": 512, "offload_profile": "sequential"},
            }, actor=actor))
        return {"campaign_id": CAMPAIGN_ID, "root_job_id": root_job["id"], "visual_workflows": len(workflows), "batches": len(batches), "pipeline_state": self.store.pipeline_control()}
