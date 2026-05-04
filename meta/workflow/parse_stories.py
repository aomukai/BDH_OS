"""Convert concept stories into LoRA training data.

Reads all .md (or .txt) phase files from a directory of 6-sentence concept
stories. Blocks are separated by blank lines. Writes two JSONL files:

  pairwise.jsonl   — each sentence predicts the next (5 pairs per story)
  sliding.jsonl    — growing context window (full story visible)

Usage:
    # Process all phases from training_data/, write to knowledge/curriculum/
    python workflow/parse_stories.py

    # Explicit paths
    python workflow/parse_stories.py --data training_data/ --out knowledge/curriculum/

    # Single file (backwards compatible)
    python workflow/parse_stories.py --file "training_data/phase 1.md"

Input format (one story per block, blocks separated by blank lines):
    This is a bird.
    The bird is small.
    The bird has feathers.
    The bird is in the sky.
    The bird flies to the nest.
    A bird is an animal.

    This is an apple.
    ...
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_stories(text: str) -> list[list[str]]:
    """Split text into stories, each a list of sentences."""
    stories = []
    current: list[str] = []

    for line in text.splitlines():
        line = line.strip()
        if line:
            current.append(line)
        else:
            if current:
                stories.append(current)
                current = []

    if current:
        stories.append(current)

    return stories


def validate_story(sentences: list[str], index: int, source: str = "") -> list[str]:
    """Return list of warning strings (empty = valid)."""
    warnings = []
    loc = f"{source} story {index+1}" if source else f"story {index+1}"

    if len(sentences) != 6:
        warnings.append(f"{loc}: expected 6 sentences, got {len(sentences)}")
        return warnings

    if not sentences[0].lower().startswith("this is"):
        warnings.append(f"{loc}: sentence 1 should start with 'This is'")

    last = sentences[5].lower()
    # Valid category forms:
    #   "A/The X is a/an Y."          — standard
    #   "The X is the Y of Z."        — part-of concepts (Phase 3), intentional
    #   "X is a/an Y." / "X is Y."    — mass nouns (frost, wood, etc.)
    #   "X are Y."                    — plural nouns (pants, etc.)
    has_category = (
        " is a " in last
        or " is an " in last
        or " is the " in last
        or " is " in last  # broad fallback; catches "X is Y." mass-noun forms
        or " are " in last
    )
    if not has_category:
        warnings.append(f"{loc}: sentence 6 may not be a category statement: {sentences[5]!r}")

    return warnings


# ---------------------------------------------------------------------------
# Training example generators
# ---------------------------------------------------------------------------

def pairwise(sentences: list[str]) -> list[dict]:
    """Each sentence → next sentence. 5 pairs per 6-sentence story."""
    return [
        {"prompt": sentences[i], "completion": f" {sentences[i+1]}"}
        for i in range(len(sentences) - 1)
    ]


def sliding(sentences: list[str]) -> list[dict]:
    """Growing context window. Story so far → next sentence."""
    examples = []
    for i in range(1, len(sentences)):
        prompt = " ".join(sentences[:i])
        examples.append({"prompt": prompt, "completion": f" {sentences[i]}"})
    return examples


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, examples: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")


def collect_phase_files(data_dir: Path) -> list[Path]:
    """Return .md and .txt files in data_dir, sorted by name."""
    files = sorted(
        p for p in data_dir.iterdir()
        if p.suffix in {".md", ".txt"} and p.is_file()
    )
    return files


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Convert concept stories to training JSONL")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--data", type=Path, default=Path("training_data"),
                       help="Directory containing phase .md/.txt files (default: training_data/)")
    group.add_argument("--file", type=Path,
                       help="Single story file (overrides --data)")
    parser.add_argument("--out", type=Path, default=Path("knowledge/curriculum"),
                        help="Output directory (default: knowledge/curriculum/)")
    args = parser.parse_args()

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build list of (path, label) to process
    if args.file:
        if not args.file.exists():
            sys.exit(f"File not found: {args.file}")
        sources: list[tuple[Path, str]] = [(args.file, args.file.name)]
    else:
        if not args.data.exists():
            sys.exit(f"Directory not found: {args.data}")
        phase_files = collect_phase_files(args.data)
        if not phase_files:
            sys.exit(f"No .md or .txt files found in {args.data}")
        sources = [(p, p.name) for p in phase_files]

    # Parse all sources
    all_pairwise: list[dict] = []
    all_sliding:  list[dict] = []
    all_warnings: list[str] = []
    total_stories = 0

    for path, label in sources:
        text = path.read_text(encoding="utf-8")
        stories = parse_stories(text)
        if not stories:
            print(f"  [skip] {label} — no stories found")
            continue

        file_warnings: list[str] = []
        for i, s in enumerate(stories):
            file_warnings.extend(validate_story(s, i, source=label))

        all_warnings.extend(file_warnings)
        total_stories += len(stories)

        for sentences in stories:
            all_pairwise.extend(pairwise(sentences))
            all_sliding.extend(sliding(sentences))

        status = f"  {len(file_warnings)} warning(s)" if file_warnings else "  ok"
        print(f"  {label:<30} {len(stories):>4} stories{status}")

    print()

    if not total_stories:
        sys.exit("No stories parsed across all files.")

    if all_warnings:
        print("Warnings:")
        for w in all_warnings:
            print(f"  !  {w}")
        print()

    pair_path    = out_dir / "pairwise.jsonl"
    sliding_path = out_dir / "sliding.jsonl"

    write_jsonl(pair_path,    all_pairwise)
    write_jsonl(sliding_path, all_sliding)

    print(f"Stories parsed     : {total_stories}")
    print(f"Pairwise examples  : {len(all_pairwise)}  -> {pair_path}")
    print(f"Sliding examples   : {len(all_sliding)}   -> {sliding_path}")

    if all_warnings:
        print(f"\n{len(all_warnings)} warning(s) above — review before training.")
    else:
        print("\nAll stories valid.")

    # Quick preview of very first story parsed
    first_stories: list[list[str]] = []
    if sources:
        first_text = sources[0][0].read_text(encoding="utf-8")
        first_stories = parse_stories(first_text)

    if first_stories:
        s = first_stories[0]
        print(f"\n--- Preview: first story from {sources[0][1]}, pairwise ---")
        for ex in pairwise(s):
            print(f"  {json.dumps(ex, ensure_ascii=False)}")

        print(f"\n--- Preview: first story from {sources[0][1]}, sliding ---")
        for ex in sliding(s):
            print(f"  {json.dumps(ex, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
