from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open(encoding="utf-8") as source, args.output.open("w", encoding="utf-8") as output:
        for line in source:
            item = json.loads(line)
            draft = {
                "ordinal": item["ordinal"],
                "source": item["source"],
                "source_id": item["source_id"],
                "local_path": item["local_path"],
                "source_object_counts": item["object_counts"],
                "source_relationships": item["relationships"],
                "human_review": {
                    "status": "pending",
                    "admission": None,
                    "visible_text": None,
                    "watermark": None,
                    "quality_flags": [],
                    "literal_caption": None,
                    "notes": [],
                },
            }
            output.write(json.dumps(draft, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
