#!/usr/bin/env python3
"""Bounded trainer for the 1.2B LFM Encoder → Ninereeds → LFM student."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import torch

from cortex.config import CORTEX_ARCHITECTURE
from cortex.student import build_student, save_cortex_checkpoint
from training.optim import FactoredAdamW
from training.diagnostics import GateCreditRecorder


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_examples(path: Path, limit: int | None) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if set(value) < {"prompt", "completion"}:
                raise ValueError(f"{path}:{line_no} lacks prompt/completion")
            rows.append({
                "prompt": str(value["prompt"]),
                "completion": str(value["completion"]),
                "metadata": {
                    key: item for key, item in value.items()
                    if key not in {"prompt", "completion"}
                },
            })
            if limit is not None and len(rows) >= limit:
                break
    if not rows:
        raise ValueError("no Cortex examples")
    return rows


def batches(
    examples: list,
    batch_size: int,
) -> list[list]:
    return [examples[index : index + batch_size] for index in range(0, len(examples), batch_size)]


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
        for batch in batches(examples, batch_size):
            prompts = [row["prompt"] for row in batch]
            responses = [row["completion"] for row in batch]
            values.append(float(student.response_loss(prompts, responses).cpu()))
    finally:
        student.train(was_training)
    return sum(values) / len(values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, required=True)
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
    parser.add_argument("--order-policy", required=True, choices=("declared_only",))
    parser.add_argument("--identity-policy-sha256", required=True)
    parser.add_argument("--identity-scope", required=True, choices=("excluded", "identity_and_integrity"))
    parser.add_argument("--campaign-contract-sha256", required=True)
    parser.add_argument("--training-mode", required=True, choices=("bootstrap", "advancement", "experimental", "evolutionary", "merge"))
    parser.add_argument("--branch-id", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--ordered-source-sha256", required=True)
    parser.add_argument("--gate-credit-report", type=Path)
    parser.add_argument("--gate-credit-log-every", type=int)
    parser.add_argument("--gate-credit-max-sampled-steps", type=int)
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.lr <= 0:
        parser.error("epochs, batch-size, and lr must be positive")
    if len(args.campaign_contract_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in args.campaign_contract_sha256
    ):
        parser.error("campaign-contract-sha256 must be a lowercase SHA-256 digest")

    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    examples = load_examples(args.jsonl, args.max_examples)
    gate_credit_enabled = args.gate_credit_report is not None
    if gate_credit_enabled != bool(
        args.gate_credit_log_every and args.gate_credit_max_sampled_steps
    ):
        parser.error("gate-credit report and positive sampling bounds must be supplied together")
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
    recorder = (
        GateCreditRecorder(
            log_every_n_steps=args.gate_credit_log_every,
            max_sampled_steps=args.gate_credit_max_sampled_steps,
        )
        if gate_credit_enabled else None
    )
    parameter_names = {id(parameter): name for name, parameter in student.named_parameters()}
    if recorder is not None:
        optimizer.diagnostic_callback = lambda parameter, gradient, update, lr: recorder.observe_optimizer_update(
            parameter_names.get(id(parameter), "unknown"), parameter, gradient, update, lr,
        )
    if optimizer_state is not None and args.train_scope == "full":
        optimizer.load_state_dict(
            optimizer_state,
            preserve_current_hyperparameters=True,
        )

    initial_loss = mean_loss(student, examples, args.batch_size)
    if not math.isfinite(initial_loss):
        raise RuntimeError("initial training loss is non-finite; checkpoint is structurally invalid")
    losses: list[float] = []
    student.train()
    for epoch in range(args.epochs):
        for batch in batches(examples, args.batch_size):
            prompts = [row["prompt"] for row in batch]
            responses = [row["completion"] for row in batch]
            step = len(losses) + 1
            sampled = recorder.begin_step(
                step, epoch=epoch + 1,
                source_metadata=[row["metadata"] for row in batch],
            ) if recorder is not None else False
            optimizer.zero_grad(set_to_none=True)
            loss = student.response_loss(
                prompts, responses,
                gate_credit_observer=recorder if sampled else None,
            )
            if not bool(torch.isfinite(loss)):
                raise RuntimeError("training loss became non-finite; candidate checkpoint will not be written")
            loss.backward()
            clip_by_device(trainable, 1.0)
            optimizer.step()
            if recorder is not None:
                recorder.finish_step()
            losses.append(float(loss.detach().cpu()))
            print(
                f"epoch={epoch + 1} step={len(losses)} loss={losses[-1]:.6f}",
                file=sys.stderr,
                flush=True,
            )
    final_loss = mean_loss(student, examples, args.batch_size)
    if not math.isfinite(final_loss):
        raise RuntimeError("final training loss is non-finite; candidate checkpoint will not be written")
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
            [examples[0]["prompt"]],
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
        "example_order": "declared",
        "order_policy": args.order_policy,
        "shuffle_allowed": False,
        "identity_policy_sha256": args.identity_policy_sha256,
        "identity_scope": args.identity_scope,
        "campaign_contract_sha256": args.campaign_contract_sha256,
        "training_mode": args.training_mode,
        "branch_id": None if args.branch_id == "unbranched" else args.branch_id,
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
        "gate_credit_diagnostics": {
            "enabled": gate_credit_enabled,
            **({
                "schema_version": "ninereeds_gate_credit_diagnostics_v1",
                "log_every_n_steps": args.gate_credit_log_every,
                "max_sampled_steps": args.gate_credit_max_sampled_steps,
                "sampled_step_count": len(recorder.records),
            } if recorder is not None else {}),
        },
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
    if recorder is not None:
        args.gate_credit_report.write_text(
            json.dumps(recorder.report({
                "campaign_id": args.campaign_id,
                "parent_checkpoint_sha256": args.parent_sha256,
                "candidate_checkpoint_sha256": sha256_file(args.output),
                "campaign_contract_sha256": args.campaign_contract_sha256,
                "training_mode": args.training_mode,
                "development_stage": "bound_by_mission_hub_campaign_contract",
                "branch_id": None if args.branch_id == "unbranched" else args.branch_id,
                "ordered_source_sha256": args.ordered_source_sha256,
                "architecture": CORTEX_ARCHITECTURE,
                "optimizer_policy": optimizer.policy(),
            }, overhead={
                "duration_seconds_inclusive": round(time.time() - started, 3),
                "peak_vram_bytes_inclusive": {
                    str(index): torch.cuda.max_memory_allocated(index)
                    for index in range(torch.cuda.device_count())
                },
            }), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"checkpoint": str(args.output), "metadata": metadata}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
