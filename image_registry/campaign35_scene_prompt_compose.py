"""Validate scene bundles and compose variant-ready Flux production briefs with DeepSeek."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable
import urllib.request


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def prompt(rows: list[dict[str, Any]]) -> str:
    return f"""Validate and compose image-production briefs for beginner visual teaching.

Research context: this is Campaign 35 M2 for Ninereeds, a recurrent latent-reasoning model with
very limited language and no assumed pretrained world knowledge. Each training exposure contains
one target English word plus one image—no explanatory caption. Each word needs ten distinct
positive visual examples. One image may fill slots for at most four words, but only when its pixels
teach each word independently. The purpose is grounded word learning, not image decoration.

For each bundle, decide whether one coherent, natural-looking image can directly and
unambiguously provide positive pixel evidence for every listed word. Mere association,
hidden intention, pretrained cultural knowledge, a caption explaining the scene, visible target
word text, or a crowded object dump does not count.
If the claims cannot coexist clearly, split them into two or more groups. Every input concept_id
must occur exactly once across that bundle's groups; never add one. Each group may contain at
most four concepts.

For every output group provide:
- concept_ids: its exact claim partition;
- capture_description: plain description of what the camera sees and when;
- flux_prompt_template: concrete generation prompt with no explanatory prose in the image;
- variation_axes: 3-6 safe visual properties that can vary while every claim remains true;
- evidence_by_concept: object mapping every concept_id to the directly visible evidence.

Keep a bundle together only when the prompt remains simple and each target is salient. Return
JSON only as {{"bundles":[{{"bundle_id":"...","groups":[...]}}]}}. Return every bundle once.

BUNDLES:
{json.dumps(rows, ensure_ascii=False)}"""


def validate(input_rows: list[dict[str, Any]], output: dict[str, Any]) -> list[dict[str, Any]]:
    expected = {row["bundle_id"]: set(row["concept_ids"]) for row in input_rows}
    bundles = output.get("bundles")
    if not isinstance(bundles, list) or {row.get("bundle_id") for row in bundles} != set(expected):
        raise ValueError("bundle IDs differ from requested batch")
    for bundle in bundles:
        groups = bundle.get("groups")
        if not isinstance(groups, list) or not groups:
            raise ValueError(f"missing groups for {bundle.get('bundle_id')}")
        seen: list[str] = []
        for group in groups:
            ids = group.get("concept_ids")
            if not isinstance(ids, list) or not 1 <= len(ids) <= 4:
                raise ValueError("invalid group size")
            seen.extend(ids)
            if set(group.get("evidence_by_concept", {})) != set(ids):
                raise ValueError("evidence keys do not match group concepts")
            for key in ("capture_description", "flux_prompt_template"):
                if not str(group.get(key) or "").strip():
                    raise ValueError(f"missing {key}")
            axes = group.get("variation_axes")
            if not isinstance(axes, list) or not 3 <= len(axes) <= 6:
                raise ValueError("variation axes must contain 3..6 items")
        if len(seen) != len(set(seen)) or set(seen) != expected[bundle["bundle_id"]]:
            raise ValueError(f"claim partition mismatch for {bundle['bundle_id']}")
    return bundles


def request_batch(endpoint: str, token: str, model: str, rows: list[dict[str, Any]], retries: int) -> list[dict[str, Any]]:
    body = json.dumps({
        "model": model, "temperature": 0, "max_tokens": 8000,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "messages": [{"role": "user", "content": prompt(rows)}],
    }).encode()
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(endpoint, data=body, headers={
                "Authorization": f"Bearer {token}", "Content-Type": "application/json",
            })
            with urllib.request.urlopen(request, timeout=180) as response:
                document = json.load(response)
            return validate(rows, json.loads(document["choices"][0]["message"]["content"]))
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"composition batch failed: {last_error}")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="https://api.deepseek.com/chat/completions")
    parser.add_argument("--token-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(list(argv) if argv is not None else None)
    token = os.environ.get(args.token_env)
    if not token:
        raise ValueError(f"missing token: {args.token_env}")
    source = load_jsonl(args.bundles)
    source_by_id = {row["bundle_id"]: row for row in source}
    args.output.mkdir(parents=True, exist_ok=True)
    partial = args.output / "composed.partial.jsonl"
    prior = load_jsonl(partial) if partial.exists() else []
    results = {row["bundle_id"]: row for row in prior}
    if not set(results) <= set(source_by_id):
        raise ValueError("partial contains bundles outside current source")
    remaining = [row for row in source if row["bundle_id"] not in results]
    work = chunks(remaining, args.batch_size)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(request_batch, args.endpoint, token, args.model, batch, args.retries): batch for batch in work}
        for completed, future in enumerate(as_completed(futures), 1):
            rows = future.result()
            with partial.open("a", encoding="utf-8") as handle:
                for row in rows:
                    results[row["bundle_id"]] = row
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            print(f"composed {completed}/{len(work)} batches bundles={len(results)}/{len(source)}", flush=True)
    if set(results) != set(source_by_id):
        raise RuntimeError("composition partition incomplete")
    briefs: list[dict[str, Any]] = []
    split_bundles = 0
    for source_row in source:
        result = results[source_row["bundle_id"]]
        if len(result["groups"]) > 1:
            split_bundles += 1
        for group_index, group in enumerate(result["groups"], 1):
            briefs.append({
                **group,
                "production_brief_id": f"{source_row['bundle_id']}-g{group_index}",
                "source_bundle_id": source_row["bundle_id"],
                "scene_anchor": source_row["scene_anchor"],
                "variant_count": source_row["variant_count"],
                "base_generation_jobs": 1,
                "flux_edit_jobs": max(0, source_row["variant_count"] - 1),
                "edit_policy": "vary only declared safe axes; preserve every evidence_by_concept claim",
                "assignment_count": source_row["variant_count"] * len(group["concept_ids"]),
                "model": args.model,
                "status": "ready_for_flux_generation_then_full_validation",
            })
    write_jsonl(args.output / "production_briefs.jsonl", briefs)
    assignments = sum(row["assignment_count"] for row in briefs)
    images = sum(row["variant_count"] for row in briefs)
    base_jobs = sum(row["base_generation_jobs"] for row in briefs)
    edit_jobs = sum(row["flux_edit_jobs"] for row in briefs)
    expected_assignments = sum(row["assignment_count"] for row in source)
    if assignments != expected_assignments:
        raise AssertionError("composition changed the assignment partition")
    summary = {
        "schema_version": "ninereeds_campaign35_scene_prompt_composition_v1",
        "source_bundles": len(source), "split_source_bundles": split_bundles,
        "production_briefs": len(briefs), "assignment_slots": assignments,
        "planned_flux_images": images, "average_claims_per_image": assignments / images,
        "base_generation_jobs": base_jobs, "flux_edit_jobs": edit_jobs,
        "model": args.model, "status": "ready_for_flux_generation_then_full_validation",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
