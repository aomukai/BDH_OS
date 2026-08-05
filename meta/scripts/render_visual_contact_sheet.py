#!/usr/bin/env python3
"""Render a labelled contact sheet from a foundational candidate receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--replacement-only", action="store_true")
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    rows = list(receipt["items"].values())
    if args.replacement_only:
        rows = [row for row in rows if row.get("replacement_spec_sha256")]
    rows = rows[args.offset : args.offset + args.count]
    columns = 4
    rows_count = (len(rows) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * 256, rows_count * 224), "white")
    draw = ImageDraw.Draw(canvas)
    for index, row in enumerate(rows):
        x, y = (index % columns) * 256, (index // columns) * 224
        with Image.open(args.catalog_root / row["object_path"]) as source:
            image = source.convert("RGB")
        image.thumbnail((248, 188))
        canvas.paste(image, (x + 4, y + 4))
        draw.text((x + 4, y + 194), f"{row['item_id']} | {row['canonical_caption']}", fill="black")
        draw.text((x + 4, y + 208), row["asset_sha256"][:12], fill="black")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, quality=92)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
