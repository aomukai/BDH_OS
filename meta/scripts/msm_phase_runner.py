#!/usr/bin/env python3
"""Run one cold-start MSM phase block.

This runner is for Phase 0/1 style cold-start bootstrapping:

generate examples -> train one bounded block -> optionally probe -> write compact report

It is intentionally separate from the later MSM session loop. Phase 0 cannot assume
Ninereeds can produce gradeable answers before frontloaded training examples have changed
weights.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shlex
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MSM_ROOT = ROOT / "training/pipeline/msm"
REGISTRY_PATH = MSM_ROOT / "state/phase_registry.json"
CONFIG_PATH = MSM_ROOT / "state/orchestrator_config.json"
WORKING_PARENT_PATH = MSM_ROOT / "phase_blocks/current_parent.json"
UNSLOTH_PYTHON = Path("/home/aomukai/.unsloth/studio/unsloth_studio/bin/python")

PHASE0_WORDS = [
    "dog",
    "cat",
    "red",
    "blue",
    "sun",
    "tree",
    "water",
    "food",
    "book",
    "hand",
    "run",
    "sit",
    "look",
    "go",
    "yes",
    "no",
]

PHASE0_SENTENCES = [
    "A dog runs.",
    "A cat sits.",
    "The sun is up.",
    "A tree is green.",
    "Water is here.",
    "A book is open.",
]

SPEAKER_TAG_RE = re.compile(r"\[(?:user|ninereeds|teacher|trainer)\]", re.IGNORECASE)
WORD_RE = re.compile(r"[a-z0-9']+")

PHASE0_GATES = {
    "bounded_output_rate": 0.90,
    "word_form_copy_rate": 0.80,
    "sentence_shape_rate": 0.70,
    "max_speaker_tag_corruption_rate": 0.05,
    "max_loop_repetition_collapse_rate": 0.05,
    "max_byte_noise_or_malformed_fragment_rate": 0.10,
}

PHASE1_GATES = {
    "target_word_inclusion_rate": 0.85,
    "exact_or_near_word_reproduction_rate": 0.75,
    "bounded_output_rate": 0.90,
    "max_malformed_rate": 0.10,
}


class RunnerError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RunnerError(f"{rel(path)} must contain a JSON object")
    return data


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return load_json(path)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def train_python() -> str:
    env_value = os.environ.get("MSM_TRAIN_PYTHON")
    if env_value:
        return env_value
    if UNSLOTH_PYTHON.exists():
        return str(UNSLOTH_PYTHON)
    return sys.executable


def current_phase(registry: dict[str, Any]) -> str:
    phase_id = registry.get("current_phase_id")
    if not isinstance(phase_id, str) or not phase_id:
        raise RunnerError("phase_registry.current_phase_id must be a non-empty string")
    return phase_id


def next_block_id(phase_id: str) -> str:
    phase_dir = MSM_ROOT / "phase_blocks" / phase_id
    existing = sorted(path for path in phase_dir.glob(f"{phase_id}_block_*") if path.is_dir())
    return f"{phase_id}_block_{len(existing) + 1:04d}"


def phase_parent(config: dict[str, Any] | None, registry: dict[str, Any], explicit_parent: str | None) -> str:
    if explicit_parent:
        return explicit_parent
    working = load_optional_json(WORKING_PARENT_PATH)
    if working:
        parent = working.get("current_parent")
        if isinstance(parent, str) and parent:
            return parent
    if config:
        parent = config.get("checkpoint_policy", {}).get("current_parent")
        if isinstance(parent, str) and parent:
            return parent
    parent = registry.get("checkpoint_policy", {}).get("current_parent")
    if isinstance(parent, str) and parent:
        return parent
    return "scratch"


def record_working_parent(config: dict[str, Any] | None, checkpoint: str | None) -> None:
    if not checkpoint:
        return
    write_json(
        WORKING_PARENT_PATH,
        {
            "schema_version": "msm_working_parent_v1",
            "updated_at": utc_now(),
            "current_parent": checkpoint,
        },
    )


def phase0_examples(count: int, seed: int) -> list[dict[str, str]]:
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    templates = ["say", "copy"]
    while len(rows) < count:
        choice = rng.choice(["word", "sentence"])
        if choice == "word":
            word = rng.choice(PHASE0_WORDS)
            verb = rng.choice(templates)
            rows.append({
                "prompt": f"[user] {verb} {word}\n[Ninereeds]",
                "completion": f" {word}.",
            })
        else:
            sentence = rng.choice(PHASE0_SENTENCES)
            rows.append({
                "prompt": "[user] write a short sentence\n[Ninereeds]",
                "completion": f" {sentence}",
            })
    return rows


def phase1_examples(count: int, seed: int) -> list[dict[str, str]]:
    # Placeholder allowlist sample. Later this should read the canonical allowlist.
    rng = random.Random(seed)
    rows: list[dict[str, str]] = []
    while len(rows) < count:
        word = rng.choice(PHASE0_WORDS)
        rows.append({
            "prompt": f"[user] the word is {word}\n[Ninereeds]",
            "completion": f" {word} is a word.",
        })
    return rows


def generate_frontload(phase_id: str, count: int, seed: int) -> list[dict[str, str]]:
    if phase_id == "phase_0_form":
        return phase0_examples(count, seed)
    if phase_id == "phase_1_word_form":
        return phase1_examples(count, seed)
    raise RunnerError(
        f"{phase_id} is not implemented in msm_phase_runner.py yet. "
        "Phase 0 and Phase 1 are the cold-start runner prerequisites."
    )


def build_train_command(
    *,
    jsonl_path: Path,
    output_checkpoint: Path,
    parent: str,
    args: argparse.Namespace,
) -> list[str]:
    cmd = [
        train_python(),
        "-u",
        "train.py",
        "--phase",
        "0",
        "--jsonl-data",
        rel(jsonl_path),
        "--mask-instruction-loss",
        "--prompt-loss-weight",
        "0.0",
        "--prompt-tail-bytes",
        str(args.prompt_tail_bytes),
        "--block-size",
        str(args.block_size),
        "--epochs",
        str(args.epochs),
        "--lr",
        str(args.lr),
        "--batch-size",
        str(args.batch_size),
        "--output",
        rel(output_checkpoint),
        "--skip-training-audit",
        "--seed",
        str(args.seed),
    ]
    if args.no_shuffle:
        cmd.append("--no-shuffle")
    if args.amp_bf16:
        cmd.append("--amp-bf16")
    if args.adam8bit:
        cmd.append("--adam8bit")
    if args.device:
        cmd.extend(["--device", args.device])
    if parent != "scratch":
        parent_path = ROOT / parent if not Path(parent).is_absolute() else Path(parent)
        if not parent_path.exists():
            raise RunnerError(f"parent checkpoint not found: {parent}")
        cmd.extend(["--resume", rel(parent_path)])
    return cmd


def run_train(cmd: list[str], stdout_path: Path) -> None:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(cmd, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RunnerError(f"train.py failed with exit code {proc.returncode}; see {rel(stdout_path)}")


def phase_probes(phase_id: str) -> list[dict[str, str]]:
    if phase_id == "phase_0_form":
        return [
            {"probe_id": "p001", "prompt": "[user] say dog\n[Ninereeds]", "target": "word_copy", "expected_text": "dog"},
            {"probe_id": "p002", "prompt": "[user] say cat\n[Ninereeds]", "target": "word_copy", "expected_text": "cat"},
            {"probe_id": "p003", "prompt": "[user] say red\n[Ninereeds]", "target": "word_copy", "expected_text": "red"},
            {"probe_id": "p004", "prompt": "[user] say blue\n[Ninereeds]", "target": "word_copy", "expected_text": "blue"},
            {
                "probe_id": "p005",
                "prompt": "[user] write a short sentence\n[Ninereeds]",
                "target": "sentence_shape",
                "expected_text": "",
            },
            {
                "probe_id": "p006",
                "prompt": "[user] write a short sentence\n[Ninereeds]",
                "target": "sentence_shape",
                "expected_text": "",
            },
        ]
    if phase_id == "phase_1_word_form":
        return [
            {"probe_id": "p001", "prompt": "[user] the word is dog\n[Ninereeds]", "target": "word_form", "expected_text": "dog"},
            {"probe_id": "p002", "prompt": "[user] the word is cat\n[Ninereeds]", "target": "word_form", "expected_text": "cat"},
            {"probe_id": "p003", "prompt": "[user] copy water\n[Ninereeds]", "target": "word_form", "expected_text": "water"},
            {"probe_id": "p004", "prompt": "[user] copy book\n[Ninereeds]", "target": "word_form", "expected_text": "book"},
        ]
    raise RunnerError(f"{phase_id} has no implemented probe manifest.")


def write_probe_manifest(path: Path, phase_id: str) -> list[dict[str, str]]:
    probes = phase_probes(phase_id)
    append_jsonl(path, probes)
    return probes


def printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    printable = 0
    for char in text:
        category = unicodedata.category(char)
        if char in "\n\t" or not category.startswith("C"):
            printable += 1
    return printable / len(text)


def word_tokens(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def has_repetition_loop(text: str) -> bool:
    if re.search(r"(.)\1{7,}", text):
        return True
    words = word_tokens(text)
    if len(words) >= 8:
        trigrams = [tuple(words[index:index + 3]) for index in range(len(words) - 2)]
        if len(set(trigrams)) < len(trigrams):
            return True
    compact = "".join(ch for ch in text.lower() if not ch.isspace())
    if len(compact) >= 16:
        chunks = [compact[index:index + 4] for index in range(len(compact) - 3)]
        if len(set(chunks)) < len(chunks) * 0.75:
            return True
    return False


def sentence_shape_ok(text: str) -> bool:
    words = word_tokens(text)
    return len(words) >= 3 and bool(re.search(r"[.!?]", text))


def evaluate_probe(phase_id: str, probe: dict[str, str], output: str) -> dict[str, Any]:
    text = output.strip()
    target = probe["target"]
    expected = probe.get("expected_text", "").lower()
    words = word_tokens(text)
    tag_corruption = bool(SPEAKER_TAG_RE.search(text))
    loop = has_repetition_loop(text)
    malformed = not text or "\ufffd" in text or "\x00" in text or printable_ratio(text) < 0.90
    bounded = bool(text) and len(text.encode("utf-8", errors="replace")) <= 128 and text.count("\n") <= 2 and not tag_corruption
    printable = bool(text) and printable_ratio(text) >= 0.95

    target_pass = False
    exact_or_near = False
    if target in {"word_copy", "word_form"} and expected:
        target_pass = expected in words[:8]
        exact_or_near = bool(words) and words[0] == expected
    elif target == "sentence_shape":
        target_pass = sentence_shape_ok(text)

    return {
        "schema_version": "msm_phase_probe_result_v1",
        "phase_id": phase_id,
        "probe_id": probe["probe_id"],
        "prompt": probe["prompt"],
        "target": target,
        "expected_text": probe.get("expected_text"),
        "output": text,
        "bounded_output": bounded,
        "printable_text": printable,
        "target_pass": target_pass,
        "exact_or_near_word_reproduction": exact_or_near,
        "speaker_tag_corruption": tag_corruption,
        "repetition_collapse": loop,
        "malformed": malformed,
    }


def rate(rows: list[dict[str, Any]], key: str, *, target: str | None = None) -> float:
    selected = [row for row in rows if target is None or row.get("target") == target]
    if not selected:
        return 0.0
    return round(sum(1 for row in selected if row.get(key) is True) / len(selected), 3)


def summarize_probe_results(phase_id: str, rows: list[dict[str, Any]]) -> tuple[dict[str, Any], str, str, str]:
    metrics: dict[str, Any] = {
        "probe_execution": "implemented",
        "probe_count": len(rows),
        "bounded_output_rate": rate(rows, "bounded_output"),
        "printable_text_rate": rate(rows, "printable_text"),
        "speaker_tag_corruption_rate": round(sum(1 for row in rows if row["speaker_tag_corruption"]) / max(len(rows), 1), 3),
        "loop_repetition_collapse_rate": round(sum(1 for row in rows if row["repetition_collapse"]) / max(len(rows), 1), 3),
        "byte_noise_or_malformed_fragment_rate": round(sum(1 for row in rows if row["malformed"]) / max(len(rows), 1), 3),
    }

    if phase_id == "phase_0_form":
        metrics["word_form_copy_rate"] = rate(rows, "target_pass", target="word_copy")
        metrics["sentence_shape_rate"] = rate(rows, "target_pass", target="sentence_shape")
        passed = (
            metrics["bounded_output_rate"] >= PHASE0_GATES["bounded_output_rate"]
            and metrics["word_form_copy_rate"] >= PHASE0_GATES["word_form_copy_rate"]
            and metrics["sentence_shape_rate"] >= PHASE0_GATES["sentence_shape_rate"]
            and metrics["speaker_tag_corruption_rate"] <= PHASE0_GATES["max_speaker_tag_corruption_rate"]
            and metrics["loop_repetition_collapse_rate"] <= PHASE0_GATES["max_loop_repetition_collapse_rate"]
            and metrics["byte_noise_or_malformed_fragment_rate"] <= PHASE0_GATES["max_byte_noise_or_malformed_fragment_rate"]
        )
    elif phase_id == "phase_1_word_form":
        metrics["target_word_inclusion_rate"] = rate(rows, "target_pass", target="word_form")
        metrics["exact_or_near_word_reproduction_rate"] = rate(rows, "exact_or_near_word_reproduction", target="word_form")
        metrics["malformed_rate"] = metrics["byte_noise_or_malformed_fragment_rate"]
        passed = (
            metrics["target_word_inclusion_rate"] >= PHASE1_GATES["target_word_inclusion_rate"]
            and metrics["exact_or_near_word_reproduction_rate"] >= PHASE1_GATES["exact_or_near_word_reproduction_rate"]
            and metrics["bounded_output_rate"] >= PHASE1_GATES["bounded_output_rate"]
            and metrics["malformed_rate"] <= PHASE1_GATES["max_malformed_rate"]
        )
    else:
        raise RunnerError(f"{phase_id} probe summarization is not implemented.")

    if passed:
        return metrics, "met", "phase_gate_review", "Phase probe gate met; orchestrator should review promotion."
    return metrics, "not_met", "run_next_block_same_phase", "Phase probe gate not met; local runner may continue with another bounded block."


def run_probes(
    *,
    checkpoint: Path,
    phase_id: str,
    probes: list[dict[str, str]],
    results_path: Path,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], str, str, str]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import torch
    from inference import BDHInference

    model = BDHInference(
        checkpoint_path=checkpoint,
        max_new_tokens=args.probe_max_new_tokens,
        temperature=args.probe_temperature,
        top_k=args.probe_top_k,
        device=args.device,
    )
    rows: list[dict[str, Any]] = []
    for index, probe in enumerate(probes):
        torch.manual_seed(args.seed + 10_000 + index)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(args.seed + 10_000 + index)
        output = model.generate_text(probe["prompt"])
        rows.append(evaluate_probe(phase_id, probe, output))
    append_jsonl(results_path, rows)
    return summarize_probe_results(phase_id, rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-id", default=None, help="Phase to run; defaults to phase_registry.current_phase_id")
    parser.add_argument("--parent", default=None, help="Parent checkpoint or 'scratch'. Defaults to registry checkpoint policy or scratch.")
    parser.add_argument("--examples", type=int, default=128, help="Frontload examples in this block.")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--block-size", type=int, default=128)
    parser.add_argument("--prompt-tail-bytes", type=int, default=64)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--device", default=None)
    parser.add_argument("--amp-bf16", action="store_true")
    parser.add_argument("--adam8bit", action="store_true")
    parser.add_argument("--no-shuffle", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Write artifacts and command, but do not run train.py.")
    parser.add_argument("--skip-probes", action="store_true", help="Train and report without executing phase probes.")
    parser.add_argument("--probe-max-new-tokens", type=int, default=32)
    parser.add_argument("--probe-temperature", type=float, default=0.2)
    parser.add_argument("--probe-top-k", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.examples <= 0:
        raise RunnerError("--examples must be > 0")
    if args.prompt_tail_bytes >= args.block_size:
        raise RunnerError("--prompt-tail-bytes must be < --block-size")

    registry = load_json(REGISTRY_PATH)
    config = load_optional_json(CONFIG_PATH)
    phase_id = args.phase_id or current_phase(registry)
    block_id = next_block_id(phase_id)
    block_dir = MSM_ROOT / "phase_blocks" / phase_id / block_id
    frontload_path = block_dir / "frontload.jsonl"
    probe_path = block_dir / "probes.jsonl"
    probe_results_path = block_dir / "probe_results.jsonl"
    stdout_path = block_dir / "train_stdout.log"
    report_path = block_dir / "block_report.json"
    runner_status_path = block_dir / "runner_status.json"
    output_checkpoint = ROOT / "core/msm" / f"{block_id}.pt"
    parent = phase_parent(config, registry, args.parent)

    rows = generate_frontload(phase_id, args.examples, args.seed)
    append_jsonl(frontload_path, rows)
    probes = write_probe_manifest(probe_path, phase_id)

    cmd = build_train_command(
        jsonl_path=frontload_path,
        output_checkpoint=output_checkpoint,
        parent=parent,
        args=args,
    )

    status = "planned"
    checkpoint_after: str | None = None
    metrics: dict[str, Any] = {
        "probe_execution": "not_run",
        "frontload_examples": len(rows),
    }
    gate_status = "not_evaluated"
    recommendation = "escalate_orchestrator"
    notes = "Dry run only; train.py was not executed." if args.dry_run else None

    try:
        if not args.dry_run:
            write_json(runner_status_path, {
                "schema_version": "msm_phase_runner_status_v1",
                "updated_at": utc_now(),
                "phase_id": phase_id,
                "block_id": block_id,
                "status": "training",
            })
            run_train(cmd, stdout_path)
            if not output_checkpoint.exists():
                raise RunnerError(f"expected output checkpoint missing: {rel(output_checkpoint)}")
            status = "trained"
            checkpoint_after = rel(output_checkpoint)
            if args.skip_probes:
                metrics["probe_execution"] = "skipped"
                notes = "Training block completed, but probes were skipped. Orchestrator decision required."
            else:
                write_json(runner_status_path, {
                    "schema_version": "msm_phase_runner_status_v1",
                    "updated_at": utc_now(),
                    "phase_id": phase_id,
                    "block_id": block_id,
                    "status": "probing",
                })
                probe_metrics, gate_status, recommendation, notes = run_probes(
                    checkpoint=output_checkpoint,
                    phase_id=phase_id,
                    probes=probes,
                    results_path=probe_results_path,
                    args=args,
                )
                metrics.update(probe_metrics)
                status = "probed"
    except Exception as exc:
        status = "failed"
        gate_status = "blocked"
        recommendation = "blocked"
        notes = str(exc)

    report = {
        "schema_version": "msm_phase_block_report_v1",
        "phase_id": phase_id,
        "block_id": block_id,
        "created_at": utc_now(),
        "status": status,
        "checkpoint_before": parent,
        "checkpoint_after": checkpoint_after,
        "frontload_examples": len(rows),
        "train_command": cmd,
        "probe_command": None,
        "metrics": metrics,
        "gate_status": gate_status,
        "local_recommendation": recommendation,
        "artifacts": {
            "frontload_jsonl": rel(frontload_path),
            "probe_jsonl": rel(probe_path),
            "probe_results_jsonl": rel(probe_results_path) if probe_results_path.exists() else None,
            "train_stdout": rel(stdout_path) if stdout_path.exists() else None,
            "report_json": rel(report_path),
        },
        "notes": notes,
    }
    write_json(report_path, report)
    if status == "probed":
        record_working_parent(config, checkpoint_after)
    write_json(runner_status_path, {
        "schema_version": "msm_phase_runner_status_v1",
        "updated_at": utc_now(),
        "phase_id": phase_id,
        "block_id": block_id,
        "status": status,
        "report_json": rel(report_path),
    })
    print(json.dumps({"block_report": rel(report_path), "status": status, "train_command": shlex.join(cmd)}, indent=2))
    return 1 if status == "failed" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
