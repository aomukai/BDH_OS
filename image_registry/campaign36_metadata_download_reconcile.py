"""Freeze downloaded assets from a bounded Campaign 36 metadata selection."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--parent-selection", required=True)
    parser.add_argument("--downloaded-selection", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """SELECT s.ordinal,s.stratum,a.id,a.source,a.source_id,a.status,
                  a.local_path,a.sha256
             FROM selection s JOIN asset a ON a.id=s.asset_id
            WHERE s.name=? ORDER BY s.ordinal""",
        (args.parent_selection,),
    ).fetchall()
    downloaded = [
        row for row in rows
        if row["local_path"] and row["sha256"] and Path(row["local_path"]).is_file()
    ]
    expected = [row["id"] for row in downloaded]
    existing = [
        row[0] for row in db.execute(
            "SELECT asset_id FROM selection WHERE name=? ORDER BY ordinal",
            (args.downloaded_selection,),
        )
    ]
    if existing and existing != expected:
        raise RuntimeError("immutable downloaded selection differs from current filesystem state")
    if not existing:
        db.executemany(
            "INSERT INTO selection(name,asset_id,stratum,ordinal) VALUES (?,?,?,?)",
            [
                (args.downloaded_selection, row["id"], "campaign36_metadata_downloaded", index)
                for index, row in enumerate(downloaded)
            ],
        )
        db.commit()
    source_requested = Counter(row["source"] for row in rows)
    source_downloaded = Counter(row["source"] for row in downloaded)
    result = {
        "schema_version": "ninereeds_campaign36_metadata_download_reconciliation_v1",
        "parent_selection": args.parent_selection,
        "downloaded_selection": args.downloaded_selection,
        "requested_assets": len(rows),
        "downloaded_assets": len(downloaded),
        "unavailable_assets": len(rows) - len(downloaded),
        "source_requested": dict(sorted(source_requested.items())),
        "source_downloaded": dict(sorted(source_downloaded.items())),
        "source_unavailable": {
            source: source_requested[source] - source_downloaded[source]
            for source in sorted(source_requested)
        },
        "created": not bool(existing),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
