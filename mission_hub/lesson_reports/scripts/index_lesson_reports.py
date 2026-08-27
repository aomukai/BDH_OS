#!/usr/bin/env python3
"""Build deterministic grep-friendly indices for canonical lesson reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def text_findings(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [item["claim"] for item in values if isinstance(item, dict) and isinstance(item.get("claim"), str)]


def build(root: Path) -> list[dict]:
    rows = []
    for path in sorted(root.glob("[LR][0-9][0-9][0-9]/*/canonical-report.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        rows.append({
            "lesson_id": value["lesson_id"],
            "conducted_sequence_number": value["conducted_sequence_number"],
            "run_id": value["run_id"],
            "run_kind": value["run_kind"],
            "report_authority": value["report_authority"],
            "outcome": value["outcome"],
            "point_id": value["point"]["id"],
            "point": value["point"]["claim"],
            "topic": value["topic"],
            "tested_items": value["tested_items"],
            "actor_efforts": value["actor_efforts"],
            "capabilities": text_findings(value.get("capabilities")),
            "difficulties": text_findings(value.get("difficulties")),
            "world_knowledge": text_findings(value.get("world_knowledge")),
            "failure_tags": value["failure_tags"],
            "review_recommendations": value["review_recommendations"],
            "path": str(path.relative_to(root.parent.parent)),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.root.resolve()
    rows = build(root)
    (root / "index.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    lines = ["# Lesson report index", ""]
    for row in rows:
        lines.extend([
            f"## {row['lesson_id']} — {row['point']}", "",
            f"- Topic: {row['topic']}",
            f"- Run: {row['run_id']} ({row['run_kind']}, {row['report_authority']}, {row['outcome']})",
            f"- Tested items: {', '.join(row['tested_items']) or '-'}",
            f"- Luna efforts: builder={row['actor_efforts']['lesson_builder']}, conductor={row['actor_efforts']['lesson_conductor']}, analyst={row['actor_efforts']['post_lesson_analyst']}",
            f"- Capabilities: {'; '.join(row['capabilities']) or '-'}",
            f"- Difficulties: {'; '.join(row['difficulties']) or '-'}",
            f"- World knowledge: {'; '.join(row['world_knowledge']) or '-'}",
            f"- Failure tags: {', '.join(row['failure_tags']) or '-'}",
            f"- Reviews: {'; '.join(row['review_recommendations']) or '-'}",
            f"- Report: `{row['path']}`", "",
        ])
    (root / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"indexed {len(rows)} canonical lesson reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
