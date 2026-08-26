"""Persistent trainbox FLUX.2 worker for Campaign 36 word-request spools."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def seed_for(request_id: str, variant: int, retry: int) -> int:
    value = hashlib.sha256(f"{request_id}:{variant}:{retry}".encode()).digest()
    return int.from_bytes(value[:4], "big") & 0x7FFFFFFF


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--gpu", type=int, choices=(0, 1), required=True)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=384)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--offload", choices=("sequential", "model"), default="sequential")
    parser.add_argument("--poll-seconds", type=float, default=5)
    parser.add_argument("--stop-file", type=Path)
    args = parser.parse_args()

    import torch
    from diffusers import Flux2KleinPipeline

    requests = args.root / "requests"
    results = args.root / "results"
    images = args.root / "images"
    requests.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    images.mkdir(parents=True, exist_ok=True)
    pipe = Flux2KleinPipeline.from_pretrained(
        args.model, local_files_only=True, torch_dtype=torch.float16
    )
    if args.offload == "model":
        pipe.enable_model_cpu_offload(gpu_id=args.gpu)
    else:
        pipe.enable_sequential_cpu_offload(gpu_id=args.gpu)
    pipe.vae.enable_slicing()
    pipe.vae.enable_tiling()
    print(f"flux worker gpu={args.gpu} ready", flush=True)

    while True:
        pending = [
            path
            for path in sorted(requests.glob("*.json"))
            if not (results / path.name).is_file()
        ]
        for request_path in pending:
            request = load(request_path)
            produced = []
            failures = []
            for variant in range(1, int(request["requested_count"]) + 1):
                for retry in range(1, int(request["attempts_per_needed"]) + 1):
                    identifier = f"{request['request_id']}-v{variant:02d}-r{retry:02d}"
                    target = images / f"{identifier}.png"
                    prompt = " ".join(
                        [
                            request["prompt"],
                            f"Distinct candidate {variant}; vary the setting, subject, viewpoint, or incidental appearance while preserving the exact teaching sense.",
                            f"Retry variation {retry}; create fresh pixels.",
                            "Natural educational photograph. Coherent anatomy and object structure. No labels, writing, logos, borders, collage panels, or watermarks.",
                        ]
                    )
                    try:
                        image = pipe(
                            prompt=prompt,
                            width=args.width,
                            height=args.height,
                            num_inference_steps=args.steps,
                            guidance_scale=1.0,
                            generator=torch.Generator(device="cpu").manual_seed(
                                seed_for(request["request_id"], variant, retry)
                            ),
                        ).images[0]
                        image.save(target, format="PNG")
                        produced.append(
                            {
                                "variant": variant,
                                "retry": retry,
                                "prompt": prompt,
                                "remote_path": str(target),
                                "sha256": sha256(target),
                                "width": args.width,
                                "height": args.height,
                            }
                        )
                        # Review happens on the main machine.  Generate one candidate per
                        # desired variant first; dispatcher feedback decides provider success.
                        break
                    except Exception as exc:
                        failures.append(
                            {
                                "variant": variant,
                                "retry": retry,
                                "type": type(exc).__name__,
                                "message": str(exc),
                            }
                        )
            atomic_json(
                results / request_path.name,
                {
                    "schema_version": "ninereeds_campaign36_replacement_flux_spool_v1",
                    "request": request,
                    "gpu": args.gpu,
                    "model": args.model,
                    "produced": produced,
                    "failures": failures,
                    "status": "generated" if produced else "generation_failed",
                },
            )
            print(
                f"completed {request['request_id']} images={len(produced)} failures={len(failures)}",
                flush=True,
            )
        if args.stop_file and args.stop_file.is_file() and not pending:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
