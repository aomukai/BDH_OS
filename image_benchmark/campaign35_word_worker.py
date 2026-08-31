from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from collections import OrderedDict
from typing import Any

from image_benchmark.common import semantic_contract_errors
from image_benchmark.queue_worker_api import is_endpoint_failure, require_healthy_endpoint
from image_registry.cli import DEFAULT_DB, connect
from image_registry.campaign35_word_review import load_bindings_for_asset
from image_registry.review_queue import (
    claim_batch,
    complete_claim,
    fail_claim,
    queue_status,
    register_worker,
    renew_claim,
)


REQUIRED_ROOT_KEYS = {
    "admission", "visible_text", "watermark", "quality_flags", "literal_caption",
    "targets", "uncertainties",
}

REQUIRED_TARGET_KEYS = {"word", "visible", "evidence"}
VALID_ADMISSION = {"usable", "unusable", "uncertain"}
VALID_VISIBILITY = {True, False, "uncertain"}


def _strip_markdown_json(raw: str) -> str:
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.I | re.S)
    return candidate


def parse_response(raw: str, target_words: list[str]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    candidate = _strip_markdown_json(raw)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return None, [f"json:{exc.msg}"]

    if not isinstance(value, dict):
        return None, ["root:not_object"]

    missing = REQUIRED_ROOT_KEYS - set(value)
    extra = set(value) - REQUIRED_ROOT_KEYS
    if missing:
        errors.append("missing:" + ",".join(sorted(missing)))
    if extra:
        errors.append("extra:" + ",".join(sorted(extra)))

    if value.get("admission") not in VALID_ADMISSION:
        errors.append("admission:invalid")

    for key in ("visible_text", "watermark"):
        if not isinstance(value.get(key), bool):
            errors.append(f"{key}:not_boolean")

    quality_flags = value.get("quality_flags")
    if not isinstance(quality_flags, list) or any(not isinstance(flag, str) for flag in quality_flags):
        errors.append("quality_flags:invalid")

    uncertainties = value.get("uncertainties")
    if not isinstance(uncertainties, list) or any(not isinstance(item, str) for item in uncertainties):
        errors.append("uncertainties:invalid")

    if not isinstance(value.get("literal_caption"), str):
        errors.append("literal_caption:not_string")
    elif not value["literal_caption"].strip():
        errors.append("literal_caption:empty")

    targets = value.get("targets")
    if not isinstance(targets, list):
        errors.append("targets:not_array")
        return None, errors

    target_rows: list[dict[str, Any]] = []

    normalized_expected = []
    for expected_word in target_words:
        normalized = str(expected_word).strip().casefold()
        if normalized:
            normalized_expected.append(normalized)
    expected = list(OrderedDict.fromkeys(normalized_expected))
    expected_set = set(expected)

    for item in targets:
        if not isinstance(item, dict):
            errors.append("targets:item:not_object")
            continue
        missing_item = REQUIRED_TARGET_KEYS - set(item)
        extra_item = set(item) - REQUIRED_TARGET_KEYS
        if missing_item:
            errors.append("targets:item:missing:" + ",".join(sorted(missing_item)))
        if extra_item:
            errors.append("targets:item:extra:" + ",".join(sorted(extra_item)))
        word = str(item.get("word", "")).strip()
        if not word:
            errors.append("targets:item:word_empty")
            continue
        target_rows.append({
            "word": word,
            "visible": item.get("visible"),
            "evidence": item.get("evidence"),
        })
        visible = item.get("visible")
        if visible not in VALID_VISIBILITY:
            errors.append(f"targets:item:{word}:visible_invalid")
        if not isinstance(item.get("evidence"), str):
            errors.append(f"targets:item:{word}:evidence_not_string")

    observed: list[str] = []
    seen: set[str] = set()
    for row in target_rows:
        normalized = row["word"].casefold()
        if normalized in seen:
            errors.append(f"targets:duplicate:{row['word']}")
        seen.add(normalized)
        observed.append(normalized)

    observed_set = set(observed)
    if expected_set != observed_set:
        missing_targets = sorted(expected_set - observed_set)
        extra_targets = sorted(observed_set - expected_set)
        if missing_targets:
            errors.append("targets:missing:" + ",".join(missing_targets))
        if extra_targets:
            errors.append("targets:extra:" + ",".join(extra_targets))

    return value, errors


def collect_unique_target_words(bindings: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in sorted(bindings, key=lambda row: (row["sequence_position"], row["slot_id"])):
        word = str(row["word"]).strip()
        normalized = word.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(word)
    return ordered


def prompt_for_asset(bindings: list[dict[str, Any]]) -> str:
    targets = collect_unique_target_words(bindings)
    if not targets:
        raise ValueError("asset has no campaign35 slot targets")
    target_block = "\n".join(f"- {target}" for target in targets)
    return """You are doing a pixel-level corpus review for Campaign 35.

This image is one slot group with these target words:
{target_block}

Classify the image using only visible visual evidence (pixels). Do NOT use captions,
metadata, filename, or prior annotations.

A target is visually present only when the image content itself plainly shows the target.
Do not treat printed text, labels, signs, logos, scene text, or watermarking as evidence for
non-textual words.
Verbs, adjectives, and relations may count when the action/state/relation is clearly visible.

Respond with exactly one JSON object and no Markdown:
{{"admission":"usable","visible_text":false,"watermark":false,"quality_flags":[],"literal_caption":"A brown dog runs across green grass.","targets":[{{"word":"dog", "visible":true, "evidence":"A dog is plainly visible."}}],"uncertainties":[]}}

admission must be one of usable, unusable, or uncertain.
visible_text and watermark are booleans.
quality_flags and uncertainties are arrays of short strings.
literal_caption must be one non-empty, complete, concise sentence describing only visible content.
Each target in targets must appear exactly once for every target above and carry
visible as JSON true, JSON false, or the string "uncertain".
""".format(target_block=target_block)


def request_review(
    endpoint: str,
    token: str,
    backend: str,
    model: str,
    image_bytes: bytes,
    prompt: str,
    timeout: int,
    disable_thinking: bool,
) -> tuple[str, dict[str, Any] | None]:
    pixels = base64.b64encode(image_bytes).decode("ascii")
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + pixels}},
            {"type": "text", "text": prompt},
        ]}],
        "max_tokens": 768,
    }
    if disable_thinking:
        if backend.casefold().startswith("openrouter"):
            payload["reasoning"] = {"enabled": False}
        else:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        document = json.load(response)
    return document["choices"][0]["message"]["content"], document.get("usage")


