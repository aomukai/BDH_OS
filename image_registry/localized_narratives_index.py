"""Build a compact FTS index from official Localized Narratives text captions."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterable


def build(inputs: list[Path], output: Path) -> dict[str, object]:
    if output.exists():
        raise ValueError(f"refusing to overwrite index: {output}")
    db = sqlite3.connect(output)
    db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE VIRTUAL TABLE narrative_search USING fts5(
            dataset_id UNINDEXED,image_id UNINDEXED,annotator_id UNINDEXED,caption,
            tokenize='porter unicode61'
        );
    """)
    count = 0
    hashes = {}
    for path in inputs:
        digest = hashlib.sha256()
        with path.open("rb") as raw:
            for line in raw:
                digest.update(line)
                row = json.loads(line)
                db.execute(
                    "INSERT INTO narrative_search VALUES (?,?,?,?)",
                    (row["dataset_id"], row["image_id"], row["annotator_id"], row["caption"]),
                )
                count += 1
                if count % 10000 == 0:
                    db.commit()
                    print(f"indexed {count}", flush=True)
        hashes[path.name] = digest.hexdigest()
    manifest = {"annotations": count, "input_sha256": hashes, "license": "CC BY 4.0"}
    db.executemany(
        "INSERT INTO metadata VALUES (?,?)",
        ((key, json.dumps(value, sort_keys=True)) for key, value in manifest.items()),
    )
    db.commit(); db.execute("PRAGMA optimize"); db.close()
    return manifest


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(json.dumps(build(args.input, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
