"""Eval harness for BDH.

Runs each prompt raw AND shaped with the same seed so the comparison is fair.
Scores for: garbage, repetition, drift, sentence formation.
Flags failure modes: loops, prompt-ignore, abrupt stop, hollow structure.
"""

from __future__ import annotations

import json
import re
import string
from datetime import datetime
from pathlib import Path

import torch

from inference import BDHInference
from prompt_shaper import shape

ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / "runs"

# ---------------------------------------------------------------------------
# Natural-language prompts — all go through the shaper for the shaped run
# ---------------------------------------------------------------------------

PROMPTS = [
    # Questions → shaper maps to definition or Q:/A:
    "What is a book?",
    "What is a friend?",
    "What is a school?",
    "Why do birds sing?",
    "Why do we sleep?",
    "How does a rainbow form?",

    # Causal / incomplete sentences → shaper passes through as fill
    "I am hungry because",
    "The old man walked slowly because",
    "She was afraid because",
    "The children laughed as they",

    # Narrative starters → shaper passes through as story
    "Once upon a time there was a",
    "She opened the door and saw",
    "It was a dark and quiet night when",

    # Descriptive / open
    "The best thing about summer is",
    "My favourite memory is",
    "The reason I like reading is",
    "If I could change one thing, I would",
    "Language is the way people",
]

# Locked config — best from previous eval
LOCKED_CONFIG = {"temperature": 0.8, "top_k": None, "max_new_tokens": 80}

# Fixed seeds — one per prompt, same seed used for both raw and shaped run
SEEDS = [42 + i * 7 for i in range(len(PROMPTS))]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_output(text: str) -> dict[str, float]:
    printable = set(string.printable)
    printable_ratio = sum(1 for c in text if c in printable) / max(len(text), 1)

    tokens = text.split()
    real_words = [t for t in tokens if re.fullmatch(r"[a-zA-Z''\-]{2,}", t)]
    word_ratio = len(real_words) / max(len(tokens), 1)

    words = [w.lower().strip(string.punctuation) for w in tokens]
    if len(words) >= 3:
        trigrams = [tuple(words[i:i+3]) for i in range(len(words) - 2)]
        no_repeat = len(set(trigrams)) / max(len(trigrams), 1)
    else:
        no_repeat = 1.0

    has_sentence = float(bool(re.search(r'[.!?]', text)))
    length_ok = min(len(tokens) / 10, 1.0)

    overall = (
        printable_ratio * 0.30
        + word_ratio    * 0.25
        + no_repeat     * 0.20
        + has_sentence  * 0.15
        + length_ok     * 0.10
    )

    return {
        "overall":   round(overall, 3),
        "printable": round(printable_ratio, 3),
        "words":     round(word_ratio, 3),
        "no_repeat": round(no_repeat, 3),
        "sentence":  round(has_sentence, 3),
        "length":    round(length_ok, 3),
    }


# ---------------------------------------------------------------------------
# Failure mode detection
# ---------------------------------------------------------------------------

def detect_failures(prompt: str, output: str) -> list[str]:
    """Return a list of failure mode labels found in the output."""
    failures = []
    tokens = output.split()

    # Loop: same 4-gram repeated
    words = [w.lower().strip(string.punctuation) for w in tokens]
    if len(words) >= 8:
        fourgrams = [tuple(words[i:i+4]) for i in range(len(words) - 3)]
        if len(fourgrams) > len(set(fourgrams)):
            failures.append("loop")

    # Abrupt stop: fewer than 6 tokens
    if len(tokens) < 6:
        failures.append("abrupt_stop")

    # Hollow structure: more than 30% whitespace/newline chars, few real words
    newline_ratio = output.count("\n") / max(len(output), 1)
    if newline_ratio > 0.15:
        failures.append("hollow_structure")

    # Prompt ignore: first real word of output has nothing to do with prompt
    # Simple heuristic — output starts with a pronoun/article when prompt was
    # a question (model should be continuing a definition, not starting a story)
    if prompt.strip().endswith("?"):
        first_word = tokens[0].lower().strip(string.punctuation) if tokens else ""
        if first_word in {"i", "he", "she", "they", "we", "it", "the", "a", "an", "so", "well"}:
            failures.append("prompt_ignore")

    return failures


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def utc_timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def generate_seeded(model: BDHInference, prompt: str, seed: int) -> str:
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    return model.generate_text(prompt)


