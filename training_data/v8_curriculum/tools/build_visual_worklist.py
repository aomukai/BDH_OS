#!/usr/bin/env python3
"""Compile the authoritative v8 lesson headers into a visual-production worklist."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANGUAGE = ROOT / "language"
LESSON_RE = re.compile(r"^lesson (L\d{3})$")
FIELD_RE = re.compile(r"^([A-Z0-9_]+):\s*(.*)$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == "`":
        return value[1:-1]
    return value


def parse_lesson(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"empty lesson: {path}")
    match = LESSON_RE.fullmatch(lines[0].strip())
    if not match:
        raise ValueError(f"invalid lesson header: {path}")

    fields: dict[str, str] = {}
    vocab_sets: list[list[str]] = []
    for line in lines[1:]:
        if line.strip() == "PPP:":
            break
        field = FIELD_RE.match(line)
        if not field:
            continue
        name, raw = field.groups()
        if name.startswith("VOCAB_SET_"):
            values = [unquote(value) for value in raw.split(",") if value.strip()]
            if len(values) != 4:
                raise ValueError(f"{path}: {name} must contain four referents")
            vocab_sets.append(values)
        else:
            fields[name] = unquote(raw)

    required = {"POINT", "DIFFICULTY", "TOPIC", "GROUNDING"}
    missing = sorted(required - fields.keys())
    if missing:
        raise ValueError(f"{path}: missing fields: {', '.join(missing)}")
    if not vocab_sets:
        raise ValueError(f"{path}: no vocabulary sets")

    relative = path.relative_to(ROOT.parent.parent).as_posix()
    return {
        "lesson_id": match.group(1),
        "source_path": relative,
        "source_sha256": sha256(path),
        "point": fields["POINT"],
        "difficulty": int(fields["DIFFICULTY"]),
        "topic": fields["TOPIC"],
        "grounding": fields["GROUNDING"],
        "vocab_sets": vocab_sets,
        "referent_count": sum(map(len, vocab_sets)),
        "presentation_present": "_PRESENTATION_" in "\n".join(lines),
        "practice_present": "_TEST_" in "\n".join(lines),
        "performance_present": any(line.startswith("PERFORMANCE:") for line in lines),
    }


def compile_worklist() -> dict[str, object]:
    paths = sorted(LANGUAGE.glob("L[0-9][0-9][0-9].md"))
    lessons = [parse_lesson(path) for path in paths]
    expected_ids = [f"L{index:03d}" for index in range(1, 201)]
    actual_ids = [str(lesson["lesson_id"]) for lesson in lessons]
    if actual_ids != expected_ids:
        raise ValueError("language lesson sequence must be exactly L001 through L200")

    ordered_identity = hashlib.sha256(
        "\n".join(
            f"{lesson['lesson_id']}:{lesson['source_sha256']}" for lesson in lessons
        ).encode("utf-8")
    ).hexdigest()
    grounding_counts: dict[str, int] = {}
    for lesson in lessons:
        grounding = str(lesson["grounding"])
        grounding_counts[grounding] = grounding_counts.get(grounding, 0) + 1

    return {
        "schema_version": "ninereeds_v8_visual_worklist_v1",
        "curriculum_identity_sha256": ordered_identity,
        "lesson_count": len(lessons),
        "referent_count": sum(int(lesson["referent_count"]) for lesson in lessons),
        "grounding_counts": dict(sorted(grounding_counts.items())),
        "performance_contracts_present": sum(
            bool(lesson["performance_present"]) for lesson in lessons
        ),
        "lessons": lessons,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(compile_worklist(), indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
