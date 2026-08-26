"""Keep Flux loaded and fulfill bounded Campaign 36 recommission requests."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Iterable


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if index != len(lines) - 1:
                raise
    return rows


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def seed_for(namespace: str, request_id: str) -> int:
    raw = hashlib.sha256(f"{namespace}:{request_id}".encode()).digest()
    return int.from_bytes(raw[:4], "big") & 0x7FFFFFFF


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--gpu", type=int, required=True)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=384)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--poll-seconds", type=float, default=10)
    parser.add_argument("--stop-file", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)

    import torch
    from diffusers import Flux2KleinPipeline

    args.output.mkdir(parents=True, exist_ok=True)
    ledger = args.output / "recommission-gpu0.jsonl"
    completed = {row["request_id"] for row in load_jsonl(ledger)}
    pipe = Flux2KleinPipeline.from_pretrained(
        args.model, local_files_only=True, torch_dtype=torch.float16,
    )
    pipe.enable_sequential_cpu_offload(gpu_id=args.gpu)
    pipe.vae.enable_slicing()
    pipe.vae.enable_tiling()

    while True:
        requests = load_jsonl(args.requests)
        pending = [row for row in requests if row["request_id"] not in completed]
        for request in pending:
            request_id = request["request_id"]
            seed = seed_for(request.get("seed_namespace", "campaign36-flux-recommission"), request_id)
            targets = "; ".join(
                f"{concept}: {description}"
                for concept, description in request.get("evidence_by_concept", {}).items()
            )
            prompt = (
                str(request["flux_prompt_template"]).strip()
                + " Create a fresh, distinct educational photograph; do not copy the rejected image. "
                + f"Correct this prior failure: {request['recommission_instruction']} "
                + f"Preserve these teaching claims exactly: {targets}. "
                + "Keep every target direct, salient, coherent, and unambiguous. Natural anatomy and "
                  "object integrity. No labels, writing, logos, borders, collage panels, or watermarks."
            )
            image = pipe(
                prompt=prompt, width=args.width, height=args.height,
                num_inference_steps=args.steps, guidance_scale=1.0,
                generator=torch.Generator(device="cpu").manual_seed(seed),
            ).images[0]
            path = args.output / f"{request_id}.png"
            image.save(path, format="PNG")
            record = {
                "schema_version": "ninereeds_campaign36_flux_recommission_generation_v1",
                "request_id": request_id,
                "production_brief_id": request["production_brief_id"],
                "variant_index": int(request["variant_index"]),
                "generation_attempt": int(request["generation_attempt"]),
                "concept_ids": request["concept_ids"], "words": request["words"],
                "evidence_by_concept": request.get("evidence_by_concept", {}),
                "flux_prompt_template": request["flux_prompt_template"],
                "prompt": prompt, "seed": seed,
                "seed_namespace": request.get("seed_namespace"),
                "rejected_sha256": request["rejected_sha256"],
                "failure_reasons": request["failure_reasons"],
                "recommission_instruction": request["recommission_instruction"],
                "local_path": str(path), "sha256": digest(path),
                "width": args.width, "height": args.height, "steps": args.steps,
                "model": args.model, "gpu": args.gpu,
            }
            with ledger.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
            completed.add(request_id)
            print(f"completed {request_id}", flush=True)
        if args.stop_file and args.stop_file.is_file() and not pending:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
