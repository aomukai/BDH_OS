from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Sequence
from typing import NamedTuple

import torch
import torch.nn.functional as F
from torch import nn

from .config import BDHCellConfig


class CellTransform(NamedTuple):
    """One cell-local nudge and the quantities needed by the Stage-1 lab."""

    state: torch.Tensor
    delta: torch.Tensor
    gates: torch.Tensor
    attention_scores: torch.Tensor


@dataclass(frozen=True)
class MaskedDenseComparison:
    output_max_abs: float
    input_gradient_max_abs: float
    encoder_gradient_max_abs: float
    value_encoder_gradient_max_abs: float
    decoder_gradient_max_abs: float
    inactive_gradient_max_abs: float

    @property
    def maximum_difference(self) -> float:
        return max(
            self.output_max_abs,
            self.input_gradient_max_abs,
            self.encoder_gradient_max_abs,
            self.value_encoder_gradient_max_abs,
            self.decoder_gradient_max_abs,
            self.inactive_gradient_max_abs,
        )


def paired_rotary_frequencies(
    gate_width: int,
    *,
    theta: float,
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    """Return BDH frequencies with adjacent even/odd gates kept as one atom."""

    if gate_width <= 0 or gate_width % 2:
        raise ValueError("gate_width must be a positive even number")
    positions = torch.arange(gate_width, dtype=dtype)
    paired_positions = torch.floor(positions / 2) * 2
    return 1.0 / (theta ** (paired_positions / gate_width)) / (2 * math.pi)


def _rope(frequencies: torch.Tensor, values: torch.Tensor) -> torch.Tensor:
    sequence_length = values.size(-2)
    phases = (
        torch.arange(
            sequence_length,
            device=values.device,
            dtype=frequencies.dtype,
        ).view(1, sequence_length, 1)
        * frequencies.to(values.device).view(1, 1, -1)
    )
    phases = (phases % 1) * (2 * math.pi)
    rotated = torch.stack(
        (-values[..., 1::2], values[..., ::2]), dim=-1
    ).reshape_as(values)
    return (
        values * torch.cos(phases).to(values.dtype)
        + rotated * torch.sin(phases).to(values.dtype)
    )


def _batched_rope(frequencies: torch.Tensor, values: torch.Tensor) -> torch.Tensor:
    """Apply independent rotary buffers to ``[cell,batch,token,gate]`` values."""

    sequence_length = values.size(-2)
    phases = (
        torch.arange(
            sequence_length,
            device=values.device,
            dtype=frequencies.dtype,
        ).view(1, 1, sequence_length, 1)
        * frequencies.to(values.device).view(frequencies.size(0), 1, 1, -1)
    )
    phases = (phases % 1) * (2 * math.pi)
    rotated = torch.stack(
        (-values[..., 1::2], values[..., ::2]), dim=-1
    ).reshape_as(values)
    return (
        values * torch.cos(phases).to(values.dtype)
        + rotated * torch.sin(phases).to(values.dtype)
    )


def _validate_state(
    state: torch.Tensor,
    *,
    width: int,
    attention_mask: torch.Tensor | None,
) -> torch.Tensor | None:
    if state.ndim != 3 or state.size(-1) != width:
        raise ValueError(
            f"state must have shape [batch, sequence, {width}], "
            f"got {tuple(state.shape)}"
        )
    if attention_mask is None:
        return None
    if attention_mask.shape != state.shape[:2]:
        raise ValueError("attention_mask must match batch and sequence dimensions")
    return attention_mask.to(device=state.device, dtype=torch.bool)


def _local_bdh_transform(
    state: torch.Tensor,
    *,
    encoder: torch.Tensor,
    value_encoder: torch.Tensor,
    decoder: torch.Tensor,
    rotary_frequencies: torch.Tensor,
    residual_scale: float,
    normalization_epsilon: float,
    attention_mask: torch.Tensor | None,
    gate_mask: torch.Tensor | None = None,
) -> CellTransform:
    valid = _validate_state(
        state,
        width=encoder.size(0),
        attention_mask=attention_mask,
    )
    normalized = F.layer_norm(
        state,
        (state.size(-1),),
        eps=normalization_epsilon,
    )
    q = F.relu(normalized @ encoder)
    if gate_mask is not None:
        q = q * gate_mask.to(device=q.device, dtype=q.dtype)
    if valid is not None:
        q = q * valid.unsqueeze(-1)

    q_rotary = _rope(rotary_frequencies, q)
    scores = torch.tril(q_rotary @ q_rotary.mT, diagonal=-1)
    if valid is not None:
        pair_mask = valid.unsqueeze(-1) & valid.unsqueeze(-2)
        scores = scores * pair_mask.to(scores.dtype)

    context = F.layer_norm(
        scores @ state,
        (state.size(-1),),
        eps=normalization_epsilon,
    )
    r = F.relu(context @ value_encoder)
    if gate_mask is not None:
        r = r * gate_mask.to(device=r.device, dtype=r.dtype)
    if valid is not None:
        r = r * valid.unsqueeze(-1)

    gates = q * r
    delta = gates @ decoder
    if valid is not None:
        delta = delta * valid.unsqueeze(-1)
    next_state = F.layer_norm(
        state + residual_scale * delta,
        (state.size(-1),),
        eps=normalization_epsilon,
    )
    if valid is not None:
        next_state = torch.where(valid.unsqueeze(-1), next_state, state)
    return CellTransform(next_state, delta, gates, scores)


class StandaloneBDHCell(nn.Module):
    """An independently stored, head-local BDH-derived Campaign 36C cell.

    This is intentionally not a view into the 1.2B Cortex tensors.  Its
    normalization, temporal attention, parameters, buffers, and optimizer
    ownership are local to one UID.
    """

    def __init__(
        self,
        config: BDHCellConfig | None = None,
        *,
        uid: int,
    ) -> None:
        super().__init__()
        self.config = config or BDHCellConfig()
        self.config.validate()
        if uid < 0:
            raise ValueError("uid must be a non-negative never-reused identifier")
        self.uid = int(uid)

        generator = torch.Generator(device="cpu")
        generator.manual_seed(self.config.initialization_seed)
        width = self.config.width
        gate_width = self.config.gate_width
        self.encoder = nn.Parameter(torch.empty(width, gate_width))
        self.value_encoder = nn.Parameter(torch.empty(width, gate_width))
        self.decoder = nn.Parameter(torch.empty(gate_width, width))
        with torch.no_grad():
            self.encoder.normal_(std=0.02, generator=generator)
            self.value_encoder.normal_(std=0.02, generator=generator)
            self.decoder.normal_(std=0.02, generator=generator)
        self.register_buffer(
            "rotary_frequencies",
            paired_rotary_frequencies(
                gate_width,
                theta=self.config.rope_theta,
            ),
            persistent=True,
        )

    @property
    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    def transform(
        self,
        state: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> CellTransform:
        return _local_bdh_transform(
            state,
            encoder=self.encoder,
            value_encoder=self.value_encoder,
            decoder=self.decoder,
            rotary_frequencies=self.rotary_frequencies,
            residual_scale=self.config.residual_scale,
            normalization_epsilon=self.config.normalization_epsilon,
            attention_mask=attention_mask,
        )

    def forward(
        self,
        state: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        return self.transform(state, attention_mask).state

    def estimated_forward_macs(self, *, batch_size: int, sequence_length: int) -> int:
        if batch_size <= 0 or sequence_length <= 0:
            raise ValueError("batch_size and sequence_length must be positive")
        width = self.config.width
        gates = self.config.gate_width
        per_item = (
            3 * sequence_length * width * gates
            + sequence_length * sequence_length * (gates + width)
        )
        return batch_size * per_item

    def storage_telemetry(self) -> dict[str, int | str]:
        parameter_bytes = sum(
            parameter.numel() * parameter.element_size()
            for parameter in self.parameters()
        )
        buffer_bytes = sum(
            buffer.numel() * buffer.element_size()
            for buffer in self.buffers()
        )
        return {
            "uid": self.uid,
            "cell_abi": self.config.cell_abi,
            "latent_abi": self.config.latent_abi,
            "rotary_pairs": self.config.rotary_pairs,
            "gate_width": self.config.gate_width,
            "parameters": self.parameter_count,
            "parameter_bytes": parameter_bytes,
            "persistent_buffer_bytes": buffer_bytes,
        }


def batched_cell_transform(
    cells: Sequence[StandaloneBDHCell],
    states: torch.Tensor,
    attention_masks: torch.Tensor | None = None,
) -> CellTransform:
    """Execute a homogeneous set of active UIDs without per-cell dispatch.

    ``states`` is ``[active_uid,batch,token,width]``.  Only parameters from
    ``cells`` are gathered, so inactive tissue allocates no activation tensors
    and cannot accidentally enter autograd.
    """

    if not cells:
        raise ValueError("at least one active cell is required")
    first = cells[0]
    if states.ndim != 4 or states.size(0) != len(cells):
        raise ValueError("states must have shape [active_uid,batch,token,width]")
    if states.size(-1) != first.config.width:
        raise ValueError("state width does not match cell width")
    signature = (
        first.config.width,
        first.config.gate_width,
        first.config.residual_scale,
        first.config.normalization_epsilon,
    )
    for cell in cells:
        candidate = (
            cell.config.width,
            cell.config.gate_width,
            cell.config.residual_scale,
            cell.config.normalization_epsilon,
        )
        if candidate != signature:
            raise ValueError("batched cells must have the same mechanical shape")
        if cell.encoder.device != states.device or cell.encoder.dtype != states.dtype:
            raise ValueError("batched cells and states must share device and dtype")

    valid: torch.Tensor | None = None
    if attention_masks is not None:
        if attention_masks.ndim == 2:
            attention_masks = attention_masks.unsqueeze(0).expand(
                len(cells), -1, -1
            )
        if attention_masks.shape != states.shape[:3]:
            raise ValueError("attention_masks must match active UID, batch, and token")
        valid = attention_masks.to(device=states.device, dtype=torch.bool)

    encoders = torch.stack([cell.encoder for cell in cells])
    value_encoders = torch.stack([cell.value_encoder for cell in cells])
    decoders = torch.stack([cell.decoder for cell in cells])
    frequencies = torch.stack([cell.rotary_frequencies for cell in cells])
    normalized = F.layer_norm(
        states,
        (states.size(-1),),
        eps=first.config.normalization_epsilon,
    )
    q = F.relu(torch.einsum("nbtd,ndg->nbtg", normalized, encoders))
    if valid is not None:
        q = q * valid.unsqueeze(-1)
    q_rotary = _batched_rope(frequencies, q)
    scores = torch.tril(q_rotary @ q_rotary.mT, diagonal=-1)
    if valid is not None:
        pair_mask = valid.unsqueeze(-1) & valid.unsqueeze(-2)
        scores = scores * pair_mask.to(scores.dtype)
    context = F.layer_norm(
        scores @ states,
        (states.size(-1),),
        eps=first.config.normalization_epsilon,
    )
    r = F.relu(torch.einsum("nbtd,ndg->nbtg", context, value_encoders))
    if valid is not None:
        r = r * valid.unsqueeze(-1)
    gates = q * r
    delta = torch.einsum("nbtg,ngd->nbtd", gates, decoders)
    if valid is not None:
        delta = delta * valid.unsqueeze(-1)
    next_state = F.layer_norm(
        states + first.config.residual_scale * delta,
        (states.size(-1),),
        eps=first.config.normalization_epsilon,
    )
    if valid is not None:
        next_state = torch.where(valid.unsqueeze(-1), next_state, states)
    return CellTransform(next_state, delta, gates, scores)


class MaskedLocalBDHHeadControl(nn.Module):
    """Local-operator gate bank with all but one aligned cohort masked off.

    This proves that unrelated zeroed slots do not change the new local
    operator.  ``MaskedDenseBDHHeadControl`` below separately preserves the
    current dense BDH layer's normalization and residual semantics.
    """

    def __init__(
        self,
        *,
        width: int,
        rotary_pairs: int,
        active_pair_start: int,
        active_pair_count: int,
        residual_scale: float = 0.25,
        rope_theta: float = float(2**16),
        normalization_epsilon: float = 1e-5,
        initialization_seed: int = 36_004,
    ) -> None:
        super().__init__()
        if width <= 0 or rotary_pairs <= 0:
            raise ValueError("width and rotary_pairs must be positive")
        if active_pair_start < 0 or active_pair_count <= 0:
            raise ValueError("the active aligned cohort must be non-empty")
        if active_pair_start + active_pair_count > rotary_pairs:
            raise ValueError("active aligned cohort lies outside the dense head")
        self.width = width
        self.rotary_pairs = rotary_pairs
        self.active_pair_start = active_pair_start
        self.active_pair_count = active_pair_count
        self.residual_scale = residual_scale
        self.rope_theta = rope_theta
        self.normalization_epsilon = normalization_epsilon

        gates = 2 * rotary_pairs
        generator = torch.Generator(device="cpu")
        generator.manual_seed(initialization_seed)
        self.encoder = nn.Parameter(torch.empty(width, gates))
        self.value_encoder = nn.Parameter(torch.empty(width, gates))
        self.decoder = nn.Parameter(torch.empty(gates, width))
        with torch.no_grad():
            self.encoder.normal_(std=0.02, generator=generator)
            self.value_encoder.normal_(std=0.02, generator=generator)
            self.decoder.normal_(std=0.02, generator=generator)
        self.register_buffer(
            "rotary_frequencies",
            paired_rotary_frequencies(gates, theta=rope_theta),
            persistent=True,
        )
        gate_mask = torch.zeros(gates)
        gate_mask[self.active_gate_slice] = 1
        self.register_buffer("gate_mask", gate_mask, persistent=False)

    @property
    def active_gate_slice(self) -> slice:
        return slice(
            2 * self.active_pair_start,
            2 * (self.active_pair_start + self.active_pair_count),
        )

    @classmethod
    def containing_cell(
        cls,
        cell: StandaloneBDHCell,
        *,
        prefix_pairs: int = 1,
        suffix_pairs: int = 1,
    ) -> "MaskedLocalBDHHeadControl":
        if prefix_pairs < 0 or suffix_pairs < 0:
            raise ValueError("prefix_pairs and suffix_pairs must be non-negative")
        control = cls(
            width=cell.config.width,
            rotary_pairs=prefix_pairs + cell.config.rotary_pairs + suffix_pairs,
            active_pair_start=prefix_pairs,
            active_pair_count=cell.config.rotary_pairs,
            residual_scale=cell.config.residual_scale,
            rope_theta=cell.config.rope_theta,
            normalization_epsilon=cell.config.normalization_epsilon,
            initialization_seed=cell.config.initialization_seed + 1,
        ).to(device=cell.encoder.device, dtype=cell.encoder.dtype)
        active = control.active_gate_slice
        with torch.no_grad():
            control.encoder[:, active].copy_(cell.encoder)
            control.value_encoder[:, active].copy_(cell.value_encoder)
            control.decoder[active, :].copy_(cell.decoder)
            control.rotary_frequencies[active].copy_(cell.rotary_frequencies)
        return control

    def transform(
        self,
        state: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> CellTransform:
        return _local_bdh_transform(
            state,
            encoder=self.encoder,
            value_encoder=self.value_encoder,
            decoder=self.decoder,
            rotary_frequencies=self.rotary_frequencies,
            residual_scale=self.residual_scale,
            normalization_epsilon=self.normalization_epsilon,
            attention_mask=attention_mask,
            gate_mask=self.gate_mask,
        )

    def forward(
        self,
        state: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        return self.transform(state, attention_mask).state

    def export_active_cell(self, *, uid: int) -> StandaloneBDHCell:
        config = BDHCellConfig(
            width=self.width,
            rotary_pairs=self.active_pair_count,
            residual_scale=self.residual_scale,
            rope_theta=self.rope_theta,
            normalization_epsilon=self.normalization_epsilon,
        )
        cell = StandaloneBDHCell(config, uid=uid).to(
            device=self.encoder.device,
            dtype=self.encoder.dtype,
        )
        active = self.active_gate_slice
        with torch.no_grad():
            cell.encoder.copy_(self.encoder[:, active])
            cell.value_encoder.copy_(self.value_encoder[:, active])
            cell.decoder.copy_(self.decoder[active, :])
            cell.rotary_frequencies.copy_(self.rotary_frequencies[active])
        return cell


class MaskedDenseBDHHeadControl(MaskedLocalBDHHeadControl):
    """One current-BDH head with every unrelated aligned cohort masked off.

    Unlike the independent candidate, the existing dense layer normalizes its
    incoming value path, normalizes the decoded update, and applies an unscaled
    residual.  The resulting difference is evidence, not a failed invariance.
    """

    def transform(
        self,
        state: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> CellTransform:
        valid = _validate_state(
            state,
            width=self.width,
            attention_mask=attention_mask,
        )
        normalized = F.layer_norm(
            state,
            (self.width,),
            eps=self.normalization_epsilon,
        )
        q = F.relu(normalized @ self.encoder)
        q = q * self.gate_mask.to(device=q.device, dtype=q.dtype)
        if valid is not None:
            q = q * valid.unsqueeze(-1)
        q_rotary = _rope(self.rotary_frequencies, q)
        scores = torch.tril(q_rotary @ q_rotary.mT, diagonal=-1)
        if valid is not None:
            pair_mask = valid.unsqueeze(-1) & valid.unsqueeze(-2)
            scores = scores * pair_mask.to(scores.dtype)
        context = F.layer_norm(
            scores @ normalized,
            (self.width,),
            eps=self.normalization_epsilon,
        )
        r = F.relu(context @ self.value_encoder)
        r = r * self.gate_mask.to(device=r.device, dtype=r.dtype)
        if valid is not None:
            r = r * valid.unsqueeze(-1)
        gates = q * r
        delta = gates @ self.decoder
        decoded = F.layer_norm(
            delta,
            (self.width,),
            eps=self.normalization_epsilon,
        )
        next_state = F.layer_norm(
            normalized + decoded,
            (self.width,),
            eps=self.normalization_epsilon,
        )
        if valid is not None:
            delta = delta * valid.unsqueeze(-1)
            next_state = torch.where(valid.unsqueeze(-1), next_state, state)
        return CellTransform(next_state, delta, gates, scores)


class LowRankResidualControl(nn.Module):
    """Parameter-nearest version of the Campaign 36B residual-cell control."""

    def __init__(
        self,
        *,
        width: int,
        rank: int,
        residual_scale: float = 0.25,
        initialization_seed: int = 36_005,
    ) -> None:
        super().__init__()
        if width <= 0 or not 0 < rank <= width:
            raise ValueError("rank must be positive and no greater than width")
        self.width = width
        self.rank = rank
        self.residual_scale = residual_scale
        generator = torch.Generator(device="cpu")
        generator.manual_seed(initialization_seed)
        self.ingress = nn.Parameter(torch.empty(width, rank))
        self.egress = nn.Parameter(torch.zeros(rank, width))
        self.key = nn.Parameter(torch.empty(width))
        self.bias = nn.Parameter(torch.zeros(rank))
        with torch.no_grad():
            self.ingress.normal_(std=1 / math.sqrt(width), generator=generator)
            self.key.normal_(std=1 / math.sqrt(width), generator=generator)

    @property
    def parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())

    @staticmethod
    def parameter_count_for(*, width: int, rank: int) -> int:
        return 2 * width * rank + width + rank

    @classmethod
    def rank_for_parameter_budget(cls, *, width: int, budget: int) -> int:
        if width <= 0 or budget <= 0:
            raise ValueError("width and budget must be positive")
        estimate = (budget - width) / (2 * width + 1)
        candidates = {
            max(1, min(width, int(math.floor(estimate)))),
            max(1, min(width, int(math.ceil(estimate)))),
        }
        return min(
            candidates,
            key=lambda rank: (
                abs(cls.parameter_count_for(width=width, rank=rank) - budget),
                rank,
            ),
        )

    @classmethod
    def for_parameter_budget(
        cls,
        *,
        width: int,
        budget: int,
        residual_scale: float = 0.25,
        initialization_seed: int = 36_005,
    ) -> "LowRankResidualControl":
        return cls(
            width=width,
            rank=cls.rank_for_parameter_budget(width=width, budget=budget),
            residual_scale=residual_scale,
            initialization_seed=initialization_seed,
        )

    def forward(
        self,
        state: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        valid = _validate_state(
            state,
            width=self.width,
            attention_mask=attention_mask,
        )
        normalized = F.layer_norm(state, (self.width,))
        if valid is None:
            pooled = normalized.mean(dim=1)
        else:
            weights = valid.to(normalized.dtype).unsqueeze(-1)
            pooled = (normalized * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1)
        gate = torch.sigmoid(
            F.cosine_similarity(pooled, self.key.unsqueeze(0), dim=-1)
        )
        hidden = F.gelu(normalized @ self.ingress + self.bias)
        delta = (hidden @ self.egress) * gate.view(-1, 1, 1)
        if valid is not None:
            delta = delta * valid.unsqueeze(-1)
        output = F.layer_norm(state + self.residual_scale * delta, (self.width,))
        if valid is not None:
            output = torch.where(valid.unsqueeze(-1), output, state)
        return output

    def estimated_forward_macs(self, *, batch_size: int, sequence_length: int) -> int:
        if batch_size <= 0 or sequence_length <= 0:
            raise ValueError("batch_size and sequence_length must be positive")
        return batch_size * 2 * sequence_length * self.width * self.rank


def compare_masked_dense_cohort(
    control: MaskedLocalBDHHeadControl,
    state: torch.Tensor,
    attention_mask: torch.Tensor | None = None,
) -> MaskedDenseComparison:
    """Compare output and gradients of a masked gate bank and its cell copy."""

    control.zero_grad(set_to_none=True)
    cell = control.export_active_cell(uid=0)
    cell.zero_grad(set_to_none=True)
    dense_input = state.detach().clone().requires_grad_(True)
    cell_input = state.detach().clone().requires_grad_(True)
    dense_output = control(dense_input, attention_mask)
    cell_output = cell(cell_input, attention_mask)
    probe = torch.linspace(
        0.5,
        1.5,
        dense_output.numel(),
        device=dense_output.device,
        dtype=dense_output.dtype,
    ).reshape_as(dense_output)
    (dense_output * probe).sum().backward()
    (cell_output * probe).sum().backward()

    active = control.active_gate_slice
    inactive = torch.ones(
        2 * control.rotary_pairs,
        dtype=torch.bool,
        device=control.encoder.device,
    )
    inactive[active] = False

    def difference(left: torch.Tensor, right: torch.Tensor) -> float:
        return float((left - right).detach().abs().max().cpu())

    inactive_gradients = torch.cat((
        control.encoder.grad[:, inactive].reshape(-1),
        control.value_encoder.grad[:, inactive].reshape(-1),
        control.decoder.grad[inactive, :].reshape(-1),
    ))
    return MaskedDenseComparison(
        output_max_abs=difference(dense_output, cell_output),
        input_gradient_max_abs=difference(dense_input.grad, cell_input.grad),
        encoder_gradient_max_abs=difference(
            control.encoder.grad[:, active], cell.encoder.grad
        ),
        value_encoder_gradient_max_abs=difference(
            control.value_encoder.grad[:, active], cell.value_encoder.grad
        ),
        decoder_gradient_max_abs=difference(
            control.decoder.grad[active, :], cell.decoder.grad
        ),
        inactive_gradient_max_abs=float(
            inactive_gradients.detach().abs().max().cpu()
            if inactive_gradients.numel()
            else 0.0
        ),
    )


def batch_composition_max_difference(
    cell: StandaloneBDHCell,
    state: torch.Tensor,
    attention_mask: torch.Tensor | None = None,
) -> float:
    """Measure whether unrelated batch peers change one UID's mathematical result."""

    with torch.no_grad():
        together = cell(state, attention_mask)
        separate = torch.cat(
            [
                cell(
                    state[index : index + 1],
                    None
                    if attention_mask is None
                    else attention_mask[index : index + 1],
                )
                for index in range(state.size(0))
            ],
            dim=0,
        )
    return float((together - separate).detach().abs().max().cpu())
