"""Reassess unresolved claims before acquiring more pixels.

The output is a proposal, not an authoritative curriculum mutation.  A text model
chooses from the closed representation taxonomy and records uncertainty so Luna or
Sol can audit the boundary without being invited to write persuasive free-form prose.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Iterable
import urllib.request


CLASSES = {
    "single_image", "contrast_pair", "image_sequence", "image_plus_context",
    "story_or_activity", "text_only", "curriculum_rewrite", "not_visually_teachable",
}
CLAIM_QUALITY = {"valid", "placeholder", "factually_suspect", "ambiguous"}
CONFIDENCE = {"high", "medium", "low"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def parse_document(raw: str, expected: set[str]) -> list[dict[str, Any]]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    document = json.loads(raw)
    rows = document.get("decisions")
    if not isinstance(rows, list) or {row.get("item_id") for row in rows} != expected:
        raise ValueError("response item IDs differ from requested batch")
    for row in rows:
        if row.get("representation_class") in CLAIM_QUALITY:
            # Some providers put the separately requested quality label in the
            # adjacent representation field. Preserve that fact explicitly;
            # a malformed claim cannot remain an image-acquisition order.
            row["normalization"] = "claim_quality_returned_in_representation_field"
            row["claim_quality"] = row["representation_class"]
            row["representation_class"] = "not_visually_teachable"
        if row.get("representation_class") not in CLASSES:
            raise ValueError(f"invalid representation class: {row.get('representation_class')}")
        if row.get("claim_quality") not in CLAIM_QUALITY:
            raise ValueError(f"invalid claim quality: {row.get('claim_quality')}")
        if row.get("confidence") not in CONFIDENCE:
            raise ValueError(f"invalid confidence: {row.get('confidence')}")
        if not str(row.get("reason") or "").strip():
            raise ValueError("missing reason")
    return rows


def make_batches(
    needs: list[dict[str, Any]], context_rows: list[dict[str, Any]], maximum_items: int,
) -> list[list[dict[str, Any]]]:
    context: dict[str, list[str]] = {}
    for row in context_rows + needs:
        claim = str(row.get("exact_teaching_claim") or "").strip()
        if claim and claim not in context.setdefault(row["concept"], []):
            context[row["concept"]].append(claim)
    groups: list[list[dict[str, Any]]] = []
    by_concept: dict[str, list[dict[str, Any]]] = {}
    for row in needs:
        by_concept.setdefault(row["concept"], []).append({
            "item_id": row["item_id"], "concept": row["concept"],
            "exact_teaching_claim": row["exact_teaching_claim"],
            "sibling_claims_for_sense_disambiguation": context[row["concept"]],
        })
    current: list[dict[str, Any]] = []
    for concept_rows in by_concept.values():
        if current and len(current) + len(concept_rows) > maximum_items:
            groups.append(current)
            current = []
        current.extend(concept_rows)
    if current:
        groups.append(current)
    return groups


def _prompt(items: list[dict[str, Any]]) -> str:
    return """You are auditing visual teaching prerequisites. For every item, choose exactly one
representation: single_image, contrast_pair, image_sequence, image_plus_context,
story_or_activity, text_only, curriculum_rewrite, or not_visually_teachable.

Use single_image only when pixels directly and unambiguously demonstrate the exact claim without
captions, hidden intentions, outside knowledge, or imagined before/after events. A related object
is not evidence for an abstract definition, purpose, cause, internal state, temporal change, or
mathematical rule. Use sibling claims only to disambiguate the intended sense of a polysemous
concept; judge each exact claim independently. Mark malformed "X is here" placeholders as
placeholder unless X is a concrete visible identity and the wording can honestly function as an
identity claim. Do not repair a factually suspect claim silently.

