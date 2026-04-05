"""Convert concept stories into LoRA training data.

Reads a plain text file of 6-sentence concept stories (one story per block,
blocks separated by blank lines). Writes two JSONL files:

  pairwise.jsonl     — each sentence predicts the next (short context, easy to debug)
  sliding.jsonl      — growing context window (full story visible, stronger signal)

Usage:
    python workflow/parse_stories.py stories.txt
    python workflow/parse_stories.py stories.txt --out knowledge/curriculum/

Input format (one story per block):
    This is a bird.
    The bird is small.
    The bird has feathers.
    The bird is in the sky.
    The bird flies to the nest.
    A bird is an animal.

    This is an apple.
    ...

Both output files go to --out directory (default: same directory as input file).
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


def validate_story(sentences: list[str], index: int) -> list[str]:
    """Return list of warning strings (empty = valid)."""
    warnings = []

    if len(sentences) != 6:
        warnings.append(f"story {index+1}: expected 6 sentences, got {len(sentences)}")

    if sentences and not sentences[0].lower().startswith("this is"):
        warnings.append(f"story {index+1}: sentence 1 should start with 'This is'")

    if len(sentences) == 6:
        last = sentences[5].lower()
        if " is a " not in last and " is an " not in last:
            warnings.append(f"story {index+1}: sentence 6 should be a category statement (e.g. 'A/The ball is a toy.')")

    return warnings


# ---------------------------------------------------------------------------
# Generators
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
# Main
# ---------------------------------------------------------------------------

def write_jsonl(path: Path, examples: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert concept stories to training JSONL")
    parser.add_argument("input", type=Path, help="Plain text file of stories")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output directory (default: same as input file)")
    args = parser.parse_args()

    if not args.input.exists():
        sys.exit(f"File not found: {args.input}")

    out_dir = args.out or args.input.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    text = args.input.read_text(encoding="utf-8")
    stories = parse_stories(text)

    if not stories:
        sys.exit("No stories found. Check that blocks are separated by blank lines.")

    # Validate
    all_warnings = []
    for i, s in enumerate(stories):
        all_warnings.extend(validate_story(s, i))

    if all_warnings:
        print("Warnings:")
        for w in all_warnings:
            print(f"  ⚠  {w}")
        print()

    # Generate
    all_pairwise: list[dict] = []
    all_sliding:  list[dict] = []

    for sentences in stories:
        all_pairwise.extend(pairwise(sentences))
        all_sliding.extend(sliding(sentences))

    pair_path    = out_dir / "pairwise.jsonl"
    sliding_path = out_dir / "sliding.jsonl"

    write_jsonl(pair_path,    all_pairwise)
    write_jsonl(sliding_path, all_sliding)

    # Report
    print(f"Stories parsed     : {len(stories)}")
    print(f"Pairwise examples  : {len(all_pairwise)}  → {pair_path}")
    print(f"Sliding examples   : {len(all_sliding)}   → {sliding_path}")

    if all_warnings:
        print(f"\n{len(all_warnings)} warning(s) above — review before training.")
    else:
        print("\nAll stories valid.")

    # Quick preview of first story, both formats
    if stories:
        print("\n--- Preview: first story, pairwise ---")
        for ex in pairwise(stories[0]):
            print(f"  {json.dumps(ex, ensure_ascii=False)}")

        print("\n--- Preview: first story, sliding ---")
        for ex in sliding(stories[0]):
            print(f"  {json.dumps(ex, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
