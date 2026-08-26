#!/usr/bin/env python3
"""Build frozen SigLIP2 feature and one-word event shards for visual birth."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "ninereeds_foundation_visual_material_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def curriculum_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for name in ("teaching-contracts.jsonl", "accepted-assets.jsonl", "dependency-edges.jsonl"):
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(bytes.fromhex(sha256(root / name)))
    return digest.hexdigest()


def split_sessions(
    contracts: list[dict[str, Any]], assets: dict[str, list[dict[str, Any]]], maximum: int,
) -> list[list[tuple[dict[str, Any], list[dict[str, Any]]]]]:
    sessions: list[list[tuple[dict[str, Any], list[dict[str, Any]]]]] = []
    current: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    size = 0
    for contract in contracts:
        rows = sorted(assets[contract["contract_id"]], key=lambda row: int(row["exposure_index"]))
        if len(rows) != 10:
            raise ValueError(f"{contract['contract_id']} has {len(rows)} images")
        if current and size + len(rows) > maximum:
            sessions.append(current)
            current, size = [], 0
        current.append((contract, rows))
        size += len(rows)
    if current:
        sessions.append(current)
    return sessions


def source_image(row: dict[str, Any], source_root: Path) -> Path:
    original = Path(row["local_path"])
    if not original.is_absolute():
        raise ValueError(f"source image path is not absolute: {original}")
    return source_root / original.relative_to("/")


def record_valid(path: Path, expected_events: int, manifest: str) -> bool:
    if not path.is_file():
        return False
    record = json.loads(path.read_text(encoding="utf-8"))
    files = (
        (record.get("feature_path"), record.get("feature_sha256")),
        (record.get("experience_path"), record.get("experience_sha256")),
        (record.get("events_path"), record.get("events_sha256")),
    )
    return bool(
        record.get("input_manifest_sha256") == manifest
        and record.get("event_count") == expected_events
        and all(path_value and Path(path_value).is_file() and sha256(Path(path_value)) == digest for path_value, digest in files)
    )


def build_session(
    index: int,
    groups: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    *,
    output: Path,
    source_root: Path,
    manifest: str,
    receptor: Any,
    processor: Any,
    device: str,
) -> dict[str, Any]:
    import numpy as np
    import torch
    from PIL import Image

    session_id = f"foundation-visual-{index:02d}"
    rows = [row for _, values in groups for row in values]
    record_path = output / f"{session_id}-record.json"
    if record_valid(record_path, len(rows), manifest):
        return json.loads(record_path.read_text(encoding="utf-8"))

    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        unique.setdefault(str(row.get("sha256") or row["asset_sha256"]), row)
    arrays: dict[str, Any] = {}
    hashes: list[str] = []
    for feature_index, digest in enumerate(sorted(unique)):
        row = unique[digest]
        path = source_image(row, source_root)
        if not path.is_file() or sha256(path) != digest:
            raise ValueError(f"image bytes fail the frozen hash: {row['contract_id']}/{row['exposure_index']}")
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        inputs = processor(images=image, return_tensors="pt").to(device)
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

    feature_path = output / f"{session_id}-features.npz"
    np.savez_compressed(feature_path, asset_sha256=np.asarray(hashes), **arrays)
    label_by_id = {contract["contract_id"]: contract["display_label"] for contract, _ in groups}
    ordered_concepts = []
    events = []
    experience_events = []
    for contract, values in groups:
        dependencies = []
        for dependency_id in contract.get("depends_on", []):
            if dependency_id not in label_by_id:
                # Dependencies from earlier sessions are already bound into the
                # parent checkpoint knowledge ledger.
                dependencies.append(dependency_id)
            else:
                dependencies.append(label_by_id[dependency_id])
        ordered_concepts.append({
            "concept": contract["display_label"],
            "depends_on_contract_ids": list(contract.get("depends_on", [])),
            "depends_on": dependencies,
        })
        for row in values:
            digest = str(row.get("sha256") or row["asset_sha256"])
            event = {
                "type": "visual",
                "concept": contract["display_label"],
                "ordinal": int(contract["ordinal"]),
                "completion": contract["display_label"],
                "asset_sha256": digest,
            }
            events.append(event)
            experience_events.append({
                "type": "observe_image",
                "asset_sha256": digest,
                "concept": contract["display_label"],
                "ordinal": int(contract["ordinal"]),
                "example_index": int(row["exposure_index"]),
                "contract_id": contract["contract_id"],
            })

    # Replace dependency IDs from earlier sessions with their canonical labels.
    all_contracts = load_jsonl(Path(groups[0][0]["_curriculum_contracts_path"])) if "_curriculum_contracts_path" in groups[0][0] else []
    if all_contracts:
        global_labels = {row["contract_id"]: row["display_label"] for row in all_contracts}
        for item in ordered_concepts:
            item["depends_on"] = [global_labels[value] for value in item.pop("depends_on_contract_ids")]
    else:
        for item in ordered_concepts:
            if item.pop("depends_on_contract_ids"):
                raise ValueError("global dependency labels are unavailable")

    experience = {
        "schema_version": "ninereeds_msm_experience_v1",
        "experience_id": session_id,
        "status": "accepted",
        "events": experience_events,
        "input_manifest_sha256": manifest,
        "supervision": "one_positive_lexical_target_per_image",
    }
    experience_path = output / f"{session_id}-experience.json"
    events_path = output / f"{session_id}-events.json"
    write_json(experience_path, experience)
    write_json(events_path, events)
    feature_manifest = {
        "schema_version": "ninereeds_visual_features_v1",
        "campaign_id": "foundation-visual-3022-v1",
        "session_id": session_id,
        "count": len(hashes),
        "format": "npz-no-pickle",
        "feature_kind": "siglip2_last_hidden_state",
        "feature_width": int(arrays["patch_0000"].shape[-1]),
        "includes_patch_mask": True,
        "includes_spatial_shapes": True,
        "input_manifest_sha256": manifest,
    }
    record = {
        "schema_version": SCHEMA,
        "session_id": session_id,
        "session_index": index,
        "event_count": len(events),
        "concept_count": len(groups),
        "unique_feature_count": len(hashes),
        "ordinal_first": int(groups[0][0]["ordinal"]),
        "ordinal_last": int(groups[-1][0]["ordinal"]),
        "ordered_concepts": [{"concept": row["concept"], "depends_on": row["depends_on"]} for row in ordered_concepts],
        "input_manifest_sha256": manifest,
        "feature_path": str(feature_path.resolve()),
        "feature_sha256": sha256(feature_path),
        "feature_bytes": feature_path.stat().st_size,
        "feature_manifest": feature_manifest,
        "experience_path": str(experience_path.resolve()),
        "experience_sha256": sha256(experience_path),
        "experience_bytes": experience_path.stat().st_size,
        "experience_manifest": experience,
        "events_path": str(events_path.resolve()),
        "events_sha256": sha256(events_path),
    }
    write_json(record_path, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curriculum", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--max-events", type=int, default=1000)
    parser.add_argument("--worker-index", type=int, default=0)
    parser.add_argument("--worker-count", type=int, default=1)
    parser.add_argument("--finalize-only", action="store_true")
    args = parser.parse_args()

    manifest = curriculum_sha256(args.curriculum)
    if manifest != args.expected_manifest_sha256:
        raise ValueError(f"curriculum manifest mismatch: {manifest}")
    contracts_path = args.curriculum / "teaching-contracts.jsonl"
    contracts = sorted(load_jsonl(contracts_path), key=lambda row: int(row["ordinal"]))
    if len(contracts) != 3022 or len({row["display_label"].casefold() for row in contracts}) != 3022:
        raise ValueError("foundation requires 3,022 unique positive lexical targets")
    # This private build-only field gives each worker the complete dependency label map.
    for contract in contracts:
        contract["_curriculum_contracts_path"] = str(contracts_path.resolve())
    asset_rows = load_jsonl(args.curriculum / "accepted-assets.jsonl")
    if len(asset_rows) != 30220:
        raise ValueError("foundation requires exactly 30,220 image exposures")
    assets: dict[str, list[dict[str, Any]]] = {}
    for row in asset_rows:
        assets.setdefault(row["contract_id"], []).append(row)
    sessions = split_sessions(contracts, assets, args.max_events)
    args.output.mkdir(parents=True, exist_ok=True)

    if not args.finalize_only:
        if not (0 <= args.worker_index < args.worker_count):
            raise ValueError("worker index is outside worker count")
        import torch
        from transformers import AutoModel, AutoProcessor

        processor = AutoProcessor.from_pretrained(args.weights, local_files_only=True)
        model = AutoModel.from_pretrained(args.weights, local_files_only=True).to(args.device).eval()
        receptor = getattr(model, "vision_model", model)
        completed = []
        for index, groups in enumerate(sessions):
            if index % args.worker_count != args.worker_index:
                continue
            record = build_session(
                index, groups, output=args.output, source_root=args.source_root,
                manifest=manifest, receptor=receptor, processor=processor, device=args.device,
            )
            completed.append(record["session_id"])
            print(json.dumps({"session_id": record["session_id"], "events": record["event_count"]}), flush=True)
        print(json.dumps({"worker_index": args.worker_index, "completed_sessions": completed}), flush=True)
        return 0

    records = []
    for index, groups in enumerate(sessions):
        path = args.output / f"foundation-visual-{index:02d}-record.json"
        expected_events = sum(len(rows) for _, rows in groups)
        if not record_valid(path, expected_events, manifest):
            raise ValueError(f"missing or invalid feature session: {index}")
        records.append(json.loads(path.read_text(encoding="utf-8")))
    result = {
        "schema_version": SCHEMA,
        "status": "frozen",
        "campaign_id": "foundation-visual-3022-v1",
        "input_manifest_sha256": manifest,
        "contract_count": len(contracts),
        "event_count": sum(row["event_count"] for row in records),
        "unique_asset_count": len({str(row.get("sha256") or row["asset_sha256"]) for row in asset_rows}),
        "session_count": len(records),
        "target": "one_positive_lexical_item",
        "order_policy": "declared_only",
        "shuffle_allowed": False,
        "sessions": records,
    }
    if result["event_count"] != 30220:
        raise ValueError("final feature manifest lost image events")
    write_json(args.output / "manifest.json", result)
    print(json.dumps({key: value for key, value in result.items() if key != "sessions"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