def run_eval(checkpoint: str = "core/bdh_100m_final.pt") -> Path:
    ts = utc_timestamp()
    out_dir = RUNS_DIR / f"eval_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = LOCKED_CONFIG
    model = BDHInference(
        checkpoint_path=ROOT / checkpoint,
        max_new_tokens=cfg["max_new_tokens"],
        temperature=cfg["temperature"],
        top_k=cfg["top_k"],
    )

    results = []
    raw_scores = []
    shaped_scores = []

    for prompt, seed in zip(PROMPTS, SEEDS):
        shaped_prompt, shape_name = shape(prompt)

        raw_out    = generate_seeded(model, prompt,        seed)
        shaped_out = generate_seeded(model, shaped_prompt, seed)

        raw_sc    = score_output(raw_out)
        shaped_sc = score_output(shaped_out)
        raw_fail    = detect_failures(prompt,        raw_out)
        shaped_fail = detect_failures(shaped_prompt, shaped_out)

        delta = round(shaped_sc["overall"] - raw_sc["overall"], 3)

        raw_scores.append(raw_sc["overall"])
        shaped_scores.append(shaped_sc["overall"])

        results.append({
            "prompt":        prompt,
            "shaped_prompt": shaped_prompt,
            "shape_name":    shape_name,
            "seed":          seed,
            "raw": {
                "output":   raw_out,
                "scores":   raw_sc,
                "failures": raw_fail,
            },
            "shaped": {
                "output":   shaped_out,
                "scores":   shaped_sc,
                "failures": shaped_fail,
            },
            "delta": delta,
        })

    avg_raw    = round(sum(raw_scores)    / len(raw_scores),    3)
    avg_shaped = round(sum(shaped_scores) / len(shaped_scores), 3)
    avg_delta  = round(avg_shaped - avg_raw, 3)

    # Collect all failures across both modes
    all_failures: dict[str, int] = {}
    for r in results:
        for f in r["raw"]["failures"] + r["shaped"]["failures"]:
            all_failures[f] = all_failures.get(f, 0) + 1

    summary = {
        "config":        cfg,
        "avg_raw":       avg_raw,
        "avg_shaped":    avg_shaped,
        "avg_delta":     avg_delta,
        "failure_counts": all_failures,
        "results":       results,
    }

    (out_dir / "results.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # --- Print report ---
    print(f"\n{'='*60}")
    print(f"  RAW avg:    {avg_raw:.3f}")
    print(f"  SHAPED avg: {avg_shaped:.3f}   (delta {avg_delta:+.3f})")
    print(f"{'='*60}")

    if all_failures:
        print("\n  Failure modes detected:")
        for f, count in sorted(all_failures.items(), key=lambda x: -x[1]):
            print(f"    {f:20s}  {count}x")

    print("\n  Per-prompt breakdown (shaped delta, failures):")
    for r in results:
        fail_str = ", ".join(r["shaped"]["failures"]) or "—"
        print(f"  [{r['delta']:+.3f}] {r['prompt'][:45]!r:47s}  failures: {fail_str}")

    print(f"\n  Worst shaped outputs (lowest score):")
    worst = sorted(results, key=lambda r: r["shaped"]["scores"]["overall"])[:3]
    for r in worst:
        print(f"\n  [{r['shaped']['scores']['overall']:.2f}] {r['shaped_prompt']!r}")
        print(f"    raw    → {r['raw']['output']!r}")
        print(f"    shaped → {r['shaped']['output']!r}")

    print(f"\n  Best shaped outputs:")
    best = sorted(results, key=lambda r: -r["shaped"]["scores"]["overall"])[:3]
    for r in best:
        print(f"\n  [{r['shaped']['scores']['overall']:.2f}] {r['shaped_prompt']!r}")
        print(f"    → {r['shaped']['output']!r}")

    print(f"\nFull results saved to: {out_dir}")
    return out_dir


if __name__ == "__main__":
    run_eval()
