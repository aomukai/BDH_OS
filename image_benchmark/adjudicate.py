from __future__ import annotations

import argparse
import json
from pathlib import Path

from image_benchmark.common import admission_policy


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply deterministic corpus-admission policy to raw model evidence."
    )
    parser.add_argument("results", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--watermark-review",
        type=Path,
        help="Optional JSONL keyed by source_id with a Luna/human alarm classification.",
    )
    args = parser.parse_args()

    watermark_reviews = {}
    if args.watermark_review:
        watermark_reviews = {
            row["source_id"]: row
            for row in (
                json.loads(line)
                for line in args.watermark_review.read_text(encoding="utf-8").splitlines()
            )
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.results.open(encoding="utf-8") as source, args.output.open(
        "w", encoding="utf-8"
    ) as destination:
        for line in source:
            row = json.loads(line)
            review = watermark_reviews.get(row.get("source_id"))
            decision, reasons = admission_policy(
                row.get("parsed"),
                row.get("schema_errors"),
                review.get("alarm") if review else None,
            )
            row["policy_admission"] = decision
            row["policy_reasons"] = reasons
            if review:
                row["watermark_adjudication"] = review
            destination.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
