"""Bounded, read-only observation of Ninereeds gate credit and optimizer movement."""

from __future__ import annotations

import math
from typing import Any

import torch


SCHEMA_VERSION = "ninereeds_gate_credit_diagnostics_v1"
OPTIMIZER_DIAGNOSTIC_CHUNK_ELEMENTS = 1 << 20


def _number(value: torch.Tensor) -> float:
    return float(value.detach().to(torch.float32).cpu())


def vector_alignment(activity: torch.Tensor, gradient: torch.Tensor) -> dict[str, Any]:
    """Summarize ``activity`` against the local descent direction ``-gradient``."""

    h = activity.detach().to(torch.float32)
    g = gradient.detach().to(torch.float32)
    h_norm = torch.linalg.vector_norm(h)
    g_norm = torch.linalg.vector_norm(g)
    dot = torch.sum(h * -g)
    denominator = h_norm * g_norm
    cosine = None if _number(denominator) == 0.0 else _number(dot / denominator)
    active = h != 0
    active_count = int(active.sum().detach().cpu())
    if active_count:
        pressure = -g[active]
        strengthening = _number((pressure > 0).to(torch.float32).mean())
        suppressing = _number((pressure < 0).to(torch.float32).mean())
    else:
        strengthening = None
        suppressing = None
    return {
        "gradient_finite_fraction": _number(torch.isfinite(g).to(torch.float32).mean()),
        "gradient_positive_fraction": _number((g > 0).to(torch.float32).mean()),
        "gradient_negative_fraction": _number((g < 0).to(torch.float32).mean()),
        "gradient_zero_fraction": _number((g == 0).to(torch.float32).mean()),
        "gradient_mean_abs": _number(g.abs().mean()),
        "gradient_rms": _number(g.square().mean().sqrt()),
        "gradient_to_gate_norm_ratio": (
            None if _number(h_norm) == 0.0 else _number(g_norm / h_norm)
        ),
        "gate_credit_dot": _number(dot),
        "gate_credit_cosine": cosine,
        "alignment_status": "insufficient_signal" if cosine is None else "measured",
        "first_order_removal_delta_loss": _number(dot),
        "active_strengthening_fraction": strengthening,
        "active_suppressing_fraction": suppressing,
    }


def _forward_stats(tensor: torch.Tensor) -> dict[str, Any]:
    value = tensor.detach().to(torch.float32)
    return {
        "element_count": value.numel(),
        "density": _number((value != 0).to(torch.float32).mean()),
        "zero_fraction": _number((value == 0).to(torch.float32).mean()),
        "mean": _number(value.mean()),
        "mean_abs": _number(value.abs().mean()),
        "rms": _number(value.square().mean().sqrt()),
        "variance": _number(value.var(unbiased=False)),
        "finite_fraction": _number(torch.isfinite(value).to(torch.float32).mean()),
    }


def _parameter_family(name: str) -> str:
    if name.startswith("core.encoder_v"):
        return "core.encoder_v"
    if name.startswith("core.encoder"):
        return "core.encoder"
    if name.startswith("core.decoder"):
        return "core.decoder"
    if name.startswith("ingress.projector"):
        return "ingress_projector"
    if name.startswith("intention"):
        return "intention"
    if name.startswith("expression.projector"):
        return "expression_projector"
    if name.startswith("visual_resampler") or name.startswith("resampler"):
        return "visual_resampler"
    return "other_trainable"


def _optimizer_update_stats(
    parameter: torch.Tensor,
    gradient: torch.Tensor,
    update: torch.Tensor,
    learning_rate: float,
) -> dict[str, float | int | None]:
    """Measure an optimizer update without materializing full-size FP32 copies.

    Merged Cortex tensors can be hundreds of millions of elements.  Converting
    a whole BF16 gradient, update, and parameter to FP32 at once makes a
    read-only observer consume enough temporary VRAM to stop training.  The
    scalar reduction is algebraically identical when accumulated over bounded
    flat chunks, while peak observer storage stays independent of tensor size.
    """
    flat_parameter = parameter.detach().reshape(-1)
    flat_gradient = gradient.detach().reshape(-1)
    flat_update = update.detach().reshape(-1)
    count = flat_gradient.numel()
    grad_abs_sum = 0.0
    grad_square_sum = 0.0
    update_square_sum = 0.0
    parameter_square_sum = 0.0
    grad_update_dot = 0.0
    nonfinite_count = 0
    for start in range(0, count, OPTIMIZER_DIAGNOSTIC_CHUNK_ELEMENTS):
        stop = min(start + OPTIMIZER_DIAGNOSTIC_CHUNK_ELEMENTS, count)
        grad = flat_gradient[start:stop].to(torch.float32)
        update_value = flat_update[start:stop].to(torch.float32)
        parameter_value = flat_parameter[start:stop].to(torch.float32)
        grad_abs_sum += float(torch.sum(torch.abs(grad)).detach().cpu())
        grad_norm = float(torch.linalg.vector_norm(grad).detach().cpu())
        update_norm = float(torch.linalg.vector_norm(update_value).detach().cpu())
        parameter_norm = float(torch.linalg.vector_norm(parameter_value).detach().cpu())
        grad_square_sum += grad_norm * grad_norm
        update_square_sum += update_norm * update_norm
        parameter_square_sum += parameter_norm * parameter_norm
        grad_update_dot += float(torch.dot(grad, update_value).detach().cpu())
        nonfinite_count += int((~torch.isfinite(grad)).sum().detach().cpu())

    gradient_norm = math.sqrt(grad_square_sum)
    optimizer_update_norm = math.sqrt(update_square_sum)
    parameter_norm = math.sqrt(parameter_square_sum)
    movement_norm = optimizer_update_norm * learning_rate
    denominator = gradient_norm * optimizer_update_norm
    return {
        "gradient_mean_abs": grad_abs_sum / count if count else 0.0,
        "gradient_rms": math.sqrt(grad_square_sum / count) if count else 0.0,
        "gradient_norm": gradient_norm,
        "nonfinite_gradient_count": nonfinite_count,
        "optimizer_update_norm_before_lr": optimizer_update_norm,
        "intended_movement_norm": movement_norm,
        "descent_to_optimizer_movement_cosine": (
            None if denominator == 0.0 else grad_update_dot / denominator
        ),
        "update_to_parameter_norm_ratio": (
            None if parameter_norm == 0.0 else movement_norm / parameter_norm
        ),
    }