def run(args: argparse.Namespace) -> None:
    token = os.environ.get(args.token_env, "") if args.token_env else ""
    if args.token_env and len(token) < 20:
        raise SystemExit(f"missing credential in {args.token_env}")
    if args.max_attempts < 1:
        raise SystemExit("--max-attempts must be positive")

    with connect(args.db) as db:
        register_worker(
            db, args.queue, args.worker_id, args.backend, args.model, args.max_claims,
        )

    batches = 0
    while True:
        if args.health_endpoint:
            try:
                require_healthy_endpoint(args.health_endpoint)
            except Exception as exc:
                raise SystemExit(
                    f"endpoint unavailable before claim: {type(exc).__name__}: {exc}"
                )

        with connect(args.db) as db:
            claims = claim_batch(
                db, args.queue, args.worker_id, lease_seconds=args.lease_seconds,
            )
            status = queue_status(db, args.queue)
        if not claims:
            unfinished = status["counts"].get("pending", 0) + status["counts"].get("leased", 0)
            if not unfinished or args.once:
                return
            time.sleep(args.poll_seconds)
            continue

        batches += 1
        for claim_index, claim in enumerate(claims):
            started = time.perf_counter()
            try:
                path = Path(claim["local_path"])
                image_bytes = path.read_bytes()
                digest = hashlib.sha256(image_bytes).hexdigest()
                if claim["sha256"] and digest != claim["sha256"]:
                    raise ValueError(f"image hash mismatch for {claim['source_id']}")
                with connect(args.db) as db:
                    renew_claim(db, claim["claim_token"], args.worker_id, args.lease_seconds)
                    bindings = load_bindings_for_asset(db, claim["queue_name"], claim["asset_id"])
                prompt = prompt_for_asset(bindings)
                expected_targets = collect_unique_target_words(bindings)
                raw, usage = request_review(
                    args.endpoint, token, args.backend, args.model,
                    image_bytes, prompt, args.timeout, args.disable_thinking,
                )
                parsed, errors = parse_response(raw, expected_targets)
                if args.require_valid_schema and errors:
                    raise ValueError("schema-invalid model response: " + "; ".join(errors))
                elapsed = time.perf_counter() - started
                record = {
                    "queue": args.queue,
                    "ordinal": claim["ordinal"],
                    "source_id": claim["source_id"],
                    "asset_id": claim["asset_id"],
                    "worker_id": args.worker_id,
                    "backend": args.backend,
                    "model": args.model,
                    "prompt_version": "campaign35-word-review-v1",
                    "attempt_number": claim["attempt_number"],
                    "inference_seconds": elapsed,
                    "raw": raw,
                    "parsed": parsed,
                    "schema_errors": errors,
                    "semantic_contract_errors": semantic_contract_errors(parsed),
                    "usage": usage,
                    "targets": expected_targets,
                }
                with connect(args.db) as db:
                    complete_claim(db, claim["claim_token"], args.worker_id, record)
                print(
                    f"{args.worker_id} {claim['ordinal']} {claim['source_id']} "
                    f"{elapsed:.2f}s schema={'ok' if not errors else errors}",
                    flush=True,
                )
            except Exception as exc:
                endpoint_failed = is_endpoint_failure(exc)
                retry = endpoint_failed or claim["attempt_number"] < args.max_attempts
                error = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "attempt_number": claim["attempt_number"],
                    "retry": retry,
                }
                with connect(args.db) as db:
                    fail_claim(db, claim["claim_token"], args.worker_id, error, retry=retry)
                print(
                    f"{args.worker_id} {claim['ordinal']} {claim['source_id']} "
                    f"failed: {type(exc).__name__}: {exc}",
                    flush=True,
                )
                if endpoint_failed:
                    for untouched in claims[claim_index + 1 :]:
                        with connect(args.db) as db:
                            fail_claim(
                                db,
                                untouched["claim_token"],
                                args.worker_id,
                                {
                                    "type": "EndpointUnavailable",
                                    "message": str(exc),
                                    "attempt_number": untouched["attempt_number"],
                                    "retry": True,
                                    "request_sent": False,
                                },
                                retry=True,
                            )
                    raise SystemExit(
                        f"endpoint became unavailable: {type(exc).__name__}: {exc}"
                    )
        if args.once and batches == 1:
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Consume Campaign 35 semantic word review queue")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument(
        "--health-endpoint",
        help="Check this URL before claiming each batch; unavailable endpoints claim no work",
    )
    parser.add_argument("--token-env")
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-claims", type=int, default=4)
    parser.add_argument("--lease-seconds", type=int, default=1800)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--poll-seconds", type=float, default=5)
    parser.add_argument("--disable-thinking", action="store_true")
    parser.add_argument(
        "--require-valid-schema", action="store_true",
        help="Fail schema-invalid responses instead of completing them",
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.max_claims < 1:
        raise SystemExit("--max-claims must be positive")
    if args.max_attempts < 1:
        raise SystemExit("--max-attempts must be positive")

    run(args)


if __name__ == "__main__":
    main()
