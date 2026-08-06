#!/usr/bin/env python3
"""Offline, bounded trainbox runtime for Mission Hub visual stages.

The parent handler owns routing, timeouts, artifact declarations, and fallback.
This process loads exactly one pinned local model and never downloads weights.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any

from mission_hub.schema import load_schema, validate


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model response contains no JSON object")
    value = json.loads(cleaned[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("model response is not a JSON object")
    return value


def snapshot(model_id: str, revision: str, weights_root: str) -> str:
    """Accept only the explicitly configured immutable local snapshot path."""
    path = Path(weights_root).resolve()
    if not path.is_dir() or path.name != revision or path.parent.name != "snapshots":
        raise OSError(f"pinned local snapshot is unavailable for {model_id}@{revision}: {path}")
    if not (path / "config.json").is_file() and not (path / "model_index.json").is_file():
        raise OSError(f"pinned local snapshot has no model configuration: {path}")
    return str(path)


def output(kind: str, path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    return {"kind": kind, "uri": str(path.resolve()), "sha256": sha256(path), "manifest": manifest}


def bounds(request: dict[str, Any]) -> dict[str, Any]:
    configured = request["configured_limits"]
    supplied = request.get("request_limits", {})
    result = dict(configured)
    for key in ("max_candidates_per_item", "max_width", "max_height", "max_generation_steps", "max_pack_items"):
        if key in supplied:
            value = supplied[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{key} must be a positive integer")
            result[key] = min(value, configured[key])
    return result


def generate(request: dict[str, Any], model_id: str, revision: str, model_path: str, root: Path, device: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import torch
    from diffusers import Flux2KleinPipeline

    limits = bounds(request)
    plans = [item for item in request["inputs"] if item["kind"] == "visual_plan"]
    if len(plans) != 1:
        raise ValueError("visual generation requires exactly one visual plan")
    specification = json.loads(Path(plans[0]["uri"]).read_text(encoding="utf-8"))
    items = specification.get("items")
    if not isinstance(items, list) or not items or len(items) > limits["max_pack_items"]:
        raise ValueError("visual generation requires a bounded non-empty items list")
    pipe = Flux2KleinPipeline.from_pretrained(model_path, local_files_only=True, torch_dtype=torch.float16)
    if not re.fullmatch(r"cuda:\d+", device):
        raise ValueError("FLUX runtime requires an explicit cuda:N device")
    gpu_id = int(device.split(":", 1)[1])
    offload = request["specification"].get("offload_profile", "sequential")
    if offload == "model":
        pipe.enable_model_cpu_offload(gpu_id=gpu_id)
    elif offload == "sequential":
        pipe.enable_sequential_cpu_offload(gpu_id=gpu_id)
    else:
        raise ValueError("offload_profile must be sequential or model")
    pipe.vae.enable_slicing()
    pipe.vae.enable_tiling()
    outputs, report_items = [], []
    total_bytes = 0
    for item in items:
        item_id = str(item.get("item_id") or "").strip()
        prompt = str(item.get("prompt") or "").strip()
        if not item_id or not prompt:
            raise ValueError("every generation item requires item_id and prompt")
        seeds = item.get("seeds", [item.get("seed", 0)])
        if not isinstance(seeds, list) or not seeds or len(seeds) > limits["max_candidates_per_item"]:
            raise ValueError("generation seeds exceed the candidate bound")
        width = int(item.get("width", specification.get("width", 1024)))
        height = int(item.get("height", specification.get("height", 1024)))
        steps = int(item.get("steps", specification.get("steps", 4)))
        if width < 64 or height < 64 or width > limits["max_width"] or height > limits["max_height"] or steps < 1 or steps > limits["max_generation_steps"]:
            raise ValueError("generation dimensions or steps exceed configured bounds")
        for seed in seeds:
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise ValueError("generation seeds must be integers")
            started = time.monotonic()
            image = pipe(
                prompt=prompt, width=width, height=height, num_inference_steps=steps,
                guidance_scale=float(item.get("guidance_scale", specification.get("guidance_scale", 3.5))),
                generator=torch.Generator(device="cpu").manual_seed(seed),
            ).images[0]
            path = root / f"candidate-{len(report_items):04d}.png"
            image.save(path, format="PNG")
            total_bytes += path.stat().st_size
            if total_bytes > limits["max_pack_bytes"]:
                raise ValueError("generated candidates exceed configured byte ceiling")
            manifest = {
                "schema_version": "ninereeds_visual_candidate_v1", "item_id": item_id,
                "prompt": prompt, "seed": seed, "width": width, "height": height,
                "steps": steps, "guidance_scale": float(item.get("guidance_scale", specification.get("guidance_scale", 3.5))),
                "source_kind": "generated", "status": "candidate_unreviewed",
            }
            outputs.append(output("visual_candidate", path, manifest))
            report_items.append({**manifest, "sha256": sha256(path), "byte_size": path.stat().st_size, "seconds": round(time.monotonic() - started, 3)})
    report = root / "generation-report.json"
    report.write_text(json.dumps({
        "schema_version": "ninereeds_visual_generation_report_v1", "model_id": model_id,
        "model_revision": revision, "items": report_items,
    }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    outputs.append(output("visual_generation_report", report, {"candidate_count": len(report_items)}))
    return outputs, {"candidates": len(report_items), "candidate_bytes": total_bytes}


def ask(model: Any, processor: Any, image: Any, prompt: str, maximum: int) -> tuple[dict[str, Any], str]:
    import torch
    messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
    inputs = processor.apply_chat_template(
        messages, tokenize=True, return_dict=True, return_tensors="pt",
        add_generation_prompt=True, enable_thinking=False,
    ).to(model.device)
    prefix = inputs["input_ids"].shape[-1]
    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=maximum, do_sample=False)
    raw = processor.decode(generated[0][prefix:], skip_special_tokens=True).strip()
    return json_object(raw), raw


def vision_language(request: dict[str, Any], stage: str, model_id: str, revision: str, model_path: str, root: Path, device: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import torch
    from PIL import Image
    from transformers import AutoModelForMultimodalLM, AutoProcessor

    candidates = [item for item in request["inputs"] if item["kind"] == "visual_candidate"]
    candidate_bound = request["configured_limits"]["max_pack_items"] * request["configured_limits"]["max_candidates_per_item"]
    if not candidates or len(candidates) > candidate_bound:
        raise ValueError(f"{stage} requires bounded visual candidates")
    processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForMultimodalLM.from_pretrained(
        model_path, local_files_only=True, dtype=torch.bfloat16, device_map={"": device},
    ).eval()
    configured_prompt = request.get("prompt") or {}
    system = configured_prompt.get("system", "Describe only visibly supported facts as one JSON object.")
    maximum = min(int(request.get("request_limits", {}).get("max_new_tokens", 512)), 2048)
    rows, transcripts = [], []
    for candidate in candidates:
        with Image.open(candidate["uri"]) as source:
            image = source.convert("RGB")
        if image.width > request["configured_limits"]["max_width"] or image.height > request["configured_limits"]["max_height"]:
            raise ValueError("input image exceeds configured dimensions")
        if stage == "visual.inspect":
            task = "\nReturn one JSON object with exactly: description, primary_subject, primary_subject_count (integer or null), colors (array), visible_objects (array), spatial_relations (array), distraction (low/medium/high), blur (none/mild/severe), occlusion (none/mild/severe), unwanted_text_or_watermark (boolean), malformation (none/possible/clear), uncertainty (array), proposed_decision (accept/review/reject)."
        else:
            task = "\nReturn one JSON object with exactly: accessibility_caption (string), teaching_caption (string), preserved_visible_facts (array), and uncertainty (array). Do not add facts that are not visible."
        parsed, raw = ask(model, processor, image, system + task + "\nSpecification: " + json.dumps(request["specification"], ensure_ascii=False), maximum)
        schema_name = configured_prompt.get("output_schema")
        if not schema_name:
            raise ValueError(f"{stage} has no configured response schema")
        errors = validate(parsed, load_schema(Path(__file__).resolve().parents[2], schema_name))
        if errors:
            raise ValueError("vision-language output failed schema validation: " + "; ".join(errors))
        rows.append({"asset_sha256": candidate["sha256"], "result": parsed})
        transcripts.append({"asset_sha256": candidate["sha256"], "raw": raw})
    report_kind = "visual_inspection_report" if stage == "visual.inspect" else "visual_caption_report"
    report_path = root / ("inspection-report.json" if stage == "visual.inspect" else "caption-report.json")
    report_path.write_text(json.dumps({"schema_version": f"ninereeds_{stage.replace('.', '_')}_v1", "items": rows}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    transcript_path = root / "provider-transcript.json"
    transcript_path.write_text(json.dumps({"schema_version": "ninereeds_provider_transcript_v1", "items": transcripts}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return [
        output(report_kind, report_path, {"item_count": len(rows)}),
        output("provider_transcript", transcript_path, {"item_count": len(rows)}),
    ], {"items": len(rows)}


def encode(request: dict[str, Any], model_id: str, revision: str, model_path: str, root: Path, device: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import numpy as np
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor

    candidates = [item for item in request["inputs"] if item["kind"] == "visual_candidate"]
    packs = [item for item in request["inputs"] if item["kind"] == "visual_pack"]
    if len(packs) != 1 or packs[0]["manifest"].get("status") != "accepted":
        raise ValueError("visual encoding requires exactly one accepted pack")
    accepted = {item["asset_sha256"] for item in packs[0]["manifest"].get("items", [])}
    if not candidates or {item["sha256"] for item in candidates} != accepted:
        raise ValueError("encoder inputs must exactly match the accepted pack")
    processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
    model = AutoModel.from_pretrained(model_path, local_files_only=True).to(device).eval()
    arrays: dict[str, Any] = {}
    hashes = []
    receptor = getattr(model, "vision_model", model)
    for index, candidate in enumerate(sorted(candidates, key=lambda item: item["sha256"])):
        with Image.open(candidate["uri"]) as source:
            image = source.convert("RGB")
        inputs = processor(images=image, return_tensors="pt").to(device)
        with torch.no_grad():
            encoded = receptor(
                pixel_values=inputs["pixel_values"],
                pixel_attention_mask=inputs["pixel_attention_mask"],
                spatial_shapes=inputs["spatial_shapes"], return_dict=True,
            )
        arrays[f"patch_{index:04d}"] = encoded.last_hidden_state.detach().float().cpu().numpy()[0]
        arrays[f"mask_{index:04d}"] = inputs["pixel_attention_mask"].detach().cpu().numpy()[0]
        arrays[f"shape_{index:04d}"] = inputs["spatial_shapes"].detach().cpu().numpy()[0]
        hashes.append(candidate["sha256"])
    feature_path = root / "visual-features.npz"
    np.savez_compressed(feature_path, asset_sha256=np.asarray(hashes), **arrays)
    first_width = int(arrays["patch_0000"].shape[-1])
    manifest = {
        "schema_version": "ninereeds_visual_features_v1", "asset_sha256": hashes,
        "count": len(hashes), "format": "npz-no-pickle", "feature_kind": "siglip2_last_hidden_state",
        "feature_width": first_width, "includes_patch_mask": True, "includes_spatial_shapes": True,
    }
    return [output("visual_features", feature_path, manifest)], {"items": len(hashes), "feature_width": first_width}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--weights-root", required=True, help="Exact pinned local snapshot directory")
    parser.add_argument("--device", required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if request.get("schema_version") != "ninereeds_visual_runtime_request_v1":
        raise ValueError("unsupported visual runtime request")
    args.result.parent.mkdir(parents=True, exist_ok=True)
    free_bytes = __import__("shutil").disk_usage(args.result.parent).free
    if free_bytes < request["configured_limits"]["minimum_free_bytes"]:
        raise RuntimeError("visual runtime has less free disk than the configured safety floor")
    model_path = snapshot(args.model_id, args.revision, args.weights_root)
    stage = request["stage"]
    if stage == "visual.generate":
        outputs, metrics = generate(request, args.model_id, args.revision, model_path, args.result.parent, args.device)
    elif stage in {"visual.inspect", "visual.caption"}:
        outputs, metrics = vision_language(request, stage, args.model_id, args.revision, model_path, args.result.parent, args.device)
    elif stage == "visual.encode":
        outputs, metrics = encode(request, args.model_id, args.revision, model_path, args.result.parent, args.device)
    else:
        raise ValueError(f"unsupported visual stage: {stage}")
    args.result.write_text(json.dumps({
        "schema_version": "ninereeds_visual_runtime_result_v1", "stage": stage,
        "outputs": outputs, "metrics": metrics,
    }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"invalid visual request: {exc}", file=__import__("sys").stderr)
        raise SystemExit(65)
    except OSError as exc:
        print(f"visual capability unavailable: {exc}", file=__import__("sys").stderr)
        raise SystemExit(69)
    except RuntimeError as exc:
        message = str(exc)
        transient = any(marker in message.lower() for marker in ("out of memory", "cuda", "not found in the cached files"))
        print(f"visual runtime failure: {message}", file=__import__("sys").stderr)
        raise SystemExit(69 if transient else 70)
