#!/usr/bin/env python3
"""Compare FLUX story pages with their cast anchor using Gemma vision."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from transformers import AutoModelForMultimodalLM, AutoProcessor

from training.pipeline.visual.catalog import AssetCatalog, utc_now


PROMPT = """Image 1 is the canonical cast reference for an original picture book.
Image 2 is a candidate story page. Compare only visible pixels. The cast should contain exactly
one Emma (girl with chestnut bob, freckles, yellow crescent hair clip, mustard raincoat and blue
boots), exactly one Taro (boy with black side-swept hair, teal raincoat and green boots), and
exactly one Biscuit (medium brown dog with floppy ears, darker muzzle, white chest patch and red
collar). Return one JSON object only with these keys:
emma_count (integer), taro_count (integer), dog_count (integer),
emma_identity_match (yes, no, or uncertain), taro_identity_match (yes, no, or uncertain),
biscuit_identity_match (yes, no, or uncertain), clothing_continuity (pass, fail, or uncertain),
style_continuity (pass, fail, or uncertain), obvious_duplicate_or_merged_character (boolean),
unrequested_symbol_or_text (boolean), overall (accept, reject, or review), reason (short string).
Reject any duplicated, missing, or merged cast member. Do not infer facts you cannot see."""


def json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("response contains no JSON object")
    value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("response JSON is not an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, default=Path("tmp/vision/model_manifest.json"))
    parser.add_argument("--story-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-new-tokens", type=int, default=256)
    args = parser.parse_args()

    model_manifest = json.loads(args.model_manifest.read_text(encoding="utf-8"))
    gemma = model_manifest["models"]["gemma_e2b"]
    snapshot = gemma["snapshot_path"]
    processor = AutoProcessor.from_pretrained(snapshot, local_files_only=True)
    model = AutoModelForMultimodalLM.from_pretrained(
        snapshot, local_files_only=True, dtype=torch.bfloat16, device_map={"": 0}
    ).eval()
    catalog = AssetCatalog(args.catalog_root)
    records = {record["asset_sha256"]: record for record in catalog.records()}
    story_report = json.loads(args.story_report.read_text(encoding="utf-8"))
    anchor_case = next(row for row in story_report["cases"] if row["case_id"] == "cast_anchor")
    anchor_record = records[anchor_case["asset_sha256"]]
    with Image.open(args.catalog_root / anchor_record["object_path"]) as source:
        anchor = source.convert("RGB")

    rows = []
    for case in story_report["cases"]:
        if case["case_id"] == "cast_anchor":
            continue
        record = records[case["asset_sha256"]]
        with Image.open(args.catalog_root / record["object_path"]) as source:
            candidate = source.convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": anchor},
                    {"type": "image", "image": candidate},
                    {"type": "text", "text": PROMPT},
                ],
            }
        ]
        inputs = processor.apply_chat_template(
            messages,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            add_generation_prompt=True,
            enable_thinking=False,
        ).to(model.device)
        length = inputs["input_ids"].shape[-1]
        started = time.monotonic()
        with torch.no_grad():
            generated = model.generate(
                **inputs, max_new_tokens=args.max_new_tokens, do_sample=False
            )
        seconds = time.monotonic() - started
        raw = processor.decode(generated[0][length:], skip_special_tokens=True).strip()
        try:
            judgement = json_object(raw)
            parse_ok = True
            error = None
        except (ValueError, json.JSONDecodeError) as exc:
            judgement = None
            parse_ok = False
            error = str(exc)
        rows.append(
            {
                "asset_sha256": case["asset_sha256"],
                "case_id": case["case_id"],
                "strategy": case["strategy"],
                "parse_ok": parse_ok,
                "judgement": judgement,
                "raw": raw,
                "error": error,
                "seconds": round(seconds, 3),
            }
        )

    report: dict[str, Any] = {
        "schema_version": "ninereeds_gemma_story_continuity_probe_v1",
        "created_at": utc_now(),
        "model_id": gemma["repo_id"],
        "model_revision": gemma["revision"],
        "execution_profile": "bf16-single-gpu-two-image-comparison",
        "anchor_sha256": anchor_case["asset_sha256"],
        "source_story_report": str(args.story_report),
        "mean_seconds_per_page": round(sum(row["seconds"] for row in rows) / len(rows), 3),
        "peak_cuda_allocated_gib": round(torch.cuda.max_memory_allocated(0) / (1024**3), 3),
        "items": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent, delete=False) as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
