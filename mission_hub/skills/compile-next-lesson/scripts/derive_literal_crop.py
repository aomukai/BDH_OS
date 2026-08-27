#!/usr/bin/env python3
"""Derive one byte-stable literal crop from an approved lesson master image."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

from PIL import Image


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive(parent: Path, output: Path, xywh: tuple[int, int, int, int]) -> None:
    if output.exists():
        raise ValueError(f"refusing to overwrite existing crop: {output}")
    x, y, width, height = xywh
    if min(x, y) < 0 or min(width, height) < 1:
        raise ValueError("crop must be x>=0, y>=0, width>=1, height>=1")
    with Image.open(parent) as source:
        if x + width > source.width or y + height > source.height:
            raise ValueError(
                f"crop [{x},{y},{width},{height}] exceeds parent dimensions "
                f"{source.width}x{source.height}"
            )
        crop = source.crop((x, y, x + width, y + height))
        output.parent.mkdir(parents=True, exist_ok=True)
        crop.save(output, format="PNG", optimize=False, compress_level=9)
    print(f"parent_sha256={digest(parent)}")
    print(f"crop_xywh={x},{y},{width},{height}")
    print(f"output_sha256={digest(output)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--xywh", type=int, nargs=4, required=True, metavar=("X", "Y", "W", "H"))
    args = parser.parse_args()
    try:
        derive(args.parent.resolve(), args.output.resolve(), tuple(args.xywh))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
