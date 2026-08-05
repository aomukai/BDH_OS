#!/usr/bin/env python3
"""Verify the pinned visual-toolchain snapshots without network access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
from PIL import Image


def load_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "ninereeds_visual_model_manifest_v1":
        raise ValueError(f"unsupported visual model manifest: {path}")
    return manifest


def probe_siglip2(snapshot: str, full: bool) -> dict[str, Any]:
    from transformers import AutoConfig, AutoModel, AutoProcessor

    config = AutoConfig.from_pretrained(snapshot, local_files_only=True)
    processor = AutoProcessor.from_pretrained(snapshot, local_files_only=True)
    result: dict[str, Any] = {
        "model_type": config.model_type,
        "processor": type(processor).__name__,
    }
    if full:
        model = AutoModel.from_pretrained(
            snapshot,
            local_files_only=True,
            dtype=torch.float16,
        ).eval()
        image = Image.new("RGB", (320, 192), color=(196, 32, 32))
        inputs = processor(
            images=image,
            text=["a red rectangle"],
            padding="max_length",
            max_length=64,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = model(**inputs)
        result["logits_per_image_shape"] = list(outputs.logits_per_image.shape)
        result["full_load"] = True
    return result


def probe_gemma(snapshot: str, full: bool) -> dict[str, Any]:
    from transformers import AutoConfig, AutoModelForMultimodalLM, AutoProcessor

    config = AutoConfig.from_pretrained(snapshot, local_files_only=True)
    processor = AutoProcessor.from_pretrained(snapshot, local_files_only=True)
    result: dict[str, Any] = {
        "model_type": config.model_type,
        "processor": type(processor).__name__,
    }
    if full:
        # The current host's GPU is shared with the foundational bootstrap.
        # A deterministic CPU load proves the checkpoint without competing for
        # its 12 GiB VRAM. The eventual judge worker can use a qualified
        # quantized/device-map profile when it is scheduled independently.
        model = AutoModelForMultimodalLM.from_pretrained(
            snapshot,
            local_files_only=True,
            dtype=torch.bfloat16,
            device_map={"": "cpu"},
        ).eval()
        image = Image.new("RGB", (192, 192), color=(196, 32, 32))
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {
                        "type": "text",
                        "text": "Name the dominant color. Answer with one word.",
                    },
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
        input_length = inputs["input_ids"].shape[-1]
        with torch.no_grad():
            generated = model.generate(
                **inputs,
                max_new_tokens=4,
                do_sample=False,
            )
        answer = processor.decode(
            generated[0][input_length:],
            skip_special_tokens=True,
        ).strip()
        result["parameter_device_count"] = len(
            {str(parameter.device) for parameter in model.parameters()}
        )
        result["execution_profile"] = "bf16-cpu"
        result["answer"] = answer
        result["full_load"] = True
    return result


def probe_flux(snapshot: str, full: bool, output_dir: Path) -> dict[str, Any]:
    from diffusers import Flux2KleinPipeline

    result: dict[str, Any] = {
        "pipeline_class": Flux2KleinPipeline.__name__,
        "model_index_present": (Path(snapshot) / "model_index.json").is_file(),
    }
    if full:
        pipe = Flux2KleinPipeline.from_pretrained(
            snapshot,
            local_files_only=True,
            torch_dtype=torch.float16,
        )
        pipe.enable_sequential_cpu_offload()
        pipe.vae.enable_slicing()
        pipe.vae.enable_tiling()
        image = pipe(
            prompt="A single red ball on a plain white background.",
            height=512,
            width=512,
            guidance_scale=1.0,
            num_inference_steps=4,
            generator=torch.Generator(device="cpu").manual_seed(0),
        ).images[0]
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "flux4b_red_ball.png"
        image.save(output_path)
        result["generated_size"] = list(image.size)
        result["output_path"] = str(output_path.resolve())
        result["full_load"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("tmp/vision/model_manifest.json"),
    )
    parser.add_argument(
        "--model",
        choices=["all", "flux4b", "flux9b", "siglip2", "gemma", "gemma_e2b"],
        default="all",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="load model weights; FLUX also performs one 512px generation",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tmp/vision/probes"),
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    names = (
        tuple(manifest["models"])
        if args.model == "all"
        else (args.model,)
    )
    results: dict[str, Any] = {}
    for name in names:
        if name not in manifest["models"]:
            raise KeyError(f"{name} is not present in {args.manifest}")
        snapshot = manifest["models"][name]["snapshot_path"]
        if name.startswith("flux"):
            results[name] = probe_flux(snapshot, args.full, args.output_dir)
        elif name == "siglip2":
            results[name] = probe_siglip2(snapshot, args.full)
        elif name.startswith("gemma"):
            results[name] = probe_gemma(snapshot, args.full)
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
