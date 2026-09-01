#!/usr/bin/env python3
"""Train the Campaign 36C organism on the frozen 3,022-concept bootstrap."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import statistics
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch

from campaign36c import (
    Campaign36CStudent,
    DevelopmentController,
    DevelopmentPolicyConfig,
    DevelopmentProbe,
    ExecutedSubgraphTrainer,
    FailureDiagnosis,
    OrganismConfig,
    OrganismSnapshotStore,
    ResidualObservation,
)
from campaign36c.bootstrap import (
    BOOTSTRAP_MANIFEST_IDENTITY,
    clear_gradients,
    clip_by_device,
    load_features,
    load_frozen_manifest,
    resolve_source,
    sha256,
)


JOURNAL_SCHEMA = "ninereeds_campaign36c_multimodal_bootstrap_event_v2"
PROGRESS_SCHEMA = "ninereeds_campaign36c_multimodal_bootstrap_progress_v2"
SESSION_REPORT_SCHEMA = "ninereeds_campaign36c_multimodal_bootstrap_session_v2"
MILESTONE_SESSIONS = {0, 9, 19, 29, 30}


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


def shared_optimizer(
    student: Campaign36CStudent,
    *,
    learning_rate: float,
    weight_decay: float,
) -> torch.optim.AdamW:
    core_side = [
        *student.organism.continuity_parameters(),
        *student.ingress.projector.parameters(),
        *student.resampler.parameters(),
    ]
    speech_side = [
        *student.intention.parameters(),
        *student.expression.projector.parameters(),
    ]
    return torch.optim.AdamW(
        [
            {
                "params": core_side,
                "component": "continuity_text_and_visual_afferents",
            },
            {"params": speech_side, "component": "intention_and_expression_bridge"},
        ],
        lr=learning_rate,
        weight_decay=weight_decay,
    )


def restore_rng(value: dict[str, Any] | None, seed: int) -> None:
    if value is None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        return
    torch.random.set_rng_state(value["cpu_rng_state"])
    if torch.cuda.is_available() and value.get("cuda_rng_states"):
        torch.cuda.set_rng_state_all(value["cuda_rng_states"])


def verify_complete_organ_set(student: Campaign36CStudent) -> dict[str, Any]:
    """Exercise cochlea, visual cortex, latent tissue, and Broca before training."""
    text_tokens = student.ingress.tokenize(["number"])
    with torch.no_grad():
        text_observed, text_mask = student.ingress(
            text_tokens["input_ids"],
            text_tokens["attention_mask"],
            text_tokens.get("token_type_ids"),
        )
        pixels = np.zeros((224, 224, 3), dtype=np.uint8)
        pixels[48:176, 48:176, :] = 192
        image_observed, image_mask = student.vision([pixels])
        text_result = student._objective_from_observation(
            text_observed,
            text_mask,
            "number",
            modality="text",
            claim_address="preflight:text:number",
            evidence_lineage=("preflight:lfm-encoder",),
            novelty=1.0,
            retain_terminal_gradient=False,
        )
        image_result = student._objective_from_observation(
            image_observed,
            image_mask,
            "image",
            modality="image",
            claim_address="preflight:image:synthetic",
            evidence_lineage=("preflight:siglip2",),
            novelty=1.0,
            retain_terminal_gradient=False,
        )
    width = student.organism.organism_config.width
    if (
        text_observed.ndim != 3
        or image_observed.ndim != 3
        or text_observed.size(-1) != width
        or image_observed.size(-1) != width
        or not bool(torch.isfinite(text_observed).all())
        or not bool(torch.isfinite(image_observed).all())
        or not bool(torch.isfinite(text_result.loss))
        or not bool(torch.isfinite(image_result.loss))
    ):
        raise RuntimeError("Campaign 36C organ preflight produced invalid latent state")
    ownership = student.organ_ownership_report()
    if (
        ownership["frozen_text_encoder_parameters"] <= 0
        or ownership["frozen_receptor_parameters"] <= 0
        or ownership["frozen_expression_parameters"] <= 0
        or ownership["trainable_text_afferent_parameters"] <= 0
        or ownership["trainable_resampler_parameters"] <= 0
        or ownership["trainable_broca_bridge_parameters"] <= 0
        or ownership["text_encoder_trainable_parameters"] != 0
        or ownership["visual_receptor_trainable_parameters"] != 0
        or ownership["expression_renderer_trainable_parameters"] != 0
    ):
        raise RuntimeError("Campaign 36C organ preflight found an incomplete organ")
    return {
        "schema_version": "ninereeds_campaign36c_organ_preflight_v1",
        "status": "passed",
        "latent_width": width,
        "text_observation_tokens": int(text_observed.size(1)),
        "visual_observation_tokens": int(image_observed.size(1)),
        "text_target_probability": text_result.target_probability,
        "image_target_probability": image_result.target_probability,
        "text_encoder_revision": student.cortex_config.encoder_revision,
        "expression_revision": student.cortex_config.lfm_revision,
        "visual_receptor_revision": student.vision.config.receptor_revision,
        "ownership": ownership,
    }


def select_sponsor(result) -> tuple[int, float, float, torch.Tensor]:
    retained = set(result.resolution.retained_patch_ids)
    records = [
        item
        for item in result.eligibility
        if item.full_transform and item.patch_id in retained and item.wave_index == 0
    ]
    if not records:
        records = [
            item
            for item in result.eligibility
            if item.full_transform and item.patch_id in retained
        ]
    if not records:
        raise RuntimeError("thought produced no retained transform for development")
    record = max(records, key=lambda item: (item.ownership, item.coverage, -item.uid))
    patch = next(item for item in result.patches if item.patch_id == record.patch_id)
    return record.uid, record.ownership, record.coverage, patch.operation_delta


def latent_target(frontier: torch.Tensor, terminal_gradient: torch.Tensor) -> torch.Tensor:
    gradient = terminal_gradient.detach().float()
    scale = float(gradient.square().mean().sqrt().cpu())
    direction = gradient / max(scale, 1e-8)
    return (frontier.detach().float() - 0.05 * direction).to(frontier.dtype)


def event_identity(event: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    claim = f"lexeme:{int(event['ordinal']):04d}:{event['concept']}"
    lineage = (f"siglip2:{event['asset_sha256']}",)
    return claim, lineage


def text_identity(event: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    claim = f"lexeme:{int(event['ordinal']):04d}:{event['concept']}"
    lineage = (f"lfm-encoder:{int(event['ordinal']):04d}:{event['concept']}",)
    return claim, lineage


def build_observation(
    *,
    event: dict[str, Any],
    objective,
    terminal_gradient: torch.Tensor,
    held_out: bool,
    existing_loss_before: float,
    existing_loss_after: float,
) -> ResidualObservation:
    sponsor_uid, ownership, coverage, delta = select_sponsor(objective.thought.result)
    root = objective.thought.root_state.detach().clone()
    frontier = (root + delta.detach()).clone()
    target = latent_target(frontier, terminal_gradient)
    return ResidualObservation(
        thought_epoch=int(objective.thought.result.eligibility[0].thought_epoch),
        sponsor_uid=sponsor_uid,
        claim_address=event_identity(event)[0],
        evidence_lineage=f"siglip2:{event['asset_sha256']}",
        source_family=f"visual-asset:{event['asset_sha256'][:16]}",
        source_reliability=1.0,
        root_state=root,
        frontier_state=frontier,
        target_state=target,
        ownership=ownership,
        coverage=coverage,
        alternatives_checked=True,
        route_resolved=False,
        existing_trial_completed=True,
        existing_loss_before=existing_loss_before,
        existing_loss_after=existing_loss_after,
        existing_regression=max(0.0, existing_loss_after - existing_loss_before),
        best_alternative_loss=float(
            torch.nn.functional.mse_loss(frontier.float(), target.float()).cpu()
        ),
        held_out=held_out,
        expected_utility=max(objective.internal_residual, 1e-6),
        candidate_neighbors=(),
    )


def apply_objective(
    student: Campaign36CStudent,
    sparse_trainer: ExecutedSubgraphTrainer,
    optimizer: torch.optim.AdamW,
    objective,
    *,
    claim: str,
    lineage: tuple[str, ...],
    update: bool,
) -> tuple[Any, torch.Tensor, Any | None]:
    if not bool(torch.isfinite(objective.loss.detach())):
        raise RuntimeError("Campaign 36C loss became non-finite")
    if not update:
        gradient = torch.autograd.grad(
            objective.loss, objective.thought.result.state, retain_graph=False
        )[0].detach()
        clear_gradients(student.shared_trainable_parameters())
        return objective, gradient, None
    credit = sparse_trainer.apply_external_loss(
        objective.thought.result,
        objective.loss,
        claim_address=claim,
        evidence_lineage=lineage,
    )
    gradient = objective.thought.result.state.grad
    if gradient is None:
        raise RuntimeError("terminal language loss produced no latent gradient")
    gradient = gradient.detach().clone()
    shared = student.shared_trainable_parameters()
    clip_by_device(shared, 1.0)
    optimizer.step()
    clear_gradients(shared)
    return objective, gradient, credit


def run_visual_objective(
    student: Campaign36CStudent,
    sparse_trainer: ExecutedSubgraphTrainer,
    optimizer: torch.optim.AdamW,
    feature,
    event: dict[str, Any],
    *,
    update: bool,
) -> tuple[Any, torch.Tensor, Any | None]:
    optimizer.zero_grad(set_to_none=True)
    claim, lineage = event_identity(event)
    objective = student.visual_objective(
        feature,
        event["completion"],
        claim_address=claim,
        evidence_lineage=lineage,
        novelty=1.0,
        retain_terminal_gradient=update,
    )
    return apply_objective(
        student,
        sparse_trainer,
        optimizer,
        objective,
        claim=claim,
        lineage=lineage,
        update=update,
    )


def run_text_objective(
    student: Campaign36CStudent,
    sparse_trainer: ExecutedSubgraphTrainer,
    optimizer: torch.optim.AdamW,
    event: dict[str, Any],
) -> tuple[Any, torch.Tensor, Any]:
    optimizer.zero_grad(set_to_none=True)
    claim, lineage = text_identity(event)
    objective = student.text_objective(
        event["concept"],
        event["completion"],
        claim_address=claim,
        evidence_lineage=lineage,
        novelty=1.0,
        retain_terminal_gradient=True,
    )
    return apply_objective(
        student,
        sparse_trainer,
        optimizer,
        objective,
        claim=claim,
        lineage=lineage,
        update=True,
    )


def maybe_develop(
    observations: list[ResidualObservation],
    student: Campaign36CStudent,
    sparse_trainer: ExecutedSubgraphTrainer,
    *,
    next_uid: int,
    policy: DevelopmentPolicyConfig,
    established_probes: tuple[DevelopmentProbe, ...],
) -> tuple[int, dict[str, Any]]:
    if not observations:
        return next_uid, {"decision": "no_complete_concept_block"}
    sponsors = {item.sponsor_uid for item in observations}
    if len(sponsors) != 1:
        return next_uid, {
            "decision": "route_unstable",
            "sponsors": sorted(sponsors),
            "reason": "coherent capacity evidence requires one local frontier",
        }
    controller = DevelopmentController(
        student.organism.substrate,
        next_uid=next_uid,
        policy=policy,
        rotary_pairs=student.organism.organism_config.cell_rotary_pairs,
        initialization_seed=36_800,
    )
    decisions = [controller.observe(item) for item in observations]
    terminal = decisions[-1]
    report: dict[str, Any] = {
        "diagnoses": [item.diagnosis.value for item in decisions],
        "actions": [item.action for item in decisions],
        "decision": terminal.action,
        "controller": controller.state_summary(),
    }
    if (
        terminal.diagnosis is FailureDiagnosis.CAPACITY_FAILURE
        and terminal.dossier_id is not None
    ):
        developmental = controller.begin_shadow(terminal.dossier_id)
        controller.train_shadow(developmental.uid)
        evaluation = controller.evaluate_shadow(
            developmental.uid, established_probes=established_probes
        )
        report["shadow_uid"] = developmental.uid
        report["shadow_evaluation"] = dataclasses.asdict(evaluation)
        if evaluation.passed:
            try:
                controller.admit(
                    developmental.uid, established_probes=established_probes
                )
            except RuntimeError as exc:
                report["decision"] = "probation_rolled_back"
                report["probation_error"] = str(exc)
            else:
                sparse_trainer.install_optimizer(
                    developmental.uid, developmental.optimizer
                )
                report["decision"] = "admitted_provisional_tissue"
                report["admitted_uid"] = developmental.uid
    next_uid = controller.uid_allocator._next_uid
    report["next_uid"] = next_uid
    report["controller"] = controller.state_summary()
    return next_uid, report


def prune_shared_snapshots(store: OrganismSnapshotStore, current_index: int) -> list[str]:
    removed: list[str] = []
    for path in sorted(store.shared_root.glob("session-*.pt")):
        try:
            index = int(path.stem.split("-")[-1])
        except ValueError:
            continue
        if index in MILESTONE_SESSIONS or index >= current_index - 1:
            continue
        path.unlink()
        manifest = store.snapshot_root / f"session-{index:02d}.json"
        if manifest.exists():
            manifest.unlink()
        removed.append(path.name)
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--organ-donor", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-sessions", type=int)
    parser.add_argument("--max-events-per-session", type=int)
    parser.add_argument("--seed", type=int, default=3_603_602)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--cell-learning-rate", type=float, default=3e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--core-device", default="cuda:0")
    parser.add_argument("--tissue-device", default="cuda:1")
    parser.add_argument("--dtype", choices=("bfloat16", "float32"), default="bfloat16")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = args.output_dir / "reports"
    reports_dir.mkdir(exist_ok=True)
    journal_path = args.output_dir / "events.jsonl"
    progress_path = args.output_dir / "progress.json"
    manifest = load_frozen_manifest(args.manifest)
    text_events_in_bootstrap = sum(
        int(session["concept_count"]) for session in manifest["sessions"]
    )
    total_events_in_bootstrap = manifest["event_count"] + text_events_in_bootstrap
    store = OrganismSnapshotStore(args.output_dir / "organism")
    core_device = torch.device(args.core_device)
    tissue_device = torch.device(args.tissue_device)
    dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
    latest = store.latest()
    restored_anchor_values: list[dict[str, Any]] = []

    if latest is not None:
        if not args.resume:
            raise RuntimeError("organism state exists; pass --resume instead of overwriting it")
        name = latest["snapshot_name"]
        shared = store.load_shared(name)
        substrate, local_optimizers = store.restore_tissue(
            name, device=tissue_device
        )
        student = Campaign36CStudent.from_snapshot(
            shared,
            substrate,
            frozen_dtype=dtype,
            local_files_only=args.local_files_only,
        )
        partition = student.place(
            core_device=core_device, tissue_device=tissue_device, dtype=dtype
        )
        sparse_trainer = ExecutedSubgraphTrainer(student.organism.substrate)
        sparse_trainer.load_optimizers(local_optimizers)
        optimizer = shared_optimizer(
            student,
            learning_rate=args.learning_rate,
            weight_decay=args.weight_decay,
        )
        optimizer.load_state_dict(shared["shared_optimizer_state"])
        restore_rng(shared.get("runtime_state"), args.seed)
        progress = dict(shared["progress"])
        restored_anchor_values = list(
            shared.get("developmental_state", {}).get("anchor_probes", [])
        )
        next_uid = int(shared["next_uid"])
        start_session = int(progress["sessions_completed"])
        cumulative_events = int(progress["events_consumed"])
        cumulative_visual_events = int(progress["visual_events_consumed"])
        cumulative_text_events = int(progress["text_events_consumed"])
        organ_preflight = dict(progress["organ_preflight"])
        run_id = str(progress["run_id"])
    else:
        if args.resume:
            raise RuntimeError("--resume requested but no organism snapshot exists")
        restore_rng(None, args.seed)
        student = Campaign36CStudent.from_organ_donor(
            args.organ_donor,
            organism_config=OrganismConfig(),
            frozen_dtype=dtype,
            local_files_only=args.local_files_only,
        )
        partition = student.place(
            core_device=core_device, tissue_device=tissue_device, dtype=dtype
        )
        organ_preflight = verify_complete_organ_set(student)
        sparse_trainer = ExecutedSubgraphTrainer(student.organism.substrate)
        sparse_trainer.optimizer_config = dataclasses.replace(
            sparse_trainer.optimizer_config,
            learning_rate=args.cell_learning_rate,
        )
        optimizer = shared_optimizer(
            student,
            learning_rate=args.learning_rate,
            weight_decay=args.weight_decay,
        )
        run_id = f"campaign36c-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
        start_session = 0
        cumulative_events = 0
        cumulative_visual_events = 0
        cumulative_text_events = 0
        next_uid = max(int(uid) for uid in student.organism.substrate.cells) + 1
        progress = {
            "schema_version": PROGRESS_SCHEMA,
            "status": "preflight",
            "run_id": run_id,
            "sessions_completed": 0,
            "events_consumed": 0,
            "events_in_bootstrap": total_events_in_bootstrap,
            "visual_events_consumed": 0,
            "visual_events_in_bootstrap": manifest["event_count"],
            "text_events_consumed": 0,
            "text_events_in_bootstrap": text_events_in_bootstrap,
            "bootstrap_manifest_identity": BOOTSTRAP_MANIFEST_IDENTITY,
            "organ_preflight": organ_preflight,
        }
        preflight = store.save(
            "embryo-preflight",
            student,
            sparse_trainer,
            optimizer,
            progress=progress,
            next_uid=next_uid,
            developmental_state={"anchor_probes": []},
            developmental_summary={"status": "no_training_event_consumed"},
        )
        verified = json.loads(preflight.read_text(encoding="utf-8"))
        if store.latest() is None or verified["progress"]["events_consumed"] != 0:
            raise RuntimeError("preflight organism snapshot failed verification")

    student.train()
    policy = DevelopmentPolicyConfig()
    anchor_probes: deque[DevelopmentProbe] = deque(
        (
            DevelopmentProbe(
                root_state=item["root_state"].to(tissue_device),
                frontier_state=item["frontier_state"].to(tissue_device),
                target_state=item["target_state"].to(tissue_device),
                maximum_absolute_regression=float(
                    item.get("maximum_absolute_regression", 1e-4)
                ),
            )
            for item in restored_anchor_values
        ),
        maxlen=8,
    )
    append_jsonl(
        journal_path,
        {
            "schema_version": JOURNAL_SCHEMA,
            "kind": "run_started" if start_session == 0 else "run_resumed",
            "run_id": run_id,
            "start_session": start_session,
            "events_consumed": cumulative_events,
            "manifest": str(args.manifest),
            "manifest_identity": BOOTSTRAP_MANIFEST_IDENTITY,
            "organ_donor": student.donor_identity,
            "partition": partition,
            "growth_policy": dataclasses.asdict(policy),
            "organ_preflight": organ_preflight,
            "events_in_bootstrap": total_events_in_bootstrap,
            "visual_events_in_bootstrap": manifest["event_count"],
            "text_events_in_bootstrap": text_events_in_bootstrap,
        },
        durable=True,
    )

    sessions = manifest["sessions"][start_session:]
    if args.max_sessions is not None:
        sessions = sessions[: args.max_sessions]
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
        started = time.monotonic()
        losses: list[float] = []
        visual_losses: list[float] = []
        text_losses: list[float] = []
        exact = 0
        visual_exact = 0
        text_exact = 0
        active_counts: list[int] = []
        developments: list[dict[str, Any]] = []

        for block_start in range(0, len(events), 10):
            block = events[block_start : block_start + 10]
            if len({int(item["ordinal"]) for item in block}) != 1:
                raise RuntimeError("frozen bootstrap lost its ten-image concept blocks")
            if len({str(item["concept"]) for item in block}) != 1:
                raise RuntimeError("frozen bootstrap concept block changed lexical identity")
            text_event = block[0]
            text_objective, _text_gradient, text_credit = run_text_objective(
                student,
                sparse_trainer,
                optimizer,
                text_event,
            )
            text_loss = float(text_objective.loss.detach().cpu())
            losses.append(text_loss)
            text_losses.append(text_loss)
            exact += int(text_objective.target_token_exact)
            text_exact += int(text_objective.target_token_exact)
            active_counts.append(
                int(text_objective.thought.result.telemetry["unique_uid_count"])
            )
            cumulative_events += 1
            cumulative_text_events += 1
            append_jsonl(journal_path, {
                "schema_version": JOURNAL_SCHEMA,
                "kind": "text_training_event",
                "run_id": run_id,
                "session_id": session_id,
                "session_index": session_index,
                "event_number": cumulative_events,
                "ordinal": text_event["ordinal"],
                "concept": text_event["concept"],
                "prompt_policy": "bare_lexeme_through_frozen_lfm_encoder",
                "loss": text_loss,
                "target_probability": text_objective.target_probability,
                "target_token_exact": text_objective.target_token_exact,
                "wave": text_objective.thought.result.telemetry,
                "updated_uids": list(text_credit.updated_uids),
                "updated_edges": [list(item) for item in text_credit.updated_edges],
            })
            provisional: list[tuple[dict[str, Any], Any, torch.Tensor, bool]] = []
            for offset, event in enumerate(block):
                feature = features.get(event["asset_sha256"])
                if feature is None:
                    raise ValueError(f"{session_id} lacks feature {event['asset_sha256']}")
                held_out = len(block) == 10 and offset >= 8
                objective, gradient, credit = run_visual_objective(
                    student,
                    sparse_trainer,
                    optimizer,
                    feature,
                    event,
                    update=not held_out,
                )
                provisional.append((event, objective, gradient, held_out))
                if not held_out:
                    losses.append(float(objective.loss.detach().cpu()))
                    visual_losses.append(float(objective.loss.detach().cpu()))
                    exact += int(objective.target_token_exact)
                    visual_exact += int(objective.target_token_exact)
                    active_counts.append(
                        int(objective.thought.result.telemetry["unique_uid_count"])
                    )
                    cumulative_events += 1
                    cumulative_visual_events += 1
                    append_jsonl(journal_path, {
                        "schema_version": JOURNAL_SCHEMA,
                        "kind": "training_event",
                        "run_id": run_id,
                        "session_id": session_id,
                        "session_index": session_index,
                        "event_number": cumulative_events,
                        "ordinal": event["ordinal"],
                        "concept": event["concept"],
                        "asset_sha256": event["asset_sha256"],
                        "loss": float(objective.loss.detach().cpu()),
                        "target_probability": objective.target_probability,
                        "target_token_exact": objective.target_token_exact,
                        "wave": objective.thought.result.telemetry,
                        "updated_uids": list(credit.updated_uids),
                        "updated_edges": [list(item) for item in credit.updated_edges],
                    })

            if len(block) == 10:
                before = statistics.fmean(
                    float(item[1].loss.detach().cpu()) for item in provisional[:2]
                )
                after = statistics.fmean(
                    float(item[1].loss.detach().cpu()) for item in provisional[8:]
                )
                observations = [
                    build_observation(
                        event=event,
                        objective=objective,
                        terminal_gradient=gradient,
                        held_out=held_out,
                        existing_loss_before=before,
                        existing_loss_after=after,
                    )
                    for event, objective, gradient, held_out in provisional
                ]
                next_uid, development = maybe_develop(
                    observations,
                    student,
                    sparse_trainer,
                    next_uid=next_uid,
                    policy=policy,
                    established_probes=tuple(anchor_probes),
                )
                development.update({
                    "ordinal": block[0]["ordinal"],
                    "concept": block[0]["concept"],
                    "loss_before": before,
                    "held_out_loss": after,
                })
                developments.append(development)
                append_jsonl(journal_path, {
                    "schema_version": JOURNAL_SCHEMA,
                    "kind": "development_decision",
                    "run_id": run_id,
                    **development,
                })
                anchor = observations[-1]
                anchor_probes.append(DevelopmentProbe(
                    root_state=anchor.root_state,
                    frontier_state=anchor.frontier_state,
                    target_state=anchor.target_state,
                ))
                for event, _old_objective, _old_gradient, _held_out in provisional[8:]:
                    objective, _gradient, credit = run_visual_objective(
                        student,
                        sparse_trainer,
                        optimizer,
                        features[event["asset_sha256"]],
                        event,
                        update=True,
                    )
                    losses.append(float(objective.loss.detach().cpu()))
                    visual_losses.append(float(objective.loss.detach().cpu()))
                    exact += int(objective.target_token_exact)
                    visual_exact += int(objective.target_token_exact)
                    active_counts.append(
                        int(objective.thought.result.telemetry["unique_uid_count"])
                    )
                    cumulative_events += 1
                    cumulative_visual_events += 1
                    append_jsonl(journal_path, {
                        "schema_version": JOURNAL_SCHEMA,
                        "kind": "training_event",
                        "run_id": run_id,
                        "session_id": session_id,
                        "session_index": session_index,
                        "event_number": cumulative_events,
                        "ordinal": event["ordinal"],
                        "concept": event["concept"],
                        "asset_sha256": event["asset_sha256"],
                        "loss": float(objective.loss.detach().cpu()),
                        "target_probability": objective.target_probability,
                        "target_token_exact": objective.target_token_exact,
                        "wave": objective.thought.result.telemetry,
                        "updated_uids": list(credit.updated_uids),
                        "updated_edges": [list(item) for item in credit.updated_edges],
                        "held_out_before_update": True,
                    })

            atomic_json(progress_path, {
                "schema_version": PROGRESS_SCHEMA,
                "status": "training",
                "run_id": run_id,
                "session_id": session_id,
                "session_index": session_index,
                "events_consumed": cumulative_events,
                "events_in_bootstrap": total_events_in_bootstrap,
                "visual_events_consumed": cumulative_visual_events,
                "visual_events_in_bootstrap": manifest["event_count"],
                "text_events_consumed": cumulative_text_events,
                "text_events_in_bootstrap": text_events_in_bootstrap,
                "active_uid_count": len(student.organism.substrate.cells),
                "next_uid": next_uid,
                "last_loss": losses[-1] if losses else None,
                "organ_preflight": organ_preflight,
            })

        duration = time.monotonic() - started
        progress = {
            "schema_version": PROGRESS_SCHEMA,
            "status": (
                "complete"
                if session_index + 1 == manifest["session_count"]
                else "training"
            ),
            "run_id": run_id,
            "sessions_completed": session_index + 1,
            "events_consumed": cumulative_events,
            "events_in_bootstrap": total_events_in_bootstrap,
            "visual_events_consumed": cumulative_visual_events,
            "visual_events_in_bootstrap": manifest["event_count"],
            "text_events_consumed": cumulative_text_events,
            "text_events_in_bootstrap": text_events_in_bootstrap,
            "active_uid_count": len(student.organism.substrate.cells),
            "next_uid": next_uid,
            "last_loss": losses[-1] if losses else None,
            "organ_preflight": organ_preflight,
        }
        snapshot = store.save(
            f"session-{session_index:02d}",
            student,
            sparse_trainer,
            optimizer,
            progress=progress,
            next_uid=next_uid,
            developmental_state={
                "anchor_probes": [
                    {
                        "root_state": item.root_state,
                        "frontier_state": item.frontier_state,
                        "target_state": item.target_state,
                        "maximum_absolute_regression": item.maximum_absolute_regression,
                    }
                    for item in anchor_probes
                ]
            },
            developmental_summary={
                "decisions": len(developments),
                "admissions": sum(
                    item.get("decision") == "admitted_provisional_tissue"
                    for item in developments
                ),
            },
        )
        report = {
            "schema_version": SESSION_REPORT_SCHEMA,
            "run_id": run_id,
            "session_id": session_id,
            "session_index": session_index,
            "source": {
                "events_sha256": session["events_sha256"],
                "features_sha256": session["feature_sha256"],
                "event_count": len(events),
            },
            "duration_seconds": round(duration, 3),
            "mean_seconds_per_event": duration / max(len(events), 1),
            "mean_loss": statistics.fmean(losses) if losses else None,
            "mean_visual_loss": (
                statistics.fmean(visual_losses) if visual_losses else None
            ),
            "mean_text_loss": statistics.fmean(text_losses) if text_losses else None,
            "target_token_exact_fraction": exact / max(len(losses), 1),
            "visual_target_token_exact_fraction": (
                visual_exact / max(len(visual_losses), 1)
            ),
            "text_target_token_exact_fraction": (
                text_exact / max(len(text_losses), 1)
            ),
            "visual_event_count": len(visual_losses),
            "text_event_count": len(text_losses),
            "mean_active_uids": statistics.fmean(active_counts) if active_counts else 0.0,
            "maximum_active_uids": max(active_counts, default=0),
            "allocated_uids": len(student.organism.substrate.cells),
            "admitted_births": sum(
                item.get("decision") == "admitted_provisional_tissue"
                for item in developments
            ),
            "development_diagnoses": {
                diagnosis: sum(
                    diagnosis in item.get("diagnoses", []) for item in developments
                )
                for diagnosis in (
                    "insufficient_evidence",
                    "evidence_failure",
                    "route_failure",
                    "existing_tissue_learning",
                    "capacity_failure",
                )
            },
            "snapshot": str(snapshot),
        }
        atomic_json(reports_dir / f"session-{session_index:02d}.json", report)
        append_jsonl(journal_path, {
            "schema_version": JOURNAL_SCHEMA,
            "kind": "session_completed",
            "report": report,
        }, durable=True)
        removed = prune_shared_snapshots(store, session_index)
        progress["pruned_shared_snapshots"] = removed
        atomic_json(progress_path, progress)
        print(json.dumps({
            "session": session_id,
            "events_consumed": cumulative_events,
            "allocated_uids": len(student.organism.substrate.cells),
            "admitted_births": report["admitted_births"],
            "mean_loss": report["mean_loss"],
            "mean_active_uids": report["mean_active_uids"],
            "duration_seconds": report["duration_seconds"],
            "snapshot": str(snapshot),
        }, sort_keys=True), flush=True)
        del features

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
