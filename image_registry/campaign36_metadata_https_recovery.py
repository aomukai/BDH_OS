"""Recover metadata candidates whose archived source URL used plain HTTP.

The original URL remains in the registry as provenance.  A successful HTTPS-upgraded
download is recorded as an additional text record and admitted like an ordinary download.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import urllib.request

from image_registry.cli import blob_filename


def download(row: sqlite3.Row, store: Path, retries: int) -> dict:
    original = str(row["original_url"])
    upgraded = "https://" + original.removeprefix("http://")
    destination = store / "blobs" / row["source"] / row["split"]
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / blob_filename(row["source_id"])
    partial = target.with_suffix(".jpg.partial")
    last_error: Exception | None = None
    for attempt in range(retries):
        partial.unlink(missing_ok=True)
        digest = hashlib.sha256()
        size = 0
        try:
            with urllib.request.urlopen(upgraded, timeout=45) as response, partial.open("wb") as output:
                while block := response.read(1024 * 1024):
                    size += len(block)
                    if size > 32 * 1024 * 1024:
                        raise RuntimeError("download exceeds 32 MiB safety bound")
                    digest.update(block)
                    output.write(block)
            if not size:
                raise RuntimeError("empty download")
            partial.replace(target)
            return {
                "asset_id": row["id"], "source": row["source"],
                "source_id": row["source_id"], "original_url": original,
                "download_url": upgraded, "local_path": str(target),
                "sha256": digest.hexdigest(), "bytes": size,
            }
        except Exception as exc:
            partial.unlink(missing_ok=True)
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(
        f'{row["source"]}:{row["source_id"]}: {type(last_error).__name__}: {last_error}'
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """SELECT a.id,a.source,a.source_id,a.split,a.original_url
             FROM selection s JOIN asset a ON a.id=s.asset_id
            WHERE s.name=? AND a.status='metadata_only'
              AND a.original_url LIKE 'http://%'
            ORDER BY s.ordinal""",
        (args.selection,),
    ).fetchall()
    successes = []
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(download, row, args.store, args.retries) for row in rows}
        for completed, future in enumerate(as_completed(futures), 1):
            try:
                record = future.result()
                successes.append(record)
                db.execute(
                    "UPDATE asset SET local_path=?,sha256=?,status='downloaded' WHERE id=?",
                    (record["local_path"], record["sha256"], record["asset_id"]),
                )
                db.execute(
                    """INSERT INTO text_record(asset_id,kind,text,author,payload_json)
                       VALUES (?,'download_recovery',?,'campaign36-https-upgrade',?)""",
                    (
                        record["asset_id"], record["download_url"],
                        json.dumps({
                            "original_url": record["original_url"],
                            "download_url": record["download_url"],
                            "policy": "scheme_upgrade_only",
                        }, sort_keys=True),
                    ),
                )
            except Exception as exc:
                failures.append(str(exc))
            if completed % 25 == 0 or completed == len(rows):
                db.commit()
                print(
                    f"processed {completed}/{len(rows)} successes={len(successes)} "
                    f"failures={len(failures)}", flush=True,
                )
    db.commit()
    db.close()
    result = {
        "schema_version": "ninereeds_campaign36_metadata_https_recovery_v1",
        "selection": args.selection,
        "attempted": len(rows),
        "downloaded": len(successes),
        "failed": len(failures),
        "bytes": sum(row["bytes"] for row in successes),
        "successes": successes,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in result.items() if key not in {"successes", "failures"}}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