class GateCreditRecorder:
    """Collect scalar evidence for selected steps without mutating model state."""

    def __init__(self, *, log_every_n_steps: int, max_sampled_steps: int) -> None:
        if log_every_n_steps < 1 or max_sampled_steps < 1:
            raise ValueError("gate-credit bounds must be positive")
        self.log_every_n_steps = log_every_n_steps
        self.max_sampled_steps = max_sampled_steps
        self.records: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None

    def should_sample(self, step: int) -> bool:
        return (
            len(self.records) < self.max_sampled_steps
            and (step == 1 or step % self.log_every_n_steps == 0)
        )

    def begin_step(self, step: int, *, epoch: int, source_metadata: list[dict[str, Any]]) -> bool:
        if not self.should_sample(step):
            self._current = None
            return False
        self._current = {
            "step": step,
            "epoch": epoch,
            "source_metadata": source_metadata,
            "layers": [],
            "parameter_updates": [],
        }
        return True

    def observe_gate(
        self, *, layer: int, tick: int, raw_gate: torch.Tensor,
        effective_gate: torch.Tensor,
    ) -> None:
        current = self._current
        if current is None:
            return
        record = {
            "layer": layer,
            "tick": tick,
            "raw_gate": _forward_stats(raw_gate),
            "effective_gate": _forward_stats(effective_gate),
            "raw_gate_credit": None,
            "effective_gate_credit": None,
        }
        current["layers"].append(record)

        def raw_hook(gradient: torch.Tensor) -> torch.Tensor:
            record["raw_gate_credit"] = vector_alignment(raw_gate, gradient)
            return gradient

        def effective_hook(gradient: torch.Tensor) -> torch.Tensor:
            record["effective_gate_credit"] = vector_alignment(effective_gate, gradient)
            return gradient

        raw_gate.register_hook(raw_hook)
        effective_gate.register_hook(effective_hook)

    def observe_optimizer_update(
        self, name: str, parameter: torch.Tensor, gradient: torch.Tensor,
        update: torch.Tensor, learning_rate: float,
    ) -> None:
        if self._current is None:
            return
        statistics = _optimizer_update_stats(
            parameter, gradient, update, learning_rate,
        )
        self.observe_optimizer_update_statistics(
            name, parameter.numel(), statistics,
        )

    def observe_optimizer_update_statistics(
        self, name: str, parameter_count: int,
        statistics: dict[str, float | int | None],
    ) -> None:
        if self._current is None:
            return
        self._current["parameter_updates"].append({
            "name": name,
            "family": _parameter_family(name),
            "parameter_count": parameter_count,
            **statistics,
        })

    def finish_step(self) -> None:
        if self._current is None:
            return
        if any(
            layer["raw_gate_credit"] is None or layer["effective_gate_credit"] is None
            for layer in self._current["layers"]
        ):
            raise RuntimeError("gate-credit backward hooks did not all execute")
        self.records.append(self._current)
        self._current = None

    def report(self, binding: dict[str, Any], *, overhead: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "diagnostic_semantics": "observational_only",
            "metric": "activation_credit_alignment_cos_h_negative_dloss_dh",
            "loss_role": "telemetry_only",
            "configuration": {
                "enabled": True,
                "log_every_n_steps": self.log_every_n_steps,
                "max_sampled_steps": self.max_sampled_steps,
                "capture_raw_gate": True,
                "capture_effective_gate": True,
                "capture_parameter_gradients": True,
                "capture_optimizer_movement": True,
                "preserve_source_metadata": True,
            },
            "binding": binding,
            "overhead": overhead,
            "sampled_steps": self.records,
        }
