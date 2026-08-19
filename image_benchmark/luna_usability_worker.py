from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
from typing import Any

from image_benchmark.luna_watermark_worker import structured_codex_review, sync_alarm_queue
from image_registry.cli import DEFAULT_DB, DEFAULT_STORE, connect
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


SOURCE_QUEUE = "visual-corpus-review-v1"
QUEUE = "visual-corpus-unusable-luna-v1"
WATERMARK_QUEUE = "visual-corpus-watermark-luna-v1"
MODEL = "gpt-5.6-luna"
PROMPT = """Judge whether the attached image is usable in a visual-language research corpus.

Choose usable when the image has recognizable subjects, actions, settings, or relationships
that can be described truthfully, even if it is rotated, artistic, unusual, moderately blurry,
low-resolution, or imperfectly composed. Motion blur is acceptable when the depicted event is
still understandable. Do not reject an image merely for visible text, branding, a logo, or a
watermark; those are adjudicated separately.

Choose unusable only for a genuinely non-instructional file: corrupt or effectively blank pixels,
severe blur or obstruction that makes the content unrecognizable, an incoherent/broken composite,
or content so visually defective that a literal caption would be misleading. Choose uncertain
only when the pixels do not support either decision. Ignore the earlier model's rejection and
inspect independently. Return the required JSON with a short, concrete visual reason."""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "usability": {
            "type": "string",
            "enum": ["usable", "unusable", "uncertain"],
        },
        "reason": {"type": "string", "minLength": 1, "maxLength": 500},
    },
    "required": ["usability", "reason"],
    "additionalProperties": False,
}

DELETION_SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus_removal (
    asset_id INTEGER PRIMARY KEY REFERENCES asset(id),
    source_id TEXT NOT NULL,
    original_path TEXT NOT NULL,
    quarantine_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    reason TEXT NOT NULL,
    adjudication_queue TEXT NOT NULL,
    adjudication_json TEXT NOT NULL,
    removed_at TEXT NOT NULL
);
"""


def sync_unusable_queue(db: Any, source_queue: str = SOURCE_QUEUE, queue: str = QUEUE) -> int:
    ensure_schema(db)
    before = db.total_changes
    db.execute(
        """INSERT OR IGNORE INTO review_queue(queue_name, asset_id, ordinal)
           SELECT ?, source.asset_id, source.ordinal
           FROM review_queue source
           JOIN asset ON asset.id=source.asset_id
           WHERE source.queue_name=? AND source.status='completed'
             AND asset.local_path IS NOT NULL
             AND asset.status NOT LIKE 'deleted_%'
             AND (
               json_extract(source.result_json, '$.parsed.admission') IN ('unusable','uncertain')
               OR json_array_length(json_extract(source.result_json, '$.parsed.uncertainties')) > 0
             )
           ORDER BY source.ordinal""",
        (queue, source_queue),
    )
    added = db.total_changes - before
    db.commit()
    return added


def quarantine_confirmed_unusable(
    db: Any,
    *,
    queue: str,
    store_root: Path,
) -> int:
    """Remove only hash-matched Luna-confirmed files from the active corpus."""
    db.executescript(DELETION_SCHEMA)
    root = store_root.resolve()
    quarantine = root / "quarantine" / "luna-confirmed-unusable-v1"
    rows = db.execute(
        """SELECT a.id AS asset_id, a.source_id, a.local_path, a.sha256, q.result_json
           FROM review_queue q JOIN asset a ON a.id=q.asset_id
           WHERE q.queue_name=? AND q.status='completed'
             AND json_extract(q.result_json, '$.usability')='unusable'
             AND a.local_path IS NOT NULL
             AND NOT EXISTS (
                 SELECT 1 FROM review_queue blocker
                 WHERE blocker.asset_id=a.id AND blocker.queue_name<>?
                   AND blocker.status IN ('pending', 'leased')
             )
           ORDER BY q.ordinal""",
        (queue, queue),
    ).fetchall()
    removed = 0
    for row in rows:
        source = Path(row["local_path"]).resolve()
        if source != root and root not in source.parents:
            raise ValueError(f"refusing corpus removal outside store root: {source}")
        if not source.is_file():
            raise ValueError(f"confirmed unusable image is missing: {source}")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != row["sha256"]:
            raise ValueError(f"refusing corpus removal after hash mismatch: {row['source_id']}")
        relative = source.relative_to(root)
        destination = quarantine / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ValueError(f"quarantine destination already exists: {destination}")
        shutil.move(str(source), str(destination))
        result = json.loads(row["result_json"])
        db.execute(
            """INSERT INTO corpus_removal(
                   asset_id, source_id, original_path, quarantine_path, sha256,
                   reason, adjudication_queue, adjudication_json, removed_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["asset_id"], row["source_id"], str(source), str(destination),
                digest, result["reason"], queue, row["result_json"], timestamp(utc_now()),
            ),
        )
        db.execute(
            "UPDATE asset SET local_path=NULL, status='quarantined_unusable' WHERE id=?",
            (row["asset_id"],),
        )
        db.commit()
        removed += 1
    return removed


