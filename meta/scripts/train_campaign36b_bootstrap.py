#!/usr/bin/env python3
"""Train Campaign 36B on the frozen 3,022-concept visual bootstrap."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import os
import shutil
import statistics
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from amorphous.growth import GrowthObservation
from amorphous.selection import (
    CohortAdmissionEvidence,
    ConceptBlockEvidence,
    selective_admission_decision,
    selective_birth_decision,
    selective_birth_integration_ready,
)
from amorphous.student import (
    AMORPHOUS_CORTEX_ARCHITECTURE,
    build_amorphous_student,
    save_amorphous_cortex_checkpoint,
)
from cortex.siglip2 import (
    BoundedVisualResampler,
    Siglip2ProjectorConfig,
    VISUAL_PROJECTOR_SCHEMA,
)
from training.optim import FactoredAdamW


BOOTSTRAP_MANIFEST_IDENTITY = (
    "e1d760e264717d05676076429a2e13e46cd05da6d8376169feaad579121ac2fb"
)
JOURNAL_SCHEMA = "ninereeds_campaign36b_event_journal_v1"
SESSION_REPORT_SCHEMA = "ninereeds_campaign36b_session_report_v1"
MIN_FREE_BYTES = 20 * 1024**3
MAX_CHECKPOINT_BYTES = 16 * 1024**3
MILESTONE_SESSIONS = {0, 9, 19, 29, 30}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def append_jsonl(path: Path, value: dict[str, Any], *, durable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        if durable:
            os.fsync(handle.fileno())


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


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


def resolve_source(path_text: str, manifest_root: Path) -> Path:
    declared = Path(path_text)
    if declared.is_file():
        return declared
    candidate = manifest_root / declared.name
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"bootstrap source is unavailable: {path_text}")


def visual_objective(
    student,
    resampler: BoundedVisualResampler,
    feature: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
    completion: str,
) -> tuple[torch.Tensor, dict[str, Any]]:
    patch, mask, shape = feature
    visual_parameter = next(resampler.parameters())
    observed, observed_mask = resampler(
        patch.unsqueeze(0).to(
            device=visual_parameter.device, dtype=visual_parameter.dtype
        ),
        mask.unsqueeze(0).to(visual_parameter.device),
        shape.unsqueeze(0).to(visual_parameter.device),
    )
    substrate_parameter = next(student.substrate.parameters())
    observed = observed.to(
        device=substrate_parameter.device, dtype=substrate_parameter.dtype
    )
    observed_mask = observed_mask.to(substrate_parameter.device)
    hidden, trace = student.substrate(
        observed, observed_mask, collect_trace=True
    )
    intentions = student.intention(hidden, observed_mask)

    encoded = student.expression.tokenizer(
        [completion],
        add_special_tokens=False,
        padding=True,
        truncation=True,
        max_length=128,
        return_tensors="pt",
    )
    response_ids = encoded["input_ids"]
    response_mask = encoded.get("attention_mask", torch.ones_like(response_ids))
    prefix = student.expression.prefix_embeddings(intentions)
    model_parameter = next(student.expression.model.parameters())
    model_device = model_parameter.device
    prefix = prefix.to(device=model_device, dtype=model_parameter.dtype)
    response_ids = response_ids.to(model_device)
    response_mask = response_mask.to(model_device)
    token_embeddings = student.expression.model.get_input_embeddings()(response_ids)
    inputs_embeds = torch.cat([prefix, token_embeddings], dim=1)
    prefix_mask = torch.ones(
        prefix.shape[:2], dtype=response_mask.dtype, device=model_device
    )
    attention_mask = torch.cat([prefix_mask, response_mask], dim=1)
    outputs = student.expression.model(
        inputs_embeds=inputs_embeds,
        attention_mask=attention_mask,
        use_cache=False,
        return_dict=True,
    )
    prefix_length = prefix.size(1)
    prediction_logits = outputs.logits[
        :, prefix_length - 1 : prefix_length - 1 + response_ids.size(1), :
    ]
    flat_logits = prediction_logits.reshape(-1, prediction_logits.size(-1))
    flat_targets = response_ids.reshape(-1)
    flat_mask = response_mask.reshape(-1).bool()
    selected_logits = flat_logits[flat_mask]
    selected_targets = flat_targets[flat_mask]
    if selected_targets.numel() == 0:
        raise ValueError("visual completion tokenized to no supervised tokens")
    loss = F.cross_entropy(selected_logits.float(), selected_targets)
    with torch.no_grad():
        probabilities = selected_logits.float().softmax(dim=-1)
        target_probability = probabilities.gather(
            1, selected_targets.unsqueeze(1)
        ).mean()
        exact = bool(torch.equal(selected_logits.argmax(dim=-1), selected_targets))
        final_trace = trace["steps"][-1]
        active_cells = int(final_trace["active_cells_by_example"][0])
        anatomy = trace["anatomy"]
        admitted_cells = max(int(anatomy["admitted_cells"]), 1)
        active_fraction = min(active_cells / admitted_cells, 1.0)
    return loss, {
        "target_token_exact": exact,
        "target_probability": float(target_probability.cpu()),
        "internal_residual": float((1.0 - target_probability).cpu()),
        "active_cells": active_cells,
        "active_admitted_fraction": active_fraction,
        "mean_delta_abs": float(final_trace["mean_delta_abs"]),
        "executed_cells": len(final_trace["cell_ids"]),
    }


def deterministic_event_rank(label: str, event: dict[str, Any]) -> str:
    identity = (
        f"{label}|{event['ordinal']}|{event['asset_sha256']}|"
        f"{event.get('concept', '')}"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


@torch.no_grad()
def replay_losses(student, resampler, events, features) -> list[float]:
    return [
        float(
            visual_objective(
                student,
                resampler,
                features[event["asset_sha256"]],
                event["completion"],
            )[0].cpu()
        )
        for event in events
    ]


def provisional_credit(cohort) -> float:
    """First-order NLL increase predicted when this cohort is zero-ablated."""
    value = 0.0
    observed = False
    for parameter in cohort.parameters():
        if parameter.grad is None:
            continue
        observed = True
        value -= float(
            torch.sum(parameter.grad.detach().float() * parameter.detach().float())
            .cpu()
        )
    return value if observed else 0.0


def runtime_state() -> dict[str, Any]:
    value: dict[str, Any] = {"cpu_rng_state": torch.random.get_rng_state()}
    if torch.cuda.is_available():
        value["cuda_rng_states"] = torch.cuda.get_rng_state_all()
    return value


def restore_runtime_state(value: dict[str, Any] | None, seed: int) -> None:
    if value is None:
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        return
    torch.random.set_rng_state(value["cpu_rng_state"])
    if torch.cuda.is_available() and "cuda_rng_states" in value:
        torch.cuda.set_rng_state_all(value["cuda_rng_states"])


def storage_projection(student, resampler, optimizer) -> dict[str, int]:
    parameter_bytes = sum(
        parameter.numel() * parameter.element_size()
        for parameter in [*student.trainable_parameters(), *resampler.parameters()]
    )
    optimizer_bytes = optimizer.state_bytes()
    projected = parameter_bytes + optimizer_bytes + 128 * 1024**2
    return {
        "trainable_parameter_bytes": parameter_bytes,
        "optimizer_state_bytes": optimizer_bytes,
        "projected_checkpoint_bytes": projected,
    }


def ensure_storage(output_dir: Path, projected: int) -> int:
    free = shutil.disk_usage(output_dir).free
    if projected > MAX_CHECKPOINT_BYTES:
        raise RuntimeError("projected checkpoint exceeds the 16 GiB campaign ceiling")
    if free < MIN_FREE_BYTES + 2 * projected:
        raise RuntimeError("free-space guard rejected the next checkpoint")
    return free


def atomic_checkpoint(path: Path, save) -> tuple[str, int]:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        save(temporary)
        byte_size = temporary.stat().st_size
        if byte_size > MAX_CHECKPOINT_BYTES:
            raise RuntimeError("checkpoint bytes exceed the 16 GiB campaign ceiling")
        digest = sha256(temporary)
        os.replace(temporary, path)
        return digest, byte_size
    finally:
        if temporary.exists():
            temporary.unlink()


def prune_checkpoints(checkpoint_dir: Path, current_index: int) -> list[str]:
    removed: list[str] = []
    for path in sorted(checkpoint_dir.glob("session-*.pt")):
        try:
            index = int(path.stem.split("-")[-1])
        except ValueError:
            continue
        retain = index in MILESTONE_SESSIONS or index >= current_index - 1
        if not retain:
            path.unlink()
            removed.append(path.name)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start-session", type=int)
    parser.add_argument("--max-sessions", type=int)
    parser.add_argument("--max-events-per-session", type=int)
    parser.add_argument(
        "--policy", choices=("unfiltered", "selective"), default="unfiltered"
    )
    parser.add_argument("--seed", type=int, default=3_603_022)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--rms-clip", type=float, default=0.125)
    parser.add_argument("--capacity-activation-fraction", type=float, default=0.45)
    parser.add_argument("--max-bootstrap-cells", type=int, default=8_192)
    parser.add_argument("--ingress-device", default="cuda:0")
    parser.add_argument("--substrate-device", default="cuda:1")
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    if not 0.0 <= args.capacity_activation_fraction <= 1.0:
        raise ValueError("capacity activation fraction must be in [0, 1]")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.output_dir / "checkpoints"
    report_dir = args.output_dir / "reports"
    checkpoint_dir.mkdir(exist_ok=True)
    report_dir.mkdir(exist_ok=True)
    journal_path = args.output_dir / "events.jsonl"
    progress_path = args.output_dir / "progress.json"

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != "ninereeds_foundation_visual_material_v1"
        or manifest.get("input_manifest_sha256") != BOOTSTRAP_MANIFEST_IDENTITY
        or manifest.get("event_count") != 30_220
        or manifest.get("session_count") != 31
        or manifest.get("order_policy") != "declared_only"
        or manifest.get("shuffle_allowed") is not False
    ):
        raise ValueError("bootstrap manifest is not the frozen 36B source")
    parent_document = torch.load(args.parent, map_location="cpu", weights_only=True)
    parent_metadata = parent_document.get("metadata", {})
    completed_before = int(parent_metadata.get("bootstrap_sessions_completed", 0))
    consumed_before = int(parent_metadata.get("training_events_consumed", 0))
    start_session = completed_before if args.start_session is None else args.start_session
    if start_session != completed_before:
        raise ValueError("start session does not continue the parent checkpoint")

    student, growth_controller, optimizer_state = build_amorphous_student(
        args.parent,
        frozen_dtype=torch.bfloat16,
        local_files_only=args.local_files_only,
    )
    visual = parent_document.get("visual_state")
    if not visual or visual.get("schema_version") != VISUAL_PROJECTOR_SCHEMA:
        raise ValueError("amorphous parent lacks the frozen visual resampler")
    visual_config = Siglip2ProjectorConfig(**visual["config"])
    resampler = BoundedVisualResampler(visual_config)
    resampler.load_state_dict(visual["resampler_state"], strict=True)
    partition = student.place(
        ingress_device=torch.device(args.ingress_device),
        substrate_device=torch.device(args.substrate_device),
        trainable_dtype=torch.bfloat16,
    )
    resampler.to(device=torch.device(args.ingress_device), dtype=torch.bfloat16)
    cell_groups = student.optimizer_parameter_groups()
    # Keep the resampler in the same slot across resumes. New cohorts are
    # appended after it by consider_growth(), so reconstruct that exact order.
    optimizer_groups = [
        cell_groups[0],
        cell_groups[1],
        {"params": list(resampler.parameters()), "component": "visual_resampler"},
        *cell_groups[2:],
    ]
    optimizer = FactoredAdamW(
        optimizer_groups,
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
        momentum=True,
        rms_clip=args.rms_clip,
        stochastic_rounding=True,
    )
    if optimizer_state is not None:
        optimizer.load_state_dict(
            optimizer_state, preserve_current_hyperparameters=True
        )
    parent_runtime = parent_document.get("runtime_state")
    restore_runtime_state(parent_runtime, args.seed)
    selective_state: dict[str, Any] = (
        dict(parent_runtime.get("selective_state", {}))
        if parent_runtime is not None
        else {}
    )
    selective_state.setdefault("cohorts", {})
    selective_state.setdefault("concept_blocks_observed", 0)
    selective_state.setdefault("last_birth_cohort_index", None)
    student.train()
    resampler.train()
    trainable = [*student.trainable_parameters(), *resampler.parameters()]

    anchor_events: list[dict[str, Any]] = []
    anchor_features: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = {}
    if args.policy == "selective":
        anchor_session = manifest["sessions"][0]
        anchor_event_path = resolve_source(
            anchor_session["events_path"], args.manifest.parent
        )
        all_anchor_events = json.loads(anchor_event_path.read_text(encoding="utf-8"))
        by_ordinal: dict[int, list[dict[str, Any]]] = {}
        for item in all_anchor_events:
            by_ordinal.setdefault(int(item["ordinal"]), []).append(item)
        anchor_events = [
            min(
                by_ordinal[ordinal],
                key=lambda item: deterministic_event_rank("selective-anchor-v1", item),
            )
            for ordinal in sorted(by_ordinal)[:8]
        ]
        anchor_feature_path = resolve_source(
            anchor_session["feature_path"], args.manifest.parent
        )
        archive = load_features(anchor_feature_path)
        anchor_features = {
            item["asset_sha256"]: archive[item["asset_sha256"]]
            for item in anchor_events
        }

    sessions = manifest["sessions"][start_session:]
    if args.max_sessions is not None:
        sessions = sessions[: args.max_sessions]
    run_id = f"campaign36b-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    parent_path = args.parent
    parent_sha = sha256(parent_path)
    cumulative_events = consumed_before
    append_jsonl(journal_path, {
        "schema_version": JOURNAL_SCHEMA,
        "kind": "run_started",
        "run_id": run_id,
        "parent": str(parent_path),
        "parent_sha256": parent_sha,
        "start_session": start_session,
        "bootstrap_manifest_identity": BOOTSTRAP_MANIFEST_IDENTITY,
        "growth_evidence_policy": {
            "policy": args.policy,
            "internal_residual": "one_minus_mean_teacher_forced_target_probability",
            "external_failure": "teacher_forced_target_token_top1_not_exact",
            "capacity_saturation": (
                "every_allocated_cell_executed_and_active_admitted_fraction_at_least_"
                f"{args.capacity_activation_fraction}"
            ),
        },
    }, durable=True)

    for relative_index, session in enumerate(sessions):
        session_index = start_session + relative_index
        session_id = session["session_id"]
        events_path = resolve_source(session["events_path"], args.manifest.parent)
        feature_path = resolve_source(session["feature_path"], args.manifest.parent)
        if sha256(events_path) != session["events_sha256"]:
            raise ValueError(f"event bytes changed for {session_id}")
        if feature_path.stat().st_size != session["feature_bytes"]:
            raise ValueError(f"feature size changed for {session_id}")
        if sha256(feature_path) != session["feature_sha256"]:
            raise ValueError(f"feature bytes changed for {session_id}")
        events = json.loads(events_path.read_text(encoding="utf-8"))
        if args.max_events_per_session is not None:
            events = events[: args.max_events_per_session]
        features = load_features(feature_path)
        anatomy_before = student.substrate.anatomy()
        session_started = time.monotonic()
        losses: list[float] = []
        residuals: list[float] = []
        exact_count = 0
        births: list[dict[str, Any]] = []
        concept_block: list[dict[str, Any]] = []
        concept_ordinal: int | None = None
        for event_offset, event in enumerate(events):
            event_number = cumulative_events + 1
            optimizer.zero_grad(set_to_none=True)
            feature = features.get(event["asset_sha256"])
            if feature is None:
                raise ValueError(
                    f"{session_id} lacks feature {event['asset_sha256']}"
                )
            loss, evidence = visual_objective(
                student, resampler, feature, event["completion"]
            )
            if not bool(torch.isfinite(loss)):
                raise RuntimeError("Campaign 36B loss became non-finite")
            loss.backward()
            if args.policy == "selective":
                for index, cohort in enumerate(student.substrate.cohorts):
                    if cohort.status != "provisional":
                        continue
                    state = selective_state["cohorts"].setdefault(str(index), {
                        "birth_event": event_number,
                        "credits": [],
                        "failed_audits": 0,
                    })
                    state["credits"].append(provisional_credit(cohort))
                    state["credits"] = state["credits"][-256:]
            clip_by_device(trainable, 1.0)
            optimizer.step()
            loss_value = float(loss.detach().cpu())
            losses.append(loss_value)
            residuals.append(evidence["internal_residual"])
            exact_count += int(evidence["target_token_exact"])
            anatomy = student.substrate.anatomy()
            capacity_saturated = (
                evidence["executed_cells"] == anatomy["allocated_cells"]
                and evidence["active_admitted_fraction"]
                >= args.capacity_activation_fraction
            )
            cohort_index = None
            selective_birth_gate = None
            if args.policy == "unfiltered" and anatomy["allocated_cells"] < args.max_bootstrap_cells:
                cohort_index = student.substrate.consider_growth(
                    growth_controller,
                    GrowthObservation(
                        internal_residual=evidence["internal_residual"],
                        externally_verified_failure=not evidence["target_token_exact"],
                        capacity_saturated=capacity_saturated,
                        event_id=f"{session_id}:{event_offset:04d}",
                    ),
                    optimizer=optimizer,
                )
                if cohort_index is not None:
                    cohort = student.substrate.cohorts[cohort_index]
                    trainable.extend(cohort.parameters())
                    births.append({
                        "event_number": event_number,
                        "cohort_index": cohort_index,
                        "cell_ids": list(cohort.cell_ids),
                    })
            elif args.policy == "selective":
                ordinal = int(event["ordinal"])
                if concept_ordinal is None:
                    concept_ordinal = ordinal
                if ordinal != concept_ordinal:
                    if concept_block:
                        raise RuntimeError("selective concept block did not contain ten exposures")
                    concept_ordinal = ordinal
                concept_block.append({**evidence, "capacity_saturated": capacity_saturated})
                if len(concept_block) == 10:
                    block_qualifies = selective_birth_decision(ConceptBlockEvidence(
                        residuals=tuple(item["internal_residual"] for item in concept_block),
                        exact_predictions=tuple(item["target_token_exact"] for item in concept_block),
                        all_admitted_cells_executed=tuple(
                            item["executed_cells"] >= anatomy["admitted_cells"]
                            for item in concept_block
                        ),
                        active_admitted_fractions=tuple(
                            item["active_admitted_fraction"] for item in concept_block
                        ),
                    ))
                    newest_index = selective_state["last_birth_cohort_index"]
                    newest_credit_count = (
                        None
                        if newest_index is None
                        else len(selective_state["cohorts"][str(newest_index)]["credits"])
                    )
                    integration_ready = selective_birth_integration_ready(
                        newest_credit_count
                    )
                    birth = block_qualifies and integration_ready
                    selective_birth_gate = {
                        "block_qualifies": block_qualifies,
                        "newest_cohort_index": newest_index,
                        "newest_cohort_credit_observations": newest_credit_count,
                        "integration_ready": integration_ready,
                        "birth": birth,
                    }
                    selective_state["concept_blocks_observed"] += 1
                    if birth and anatomy["allocated_cells"] < args.max_bootstrap_cells:
                        cohort_index = student.substrate.add_cohort(status="provisional")
                        cohort = student.substrate.cohorts[cohort_index]
                        optimizer.add_param_group({"params": list(cohort.parameters())})
                        trainable.extend(cohort.parameters())
                        growth_controller.birth_count += 1
                        growth_controller.last_event_id = f"{session_id}:{event_offset:04d}"
                        selective_state["cohorts"][str(cohort_index)] = {
                            "birth_event": event_number,
                            "credits": [],
                            "failed_audits": 0,
                        }
                        selective_state["last_birth_cohort_index"] = cohort_index
                        births.append({
                            "event_number": event_number,
                            "cohort_index": cohort_index,
                            "cell_ids": list(cohort.cell_ids),
                        })
                    concept_block = []
                    concept_ordinal = None
            record = {
                "schema_version": JOURNAL_SCHEMA,
                "kind": "training_event",
                "run_id": run_id,
                "session_id": session_id,
                "session_index": session_index,
                "event_offset": event_offset,
                "event_number": event_number,
                "ordinal": event["ordinal"],
                "concept": event["concept"],
                "asset_sha256": event["asset_sha256"],
                "loss_telemetry": loss_value,
                **evidence,
                "capacity_saturated": capacity_saturated,
                "birth_cohort_index": cohort_index,
                "selective_birth_gate": selective_birth_gate,
                "policy": args.policy,
                "anatomy": student.substrate.anatomy(),
            }
            append_jsonl(journal_path, record)
            cumulative_events += 1
            if event_number % 10 == 0:
                atomic_json(progress_path, {
                    "schema_version": "ninereeds_campaign36b_progress_v1",
                    "status": "training",
                    "run_id": run_id,
                    "session_id": session_id,
                    "session_index": session_index,
                    "event_number": event_number,
                    "events_in_bootstrap": manifest["event_count"],
                    "anatomy": student.substrate.anatomy(),
                    "last_loss": loss_value,
                    "birth_count": growth_controller.birth_count,
                })

        promoted: list[int] = []
        made_dormant: list[int] = []
        admission_audits: dict[str, Any] = {}
        if args.policy == "unfiltered":
            for cohort_index, cohort in enumerate(student.substrate.cohorts):
                if cohort.status == "provisional":
                    student.substrate.set_cohort_status(cohort_index, "admitted")
                    promoted.append(cohort_index)
        else:
            mature = []
            for cohort_index, cohort in enumerate(student.substrate.cohorts):
                if cohort.status != "provisional":
                    continue
                state = selective_state["cohorts"][str(cohort_index)]
                age = cumulative_events - int(state["birth_event"])
                if age >= 128 and len(state["credits"]) >= 32:
                    mature.append(cohort_index)
                else:
                    admission_audits[str(cohort_index)] = {
                        "decision": "provisional",
                        "reason": "minimum_age_or_credit_not_reached",
                        "age_exposures": age,
                        "credit_observations": len(state["credits"]),
                    }
            if mature:
                replay_events = sorted(
                    events,
                    key=lambda item: deterministic_event_rank(
                        f"selective-replay-v1|{session_id}", item
                    ),
                )[:32]
                student.eval(); resampler.eval()
                enabled_replay = replay_losses(
                    student, resampler, replay_events, features
                )
                enabled_anchors = replay_losses(
                    student, resampler, anchor_events, anchor_features
                )
                pending: dict[int, str] = {}
                for cohort_index in mature:
                    cohort = student.substrate.cohorts[cohort_index]
                    state = selective_state["cohorts"][str(cohort_index)]
                    student.substrate.set_cohort_status(cohort_index, "dormant")
                    try:
                        ablated_replay = replay_losses(
                            student, resampler, replay_events, features
                        )
                        ablated_anchors = replay_losses(
                            student, resampler, anchor_events, anchor_features
                        )
                    finally:
                        student.substrate.set_cohort_status(cohort_index, "provisional")
                    replay_delta = tuple(
                        ablated - enabled
                        for enabled, ablated in zip(
                            enabled_replay, ablated_replay, strict=True
                        )
                    )
                    anchor_harm = tuple(
                        enabled - ablated
                        for enabled, ablated in zip(
                            enabled_anchors, ablated_anchors, strict=True
                        )
                    )
                    decision = selective_admission_decision(CohortAdmissionEvidence(
                        age_exposures=cumulative_events - int(state["birth_event"]),
                        online_credit_deltas=tuple(state["credits"]),
                        replay_delta_nll=replay_delta,
                        anchor_harm_nll=anchor_harm,
                        completed_failed_audits=int(state["failed_audits"]),
                    ))
                    pending[cohort_index] = decision
                    admission_audits[str(cohort_index)] = {
                        "decision": decision,
                        "age_exposures": cumulative_events - int(state["birth_event"]),
                        "credit_observations": len(state["credits"]),
                        "helpful_credit_fraction": sum(
                            value > 0 for value in state["credits"]
                        ) / len(state["credits"]),
                        "median_replay_delta_nll": statistics.median(replay_delta),
                        "mean_anchor_harm_nll": statistics.fmean(anchor_harm),
                        "failed_audits_before": int(state["failed_audits"]),
                    }
                for cohort_index, decision in pending.items():
                    state = selective_state["cohorts"][str(cohort_index)]
                    if decision == "promote":
                        student.substrate.set_cohort_status(cohort_index, "admitted")
                        promoted.append(cohort_index)
                    elif decision == "dormant":
                        student.substrate.set_cohort_status(cohort_index, "dormant")
                        state["failed_audits"] = int(state["failed_audits"]) + 1
                        made_dormant.append(cohort_index)
                    else:
                        state["failed_audits"] = int(state["failed_audits"]) + 1
                student.train(); resampler.train()
        anatomy_after = student.substrate.anatomy()
        projection = storage_projection(student, resampler, optimizer)
        free_before = ensure_storage(
            args.output_dir, projection["projected_checkpoint_bytes"]
        )
        metadata = {
            "schema_version": "ninereeds_campaign36b_bootstrap_checkpoint_v1",
            "architecture": AMORPHOUS_CORTEX_ARCHITECTURE,
            "campaign_track": "36B",
            "bootstrap_manifest_sha256": BOOTSTRAP_MANIFEST_IDENTITY,
            "bootstrap_sessions_completed": session_index + 1,
            "training_events_consumed": cumulative_events,
            "session_id": session_id,
            "session_index": session_index,
            "session_event_count": len(events),
            "anatomy_before": anatomy_before,
            "anatomy": anatomy_after,
            "births": births,
            "promoted_cohort_indices": promoted,
            "dormant_cohort_indices": made_dormant,
            "admission_audits": admission_audits,
            "growth_policy": args.policy,
            "growth_birth_count": growth_controller.birth_count,
            "mean_loss_telemetry": sum(losses) / len(losses),
            "mean_internal_residual": sum(residuals) / len(residuals),
            "target_token_exact_fraction": exact_count / len(events),
            "optimizer_policy": optimizer.policy(),
            "storage_projection": projection,
            "partition": partition,
        }
        output_checkpoint = checkpoint_dir / f"session-{session_index:02d}.pt"
        checkpoint_sha, checkpoint_bytes = atomic_checkpoint(
            output_checkpoint,
            lambda target: save_amorphous_cortex_checkpoint(
                target,
                student,
                growth_controller=growth_controller,
                parent=str(parent_path),
                metadata=metadata,
                optimizer_state=optimizer.state_dict(),
                visual_state={
                    "schema_version": VISUAL_PROJECTOR_SCHEMA,
                    "config": dataclasses.asdict(visual_config),
                    "resampler_state": resampler.state_dict(),
                },
                runtime_state={
                    **runtime_state(),
                    "selective_state": selective_state,
                },
            ),
        )
        duration = time.monotonic() - session_started
        report = {
            "schema_version": SESSION_REPORT_SCHEMA,
            "run_id": run_id,
            "session_id": session_id,
            "session_index": session_index,
            "parent_checkpoint": str(parent_path),
            "parent_checkpoint_sha256": parent_sha,
            "candidate_checkpoint": str(output_checkpoint),
            "candidate_checkpoint_sha256": checkpoint_sha,
            "candidate_checkpoint_bytes": checkpoint_bytes,
            "source": {
                "events_sha256": session["events_sha256"],
                "features_sha256": session["feature_sha256"],
                "event_count": len(events),
            },
            "duration_seconds": round(duration, 3),
            "anatomy_before": anatomy_before,
            "anatomy_after": anatomy_after,
            "births": births,
            "promoted_cohort_indices": promoted,
            "dormant_cohort_indices": made_dormant,
            "admission_audits": admission_audits,
            "growth_policy": args.policy,
            "mean_loss_telemetry": metadata["mean_loss_telemetry"],
            "mean_internal_residual": metadata["mean_internal_residual"],
            "target_token_exact_fraction": metadata["target_token_exact_fraction"],
            "storage": {
                **projection,
                "checkpoint_bytes": checkpoint_bytes,
                "free_bytes_before_checkpoint": free_before,
            },
        }
        atomic_json(report_dir / f"session-{session_index:02d}.json", report)
        append_jsonl(journal_path, {
            "schema_version": JOURNAL_SCHEMA,
            "kind": "session_completed",
            "report": report,
        }, durable=True)
        removed = prune_checkpoints(checkpoint_dir, session_index)
        parent_path = output_checkpoint
        parent_sha = checkpoint_sha
        del features
        atomic_json(progress_path, {
            "schema_version": "ninereeds_campaign36b_progress_v1",
            "status": "training" if relative_index + 1 < len(sessions) else "complete",
            "run_id": run_id,
            "sessions_completed": session_index + 1,
            "event_number": cumulative_events,
            "events_in_bootstrap": manifest["event_count"],
            "latest_checkpoint": str(output_checkpoint),
            "latest_checkpoint_sha256": checkpoint_sha,
            "anatomy": anatomy_after,
            "growth_birth_count": growth_controller.birth_count,
            "pruned_checkpoints": removed,
        })
        print(json.dumps({
            "session": session_id,
            "event_number": cumulative_events,
            "cells": anatomy_after["allocated_cells"],
            "births": len(births),
            "checkpoint": str(output_checkpoint),
            "checkpoint_bytes": checkpoint_bytes,
            "duration_seconds": round(duration, 3),
        }, sort_keys=True), flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
