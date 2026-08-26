"""Adjudicate Gemma-uncertain Campaign 35 word-to-image fits with Luna."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from image_benchmark.luna_watermark_worker import structured_codex_review
from image_registry.cli import DEFAULT_DB, connect
from image_registry.campaign35_word_review import load_bindings_for_asset
from image_registry.review_queue import (
    claim_batch, complete_claim, ensure_schema, fail_claim, queue_status,
    register_worker, renew_claim,
)


SOURCE_QUEUE = "campaign35-word-semantic-review-v2"
QUEUE = "campaign35-word-fit-luna-v1"
MODEL = "gpt-5.6-luna"
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reason": {"type": "string", "minLength": 1, "maxLength": 500},
        "targets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string", "minLength": 1},
                    "verdict": {"type": "string", "enum": ["accept", "reject", "uncertain"]},
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


def uncertain_contracts(db: Any, source_queue: str, asset_id: int) -> list[dict[str, Any]]:
    row = db.execute(
        "SELECT status,result_json FROM review_queue WHERE queue_name=? AND asset_id=?",
        (source_queue, asset_id),
    ).fetchone()
    if row is None or row["status"] != "completed":
        return []
    record = json.loads(row["result_json"])
    parsed = record.get("parsed") or {}
    uncertain = {
        str(item.get("word", "")).casefold()
        for item in parsed.get("targets", [])
        if isinstance(item, dict) and item.get("visible") == "uncertain"
    }
    contracts: dict[str, dict[str, Any]] = {}
    for item in load_bindings_for_asset(db, source_queue, asset_id):
        word = str(item["word"]).strip()
        key = word.casefold()
        if not key or key not in uncertain:
            continue
        row = contracts.setdefault(key, {"word": word, "senses": []})
        sense = str(item.get("teaching_sense") or item.get("concept") or word).strip()
        if sense and sense not in row["senses"]:
            row["senses"].append(sense)
    return [contracts[key] for key in sorted(contracts)]


def sync_word_fit_queue(db: Any, source_queue: str = SOURCE_QUEUE, queue: str = QUEUE) -> int:
    ensure_schema(db)
    before = db.total_changes
    db.execute(
        """INSERT OR IGNORE INTO review_queue(queue_name,asset_id,ordinal)
           SELECT DISTINCT ?, source.asset_id, source.ordinal
           FROM review_queue source
           JOIN asset ON asset.id=source.asset_id
           JOIN campaign35_word_review_slot_binding binding
             ON binding.queue_name=source.queue_name AND binding.asset_id=source.asset_id
           JOIN json_each(source.result_json, '$.parsed.targets') target
           WHERE source.queue_name=? AND source.status='completed'
             AND asset.local_path IS NOT NULL
             AND asset.status NOT LIKE 'deleted_%'
             AND lower(json_extract(target.value, '$.word'))=lower(binding.word)
             AND json_extract(target.value, '$.visible')='uncertain'
           ORDER BY source.ordinal""",
        (queue, source_queue),
    )
    added = db.total_changes - before
    db.commit()
    return added


def prompt(contracts: list[dict[str, Any]]) -> str:
    targets = "\n".join(
        f"- {row['word']} — REQUIRED SENSE: {'; '.join(row['senses'])}"
        for row in contracts
    )
    return f"""Inspect the attached image and judge only whether each target word is directly and
unambiguously supported by the visible pixels.

Fixed word/sense contracts:
{targets}

Accept a word only when the depicted subject, property, action, relation, or symbol itself is
visible and matches its REQUIRED SENSE exactly. Do not rely on filenames, metadata, prior captions,
overlaid teaching labels, outside knowledge, hidden intentions, or imagined before/after events.
Reject a broader category, related concept, different homonym, partial phrase match, or absent target.
Use uncertain only when relevant pixels are
genuinely too ambiguous to decide. Return exactly one result for every target word and a short
top-level reason summarizing the judgments."""


def review(image: Path, contracts: list[dict[str, Any]], args: argparse.Namespace) -> tuple[dict, dict]:
    words = [row["word"].casefold() for row in contracts]
    result, transcript = structured_codex_review(
        image, executable=args.codex, model=args.model, timeout=args.timeout,
        prompt=prompt(contracts), schema=SCHEMA, temporary_prefix="ninereeds-luna-word-fit-",
    )
    returned = [str(item.get("word", "")).casefold() for item in result["targets"]]
    if len(returned) != len(set(returned)) or set(returned) != set(words):
        raise ValueError("Luna word-fit result does not cover the exact target set")
    return result, transcript


def run(args: argparse.Namespace) -> None:
    with connect(args.db) as db:
        added = sync_word_fit_queue(db, args.source_queue, args.queue)
        register_worker(db, args.queue, args.worker_id, "codex", args.model, 1)
    print(f"synced {added} new word-fit candidate(s)", flush=True)
    processed = 0
    while args.max_items is None or processed < args.max_items:
        with connect(args.db) as db:
            claims = claim_batch(db, args.queue, args.worker_id, requested=1,
                                 lease_seconds=args.lease_seconds)
            status = queue_status(db, args.queue)
        if not claims:
            with connect(args.db) as db:
                added = sync_word_fit_queue(db, args.source_queue, args.queue)
                status = queue_status(db, args.queue)
                source_status = queue_status(db, args.source_queue)
            if added:
                print(f"synced {added} new word-fit candidate(s)", flush=True)
                continue
            unfinished = sum(status["counts"].get(key, 0) for key in ("pending", "leased"))
            source_unfinished = sum(
                source_status["counts"].get(key, 0) for key in ("pending", "leased")
            )
            if not unfinished and not source_unfinished:
                return
            time.sleep(args.poll_seconds)
            continue
        claim = claims[0]
        started = time.perf_counter()
        try:
            with connect(args.db) as db:
                contracts = uncertain_contracts(db, args.source_queue, claim["asset_id"])
                renew_claim(db, claim["claim_token"], args.worker_id, args.lease_seconds)
            if not contracts:
                raise ValueError("word-fit claim has no uncertain target words")
            words = [row["word"].casefold() for row in contracts]
            path = Path(claim["local_path"])
            if hashlib.sha256(path.read_bytes()).hexdigest() != claim["sha256"]:
                raise ValueError(f"image hash mismatch for {claim['source_id']}")
            result, transcript = review(path, contracts, args)
            record = {
                **result, "source_id": claim["source_id"], "ordinal": claim["ordinal"],
                "worker_id": args.worker_id, "backend": "codex", "model": args.model,
                "prompt_version": "campaign36-word-fit-v2-exact-sense",
                "attempt_number": claim["attempt_number"],
                "inference_seconds": time.perf_counter() - started,
                "transcript": transcript,
            }
            with connect(args.db) as db:
                complete_claim(db, claim["claim_token"], args.worker_id, record)
            print(f"{claim['ordinal']} {claim['source_id']} {len(words)} target(s) "
                  f"{record['inference_seconds']:.2f}s", flush=True)
        except Exception as exc:
            retry = claim["attempt_number"] < args.max_attempts
            with connect(args.db) as db:
                fail_claim(db, claim["claim_token"], args.worker_id,
                           {"type": type(exc).__name__, "message": str(exc), "retry": retry},
                           retry=retry)
            print(f"{claim['ordinal']} failed: {type(exc).__name__}: {exc}", flush=True)
        processed += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source-queue", default=SOURCE_QUEUE)
    parser.add_argument("--queue", default=QUEUE)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--lease-seconds", type=int, default=1800)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-attempts", type=int, default=6)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--poll-seconds", type=float, default=5)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
