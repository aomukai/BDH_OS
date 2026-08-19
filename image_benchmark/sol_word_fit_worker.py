"""Final-judge Luna-uncertain Campaign 35 word/image fits with Sol."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from image_benchmark.luna_watermark_worker import structured_codex_review
from image_benchmark.luna_word_fit_worker import prompt
from image_registry.cli import DEFAULT_DB, connect
from image_registry.review_queue import (
    claim_batch, complete_claim, ensure_schema, fail_claim, queue_status,
    register_worker, renew_claim,
)


LUNA_QUEUE = "campaign35-word-fit-luna-v1"
QUEUE = "campaign35-word-fit-sol-v1"
MODEL = "gpt-5.6-sol"
FINAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reason": {"type": "string", "minLength": 1, "maxLength": 500},
        "targets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string", "minLength": 1},
                    "verdict": {"type": "string", "enum": ["accept", "reject"]},
                    "reason": {"type": "string", "minLength": 1, "maxLength": 500},
                },
                "required": ["word", "verdict", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reason", "targets"],
    "additionalProperties": False,
}


def uncertain_words(db: Any, luna_queue: str, asset_id: int) -> list[str]:
    row = db.execute(
        "SELECT status,result_json FROM review_queue WHERE queue_name=? AND asset_id=?",
        (luna_queue, asset_id),
    ).fetchone()
    if row is None or row["status"] != "completed":
        return []
    result = json.loads(row["result_json"])
    return sorted({
        str(item.get("word", "")).casefold()
        for item in result.get("targets", [])
        if isinstance(item, dict) and item.get("verdict") == "uncertain" and item.get("word")
    })


def sync_queue(db: Any, luna_queue: str = LUNA_QUEUE, queue: str = QUEUE) -> int:
    ensure_schema(db)
    before = db.total_changes
    db.execute(
        """INSERT OR IGNORE INTO review_queue(queue_name,asset_id,ordinal)
           SELECT DISTINCT ?, luna.asset_id, luna.ordinal
           FROM review_queue luna
           JOIN asset ON asset.id=luna.asset_id
           JOIN json_each(luna.result_json, '$.targets') target
           WHERE luna.queue_name=? AND luna.status='completed'
             AND json_extract(target.value, '$.verdict')='uncertain'
             AND asset.local_path IS NOT NULL
             AND asset.status NOT LIKE 'deleted_%'
           ORDER BY luna.ordinal""",
        (queue, luna_queue),
    )
    added = db.total_changes - before
    db.commit()
    return added


def final_review(image: Path, words: list[str], args: argparse.Namespace) -> tuple[dict, dict]:
    final_prompt = prompt(words) + (
        "\nYou are the final judge. You must decide accept or reject from the pixels; "
        "uncertain is not an available outcome. When ambiguity prevents positive support, reject."
    )
    result, transcript = structured_codex_review(
        image, executable=args.codex, model=args.model, timeout=args.timeout,
        prompt=final_prompt, schema=FINAL_SCHEMA,
        temporary_prefix="ninereeds-sol-word-fit-",
    )
    returned = [str(item.get("word", "")).casefold() for item in result["targets"]]
    if len(returned) != len(set(returned)) or set(returned) != set(words):
        raise ValueError("Sol final result does not cover the exact target set")
    return result, transcript


def run(args: argparse.Namespace) -> None:
    with connect(args.db) as db:
        added = sync_queue(db, args.luna_queue, args.queue)
        register_worker(db, args.queue, args.worker_id, "codex", args.model, 1)
    print(f"synced {added} Sol final-judgment candidate(s)", flush=True)
    processed = 0
    while args.max_items is None or processed < args.max_items:
        with connect(args.db) as db:
            # Newly completed Luna cases can enter while this worker is alive.
            sync_queue(db, args.luna_queue, args.queue)
            claims = claim_batch(
                db, args.queue, args.worker_id, requested=1,
                lease_seconds=args.lease_seconds,
            )
            status = queue_status(db, args.queue)
            luna_status = queue_status(db, args.luna_queue)
            upstream_status = (
                queue_status(db, args.semantic_source_queue)
                if args.semantic_source_queue else None
            )
        if not claims:
            unfinished = sum(status["counts"].get(key, 0) for key in ("pending", "leased"))
            luna_unfinished = sum(
                luna_status["counts"].get(key, 0) for key in ("pending", "leased")
            )
            upstream_unfinished = 0 if upstream_status is None else sum(
                upstream_status["counts"].get(key, 0) for key in ("pending", "leased")
            )
            if not unfinished and not luna_unfinished and not upstream_unfinished:
                return
            time.sleep(args.poll_seconds)
            continue
        claim = claims[0]
        started = time.perf_counter()
        try:
            with connect(args.db) as db:
                words = uncertain_words(db, args.luna_queue, claim["asset_id"])
                renew_claim(db, claim["claim_token"], args.worker_id, args.lease_seconds)
            if not words:
                raise ValueError("Sol claim has no Luna-uncertain target words")
            path = Path(claim["local_path"])
            if hashlib.sha256(path.read_bytes()).hexdigest() != claim["sha256"]:
                raise ValueError(f"image hash mismatch for {claim['source_id']}")
            # Reuse the exact word-fit contract; only the model and provenance differ.
            result, transcript = final_review(path, words, args)
            record = {
                **result, "source_id": claim["source_id"], "ordinal": claim["ordinal"],
                "worker_id": args.worker_id, "backend": "codex", "model": args.model,
                "prompt_version": "campaign35-word-fit-final-judge-v1",
                "attempt_number": claim["attempt_number"],
                "inference_seconds": time.perf_counter() - started,
                "transcript": transcript,
                "final_judge": "sol",
            }
            with connect(args.db) as db:
                complete_claim(db, claim["claim_token"], args.worker_id, record)
            print(
                f"{claim['ordinal']} {claim['source_id']} {len(words)} final target(s) "
                f"{record['inference_seconds']:.2f}s", flush=True,
            )
        except Exception as exc:
            retry = claim["attempt_number"] < args.max_attempts
            with connect(args.db) as db:
                fail_claim(
                    db, claim["claim_token"], args.worker_id,
                    {"type": type(exc).__name__, "message": str(exc), "retry": retry},
                    retry=retry,
                )
            print(f"{claim['ordinal']} failed: {type(exc).__name__}: {exc}", flush=True)
        processed += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--luna-queue", default=LUNA_QUEUE)
    parser.add_argument("--queue", default=QUEUE)
    parser.add_argument("--semantic-source-queue")
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--lease-seconds", type=int, default=1800)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--poll-seconds", type=float, default=5)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--max-items", type=int)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
