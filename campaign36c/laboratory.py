from __future__ import annotations

import copy
import dataclasses
import json
import statistics
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import torch
import torch.nn.functional as F
from torch import nn

from .cell import (
    LowRankResidualControl,
    MaskedDenseBDHHeadControl,
    MaskedLocalBDHHeadControl,
    StandaloneBDHCell,
    batch_composition_max_difference,
    compare_masked_dense_cohort,
)
from .checkpoint import (
    build_cell_optimizer,
    load_cell_checkpoint,
    save_cell_checkpoint,
    tensor_storage_bytes,
)
from .config import BDHCellConfig, CellOptimizerConfig


CAMPAIGN36C_LATENT_TASK_SCHEMA = "ninereeds_campaign36c_latent_task_v0"
CAMPAIGN36C_CELL_LAB_RESULT_SCHEMA = "ninereeds_campaign36c_cell_lab_result_v0"


@dataclass(frozen=True)
class LatentSplit:
    root_state: torch.Tensor
    target_state: torch.Tensor
    attention_mask: torch.Tensor | None = None

    def validate(self, *, width: int | None = None) -> None:
        if self.root_state.ndim != 3:
            raise ValueError("root_state must have shape [batch, sequence, width]")
        if self.target_state.shape != self.root_state.shape:
            raise ValueError("target_state must have the same shape as root_state")
        if width is not None and self.root_state.size(-1) != width:
            raise ValueError(f"latent split width must be {width}")
        if (
            self.attention_mask is not None
            and self.attention_mask.shape != self.root_state.shape[:2]
        ):
            raise ValueError("attention_mask must match batch and sequence dimensions")
        if self.root_state.size(0) <= 0 or self.root_state.size(1) <= 0:
            raise ValueError("latent split may not be empty")

    def to(self, *, device: torch.device, dtype: torch.dtype) -> "LatentSplit":
        return LatentSplit(
            root_state=self.root_state.to(device=device, dtype=dtype),
            target_state=self.target_state.to(device=device, dtype=dtype),
            attention_mask=(
                None
                if self.attention_mask is None
                else self.attention_mask.to(device=device)
            ),
        )


@dataclass(frozen=True)
class LatentTask:
    training: LatentSplit
    evaluation: LatentSplit
    extra_core_tick_evaluation: torch.Tensor | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def width(self) -> int:
        return self.training.root_state.size(-1)

    def validate(self) -> None:
        self.training.validate()
        self.evaluation.validate(width=self.width)
        if self.extra_core_tick_evaluation is not None:
            if self.extra_core_tick_evaluation.shape != self.evaluation.target_state.shape:
                raise ValueError(
                    "extra_core_tick_evaluation must match the evaluation target shape"
                )

    def to(self, *, device: torch.device, dtype: torch.dtype) -> "LatentTask":
        return LatentTask(
            training=self.training.to(device=device, dtype=dtype),
            evaluation=self.evaluation.to(device=device, dtype=dtype),
            extra_core_tick_evaluation=(
                None
                if self.extra_core_tick_evaluation is None
                else self.extra_core_tick_evaluation.to(device=device, dtype=dtype)
            ),
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class CellLabConfig:
    pair_counts: tuple[int, ...] = (1, 2, 4, 8, 16, 32)
    training_steps: int = 64
    benchmark_warmup: int = 3
    benchmark_iterations: int = 10
    residual_scale: float = 0.25
    seed: int = 36_003
    mechanical_tolerance: float = 1e-5
    minimum_improvement_fraction: float = 0.01

    def validate(self) -> None:
        if not self.pair_counts or any(value <= 0 for value in self.pair_counts):
            raise ValueError("pair_counts must contain positive cohort sizes")
        if tuple(sorted(set(self.pair_counts))) != self.pair_counts:
            raise ValueError("pair_counts must be sorted and unique")
        if self.training_steps <= 0:
            raise ValueError("training_steps must be positive")
        if self.benchmark_warmup < 0 or self.benchmark_iterations <= 0:
            raise ValueError("benchmark counts are invalid")
        if not 0.0 < self.residual_scale <= 1.0:
            raise ValueError("residual_scale must be in (0, 1]")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if self.mechanical_tolerance < 0:
            raise ValueError("mechanical_tolerance must be non-negative")
        if not 0.0 <= self.minimum_improvement_fraction < 1.0:
            raise ValueError("minimum_improvement_fraction must be in [0, 1)")


def save_latent_task(path: Path, task: LatentTask) -> None:
    """Save continuity-core latent evidence as a portable Stage-1 input bundle."""

    task.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": CAMPAIGN36C_LATENT_TASK_SCHEMA,
            "training": {
                "root_state": task.training.root_state,
                "target_state": task.training.target_state,
                "attention_mask": task.training.attention_mask,
            },
            "evaluation": {
                "root_state": task.evaluation.root_state,
                "target_state": task.evaluation.target_state,
                "attention_mask": task.evaluation.attention_mask,
            },
            "extra_core_tick_evaluation": task.extra_core_tick_evaluation,
            "metadata": task.metadata,
        },
        path,
    )