Also choose claim_quality: valid, placeholder, factually_suspect, or ambiguous; and confidence:
high, medium, or low. Return JSON only in this exact shape:
{"decisions":[{"item_id":"...","representation_class":"...","claim_quality":"...",
"confidence":"...","reason":"one concrete sentence","visible_criterion":"what pixels must
show, or none"}]}. Return every requested item exactly once and add no items.

ITEMS:
""" + json.dumps(items, ensure_ascii=False)


def request_batch(
    endpoint: str, token: str, model: str, items: list[dict[str, Any]], retries: int,
    disable_thinking: bool = False,
) -> list[dict[str, Any]]:
    expected = {row["item_id"] for row in items}
    disable_thinking_payload: dict[str, Any] = {}
    if disable_thinking:
        if "openrouter.ai" in endpoint.casefold():
            disable_thinking_payload["reasoning"] = {"enabled": False}
        else:
            disable_thinking_payload["chat_template_kwargs"] = {"enable_thinking": False}
    body = json.dumps({
        "model": model, "temperature": 0, "max_tokens": 6000,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": _prompt(items)}],
        **disable_thinking_payload,
    }).encode()
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                endpoint, data=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                document = json.load(response)
            return parse_document(document["choices"][0]["message"]["content"], expected)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"batch failed after {retries} attempts: {last_error}")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--needs", type=Path, required=True)
    parser.add_argument("--context", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="https://openrouter.ai/api/v1/chat/completions")
    parser.add_argument("--token-env", default="OPENROUTER_API_KEY")
    parser.add_argument("--model", default="google/gemma-4-26b-a4b-it")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--maximum-items", type=int, default=20)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--disable-thinking", action="store_true")
    parser.add_argument(
        "--allow-partial-superset", action="store_true",
        help="Reuse a partial ledger from a previous superset run, ignoring rows outside current needs.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not 1 <= args.workers <= 16 or not 1 <= args.maximum_items <= 40:
        raise ValueError("workers must be 1..16 and maximum-items 1..40")
    token = os.environ.get(args.token_env)
    if not token:
        raise ValueError(f"missing token environment variable: {args.token_env}")
    needs = load_jsonl(args.needs)
    context = [row for path in args.context for row in load_jsonl(path)]
    args.output.mkdir(parents=True, exist_ok=True)
    partial_path = args.output / "partial.jsonl"
    partial_rows = load_jsonl(partial_path) if partial_path.exists() else []
    wanted = {row["item_id"] for row in needs}
    if args.allow_partial_superset:
        partial_rows = [row for row in partial_rows if row.get("item_id") in wanted]
    results: dict[str, dict[str, Any]] = {row["item_id"]: row for row in partial_rows}
    if not set(results).issubset(wanted):
        raise ValueError("partial file contains items outside the current input")
    remaining = [row for row in needs if row["item_id"] not in results]
    batches = make_batches(remaining, context, args.maximum_items)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                request_batch, args.endpoint, token, args.model, batch, args.retries,
                args.disable_thinking,
            ): batch
            for batch in batches
        }
        for completed, future in enumerate(as_completed(futures), 1):
            completed_rows = future.result()
            for row in completed_rows:
                row["schema_version"] = "ninereeds_representation_reassessment_proposal_v1"
                row["model"] = args.model
                results[row["item_id"]] = row
            with partial_path.open("a", encoding="utf-8") as handle:
                for row in completed_rows:
                    handle.write(json.dumps(results[row["item_id"]], ensure_ascii=False, sort_keys=True) + "\n")
                handle.flush()
            print(f"completed {completed}/{len(batches)} batches items={len(results)}/{len(needs)}", flush=True)
    if set(results) != {row["item_id"] for row in needs}:
        raise RuntimeError("completed proposal does not cover the exact input set")
    ordered = [results[row["item_id"]] for row in needs]
    (args.output / "representation_proposal.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ordered),
        encoding="utf-8",
    )
    from collections import Counter
    summary = {
        "schema_version": "ninereeds_representation_reassessment_summary_v1",
        "items": len(ordered), "batches": len(batches), "model": args.model,
        "representation_counts": dict(Counter(row["representation_class"] for row in ordered)),
        "claim_quality_counts": dict(Counter(row["claim_quality"] for row in ordered)),
        "confidence_counts": dict(Counter(row["confidence"] for row in ordered)),
        "status": "proposal_requires_boundary_audit_before_reconciliation",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
