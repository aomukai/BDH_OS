"""Build a deterministic census of Ninereeds documentation source candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


INCLUDED_SUFFIXES = {".md", ".pdf", ".png"}
ARCHIVE_SURFACE_NAMES = {"docs", "handoff", "handoffs"}
EMBEDDED_ARCHIVE_PATTERNS = (
    "**/training/harness/*.md",
    "**/training/teacher_skills/*.md",
)
EMBEDDED_ARCHIVE_FILES = ("training_harness_design_pre_2026-05-23.md",)
HEADING = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _title(path: Path) -> str:
    if path.suffix.lower() == ".md":
        try:
            match = HEADING.search(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            match = None
        if match:
            return match.group(1).strip()
    return path.name


def candidate_paths(repo_root: Path) -> list[Path]:
    root = repo_root.resolve()
    candidates: set[Path] = set()
    for surface in (root / "docs", root / "handoff"):
        if surface.is_dir():
            candidates.update(
                path for path in surface.rglob("*")
                if path.is_file() and path.suffix.lower() in INCLUDED_SUFFIXES
            )
    archive = root / "archive"
    if archive.is_dir():
        for path in archive.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in INCLUDED_SUFFIXES:
                continue
            relative_parts = path.relative_to(archive).parts[:-1]
            if any(part.lower() in ARCHIVE_SURFACE_NAMES for part in relative_parts):
                candidates.add(path)
        for pattern in EMBEDDED_ARCHIVE_PATTERNS:
            candidates.update(path for path in archive.glob(pattern) if path.is_file())
        candidates.update(
            archive / relative for relative in EMBEDDED_ARCHIVE_FILES
            if (archive / relative).is_file()
        )
    return sorted(candidates, key=lambda path: path.relative_to(root).as_posix())


def build_census(repo_root: Path) -> dict:
    root = repo_root.resolve()
    records = []
    paths_by_hash: dict[str, list[str]] = {}
    for path in candidate_paths(root):
        relative = path.relative_to(root).as_posix()
        digest = _sha256(path)
        paths_by_hash.setdefault(digest, []).append(relative)
        records.append({
            "candidate_id": f"candidate-{hashlib.sha256(relative.encode()).hexdigest()[:16]}",
            "path": relative,
            "sha256": digest,
            "bytes": path.stat().st_size,
            "format": path.suffix.lower().removeprefix("."),
            "title": _title(path),
            "intake_disposition": "needs_identity_or_scope_review",
        })
    duplicate_groups = [
        {"sha256": digest, "paths": paths}
        for digest, paths in sorted(paths_by_hash.items()) if len(paths) > 1
    ]
    return {
        "schema_version": "ninereeds_source_census_v1",
        "generated_from": [
            "docs/", "handoff/",
            "archive/**/{docs,handoff,handoffs}/"
            ,"archive/**/training/{harness,teacher_skills}/",
            "archive/training_harness_design_pre_2026-05-23.md"
        ],
        "candidate_count": len(records),
        "unique_byte_count": len(paths_by_hash),
        "duplicate_groups": duplicate_groups,
        "candidates": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(build_census(args.root), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
