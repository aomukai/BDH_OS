#!/usr/bin/env python3
"""Bounded trainer for the 1.2B LFM Encoder → Ninereeds → LFM student."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import torch

from cortex.config import CORTEX_ARCHITECTURE
from cortex.student import build_student, save_cortex_checkpoint
from training.optim import FactoredAdamW
from training.pipeline.cortex.script_examples import examples_from_msm_script


def load_examples(path: Path, limit: int | None) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if set(value) < {"prompt", "completion"}:
                raise ValueError(f"{path}:{line_no} lacks prompt/completion")
            rows.append((str(value["prompt"]), str(value["completion"])))
            if limit is not None and len(rows) >= limit:
                break
    if not rows:
        raise ValueError("no Cortex examples")
    return rows


def batches(
    examples: list[tuple[str, str]],
    batch_size: int,
    *,
    seed: int,
) -> list[list[tuple[str, str]]]:
    order = list(examples)
    random.Random(seed).shuffle(order)
    return [order[index : index + batch_size] for index in range(0, len(order), batch_size)]


def clip_by_device(parameters, max_norm: float) -> None:
    grouped: dict[torch.device, list[torch.nn.Parameter]] = {}
    for parameter in parameters:
        if parameter.grad is not None:
            grouped.setdefault(parameter.device, []).append(parameter)
    for values in grouped.values():
        torch.nn.utils.clip_grad_norm_(values, max_norm, foreach=False)


@torch.no_grad()
def mean_loss(student, examples, batch_size: int) -> float:
    was_training = student.training
    student.eval()
    values = []
    try:
        for batch in batches(examples, batch_size, seed=0):
            prompts, responses = zip(*batch)
            values.append(float(student.response_loss(list(prompts), list(responses)).cpu()))
    finally:
        student.train(was_training)
    return sum(values) / len(values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--jsonl", type=Path)
    source.add_argument("--script-stdin", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parent", default="scratch")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--max-examples", type=int)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--ingress-device", default="cuda:0")
    parser.add_argument("--core-device", default="cuda:1")
    parser.add_argument(
        "--train-scope",
        choices=("full", "expression_bridge"),
        default="full",
    )
    parser.add_argument("--rms-clip", type=float)
    parser.add_argument("--stochastic-rounding", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--probe-max-new-tokens", type=int, default=16)
    parser.add_argument("--source-concept")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.lr <= 0:
        parser.error("epochs, batch-size, and lr must be positive")

    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    script = json.load(sys.stdin) if args.script_stdin else None
    if script is not None:
        examples = examples_from_msm_script(
            script,
            Path("training/pipeline/script_schema.json"),
        )
        if args.max_examples is not None:
            examples = examples[: args.max_examples]
        source_metadata = {
            "source_type": "msm_script",
            "script_id": script["script_id"],
            "session_id": script["session_id"],
            "concept": script["concept"],
            "script_fingerprint": script["script_fingerprint"],
        }
    else:
        assert args.jsonl is not None
        examples = load_examples(args.jsonl, args.max_examples)
        source_metadata = {
            "source_type": "jsonl",
            "jsonl_path": str(args.jsonl),
            **(
                {"concept": args.source_concept}
                if args.source_concept is not None
                else {}
            ),
        }
    if not examples:
        parser.error("training source produced no examples")
    parent = None if args.parent == "scratch" else Path(args.parent)
    started = time.time()
    student, parent_kind, optimizer_state = build_student(
        parent,
        frozen_dtype=torch.bfloat16,
        local_files_only=args.local_files_only,
    )
    partition = student.place(
        ingress_device=torch.device(args.ingress_device),
        core_device=torch.device(args.core_device),
        trainable_dtype=torch.bfloat16,
    )
    train_scope = student.set_train_scope(args.train_scope)
    trainable = list(student.trainable_parameters())
    optimizer = FactoredAdamW(
        trainable,
        lr=args.lr,
        weight_decay=args.weight_decay,
        momentum=True,
        rms_clip=args.rms_clip,
        stochastic_rounding=args.stochastic_rounding,
    )
    if optimizer_state is not None and args.train_scope == "full":
        optimizer.load_state_dict(
            optimizer_state,
            preserve_current_hyperparameters=True,
        )

    initial_loss = mean_loss(student, examples, args.batch_size)
    losses: list[float] = []
    student.train()
    for epoch in range(args.epochs):
        for batch in batches(examples, args.batch_size, seed=args.seed + epoch):
            prompts, responses = zip(*batch)
            optimizer.zero_grad(set_to_none=True)
            loss = student.response_loss(list(prompts), list(responses))
            loss.backward()
            clip_by_device(trainable, 1.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            print(
                f"epoch={epoch + 1} step={len(losses)} loss={losses[-1]:.6f}",
                file=sys.stderr,
                flush=True,
            )
    final_loss = mean_loss(student, examples, args.batch_size)
    ownership = student.ownership_report()
    if (
        ownership["encoder_parameters_with_gradients"]
        or ownership["lfm_parameters_with_gradients"]
    ):
        raise RuntimeError("frozen Cortex ownership boundary was violated")
    if not student.ingress.causal_runtime_is_restored():
        raise RuntimeError("LFM2 causal runtime was not restored after encoder inference")
    try:
        generated = student.generate_text(
            [examples[0][0]],
            max_new_tokens=args.probe_max_new_tokens,
        )
        generation_error = None
    except Exception as exc:
        generated = []
        generation_error = f"{type(exc).__name__}: {exc}"

    metadata = {
        "schema_version": "ninereeds_cortex_training_run_v1",
        "architecture": CORTEX_ARCHITECTURE,
        "parent_kind": parent_kind,
        "examples": len(examples),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "seed": args.seed,
        "train_scope": train_scope,
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "step_losses": losses,
        "optimizer": optimizer.policy(),
        "optimizer_state_bytes": optimizer.state_bytes(),
        "ownership": ownership,
        "partition": partition,
        "generated": generated,
        "generation_error": generation_error,
        "duration_seconds": round(time.time() - started, 3),
        "peak_vram_bytes": {
            str(index): torch.cuda.max_memory_allocated(index)
            for index in range(torch.cuda.device_count())
        },
        "training_source": source_metadata,
    }
    save_cortex_checkpoint(
        args.output,
        student,
        parent=args.parent,
        metadata=metadata,
        optimizer_state=(
            optimizer.state_dict()
            if args.train_scope == "full"
            else None
        ),
    )
    print(json.dumps({"checkpoint": str(args.output), "metadata": metadata}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
