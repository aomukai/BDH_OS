#!/usr/bin/env python3
"""Render a tiny grounded-story sequence with two FLUX reference strategies."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
from pathlib import Path
from typing import Any

import torch
from diffusers import Flux2KleinPipeline
from PIL import Image

from training.pipeline.visual.catalog import AssetCatalog, utc_now


CHARACTER_BIBLE = {
    "emma": (
        "Emma is an eight-year-old girl with a round freckled face, large brown eyes, "
        "and a chin-length wavy chestnut bob held by one yellow crescent hair clip on her left. "
        "She wears a mustard-yellow hooded raincoat, navy trousers, and blue rubber boots."
    ),
    "taro": (
        "Taro is an eight-year-old boy, the same age and height as Emma, with a narrow face, "
        "warm brown eyes, and straight black hair with a side-swept fringe. He wears a teal-blue "
        "hooded raincoat, rust-red trousers, and green rubber boots."
    ),
    "biscuit": (
        "Biscuit is a medium-sized sturdy brown dog with floppy ears, a slightly darker muzzle, "
        "warm brown eyes, a small white patch on his chest, and a plain red collar."
    ),
}

LOCATION_BIBLE = {
    "meadow_path": (
        "The Meadow Path is narrow and runs through long grass between Gran's garden gate and the "
        "pond. Dandelions, daisies, and clover grow at its edges; it becomes muddy after rain."
    ),
    "oak": (
        "The Oak is a very old broad oak at the edge of Gran's field, with rough deeply furrowed "
        "bark, one low child-high branch, and large raised roots with a squirrel hole between two."
    ),
}

STYLE = (
    "Warm hand-painted children's picture-book illustration, soft opaque gouache and colored "
    "pencil texture on lightly speckled paper, expressive natural faces, simple readable shapes, "
    "muted countryside palette, consistent proportions, landscape page, no writing or border."
)

PAGES = [
    {
        "id": "page_1_first_drops",
        "story_text": (
            "The sky darkened as Emma and Taro walked down the meadow path. A fat drop landed "
            "on Emma's nose. Biscuit lifted his snout toward the rain."
        ),
        "scene": (
            "Emma and Taro walk side by side down a meadow path beneath a darkening grey sky. "
            "One large raindrop lands on Emma's nose and she looks up in surprise. Biscuit walks "
            "beside them with his snout lifted. The narrow path runs through long grass with daisies, "
            "dandelions, and clover. Wide establishing view; all three full bodies visible."
        ),
    },
    {
        "id": "page_2_running",
        "story_text": (
            "The drops came faster. Emma's boots splashed through puddles. Taro slipped, caught "
            "himself, and ran faster."
        ),
        "scene": (
            "Rain falls hard on the meadow path. Emma runs through a shallow puddle, blue boots "
            "splashing. Taro is beside her, briefly off balance but catching himself. Biscuit trots "
            "behind them happily in the rain. The narrow path is bordered by long grass, daisies, "
            "dandelions, and clover. Dynamic side view; all three clearly visible."
        ),
    },
    {
        "id": "page_3_under_oak",
        "story_text": (
            "They ducked under the oak. A tiny stream trickled between its roots. Biscuit plopped "
            "down in it, and the children laughed as rain drummed on the leaves."
        ),
        "scene": (
            "Under the broad old oak with rough deeply furrowed bark and large raised roots, Emma "
            "and Taro crouch together laughing, wet from the rain. "
            "A tiny stream winds between the exposed roots, and Biscuit sits squarely in the water "
            "with muddy fur. Rain curtains the meadow beyond the sheltering branches."
        ),
    },
]


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, default=Path("tmp/vision/model_manifest.json"))
    parser.add_argument("--story", type=Path, default=Path("training_data/02_thinking/grounded_stories/story_05_EN.md"))
    parser.add_argument(
        "--world-bible",
        type=Path,
        default=Path("training/corpus_admin/grounded_stories/world_bible.md"),
    )
    parser.add_argument("--output-report", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.model_manifest.read_text(encoding="utf-8"))
    model = manifest["models"]["flux4b"]
    story_bytes = args.story.read_bytes()
    story_sha256 = hashlib.sha256(story_bytes).hexdigest()
    world_bible_sha256 = hashlib.sha256(args.world_bible.read_bytes()).hexdigest()
    catalog = AssetCatalog(args.catalog_root)
    existing = {record["asset_sha256"]: record for record in catalog.records()}

    torch.cuda.reset_peak_memory_stats()
    load_started = time.monotonic()
    pipe = Flux2KleinPipeline.from_pretrained(
        model["snapshot_path"], local_files_only=True, torch_dtype=torch.float16
    )
    pipe.enable_sequential_cpu_offload()
    pipe.vae.enable_slicing()
    pipe.vae.enable_tiling()
    load_seconds = time.monotonic() - load_started

    rows: list[dict[str, Any]] = []
    family_id = "grounded-story-picturebook:story-05:consistency-probe"

    def render(
        *,
        case_id: str,
        mode: str,
        prompt: str,
        seed: int,
        reference: Image.Image | None,
        parent_sha256: str | None,
        strategy: str,
        story_text: str | None,
    ) -> tuple[Image.Image, dict[str, Any]]:
        started = time.monotonic()
        options: dict[str, Any] = {
            "prompt": prompt,
            "height": 512,
            "width": 768,
            "guidance_scale": 1.0,
            "num_inference_steps": 4,
            "generator": torch.Generator(device="cpu").manual_seed(seed),
        }
        if reference is not None:
            options["image"] = reference
        image = pipe(**options).images[0]
        payload = png_bytes(image)
        digest = hashlib.sha256(payload).hexdigest()
        metadata = {
            "display_filename": f"story_05_{case_id}_{seed}.png",
            "family_id": family_id,
            "split": "qualification",
            "description": {
                "text": f"Unverified picture-book candidate for story 05: {story_text or 'cast anchor'}",
                "status": "source_label_only",
                "author": "flux_story_consistency_probe",
                "model_id": None,
                "model_revision": None,
            },
            "search_terms": [
                "grounded story 05", "Emma", "Taro", "Biscuit", "picture book", strategy, case_id
            ],
            "facts": [],
            "claims": [
                {"text": "Emma, Taro, and Biscuit retain their canonical identities", "status": "candidate", "verified_by": []}
            ],
            "source": {
                "kind": "generated",
                "dataset": "ninereeds-grounded-stories",
                "item_id": "story_05_EN",
                "license": "project-owned",
                "attribution": "NineReeds grounded story 05; generated locally with FLUX.2 Klein 4B",
            },
            "lineage": {
                "parent_sha256": parent_sha256,
                "model_id": model["repo_id"],
                "model_revision": model["revision"],
                "prompt": prompt,
                "seed": seed,
                "intended_delta": story_text or "canonical cast anchor",
            },
        }
        record = existing.get(digest)
        if record is None:
            record = catalog.import_bytes(payload, metadata, export_jsonl=False)
            existing[digest] = record
        row = {
            "case_id": case_id,
            "mode": mode,
            "strategy": strategy,
            "seed": seed,
            "seconds": round(time.monotonic() - started, 3),
            "asset_sha256": record["asset_sha256"],
            "object_path": record["object_path"],
            "parent_sha256": parent_sha256,
            "prompt": prompt,
            "story_text": story_text,
        }
        rows.append(row)
        return image, record

    bible = " ".join(CHARACTER_BIBLE.values())
    anchor_prompt = (
        f"Create the canonical cast reference for an original children's picture book. {bible} "
        "Show Emma standing on the left, Taro standing on the right, and Biscuit sitting between "
        "them, all facing the viewer, full bodies visible, relaxed neutral expressions, plain warm "
        f"cream background, no other characters or objects. {STYLE}"
    )
    anchor_image, anchor_record = render(
        case_id="cast_anchor",
        mode="generate",
        prompt=anchor_prompt,
        seed=5100,
        reference=None,
        parent_sha256=None,
        strategy="anchor_generation",
        story_text=None,
    )

    # Star topology: every page refers back to the clean cast anchor.
    for index, page in enumerate(PAGES, start=1):
        prompt = (
            f"Image 1 is the canonical cast reference. Create a new story illustration: {page['scene']} "
            "Preserve the exact identities from Image 1: Emma's face, freckles, chestnut bob and "
            "yellow crescent hair clip; Taro's face, black side-swept hair and shorter height; "
            "Biscuit's brown coat, darker muzzle, white chest patch, floppy ears and red collar. "
            "Preserve their clothing "
            f"colors and body proportions. Do not add, remove, merge, or duplicate characters. {STYLE}"
        )
        render(
            case_id=page["id"],
            mode="edit",
            prompt=prompt,
            seed=5100 + index,
            reference=anchor_image,
            parent_sha256=anchor_record["asset_sha256"],
            strategy="fixed_cast_anchor",
            story_text=page["story_text"],
        )

    # Chain topology: each page uses the previous page, which may accumulate drift.
    previous_image = anchor_image
    previous_record = anchor_record
    for index, page in enumerate(PAGES, start=1):
        prompt = (
            f"Continue the same original picture book from Image 1 with a new scene: {page['scene']} "
            "Keep exactly the same Emma, Taro, and Biscuit as Image 1. Preserve their faces, hair, "
            "relative ages and heights, clothing colors, body proportions, and Biscuit's markings "
            f"and red collar. Do not add, remove, merge, or duplicate characters. {STYLE}"
        )
        previous_image, previous_record = render(
            case_id=page["id"],
            mode="edit",
            prompt=prompt,
            seed=5200 + index,
            reference=previous_image,
            parent_sha256=previous_record["asset_sha256"],
            strategy="previous_page_chain",
            story_text=page["story_text"],
        )

    catalog.export_jsonl()
    report = {
        "schema_version": "ninereeds_flux_story_consistency_probe_v1",
        "created_at": utc_now(),
        "story_path": str(args.story),
        "story_sha256": story_sha256,
        "world_bible_path": str(args.world_bible),
        "world_bible_sha256": world_bible_sha256,
        "model_id": model["repo_id"],
        "model_revision": model["revision"],
        "execution_profile": "fp16-sequential-cpu-offload-768x512-4-steps",
        "load_seconds": round(load_seconds, 3),
        "peak_cuda_allocated_gib": {
            str(index): round(torch.cuda.max_memory_allocated(index) / (1024**3), 3)
            for index in range(torch.cuda.device_count())
        },
        "provisional_visual_character_bible": CHARACTER_BIBLE,
        "location_bible": LOCATION_BIBLE,
        "style_bible": STYLE,
        "cases": rows,
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
