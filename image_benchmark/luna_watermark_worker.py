from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any

from image_registry.cli import DEFAULT_DB, connect
from image_registry.review_queue import (
    claim_batch,
    complete_claim,
    ensure_schema,
    fail_claim,
    queue_status,
    register_worker,
    renew_claim,
)


SOURCE_QUEUE = "visual-corpus-review-v1"
QUEUE = "visual-corpus-watermark-luna-v1"
MODEL = "gpt-5.6-luna"
PROMPT = """Judge only whether the attached image contains a true watermark or added overlay.

A true watermark or added overlay is text, a photographer credit, stock mark, channel mark,
website, badge, logo, timestamp, or graphic visually laid over the underlying picture. Text
or branding physically present in the photographed scene (signs, clothing, product packaging,
vehicle markings, artwork) is not an overlay. Choose in_scene_text_or_branding both when a
visible mark is part of the scene and when the alleged mark is not actually visible. Choose
uncertain only when a visible mark exists but its visual integration cannot be judged. Do not
choose uncertain merely because provenance is unknowable. Ignore the earlier model's alarm,
inspect the pixels independently, and return a short, concrete visual reason."""

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "alarm": {
            "type": "string",
            "enum": [
                "true_watermark_or_added_overlay",
                "in_scene_text_or_branding",
                "uncertain",
            ],
        },
        "reason": {"type": "string", "minLength": 1, "maxLength": 500},
    },
    "required": ["alarm", "reason"],
    "additionalProperties": False,
}


def sync_alarm_queue(db: Any, source_queue: str = SOURCE_QUEUE, queue: str = QUEUE) -> int:
    """Add every completed Gemma watermark alarm without disturbing existing work."""
    ensure_schema(db)
    before = db.total_changes
    db.execute(
        """INSERT OR IGNORE INTO review_queue(queue_name, asset_id, ordinal)
           SELECT ?, source.asset_id, source.ordinal
           FROM review_queue source
           WHERE source.queue_name=? AND source.status='completed'
             AND json_extract(source.result_json, '$.parsed.watermark')=1
           ORDER BY source.ordinal""",
        (queue, source_queue),
    )
    added = db.total_changes - before
    db.commit()
    return added


def codex_review(
    image: Path,
    *,
    executable: str,
    model: str,
    timeout: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="ninereeds-luna-watermark-") as raw_root:
        root = Path(raw_root)
        schema_path = root / "schema.json"
        output_path = root / "result.json"
        schema_path.write_text(json.dumps(SCHEMA, sort_keys=True), encoding="utf-8")
        command = [
            executable,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "-C",
            str(root),
            "--model",
            model,
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--image",
            str(image.resolve()),
            "--color",
            "never",
            "-",
        ]
        completed = subprocess.run(
            command,
            input=PROMPT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        transcript = {
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }
        if completed.returncode != 0 or not output_path.is_file():
            raise RuntimeError(
                f"Codex Luna failed with exit {completed.returncode}: "
                f"{completed.stderr[-1000:]}"
            )
        result = json.loads(output_path.read_text(encoding="utf-8"))
        if set(result) != {"alarm", "reason"}:
            raise ValueError("Luna result does not match the watermark schema")
        if result["alarm"] not in SCHEMA["properties"]["alarm"]["enum"]:
            raise ValueError("Luna returned an unknown watermark classification")
        if not isinstance(result["reason"], str) or not result["reason"].strip():
            raise ValueError("Luna returned an empty watermark reason")
        return result, transcript


def run(args: argparse.Namespace) -> None:
    with connect(args.db) as db:
        added = sync_alarm_queue(db, args.source_queue, args.queue)
        register_worker(db, args.queue, args.worker_id, "codex", args.model, 1)
    print(f"synced {added} new watermark alarm(s)", flush=True)

    processed = 0
    while True:
        if args.max_items is not None and processed >= args.max_items:
            return
        with connect(args.db) as db:
            claims = claim_batch(
                db,
                args.queue,
                args.worker_id,
                requested=1,
                lease_seconds=args.lease_seconds,
            )
            status = queue_status(db, args.queue)
        if not claims:
            with connect(args.db) as db:
                added = sync_alarm_queue(db, args.source_queue, args.queue)
                source_status = queue_status(db, args.source_queue)
                status = queue_status(db, args.queue)
            if added:
                print(f"synced {added} new watermark alarm(s)", flush=True)
                continue
            source_unfinished = sum(
                source_status["counts"].get(state, 0)
                for state in ("pending", "leased")
            )
            adjudication_unfinished = sum(
                status["counts"].get(state, 0)
                for state in ("pending", "leased")
            )
            if not source_unfinished and not adjudication_unfinished:
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
            adjudication, transcript = codex_review(
                path,
                executable=args.codex,
                model=args.model,
                timeout=args.timeout,
            )
            record = {
                **adjudication,
                "source_id": claim["source_id"],
                "ordinal": claim["ordinal"],
                "worker_id": args.worker_id,
                "backend": "codex",
                "model": args.model,
                "prompt_version": "watermark-adjudication-v1",
                "attempt_number": claim["attempt_number"],
                "inference_seconds": time.perf_counter() - started,
                "transcript": transcript,
            }
            with connect(args.db) as db:
                complete_claim(db, claim["claim_token"], args.worker_id, record)
            print(
                f"{claim['ordinal']} {claim['source_id']} {record['alarm']} "
                f"{record['inference_seconds']:.2f}s",
                flush=True,
            )
            processed += 1
        except Exception as exc:
            with connect(args.db) as db:
                fail_claim(
                    db,
                    claim["claim_token"],
                    args.worker_id,
                    {"type": type(exc).__name__, "message": str(exc), "retry": False},
                    retry=False,
                )
            print(
                f"{claim['ordinal']} {claim['source_id']} failed: "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            processed += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Adjudicate Gemma watermark alarms with Codex Luna")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source-queue", default=SOURCE_QUEUE)
    parser.add_argument("--queue", default=QUEUE)
    parser.add_argument("--worker-id", default="codex-luna-watermark-01")
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--lease-seconds", type=int, default=1800)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--poll-seconds", type=float, default=5)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
