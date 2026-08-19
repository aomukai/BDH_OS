"""Use Luna to enforce semantic coherence of Campaign 35 multi-claim scene bundles."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Iterable


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def schema_for(ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["keep", "split"]},
            "groups": {
                "type": "array", "minItems": 1, "maxItems": len(ids),
                "items": {
                    "type": "object",
                    "properties": {
                        "concept_ids": {
                            "type": "array", "minItems": 1, "maxItems": 4,
                            "items": {"type": "string", "enum": ids},
                        },
                        "coherent_scene": {"type": "string", "minLength": 1, "maxLength": 600},
                        "reason": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                    "required": ["concept_ids", "coherent_scene", "reason"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["verdict", "groups"], "additionalProperties": False,
    }


def validate(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expected = row["concept_ids"]
    seen = [item for group in result["groups"] for item in group["concept_ids"]]
    if len(seen) != len(set(seen)) or set(seen) != set(expected):
        raise ValueError("Luna changed the exact concept partition")
    if result["verdict"] == "keep" and len(result["groups"]) != 1:
        raise ValueError("keep verdict must have one group")
    if result["verdict"] == "split" and len(result["groups"]) < 2:
        raise ValueError("split verdict must have multiple groups")
    return result


def prompt(row: dict[str, Any]) -> str:
    return f"""Audit whether these beginner visual-teaching claims belong in one image.

Research context: Campaign 35 M2 trains Ninereeds with one English target word plus one image and
no explanatory caption. Ninereeds has very limited language and no assumed pretrained world
knowledge. Each word needs ten distinct positive examples. An image may serve at most four words,
but the pixels must teach every assigned word independently.

Keep them together only if a single simple, natural scene can make every target independently
salient and directly visible. Split whenever the result would be a crowded inventory, a contrived
juxtaposition, mere association, cultural shorthand, or dependence on a caption. Text spelling the
target word inside the image is circular and does not count as teaching it. A group of one is
correct when no honest partner exists. Do not
drop, duplicate, rename, or add concept IDs. For each resulting group describe one coherent scene
and state briefly why its claims naturally coexist.

BUNDLE:
{json.dumps(row, ensure_ascii=False)}"""


def audit_one(row: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    last_error = "unknown failure"
    for _attempt in range(args.retries):
        with tempfile.TemporaryDirectory(prefix="ninereeds-bundle-luna-") as raw:
            root = Path(raw)
            schema = root / "schema.json"
            output = root / "output.json"
            schema.write_text(json.dumps(schema_for(row["concept_ids"]), sort_keys=True), encoding="utf-8")
            completed = subprocess.run([
                args.codex, "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                "--sandbox", "read-only", "--skip-git-repo-check", "-C", str(root),
                "--model", args.model, "--output-schema", str(schema),
                "--output-last-message", str(output), "--color", "never", "-",
            ], input=prompt(row), text=True, capture_output=True, timeout=args.timeout, check=False)
            if completed.returncode != 0 or not output.is_file():
                last_error = completed.stderr[-800:]
                continue
            try:
                result = validate(row, json.loads(output.read_text(encoding="utf-8")))
                return {"bundle_id": row["bundle_id"], **result, "model": args.model}
            except Exception as exc:
                last_error = str(exc)
    raise RuntimeError(f"Luna bundle audit failed after {args.retries} attempts: {last_error}")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(list(argv) if argv is not None else None)
    source = load_jsonl(args.bundles)
    source_by_id = {row["bundle_id"]: row for row in source}
    args.output.mkdir(parents=True, exist_ok=True)
    partial = args.output / "partial.jsonl"
    prior = load_jsonl(partial) if partial.exists() else []
    results = {row["bundle_id"]: row for row in prior}
    if not set(results) <= set(source_by_id):
        raise ValueError("partial contains unknown bundles")
    remaining = [row for row in source if row["bundle_id"] not in results]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(audit_one, row, args): row for row in remaining}
        for completed, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results[result["bundle_id"]] = result
            with partial.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
            print(f"audited {completed}/{len(remaining)} bundles", flush=True)
    if set(results) != set(source_by_id):
        raise RuntimeError("audit partition incomplete")

    audited: list[dict[str, Any]] = []
    split = 0
    for row in source:
        result = results[row["bundle_id"]]
        if result["verdict"] == "split":
            split += 1
        claims = {claim["concept_id"]: claim for claim in row["claims"]}
        for index, group in enumerate(result["groups"], 1):
            ids = group["concept_ids"]
            audited.append({
                "bundle_id": f"{row['bundle_id']}-a{index}",
                "source_bundle_id": row["bundle_id"],
                "scene_anchor": row["scene_anchor"], "concept_ids": ids,
                "words": [claims[item]["word"] for item in ids],
                "variant_count": row["variant_count"],
                "assignment_count": row["variant_count"] * len(ids),
                "claims": [claims[item] for item in ids],
                "luna_coherent_scene": group["coherent_scene"],
                "luna_reason": group["reason"], "luna_model": args.model,
                "status": "approved_partition_pending_deepseek_prompt_composition",
            })
    write_path = args.output / "audited_bundles.jsonl"
    write_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in audited),
        encoding="utf-8",
    )
    assignments = sum(row["assignment_count"] for row in audited)
    images = sum(row["variant_count"] for row in audited)
    summary = {
        "schema_version": "ninereeds_campaign35_scene_bundle_luna_audit_v1",
        "source_bundles": len(source), "split_source_bundles": split,
        "audited_bundles": len(audited), "assignment_slots": assignments,
        "planned_images_after_semantic_splits": images,
        "average_claims_per_image": assignments / images, "model": args.model,
        "status": "approved_partition_pending_deepseek_prompt_composition",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
