#!/usr/bin/env python3
"""Register frozen visual-birth shards and authorize the 1.2B bootstrap workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mission_hub.campaign_contract import campaign_contract_sha256, validate_campaign_contract
from mission_hub.config import load_config_bundle, machine_id_for_role
from mission_hub.service import MissionHubService
from mission_hub.store import MissionHubStore, utc_now


CAMPAIGN_ID = "foundation-visual-3022-v1"
EXPECTED_MANIFEST = "e1d760e264717d05676076429a2e13e46cd05da6d8376169feaad579121ac2fb"


def one_job_artifact(store: MissionHubStore, job_id: str, kind: str) -> dict:
    _, artifacts, _ = store.workflow_job_artifacts(job_id)
    selected = [item for item in artifacts if item["kind"] == kind]
    if len(selected) != 1:
        raise ValueError(f"job {job_id} does not have exactly one {kind}")
    return selected[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/mission_hub"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--local-output", type=Path, required=True)
    parser.add_argument("--evaluation-suite", type=Path, required=True)
    parser.add_argument("--actor", default="operator:foundation-visual-3022")
    args = parser.parse_args()

    bundle = load_config_bundle(args.config)
    store = MissionHubStore(Path(bundle.base["hub"]["state_root"]) / bundle.base["hub"]["database_name"])
    service = MissionHubService(store, bundle)
    material = json.loads(args.manifest.read_text(encoding="utf-8"))
    required = {
        "status": "frozen", "input_manifest_sha256": EXPECTED_MANIFEST,
        "contract_count": 3022, "event_count": 30220, "session_count": 31,
        "target": "one_positive_lexical_item", "order_policy": "declared_only",
        "shuffle_allowed": False,
    }
    if any(material.get(key) != value for key, value in required.items()):
        raise ValueError("visual foundation material is not the exact frozen 3,022 × 10 handoff")

    with store._connect() as db:
        campaign = db.execute(
            "SELECT state,metadata_json FROM campaigns WHERE id=?", (CAMPAIGN_ID,),
        ).fetchone()
        root_job = db.execute(
            """SELECT id,status FROM jobs
               WHERE idempotency_key LIKE 'foundation-visual-3022:neutral-root:v%'
                 AND status='succeeded'
               ORDER BY updated_at DESC LIMIT 1""",
        ).fetchone()
    if campaign is None or campaign["state"] != "active":
        raise ValueError("visual foundation campaign is not active")
    if root_job is None:
        raise RuntimeError("neutral 1.2B root is not ready")
    metadata = json.loads(campaign["metadata_json"])
    contract = validate_campaign_contract(metadata["campaign_contract"], bundle.campaign_modes)
    if contract["mode"] != "bootstrap":
        raise ValueError("visual foundation must remain a bootstrap campaign")
    root = one_job_artifact(store, root_job["id"], "checkpoint")
    trainbox = machine_id_for_role(bundle, "trainbox")

    with store.transaction() as db:
        row = db.execute("SELECT metadata_json FROM campaigns WHERE id=?", (CAMPAIGN_ID,)).fetchone()
        current = json.loads(row[0])
        bound = current.get("starting_checkpoint_artifact_id")
        if bound not in {None, root["id"]}:
            raise ValueError("campaign is already bound to a different neutral root")
        if bound is None:
            current["starting_checkpoint_artifact_id"] = root["id"]
            db.execute(
                "UPDATE campaigns SET metadata_json=?,updated_at=? WHERE id=?",
                (json.dumps(current, sort_keys=True, separators=(",", ":")), utc_now(), CAMPAIGN_ID),
            )
            store._event(db, "campaign", CAMPAIGN_ID, "campaign.neutral_root_bound", args.actor, {
                "checkpoint_artifact_id": root["id"], "checkpoint_sha256": root["sha256"],
            })

    suite = service.ingest_artifact(
        kind="evaluation_suite", source_path=str(args.evaluation_suite), lifecycle="candidate",
        manifest={
            "purpose": "required workflow fixture; behavioral language evaluation intentionally disabled",
            "campaign_id": CAMPAIGN_ID,
        }, actor=args.actor,
    )
    try:
        store.artifact_at(suite["id"], machine_id=trainbox)
    except Exception:
        service.materialize_artifact(suite["id"], machine_id=trainbox, actor=args.actor)

    sessions = []
    registrations = []
    for item in material["sessions"]:
        feature_path = Path(item["feature_path"])
        feature_id = store.register_artifact(
            bundle, kind="visual_features", sha256=item["feature_sha256"],
            byte_size=item["feature_bytes"], lifecycle="candidate",
            manifest=item["feature_manifest"], producing_run_id=None,
            machine_id=trainbox, uri=str(feature_path), actor=args.actor,
        )
        local_experience = args.local_output / Path(item["experience_path"]).name
        if not local_experience.is_file():
            raise ValueError(f"missing local experience receipt: {local_experience}")
        experience = service.ingest_artifact(
            kind="visual_experience", source_path=str(local_experience), lifecycle="candidate",
            manifest={
                "schema_version": "ninereeds_msm_experience_v1",
                "experience_id": item["session_id"], "status": "accepted",
                "event_count": item["event_count"],
                "input_manifest_sha256": EXPECTED_MANIFEST,
                "supervision": "one_positive_lexical_target_per_image",
                "event_identity_location": "immutable_visual_experience_bytes",
            }, actor=args.actor,
        )
        try:
            store.artifact_at(experience["id"], machine_id=trainbox)
        except Exception:
            service.materialize_artifact(experience["id"], machine_id=trainbox, actor=args.actor)
        events_path = args.local_output / Path(item["events_path"]).name
        events = json.loads(events_path.read_text(encoding="utf-8"))
        if len(events) != item["event_count"]:
            raise ValueError(f"event count changed for {item['session_id']}")
        sessions.append({
            "id": item["session_id"],
            "visual_features_artifact_id": feature_id,
            "visual_experience_artifact_id": experience["id"],
            "ordered_concepts": item["ordered_concepts"],
            "events": events,
            "parameters": {
                "epochs": 1, "learning_rate": 0.0002, "weight_decay": 0.0,
                "seed": 3603022, "ingress_device": "cuda:0", "core_device": "cuda:1",
                "local_files_only": True, "rms_clip": 0.125,
                "stochastic_rounding": True,
            },
        })
        registrations.append({
            "session_id": item["session_id"], "events": item["event_count"],
            "visual_features_artifact_id": feature_id,
            "visual_experience_artifact_id": experience["id"],
        })

    workflow_specification = {
        "campaign_id": CAMPAIGN_ID,
        "branch_id": None,
        "starting_checkpoint_artifact_id": root["id"],
        "evaluation_suite_artifact_id": suite["id"],
        "architecture": "lfm2_5_encoder_230m_frozen__ninereeds_1_2b__lfm2_5_230m_frozen",
        "identity_scope": "excluded",
        "training_job_type": "model.multimodal_train",
        "multimodal_mode": "visual",
        "evaluation_policy": "none",
        "sessions": sessions,
        "evaluation_parameters": {
            "ingress_device": "cuda:0", "core_device": "cuda:1", "max_new_tokens": 24,
        },
        "authorization": {
            "exact_workflow_reviewed": True,
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_automatic_branch_ranking": False,
            "allow_pipeline_continue_after_completion": False,
        },
    }
    workflow = store.create_cortex_workflow(bundle, workflow_specification, actor=args.actor)
    material_binding = {
        "schema_version": material["schema_version"],
        "status": "frozen_for_training",
        "input_manifest_sha256": EXPECTED_MANIFEST,
        "event_count": 30220, "contract_count": 3022,
        "session_count": len(sessions), "registrations": registrations,
        "workflow_id": workflow["id"],
        "campaign_contract_sha256": campaign_contract_sha256(contract),
        "bound_at": utc_now(),
    }
    with store.transaction() as db:
        row = db.execute("SELECT metadata_json FROM campaigns WHERE id=?", (CAMPAIGN_ID,)).fetchone()
        current = json.loads(row[0])
        prior = current.get("foundation_visual_material")
        if prior is not None and (
            prior.get("workflow_id") != workflow["id"]
            or prior.get("input_manifest_sha256") != EXPECTED_MANIFEST
        ):
            raise ValueError("campaign material is already frozen to different bytes")
        if prior is None:
            current["foundation_visual_material"] = material_binding
            db.execute(
                "UPDATE campaigns SET metadata_json=?,updated_at=? WHERE id=?",
                (json.dumps(current, sort_keys=True, separators=(",", ":")), utc_now(), CAMPAIGN_ID),
            )
            store._event(db, "campaign", CAMPAIGN_ID, "campaign.visual_birth_material_frozen", args.actor, material_binding)
    pipeline = store.request_pipeline_state("running", actor=args.actor)
    print(json.dumps({
        "workflow_id": workflow["id"], "sessions": len(sessions), "events": 30220,
        "root_checkpoint_artifact_id": root["id"], "pipeline": pipeline,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
