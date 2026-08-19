"""Generate one resumable shard of Campaign 35 Flux production briefs on trainbox."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def seed_for(namespace: str, brief_id: str, variant: int) -> int:
    raw = hashlib.sha256(f"{namespace}:{brief_id}:{variant}".encode()).digest()
    return int.from_bytes(raw[:4], "big") & 0x7FFFFFFF


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--briefs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--gpu", type=int, required=True)
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--shards", type=int, required=True)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=384)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument(
        "--seed-namespace", default="campaign35",
        help="Stable namespace used to vary deterministic seeds between specialist cycles.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not 0 <= args.shard < args.shards or args.shards < 1:
        raise ValueError("invalid shard partition")

    import torch
    from PIL import Image
    from diffusers import Flux2KleinPipeline

    briefs = load_jsonl(args.briefs)
    selected = [row for index, row in enumerate(briefs) if index % args.shards == args.shard]
    args.output.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output / f"generation-shard-{args.shard:02d}.jsonl"
    completed = {
        (row["production_brief_id"], int(row["variant_index"]))
        for row in load_jsonl(ledger_path)
        if Path(row["local_path"]).is_file()
    } if ledger_path.exists() else set()

    pipe = Flux2KleinPipeline.from_pretrained(
        args.model, local_files_only=True, torch_dtype=torch.float16,
    )
    pipe.enable_sequential_cpu_offload(gpu_id=args.gpu)
    pipe.vae.enable_slicing()
    pipe.vae.enable_tiling()

    for brief in selected:
        brief_id = brief["production_brief_id"]
        base_path = args.output / f"{brief_id}-v00.png"
        for variant in range(int(brief["variant_count"])):
            key = (brief_id, variant)
            if key in completed:
                continue
            path = args.output / f"{brief_id}-v{variant:02d}.png"
            seed = seed_for(args.seed_namespace, brief_id, variant)
            evidence = "; ".join(
                f"{concept}: {description}"
                for concept, description in brief["evidence_by_concept"].items()
            )
            if variant == 0:
                mode = "generate"
                prompt = (
                    brief["flux_prompt_template"].strip()
                    + " Natural educational photograph, clear primary teaching evidence, simple coherent composition."
                    + " No labels, writing, logos, borders, collage panels, or watermarks."
                )
                parent = None
                options: dict[str, Any] = {}
            else:
                mode = "edit"
                axes = ", ".join(str(value) for value in brief["variation_axes"])
                prompt = (
                    "Create a distinct variation of this educational photograph. "
                    f"Vary only safe incidental properties from this list: {axes}. "
                    f"Preserve every teaching claim exactly: {evidence}. "
                    "Keep all target subjects and relations prominent, recognizable, and unambiguous. "
                    "Change nothing that would weaken a target claim. No labels, writing, logos, borders, "
                    "collage panels, or watermarks."
                )
                parent = str(base_path)
                if not base_path.is_file():
                    raise RuntimeError(f"base image is missing before edit: {base_path}")
                with Image.open(base_path) as source:
                    options = {"image": source.convert("RGB")}
                    image = pipe(
                        prompt=prompt, width=args.width, height=args.height,
                        num_inference_steps=args.steps, guidance_scale=1.0,
                        generator=torch.Generator(device="cpu").manual_seed(seed), **options,
                    ).images[0]
                image.save(path, format="PNG")
                record = {
                    "schema_version": "ninereeds_campaign35_flux_generation_v1",
                    "production_brief_id": brief_id, "variant_index": variant,
                    "mode": mode, "concept_ids": brief["concept_ids"],
                    "words": brief["concept_ids"],
                    "prompt": prompt, "seed": seed, "parent_path": parent,
                    "seed_namespace": args.seed_namespace,
                    "local_path": str(path), "sha256": digest(path),
                    "width": args.width, "height": args.height, "steps": args.steps,
                    "model": args.model, "gpu": args.gpu, "shard": args.shard,
                    "evidence_by_concept": brief["evidence_by_concept"],
                }
                with ledger_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                    handle.flush()
                print(f"completed {brief_id} variant={variant + 1}/{brief['variant_count']}", flush=True)
                continue

            image = pipe(
                prompt=prompt, width=args.width, height=args.height,
                num_inference_steps=args.steps, guidance_scale=1.0,
                generator=torch.Generator(device="cpu").manual_seed(seed), **options,
            ).images[0]
            image.save(path, format="PNG")
            record = {
                "schema_version": "ninereeds_campaign35_flux_generation_v1",
                "production_brief_id": brief_id, "variant_index": variant,
                "mode": mode, "concept_ids": brief["concept_ids"],
                "words": brief["concept_ids"],
                "prompt": prompt, "seed": seed, "parent_path": parent,
                "seed_namespace": args.seed_namespace,
                "local_path": str(path), "sha256": digest(path),
                "width": args.width, "height": args.height, "steps": args.steps,
                "model": args.model, "gpu": args.gpu, "shard": args.shard,
                "evidence_by_concept": brief["evidence_by_concept"],
            }
            with ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
            print(f"completed {brief_id} variant={variant + 1}/{brief['variant_count']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
