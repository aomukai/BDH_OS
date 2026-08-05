#!/usr/bin/env python3
"""Reuse catalog assets and commission remaining foundation-plan candidates with FLUX."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import io
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from diffusers import Flux2KleinPipeline

from training.pipeline.visual.catalog import AssetCatalog, utc_now
from training.pipeline.visual.foundation import validate_plan


RECEIPT_SCHEMA = "ninereeds_foundational_visual_candidates_v1"


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def image_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def accepted_claim(record: dict[str, Any], caption: str) -> bool:
    return any(claim.get("text") == caption and claim.get("status") == "accepted" for claim in record["claims"])


def reusable_assets(catalog: AssetCatalog, caption: str, used: set[str]) -> list[dict[str, Any]]:
    try:
        records = catalog.search(f'"{caption}"', split="train")
    except Exception:
        return []
    return [
        record for record in records
        if record["asset_sha256"] not in used
        and accepted_claim(record, caption)
        and record["source"]["kind"] in {"dataset", "operator"}
    ]


def new_receipt(plan: dict[str, Any], plan_path: Path) -> dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA,
        "pack_id": plan["pack_id"],
        "plan_path": str(plan_path.resolve()),
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "running",
        "model": None,
        "items": {},
        "superseded": [],
        "applied_replacement_specs": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, default=Path("tmp/vision/model_manifest.json"))
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--lock-file", type=Path, default=Path("/home/aomukai/.local/state/ninereeds-control/worker/trainbox-worker.lock"))
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--offload-profile", choices=["sequential", "model"], default="sequential")
    parser.add_argument(
        "--replacement-spec", type=Path,
        help="JSON object with replacements: [{item_id, prompt, seed, reason}]",
    )
    args = parser.parse_args()
    if args.max_items is not None and args.max_items <= 0:
        parser.error("--max-items must be positive")

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    validate_plan(plan)
    plan_hash = hashlib.sha256(args.plan.read_bytes()).hexdigest()
    if args.receipt.exists():
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        if receipt.get("schema_version") != RECEIPT_SCHEMA or receipt.get("plan_sha256") != plan_hash:
            raise ValueError("receipt belongs to a different plan")
    else:
        receipt = new_receipt(plan, args.plan)
    receipt.setdefault("superseded", [])
    receipt.setdefault("applied_replacement_specs", [])
    replacement_rows = []
    replacement_spec_sha256 = None
    if args.replacement_spec:
        replacement_spec_sha256 = hashlib.sha256(args.replacement_spec.read_bytes()).hexdigest()
        if replacement_spec_sha256 in receipt["applied_replacement_specs"]:
            replacement_spec_sha256 = None
        else:
            replacement_doc = json.loads(args.replacement_spec.read_text(encoding="utf-8"))
            replacement_rows = replacement_doc.get("replacements", [])
    if replacement_rows:
        plan_ids = {item["item_id"] for item in plan["items"]}
        replacement_ids = [row.get("item_id") for row in replacement_rows]
        if (
            not replacement_rows or len(replacement_ids) != len(set(replacement_ids))
            or any(item_id not in plan_ids for item_id in replacement_ids)
            or any(not isinstance(row.get("prompt"), str) or not row["prompt"].strip() for row in replacement_rows)
            or any(not isinstance(row.get("seed"), int) or isinstance(row["seed"], bool) for row in replacement_rows)
            or any(not isinstance(row.get("reason"), str) or not row["reason"].strip() for row in replacement_rows)
        ):
            raise ValueError("invalid replacement spec")

    args.lock_file.parent.mkdir(parents=True, exist_ok=True)
    with args.lock_file.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("trainbox worker lock is already held") from exc

        catalog = AssetCatalog(args.catalog_root)
        overrides = {row["item_id"]: row for row in replacement_rows}
        for item_id, replacement in overrides.items():
            previous = receipt["items"].pop(item_id, None)
            if previous is not None and previous.get("replacement_spec_sha256") == replacement_spec_sha256:
                receipt["items"][item_id] = previous
                continue
            if previous is None:
                raise ValueError(f"replacement item has no current candidate: {item_id}")
            receipt["superseded"].append({
                **previous, "superseded_at": utc_now(),
                "replacement_reason": replacement["reason"],
                "replacement_spec_sha256": replacement_spec_sha256,
            })
        if overrides:
            receipt["updated_at"] = utc_now()
            receipt["status"] = "running"
            atomic_json(args.receipt, receipt)
        effective_items = []
        for original in plan["items"]:
            item = dict(original)
            if item["item_id"] in overrides:
                item["prompt"] = overrides[item["item_id"]]["prompt"].strip()
                item["seed"] = overrides[item["item_id"]]["seed"]
            effective_items.append(item)
        existing_by_sha256 = {record["asset_sha256"]: record for record in catalog.records()}
        used = {row["asset_sha256"] for row in receipt["items"].values() if "asset_sha256" in row}
        completed_this_run = 0
        for item in effective_items:
            if item["item_id"] in receipt["items"]:
                continue
            reusable = reusable_assets(catalog, item["canonical_caption"], used)
            if not reusable:
                continue
            record = reusable[0]
            receipt["items"][item["item_id"]] = {
                "item_id": item["item_id"], "concept_id": item["concept_id"],
                "canonical_caption": item["canonical_caption"], "status": "reused_verified",
                "asset_sha256": record["asset_sha256"], "object_path": record["object_path"],
                "source_kind": record["source"]["kind"], "seconds": 0.0,
                **(
                    {"replacement_spec_sha256": replacement_spec_sha256}
                    if item["item_id"] in overrides else {}
                ),
            }
            used.add(record["asset_sha256"])
            completed_this_run += 1
            receipt["updated_at"] = utc_now()
            atomic_json(args.receipt, receipt)
            if args.max_items is not None and completed_this_run >= args.max_items:
                print(json.dumps({"receipt": str(args.receipt), "completed_this_run": completed_this_run, "status": "partial"}))
                return 0

        remaining = [item for item in effective_items if item["item_id"] not in receipt["items"]]
        if remaining and (args.max_items is None or completed_this_run < args.max_items):
            manifest = json.loads(args.model_manifest.read_text(encoding="utf-8"))
            model = manifest["models"]["flux4b"]
            receipt["model"] = {
                "repo_id": model["repo_id"], "revision": model["revision"],
                "execution_profile": f"fp16-{args.offload_profile}-cpu-offload",
            }
            pipe = Flux2KleinPipeline.from_pretrained(
                model["snapshot_path"], local_files_only=True, torch_dtype=torch.float16,
            )
            if args.offload_profile == "model":
                pipe.enable_model_cpu_offload()
            else:
                pipe.enable_sequential_cpu_offload()
            pipe.vae.enable_slicing()
            pipe.vae.enable_tiling()
            for item in remaining:
                if args.max_items is not None and completed_this_run >= args.max_items:
                    break
                started = time.monotonic()
                image = pipe(
                    prompt=item["prompt"], height=plan["generation"]["height"],
                    width=plan["generation"]["width"],
                    guidance_scale=plan["generation"]["guidance_scale"],
                    num_inference_steps=plan["generation"]["steps"],
                    generator=torch.Generator(device="cpu").manual_seed(item["seed"]),
                ).images[0]
                payload = image_bytes(image)
                digest = hashlib.sha256(payload).hexdigest()
                metadata = {
                        "display_filename": f"{plan['pack_id']}_{item['item_id']}_{item['seed']}.png",
                        "family_id": f"{plan['pack_id']}:{item['item_id']}",
                        "split": "unassigned",
                        "description": {
                            "text": f"Unverified FLUX candidate commissioned for: {item['canonical_caption']}",
                            "status": "source_label_only", "author": plan["pack_id"],
                            "model_id": None, "model_revision": None,
                        },
                        "search_terms": [item["concept_id"], item["canonical_caption"], plan["pack_id"], "generated"],
                        "facts": [],
                        "claims": [{"text": item["canonical_caption"], "status": "candidate", "verified_by": []}],
                        "source": {
                            "kind": "generated", "dataset": None, "item_id": item["item_id"],
                            "license": "Apache-2.0",
                            "attribution": "Generated locally with black-forest-labs/FLUX.2-klein-4B",
                        },
                        "lineage": {
                            "parent_sha256": None, "model_id": model["repo_id"],
                            "model_revision": model["revision"], "prompt": item["prompt"],
                            "seed": item["seed"], "intended_delta": item["canonical_caption"],
                        },
                    }
                record = existing_by_sha256.get(digest)
                if record is not None:
                    lineage = metadata["lineage"]
                    if any(record["lineage"].get(key) != value for key, value in lineage.items()):
                        raise RuntimeError(f"deterministic output {digest} has conflicting lineage")
                else:
                    record = catalog.import_bytes(payload, metadata, export_jsonl=False)
                    existing_by_sha256[digest] = record
                receipt["items"][item["item_id"]] = {
                    "item_id": item["item_id"], "concept_id": item["concept_id"],
                    "canonical_caption": item["canonical_caption"], "status": "commissioned_pending_review",
                    "asset_sha256": record["asset_sha256"], "object_path": record["object_path"],
                    "source_kind": "generated", "seconds": round(time.monotonic() - started, 3),
                    **(
                        {"replacement_spec_sha256": replacement_spec_sha256}
                        if item["item_id"] in overrides else {}
                    ),
                }
                used.add(record["asset_sha256"])
                completed_this_run += 1
                receipt["updated_at"] = utc_now()
                atomic_json(args.receipt, receipt)
            del pipe
            torch.cuda.empty_cache()
            catalog.export_jsonl()

        receipt["status"] = "candidates_complete" if len(receipt["items"]) == len(plan["items"]) else "partial"
        if overrides and receipt["status"] == "candidates_complete" and replacement_spec_sha256 not in receipt["applied_replacement_specs"]:
            receipt["applied_replacement_specs"].append(replacement_spec_sha256)
        receipt["updated_at"] = utc_now()
        atomic_json(args.receipt, receipt)
        print(json.dumps({
            "receipt": str(args.receipt.resolve()), "status": receipt["status"],
            "completed": len(receipt["items"]), "target": len(plan["items"]),
            "completed_this_run": completed_this_run,
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
