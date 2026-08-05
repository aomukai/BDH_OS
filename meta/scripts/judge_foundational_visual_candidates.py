#!/usr/bin/env python3
"""Run resumable blind Gemma observation and exact-goal review over a candidate receipt."""

from __future__ import annotations

import argparse
import fcntl
import json
import re
import tempfile
import threading
import time
from queue import Queue
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from transformers import AutoModelForMultimodalLM, AutoProcessor

from training.pipeline.visual.catalog import AssetCatalog, utc_now


BLIND_PROMPT = """Describe this image literally for a searchable educational image catalog.
Do not infer hidden details. Return one JSON object only with exactly these keys:
description (one thorough sentence), primary_subject (short noun phrase or uncertain),
primary_subject_count (integer or null), colors (array), visible_objects (array),
spatial_relations (array of literal phrases), setting (short string), distraction (low, medium, high),
blur (none, mild, severe), occlusion (none, mild, severe), unwanted_text_or_watermark (boolean),
malformation (none, possible, clear), uncertainty (array). Report only visibly supported facts."""

RUBRIC_PROMPT = """The exact teaching goal is {goal}. A blind observer described the image as:
{description}
Judge the pixels and the exact goal. Return one JSON object only with exactly these keys:
decision (accept, reject, review), content_match (boolean), primary_subject_prominent (boolean),
single_clear_primary_subject (boolean), cleanliness (pass, fail), correctness (pass, fail, uncertain),
concise_reason (string), preserved_visible_facts (array). Accept only when this is a clean,
unambiguous example of the requested concept; uncertainty requires review, not acceptance."""


def json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("response contains no JSON object")
    value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("response JSON is not an object")
    return value


def ask(model, processor, image: Image.Image, prompt: str, maximum: int) -> tuple[dict[str, Any], str, float]:
    messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
    inputs = processor.apply_chat_template(
        messages, tokenize=True, return_dict=True, return_tensors="pt",
        add_generation_prompt=True, enable_thinking=False,
    ).to(model.device)
    prefix = inputs["input_ids"].shape[-1]
    started = time.monotonic()
    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=maximum, do_sample=False)
    raw = processor.decode(generated[0][prefix:], skip_special_tokens=True).strip()
    return json_object(raw), raw, time.monotonic() - started


