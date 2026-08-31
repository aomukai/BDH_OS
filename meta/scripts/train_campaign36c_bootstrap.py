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

import torch

from campaign36c import (
    Campaign36CVisualStudent,
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


JOURNAL_SCHEMA = "ninereeds_campaign36c_bootstrap_event_v1"
PROGRESS_SCHEMA = "ninereeds_campaign36c_bootstrap_progress_v1"
SESSION_REPORT_SCHEMA = "ninereeds_campaign36c_bootstrap_session_v1"
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
    student: Campaign36CVisualStudent,
    *,
    learning_rate: float,
    weight_decay: float,
) -> torch.optim.AdamW:
    core_side = [
        *student.organism.continuity_parameters(),
        *student.resampler.parameters(),
    ]
    speech_side = [
        *student.intention.parameters(),
        *student.expression.projector.parameters(),
    ]
    return torch.optim.AdamW(
        [
            {"params": core_side, "component": "continuity_and_visual"},
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
    claim = f"visual:lexeme:{int(event['ordinal']):04d}:{event['concept']}"
    lineage = (f"siglip2:{event['asset_sha256']}",)
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


def run_objective(
    student: Campaign36CVisualStudent,
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


def maybe_develop(
    observations: list[ResidualObservation],
    student: Campaign36CVisualStudent,
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
        student = Campaign36CVisualStudent.from_snapshot(
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
        run_id = str(progress["run_id"])
    else:
        if args.resume:
            raise RuntimeError("--resume requested but no organism snapshot exists")
        restore_rng(None, args.seed)
        student = Campaign36CVisualStudent.from_organ_donor(
            args.organ_donor,
            organism_config=OrganismConfig(),
            frozen_dtype=dtype,
            local_files_only=args.local_files_only,
        )
        partition = student.place(
            core_device=core_device, tissue_device=tissue_device, dtype=dtype
        )
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
        next_uid = max(int(uid) for uid in student.organism.substrate.cells) + 1
        progress = {
            "schema_version": PROGRESS_SCHEMA,
            "status": "preflight",
            "run_id": run_id,
            "sessions_completed": 0,
            "events_consumed": 0,
            "events_in_bootstrap": manifest["event_count"],
            "bootstrap_manifest_identity": BOOTSTRAP_MANIFEST_IDENTITY,
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
        exact = 0
        active_counts: list[int] = []
        developments: list[dict[str, Any]] = []

        for block_start in range(0, len(events), 10):
            block = events[block_start : block_start + 10]
            if len({int(item["ordinal"]) for item in block}) != 1:
                raise RuntimeError("frozen bootstrap lost its ten-image concept blocks")
            provisional: list[tuple[dict[str, Any], Any, torch.Tensor, bool]] = []
            for offset, event in enumerate(block):
                feature = features.get(event["asset_sha256"])
                if feature is None:
                    raise ValueError(f"{session_id} lacks feature {event['asset_sha256']}")
                held_out = len(block) == 10 and offset >= 8
                objective, gradient, credit = run_objective(
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
                    exact += int(objective.target_token_exact)
                    active_counts.append(
                        int(objective.thought.result.telemetry["unique_uid_count"])
                    )
                    cumulative_events += 1
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
                    objective, _gradient, credit = run_objective(
                        student,
                        sparse_trainer,
                        optimizer,
                        features[event["asset_sha256"]],
                        event,
                        update=True,
                    )
                    losses.append(float(objective.loss.detach().cpu()))
                    exact += int(objective.target_token_exact)
                    active_counts.append(
                        int(objective.thought.result.telemetry["unique_uid_count"])
                    )
                    cumulative_events += 1
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

            if cumulative_events % 10 == 0:
                atomic_json(progress_path, {
                    "schema_version": PROGRESS_SCHEMA,
                    "status": "training",
                    "run_id": run_id,
                    "session_id": session_id,
                    "session_index": session_index,
                    "events_consumed": cumulative_events,
                    "events_in_bootstrap": manifest["event_count"],
                    "active_uid_count": len(student.organism.substrate.cells),
                    "next_uid": next_uid,
                    "last_loss": losses[-1] if losses else None,
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
            "events_in_bootstrap": manifest["event_count"],
            "active_uid_count": len(student.organism.substrate.cells),
            "next_uid": next_uid,
            "last_loss": losses[-1] if losses else None,
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
            "target_token_exact_fraction": exact / max(len(losses), 1),
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
