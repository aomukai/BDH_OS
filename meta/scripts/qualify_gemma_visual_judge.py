#!/usr/bin/env python3
"""Probe the pinned Gemma visual judge on a reserved Oxford Pet slice."""

from __future__ import annotations

import argparse
import json
import logging
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from transformers import AutoModelForMultimodalLM, AutoProcessor

from training.pipeline.visual.catalog import AssetCatalog, utc_now


BLIND_PROMPT = """Describe this image literally for an educational image catalog.
Do not guess hidden or uncertain details. Return one JSON object only with these keys:
description (one thorough sentence), primary_species (cat, dog, other, or uncertain),
primary_subject_count (integer or null), colors (array), visible_objects (array),
spatial_relations (array of short literal phrases), setting (short string),
distraction (low, medium, or high), blur (none, mild, or severe),
occlusion (none, mild, or severe), unwanted_text_or_watermark (boolean),
malformation (none, possible, or clear), uncertainty (array of short strings).
Only report facts supported by visible pixels."""

RUBRIC_PROMPT = """The proposed teaching goal is {claim}. Judge whether this photograph is a
clean training example for that exact claim. It should show the target prominently, avoid
misleading extra subjects and excessive distraction, and have no severe blur, occlusion,
watermark, text, or visible malformation. A prior blind catalog description was:
{description}
Return one JSON object only with: decision (accept, reject, or review), content_match
(boolean), single_primary_subject (boolean), cleanliness (pass or fail), correctness
(pass, fail, or uncertain), concise_reason (string), and preserved_visible_facts (array)."""

SPECIES_PROMPT = "Is the primary animal in this image a cat or a dog? Answer cat, dog, or other."


class ResponseParseError(ValueError):
    def __init__(self, message: str, raw: str, seconds: float) -> None:
        super().__init__(message)
        self.raw = raw
        self.seconds = seconds


def json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("response contains no JSON object")
    value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("response JSON is not an object")
    return value


def ask(model, processor, image: Image.Image, prompt: str, max_new_tokens: int) -> tuple[dict[str, Any], str, float]:
    messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]}]
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
        generated = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    seconds = time.monotonic() - started
    raw = processor.decode(generated[0][length:], skip_special_tokens=True).strip()
    try:
        value = json_object(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ResponseParseError(str(exc), raw, seconds) from exc
    return value, raw, seconds


def hard_gate_reasons(blind: dict[str, Any], expected_species: str) -> list[str]:
    reasons = []
    if blind.get("primary_species") != expected_species:
        reasons.append("wrong_or_uncertain_species")
    if blind.get("primary_subject_count") != 1:
        reasons.append("not_one_primary_subject")
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
    return reasons


def ask_species(model, processor, image: Image.Image) -> tuple[str, str, float]:
    messages = [{"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": SPECIES_PROMPT}]}]
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
        generated = model.generate(**inputs, max_new_tokens=4, do_sample=False)
    seconds = time.monotonic() - started
    raw = processor.decode(generated[0][length:], skip_special_tokens=True).strip()
    match = re.search(r"\b(cat|dog|other)\b", raw.casefold())
    return (match.group(1) if match else "unparsed"), raw, seconds


def source_species(record: dict[str, Any]) -> str:
    for claim in record["claims"]:
        if claim["text"] in {"a cat", "a dog"}:
            return claim["text"].split()[1]
    mentioned = {
        species
        for claim in record["claims"]
        for species in ("cat", "dog")
        if re.search(rf"\b{species}\b", claim["text"], flags=re.IGNORECASE)
    }
    if len(mentioned) == 1:
        return mentioned.pop()
    raise ValueError(f"asset lacks source species claim: {record['asset_sha256']}")


def teaching_goal(record: dict[str, Any], expected_species: str) -> str:
    for claim in record["claims"]:
        if claim.get("status") == "candidate":
            return claim["text"]
    for claim in record["claims"]:
        if claim["text"] in {"a cat", "a dog"}:
            return claim["text"]
    return f"a {expected_species}"


