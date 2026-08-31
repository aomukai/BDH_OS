from __future__ import annotations

import dataclasses
import os
import uuid
from pathlib import Path
from typing import Any, Iterable

import torch

from .cell import StandaloneBDHCell
from .config import BDHCellConfig, CellOptimizerConfig


CAMPAIGN36C_CELL_CHECKPOINT_SCHEMA = "ninereeds_campaign36c_cell_checkpoint_v0"


def build_cell_optimizer(
    parameters: Iterable[torch.nn.Parameter],
    config: CellOptimizerConfig | None = None,
) -> torch.optim.AdamW:
    """Build the explicit UID-local full-moment optimizer used by Stage 1."""

    policy = config or CellOptimizerConfig()
    policy.validate()
    return torch.optim.AdamW(
        parameters,
        lr=policy.learning_rate,
        betas=policy.betas,
        eps=policy.epsilon,
        weight_decay=policy.weight_decay,
        amsgrad=policy.amsgrad,
    )


def tensor_storage_bytes(value: Any) -> int:
    """Count tensor payload bytes in an arbitrarily nested checkpoint value."""

    if isinstance(value, torch.Tensor):
        return value.numel() * value.element_size()
    if isinstance(value, dict):
        return sum(tensor_storage_bytes(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(tensor_storage_bytes(item) for item in value)
    return 0


def _dtype_name(dtype: torch.dtype) -> str:
    name = str(dtype)
    if not name.startswith("torch."):
        raise ValueError(f"unsupported torch dtype name: {name}")
    return name.removeprefix("torch.")


def _resolve_dtype(name: str) -> torch.dtype:
    dtype = getattr(torch, name, None)
    if not isinstance(dtype, torch.dtype):
        raise ValueError(f"unsupported checkpoint dtype: {name}")
    return dtype


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def save_cell_checkpoint(
    path: Path,
    cell: StandaloneBDHCell,
    optimizer: torch.optim.Optimizer,
    *,
    optimizer_config: CellOptimizerConfig,
    metadata: dict[str, Any] | None = None,
) -> dict[str, int | str]:
    """Atomically save one bounded Stage-1 experiment checkpoint.

    This is a laboratory checkpoint, not the one-file-per-cell storage design.
    Campaign 36C's scaled persistence stage must use packed records and segments.
    """

    optimizer_config.validate()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    parameter = next(cell.parameters())
    document = {
        "schema_version": CAMPAIGN36C_CELL_CHECKPOINT_SCHEMA,
        "uid": cell.uid,
        "cell_config": dataclasses.asdict(cell.config),
        "cell_state": cell.state_dict(),
        "parameter_dtype": _dtype_name(parameter.dtype),
        "optimizer_config": dataclasses.asdict(optimizer_config),
        "optimizer_state": optimizer.state_dict(),
        "torch_rng_state": torch.get_rng_state(),
        "cuda_rng_state": (
            torch.cuda.get_rng_state_all()
            if torch.cuda.is_available() and torch.cuda.is_initialized()
            else []
        ),
        "metadata": metadata or {},
    }
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as stream:
            torch.save(document, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {
        "schema_version": CAMPAIGN36C_CELL_CHECKPOINT_SCHEMA,
        "checkpoint_bytes": path.stat().st_size,
        "cell_parameter_bytes": tensor_storage_bytes(document["cell_state"]),
        "optimizer_tensor_bytes": tensor_storage_bytes(document["optimizer_state"]),
    }


def load_cell_checkpoint(
    path: Path,
    *,
    device: torch.device | str = "cpu",
    restore_rng: bool = False,
) -> tuple[
    StandaloneBDHCell,
    torch.optim.AdamW,
    CellOptimizerConfig,
    dict[str, Any],
]:
    """Cold-load cell parameters, buffers, UID, and UID-local optimizer state."""

    value = torch.load(path, map_location=device, weights_only=True)
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != CAMPAIGN36C_CELL_CHECKPOINT_SCHEMA
    ):
        raise ValueError("unsupported Campaign 36C cell checkpoint")
    config = BDHCellConfig(**value["cell_config"])
    dtype = _resolve_dtype(value["parameter_dtype"])
    cell = StandaloneBDHCell(config, uid=int(value["uid"])).to(
        device=device,
        dtype=dtype,
    )
    cell.load_state_dict(value["cell_state"], strict=True)
    optimizer_config = CellOptimizerConfig(**value["optimizer_config"])
    optimizer = build_cell_optimizer(cell.parameters(), optimizer_config)
    optimizer.load_state_dict(value["optimizer_state"])
    if restore_rng:
        torch.set_rng_state(value["torch_rng_state"].cpu())
        cuda_rng_state = value.get("cuda_rng_state", [])
        if cuda_rng_state and torch.cuda.is_available():
            torch.cuda.set_rng_state_all(cuda_rng_state)
    return cell, optimizer, optimizer_config, dict(value.get("metadata", {}))
