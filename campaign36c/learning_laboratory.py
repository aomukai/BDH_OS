from __future__ import annotations

import hashlib
import io
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
import statistics
import tempfile
from typing import Any

import torch
import torch.nn.functional as F

from .cell import StandaloneBDHCell
from .config import BDHCellConfig, CellOptimizerConfig, SparseWaveConfig
from .epistemics import PatchReducer, ResultGrade, make_latent_patch
from .learning import ExecutedSubgraphTrainer, LearningExample, RetentionProbe
from .wave import SparseWaveSubstrate, WaveCell


CAMPAIGN36C_LEARNING_LAB_RESULT_SCHEMA = (
    "ninereeds_campaign36c_learning_lab_result_v0"
)


@dataclass(frozen=True)
class LearningLabConfig:
    width: int = 512
    rotary_pairs: int = 2
    sequence_length: int = 16
    training_examples: int = 12
    evaluation_examples: int = 6
    training_steps: int = 64
    black_swan_steps: int = 32
    common_replay_steps: int = 16
    disconnected_cells: int = 64
    learning_rate: float = 0.03
    minimum_heldout_improvement_fraction: float = 0.01
    seed: int = 36_300

    def validate(self) -> None:
        positive = (
            "width",
            "rotary_pairs",
            "sequence_length",
            "training_examples",
            "evaluation_examples",
            "training_steps",
            "black_swan_steps",
            "common_replay_steps",
        )
        if any(getattr(self, name) <= 0 for name in positive):
            raise ValueError("laboratory dimensions and step counts must be positive")
        if self.disconnected_cells < 0 or self.learning_rate <= 0:
            raise ValueError("disconnected count and learning rate are invalid")
        if not 0 <= self.minimum_heldout_improvement_fraction <= 1:
            raise ValueError("held-out improvement fraction must be in [0, 1]")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")