def selected_records(
    catalog: AssetCatalog,
    per_species: int,
    asset_sha256: list[str] | None = None,
) -> list[dict[str, Any]]:
    if asset_sha256:
        requested = set(asset_sha256)
        selected = [record for record in catalog.records() if record["asset_sha256"] in requested]
        found = {record["asset_sha256"] for record in selected}
        if found != requested:
            raise ValueError("requested assets are missing from the catalog: " + ", ".join(sorted(requested - found)))
        return sorted(selected, key=lambda record: asset_sha256.index(record["asset_sha256"]))
    selected: dict[str, list[dict[str, Any]]] = {"cat": [], "dog": []}
    for record in catalog.records():
        if record["split"] != "qualification" or record["source"]["kind"] != "dataset":
            continue
        species = source_species(record)
        if len(selected[species]) < per_species:
            selected[species].append(record)
    if any(len(records) != per_species for records in selected.values()):
        raise ValueError("qualification catalog does not contain enough cats and dogs")
    return [item for species in ("cat", "dog") for item in selected[species]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, default=Path("tmp/vision/model_manifest.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-species", type=int, default=5)
    parser.add_argument(
        "--asset-sha256",
        action="append",
        help="inspect an exact asset; repeat for a check-again batch",
    )
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--one-pass", action="store_true")
    parser.add_argument("--species-only", action="store_true")
    parser.add_argument(
        "--device-profile",
        choices=["bf16-cpu", "bf16-single-gpu", "bf16-dual-gpu", "int8-single-gpu", "nf4-single-gpu"],
        default="bf16-cpu",
    )
    parser.add_argument("--judge-model", choices=["gemma", "gemma_e2b"], default="gemma")
    args = parser.parse_args()
    if args.per_species <= 0:
        parser.error("--per-species must be positive")
    model_manifest = json.loads(args.model_manifest.read_text(encoding="utf-8"))
    gemma = model_manifest["models"][args.judge_model]
    snapshot = gemma["snapshot_path"]
    processor = AutoProcessor.from_pretrained(snapshot, local_files_only=True)
    device_map: Any = {"": "cpu"}
    load_options: dict[str, Any] = {}
    if args.device_profile == "bf16-single-gpu":
        device_map = {"": 0}
    elif args.device_profile in {"int8-single-gpu", "nf4-single-gpu"}:
        from transformers import BitsAndBytesConfig

        device_map = {"": 0}
        if args.device_profile == "int8-single-gpu":
            logging.getLogger("bitsandbytes.autograd._functions").setLevel(logging.ERROR)
            load_options["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        else:
            load_options["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
    elif args.device_profile == "bf16-dual-gpu":
        device_map = "balanced"
        load_options["max_memory"] = {0: "11GiB", 1: "11GiB", "cpu": "32GiB"}
    model = AutoModelForMultimodalLM.from_pretrained(
        snapshot,
        local_files_only=True,
        dtype=torch.bfloat16,
        device_map=device_map,
        **load_options,
    ).eval()
    catalog = AssetCatalog(args.catalog_root)
    rows = []
    for record in selected_records(catalog, args.per_species, args.asset_sha256):
        expected = source_species(record)
        image_path = args.catalog_root / record["object_path"]
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        row: dict[str, Any] = {
            "asset_sha256": record["asset_sha256"],
            "display_filename": record["display_filename"],
            "expected_species": expected,
            "teaching_goal": teaching_goal(record, expected),
        }
        try:
            if args.species_only:
                observed, raw, seconds = ask_species(model, processor, image)
                row.update(
                    {
                        "parse_ok": observed != "unparsed",
                        "species_match": observed == expected,
                        "observed_species": observed,
                        "blind_raw": raw,
                        "rubric": None,
                        "rubric_raw": None,
                        "seconds": round(seconds, 3),
                    }
                )
                rows.append(row)
                continue
            blind, blind_raw, blind_seconds = ask(model, processor, image, BLIND_PROMPT, args.max_new_tokens)
            if args.one_pass:
                rubric = None
                rubric_raw = None
                rubric_seconds = 0.0
            else:
                rubric, rubric_raw, rubric_seconds = ask(
                    model,
                    processor,
                    image,
                    RUBRIC_PROMPT.format(
                        claim=repr(row["teaching_goal"]),
                        description=blind.get("description", ""),
                    ),
                    args.max_new_tokens,
                )
            row.update(
                {
                    "parse_ok": True,
                    "species_match": blind.get("primary_species") == expected,
                    "blind": blind,
                    "rubric": rubric,
                    "blind_raw": blind_raw,
                    "rubric_raw": rubric_raw,
                    "seconds": round(blind_seconds + rubric_seconds, 3),
                    "hard_gate_reasons": hard_gate_reasons(blind, expected),
                    "effective_decision": (
                        "reject"
                        if hard_gate_reasons(blind, expected)
                        else (rubric or {}).get("decision", "review")
                    ),
                }
            )
        except (ValueError, json.JSONDecodeError, RuntimeError) as exc:
            row.update({"parse_ok": False, "species_match": False, "error": str(exc)})
            if isinstance(exc, ResponseParseError):
                row.update({"failed_raw": exc.raw, "seconds": round(exc.seconds, 3)})
        rows.append(row)
    parsed = [row for row in rows if row["parse_ok"]]
    report = {
        "schema_version": "ninereeds_gemma_visual_judge_probe_v1",
        "created_at": utc_now(),
        "model_id": gemma["repo_id"],
        "model_revision": gemma["revision"],
        "execution_profile": args.device_profile,
        "rubric_version": "oxford-pet-clean-concept-v1",
        "sample_size": len(rows),
        "metrics": {
            "parse_success_fraction": round(len(parsed) / len(rows), 6),
            "source_species_agreement_fraction": round(sum(row["species_match"] for row in rows) / len(rows), 6),
            "accept_fraction": (
                None
                if args.one_pass or args.species_only
                else round(sum((row.get("rubric") or {}).get("decision") == "accept" for row in rows) / len(rows), 6)
            ),
            "mean_seconds_per_image": round(sum(row.get("seconds", 0) for row in rows) / len(rows), 3),
            "hard_gate_accept_fraction": (
                None
                if args.species_only
                else round(sum(row.get("effective_decision") == "accept" for row in rows) / len(rows), 6)
            ),
            "rubric_false_accept_count": sum(
                bool(row.get("hard_gate_reasons"))
                and (row.get("rubric") or {}).get("decision") == "accept"
                for row in rows
            ),
            "peak_cuda_allocated_gib": (
                {
                    str(index): round(torch.cuda.max_memory_allocated(index) / (1024**3), 3)
                    for index in range(torch.cuda.device_count())
                }
                if torch.cuda.is_available() and args.device_profile != "bf16-cpu"
                else None
            ),
        },
        "qualification_status": "probe_only_pending_human_labels",
        "limitations": [
            "Oxford source labels test species agreement only, not cleanliness or factual completeness.",
            "False-accept and false-reject rates require a human-labelled set with intentional defects and distractions.",
        ],
        "items": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent, delete=False) as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output.resolve()), **report["metrics"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
