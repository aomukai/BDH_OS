from __future__ import annotations

import argparse
import base64
import hashlib
import http.client
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from image_benchmark.common import PROMPT, parse_response, semantic_contract_errors
from image_registry.cli import DEFAULT_DB, connect
from image_registry.review_queue import (
    claim_batch,
    complete_claim,
    fail_claim,
    queue_status,
    register_worker,
    renew_claim,
)


def request_review(
    endpoint: str,
    token: str,
    backend: str,
    model: str,
    image_bytes: bytes,
    timeout: int,
    disable_thinking: bool,
) -> tuple[str, dict[str, Any] | None]:
    pixels = base64.b64encode(image_bytes).decode("ascii")
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + pixels}},
            {"type": "text", "text": PROMPT},
        ]}],
        "max_tokens": 512,
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
        endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        document = json.load(response)
    return document["choices"][0]["message"]["content"], document.get("usage")


ENDPOINT_FAILURES = (
    ConnectionResetError,
    ConnectionRefusedError,
    http.client.RemoteDisconnected,
)


def is_endpoint_failure(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in {408, 425, 429, 500, 502, 503, 504}
    return isinstance(exc, ENDPOINT_FAILURES) or isinstance(exc, urllib.error.URLError)


def require_healthy_endpoint(endpoint: str, timeout: int = 5) -> None:
    with urllib.request.urlopen(endpoint, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(
                f"image-review endpoint health returned HTTP {response.status}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Consume a leased image-review queue")
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
        help="Return schema-invalid responses to the shared queue instead of completing them",
    )
    parser.add_argument("--once", action="store_true", help="Claim at most one batch")
    args = parser.parse_args()

    token = os.environ.get(args.token_env, "") if args.token_env else ""
    if args.token_env and len(token) < 20:
        raise SystemExit(f"missing credential in {args.token_env}")
    if args.max_attempts < 1:
        raise SystemExit("--max-attempts must be positive")

    with connect(args.db) as db:
        register_worker(
            db, args.queue, args.worker_id, args.backend, args.model, args.max_claims
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
                db, args.queue, args.worker_id, lease_seconds=args.lease_seconds
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
                raw, usage = request_review(
                    args.endpoint, token, args.backend, args.model, image_bytes,
                    args.timeout, args.disable_thinking,
                )
                elapsed = time.perf_counter() - started
                parsed, errors = parse_response(raw)
                if args.require_valid_schema and errors:
                    raise ValueError("schema-invalid model response: " + "; ".join(errors))
                record = {
                    "queue": args.queue,
                    "ordinal": claim["ordinal"],
                    "source_id": claim["source_id"],
                    "worker_id": args.worker_id,
                    "backend": args.backend,
                    "model": args.model,
                    "prompt_version": "visual-audit-v1",
                    "attempt_number": claim["attempt_number"],
                    "inference_seconds": elapsed,
                    "raw": raw,
                    "parsed": parsed,
                    "schema_errors": errors,
                    "semantic_contract_errors": semantic_contract_errors(parsed),
                    "usage": usage,
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
                    "type": type(exc).__name__, "message": str(exc),
                    "attempt_number": claim["attempt_number"], "retry": retry,
                }
                try:
                    with connect(args.db) as db:
                        fail_claim(
                            db, claim["claim_token"], args.worker_id, error, retry=retry
                        )
                except ValueError:
                    # An expired claim may already have been atomically returned
                    # to the queue. Never complete it using stale ownership.
                    pass
                print(
                    f"{args.worker_id} {claim['ordinal']} {claim['source_id']} "
                    f"failed: {type(exc).__name__}: {exc}",
                    flush=True,
                )
                if endpoint_failed:
                    # Claims already leased with this batch were never sent to
                    # the dead endpoint. Return them, then let systemd retry
                    # only after the health preflight succeeds.
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


if __name__ == "__main__":
    main()
