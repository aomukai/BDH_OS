#!/usr/bin/env python3
"""Train Ninereeds on an exact ordered mixture of text and SigLIP2 features."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from cortex.config import CORTEX_ARCHITECTURE
from cortex.siglip2 import BoundedVisualResampler, Siglip2ProjectorConfig, VISUAL_PROJECTOR_SCHEMA
from cortex.student import build_student, load_visual_state, save_cortex_checkpoint
from training.diagnostics import GateCreditRecorder
from training.optim import FactoredAdamW


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def clip_by_device(parameters: list[torch.nn.Parameter], maximum: float) -> None:
    grouped: dict[torch.device, list[torch.nn.Parameter]] = {}
    for parameter in parameters:
        if parameter.grad is not None:
            grouped.setdefault(parameter.device, []).append(parameter)
    for values in grouped.values():
        torch.nn.utils.clip_grad_norm_(values, maximum, foreach=False)


def load_features(path: Path) -> dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
    result: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = {}
    with np.load(path, allow_pickle=False) as values:
        hashes = [str(item) for item in values["asset_sha256"].tolist()]
        for index, digest in enumerate(hashes):
            result[digest] = (
                torch.from_numpy(values[f"patch_{index:04d}"]),
                torch.from_numpy(values[f"mask_{index:04d}"]),
                torch.from_numpy(values[f"shape_{index:04d}"]),
            )
    if not result:
        raise ValueError("visual feature archive is empty")
    return result


def visual_loss(student, resampler, feature, completion: str, observer=None):
    patch, mask, shape = feature
    parameter = next(resampler.parameters())
    observed, observed_mask = resampler(
        patch.unsqueeze(0).to(device=parameter.device, dtype=parameter.dtype),
        mask.unsqueeze(0).to(parameter.device),
        shape.unsqueeze(0).to(parameter.device),
    )
    hidden = student.core.encode_embeds(observed, gate_credit_observer=observer)
    intentions = student.intention(hidden, observed_mask.to(hidden.device))
    encoded = student.expression.tokenizer(
        [completion], add_special_tokens=False, padding=True, truncation=True,
        max_length=128, return_tensors="pt",
    )
    return student.expression.response_loss(
        intentions, encoded["input_ids"], encoded.get("attention_mask"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--output-observer", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if request.get("schema_version") != "ninereeds_multimodal_train_request_v1":
        raise ValueError("unsupported multimodal training request")
    if request["order_policy"] != "declared_only" or request["shuffle_allowed"] is not False:
        raise ValueError("multimodal training order is immutable")
    events = request.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("multimodal training requires ordered events")
    if request["mode"] not in {"visual", "joint"}:
        raise ValueError("multimodal mode must be visual or joint")
    if request["mode"] == "visual" and any(event.get("type") != "visual" for event in events):
        raise ValueError("visual-only training contains a non-visual event")

    parent = Path(request["parent_checkpoint"]).resolve()
    feature_path = Path(request["visual_features"]).resolve()
    if sha256(parent) != request["parent_sha256"] or sha256(feature_path) != request["visual_features_sha256"]:
        raise ValueError("multimodal input bytes changed after authorization")
    features = load_features(feature_path)

    parameters = request["parameters"]
    torch.manual_seed(parameters["seed"])
    torch.cuda.manual_seed_all(parameters["seed"])
    student, parent_kind, optimizer_state = build_student(
        parent, frozen_dtype=torch.bfloat16, local_files_only=parameters["local_files_only"],
    )
    previous_visual = load_visual_state(parent)
    config = Siglip2ProjectorConfig(**previous_visual["config"]) if previous_visual else Siglip2ProjectorConfig()
    resampler = BoundedVisualResampler(config)
    if previous_visual:
        resampler.load_state_dict(previous_visual["resampler_state"], strict=True)
    partition = student.place(
        ingress_device=torch.device(parameters["ingress_device"]),
        core_device=torch.device(parameters["core_device"]),
        trainable_dtype=torch.bfloat16,
    )
    student.set_train_scope("full")
    resampler.to(device=torch.device(parameters["ingress_device"]), dtype=torch.bfloat16)
    trainable = [*student.trainable_parameters(), *resampler.parameters()]
    optimizer = FactoredAdamW(
        trainable, lr=parameters["learning_rate"], weight_decay=parameters["weight_decay"],
        momentum=True, rms_clip=parameters.get("rms_clip"),
        stochastic_rounding=parameters.get("stochastic_rounding", False),
    )
    if optimizer_state is not None and previous_visual is not None:
        optimizer.load_state_dict(optimizer_state, preserve_current_hyperparameters=True)

    fixture = request["observer_fixture"]
    recorder = GateCreditRecorder(
        log_every_n_steps=fixture["log_every_n_steps"],
        max_sampled_steps=fixture["max_sampled_steps"],
    )
    names = {id(parameter): name for name, parameter in student.named_parameters()}
    names.update({id(parameter): f"visual_resampler.{name}" for name, parameter in resampler.named_parameters()})
    optimizer.diagnostic_callback = lambda parameter, gradient, update, lr: recorder.observe_optimizer_update(
        names.get(id(parameter), "unknown"), parameter, gradient, update, lr,
    )

    started = time.monotonic()
    losses: list[float] = []
    student.train(); resampler.train()
    for epoch in range(parameters["epochs"]):
        for event_index, event in enumerate(events, 1):
            sampled = recorder.begin_step(
                len(losses) + 1, epoch=epoch + 1,
                source_metadata=[{
                    "event_index": event_index, "event_type": event["type"],
                    "concept": event["concept"], "ordinal": event["ordinal"],
                }],
            )
            optimizer.zero_grad(set_to_none=True)
            if event["type"] == "text":
                loss = student.response_loss(
                    [event["prompt"]], [event["completion"]],
                    gate_credit_observer=recorder if sampled else None,
                )
            elif event["type"] == "visual":
                digest = event["asset_sha256"]
                if digest not in features:
                    raise ValueError(f"event names unavailable visual features: {digest}")
                loss = visual_loss(
                    student, resampler, features[digest], event["completion"],
                    recorder if sampled else None,
                )
            else:
                raise ValueError(f"unsupported event type: {event.get('type')}")
            if not bool(torch.isfinite(loss)):
                raise RuntimeError("multimodal loss became non-finite")
            loss.backward()
            clip_by_device(trainable, 1.0)
            optimizer.step()
            recorder.finish_step()
            losses.append(float(loss.detach().cpu()))

    if not losses or not all(math.isfinite(value) for value in losses):
        raise RuntimeError("multimodal run produced invalid telemetry")
    metadata = {
        "schema_version": "ninereeds_multimodal_training_run_v1",
        "architecture": CORTEX_ARCHITECTURE,
        "parent_kind": parent_kind,
        "parent_checkpoint_sha256": request["parent_sha256"],
        "visual_features_sha256": request["visual_features_sha256"],
        "visual_experience_sha256": request["visual_experience_sha256"],
        "mode": request["mode"], "event_count": len(events),
        "epochs": parameters["epochs"], "seed": parameters["seed"],
        "example_order": "declared", "order_policy": "declared_only", "shuffle_allowed": False,
        "campaign_id": request["campaign_id"], "branch_id": request["branch_id"],
        "campaign_contract_sha256": request["campaign_contract_sha256"],
        "identity_policy_sha256": request["identity_policy_sha256"],
        "identity_scope": request["identity_scope"],
        "loss_role": "telemetry_only", "step_losses": losses,
        "optimizer": optimizer.policy(), "optimizer_state_bytes": optimizer.state_bytes(),
        "partition": partition, "ownership": student.ownership_report(),
        "duration_seconds": round(time.monotonic() - started, 3),
        "gate_credit_diagnostics": {
            "enabled": True, "fixture_id": fixture["id"], "fixture_version": fixture["version"],
            "sampled_step_count": len(recorder.records),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_cortex_checkpoint(
        args.output, student, parent=str(parent), metadata=metadata,
        optimizer_state=optimizer.state_dict(),
        visual_state={
            "schema_version": VISUAL_PROJECTOR_SCHEMA,
            "config": dataclasses.asdict(config),
            "resampler_state": resampler.state_dict(),
        },
    )
    args.output_report.write_text(
        json.dumps({"schema_version": "ninereeds_multimodal_training_report_v1", "metadata": metadata}, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    args.output_observer.write_text(
        json.dumps(recorder.report({
            "campaign_id": request["campaign_id"], "branch_id": request["branch_id"],
            "parent_checkpoint_sha256": request["parent_sha256"],
            "candidate_checkpoint_sha256": sha256(args.output),
            "campaign_contract_sha256": request["campaign_contract_sha256"],
            "training_mode": "evolutionary", "architecture": CORTEX_ARCHITECTURE,
            "ordered_source_sha256": request["visual_experience_sha256"],
            "optimizer_policy": optimizer.policy(),
        }, overhead={"duration_seconds_inclusive": round(time.monotonic() - started, 3)}), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"checkpoint": str(args.output), "checkpoint_sha256": sha256(args.output), "metadata": metadata}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