def load_latent_task(path: Path) -> LatentTask:
    value = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(value, dict) or value.get("schema_version") != CAMPAIGN36C_LATENT_TASK_SCHEMA:
        raise ValueError("unsupported Campaign 36C latent-task bundle")

    def split(name: str) -> LatentSplit:
        item = value[name]
        return LatentSplit(
            root_state=item["root_state"],
            target_state=item["target_state"],
            attention_mask=item.get("attention_mask"),
        )

    task = LatentTask(
        training=split("training"),
        evaluation=split("evaluation"),
        extra_core_tick_evaluation=value.get("extra_core_tick_evaluation"),
        metadata=dict(value.get("metadata", {})),
    )
    task.validate()
    return task


def synthetic_latent_task(
    *,
    width: int = 512,
    sequence_length: int = 16,
    training_examples: int = 16,
    evaluation_examples: int = 8,
    teacher_pairs: int = 8,
    residual_scale: float = 0.25,
    seed: int = 36_003,
) -> LatentTask:
    """Create a deterministic mechanical smoke task, not behavioral evidence."""

    if min(width, sequence_length, training_examples, evaluation_examples, teacher_pairs) <= 0:
        raise ValueError("synthetic task dimensions must be positive")
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    train_root = torch.randn(
        training_examples, sequence_length, width, generator=generator
    )
    eval_root = torch.randn(
        evaluation_examples, sequence_length, width, generator=generator
    )
    teacher = StandaloneBDHCell(
        BDHCellConfig(
            width=width,
            rotary_pairs=teacher_pairs,
            residual_scale=residual_scale,
            initialization_seed=seed + 1,
        ),
        uid=0,
    ).eval()
    with torch.no_grad():
        # A stronger decoder makes the bounded smoke test informative without
        # pretending the random task measures cognitive usefulness.
        teacher.encoder.mul_(3)
        teacher.value_encoder.mul_(3)
        teacher.decoder.mul_(4)
        train_target = teacher(train_root)
        eval_target = teacher(eval_root)
    task = LatentTask(
        training=LatentSplit(train_root, train_target),
        evaluation=LatentSplit(eval_root, eval_target),
        metadata={
            "kind": "deterministic_synthetic_mechanical_smoke",
            "teacher_pairs": teacher_pairs,
            "seed": seed,
            "behavioral_evidence": False,
        },
    )
    task.validate()
    return task


def _masked_mse(output: torch.Tensor, split: LatentSplit) -> torch.Tensor:
    square_error = (output.float() - split.target_state.float()).square()
    if split.attention_mask is None:
        return square_error.mean()
    weights = split.attention_mask.to(
        device=output.device,
        dtype=square_error.dtype,
    ).unsqueeze(-1)
    return (square_error * weights).sum() / (
        weights.sum().clamp_min(1) * output.size(-1)
    )


def _no_cell_output(split: LatentSplit) -> torch.Tensor:
    output = F.layer_norm(split.root_state, (split.root_state.size(-1),))
    if split.attention_mask is not None:
        valid = split.attention_mask.to(device=output.device, dtype=torch.bool)
        output = torch.where(valid.unsqueeze(-1), output, split.root_state)
    return output


def _train(
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    split: LatentSplit,
    *,
    steps: int,
) -> tuple[float, float]:
    model.train()
    with torch.no_grad():
        initial = float(_masked_mse(model(split.root_state, split.attention_mask), split).cpu())
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        loss = _masked_mse(model(split.root_state, split.attention_mask), split)
        loss.backward()
        optimizer.step()
    with torch.no_grad():
        final = float(_masked_mse(model(split.root_state, split.attention_mask), split).cpu())
    return initial, final


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _benchmark_forward_milliseconds(
    model: nn.Module,
    split: LatentSplit,
    *,
    device: torch.device,
    warmup: int,
    iterations: int,
) -> dict[str, float]:
    model.eval()
    with torch.no_grad():
        for _ in range(warmup):
            model(split.root_state, split.attention_mask)
        _synchronize(device)
        samples = []
        for _ in range(iterations):
            start = time.perf_counter()
            model(split.root_state, split.attention_mask)
            _synchronize(device)
            samples.append((time.perf_counter() - start) * 1_000)
    return {
        "median_ms": statistics.median(samples),
        "minimum_ms": min(samples),
        "maximum_ms": max(samples),
    }


