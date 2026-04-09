from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import torch

from inference import BDHInference

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AnchorRule:
    prompt: str
    must_contain_any: tuple[str, ...]
    must_not_contain_any: tuple[str, ...] = ()


ANCHORS: tuple[AnchorRule, ...] = (
    AnchorRule(
        prompt="The sun is bright and",
        must_contain_any=("hot", "warm", "light", "sky"),
        must_not_contain_any=("animal",),
    ),
    AnchorRule(
        prompt="A dog is an animal that",
        must_contain_any=("runs", "walks", "rests", "ground", "fur", "legs", "tail"),
    ),
    AnchorRule(
        prompt="Rain falls from",
        must_contain_any=("cloud", "sky"),
    ),
    AnchorRule(
        prompt="A fish moves through",
        must_contain_any=("water",),
        must_not_contain_any=("air", "sky"),
    ),
    AnchorRule(
        prompt="The moon is hot because",
        must_contain_any=("cool", "night", "pale", "not"),
    ),
    AnchorRule(
        prompt="A fish flies over",
        must_contain_any=("water", "not"),
        must_not_contain_any=("sky",),
    ),
    AnchorRule(
        prompt="The dog shines in",
        must_contain_any=("ground", "yard", "house", "path"),
        must_not_contain_any=("water", "sky"),
    ),
    AnchorRule(
        prompt="The river has feathers",
        must_contain_any=("water", "bank", "flow", "river"),
        must_not_contain_any=("feather",),
    ),
    AnchorRule(
        prompt="The bird has",
        must_contain_any=("wings", "feathers", "beak"),
    ),
    AnchorRule(
        prompt="A vehicle is an animal that",
        must_contain_any=("not", "machine", "moves", "carries", "vehicle"),
        must_not_contain_any=("runs", "eats", "fur", "legs"),
    ),
    AnchorRule(
        prompt="The hungry bunny hops to the carrot",
        must_contain_any=("eat", "eats", "food", "carrot"),
        must_not_contain_any=("sleep", "sleeps"),
    ),
)


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _matches_rule(output: str, rule: AnchorRule) -> tuple[bool, list[str]]:
    text = output.lower()
    reasons: list[str] = []

    has_required = any(token in text for token in rule.must_contain_any)
    if not has_required:
        reasons.append(f"missing any required token: {rule.must_contain_any}")

    bad_tokens = [token for token in rule.must_not_contain_any if token in text]
    if bad_tokens:
        reasons.append(f"contains forbidden token(s): {tuple(bad_tokens)}")

    return (has_required and not bad_tokens), reasons


def run_probe(
    checkpoint: Path,
    *,
    device: str | None,
    max_new_tokens: int,
    seed: int,
) -> dict:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    infer = BDHInference(
        checkpoint,
        max_new_tokens=max_new_tokens,
        temperature=1.0,
        top_k=1,
        device=device,
    )

    rows = []
    passed = 0

    for rule in ANCHORS:
        out = infer.generate_text(rule.prompt)
        ok, reasons = _matches_rule(out, rule)
        if ok:
            passed += 1
        rows.append(
            {
                "prompt": rule.prompt,
                "output": out,
                "pass": ok,
                "reasons": reasons,
            }
        )

    total = len(ANCHORS)
    score = passed / total
    return {
        "checkpoint": str(checkpoint),
        "seed": seed,
        "device": str(infer.device),
        "max_new_tokens": max_new_tokens,
        "decode": {"temperature": 1.0, "top_k": 1},
        "score": {"passed": passed, "total": total, "ratio": round(score, 3)},
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Deterministic {len(ANCHORS)}-anchor probe for BDH checkpoints"
    )
    parser.add_argument("--checkpoint", type=Path, required=True, help="Checkpoint path")
    parser.add_argument("--device", type=str, default=None, help="cpu / cuda / mps (auto if omitted)")
    parser.add_argument("--max-new-tokens", type=int, default=64, help="Generation length per prompt")
    parser.add_argument("--seed", type=int, default=1337, help="Seed for deterministic generation")
    parser.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="Optional output directory (default: runs/anchor_probe_<timestamp>)",
    )
    args = parser.parse_args()

    if not args.checkpoint.exists():
        raise FileNotFoundError(f"Checkpoint not found: {args.checkpoint}")

    stamp = _utc_stamp()
    outdir = args.outdir if args.outdir is not None else ROOT / "runs" / f"anchor_probe_{stamp}"
    outdir.mkdir(parents=True, exist_ok=True)

    result = run_probe(
        args.checkpoint,
        device=args.device,
        max_new_tokens=args.max_new_tokens,
        seed=args.seed,
    )

    json_path = outdir / "anchor_probe.json"
    md_path = outdir / "anchor_probe.md"

    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# Anchor Probe",
        "",
        f"- checkpoint: `{result['checkpoint']}`",
        f"- device: `{result['device']}`",
        f"- seed: `{result['seed']}`",
        f"- decode: `temperature=1.0, top_k=1`",
        f"- score: **{result['score']['passed']}/{result['score']['total']}** ({result['score']['ratio']})",
        "",
        "## Results",
        "",
    ]

    for row in result["results"]:
        status = "PASS" if row["pass"] else "FAIL"
        lines.append(f"- [{status}] `{row['prompt']}` -> `{row['output'].replace(chr(10), ' ')}`")
        if row["reasons"]:
            lines.append(f"  reasons: {', '.join(row['reasons'])}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n============================================================")
    print("  Anchor Probe")
    print("============================================================")
    print(f"  Checkpoint: {result['checkpoint']}")
    print(f"  Device:     {result['device']}")
    print(f"  Seed:       {result['seed']}")
    print(f"  Score:      {result['score']['passed']}/{result['score']['total']} ({result['score']['ratio']})")
    print(f"  Saved:      {json_path}")
    print(f"              {md_path}")
    print()


if __name__ == "__main__":
    main()
