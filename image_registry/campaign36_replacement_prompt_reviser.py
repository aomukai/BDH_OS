"""Revise Campaign 36 word-image prompts after both providers fail a cycle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any

from image_registry.campaign36_replacement_generation_queue import (
    connect,
    revise_prompt,
)


SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "minLength": 20, "maxLength": 3000},
        "strategy": {"type": "string", "minLength": 1, "maxLength": 500},
    },
    "required": ["prompt", "strategy"],
    "additionalProperties": False,
}


def next_word(db: Any) -> dict[str, Any] | None:
    row = db.execute(
        """SELECT * FROM campaign36_word_generation
           WHERE status='needs_prompt_revision' ORDER BY ordinal LIMIT 1"""
    ).fetchone()
    if row is None:
        return None
    attempts = [
        dict(item)
        for item in db.execute(
            """SELECT prompt_cycle,provider,produced_count,accepted_added,
                      prompt,evidence_json,finished_at
               FROM campaign36_word_generation_attempt
               WHERE word=? ORDER BY id""",
            (row["word"],),
        )
    ]
    return {**dict(row), "attempts": attempts}


def prompt(item: dict[str, Any]) -> str:
    return f"""Write one improved image-generation prompt for a visual vocabulary corpus.

The target word and meaning are fixed. The image itself—not a caption or label—must teach
the meaning directly. Flux and GPT Image have both already failed to complete ten accepted
images. Study the attempt evidence and choose a clearer, simpler visual representation that
addresses the actual failures. Do not alter the meaning, use a related substitute, or rely on
visible explanatory text. The prompt must work for both a photorealistic Flux model and GPT
Image, permit varied subjects/settings across multiple images, and avoid logos and watermarks.

WORD: {item['word']}
EXACT TEACHING SENSE: {item['teaching_sense']}
ACCEPTED SO FAR: {item['accepted_count']}/{item['target_count']}
ATTEMPT EVIDENCE:
{json.dumps(item['attempts'], ensure_ascii=False, indent=2)}

Return only the schema-bound prompt and a short strategy explanation."""


def request(item: dict[str, Any], args: argparse.Namespace) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="ninereeds-c36-prompt-revision-") as raw:
        root = Path(raw)
        schema = root / "schema.json"
        result = root / "result.json"
        schema.write_text(json.dumps(SCHEMA, sort_keys=True), encoding="utf-8")
        completed = subprocess.run(
            [
                args.codex,
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
                args.model,
                "--output-schema",
                str(schema),
                "--output-last-message",
                str(result),
                "--color",
                "never",
                "-",
            ],
            input=prompt(item),
            text=True,
            capture_output=True,
            timeout=args.timeout,
            check=False,
        )
        if completed.returncode != 0 or not result.is_file():
            raise RuntimeError(
                f"prompt revision failed with exit {completed.returncode}: "
                f"{completed.stderr[-1000:]}"
            )
        value = json.loads(result.read_text(encoding="utf-8"))
        if set(value) != set(SCHEMA["required"]):
            raise ValueError("prompt revision response violated its schema")
        return value


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    with connect(args.db) as db:
        item = next_word(db)
    if item is None:
        return {"status": "idle"}
    result = request(item, args)
    with connect(args.db) as db:
        state = revise_prompt(db, word=item["word"], prompt=result["prompt"])
    return {
        "status": "revised",
        "word": item["word"],
        "prompt_cycle": state["prompt_cycle"],
        "strategy": result["strategy"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--poll-seconds", type=float, default=30)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    while True:
        try:
            result = run_once(args)
        except Exception as exc:
            result = {"status": "error", "type": type(exc).__name__, "message": str(exc)}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        if not args.loop:
            return 0 if result["status"] != "error" else 1
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
