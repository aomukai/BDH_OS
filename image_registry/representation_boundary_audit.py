"""Use Luna to audit Gemma's single-image representation boundary."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Iterable

from .representation_reassessment import load_jsonl


ALTERNATIVES = [
    "contrast_pair", "image_sequence", "image_plus_context", "story_or_activity",
    "text_only", "curriculum_rewrite", "not_visually_teachable",
]
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["confirm_single_image", "reclassify", "uncertain"]},
        "representation_class": {"type": "string", "enum": ["single_image", *ALTERNATIVES]},
        "reason": {"type": "string", "minLength": 1, "maxLength": 500},
        "visible_criterion": {"type": "string", "minLength": 1, "maxLength": 500},
    },
    "required": ["verdict", "representation_class", "reason", "visible_criterion"],
    "additionalProperties": False,
}


def validate(result: dict[str, Any]) -> dict[str, Any]:
    if set(result) != set(SCHEMA["required"]):
        raise ValueError("Luna result does not match the boundary schema")
    if result["verdict"] == "confirm_single_image" and result["representation_class"] != "single_image":
        raise ValueError("confirmed verdict must retain single_image")
    if result["verdict"] == "reclassify" and result["representation_class"] == "single_image":
        raise ValueError("reclassified verdict must choose another representation")
    return result


def _prompt(row: dict[str, Any], need: dict[str, Any], siblings: list[str]) -> str:
    return f"""Audit one proposed single-image teaching claim independently.

Concept: {need['concept']}
Exact claim: {need['exact_teaching_claim']}
Sibling claims (sense disambiguation only): {json.dumps(siblings, ensure_ascii=False)}
Gemma reason: {row['reason']}
Gemma visible criterion: {row.get('visible_criterion', '')}
Gemma confidence: {row['confidence']}
Gemma claim quality: {row['claim_quality']}

Confirm single_image only when natural, unlabeled pixels can directly and unambiguously provide
positive evidence for the exact claim without a caption, outside knowledge, hidden intention,
imagined before/after, or a merely correlated object. Otherwise reclassify to contrast_pair,
image_sequence, image_plus_context, story_or_activity, text_only, curriculum_rewrite, or
not_visually_teachable. Use uncertain only when the representation boundary genuinely cannot be
decided from the supplied claims. Return only the schema-bound JSON."""


def review(row: dict[str, Any], need: dict[str, Any], siblings: list[str], args: argparse.Namespace) -> dict[str, Any]:
    last_error = "unknown failure"
    for _attempt in range(args.retries):
        with tempfile.TemporaryDirectory(prefix="ninereeds-representation-luna-") as raw:
            root = Path(raw)
            schema = root / "schema.json"
            output = root / "output.json"
            schema.write_text(json.dumps(SCHEMA, sort_keys=True), encoding="utf-8")
            completed = subprocess.run(
                [
                    args.codex, "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                    "--sandbox", "read-only", "--skip-git-repo-check", "-C", str(root),
                    "--model", args.model, "--output-schema", str(schema),
                    "--output-last-message", str(output), "--color", "never", "-",
                ],
                input=_prompt(row, need, siblings), text=True, capture_output=True,
                timeout=args.timeout, check=False,
            )
            if completed.returncode != 0 or not output.is_file():
                last_error = f"exit {completed.returncode}: {completed.stderr[-800:]}"
                continue
            try:
                result = validate(json.loads(output.read_text(encoding="utf-8")))
                return {
                    **result, "item_id": row["item_id"], "model": args.model,
                    "schema_version": "ninereeds_representation_boundary_audit_v1",
                    "gemma_confidence": row["confidence"], "gemma_claim_quality": row["claim_quality"],
                }
            except Exception as exc:
                last_error = str(exc)
    raise RuntimeError(f"Codex Luna failed after {args.retries} attempts: {last_error}")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--needs", type=Path, required=True)
    parser.add_argument("--context", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-high", type=int, default=80)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args(list(argv) if argv is not None else None)
    proposals = load_jsonl(args.proposal)
    needs = {row["item_id"]: row for row in load_jsonl(args.needs)}
    context_rows = [row for path in args.context for row in load_jsonl(path)]
    sibling_map: dict[str, list[str]] = {}
    for row in context_rows + list(needs.values()):
        claim = row.get("exact_teaching_claim")
        if claim and claim not in sibling_map.setdefault(row["concept"], []):
            sibling_map[row["concept"]].append(claim)
    singles = [row for row in proposals if row["representation_class"] == "single_image"]
    nonhigh = [row for row in singles if row["confidence"] != "high"]
    high = sorted(
        (row for row in singles if row["confidence"] == "high"),
        key=lambda row: hashlib.sha256(row["item_id"].encode()).hexdigest(),
    )[:args.sample_high]
    selected = nonhigh + high
    args.output.mkdir(parents=True, exist_ok=True)
    partial = args.output / "partial.jsonl"
    prior = load_jsonl(partial) if partial.exists() else []
    results = {row["item_id"]: row for row in prior}
    selected_ids = {row["item_id"] for row in selected}
    if not set(results).issubset(selected_ids):
        raise ValueError("partial audit contains an item outside the selected boundary")
    remaining = [row for row in selected if row["item_id"] not in results]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(review, row, needs[row["item_id"]], sibling_map[needs[row["item_id"]]["concept"]], args): row
            for row in remaining
        }
        for completed, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results[result["item_id"]] = result
            with partial.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
            print(f"completed {completed}/{len(remaining)} audit items", flush=True)
    ordered = [results[row["item_id"]] for row in selected]
    (args.output / "audit.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ordered),
        encoding="utf-8",
    )
    from collections import Counter
    summary = {
        "schema_version": "ninereeds_representation_boundary_audit_summary_v1",
        "audited": len(ordered), "nonhigh_single_images": len(nonhigh),
        "sampled_high_single_images": len(high),
        "verdict_counts": dict(Counter(row["verdict"] for row in ordered)),
        "reclassification_counts": dict(Counter(
            row["representation_class"] for row in ordered if row["verdict"] == "reclassify"
        )),
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
