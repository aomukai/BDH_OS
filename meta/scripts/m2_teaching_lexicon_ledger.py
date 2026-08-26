#!/usr/bin/env python3
"""Atomic claim and append operations for the shared M2 teaching lexicon."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "ninereeds_m2_teaching_lexicon_mapping_v1"


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            ordinal = row.get("source", {}).get("ordinal")
            if row.get("schema_version") != SCHEMA_VERSION or not isinstance(ordinal, int):
                raise ValueError(f"invalid row at {path}:{line_number}")
            rows.append(row)
    ordinals = [row["source"]["ordinal"] for row in rows]
    if len(set(ordinals)) != len(ordinals):
        raise ValueError(f"duplicate ordinals in {path}")
    return rows


def claim_path(output: Path, ordinal: int) -> Path:
    return output.parent / f"{output.name}.claims" / f"{ordinal:04d}.owner"


def claim(output: Path, ordinal: int, worker_id: str) -> bool:
    path = claim_path(output, ordinal)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path.read_text(encoding="utf-8").strip() == worker_id
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(worker_id + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return True


def append(output: Path, row: dict[str, Any]) -> str:
    ordinal = row.get("source", {}).get("ordinal")
    if row.get("schema_version") != SCHEMA_VERSION or not isinstance(ordinal, int):
        raise ValueError("refusing invalid result record")
    output.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output.parent / f"{output.name}.lock"
    with lock_path.open("a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if any(existing["source"]["ordinal"] == ordinal for existing in read_rows(output)):
            return "already_completed"
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    return "appended"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("completed")
    claim_parser = subparsers.add_parser("claim")
    claim_parser.add_argument("--ordinal", type=int, required=True)
    claim_parser.add_argument("--worker-id", required=True)
    subparsers.add_parser("append")
    args = parser.parse_args()

    if args.command == "completed":
        print(json.dumps([row["source"]["ordinal"] for row in read_rows(args.output)]))
    elif args.command == "claim":
        print(json.dumps({"claimed": claim(args.output, args.ordinal, args.worker_id)}))
    else:
        row = json.load(__import__("sys").stdin)
        print(json.dumps({"status": append(args.output, row)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
