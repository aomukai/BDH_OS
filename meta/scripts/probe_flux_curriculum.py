#!/usr/bin/env python3
"""Generate and edit a tiny, catalogued FLUX curriculum probe."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from diffusers import Flux2KleinPipeline

from training.pipeline.visual.catalog import AssetCatalog, utc_now


PARENT_SHA256 = "00ab671e24fd150f84b6cf779abf5e527efcbdad9e00992aa73a227083a3be28"

CASES: list[dict[str, Any]] = [
    {
        "id": "generated_plain_dog",
        "mode": "generate",
        "prompt_style": "negative_heavy_narrative",
        "seed": 1701,
        "goal": "a dog",
        "prompt": (
            "Natural educational photograph of one young brown dog standing alone on short green "
            "grass, full body centered and clearly visible, simple uncluttered background, soft "
            "daylight. No people, no other animals, no objects, no text, no watermark."
        ),
        "search_terms": ["dog", "brown dog", "grass", "standing", "generated"],
    },
    {
        "id": "generated_dog_under_table_two_balls",
        "mode": "generate",
        "prompt_style": "negative_heavy_narrative",
        "seed": 1702,
        "goal": "the dog is under the table; exactly two red balls",
        "prompt": (
            "Natural educational photograph of exactly one brown dog lying clearly underneath a "
            "simple four-legged wooden table. Exactly two bright red balls lie side by side on the "
            "floor in front of the dog. Uncluttered room, full dog visible, no people, no other "
            "animals, no extra balls, no text, no watermark."
        ),
        "search_terms": ["dog", "under table", "two red balls", "in front of", "generated"],
    },
    {
        "id": "edited_add_two_red_balls",
        "mode": "edit",
        "prompt_style": "negative_heavy_narrative",
        "seed": 1703,
        "goal": "exactly two red balls are in front of the dog",
        "prompt": (
            "Edit this photograph while preserving the same dog, pose, stone ledge, lighting, and "
            "background. Add exactly two bright red balls resting on the ledge directly in front of "
            "the dog. Change nothing else. No text or watermark."
        ),
        "search_terms": ["dog", "two red balls", "in front of", "stone ledge", "edited"],
    },
    {
        "id": "edited_dog_under_table",
        "mode": "edit",
        "prompt_style": "negative_heavy_narrative",
        "seed": 1704,
        "goal": "the dog is under the table",
        "prompt": (
            "Edit this photograph into a simple indoor educational scene. Preserve the same dog's "
            "appearance and lying pose, and place the dog clearly underneath a plain four-legged "
            "wooden table. Remove the city background and ledge. No people, no other animals, no "
            "extra objects, no text, no watermark."
        ),
        "search_terms": ["dog", "under table", "indoors", "edited"],
    },
    {
        "id": "generated_plain_dog_positive",
        "mode": "generate",
        "prompt_style": "positive_narrative",
        "seed": 1701,
        "goal": "a dog",
        "prompt": (
            "One young brown dog stands alone on short green grass, its full body centered and "
            "clearly visible. A smooth softly blurred green field fills the background. Natural "
            "educational photography, soft daylight, anatomically correct, sharp focus."
        ),
        "search_terms": ["dog", "brown dog", "grass", "standing", "positive prompt", "generated"],
    },
    {
        "id": "generated_plain_dog_json",
        "mode": "generate",
        "prompt_style": "structured_json",
        "seed": 1701,
        "goal": "a dog",
        "prompt": (
            '{"scene":"an empty green field","subjects":[{"count":1,"description":"young brown dog",'
            '"position":"center","action":"standing with full body visible"}],"style":"natural educational '
            'photography","lighting":"soft daylight","background":"smooth uncluttered grass",'
            '"composition":"eye-level, centered, sharp focus"}'
        ),
        "search_terms": ["dog", "brown dog", "grass", "standing", "json prompt", "generated"],
    },
    {
        "id": "generated_relation_positive",
        "mode": "generate",
        "prompt_style": "positive_narrative",
        "seed": 1702,
        "goal": "the dog is under the table; exactly two red balls",
        "prompt": (
            "Exactly one brown dog lies underneath a simple four-legged wooden table. Exactly two "
            "bright red balls rest side by side on the floor directly in front of the dog's face. "
            "The room is empty and uncluttered. Natural educational photography, full dog visible, "
            "eye-level composition, sharp focus throughout."
        ),
        "search_terms": ["dog", "under table", "two red balls", "positive prompt", "generated"],
    },
    {
        "id": "generated_relation_json",
        "mode": "generate",
        "prompt_style": "structured_json",
        "seed": 1702,
        "goal": "the dog is under the table; exactly two red balls",
        "prompt": (
            '{"scene":"empty uncluttered room","subjects":[{"count":1,"description":"brown dog",'
            '"action":"lying","position":"clearly underneath a four-legged wooden table"},{"count":2,'
            '"description":"bright red balls","position":"side by side directly in front of the dog"}],'
            '"relations":["dog under table","two balls in front of dog"],"style":"natural educational '
            'photography","composition":"eye-level, full dog visible, sharp focus"}'
        ),
        "search_terms": ["dog", "under table", "two red balls", "json prompt", "generated"],
    },
    {
        "id": "edited_balls_concise",
        "mode": "edit",
        "prompt_style": "concise_edit",
        "seed": 1703,
        "goal": "exactly two red balls are in front of the dog",
        "prompt": (
            "Add exactly two bright red balls on the stone ledge directly in front of the dog. "
            "Keep the dog, pose, ledge, lighting, framing, and background unchanged."
        ),
        "search_terms": ["dog", "two red balls", "concise edit", "stone ledge", "edited"],
    },
    {
        "id": "edited_balls_json",
        "mode": "edit",
        "prompt_style": "structured_json_edit",
        "seed": 1703,
        "goal": "exactly two red balls are in front of the dog",
        "prompt": (
            '{"edit":{"action":"add","object":{"count":2,"description":"bright red balls"},'
            '"position":"on the stone ledge directly in front of the dog"},"preserve":["dog identity",'
            '"dog pose","stone ledge","lighting","framing","background"]}'
        ),
        "search_terms": ["dog", "two red balls", "json edit", "stone ledge", "edited"],
    },
    {
        "id": "edited_balls_total_positive",
        "mode": "edit",
        "prompt_style": "positive_total_edit",
        "seed": 1703,
        "goal": "exactly two red balls are in front of the dog",
        "prompt": (
            "Add bright red balls on the stone ledge directly in front of the dog. The final image "
            "contains a total of exactly two red balls. Keep the dog, pose, ledge, lighting, "
            "framing, and background unchanged."
        ),
        "search_terms": ["dog", "two red balls", "total count edit", "stone ledge", "edited"],
    },
]


def image_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, default=Path("tmp/vision/model_manifest.json"))
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--case-id", action="append", choices=[case["id"] for case in CASES])
    parser.add_argument("--seed-offset", type=int, default=0)
    parser.add_argument(
        "--offload-profile",
        choices=["sequential", "model"],
        default="sequential",
    )
    args = parser.parse_args()
    manifest = json.loads(args.model_manifest.read_text(encoding="utf-8"))
    model = manifest["models"]["flux4b"]
    catalog = AssetCatalog(args.catalog_root)
    parent = next(record for record in catalog.records() if record["asset_sha256"] == PARENT_SHA256)
    with Image.open(args.catalog_root / parent["object_path"]) as source:
        reference = source.convert("RGB")
    torch.cuda.reset_peak_memory_stats()
    load_started = time.monotonic()
    pipe = Flux2KleinPipeline.from_pretrained(
        model["snapshot_path"],
        local_files_only=True,
        torch_dtype=torch.float16,
    )
    if args.offload_profile == "model":
        pipe.enable_model_cpu_offload()
    else:
        pipe.enable_sequential_cpu_offload()
    pipe.vae.enable_slicing()
    pipe.vae.enable_tiling()
    load_seconds = time.monotonic() - load_started
    rows = []
    existing_by_sha256 = {record["asset_sha256"]: record for record in catalog.records()}
    selected_cases = [case for case in CASES if not args.case_id or case["id"] in args.case_id]
    for case in selected_cases:
        effective_seed = case["seed"] + args.seed_offset
        started = time.monotonic()
        options: dict[str, Any] = {
            "prompt": case["prompt"],
            "height": 384,
            "width": 512,
            "guidance_scale": 1.0,
            "num_inference_steps": 4,
            "generator": torch.Generator(device="cpu").manual_seed(effective_seed),
        }
        if case["mode"] == "edit":
            options["image"] = reference
        image = pipe(**options).images[0]
        if case["mode"] == "edit":
            family_id = parent["family_id"]
            split = parent["split"]
            source_kind = "edited"
            parent_sha256 = parent["asset_sha256"]
        else:
            family_id = f"flux-probe-20260731:{case['id']}"
            split = "qualification"
            source_kind = "generated"
            parent_sha256 = None
        payload = image_bytes(image)
        digest = hashlib.sha256(payload).hexdigest()
        asset_metadata = {
                "display_filename": f"flux_probe_{case['id']}_{effective_seed}.png",
                "family_id": family_id,
                "split": split,
                "description": {
                    "text": f"Unverified FLUX probe candidate intended to teach: {case['goal']}",
                    "status": "source_label_only",
                    "author": "flux_probe_plan",
                    "model_id": None,
                    "model_revision": None,
                },
                "search_terms": case["search_terms"],
                "facts": [],
                "claims": [{"text": case["goal"], "status": "candidate", "verified_by": []}],
                "source": {
                    "kind": source_kind,
                    "dataset": None,
                    "item_id": case["id"],
                    "license": "Apache-2.0",
                    "attribution": "Generated locally with black-forest-labs/FLUX.2-klein-4B",
                },
                "lineage": {
                    "parent_sha256": parent_sha256,
                    "model_id": model["repo_id"],
                    "model_revision": model["revision"],
                    "prompt": case["prompt"],
                    "seed": effective_seed,
                    "intended_delta": case["goal"],
                },
            }
        record = existing_by_sha256.get(digest)
        if record is not None:
            expected_lineage = asset_metadata["lineage"]
            if any(record["lineage"].get(key) != expected_lineage[key] for key in expected_lineage):
                raise RuntimeError(
                    f"deterministic output {digest} already has conflicting lineage metadata"
                )
        else:
            record = catalog.import_bytes(payload, asset_metadata, export_jsonl=False)
            existing_by_sha256[digest] = record
        rows.append(
            {
                "case_id": case["id"],
                "mode": case["mode"],
                "prompt_style": case["prompt_style"],
                "goal": case["goal"],
                "prompt": case["prompt"],
                "seed": effective_seed,
                "asset_sha256": record["asset_sha256"],
                "object_path": record["object_path"],
                "parent_sha256": parent_sha256,
                "seconds": round(time.monotonic() - started, 3),
            }
        )
    catalog.export_jsonl()
    report = {
        "schema_version": "ninereeds_flux_curriculum_probe_v1",
        "created_at": utc_now(),
        "model_id": model["repo_id"],
        "model_revision": model["revision"],
        "execution_profile": f"fp16-{args.offload_profile}-cpu-offload",
        "load_seconds": round(load_seconds, 3),
        "peak_cuda_allocated_gib": {
            str(index): round(torch.cuda.max_memory_allocated(index) / (1024**3), 3)
            for index in range(torch.cuda.device_count())
        },
        "cases": rows,
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