def _parameter_max_difference(
    left: Iterable[torch.nn.Parameter],
    right: Iterable[torch.nn.Parameter],
) -> float:
    differences = [
        float((a - b).detach().abs().max().cpu())
        for a, b in zip(left, right, strict=True)
    ]
    return max(differences, default=0.0)


def _resume_update_difference(
    cell: StandaloneBDHCell,
    optimizer: torch.optim.Optimizer,
    restored: StandaloneBDHCell,
    restored_optimizer: torch.optim.Optimizer,
    split: LatentSplit,
) -> float:
    for model, model_optimizer in (
        (cell, optimizer),
        (restored, restored_optimizer),
    ):
        model_optimizer.zero_grad(set_to_none=True)
        loss = _masked_mse(model(split.root_state, split.attention_mask), split)
        loss.backward()
        model_optimizer.step()
    return _parameter_max_difference(cell.parameters(), restored.parameters())


def _run_trial(
    *,
    pair_count: int,
    task: LatentTask,
    config: CellLabConfig,
    optimizer_config: CellOptimizerConfig,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    cell = StandaloneBDHCell(
        BDHCellConfig(
            width=task.width,
            rotary_pairs=pair_count,
            residual_scale=config.residual_scale,
            initialization_seed=config.seed + pair_count,
        ),
        uid=pair_count,
    ).to(device=device, dtype=dtype)
    optimizer = build_cell_optimizer(cell.parameters(), optimizer_config)
    initial_loss, final_training_loss = _train(
        cell,
        optimizer,
        task.training,
        steps=config.training_steps,
    )
    cell.eval()
    with torch.no_grad():
        evaluation_output = cell(
            task.evaluation.root_state,
            task.evaluation.attention_mask,
        )
        evaluation_loss = float(_masked_mse(evaluation_output, task.evaluation).cpu())

    low_rank = LowRankResidualControl.for_parameter_budget(
        width=task.width,
        budget=cell.parameter_count,
        residual_scale=config.residual_scale,
        initialization_seed=config.seed + 10_000 + pair_count,
    ).to(device=device, dtype=dtype)
    low_rank_optimizer = build_cell_optimizer(low_rank.parameters(), optimizer_config)
    low_rank_initial_loss, low_rank_final_training_loss = _train(
        low_rank,
        low_rank_optimizer,
        task.training,
        steps=config.training_steps,
    )
    low_rank.eval()
    with torch.no_grad():
        low_rank_evaluation_loss = float(
            _masked_mse(
                low_rank(task.evaluation.root_state, task.evaluation.attention_mask),
                task.evaluation,
            ).cpu()
        )

    batch_difference = batch_composition_max_difference(
        cell,
        task.evaluation.root_state,
        task.evaluation.attention_mask,
    )
    local_control = MaskedLocalBDHHeadControl.containing_cell(cell)
    local_masked_comparison = compare_masked_dense_cohort(
        local_control,
        task.evaluation.root_state,
        task.evaluation.attention_mask,
    )
    dense_control = MaskedDenseBDHHeadControl.containing_cell(cell)
    reference_dense_comparison = compare_masked_dense_cohort(
        dense_control,
        task.evaluation.root_state,
        task.evaluation.attention_mask,
    )

    with tempfile.TemporaryDirectory(prefix="ninereeds-36c-cell-") as directory:
        checkpoint_path = Path(directory) / "cell.pt"
        checkpoint_storage = save_cell_checkpoint(
            checkpoint_path,
            cell,
            optimizer,
            optimizer_config=optimizer_config,
            metadata={"purpose": "campaign36c_stage1_cold_restore"},
        )
        restored, restored_optimizer, restored_policy, restored_metadata = load_cell_checkpoint(
            checkpoint_path,
            device=device,
        )
        restored.eval()
        with torch.no_grad():
            restored_output = restored(
                task.evaluation.root_state,
                task.evaluation.attention_mask,
            )
        cold_restore_difference = float(
            (evaluation_output - restored_output).detach().abs().max().cpu()
        )
        resume_update_difference = _resume_update_difference(
            cell,
            optimizer,
            restored,
            restored_optimizer,
            task.training,
        )

    storage = cell.storage_telemetry()
    storage.update({
        "optimizer_tensor_bytes": tensor_storage_bytes(optimizer.state_dict()),
        "checkpoint_bytes": checkpoint_storage["checkpoint_bytes"],
    })
    forward_timing = _benchmark_forward_milliseconds(
        cell,
        task.evaluation,
        device=device,
        warmup=config.benchmark_warmup,
        iterations=config.benchmark_iterations,
    )
    low_rank_timing = _benchmark_forward_milliseconds(
        low_rank,
        task.evaluation,
        device=device,
        warmup=config.benchmark_warmup,
        iterations=config.benchmark_iterations,
    )
    mechanical_maximum = max(
        batch_difference,
        local_masked_comparison.maximum_difference,
        cold_restore_difference,
        resume_update_difference,
    )
    return {
        "rotary_pairs": pair_count,
        "cell": {
            "initial_training_mse": initial_loss,
            "final_training_mse": final_training_loss,
            "evaluation_mse": evaluation_loss,
            "forward_timing": forward_timing,
            "estimated_evaluation_forward_macs": cell.estimated_forward_macs(
                batch_size=task.evaluation.root_state.size(0),
                sequence_length=task.evaluation.root_state.size(1),
            ),
            "storage": storage,
        },
        "parameter_nearest_36b_residual_control": {
            "rank": low_rank.rank,
            "parameters": low_rank.parameter_count,
            "parameter_difference": low_rank.parameter_count - cell.parameter_count,
            "initial_training_mse": low_rank_initial_loss,
            "final_training_mse": low_rank_final_training_loss,
            "evaluation_mse": low_rank_evaluation_loss,
            "forward_timing": low_rank_timing,
            "estimated_evaluation_forward_macs": low_rank.estimated_forward_macs(
                batch_size=task.evaluation.root_state.size(0),
                sequence_length=task.evaluation.root_state.size(1),
            ),
        },
        "mechanics": {
            "batch_composition_max_abs": batch_difference,
            "masked_local_operator": dataclasses.asdict(local_masked_comparison),
            "reference_dense_bdh_difference": dataclasses.asdict(
                reference_dense_comparison
            ),
            "cold_restore_output_max_abs": cold_restore_difference,
            "resumed_update_parameter_max_abs": resume_update_difference,
            "optimizer_policy_restored": restored_policy == optimizer_config,
            "checkpoint_metadata_restored": restored_metadata
            == {"purpose": "campaign36c_stage1_cold_restore"},
            "maximum_difference": mechanical_maximum,
            "within_tolerance": mechanical_maximum <= config.mechanical_tolerance,
        },
    }


def _select_trials(
    trials: list[dict[str, Any]],
    *,
    no_cell_loss: float,
    extra_core_tick_loss: float | None,
    lab: CellLabConfig,
) -> dict[str, Any]:
    mechanically_valid = [
        trial
        for trial in trials
        if trial["mechanics"]["within_tolerance"]
        and trial["mechanics"]["optimizer_policy_restored"]
        and trial["mechanics"]["checkpoint_metadata_restored"]
    ]
    useful = [
        trial
        for trial in mechanically_valid
        if trial["comparisons"]["improvement_vs_no_cell_fraction"]
        >= lab.minimum_improvement_fraction
        and trial["comparisons"]["outperforms_parameter_nearest_36b_residual"]
        and (
            extra_core_tick_loss is None
            or trial["cell"]["evaluation_mse"] < extra_core_tick_loss
        )
    ]
    selected = useful[0] if useful else None
    exit_gate_met = selected is not None and extra_core_tick_loss is not None
    return {
        "status": (
            "stage1_exit_gate_met"
            if exit_gate_met
            else "provisional_candidate_missing_extra_core_tick"
            if selected is not None
            else "no_qualifying_candidate"
        ),
        "selected_rotary_pairs": (
            None if selected is None else selected["rotary_pairs"]
        ),
        "stage1_exit_gate_met": exit_gate_met,
        "missing_evidence": (
            ["equal_cost_extra_core_tick_control"]
            if selected is not None and extra_core_tick_loss is None
            else []
        ),
    }


def run_cell_laboratory(
    task: LatentTask,
    *,
    config: CellLabConfig | None = None,
    optimizer_config: CellOptimizerConfig | None = None,
    device: torch.device | str = "cpu",
    dtype: torch.dtype = torch.float32,
) -> dict[str, Any]:
    """Run the frozen Stage-1 cohort sweep without activating later 36C stages."""

    task.validate()
    lab = config or CellLabConfig()
    lab.validate()
    optimizer_policy = optimizer_config or CellOptimizerConfig()
    optimizer_policy.validate()
    execution_device = torch.device(device)
    resident_task = task.to(device=execution_device, dtype=dtype)
    with torch.no_grad():
        no_cell_loss = float(
            _masked_mse(_no_cell_output(resident_task.evaluation), resident_task.evaluation).cpu()
        )
        extra_core_tick_loss = (
            None
            if resident_task.extra_core_tick_evaluation is None
            else float(
                _masked_mse(
                    resident_task.extra_core_tick_evaluation,
                    resident_task.evaluation,
                ).cpu()
            )
        )
    trials = [
        _run_trial(
            pair_count=pair_count,
            task=resident_task,
            config=lab,
            optimizer_config=optimizer_policy,
            device=execution_device,
            dtype=dtype,
        )
        for pair_count in lab.pair_counts
    ]
    for trial in trials:
        cell_loss = trial["cell"]["evaluation_mse"]
        residual_loss = trial["parameter_nearest_36b_residual_control"][
            "evaluation_mse"
        ]
        trial["comparisons"] = {
            "improvement_vs_no_cell_fraction": (
                no_cell_loss - cell_loss
            ) / max(no_cell_loss, 1e-12),
            "outperforms_parameter_nearest_36b_residual": cell_loss < residual_loss,
            "outperforms_extra_core_tick": (
                None if extra_core_tick_loss is None else cell_loss < extra_core_tick_loss
            ),
        }
    selection = _select_trials(
        trials,
        no_cell_loss=no_cell_loss,
        extra_core_tick_loss=extra_core_tick_loss,
        lab=lab,
    )
    return {
        "schema_version": CAMPAIGN36C_CELL_LAB_RESULT_SCHEMA,
        "stage": "campaign36c_stage1_standalone_cell_laboratory",
        "task": {
            "width": resident_task.width,
            "training_shape": list(resident_task.training.root_state.shape),
            "evaluation_shape": list(resident_task.evaluation.root_state.shape),
            "metadata": resident_task.metadata,
        },
        "execution": {
            "device": str(execution_device),
            "dtype": str(dtype),
            "torch_version": torch.__version__,
            "cuda_device_name": (
                torch.cuda.get_device_name(execution_device)
                if execution_device.type == "cuda"
                else None
            ),
        },
        "lab_config": dataclasses.asdict(lab),
        "optimizer_config": dataclasses.asdict(optimizer_policy),
        "controls": {
            "no_cell_evaluation_mse": no_cell_loss,
            "extra_core_tick_evaluation_mse": extra_core_tick_loss,
            "extra_core_tick_available": extra_core_tick_loss is not None,
        },
        "trials": trials,
        "selection": selection,
    }


def merge_cell_lab_results(
    shards: list[dict[str, Any]],
    *,
    config: CellLabConfig,
) -> dict[str, Any]:
    """Merge independent device shards without averaging trial evidence."""

    config.validate()
    if not shards:
        raise ValueError("at least one cell-lab shard is required")
    first = shards[0]
    for shard in shards:
        if shard.get("schema_version") != CAMPAIGN36C_CELL_LAB_RESULT_SCHEMA:
            raise ValueError("cannot merge an unsupported cell-lab result")
        if shard["task"] != first["task"] or shard["controls"] != first["controls"]:
            raise ValueError("cell-lab shards do not describe the same task and controls")
        comparison = dict(shard["lab_config"])
        comparison.pop("pair_counts", None)
        expected = dataclasses.asdict(config)
        expected.pop("pair_counts", None)
        if comparison != expected:
            raise ValueError("cell-lab shards used different experiment policies")
        if shard["optimizer_config"] != first["optimizer_config"]:
            raise ValueError("cell-lab shards used different optimizer policies")
    trials = sorted(
        [trial for shard in shards for trial in shard["trials"]],
        key=lambda trial: trial["rotary_pairs"],
    )
    observed_pairs = tuple(trial["rotary_pairs"] for trial in trials)
    if observed_pairs != config.pair_counts:
        raise ValueError(
            f"cell-lab shards cover {observed_pairs}, expected {config.pair_counts}"
        )
    result = copy.deepcopy(first)
    result["execution"] = {
        "parallel_shards": len(shards),
        "devices": [shard["execution"] for shard in shards],
    }
    result["lab_config"] = dataclasses.asdict(config)
    result["trials"] = trials
    result["selection"] = _select_trials(
        trials,
        no_cell_loss=first["controls"]["no_cell_evaluation_mse"],
        extra_core_tick_loss=first["controls"]["extra_core_tick_evaluation_mse"],
        lab=config,
    )
    return result


def write_lab_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
