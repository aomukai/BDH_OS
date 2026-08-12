from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from image_benchmark.common import semantic_contract_errors


def percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, round((len(values) - 1) * fraction))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path, nargs="+")
    args = parser.parse_args()
    for path in args.results:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        timings = [float(row["inference_seconds"]) for row in rows]
        parsed = [row for row in rows if row.get("parsed") is not None]
        summary = {
            "path": str(path),
            "model": rows[0]["model"] if rows else None,
            "completed": len(rows),
            "json_parseable": len(parsed),
            "schema_valid": sum(not row.get("schema_errors") for row in rows),
            "median_seconds": round(statistics.median(timings), 3) if timings else None,
            "p95_seconds": round(percentile(timings, 0.95), 3) if timings else None,
            "images_per_minute": round(60 / statistics.mean(timings), 2) if timings else None,
            "admissions": Counter(
                (row.get("parsed") or {}).get("admission") or "<unparsed>" for row in rows
            ),
            "schema_errors": Counter(error for row in rows for error in row.get("schema_errors", [])),
            "semantic_contract_errors": Counter(
                error for row in rows for error in semantic_contract_errors(row.get("parsed"))
            ),
        }
        summary["admissions"] = dict(summary["admissions"])
        summary["schema_errors"] = dict(summary["schema_errors"])
        summary["semantic_contract_errors"] = dict(summary["semantic_contract_errors"])
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
