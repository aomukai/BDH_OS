#!/usr/bin/env python3
"""Train one fresh complete Mycelium organism on an immutable research dataset."""

from __future__ import annotations

import argparse
from collections import deque
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import statistics
import time
import uuid
from typing import Any, Iterator

import torch

from campaign36c import (
    Campaign36CStudent,
    DevelopmentPolicyConfig,
    DevelopmentProbe,
    ExecutedSubgraphTrainer,
    OrganismConfig,
    OrganismSnapshotStore,
    ResidualObservation,
    SparseWaveConfig,
)
from campaign36c.research_data import (
    inspect_dataset,
    iter_dataset_records,
    load_record_image,
    validate_dataset_manifest,
)
from meta.scripts.train_campaign36c_bootstrap import (
    append_jsonl,
    apply_objective,
    atomic_json,
    clear_gradients,
    latent_target,
    maybe_develop,
    restore_rng,
    select_sponsor,
    shared_optimizer,
    verify_complete_organ_set,
)


JOURNAL_SCHEMA = "ninereeds_mycelium_research_training_event_v1"
PROGRESS_SCHEMA = "ninereeds_mycelium_research_training_progress_v1"


def _spool_records(
    database: Path,
    dataset: Path,
    manifest: dict[str, Any],
    *,
    limit: int,
) -> int:
    if database.exists():
        raise RuntimeError("research record spool already exists")
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "CREATE TABLE records(ordinal INTEGER PRIMARY KEY, payload_json TEXT NOT NULL)"
        )
        count = 0
        for record in iter_dataset_records(dataset, manifest):
            connection.execute(
                "INSERT INTO records(ordinal,payload_json) VALUES(?,?)",
                (count, json.dumps(record, ensure_ascii=False, sort_keys=True)),
            )
            count += 1
            if count >= limit:
                break
            if count % 10_000 == 0:
                connection.commit()
        connection.commit()
    finally:
        connection.close()
    if count == 0:
        raise RuntimeError("research dataset produced no usable training records")
    return count


def _epoch_records(
    database: Path,
    *,
    order_policy: str,
    order_seed: int,
    epoch: int,
) -> Iterator[dict[str, Any]]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        if order_policy == "declared":
            rows = connection.execute(
                "SELECT payload_json FROM records ORDER BY ordinal"
            )
        else:
            effective_epoch = 0 if order_policy == "shuffle_once" else epoch
            seed_payload = f"{order_seed}:{effective_epoch}".encode("utf-8")
            seed_digest = hashlib.sha256(seed_payload).digest()
            multiplier = int.from_bytes(seed_digest[:4], "big") % 2_147_483_646 + 1
            offset = int.from_bytes(seed_digest[4:8], "big") % 2_147_483_647
            rows = connection.execute(
                """SELECT payload_json FROM records
                   ORDER BY ((ordinal * ? + ?) % 2147483647), ordinal""",
                (multiplier, offset),
            )
        for row in rows:
            yield json.loads(row[0])
    finally:
        connection.close()


