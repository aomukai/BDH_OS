#!/usr/bin/env python3
"""Train only the bounded SigLIP2-to-Cortex resampler from verified features."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import torch

from cortex.siglip2 import BoundedVisualResampler, Siglip2ProjectorConfig, VISUAL_PROJECTOR_SCHEMA
from cortex.student import build_student
from training.diagnostics import GateCreditRecorder


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-projector", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--output-observer", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    if request.get("schema_version") != "ninereeds_visual_projector_train_request_v1":
        raise ValueError("unsupported visual training request")
    required_training_policy = {
        "order_policy": "declared_only", "shuffle_allowed": False,
        "dependency_order_required": True,
    }
    if any(request.get("training_policy", {}).get(key) != value for key, value in required_training_policy.items()):
        raise ValueError("visual training requires immutable declared dependency order")
    identity_digest = request.get("identity_policy_sha256")
    if not isinstance(identity_digest, str) or len(identity_digest) != 64 or any(
        character not in "0123456789abcdef" for character in identity_digest
    ):
        raise ValueError("visual training requires an immutable identity policy hash")
    if request.get("identity_scope") not in {"excluded", "identity_and_integrity"}:
        raise ValueError("visual training requires an explicit identity scope")
    campaign_digest = request.get("campaign_contract_sha256")
    if not isinstance(campaign_digest, str) or len(campaign_digest) != 64 or any(
        character not in "0123456789abcdef" for character in campaign_digest
    ):
        raise ValueError("visual training requires an immutable campaign-purpose contract hash")
    if request.get("training_mode") not in {"bootstrap", "advancement", "experimental", "evolutionary", "merge"}:
        raise ValueError("visual training requires an explicit training mode")
    spec = request["specification"]
    fixture = request.get("observer_fixture")
    if not isinstance(fixture, dict) or fixture.get("id") != "gate-credit-v1" or fixture.get("version") != 1 or fixture.get("required") is not True:
        raise ValueError("visual training requires the versioned observer fixture")
    if spec["training_scope"] != "projector_only":
        raise ValueError("only projector_only training is commissioned")
    base = Path(request["base_checkpoint"]["uri"])
    features_path = Path(request["visual_features"]["uri"])
    experience_path = Path(request["visual_experience"]["uri"])
    base_before = sha256(base)
    experience = json.loads(experience_path.read_text(encoding="utf-8"))
    observed_hashes = {event.get("asset_sha256") for event in experience.get("events", []) if event.get("type") == "observe_image"}
    pair_hashes = {pair["asset_sha256"] for pair in spec["pairs"]}
    if not pair_hashes.issubset(observed_hashes):
        raise ValueError("training pair references an image absent from the visual experience")
    archive = np.load(features_path, allow_pickle=False)
    hashes = [str(value) for value in archive["asset_sha256"].tolist()]
    if len(hashes) != len(set(hashes)) or set(hashes) != set(request["visual_features"]["manifest"]["asset_sha256"]):
        raise ValueError("visual feature index does not match its manifest")
    feature_by_hash = {}
    for index, digest in enumerate(hashes):
        patch = torch.from_numpy(archive[f"patch_{index:04d}"])
        mask = torch.from_numpy(archive[f"mask_{index:04d}"])
        shape = torch.from_numpy(archive[f"shape_{index:04d}"])
        if patch.ndim != 2 or patch.shape[-1] != 768 or mask.shape != patch.shape[:1] or shape.shape != (2,):
            raise ValueError("visual feature tensors have an incompatible shape")
        feature_by_hash[digest] = (patch.unsqueeze(0), mask.unsqueeze(0), shape.unsqueeze(0))
    if not pair_hashes.issubset(feature_by_hash):
        raise ValueError("training pair has no pinned receptor features")
    train = [pair for pair in spec["pairs"] if pair["split"] == "train"]
    validation = [pair for pair in spec["pairs"] if pair["split"] == "validation"]
    exposures = len(train) * spec["epochs"]
    if exposures > request["limits"]["max_exposures"]:
        raise ValueError("visual training exceeds max_exposures")
    torch.manual_seed(spec["seed"])
    student, parent_kind, _ = build_student(base, frozen_dtype=torch.bfloat16, local_files_only=True)
    student.place(ingress_device=torch.device("cuda:0"), core_device=torch.device("cuda:1"), trainable_dtype=torch.bfloat16)
    student.requires_grad_(False).eval()
    config = Siglip2ProjectorConfig()
    resampler = BoundedVisualResampler(config).to(device="cuda:0", dtype=torch.bfloat16)

    def intention(pair: dict) -> torch.Tensor:
        patch, mask, shape = feature_by_hash[pair["asset_sha256"]]
        observed, observed_mask = resampler(patch.to("cuda:0", dtype=torch.bfloat16), mask.to("cuda:0"), shape.to("cuda:0"))
        hidden = student.core.encode_embeds(observed)
        return student.intention(hidden, observed_mask.to(hidden.device))

    def target(pair: dict) -> torch.Tensor:
        with torch.no_grad():
            return student.intentions([pair["text"]]).detach()

    @torch.no_grad()
    def measure(rows: list[dict]) -> float:
        resampler.eval()
        losses = []
        for pair in rows:
            predicted = intention(pair)
            losses.append(torch.nn.functional.mse_loss(predicted.float(), target(pair).to(predicted.device).float()).item())
        return float(sum(losses) / len(losses))

    baseline = measure(validation)
    optimizer = torch.optim.AdamW(resampler.parameters(), lr=spec["learning_rate"], weight_decay=spec["weight_decay"])
    recorder = GateCreditRecorder(
        log_every_n_steps=fixture["log_every_n_steps"],
        max_sampled_steps=fixture["max_sampled_steps"],
    )
    curve, started, step = [], time.monotonic(), 0
    for epoch in range(spec["epochs"]):
        resampler.train()
        for offset in range(0, len(train), spec["batch_size"]):
            batch = train[offset:offset + spec["batch_size"]]
            step += 1
            recorder.begin_step(
                step, epoch=epoch + 1,
                source_metadata=[{"asset_sha256": pair["asset_sha256"], "text": pair["text"]} for pair in batch],
            )
            predicted = torch.cat([intention(pair) for pair in batch], dim=0)
            expected = torch.cat([target(pair) for pair in batch], dim=0).to(predicted.device)
            loss = torch.nn.functional.mse_loss(predicted.float(), expected.float())
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(resampler.parameters(), 1.0)
            optimizer.step()
            recorder.finish_step()
        curve.append({"epoch": epoch + 1, "validation_loss": measure(validation)})
    final = curve[-1]["validation_loss"]
    if sha256(base) != base_before:
        raise RuntimeError("base language checkpoint changed during visual training")
    metadata = {
        "training_scope": "projector_only", "language_core_frozen": True,
        "base_checkpoint_sha256": base_before, "parent_kind": parent_kind,
        "visual_features_sha256": request["visual_features"]["sha256"],
        "visual_experience_sha256": request["visual_experience"]["sha256"],
        "epochs": spec["epochs"], "exposures": exposures, "batch_size": spec["batch_size"],
        "learning_rate": spec["learning_rate"], "weight_decay": spec["weight_decay"], "seed": spec["seed"],
        "example_order": "declared", "order_policy": "declared_only", "shuffle_allowed": False,
        "identity_policy_sha256": identity_digest, "identity_scope": request["identity_scope"],
        "campaign_contract_sha256": campaign_digest, "training_mode": request["training_mode"],
        "branch_id": request.get("branch_id"),
        "baseline_validation_loss": baseline, "final_validation_loss": final,
        "duration_seconds": round(time.monotonic() - started, 3),
        "gate_credit_diagnostics": {
            "enabled": True, "fixture_id": fixture["id"], "fixture_version": fixture["version"],
            "log_every_n_steps": fixture["log_every_n_steps"],
            "max_sampled_steps": fixture["max_sampled_steps"],
            "sampled_step_count": len(recorder.records),
        },
    }
    args.output_projector.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "schema_version": VISUAL_PROJECTOR_SCHEMA, "config": dataclasses.asdict(config),
        "base_checkpoint": str(base), "base_checkpoint_sha256": base_before,
        "resampler_state": resampler.state_dict(), "metadata": metadata,
    }, args.output_projector)
    args.output_report.write_text(json.dumps({
        "schema_version": "ninereeds_visual_projector_training_report_v1",
        "metadata": metadata, "learning_curve": curve,
    }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    args.output_observer.write_text(json.dumps(recorder.report({
        "training_scope": "projector_only",
        "base_checkpoint_sha256": base_before,
        "visual_features_sha256": request["visual_features"]["sha256"],
        "visual_experience_sha256": request["visual_experience"]["sha256"],
        "campaign_contract_sha256": campaign_digest,
        "training_mode": request["training_mode"],
        "branch_id": request.get("branch_id"),
        "architecture": "siglip2_resampler_to_frozen_cortex",
        "optimizer_policy": {"name": "torch.optim.AdamW", "learning_rate": spec["learning_rate"], "weight_decay": spec["weight_decay"]},
    }, overhead={
        "duration_seconds_inclusive": round(time.monotonic() - started, 3),
        "peak_vram_bytes_inclusive": {str(index): torch.cuda.max_memory_allocated(index) for index in range(torch.cuda.device_count())},
        "scope_note": "The language core is frozen; gate layers receive no gradient. This fixture records the absence explicitly and binds ordered source metadata.",
    }), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"projector": str(args.output_projector), "report": str(args.output_report), **metadata}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