def review(image: Path, args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    result, transcript = structured_codex_review(
        image,
        executable=args.codex,
        model=args.model,
        timeout=args.timeout,
        prompt=PROMPT,
        schema=SCHEMA,
        temporary_prefix="ninereeds-luna-usability-",
    )
    if result["usability"] not in SCHEMA["properties"]["usability"]["enum"]:
        raise ValueError("Luna returned an unknown usability classification")
    return result, transcript


def run(args: argparse.Namespace) -> None:
    with connect(args.db) as db:
        added = sync_unusable_queue(db, args.source_queue, args.queue)
        register_worker(db, args.queue, args.worker_id, "codex", args.model, 1)
    print(f"synced {added} new unusable candidate(s)", flush=True)

    processed = 0
    while True:
        if args.max_items is not None and processed >= args.max_items:
            return
        with connect(args.db) as db:
            claims = claim_batch(db, args.queue, args.worker_id, requested=1,
                                 lease_seconds=args.lease_seconds)
        if not claims:
            with connect(args.db) as db:
                added = sync_unusable_queue(db, args.source_queue, args.queue)
                # Ensure the other Luna queue contains every watermark alarm
                # before deciding that no consumer still needs a candidate.
                sync_alarm_queue(db, args.source_queue, args.watermark_queue)
                source_status = queue_status(db, args.source_queue)
                own_status = queue_status(db, args.queue)
                watermark_status = queue_status(db, args.watermark_queue)
            if added:
                print(f"synced {added} new unusable candidate(s)", flush=True)
                continue
            source_unfinished = sum(source_status["counts"].get(s, 0) for s in ("pending", "leased"))
            own_unfinished = sum(own_status["counts"].get(s, 0) for s in ("pending", "leased"))
            watermark_unfinished = sum(watermark_status["counts"].get(s, 0) for s in ("pending", "leased"))
            if not source_unfinished and not own_unfinished and not watermark_unfinished:
                if not args.skip_quarantine:
                    with connect(args.db) as db:
                        removed = quarantine_confirmed_unusable(
                            db, queue=args.queue, store_root=args.store_root,
                        )
                    print(f"quarantined {removed} confirmed unusable image(s)", flush=True)
                return
            time.sleep(args.poll_seconds)
            continue

        claim = claims[0]
        started = time.perf_counter()
        try:
            path = Path(claim["local_path"])
            if hashlib.sha256(path.read_bytes()).hexdigest() != claim["sha256"]:
                raise ValueError(f"image hash mismatch for {claim['source_id']}")
            with connect(args.db) as db:
                renew_claim(db, claim["claim_token"], args.worker_id, args.lease_seconds)
            adjudication, transcript = review(path, args)
            record = {
                **adjudication,
                "source_id": claim["source_id"], "ordinal": claim["ordinal"],
                "worker_id": args.worker_id, "backend": "codex", "model": args.model,
                "prompt_version": "usability-adjudication-v1",
                "attempt_number": claim["attempt_number"],
                "inference_seconds": time.perf_counter() - started,
                "transcript": transcript,
            }
            with connect(args.db) as db:
                complete_claim(db, claim["claim_token"], args.worker_id, record)
            print(f"{claim['ordinal']} {claim['source_id']} {record['usability']} "
                  f"{record['inference_seconds']:.2f}s", flush=True)
        except Exception as exc:
            with connect(args.db) as db:
                fail_claim(db, claim["claim_token"], args.worker_id,
                           {"type": type(exc).__name__, "message": str(exc), "retry": False},
                           retry=False)
            print(f"{claim['ordinal']} {claim['source_id']} failed: {type(exc).__name__}: {exc}",
                  flush=True)
        processed += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Adjudicate rejected images with Codex Luna")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source-queue", default=SOURCE_QUEUE)
    parser.add_argument("--queue", default=QUEUE)
    parser.add_argument("--watermark-queue", default=WATERMARK_QUEUE)
    parser.add_argument("--worker-id", default="codex-luna-usability-01")
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--store-root", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--lease-seconds", type=int, default=1800)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--poll-seconds", type=float, default=5)
    parser.add_argument(
        "--skip-quarantine", action="store_true",
        help="Record adjudications without moving files; finalize once after parallel workers exit.",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