def hard_gates(blind: dict[str, Any], rubric: dict[str, Any]) -> list[str]:
    reasons = []
    if blind.get("unwanted_text_or_watermark") is not False:
        reasons.append("text_or_watermark")
    if blind.get("blur") == "severe":
        reasons.append("severe_blur")
    if blind.get("occlusion") == "severe":
        reasons.append("severe_occlusion")
    if blind.get("malformation") != "none":
        reasons.append("possible_malformation")
    if blind.get("distraction") == "high":
        reasons.append("high_distraction")
    if rubric.get("content_match") is not True:
        reasons.append("content_mismatch")
    if rubric.get("single_clear_primary_subject") is not True:
        reasons.append("ambiguous_primary_subject")
    if rubric.get("cleanliness") != "pass":
        reasons.append("cleanliness_failure")
    if rubric.get("correctness") != "pass":
        reasons.append("correctness_not_pass")
    return reasons


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def judge_candidate(model, processor, image_path: Path, candidate: dict[str, Any], record: dict[str, Any], maximum: int) -> dict[str, Any]:
    with Image.open(image_path) as source:
        image = source.convert("RGB")
    row: dict[str, Any] = {
        "asset_sha256": candidate["asset_sha256"], "display_filename": record["display_filename"],
        "item_id": candidate["item_id"], "concept_id": candidate["concept_id"],
        "teaching_goal": candidate["canonical_caption"],
    }
    try:
        blind, blind_raw, first_seconds = ask(model, processor, image, BLIND_PROMPT, maximum)
        rubric, rubric_raw, second_seconds = ask(
            model, processor, image,
            RUBRIC_PROMPT.format(goal=repr(candidate["canonical_caption"]), description=blind.get("description", "")),
            maximum,
        )
        gates = hard_gates(blind, rubric)
        row.update({
            "parse_ok": True, "blind": blind, "rubric": rubric,
            "blind_raw": blind_raw, "rubric_raw": rubric_raw, "hard_gate_reasons": gates,
            "effective_decision": "reject" if gates else rubric.get("decision", "review"),
            "seconds": round(first_seconds + second_seconds, 3),
        })
    except (ValueError, json.JSONDecodeError, RuntimeError) as exc:
        row.update({"parse_ok": False, "error": str(exc), "hard_gate_reasons": [], "effective_decision": "review"})
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, default=Path("tmp/vision/model_manifest.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge-model", choices=["gemma_e2b", "gemma"], default="gemma_e2b")
    parser.add_argument("--device-profile", choices=["bf16-single-gpu", "bf16-cpu", "int8-single-gpu"], default="bf16-single-gpu")
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--workers", type=int, choices=[1, 2], default=1)
    parser.add_argument("--lock-file", type=Path, default=Path("/home/aomukai/.local/state/ninereeds-control/worker/trainbox-worker.lock"))
    args = parser.parse_args()

    args.lock_file.parent.mkdir(parents=True, exist_ok=True)
    worker_lock = args.lock_file.open("a+")
    try:
        fcntl.flock(worker_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        worker_lock.close()
        raise RuntimeError("trainbox worker lock is already held") from exc

    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    manifest = json.loads(args.model_manifest.read_text(encoding="utf-8"))
    judge = manifest["models"][args.judge_model]
    if args.output.exists():
        output = json.loads(args.output.read_text(encoding="utf-8"))
        if output.get("source_receipt") != str(args.receipt.resolve()):
            raise ValueError("existing judge report belongs to another receipt")
    else:
        output = {
            "schema_version": "ninereeds_foundational_visual_judge_v1",
            "created_at": utc_now(), "updated_at": utc_now(),
            "source_receipt": str(args.receipt.resolve()), "model_id": judge["repo_id"],
            "model_revision": judge["revision"], "execution_profile": args.device_profile,
            "worker_count": args.workers,
            "rubric_version": "foundation-single-concept-v1", "items": [],
            "failed_attempts": [],
        }
    output["worker_count"] = args.workers
    output.setdefault("failed_attempts", [])
    prior_failures = {}
    for row in output["failed_attempts"]:
        prior_failures[row["asset_sha256"]] = prior_failures.get(row["asset_sha256"], 0) + 1
    retryable_rows = [
        row for row in output["items"]
        if not row.get("parse_ok", False) and prior_failures.get(row["asset_sha256"], 0) < 1
    ]
    if retryable_rows:
        retryable_hashes = {row["asset_sha256"] for row in retryable_rows}
        output["failed_attempts"].extend(retryable_rows)
        output["items"] = [row for row in output["items"] if row["asset_sha256"] not in retryable_hashes]
        atomic_json(args.output, output)
    done = {row["asset_sha256"] for row in output["items"]}
    pending = [row for row in receipt["items"].values() if row["asset_sha256"] not in done]
    if args.max_items is not None:
        pending = pending[:args.max_items]
    if not pending:
        print(json.dumps({"output": str(args.output.resolve()), "new_items": 0}))
        return 0

    if args.workers == 2 and args.device_profile != "bf16-single-gpu":
        parser.error("two workers require the qualified bf16-single-gpu profile")
    options: dict[str, Any] = {}
    if args.device_profile == "int8-single-gpu":
        from transformers import BitsAndBytesConfig
        options["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
    worker_models = []
    for worker_index in range(args.workers):
        processor = AutoProcessor.from_pretrained(judge["snapshot_path"], local_files_only=True)
        device_map: Any = {"": worker_index} if args.device_profile != "bf16-cpu" else {"": "cpu"}
        model = AutoModelForMultimodalLM.from_pretrained(
            judge["snapshot_path"], local_files_only=True, dtype=torch.bfloat16,
            device_map=device_map, **options,
        ).eval()
        worker_models.append((model, processor))
    catalog = AssetCatalog(args.catalog_root)
    records = {record["asset_sha256"]: record for record in catalog.records()}
    queue: Queue[dict[str, Any] | None] = Queue()
    def run_worker(worker_index: int) -> None:
        model, processor = worker_models[worker_index]
        try:
            for candidate in pending[worker_index::args.workers]:
                record = records[candidate["asset_sha256"]]
                queue.put(judge_candidate(
                    model, processor, args.catalog_root / record["object_path"],
                    candidate, record, args.max_new_tokens,
                ))
        except Exception as exc:
            queue.put({"_worker_error": f"worker {worker_index}: {type(exc).__name__}: {exc}"})
        finally:
            queue.put(None)

    threads = [threading.Thread(target=run_worker, args=(index,), daemon=False) for index in range(args.workers)]
    for thread in threads:
        thread.start()
    finished = 0
    worker_errors = []
    while finished < len(threads):
        row = queue.get()
        if row is None:
            finished += 1
            continue
        if "_worker_error" in row:
            worker_errors.append(row["_worker_error"])
            continue
        output["items"].append(row)
        output["updated_at"] = utc_now()
        atomic_json(args.output, output)
    for thread in threads:
        thread.join()
    if worker_errors:
        raise RuntimeError("; ".join(worker_errors))
    parsed = [row for row in output["items"] if row["parse_ok"]]
    output["metrics"] = {
        "sample_size": len(output["items"]),
        "parse_success_fraction": round(len(parsed) / len(output["items"]), 6),
        "mean_seconds_per_image": round(sum(row.get("seconds", 0) for row in output["items"]) / len(output["items"]), 3),
        "effective_decisions": {
            decision: sum(row.get("effective_decision") == decision for row in output["items"])
            for decision in ("accept", "review", "reject")
        },
    }
    atomic_json(args.output, output)
    print(json.dumps({"output": str(args.output.resolve()), **output["metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
