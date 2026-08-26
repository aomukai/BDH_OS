"""Resolve exhausted Campaign 36 semantic reviews with an exact-sense Luna pass.

The ordinary Gemma fleet is intentionally strict about its JSON contract.  If an
asset exhausts that bounded retry budget, this worker preserves every failed
attempt, reviews the same immutable teaching senses with Luna, and projects the
trusted result back into the authoritative semantic queue.  The separate
fallback queue makes the escalation and its evidence auditable and restart-safe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from typing import Any

from image_benchmark.campaign35_word_worker import (
    collect_unique_target_words,
    parse_response,
)
from image_benchmark.luna_campaign_word_worker import (
    MODEL,
    SCHEMA,
    coalesce_sense_targets,
    prompt_for,
)
from image_benchmark.luna_watermark_worker import structured_codex_review
from image_registry.campaign35_word_review import load_bindings_for_asset
from image_registry.cli import DEFAULT_DB, connect
from image_registry.review_queue import (
    claim_batch,
    complete_claim,
    ensure_schema,
    fail_claim,
    queue_status,
    register_worker,
    renew_claim,
    timestamp,
    utc_now,
)


PROMPT_VERSION = "campaign35-word-review-v2-exact-sense"


def sync_terminal_failures(
    db: sqlite3.Connection, source_queue: str, fallback_queue: str,
) -> int:
    """Add newly exhausted source rows to the durable Luna fallback queue."""
    ensure_schema(db)
    before = db.total_changes
    db.execute(
        """INSERT OR IGNORE INTO review_queue(queue_name,asset_id,ordinal,status)
           SELECT ?,asset_id,ordinal,'pending' FROM review_queue
           WHERE queue_name=? AND status='failed'""",
        (fallback_queue, source_queue),
    )
    changed = db.total_changes - before
    db.commit()
    return changed


def project_completed_fallbacks(
    db: sqlite3.Connection, source_queue: str, fallback_queue: str,
) -> int:
    """Make completed Luna verdicts authoritative without erasing failures."""
    ensure_schema(db)
    db.execute("BEGIN IMMEDIATE")
    try:
        rows = db.execute(
            """SELECT f.asset_id,f.completed_at,f.result_json
               FROM review_queue f JOIN review_queue s ON s.asset_id=f.asset_id
               WHERE f.queue_name=? AND f.status='completed'
                 AND s.queue_name=? AND s.status='failed'""",
            (fallback_queue, source_queue),
        ).fetchall()
        changed = 0
        for row in rows:
            record = json.loads(row["result_json"])
            if record.get("prompt_version") != PROMPT_VERSION:
                raise ValueError(
                    f"fallback result lacks exact-sense provenance: {row['asset_id']}"
                )
            cursor = db.execute(
                """UPDATE review_queue
                   SET status='completed',current_attempt_id=NULL,
                       completed_at=?,result_json=?
                   WHERE queue_name=? AND asset_id=? AND status='failed'""",
                (
                    row["completed_at"] or timestamp(utc_now()),
                    row["result_json"], source_queue, row["asset_id"],
                ),
            )
            changed += cursor.rowcount
        db.commit()
        return changed
    except Exception:
        db.rollback()
        raise


def run(args: argparse.Namespace) -> None:
    with connect(args.db) as db:
        ensure_schema(db)
        register_worker(db, args.queue, args.worker_id, "codex", args.model, 1)
    processed = 0
    while args.max_items is None or processed < args.max_items:
        with connect(args.db) as db:
            project_completed_fallbacks(db, args.source_queue, args.queue)
            sync_terminal_failures(db, args.source_queue, args.queue)
            claims = claim_batch(
                db, args.queue, args.worker_id, requested=1,
                lease_seconds=args.lease_seconds,
            )
            status = queue_status(db, args.queue)
        if not claims:
            # The source queue is still active, so new terminal failures can
            # appear later.  Stay dormant instead of treating an empty fallback
            # queue as completion.
            time.sleep(args.poll_seconds)
            continue
        claim = claims[0]
        started = time.perf_counter()
        try:
            image = Path(claim["local_path"])
            if hashlib.sha256(image.read_bytes()).hexdigest() != claim["sha256"]:
                raise ValueError(f"image hash mismatch for {claim['source_id']}")
            with connect(args.db) as db:
                renew_claim(db, claim["claim_token"], args.worker_id, args.lease_seconds)
                bindings = load_bindings_for_asset(
                    db, args.source_queue, claim["asset_id"],
                )
            expected = collect_unique_target_words(bindings)
            parsed, transcript = structured_codex_review(
                image, executable=args.codex, model=args.model, timeout=args.timeout,
                prompt=prompt_for(bindings), schema=SCHEMA,
                temporary_prefix="ninereeds-luna-terminal-semantic-",
            )
            review_reason = parsed.pop("reason")
            for target in parsed["targets"]:
                target["visible"] = {
                    "present": True, "absent": False, "uncertain": "uncertain",
                }[target["visible"]]
            parsed["targets"] = coalesce_sense_targets(parsed["targets"], expected)
            _, errors = parse_response(json.dumps(parsed), expected)
            if errors:
                raise ValueError("schema-invalid Luna fallback: " + "; ".join(errors))
            record: dict[str, Any] = {
                "queue": args.source_queue,
                "fallback_queue": args.queue,
                "ordinal": claim["ordinal"],
                "source_id": claim["source_id"],
                "asset_id": claim["asset_id"],
                "worker_id": args.worker_id,
                "backend": "codex-luna-terminal-fallback",
                "model": args.model,
                "prompt_version": PROMPT_VERSION,
                "attempt_number": claim["attempt_number"],
                "inference_seconds": time.perf_counter() - started,
                "raw": json.dumps(parsed, ensure_ascii=False),
                "parsed": parsed,
                "schema_errors": [],
                "semantic_contract_errors": [],
                "usage": None,
                "targets": expected,
                "transcript": transcript,
                "review_reason": review_reason,
                "escalation_reason": "ordinary_exact_sense_review_exhausted",
            }
            with connect(args.db) as db:
                complete_claim(db, claim["claim_token"], args.worker_id, record)
                project_completed_fallbacks(db, args.source_queue, args.queue)
            print(
                f"projected {claim['ordinal']} {claim['source_id']} via Luna fallback",
                flush=True,
            )
        except Exception as exc:
            retry = claim["attempt_number"] < args.max_attempts
            with connect(args.db) as db:
                fail_claim(
                    db, claim["claim_token"], args.worker_id,
                    {"type": type(exc).__name__, "message": str(exc), "retry": retry},
                    retry=retry,
                )
            print(
                f"fallback {claim['ordinal']} failed: {type(exc).__name__}: {exc}",
                flush=True,
            )
        processed += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source-queue", required=True)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--lease-seconds", type=int, default=1800)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-attempts", type=int, default=12)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--poll-seconds", type=float, default=5)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
