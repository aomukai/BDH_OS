from __future__ import annotations

import dataclasses
import math
from typing import Any, Iterable

import torch
import torch.nn.functional as F
from torch import nn

from .config import CellSubstrateConfig
from .growth import GrowthController, GrowthObservation


AMORPHOUS_SUBSTRATE_SCHEMA = "ninereeds_amorphous_substrate_v1"
CELL_STATUSES = {"provisional", "admitted", "dormant"}


class CellCohort(nn.Module):
    """A vectorized birth cohort of homogeneous low-rank residual cells."""

    def __init__(
        self,
        *,
        count: int,
        width: int,
        rank: int,
        cell_ids: tuple[int, ...],
        birth_seed: int,
        status: str,
    ) -> None:
        super().__init__()
        if count <= 0 or len(cell_ids) != count:
            raise ValueError("count and cell_ids must describe a non-empty cohort")
        if status not in CELL_STATUSES:
            raise ValueError(f"unsupported cell status: {status}")
        self.count = count
        self.width = width
        self.rank = rank
        self.cell_ids = cell_ids
        self.birth_seed = birth_seed
        self.status = status

        generator = torch.Generator(device="cpu")
        generator.manual_seed(birth_seed)
        ingress = torch.empty(count, width, rank)
        ingress.normal_(std=1.0 / math.sqrt(width), generator=generator)
        keys = torch.empty(count, width)
        keys.normal_(std=1.0 / math.sqrt(width), generator=generator)
        self.ingress = nn.Parameter(ingress)
        self.egress = nn.Parameter(torch.zeros(count, rank, width))
        self.keys = nn.Parameter(keys)
        self.bias = nn.Parameter(torch.zeros(count, rank))

    def set_status(self, status: str) -> None:
        if status not in CELL_STATUSES:
            raise ValueError(f"unsupported cell status: {status}")
        self.status = status
        self.requires_grad_(status != "dormant")

    def contribution(
        self,
        state: torch.Tensor,
        pooled: torch.Tensor,
        *,
        gate_temperature: float,
        provisional_scale: float,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if self.status == "dormant":
            raise RuntimeError("dormant cohorts must not execute")
        normalized_keys = F.normalize(self.keys, dim=-1)
        normalized_context = F.normalize(pooled, dim=-1)
        gates = torch.sigmoid(
            normalized_context @ normalized_keys.mT / gate_temperature
        )
        if self.status == "provisional":
            gates = gates * provisional_scale

        latent = torch.einsum("btd,cdr->btcr", state, self.ingress)
        latent = F.gelu(latent + self.bias.view(1, 1, self.count, self.rank))
        transformed = torch.einsum("btcr,crd->btcd", latent, self.egress)
        numerator = (transformed * gates[:, None, :, None]).sum(dim=2)
        denominator = gates.sum(dim=1).view(-1, 1, 1)
        return numerator, denominator, gates

    def manifest(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "cell_ids": list(self.cell_ids),
            "birth_seed": self.birth_seed,
            "status": self.status,
        }


class AmorphousSubstrate(nn.Module):
    """A growing population of cells operating on a shared latent workspace."""

    def __init__(
        self,
        config: CellSubstrateConfig | None = None,
        *,
        initialize_seed_population: bool = True,
    ) -> None:
        super().__init__()
        self.config = config or CellSubstrateConfig()
        self.config.validate()
        self.cohorts = nn.ModuleList()
        self.input_norm = nn.LayerNorm(
            self.config.width, elementwise_affine=False, bias=False
        )
        self.output_norm = nn.LayerNorm(
            self.config.width, elementwise_affine=False, bias=False
        )
        self.next_cell_id = 0
        self.birth_ordinal = 0
        if initialize_seed_population and self.config.seed_cells:
            self.add_cohort(
                self.config.seed_cells,
                status="admitted",
                birth_seed=self.config.initialization_seed,
            )

    @property
    def allocated_cells(self) -> int:
        return sum(cohort.count for cohort in self.cohorts)

    def _execution_device_and_dtype(self) -> tuple[torch.device, torch.dtype]:
        parameter = next(self.parameters(), None)
        if parameter is None:
            return torch.device("cpu"), torch.float32
        return parameter.device, parameter.dtype

    def add_cohort(
        self,
        count: int | None = None,
        *,
        status: str = "provisional",
        birth_seed: int | None = None,
        cell_ids: tuple[int, ...] | None = None,
    ) -> int:
        count = self.config.birth_cohort_size if count is None else count
        if count <= 0:
            raise ValueError("cohort count must be positive")
        if self.allocated_cells + count > self.config.max_cells:
            raise RuntimeError("cell allocation would exceed max_cells")
        if cell_ids is None:
            cell_ids = tuple(range(self.next_cell_id, self.next_cell_id + count))
        if len(set(cell_ids)) != count or min(cell_ids) < 0:
            raise ValueError("cell_ids must be unique non-negative identifiers")
        existing = {
            cell_id for cohort in self.cohorts for cell_id in cohort.cell_ids
        }
        if existing.intersection(cell_ids):
            raise ValueError("cell_ids must be globally unique")
        if birth_seed is None:
            birth_seed = self.config.initialization_seed + self.birth_ordinal

        device, dtype = self._execution_device_and_dtype()
        cohort = CellCohort(
            count=count,
            width=self.config.width,
            rank=self.config.rank,
            cell_ids=cell_ids,
            birth_seed=birth_seed,
            status=status,
        ).to(device=device, dtype=dtype)
        self.cohorts.append(cohort)
        self.next_cell_id = max(self.next_cell_id, max(cell_ids) + 1)
        self.birth_ordinal += 1
        return len(self.cohorts) - 1

    def consider_growth(
        self,
        controller: GrowthController,
        observation: GrowthObservation,
        *,
        optimizer: torch.optim.Optimizer | None = None,
    ) -> int | None:
        if not controller.observe(observation):
            return None
        cohort_index = self.add_cohort(status="provisional")
        if optimizer is not None:
            optimizer.add_param_group({
                "params": list(self.cohorts[cohort_index].parameters())
            })
        return cohort_index

    def set_cohort_status(self, cohort_index: int, status: str) -> None:
        self.cohorts[cohort_index].set_status(status)

    def trainable_parameters(self) -> Iterable[nn.Parameter]:
        return (parameter for parameter in self.parameters() if parameter.requires_grad)

    def anatomy(self) -> dict[str, int]:
        counts = {status: 0 for status in CELL_STATUSES}
        parameters = {status: 0 for status in CELL_STATUSES}
        for cohort in self.cohorts:
            counts[cohort.status] += cohort.count
            parameters[cohort.status] += sum(
                parameter.numel() for parameter in cohort.parameters()
            )
        return {
            "allocated_cells": self.allocated_cells,
            "allocated_cell_parameters": sum(parameters.values()),
            **{f"{status}_cells": counts[status] for status in sorted(counts)},
            **{
                f"{status}_cell_parameters": parameters[status]
                for status in sorted(parameters)
            },
        }

    def _pooled_state(
        self,
        state: torch.Tensor,
        attention_mask: torch.Tensor | None,
    ) -> torch.Tensor:
        if attention_mask is None:
            return state.mean(dim=1)
        if attention_mask.shape != state.shape[:2]:
            raise ValueError("attention_mask must match batch and sequence dimensions")
        mask = attention_mask.to(device=state.device, dtype=state.dtype).unsqueeze(-1)
        return (state * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)

    def forward(
        self,
        observations: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        *,
        collect_trace: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, dict[str, Any]]:
        if observations.ndim != 3 or observations.size(-1) != self.config.width:
            raise ValueError(
                "observations must have shape [batch, sequence, "
                f"{self.config.width}], got {tuple(observations.shape)}"
            )
        executable = [
            cohort for cohort in self.cohorts if cohort.status != "dormant"
        ]
        if not executable:
            raise RuntimeError("amorphous substrate has no executable cells")

        state = self.input_norm(observations)
        step_traces: list[dict[str, Any]] = []
        for step in range(self.config.propagation_steps):
            pooled = self._pooled_state(state, attention_mask)
            numerator = torch.zeros_like(state)
            denominator = torch.zeros(
                state.size(0), 1, 1, device=state.device, dtype=state.dtype
            )
            gate_values = []
            cell_ids = []
            for cohort in executable:
                contribution, cohort_denominator, gates = cohort.contribution(
                    state,
                    pooled,
                    gate_temperature=self.config.gate_temperature,
                    provisional_scale=self.config.provisional_scale,
                )
                numerator = numerator + contribution
                denominator = denominator + cohort_denominator
                if collect_trace:
                    gate_values.append(gates.detach().to(torch.float32).cpu())
                    cell_ids.extend(cohort.cell_ids)
            delta = numerator / denominator.clamp_min(1.0)
            state = self.output_norm(state + self.config.residual_scale * delta)

            if collect_trace:
                all_gates = torch.cat(gate_values, dim=1)
                step_traces.append({
                    "step": step + 1,
                    "cell_ids": list(cell_ids),
                    "mean_gate_by_cell": all_gates.mean(dim=0).tolist(),
                    "active_cells_by_example": (
                        all_gates >= self.config.activation_threshold
                    ).sum(dim=1).tolist(),
                    "mean_delta_abs": float(delta.detach().abs().mean().cpu()),
                })

        if not collect_trace:
            return state
        return state, {
            "schema_version": "ninereeds_amorphous_activation_trace_v1",
            "anatomy": self.anatomy(),
            "propagation_steps": self.config.propagation_steps,
            "steps": step_traces,
        }

    def checkpoint(
        self,
        *,
        growth_controller: GrowthController | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": AMORPHOUS_SUBSTRATE_SCHEMA,
            "config": dataclasses.asdict(self.config),
            "cohorts": [cohort.manifest() for cohort in self.cohorts],
            "next_cell_id": self.next_cell_id,
            "birth_ordinal": self.birth_ordinal,
            "model_state": self.state_dict(),
            "growth_controller": (
                growth_controller.state_dict()
                if growth_controller is not None
                else None
            ),
            "metadata": metadata or {},
        }

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint: dict[str, Any],
    ) -> tuple["AmorphousSubstrate", GrowthController | None]:
        if checkpoint.get("schema_version") != AMORPHOUS_SUBSTRATE_SCHEMA:
            raise ValueError("unsupported amorphous substrate checkpoint")
        model = cls(
            CellSubstrateConfig(**checkpoint["config"]),
            initialize_seed_population=False,
        )
        for manifest in checkpoint["cohorts"]:
            model.add_cohort(
                int(manifest["count"]),
                status=str(manifest["status"]),
                birth_seed=int(manifest["birth_seed"]),
                cell_ids=tuple(int(value) for value in manifest["cell_ids"]),
            )
        model.load_state_dict(checkpoint["model_state"], strict=True)
        model.next_cell_id = int(checkpoint["next_cell_id"])
        model.birth_ordinal = int(checkpoint["birth_ordinal"])
        controller_state = checkpoint.get("growth_controller")
        controller = (
            GrowthController.from_state_dict(controller_state)
            if controller_state is not None
            else None
        )
        return model, controller
