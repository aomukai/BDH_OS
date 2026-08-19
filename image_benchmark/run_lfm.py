from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

from image_benchmark.common import PROMPT, parse_response, semantic_contract_errors
from image_registry.cli import connect


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--selection", default="benchmark-100")
    parser.add_argument("--db", type=Path, default=Path("training_data/image_registry/registry.sqlite3"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--min-p", type=float)
    parser.add_argument("--repetition-penalty", type=float, default=1.05)
    args = parser.parse_args()

    completed: set[str] = set()
    if args.output.exists():
        for line in args.output.read_text(encoding="utf-8").splitlines():
            completed.add(json.loads(line)["source_id"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with connect(args.db) as db:
        rows = db.execute(
            """SELECT s.ordinal, a.source_id, a.local_path FROM selection s
               JOIN asset a ON a.id=s.asset_id WHERE s.name=? ORDER BY s.ordinal""",
            (args.selection,),
        ).fetchall()
    if args.limit is not None:
        rows = rows[:args.limit]

    load_start = time.perf_counter()
    model = AutoModelForImageTextToText.from_pretrained(
        args.model, dtype=torch.bfloat16
    ).to("cuda").eval()
    processor = AutoProcessor.from_pretrained(args.model)
    load_seconds = time.perf_counter() - load_start

    with args.output.open("a", encoding="utf-8", buffering=1) as output:
        for index, row in enumerate(rows, 1):
            if row["source_id"] in completed:
                continue
            with Image.open(row["local_path"]) as opened:
                image = opened.convert("RGB")
            messages = [{"role": "user", "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": PROMPT},
            ]}]
            inputs = processor.apply_chat_template(
                messages, add_generation_prompt=True, return_tensors="pt",
                return_dict=True, tokenize=True,
            ).to("cuda")
            torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            generation = {
                "max_new_tokens": 512,
                "do_sample": True,
                "temperature": args.temperature,
                "repetition_penalty": args.repetition_penalty,
            }
            if args.top_k is not None:
                generation["top_k"] = args.top_k
            if args.min_p is not None:
                generation["min_p"] = args.min_p
            with torch.inference_mode():
                generated = model.generate(**inputs, **generation)
            elapsed = time.perf_counter() - started
            new_tokens = generated[:, inputs["input_ids"].shape[1]:]
            raw = processor.batch_decode(new_tokens, skip_special_tokens=True)[0]
            parsed, errors = parse_response(raw)
            record = {
                "selection": args.selection,
                "ordinal": row["ordinal"],
                "source_id": row["source_id"],
                "model": args.model_name,
                "model_path": str(args.model),
                "prompt_version": "visual-audit-v1",
                "generation": generation,
                "load_seconds": load_seconds if index == 1 else None,
                "inference_seconds": elapsed,
                "peak_vram_bytes": torch.cuda.max_memory_allocated(),
                "generated_tokens": int(new_tokens.shape[1]),
                "raw": raw,
                "parsed": parsed,
                "schema_errors": errors,
                "semantic_contract_errors": semantic_contract_errors(parsed),
            }
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            print(f'{index}/{len(rows)} {row["source_id"]} {elapsed:.2f}s schema={"ok" if not errors else errors}')


if __name__ == "__main__":
    main()
