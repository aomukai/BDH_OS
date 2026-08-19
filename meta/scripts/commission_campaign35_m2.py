#!/usr/bin/env python3
"""Register frozen Campaign 35 visual shards and authorize M2 only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mission_hub.campaign_contract import campaign_contract_sha256, validate_campaign_contract
from mission_hub.config import load_config_bundle, machine_id_for_role
from mission_hub.service import MissionHubService
from mission_hub.store import MissionHubStore, utc_now


CAMPAIGN_ID = "campaign-35-multimodal-foundation-v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/mission_hub"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--local-experiences", type=Path, required=True)
    parser.add_argument("--actor", default="operator:campaign35-m2-material")
    args = parser.parse_args()
    bundle = load_config_bundle(args.config)
    store = MissionHubStore(Path(bundle.base["hub"]["state_root"]) / bundle.base["hub"]["database_name"])
    service = MissionHubService(store, bundle)
    material = json.loads(args.manifest.read_text(encoding="utf-8"))
    if material.get("status") != "frozen" or material.get("event_count") != 14_397:
        raise ValueError("M2 material manifest is not the frozen reviewed handoff")
    trainbox = machine_id_for_role(bundle, "trainbox")
    hub = machine_id_for_role(bundle, "mission_hub")

    with store._connect() as db:
        campaign = db.execute("SELECT metadata_json,state FROM campaigns WHERE id=?", (CAMPAIGN_ID,)).fetchone()
    if campaign is None or campaign["state"] != "active":
        raise ValueError("Campaign 35 is not active")
    metadata = json.loads(campaign["metadata_json"])
    execution = metadata["campaign35_execution"]
    contract = validate_campaign_contract(metadata["campaign_contract"], bundle.campaign_modes)
    root_id = metadata["starting_checkpoint_artifact_id"]
    service.materialize_artifact(root_id, machine_id=trainbox, actor=args.actor) if not _at(store, root_id, trainbox) else None

    sessions = []
    registered = []
    for item in material["sessions"]:
        feature_manifest = {
            "schema_version": "ninereeds_visual_features_v1",
            "campaign_id": CAMPAIGN_ID, "session_id": item["session_id"],
            "count": item["unique_feature_count"],
            "format": "npz-no-pickle", "feature_kind": "siglip2_last_hidden_state",
            "feature_width": item["feature_manifest"]["feature_width"],
            "includes_patch_mask": True, "includes_spatial_shapes": True,
            "asset_identity_location": "embedded_in_feature_archive",
        }
        feature_id = store.register_artifact(
            bundle, kind="visual_features", sha256=item["feature_sha256"],
            byte_size=item["feature_bytes"], lifecycle="candidate",
            manifest=feature_manifest, producing_run_id=None,
            machine_id=trainbox, uri=item["feature_path"], actor=args.actor,
        )
        local_experience = args.local_experiences / Path(item["experience_path"]).name
        experience_manifest = {
            "schema_version": "ninereeds_msm_experience_v1",
            "experience_id": item["experience_manifest"]["experience_id"],
            "status": "accepted", "event_count": len(item["experience_manifest"]["events"]),
            "source_assignment_sha256": material["assignment_sha256"],
            "event_identity_location": "immutable_visual_experience_bytes",
        }
        experience = service.ingest_artifact(
            kind="visual_experience", source_path=str(local_experience), lifecycle="candidate",
            manifest=experience_manifest, actor=args.actor,
        )
        service.materialize_artifact(experience["id"], machine_id=trainbox, actor=args.actor)
        local_events = args.local_experiences / Path(item["m2_events_path"]).name
        source_events = json.loads(local_events.read_text(encoding="utf-8"))
        if len(source_events) != item["event_count"]:
            raise ValueError(f"event count changed for {item['session_id']}")
        # Slot IDs and global sequence positions remain in the frozen source
        # ledger.  The executable job schema intentionally receives only the
        # five fields required by the deterministic trainer.
        events = [{key: event[key] for key in (
            "type", "concept", "ordinal", "completion", "asset_sha256",
        )} for event in source_events]
        sessions.append({
            "id": item["session_id"],
            "visual_features_artifact_id": feature_id,
            "visual_experience_artifact_id": experience["id"],
            "ordered_concepts": item["ordered_concepts"],
            "events": events,
            "parameters": {
                "epochs": 1, "learning_rate": 0.0002, "weight_decay": 0.0,
                "seed": 35000000, "ingress_device": "cuda:0", "core_device": "cuda:1",
                "local_files_only": True, "rms_clip": 0.125, "stochastic_rounding": True,
            },
        })
        registered.append({
            "session_id": item["session_id"], "visual_features_artifact_id": feature_id,
            "visual_experience_artifact_id": experience["id"], "event_count": len(events),
        })

    workflow_spec = {
        "campaign_id": CAMPAIGN_ID,
        "branch_id": "m2-images",
        "starting_checkpoint_artifact_id": root_id,
        "evaluation_suite_artifact_id": execution["evaluation_suite_artifact_id"],
        "architecture": "lfm2_5_encoder_230m_frozen__ninereeds_1_2b__lfm2_5_230m_frozen",
        "identity_scope": "identity_and_integrity",
        "training_job_type": "model.multimodal_train",
        "multimodal_mode": "visual",
        "evaluation_policy": "none",
        "sessions": sessions,
        "evaluation_parameters": {"ingress_device": "cuda:0", "core_device": "cuda:1", "max_new_tokens": 128},
        "authorization": {
            "exact_workflow_reviewed": True, "allow_weight_updates": True,
            "allow_checkpoint_promotion": False, "allow_automatic_branch_ranking": False,
            "allow_pipeline_continue_after_completion": False,
        },
    }
    workflow = store.create_cortex_workflow(bundle, workflow_spec, actor=args.actor)
    material_record = {
        "status": "frozen_for_m2",
        "schema_version": material["schema_version"],
        "assignment_sha256": material["assignment_sha256"],
        "event_count": material["event_count"],
        "unique_asset_count": material["unique_asset_count"],
        "session_count": material["session_count"],
        "m2_target": material["m2_target"],
        "m3_target": material["m3_target"],
        "same_assets_and_order": True,
        "registered_sessions": registered,
        "workflow_id": workflow["id"],
        "frozen_at": utc_now(),
    }
    with store.transaction() as db:
        row = db.execute("SELECT metadata_json FROM campaigns WHERE id=?", (CAMPAIGN_ID,)).fetchone()
        current = json.loads(row[0])
        prior = current.get("campaign35_m2_material")
        if prior is not None and prior != material_record:
            # Reruns are allowed only when they resolve to the already-bound workflow.
            if prior.get("workflow_id") != workflow["id"] or prior.get("assignment_sha256") != material["assignment_sha256"]:
                raise ValueError("Campaign 35 M2 material is already frozen with different bytes")
        else:
            current["campaign35_m2_material"] = material_record
            db.execute("UPDATE campaigns SET metadata_json=?,updated_at=? WHERE id=?", (json.dumps(current, sort_keys=True, separators=(",", ":")), utc_now(), CAMPAIGN_ID))
            store._event(db, "campaign", CAMPAIGN_ID, "campaign.m2_visual_material_frozen", args.actor, material_record)
    pipeline = store.request_pipeline_state("running", actor=args.actor)
    print(json.dumps({"workflow_id": workflow["id"], "sessions": len(sessions), "events": material["event_count"], "pipeline": pipeline}, sort_keys=True))
    return 0


def _at(store: MissionHubStore, artifact_id: str, machine_id: str) -> bool:
    try:
        store.artifact_at(artifact_id, machine_id=machine_id)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
