"""Bounded, read-only observation of Ninereeds gate credit and optimizer movement."""

from __future__ import annotations

import math
from typing import Any

import torch


SCHEMA_VERSION = "ninereeds_gate_credit_diagnostics_v1"


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
    return "other_trainable"


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
        grad = gradient.detach().to(torch.float32)
        update_value = update.detach().to(torch.float32)
        grad_norm = torch.linalg.vector_norm(grad)
        update_norm = torch.linalg.vector_norm(update_value)
        movement_norm = update_norm * learning_rate
        parameter_norm = torch.linalg.vector_norm(parameter.detach())
        denominator = grad_norm * update_norm
        # movement = -lr * update, so cos(-grad, movement) == cos(grad, update).
        cosine = None if _number(denominator) == 0.0 else _number(torch.sum(grad * update_value) / denominator)
        self._current["parameter_updates"].append({
            "name": name,
            "family": _parameter_family(name),
            "parameter_count": parameter.numel(),
            "gradient_mean_abs": _number(grad.abs().mean()),
            "gradient_rms": _number(grad.square().mean().sqrt()),
            "gradient_norm": _number(grad_norm),
            "nonfinite_gradient_count": int((~torch.isfinite(grad)).sum().detach().cpu()),
            "optimizer_update_norm_before_lr": _number(update_norm),
            "intended_movement_norm": _number(movement_norm),
            "descent_to_optimizer_movement_cosine": cosine,
            "update_to_parameter_norm_ratio": (
                None if _number(parameter_norm) == 0.0 else _number(movement_norm / parameter_norm)
            ),
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