def _record_blocks(records: Iterator[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    block: list[dict[str, Any]] = []
    for record in records:
        block.append(record)
        if len(block) == 10:
            yield block
            block = []
    if block:
        yield block


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _research_observation(
    record: dict[str, Any],
    objective: Any,
    gradient: torch.Tensor,
    *,
    held_out: bool,
    existing_loss_before: float,
    existing_loss_after: float,
) -> ResidualObservation:
    sponsor_uid, ownership, coverage, delta = select_sponsor(objective.thought.result)
    root = objective.thought.root_state.detach().clone()
    frontier = (root + delta.detach()).clone()
    target = latent_target(frontier, gradient)
    return ResidualObservation(
        thought_epoch=int(objective.thought.result.eligibility[0].thought_epoch),
        sponsor_uid=sponsor_uid,
        claim_address=f"research:{record['record_id']}",
        evidence_lineage=record["evidence_lineage"],
        source_family=record["source_family"],
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


def _objective(
    student: Campaign36CStudent,
    record: dict[str, Any],
    dataset_path: Path,
    dataset_manifest: dict[str, Any],
    *,
    retain_terminal_gradient: bool,
) -> Any:
    claim = f"research:{record['record_id']}"
    lineage = (record["evidence_lineage"],)
    if record["modality"] == "text":
        return student.text_objective(
            record["prompt"],
            record["completion"],
            claim_address=claim,
            evidence_lineage=lineage,
            novelty=1.0,
            retain_terminal_gradient=retain_terminal_gradient,
        )
    image = load_record_image(dataset_path, dataset_manifest, record["image_member"])
    return student.image_objective(
        image,
        record["completion"],
        claim_address=claim,
        evidence_lineage=lineage,
        novelty=1.0,
        retain_terminal_gradient=retain_terminal_gradient,
    )


def _apply_record(
    student: Campaign36CStudent,
    sparse_trainer: ExecutedSubgraphTrainer,
    optimizer: torch.optim.AdamW,
    record: dict[str, Any],
    dataset_path: Path,
    dataset_manifest: dict[str, Any],
    *,
    update: bool,
) -> tuple[Any, torch.Tensor, Any | None]:
    optimizer.zero_grad(set_to_none=True)
    objective = _objective(
        student,
        record,
        dataset_path,
        dataset_manifest,
        retain_terminal_gradient=update,
    )
    return apply_objective(
        student,
        sparse_trainer,
        optimizer,
        objective,
        claim=f"research:{record['record_id']}",
        lineage=(record["evidence_lineage"],),
        update=update,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-spec", type=Path, required=True)
    parser.add_argument("--organ-donor", type=Path, required=True)
    parser.add_argument("--visual-receptor-snapshot", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--epochs", type=int, required=True)
    parser.add_argument("--max-records-per-epoch", type=int, required=True)
    parser.add_argument(
        "--order-policy",
        choices=("declared", "shuffle_once", "reshuffle_each_epoch"),
        required=True,
    )
    parser.add_argument("--order-seed", type=int, required=True)
    parser.add_argument("--seed", type=int, default=3_603_602)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--cell-learning-rate", type=float, default=3e-3)
    parser.add_argument("--weight-decay", type=float, default=0.0)
    parser.add_argument("--seed-ingress-cells", type=int, default=8)
    parser.add_argument("--cell-rotary-pairs", type=int, default=2)
    parser.add_argument("--initial-route-energy", type=float, default=64.0)
    parser.add_argument("--branch-energy-floor", type=float, default=0.10)
    parser.add_argument("--max-waves", type=int, default=32)
    parser.add_argument("--max-total-activations", type=int, default=256)
    parser.add_argument("--max-degree", type=int, default=16)
    parser.add_argument("--max-fanout", type=int, default=4)
    parser.add_argument("--minimum-observations", type=int, default=6)
    parser.add_argument("--minimum-independent-lineages", type=int, default=6)
    parser.add_argument("--minimum-source-families", type=int, default=2)
    parser.add_argument("--minimum-residual-coherence", type=float, default=0.80)
    parser.add_argument("--shadow-training-steps", type=int, default=64)
    parser.add_argument("--shadow-learning-rate", type=float, default=0.03)
    parser.add_argument("--core-device", default="cuda:0")
    parser.add_argument("--tissue-device", default="cuda:1")
    parser.add_argument("--dtype", choices=("bfloat16", "float32"), default="bfloat16")
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    if args.epochs < 1 or args.max_records_per_epoch < 1:
        raise ValueError("research epochs and record exposure must be positive")
    dataset_spec = json.loads(args.dataset_spec.read_text(encoding="utf-8"))
    dataset_path = Path(dataset_spec["path"]).resolve()
    dataset_manifest = validate_dataset_manifest(dataset_spec["manifest"])
    source = dataset_manifest["source"]
    if (
        not dataset_path.is_file()
        or dataset_path.stat().st_size != source["byte_size"]
        or _sha256(dataset_path) != source["sha256"]
    ):
        raise RuntimeError("research dataset bytes do not match their immutable manifest")
    inspection = inspect_dataset(dataset_path, dataset_manifest)

    organism_config = OrganismConfig(
        seed_ingress_cells=args.seed_ingress_cells,
        cell_rotary_pairs=args.cell_rotary_pairs,
    )
    wave_config = SparseWaveConfig(
        initial_route_energy=args.initial_route_energy,
        branch_energy_floor=args.branch_energy_floor,
        max_waves=args.max_waves,
        max_total_activations=args.max_total_activations,
        max_degree=args.max_degree,
        max_fanout=args.max_fanout,
    )
    policy = DevelopmentPolicyConfig(
        minimum_observations=args.minimum_observations,
        minimum_independent_lineages=args.minimum_independent_lineages,
        minimum_source_families=args.minimum_source_families,
        minimum_residual_coherence=args.minimum_residual_coherence,
        shadow_training_steps=args.shadow_training_steps,
        shadow_learning_rate=args.shadow_learning_rate,
    )
    organism_config.validate()
    wave_config.validate()
    policy.validate()
    experiment_config = {
        "dataset": {
            "artifact_id": dataset_spec["artifact_id"],
            "sha256": source["sha256"],
            "name": dataset_manifest["dataset_name"],
            "adapter": dataset_manifest["adapter"],
            "inspection": inspection,
        },
        "exposure": {
            "epochs": args.epochs,
            "max_records_per_epoch": args.max_records_per_epoch,
            "order_policy": args.order_policy,
            "order_seed": args.order_seed,
        },
        "optimizer": {
            "seed": args.seed,
            "learning_rate": args.learning_rate,
            "cell_learning_rate": args.cell_learning_rate,
            "weight_decay": args.weight_decay,
        },
        "organism": dataclasses.asdict(organism_config),
        "wave": dataclasses.asdict(wave_config),
        "development": dataclasses.asdict(policy),
    }

    args.output_dir.mkdir(parents=True, exist_ok=False)
    journal_path = args.output_dir / "events.jsonl"
    progress_path = args.output_dir / "progress.json"
    spool_path = args.output_dir / "records.sqlite3"
    record_count = _spool_records(
        spool_path,
        dataset_path,
        dataset_manifest,
        limit=args.max_records_per_epoch,
    )
    restore_rng(None, args.seed)
    dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float32
    core_device = torch.device(args.core_device)
    tissue_device = torch.device(args.tissue_device)
    student = Campaign36CStudent.from_organ_donor(
        args.organ_donor,
        organism_config=organism_config,
        wave_config=wave_config,
        frozen_dtype=dtype,
        local_files_only=args.local_files_only,
        visual_receptor_snapshot=args.visual_receptor_snapshot,
    )
    partition = student.place(core_device=core_device, tissue_device=tissue_device, dtype=dtype)
    organ_preflight = verify_complete_organ_set(student)
    sparse_trainer = ExecutedSubgraphTrainer(student.organism.substrate)
    sparse_trainer.optimizer_config = dataclasses.replace(
        sparse_trainer.optimizer_config, learning_rate=args.cell_learning_rate
    )
    optimizer = shared_optimizer(
        student, learning_rate=args.learning_rate, weight_decay=args.weight_decay
    )
    clear_gradients(student.shared_trainable_parameters())
    store = OrganismSnapshotStore(args.output_dir / "organism")
    next_uid = max(int(uid) for uid in student.organism.substrate.cells) + 1
    run_id = f"mycelium-research-{time.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
    cumulative_events = 0
    modality_events = {"text": 0, "image_text": 0}
    anchor_probes: deque[DevelopmentProbe] = deque(maxlen=8)
    initial = {
        "schema_version": PROGRESS_SCHEMA,
        "status": "preflight",
        "run_id": run_id,
        "epochs_completed": 0,
        "epochs_target": args.epochs,
        "records_per_epoch": record_count,
        "events_consumed": 0,
        "modality_events_consumed": modality_events,
        "active_uid_count": len(student.organism.substrate.cells),
        "next_uid": next_uid,
        "organ_preflight": organ_preflight,
        "experiment_config": experiment_config,
    }
    store.save(
        "embryo-preflight",
        student,
        sparse_trainer,
        optimizer,
        progress=initial,
        next_uid=next_uid,
        developmental_state={"anchor_probes": []},
        developmental_summary={"status": "no_training_event_consumed"},
    )
    atomic_json(progress_path, initial)
    append_jsonl(journal_path, {
        "schema_version": JOURNAL_SCHEMA,
        "kind": "run_started",
        "run_id": run_id,
        "dataset_artifact_id": dataset_spec["artifact_id"],
        "dataset_sha256": source["sha256"],
        "partition": partition,
        "experiment_config": experiment_config,
    }, durable=True)

    student.train()
    for epoch in range(args.epochs):
        started = time.monotonic()
        records = _epoch_records(
            spool_path,
            order_policy=args.order_policy,
            order_seed=args.order_seed,
            epoch=epoch,
        )
        losses: list[float] = []
        developments: list[dict[str, Any]] = []
        for block_index, block in enumerate(_record_blocks(records)):
            block_start = block_index * 10
            provisional: list[tuple[dict[str, Any], Any, torch.Tensor, bool]] = []
            complete_block = len(block) == 10
            for offset, record in enumerate(block):
                held_out = complete_block and offset >= 8
                objective, gradient, credit = _apply_record(
                    student,
                    sparse_trainer,
                    optimizer,
                    record,
                    dataset_path,
                    dataset_manifest,
                    update=not held_out,
                )
                provisional.append((record, objective, gradient, held_out))
                if not held_out:
                    loss = float(objective.loss.detach().cpu())
                    losses.append(loss)
                    cumulative_events += 1
                    modality_events[record["modality"]] += 1
                    append_jsonl(journal_path, {
                        "schema_version": JOURNAL_SCHEMA,
                        "kind": "training_event",
                        "run_id": run_id,
                        "epoch": epoch,
                        "event_number": cumulative_events,
                        "record_id": record["record_id"],
                        "modality": record["modality"],
                        "loss": loss,
                        "target_probability": objective.target_probability,
                        "target_token_exact": objective.target_token_exact,
                        "updated_uids": list(credit.updated_uids),
                    })
            if complete_block:
                before = statistics.fmean(
                    float(item[1].loss.detach().cpu()) for item in provisional[:2]
                )
                after = statistics.fmean(
                    float(item[1].loss.detach().cpu()) for item in provisional[8:]
                )
                observations = [
                    _research_observation(
                        record,
                        objective,
                        gradient,
                        held_out=held_out,
                        existing_loss_before=before,
                        existing_loss_after=after,
                    )
                    for record, objective, gradient, held_out in provisional
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
                    "epoch": epoch,
                    "block_start": block_start,
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
                for record, _objective_value, _gradient, _held_out in provisional[8:]:
                    objective, _gradient_value, credit = _apply_record(
                        student,
                        sparse_trainer,
                        optimizer,
                        record,
                        dataset_path,
                        dataset_manifest,
                        update=True,
                    )
                    loss = float(objective.loss.detach().cpu())
                    losses.append(loss)
                    cumulative_events += 1
                    modality_events[record["modality"]] += 1
                    append_jsonl(journal_path, {
                        "schema_version": JOURNAL_SCHEMA,
                        "kind": "training_event",
                        "run_id": run_id,
                        "epoch": epoch,
                        "event_number": cumulative_events,
                        "record_id": record["record_id"],
                        "modality": record["modality"],
                        "loss": loss,
                        "target_probability": objective.target_probability,
                        "target_token_exact": objective.target_token_exact,
                        "updated_uids": list(credit.updated_uids),
                        "held_out_before_update": True,
                    })
        progress = {
            "schema_version": PROGRESS_SCHEMA,
            "status": "complete" if epoch + 1 == args.epochs else "training",
            "run_id": run_id,
            "epochs_completed": epoch + 1,
            "epochs_target": args.epochs,
            "records_per_epoch": record_count,
            "events_consumed": cumulative_events,
            "modality_events_consumed": dict(modality_events),
            "active_uid_count": len(student.organism.substrate.cells),
            "next_uid": next_uid,
            "last_loss": losses[-1] if losses else None,
            "mean_loss": statistics.fmean(losses) if losses else None,
            "duration_seconds": round(time.monotonic() - started, 3),
            "admitted_births": sum(
                item.get("decision") == "admitted_provisional_tissue"
                for item in developments
            ),
            "organ_preflight": organ_preflight,
            "experiment_config": experiment_config,
        }
        store.save(
            f"epoch-{epoch:04d}",
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
                "admissions": progress["admitted_births"],
            },
        )
        atomic_json(progress_path, progress)
        append_jsonl(journal_path, {
            "schema_version": JOURNAL_SCHEMA,
            "kind": "epoch_completed",
            "progress": progress,
        }, durable=True)
        print(json.dumps(progress, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
