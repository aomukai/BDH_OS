#!/usr/bin/env python3
"""Export Cosmopedia parquet shards into prompt+completion JSONL.

This preserves each prompt as a single instruction block (including newlines)
and pairs it with the generated story text.

Example:
  python3 workflow/export_cosmopedia_prompt_completion_jsonl.py \
    --input-glob 'training_data/train-*.parquet' \
    --output training_data/cosmopedia_prompt_completion_v1.jsonl \
    --max-rows 100000 \
    --sample-mode reservoir \
    --seed 1337
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import duckdb


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export Cosmopedia as prompt+completion JSONL for instruction-style training."
    )
    p.add_argument(
        "--input-glob",
        default="training_data/train-*.parquet",
        help="Glob for parquet shards",
    )
    p.add_argument(
        "--output",
        default="training_data/cosmopedia_prompt_completion_v1.jsonl",
        help="Output JSONL path",
    )
    p.add_argument(
        "--max-rows",
        type=int,
        default=100_000,
        help="Maximum rows to write",
    )
    p.add_argument(
        "--sample-mode",
        choices=("first_fit", "reservoir"),
        default="reservoir",
        help="first_fit stops at max_rows; reservoir samples uniformly across full corpus",
    )
    p.add_argument("--seed", type=int, default=1337, help="Random seed for reservoir mode")
    p.add_argument("--min-prompt-chars", type=int, default=40, help="Drop short prompts")
    p.add_argument("--min-text-chars", type=int, default=120, help="Drop short completions")
    p.add_argument("--max-text-chars", type=int, default=12000, help="Drop very long completions")
    p.add_argument(
        "--max-combined-bytes",
        type=int,
        default=None,
        help="Drop samples where prompt+separator+completion bytes exceed this limit",
    )
    p.add_argument(
        "--keep-meta",
        action="store_true",
        help="Include format/audience/seed_data metadata fields in each JSON object",
    )
    p.add_argument(
        "--format-style",
        choices=("raw_split", "tagged_split", "instruction_response"),
        default="raw_split",
        help=(
            "raw_split: {prompt, completion}; "
            "tagged_split: prompt/completion include explicit headers; "
            "instruction_response: single {text} with both sections."
        ),
    )
    return p.parse_args()


def iter_rows(con: duckdb.DuckDBPyConnection, shard: Path):
    q = (
        "SELECT prompt, text, format, audience, seed_data "
        f"FROM read_parquet('{shard.as_posix()}') "
        "WHERE prompt IS NOT NULL AND text IS NOT NULL"
    )
    cur = con.execute(q)
    while True:
        rows = cur.fetchmany(2048)
        if not rows:
            break
        for row in rows:
            yield row


def norm_multiline(s: str) -> str:
    # Keep line structure; only normalize CRLF and strip outer blank space.
    return s.replace("\r\n", "\n").replace("\r", "\n").strip()


def build_record(prompt: str, completion: str, format_style: str) -> dict:
    if format_style == "instruction_response":
        return {
            "text": (
                "### Instruction:\n"
                f"{prompt}\n\n"
                "### Response:\n"
                f"{completion}"
            )
        }
    if format_style == "tagged_split":
        return {
            "prompt": f"### Instruction:\n{prompt}\n\n### Response:\n",
            "completion": completion,
        }
    return {"prompt": prompt, "completion": completion}


def main() -> None:
    args = parse_args()
    shards = sorted(Path(".").glob(args.input_glob))
    if not shards:
        raise FileNotFoundError(f"No parquet shards found for glob: {args.input_glob}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()

    rng = random.Random(args.seed)
    reservoir: list[dict] = []
    scanned = 0
    rows_seen = 0
    skipped_prompt_short = 0
    skipped_text_short = 0
    skipped_text_long = 0
    skipped_combined_long = 0

    def maybe_add(rec: dict) -> None:
        nonlocal scanned
        scanned += 1

        if args.sample_mode == "reservoir":
            if len(reservoir) < args.max_rows:
                reservoir.append(rec)
                return
            j = rng.randint(0, scanned - 1)
            if j < args.max_rows:
                reservoir[j] = rec
            return

        if len(reservoir) < args.max_rows:
            reservoir.append(rec)

    for shard in shards:
        for prompt, text, fmt, audience, seed_data in iter_rows(con, shard):
            rows_seen += 1
            if args.sample_mode == "first_fit" and len(reservoir) >= args.max_rows:
                break

            p = norm_multiline(str(prompt))
            t = norm_multiline(str(text))

            if len(p) < args.min_prompt_chars:
                skipped_prompt_short += 1
                continue
            if len(t) < args.min_text_chars:
                skipped_text_short += 1
                continue
            if len(t) > args.max_text_chars:
                skipped_text_long += 1
                continue

            combined_bytes = len(p.encode("utf-8")) + 1 + len(t.encode("utf-8"))
            if args.max_combined_bytes is not None and combined_bytes > args.max_combined_bytes:
                skipped_combined_long += 1
                continue

            rec = build_record(p, t, args.format_style)
            if args.keep_meta:
                rec["format"] = str(fmt)
                rec["audience"] = str(audience)
                rec["seed_data"] = str(seed_data)
            maybe_add(rec)

        if args.sample_mode == "first_fit" and len(reservoir) >= args.max_rows:
            break

    with out_path.open("w", encoding="utf-8") as f:
        for rec in reservoir:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print("output:", out_path)
    print("rows_written:", len(reservoir))
    print("rows_seen:", rows_seen)
    print("rows_scanned:", scanned)
    print("skipped_prompt_short:", skipped_prompt_short)
    print("skipped_text_short:", skipped_text_short)
    print("skipped_text_long:", skipped_text_long)
    print("skipped_combined_long:", skipped_combined_long)
    print("shards_seen:", len(shards))


if __name__ == "__main__":
    main()