def _member(
    uid: int,
    config: LearningLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> WaveCell:
    return WaveCell(
        StandaloneBDHCell(
            BDHCellConfig(
                width=config.width,
                rotary_pairs=config.rotary_pairs,
                initialization_seed=config.seed + uid,
            ),
            uid=uid,
        ),
        max_degree=8,
        max_fanout=4,
    ).to(device=device, dtype=dtype)


def _teacher_cells(
    count: int,
    config: LearningLabConfig,
    *,
    seed_offset: int,
    device: torch.device,
    dtype: torch.dtype,
) -> list[StandaloneBDHCell]:
    cells = [
        StandaloneBDHCell(
            BDHCellConfig(
                width=config.width,
                rotary_pairs=config.rotary_pairs,
                initialization_seed=config.seed + seed_offset + index,
            ),
            uid=90_000 + seed_offset + index,
        ).to(device=device, dtype=dtype)
        for index in range(count)
    ]
    with torch.no_grad():
        for cell in cells:
            cell.encoder.mul_(4.0)
            cell.value_encoder.mul_(4.0)
            cell.decoder.mul_(8.0)
    return cells


def _examples(
    count: int,
    config: LearningLabConfig,
    *,
    base_seed: int,
    example_offset: int = 0,
    ingress_uid: int,
    teacher: list[StandaloneBDHCell],
    claim_address: str,
    lineage_prefix: str,
    device: torch.device,
    dtype: torch.dtype,
) -> list[LearningExample]:
    examples: list[LearningExample] = []
    base_generator = torch.Generator(device="cpu").manual_seed(base_seed)
    prototype = torch.randn(
        1,
        config.sequence_length,
        config.width,
        generator=base_generator,
    )
    for index in range(count):
        generator = torch.Generator(device="cpu").manual_seed(
            base_seed + example_offset + index + 1
        )
        noise = torch.randn(
            1,
            config.sequence_length,
            config.width,
            generator=generator,
        )
        root = (prototype + 0.05 * noise).to(device=device, dtype=dtype)
        with torch.no_grad():
            target = root
            for cell in teacher:
                target = cell(target)
        examples.append(
            LearningExample(
                root_state=root,
                target_state=target.detach(),
                ingress_uids=ingress_uid,
                claim_address=claim_address,
                evidence_lineage=(f"{lineage_prefix}:{index}",),
            )
        )
    return examples


def _mean_loss(
    trainer: ExecutedSubgraphTrainer,
    examples: list[LearningExample],
) -> float:
    return statistics.fmean(trainer.evaluate_loss(example) for example in examples)


def _state_digest(module: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(module.state_dict().items()):
        digest.update(name.encode("utf-8"))
        tensor = value.detach().float().contiguous().cpu()
        digest.update(tensor.reshape(-1).view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def _optimizer_digest(
    trainer: ExecutedSubgraphTrainer,
    uids: tuple[int, ...],
) -> str:
    buffer = io.BytesIO()
    torch.save(
        {
            uid: trainer._optimizers[uid].state_dict()
            for uid in uids
            if uid in trainer._optimizers
        },
        buffer,
    )
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def _black_swan_reduction(
    config: LearningLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    positive = torch.ones(
        1, config.sequence_length, config.width, device=device, dtype=dtype
    )
    common = make_latent_patch(
        patch_id="common-white-universal",
        source_uid=1,
        base_version="swan-root",
        claim_address="swan:universal-colour",
        expected_merge_mode="single_value",
        state_before=torch.zeros_like(positive),
        operation_delta=positive,
        dependency_ids=(),
        evidence_lineage=("white-stream",),
        route_provenance=((1,),),
        ownership=0.99,
        coverage=0.99,
    )
    exception = make_latent_patch(
        patch_id="rare-black-observation",
        source_uid=20,
        base_version="swan-root",
        claim_address="swan:universal-colour",
        expected_merge_mode="single_value",
        state_before=torch.zeros_like(positive),
        operation_delta=-positive,
        dependency_ids=(),
        evidence_lineage=("black-observation",),
        route_provenance=((20,),),
        ownership=0.95,
        coverage=0.95,
    )
    envelope = PatchReducer().reduce((common, exception))
    return {
        "grade": envelope.grade.value,
        "hypothesis_count": len(envelope.hypotheses),
        "conflict_summary": [list(item) for item in envelope.conflict_summary],
        "rare_evidence_retained": (
            exception.patch_id in envelope.retained_patch_ids
        ),
        "pass": (
            envelope.grade is ResultGrade.UNRESOLVED
            and len(envelope.hypotheses) == 2
            and exception.patch_id in envelope.retained_patch_ids
        ),
    }


def run_learning_laboratory(
    config: LearningLabConfig | None = None,
    *,
    device: str | torch.device = "cpu",
    dtype: torch.dtype = torch.float32,
) -> dict[str, Any]:
    config = config or LearningLabConfig()
    config.validate()
    target_device = torch.device(device)
    if target_device.type == "cpu" and dtype != torch.float32:
        raise ValueError("the CPU Stage-3 lab requires float32")
    if target_device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable")

    substrate = SparseWaveSubstrate(
        SparseWaveConfig(
            initial_route_energy=64,
            max_degree=16,
            max_fanout=4,
            max_total_activations=128,
        )
    ).to(device=target_device, dtype=dtype)
    common_teacher = _teacher_cells(
        3,
        config,
        seed_offset=10_000,
        device=target_device,
        dtype=dtype,
    )
    rare_teacher = _teacher_cells(
        2,
        config,
        seed_offset=20_000,
        device=target_device,
        dtype=dtype,
    )
    with torch.no_grad():
        for cell in (*common_teacher, *rare_teacher):
            cell.encoder.mul_(1.5)
            cell.value_encoder.mul_(1.5)
            cell.decoder.mul_(2.0)
    common_train = _examples(
        config.training_examples,
        config,
        base_seed=config.seed + 30_000,
        example_offset=0,
        ingress_uid=1,
        teacher=common_teacher,
        claim_address="synthetic:common-route",
        lineage_prefix="common-train",
        device=target_device,
        dtype=dtype,
    )
    common_eval = _examples(
        config.evaluation_examples,
        config,
        base_seed=config.seed + 30_000,
        example_offset=10_000,
        ingress_uid=1,
        teacher=common_teacher,
        claim_address="synthetic:common-route",
        lineage_prefix="common-eval",
        device=target_device,
        dtype=dtype,
    )
    rare_train = _examples(
        max(2, config.training_examples // 3),
        config,
        base_seed=config.seed + 50_000,
        example_offset=0,
        ingress_uid=20,
        teacher=rare_teacher,
        claim_address="synthetic:black-swan-route",
        lineage_prefix="rare-train",
        device=target_device,
        dtype=dtype,
    )
    rare_eval = _examples(
        max(2, config.evaluation_examples // 2),
        config,
        base_seed=config.seed + 50_000,
        example_offset=10_000,
        ingress_uid=20,
        teacher=rare_teacher,
        claim_address="synthetic:black-swan-route",
        lineage_prefix="rare-eval",
        device=target_device,
        dtype=dtype,
    )

    common_prototype = common_train[0].root_state
    rare_prototype = rare_train[0].root_state
    for uid in (1, 2, 3):
        member = _member(uid, config, device=target_device, dtype=dtype)
        member.receptor.tune_to(common_prototype)
        substrate.add_cell(member)
    for uid in (20, 21):
        member = _member(uid, config, device=target_device, dtype=dtype)
        member.receptor.tune_to(rare_prototype)
        substrate.add_cell(member)
    rejected = _member(90, config, device=target_device, dtype=dtype)
    rejected.receptor.tune_to(-common_prototype)
    substrate.add_cell(rejected)
    for offset in range(config.disconnected_cells):
        substrate.add_cell(
            _member(1_000 + offset, config, device=target_device, dtype=dtype)
        )
    substrate.connect(1, 2)
    substrate.connect(2, 3)
    substrate.connect(1, 90, route_familiarity=0.0)
    substrate.connect(20, 21)

    trainer = ExecutedSubgraphTrainer(
        substrate,
        optimizer_config=CellOptimizerConfig(learning_rate=config.learning_rate),
    )
    inactive_uids = (20, 21, 90, *(1_000 + i for i in range(config.disconnected_cells)))
    inactive_before = {
        uid: _state_digest(substrate.cells[str(uid)]) for uid in inactive_uids
    }
    common_loss_before = _mean_loss(trainer, common_eval)
    last_common = None
    updated_common_uids: set[int] = set()
    credit_roles: set[str] = set()
    receipt_dispositions: set[str] = set()
    for step in range(config.training_steps):
        last_common = trainer.train_step(common_train[step % len(common_train)])
        updated_common_uids.update(last_common.updated_uids)
        credit_roles.update(event.role.value for event in last_common.credit_events)
        receipt_dispositions.update(
            receipt.disposition.value for receipt in last_common.thought_result.receipts
        )
    common_loss_after = _mean_loss(trainer, common_eval)
    inactive_after_common = {
        uid: _state_digest(substrate.cells[str(uid)]) for uid in inactive_uids
    }
    inactive_untouched = inactive_before == inactive_after_common

    unknown_before = {
        uid: _state_digest(substrate.cells[str(uid)]) for uid in (1, 2, 3)
    }
    optimizer_uids_before_unknown = trainer.optimizer_uids
    unknown = trainer.train_step(common_train[0], outcome_available=False)
    unknown_outcome_no_update = (
        unknown.updated_uids == ()
        and trainer.optimizer_uids == optimizer_uids_before_unknown
        and unknown_before
        == {uid: _state_digest(substrate.cells[str(uid)]) for uid in (1, 2, 3)}
        and all(event.grade.value == "pending" for event in unknown.credit_events)
    )

    with torch.inference_mode():
        anchor_target = substrate.run_thought(
            common_eval[0].root_state,
            ingress_uids=common_eval[0].ingress_uids,
            claim_address=common_eval[0].claim_address,
            evidence_lineage=common_eval[0].evidence_lineage,
        ).state.clone()
    exact_anchor_example = LearningExample(
        **{
            **common_eval[0].__dict__,
            "target_state": anchor_target,
            "evidence_lineage": ("retention-anchor",),
        }
    )
    anchor = RetentionProbe(exact_anchor_example, maximum_absolute_regression=0.0)
    conflicting = LearningExample(
        **{
            **common_train[0].__dict__,
            "target_state": -common_train[0].target_state,
            "evidence_lineage": ("adversarial-conflict",),
        }
    )
    retention = trainer.train_step(
        conflicting,
        retention_probes=(anchor,),
    )

    rare_loss_before = _mean_loss(trainer, rare_eval)
    for step in range(config.black_swan_steps):
        trainer.train_step(rare_train[step % len(rare_train)])
    rare_loss_after = _mean_loss(trainer, rare_eval)
    rare_parameter_digest = {
        uid: _state_digest(substrate.cells[str(uid)]) for uid in (20, 21)
    }
    rare_optimizer_digest = _optimizer_digest(trainer, (20, 21))
    rare_loss_before_common_replay = _mean_loss(trainer, rare_eval)
    for step in range(config.common_replay_steps):
        trainer.train_step(common_train[step % len(common_train)])
    rare_loss_after_common_replay = _mean_loss(trainer, rare_eval)
    rare_survives_common_replay = (
        rare_parameter_digest
        == {uid: _state_digest(substrate.cells[str(uid)]) for uid in (20, 21)}
        and rare_optimizer_digest == _optimizer_digest(trainer, (20, 21))
        and rare_loss_after_common_replay == rare_loss_before_common_replay
    )

    common_improvement = (
        (common_loss_before - common_loss_after) / max(common_loss_before, 1e-12)
    )
    rare_improvement = (
        (rare_loss_before - rare_loss_after) / max(rare_loss_before, 1e-12)
    )
    black_swan_reduction = _black_swan_reduction(
        config, device=target_device, dtype=dtype
    )
    active_route_learning_pass = (
        common_improvement >= config.minimum_heldout_improvement_fraction
        and updated_common_uids == {1, 2, 3}
        and set(trainer.optimizer_uids).issuperset({1, 2, 3})
    )
    black_swan_pass = (
        rare_improvement >= config.minimum_heldout_improvement_fraction
        and rare_survives_common_replay
        and black_swan_reduction["pass"]
    )
    typed_credit_pass = (
        {"transform", "route"}.issubset(credit_roles)
        and {"forwarded", "absorbed", "rejected"}.issubset(receipt_dispositions)
    )
    retention_pass = retention.retention_rollback
    stage3_exit_gate_met = all(
        (
            active_route_learning_pass,
            inactive_untouched,
            unknown_outcome_no_update,
            typed_credit_pass,
            retention_pass,
            black_swan_pass,
        )
    )
    assert last_common is not None
    return {
        "schema_version": CAMPAIGN36C_LEARNING_LAB_RESULT_SCHEMA,
        "lab_config": asdict(config),
        "execution": {
            "device": str(target_device),
            "dtype": str(dtype),
            "cuda_device_name": (
                torch.cuda.get_device_name(target_device)
                if target_device.type == "cuda"
                else None
            ),
        },
        "learning": {
            "common_heldout_loss_before": common_loss_before,
            "common_heldout_loss_after": common_loss_after,
            "common_heldout_improvement_fraction": common_improvement,
            "updated_common_uids": sorted(updated_common_uids),
            "optimizer_telemetry": trainer.optimizer_state_telemetry(),
            "route_familiarity": {
                "1->2": substrate.cells["1"].ports[2].route_familiarity,
                "2->3": substrate.cells["2"].ports[3].route_familiarity,
            },
            "credit_roles": sorted(credit_roles),
            "receipt_dispositions": sorted(receipt_dispositions),
        },
        "containment": {
            "inactive_uid_count_during_common_training": len(inactive_uids),
            "inactive_tissue_bit_identical": inactive_untouched,
            "unknown_outcome_no_update": unknown_outcome_no_update,
            "unknown_credit_event_count": len(unknown.credit_events),
            "retention_rollback": retention.retention_rollback,
            "retention_losses_before": list(retention.retention_losses_before),
            "retention_losses_after": list(retention.retention_losses_after),
        },
        "black_swan": {
            "heldout_loss_before": rare_loss_before,
            "heldout_loss_after": rare_loss_after,
            "heldout_improvement_fraction": rare_improvement,
            "parameter_and_optimizer_state_survives_common_replay": (
                rare_survives_common_replay
            ),
            "loss_before_common_replay": rare_loss_before_common_replay,
            "loss_after_common_replay": rare_loss_after_common_replay,
            "reduction": black_swan_reduction,
        },
        "selection": {
            "active_route_learning_pass": active_route_learning_pass,
            "inactive_tissue_untouched_pass": inactive_untouched,
            "unknown_outcome_expiry_pass": unknown_outcome_no_update,
            "typed_credit_and_receipts_pass": typed_credit_pass,
            "retention_pass": retention_pass,
            "black_swan_survival_pass": black_swan_pass,
            "stage3_exit_gate_met": stage3_exit_gate_met,
            "learning_rule": (
                "ordinary end-to-end backpropagation through the executed graph; "
                "not claimed as Hebbian learning"
            ),
        },
    }


def merge_learning_lab_results(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one Stage-3 device report is required")
    first = reports[0]
    if any(report["lab_config"] != first["lab_config"] for report in reports):
        raise ValueError("Stage-3 device reports used different configurations")
    all_devices_pass = all(
        report["selection"]["stage3_exit_gate_met"] for report in reports
    )
    return {
        "schema_version": CAMPAIGN36C_LEARNING_LAB_RESULT_SCHEMA,
        "lab_config": first["lab_config"],
        "execution": {"devices": [report["execution"] for report in reports]},
        "device_reports": reports,
        "selection": {
            "all_devices_pass": all_devices_pass,
            "stage3_exit_gate_met": all_devices_pass,
            "learning_rule": first["selection"]["learning_rule"],
        },
    }


def write_learning_lab_result(path: str | Path, result: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
