#!/usr/bin/env python3
"""Strict structural validator for generated Ninereeds vocabulary blocks."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANGUAGE = ROOT / "language"
STAGES = ("AFFIRMATIVE", "NEGATIVE", "W", "OR")
KINDS = ("PRESENTATION_QUESTION", "PRESENTATION_ANSWER", "TEST_QUESTION", "TEST_ANSWER")
LABELS = tuple(f"{stage}_{kind}" for stage in STAGES for kind in KINDS)


def main() -> None:
    errors: list[str] = []
    lesson_count = block_count = instance_count = 0
    for path in sorted(LANGUAGE.glob("L[0-9][0-9][0-9].md")):
        lesson_count += 1
        text = path.read_text(encoding="utf-8")
        sets = re.findall(r"^VOCAB_SET_(\d+): (.+)$", text, re.MULTILINE)
        blocks = re.split(r"^VOCAB_BLOCK_\d+:\n", text, flags=re.MULTILINE)[1:]
        block_headers = re.findall(r"^VOCAB_BLOCK_(\d+):$", text, re.MULTILINE)
        expected_headers = [str(i) for i in range(1, len(sets) + 1)]
        if block_headers != expected_headers:
            errors.append(f"{path.name}: block headers {block_headers}, expected {expected_headers}")
        if len(blocks) != len(sets):
            errors.append(f"{path.name}: {len(blocks)} blocks for {len(sets)} sets")
            continue
        block_count += len(blocks)
        for set_no, ((_, vocab), block) in enumerate(zip(sets, blocks), 1):
            items = [item.strip() for item in vocab.split(",")]
            if len(items) != 4:
                errors.append(f"{path.name} set {set_no}: {len(items)} vocabulary items")
            fields = re.findall(r"^- ([A-Z_]+):(.*)$", block, re.MULTILINE)
            found_labels = [label for label, _ in fields]
            if len(fields) != 64:
                errors.append(f"{path.name} block {set_no}: {len(fields)} fields, expected 64")
            for label in LABELS:
                count = found_labels.count(label)
                if count != 4:
                    errors.append(f"{path.name} block {set_no}: {label} occurs {count} times")
            for label, value in fields:
                if label.endswith("TEST_ANSWER") and value.strip():
                    errors.append(f"{path.name} block {set_no}: nonblank {label}")
                if (label.endswith("PRESENTATION_ANSWER") or label.endswith("_QUESTION")) and not value.strip():
                    errors.append(f"{path.name} block {set_no}: blank {label}")
            instance_count += 4
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print(f"OK: {lesson_count} lessons, {block_count} blocks, {instance_count} teaching instances")


if __name__ == "__main__":
    main()
