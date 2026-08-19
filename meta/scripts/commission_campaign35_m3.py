#!/usr/bin/env python3
"""Freeze and optionally commission Campaign 35 M3 from exact M1 and M2 material.

M3 starts at the neutral Campaign 35 checkpoint.  Within each curriculum
concept it alternates the next reviewed image/full caption and the next M1
text exchange, then emits any remainder.  No concept is split across sessions;
the M2 feature and accepted-experience shards are reused byte-for-byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from mission_hub.config import load_config_bundle
from mission_hub.jsonutil import canonical_json
from mission_hub.schema import load_schema, validate
from mission_hub.store import MissionHubStore, utc_now


CAMPAIGN_ID = "campaign-35-multimodal-foundation-v1"
ASSIGNMENT_COUNT = 14_397
TEXT_COUNT = 7_891
TOTAL_COUNT = ASSIGNMENT_COUNT + TEXT_COUNT
MAX_EVENTS = 512


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_immutable(path: Path, value: Any) -> str:
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if path.exists() and path.read_bytes() != payload:
        raise ValueError(f"refusing to replace different frozen M3 material: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def concept_events(
    curriculum: dict[str, Any], images: list[dict[str, Any]], texts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index in range(max(len(images), len(texts))):
        if index < len(images):
            image = images[index]
            result.append({
                "type": "visual",
                "concept": curriculum["concept"],
                "ordinal": curriculum["ordinal"],
                "completion": image["literal_caption"].strip(),
                "asset_sha256": image["sha256"],
            })
        if index < len(texts):
            text = texts[index]
            result.append({
                "type": "text",
                "concept": curriculum["concept"],
                "ordinal": curriculum["ordinal"],
                "prompt": text["prompt"],
                "completion": text["completion"],
            })
    return result


def split_at_concepts(
    concepts: list[tuple[dict[str, Any], list[dict[str, Any]]]],
) -> list[list[tuple[dict[str, Any], list[dict[str, Any]]]]]:
    sessions: list[list[tuple[dict[str, Any], list[dict[str, Any]]]]] = []
    current: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    current_count = 0
    for item in concepts:
        event_count = len(item[1])
        if event_count > MAX_EVENTS:
            raise ValueError(f"concept {item[0]['concept_id']} exceeds the session event ceiling")
        if current and current_count + event_count > MAX_EVENTS:
            sessions.append(current)
            current, current_count = [], 0
        current.append(item)
        current_count += event_count
    if current:
        sessions.append(current)
    return sessions


def build(args: argparse.Namespace, bundle: Any, store: MissionHubStore) -> tuple[dict[str, Any], dict[str, Any]]:
    assignments = read_jsonl(args.assignments)
    texts = read_jsonl(args.text_lessons)
    curriculum_rows = read_jsonl(args.curriculum)
    m2_manifest = json.loads(args.m2_manifest.read_text(encoding="utf-8"))
    if len(assignments) != ASSIGNMENT_COUNT or len(texts) != TEXT_COUNT or len(curriculum_rows) != 2_500:
        raise ValueError("M3 inputs do not have the exact Campaign 35 frozen counts")
    if sha256(args.assignments) != m2_manifest.get("assignment_sha256"):
        raise ValueError("M3 assignments differ from the exact M2 assignment ledger")
    assignments.sort(key=lambda row: row["sequence_position"])
    texts.sort(key=lambda row: (row["ordinal"], row["example_index"]))
    curriculum_rows.sort(key=lambda row: row["ordinal"])
    curriculum = {row["ordinal"]: row for row in curriculum_rows}
    if list(curriculum) != list(range(1, 2_501)):
        raise ValueError("Campaign 35 curriculum ordinals are not exactly 1..2500")
    if len({row["slot_id"] for row in assignments}) != ASSIGNMENT_COUNT:
        raise ValueError("M3 image assignment slot IDs are not unique")
    if any(row.get("disposition") != "accepted" or not str(row.get("literal_caption", "")).strip() for row in assignments):
        raise ValueError("M3 image assignments are not all accepted and fully captioned")
    for row in (*assignments, *texts):
        item = curriculum.get(row.get("ordinal"))
        if item is None or row.get("concept_id") != item["concept_id"]:
            raise ValueError(f"material/curriculum mismatch at ordinal {row.get('ordinal')}")

    with store._connect() as db:
        campaign = db.execute(
            "SELECT state,metadata_json FROM campaigns WHERE id=?", (CAMPAIGN_ID,),
        ).fetchone()
    if campaign is None or campaign["state"] != "active":
        raise ValueError("Campaign 35 is not active")
    metadata = json.loads(campaign["metadata_json"])
    m2_record = metadata.get("campaign35_m2_material")
    if not isinstance(m2_record, dict) or m2_record.get("status") != "frozen_for_m2":
        raise ValueError("M2 material has not been frozen and registered")
    if m2_record.get("assignment_sha256") != m2_manifest.get("assignment_sha256"):
        raise ValueError("registered M2 material differs from the local frozen manifest")
    registered = {row["session_id"]: row for row in m2_record["registered_sessions"]}
    if len(registered) != len(m2_manifest["sessions"]):
        raise ValueError("registered M2 feature shard count differs from its frozen manifest")

    images_by_ordinal: dict[int, list[dict[str, Any]]] = {}
    texts_by_ordinal: dict[int, list[dict[str, Any]]] = {}
    for row in assignments:
        images_by_ordinal.setdefault(row["ordinal"], []).append(row)
    for row in texts:
        texts_by_ordinal.setdefault(row["ordinal"], []).append(row)

    sessions: list[dict[str, Any]] = []
    frozen_sessions: list[dict[str, Any]] = []
    previous_last = 0
    for base in m2_manifest["sessions"]:
        base_id = base["session_id"]
        if base_id not in registered:
            raise ValueError(f"M2 shard is not registered: {base_id}")
        domain_first = previous_last + 1
        domain_last = 2_500 if base is m2_manifest["sessions"][-1] else base["ordinal_last"]
        previous_last = base["ordinal_last"]
        concept_groups = []
        for ordinal in range(domain_first, domain_last + 1):
            events = concept_events(
                curriculum[ordinal], images_by_ordinal.get(ordinal, []), texts_by_ordinal.get(ordinal, []),
            )
            if not events:
                raise ValueError(f"M3 concept has no material at ordinal {ordinal}")
            concept_groups.append((curriculum[ordinal], events))
        for part_index, part in enumerate(split_at_concepts(concept_groups)):
            events = [event for _, group in part for event in group]
            # Session IDs are durable admission identities.  The original
            # oversized v1 workflow already bound m3-joint-00, so repaired
            # transport packaging must use new identities even though every
            # underlying exposure remains byte-for-byte identical.
            session_id = f"m3-joint-v3-{len(sessions):02d}"
            event_path = args.output / f"{session_id}-events.json"
            event_sha = write_immutable(event_path, events)
            ordered = [{"concept": row["concept"], "depends_on": []} for row, _ in part]
            source = registered[base_id]
            sessions.append({
                "id": session_id,
                "visual_features_artifact_id": source["visual_features_artifact_id"],
                "visual_experience_artifact_id": source["visual_experience_artifact_id"],
                "ordered_concepts": ordered,
                "events": events,
                "parameters": {
                    "epochs": 1,
                    "learning_rate": 0.0002,
                    "weight_decay": 0.0,
                    "seed": 35_000_000,
                    "ingress_device": "cuda:0",
                    "core_device": "cuda:1",
                    "local_files_only": True,
                    "rms_clip": 0.125,
                    "stochastic_rounding": True,
                },
            })
            frozen_sessions.append({
                "session_id": session_id,
                "base_m2_session_id": base_id,
                "base_part_index": part_index,
                "ordinal_first": part[0][0]["ordinal"],
                "ordinal_last": part[-1][0]["ordinal"],
                "concept_count": len(part),
                "event_count": len(events),
                "visual_event_count": sum(event["type"] == "visual" for event in events),
                "text_event_count": sum(event["type"] == "text" for event in events),
                "events_path": str(event_path.resolve()),
                "events_sha256": event_sha,
                "visual_features_artifact_id": source["visual_features_artifact_id"],
                "visual_experience_artifact_id": source["visual_experience_artifact_id"],
            })

    flattened = [event for session in sessions for event in session["events"]]
    visual = [event for event in flattened if event["type"] == "visual"]
    text = [event for event in flattened if event["type"] == "text"]
    expected_visual = [(row["ordinal"], row["sha256"], row["literal_caption"].strip()) for row in assignments]
    actual_visual = [(row["ordinal"], row["asset_sha256"], row["completion"]) for row in visual]
    if actual_visual != expected_visual:
        raise ValueError("M3 does not preserve exact M2 image bytes, order, and verified captions")
    expected_text = [(row["ordinal"], row["prompt"], row["completion"]) for row in texts]
    actual_text = [(row["ordinal"], row["prompt"], row["completion"]) for row in text]
    if actual_text != expected_text:
        raise ValueError("M3 does not preserve exact M1 text bytes and concept order")
    if len(flattened) != TOTAL_COUNT or max(map(len, (session["events"] for session in sessions))) > MAX_EVENTS:
        raise ValueError("M3 combined event count or session ceiling changed")

    execution = metadata["campaign35_execution"]
    workflow = {
        "campaign_id": CAMPAIGN_ID,
        "branch_id": "m3-words-and-images",
        "starting_checkpoint_artifact_id": metadata["starting_checkpoint_artifact_id"],
        "evaluation_suite_artifact_id": execution["evaluation_suite_artifact_id"],
        "architecture": "lfm2_5_encoder_230m_frozen__ninereeds_1_2b__lfm2_5_230m_frozen",
        "identity_scope": "identity_and_integrity",
        "training_job_type": "model.multimodal_train",
        "multimodal_mode": "joint",
        "evaluation_policy": "behavioral_and_mri",
        "sessions": sessions,
        "evaluation_parameters": {"ingress_device": "cuda:0", "core_device": "cuda:1", "max_new_tokens": 128},
        "authorization": {
            "exact_workflow_reviewed": True,
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_automatic_branch_ranking": False,
            "allow_pipeline_continue_after_completion": False,
        },
    }
    schema = load_schema(bundle.root.parent.parent, "schemas/mission_hub/workflows/cortex-workflow.schema.json")
    errors = validate(workflow, schema)
    if errors:
        raise ValueError("invalid frozen M3 workflow: " + "; ".join(errors))
    manifest = {
        "schema_version": "ninereeds_campaign35_m3_material_v1",
        "status": "frozen",
        "campaign_id": CAMPAIGN_ID,
        "ordering_policy": "per_concept_alternate_next_image_full_caption_then_next_m1_text_then_remainder",
        "neutral_root": metadata["starting_checkpoint_artifact_id"],
        "m2_assignment_sha256": sha256(args.assignments),
        "m2_manifest_sha256": sha256(args.m2_manifest),
        "m1_text_sha256": sha256(args.text_lessons),
        "curriculum_sha256": sha256(args.curriculum),
        "visual_event_count": len(visual),
        "text_event_count": len(text),
        "event_count": len(flattened),
        "concept_count": len(curriculum),
        "session_count": len(sessions),
        "same_m2_assets_and_visual_order": True,
        "same_m1_text_and_concept_order": True,
        "sessions": frozen_sessions,
    }
    return workflow, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/mission_hub"))
    parser.add_argument("--assignments", type=Path, default=Path("/media/aomukai/FILES/Ninereeds/image-corpus/exports/campaign35-auto-image-loop-v1/flux-specialist-controller-v1/completion/accepted_assignments.jsonl"))
    parser.add_argument("--m2-manifest", type=Path, default=Path("/home/aomukai/.local/share/ninereeds/mission-hub/campaign35-m2-material/manifest.json"))
    parser.add_argument("--text-lessons", type=Path, default=Path("config/mission_hub/campaign_material/campaign35/text-lessons.jsonl"))
    parser.add_argument("--curriculum", type=Path, default=Path("config/mission_hub/campaign_material/campaign35/curriculum.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("/home/aomukai/.local/share/ninereeds/mission-hub/campaign35-m3-material-v3"))
    parser.add_argument("--replace-failed-workflow-id", help="supersede a failed, pre-update M3 workflow with these exact repaired bytes")
    parser.add_argument("--start", action="store_true", help="authorize the exact workflow and unpause the pipeline")
    parser.add_argument("--actor", default="operator:campaign35-m3-material")
    args = parser.parse_args()
    bundle = load_config_bundle(args.config)
    store = MissionHubStore(Path(bundle.base["hub"]["state_root"]) / bundle.base["hub"]["database_name"])
    workflow, manifest = build(args, bundle, store)
    manifest_path = args.output / "manifest.json"
    manifest_sha = write_immutable(manifest_path, manifest)
    workflow_path = args.output / "workflow.json"
    workflow_sha = write_immutable(workflow_path, workflow)
    result = {
        "status": "frozen",
        "manifest": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "workflow": str(workflow_path),
        "workflow_sha256": workflow_sha,
        "sessions": manifest["session_count"],
        "events": manifest["event_count"],
        "visual_events": manifest["visual_event_count"],
        "text_events": manifest["text_event_count"],
    }
    if args.start:
        created = store.create_cortex_workflow(
            bundle, workflow, actor=args.actor,
            replaces_pretraining_workflow_id=args.replace_failed_workflow_id,
        )
        material_record = {
            **{key: value for key, value in manifest.items() if key != "sessions"},
            "status": "frozen_for_m3",
            "manifest_sha256": manifest_sha,
            "workflow_sha256": workflow_sha,
            "workflow_id": created["id"],
            "frozen_at": utc_now(),
        }
        with store.transaction() as db:
            row = db.execute("SELECT metadata_json FROM campaigns WHERE id=?", (CAMPAIGN_ID,)).fetchone()
            current = json.loads(row[0])
            prior = current.get("campaign35_m3_material")
            if prior is not None and prior != material_record:
                replaced_id = args.replace_failed_workflow_id
                replaced = db.execute(
                    "SELECT status FROM cortex_workflows WHERE id=?", (replaced_id,),
                ).fetchone() if replaced_id else None
                successful = db.execute(
                    """SELECT COUNT(*) FROM cortex_workflow_jobs w JOIN jobs j ON j.id=w.job_id
                       WHERE w.workflow_id=? AND j.job_type IN ('model.train','model.multimodal_train')
                         AND j.status='succeeded'""",
                    (replaced_id,),
                ).fetchone()[0] if replaced_id else 0
                if (
                    prior.get("workflow_id") != replaced_id
                    or replaced is None or replaced["status"] not in {"failed", "blocked", "cancelled"}
                    or successful
                ):
                    raise ValueError("Campaign 35 M3 is already frozen with different material")
                history = current.setdefault("campaign35_m3_material_history", [])
                if not any(item.get("workflow_id") == prior.get("workflow_id") for item in history):
                    history.append({**prior, "superseded_at": utc_now(), "superseded_by": created["id"]})
            current["campaign35_m3_material"] = material_record
            db.execute(
                "UPDATE campaigns SET metadata_json=?,updated_at=? WHERE id=?",
                (canonical_json(current), utc_now(), CAMPAIGN_ID),
            )
            store._event(db, "campaign", CAMPAIGN_ID, "campaign.m3_joint_material_frozen", args.actor, material_record)
        result["workflow_id"] = created["id"]
        result["pipeline"] = store.request_pipeline_state("running", actor=args.actor)
        result["status"] = "authorized"
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
