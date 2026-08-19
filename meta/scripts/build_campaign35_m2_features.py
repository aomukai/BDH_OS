#!/usr/bin/env python3
"""Build immutable Campaign 35 M2/M3 feature and experience shards.

This runs on the trainbox after the reviewed image files and final assignment
ledger have been copied there.  M2 uses ``lexical_label``; M3 reuses the same
features and ordering with ``literal_caption``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def split_sessions(rows: list[dict[str, Any]], maximum: int) -> list[list[dict[str, Any]]]:
    """Split at concept boundaries while respecting the workflow event cap."""
    groups: list[list[dict[str, Any]]] = []
    for row in rows:
        if not groups or groups[-1][0]["concept_id"] != row["concept_id"]:
            groups.append([])
        groups[-1].append(row)
    if any(len(group) > maximum for group in groups):
        raise ValueError("one concept exceeds the per-session exposure ceiling")
    sessions: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for group in groups:
        if current and len(current) + len(group) > maximum:
            sessions.append(current)
            current = []
        current.extend(group)
    if current:
        sessions.append(current)
    return sessions


def local_image(row: dict[str, Any], source_root: Path) -> Path:
    original = Path(row["verified_local_path"])
    if not original.is_absolute():
        raise ValueError(f"accepted image path is not absolute: {original}")
    return source_root / original.relative_to("/")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assignments", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-events", type=int, default=1024)
    args = parser.parse_args()

    import numpy as np
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor

    rows = read_rows(args.assignments)
    rows.sort(key=lambda row: row["sequence_position"])
    if len(rows) != 14_397 or len({row["slot_id"] for row in rows}) != len(rows):
        raise ValueError("assignment ledger is not the frozen 14,397-slot M2 handoff")
    if any(row.get("disposition") != "accepted" for row in rows):
        raise ValueError("assignment ledger contains a non-accepted row")
    if any(not str(row.get("word", "")).strip() for row in rows):
        raise ValueError("M2 lexical target is empty")
    if any(not str(row.get("literal_caption", "")).strip() for row in rows):
        raise ValueError("M3 verified caption is empty")

    sessions = split_sessions(rows, args.max_events)
    args.output.mkdir(parents=True, exist_ok=True)
    processor = AutoProcessor.from_pretrained(args.weights, local_files_only=True)
    model = AutoModel.from_pretrained(args.weights, local_files_only=True).to(args.device).eval()
    receptor = getattr(model, "vision_model", model)
    manifest_sessions = []

    for index, session_rows in enumerate(sessions):
        session_id = f"m2-visual-{index:02d}"
        record_path = args.output / f"{session_id}-record.json"
        if record_path.is_file():
            record = json.loads(record_path.read_text(encoding="utf-8"))
            immutable_files = (
                (record["feature_path"], record["feature_sha256"]),
                (record["experience_path"], record["experience_sha256"]),
                (record["m2_events_path"], record["m2_events_sha256"]),
            )
            if (
                record.get("session_id") == session_id
                and record.get("event_count") == len(session_rows)
                and all(Path(path).is_file() and sha256(Path(path)) == digest for path, digest in immutable_files)
            ):
                manifest_sessions.append(record)
                continue
        unique: dict[str, dict[str, Any]] = {}
        for row in session_rows:
            unique.setdefault(row["sha256"], row)
        arrays: dict[str, Any] = {}
        hashes: list[str] = []
        for feature_index, digest in enumerate(sorted(unique)):
            row = unique[digest]
            path = local_image(row, args.source_root)
            if not path.is_file() or sha256(path) != digest:
                raise ValueError(f"image bytes fail the frozen hash: {row['slot_id']}")
            with Image.open(path) as source:
                image = source.convert("RGB")
            inputs = processor(images=image, return_tensors="pt").to(args.device)
            with torch.no_grad():
                encoded = receptor(
                    pixel_values=inputs["pixel_values"],
                    pixel_attention_mask=inputs["pixel_attention_mask"],
                    spatial_shapes=inputs["spatial_shapes"],
                    return_dict=True,
                )
            arrays[f"patch_{feature_index:04d}"] = encoded.last_hidden_state.detach().float().cpu().numpy()[0]
            arrays[f"mask_{feature_index:04d}"] = inputs["pixel_attention_mask"].detach().cpu().numpy()[0]
            arrays[f"shape_{feature_index:04d}"] = inputs["spatial_shapes"].detach().cpu().numpy()[0]
            hashes.append(digest)

        feature_path = args.output / f"{session_id}-features.npz"
        np.savez_compressed(feature_path, asset_sha256=np.asarray(hashes), **arrays)
        feature_manifest = {
            "schema_version": "ninereeds_visual_features_v1",
            "asset_sha256": hashes,
            "count": len(hashes),
            "format": "npz-no-pickle",
            "feature_kind": "siglip2_last_hidden_state",
            "feature_width": int(arrays["patch_0000"].shape[-1]),
            "includes_patch_mask": True,
            "includes_spatial_shapes": True,
            "campaign_id": "campaign-35-multimodal-foundation-v1",
            "session_id": session_id,
        }
        experience_events = []
        m2_events = []
        seen_concepts: set[str] = set()
        ordered_concepts = []
        for row in session_rows:
            experience_events.extend([
                {
                    "type": "observe_image", "asset_sha256": row["sha256"],
                    "concept": row["concept"], "ordinal": row["ordinal"],
                    "example_index": row["exposure_index"], "slot_id": row["slot_id"],
                },
                {
                    "type": "hear_or_read_text", "text": row["literal_caption"],
                    "concept": row["concept"], "ordinal": row["ordinal"],
                    "example_index": row["exposure_index"], "slot_id": row["slot_id"],
                },
            ])
            m2_events.append({
                "type": "visual", "concept": row["concept"], "ordinal": row["ordinal"],
                "completion": row["word"], "asset_sha256": row["sha256"],
                "slot_id": row["slot_id"], "sequence_position": row["sequence_position"],
            })
            key = row["concept"].casefold()
            if key not in seen_concepts:
                seen_concepts.add(key)
                ordered_concepts.append({"concept": row["concept"], "depends_on": []})
        experience = {
            "schema_version": "ninereeds_msm_experience_v1",
            "experience_id": f"campaign35-{session_id}",
            "status": "accepted",
            "events": experience_events,
            "source_assignment_sha256": sha256(args.assignments),
        }
        experience_path = args.output / f"{session_id}-experience.json"
        experience_path.write_text(
            json.dumps(experience, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        events_path = args.output / f"{session_id}-m2-events.json"
        events_path.write_text(
            json.dumps(m2_events, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        record = {
            "session_id": session_id,
            "event_count": len(m2_events),
            "unique_feature_count": len(hashes),
            "ordinal_first": session_rows[0]["ordinal"],
            "ordinal_last": session_rows[-1]["ordinal"],
            "ordered_concepts": ordered_concepts,
            "feature_path": str(feature_path.resolve()),
            "feature_sha256": sha256(feature_path),
            "feature_bytes": feature_path.stat().st_size,
            "feature_manifest": feature_manifest,
            "experience_path": str(experience_path.resolve()),
            "experience_sha256": sha256(experience_path),
            "experience_bytes": experience_path.stat().st_size,
            "experience_manifest": experience,
            "m2_events_path": str(events_path.resolve()),
            "m2_events_sha256": sha256(events_path),
        }
        record_path.write_text(
            json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest_sessions.append(record)

    manifest = {
        "schema_version": "ninereeds_campaign35_m2_material_v1",
        "status": "frozen",
        "campaign_id": "campaign-35-multimodal-foundation-v1",
        "assignment_sha256": sha256(args.assignments),
        "event_count": len(rows),
        "unique_asset_count": len({row["sha256"] for row in rows}),
        "session_count": len(manifest_sessions),
        "m2_target": "lexical_label",
        "m3_target": "verified_literal_caption",
        "same_assets_and_order": True,
        "sessions": manifest_sessions,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in manifest.items() if key != "sessions"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
