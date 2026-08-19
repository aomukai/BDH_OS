from __future__ import annotations

import math
from typing import Iterable

import torch
from torch.optim import Optimizer


STOCHASTIC_ROUNDING_CHUNK_ELEMENTS = 1 << 20
MEMORY_BOUNDED_FACTORED_MIN_ELEMENTS = 1 << 20


class FactoredAdamW(Optimizer):
    """Adam momentum with an Adafactor-style factored second moment.

    This is the controlled Ninereeds "SkewAdam B" experiment: it retains full
    momentum and changes only second-moment allocation by default. Optional RMS
    clipping and stochastic bf16 updates are separate switches.
    """

    policy_version = "ninereeds_factored_adamw_v1"

    def __init__(
        self,
        params: Iterable[torch.nn.Parameter],
        *,
        lr: float = 1e-3,
        betas: tuple[float, float] = (0.9, 0.999),
        eps: float = 1e-8,
        weight_decay: float = 0.0,
        momentum: bool = True,
        rms_clip: float | None = None,
        stochastic_rounding: bool = False,
        diagnostic_callback=None,
    ) -> None:
        if lr <= 0:
            raise ValueError("lr must be positive")
        if not 0 <= betas[0] < 1 or not 0 <= betas[1] < 1:
            raise ValueError("betas must be in [0, 1)")
        if eps <= 0 or weight_decay < 0:
            raise ValueError("eps must be positive and weight_decay non-negative")
        if rms_clip is not None and rms_clip <= 0:
            raise ValueError("rms_clip must be positive")
        defaults = dict(
            lr=lr,
            betas=betas,
            eps=eps,
            weight_decay=weight_decay,
            momentum=momentum,
            rms_clip=rms_clip,
            stochastic_rounding=stochastic_rounding,
        )
        super().__init__(params, defaults)
        self.diagnostic_callback = diagnostic_callback
        self.diagnostic_statistics_callback = None

    @staticmethod
    def _factorable(tensor: torch.Tensor) -> bool:
        return tensor.ndim >= 2 and tensor.shape[-1] > 1 and tensor.numel() > 1024

    @torch.no_grad()
    def step(self, closure=None):
        loss = closure() if closure is not None else None
        for group in self.param_groups:
            beta1, beta2 = group["betas"]
            for parameter in group["params"]:
                if parameter.grad is None:
                    continue
                source_gradient = parameter.grad.detach()
                bounded_factored = (
                    self._factorable(parameter)
                    and parameter.numel() >= MEMORY_BOUNDED_FACTORED_MIN_ELEMENTS
                )
                if bounded_factored:
                    flat_gradient = source_gradient.reshape(-1)
                    for start in range(0, flat_gradient.numel(), STOCHASTIC_ROUNDING_CHUNK_ELEMENTS):
                        stop = min(start + STOCHASTIC_ROUNDING_CHUNK_ELEMENTS, flat_gradient.numel())
                        if not torch.isfinite(flat_gradient[start:stop]).all():
                            raise FloatingPointError("non-finite gradient in FactoredAdamW")
                    grad = None
                else:
                    grad = source_gradient.float()
                    if not torch.isfinite(grad).all():
                        raise FloatingPointError("non-finite gradient in FactoredAdamW")
                state = self.state[parameter]
                if not state:
                    state["step"] = 0
                    if group["momentum"]:
                        state["exp_avg"] = torch.zeros_like(
                            parameter,
                            dtype=torch.float32,
                            memory_format=torch.preserve_format,
                        )
                    if self._factorable(parameter):
                        state["exp_avg_sq_row"] = torch.zeros(
                            parameter.shape[:-1],
                            dtype=torch.float32,
                            device=parameter.device,
                        )
                        state["exp_avg_sq_col"] = torch.zeros(
                            parameter.shape[-1],
                            dtype=torch.float32,
                            device=parameter.device,
                        )
                        state["factored"] = True
                    else:
                        state["exp_avg_sq"] = torch.zeros_like(
                            parameter,
                            dtype=torch.float32,
                            memory_format=torch.preserve_format,
                        )
                        state["factored"] = False
                state["step"] += 1
                step = state["step"]

                if bounded_factored:
                    self._bounded_factored_step(
                        parameter, source_gradient, state, group, step,
                    )
                    continue

                if state["factored"]:
                    grad_sq = grad.square()
                    row = state["exp_avg_sq_row"]
                    col = state["exp_avg_sq_col"]
                    row.mul_(beta2).add_(grad_sq.mean(dim=-1), alpha=1 - beta2)
                    reduce_dims = tuple(range(grad.ndim - 1))
                    col.mul_(beta2).add_(grad_sq.mean(dim=reduce_dims), alpha=1 - beta2)
                    row_mean = row.mean().clamp_min(group["eps"])
                    variance = row.unsqueeze(-1) * col / row_mean
                else:
                    variance = state["exp_avg_sq"]
                    variance.mul_(beta2).addcmul_(grad, grad, value=1 - beta2)

                variance = variance / (1 - beta2**step)
                if group["momentum"]:
                    momentum = state["exp_avg"]
                    momentum.mul_(beta1).add_(grad, alpha=1 - beta1)
                    numerator = momentum / (1 - beta1**step)
                else:
                    numerator = grad
                update = numerator / variance.sqrt().add_(group["eps"])
                if group["rms_clip"] is not None:
                    rms = update.square().mean().sqrt()
                    update.div_(torch.maximum(rms / group["rms_clip"], torch.ones_like(rms)))
                if group["weight_decay"]:
                    update.add_(parameter.detach().float(), alpha=group["weight_decay"])
                if self.diagnostic_callback is not None:
                    self.diagnostic_callback(
                        parameter, grad, update, float(group["lr"]),
                    )
                target = parameter.detach().float().add(
                    update,
                    alpha=-group["lr"],
                )
                if group["stochastic_rounding"] and parameter.dtype == torch.bfloat16:
                    self._copy_stochastic_bf16_(parameter, target)
                else:
                    parameter.copy_(target.to(parameter.dtype))
        return loss

    def _bounded_factored_step(
        self,
        parameter: torch.Tensor,
        source_gradient: torch.Tensor,
        state: dict,
        group: dict,
        step: int,
    ) -> None:
        """Apply one large factored update without full-size FP32 intermediates."""
        beta1, beta2 = group["betas"]
        width = parameter.shape[-1]
        row_count = parameter.numel() // width
        rows_per_chunk = max(1, STOCHASTIC_ROUNDING_CHUNK_ELEMENTS // width)
        gradient_rows = source_gradient.reshape(row_count, width)
        parameter_rows = parameter.reshape(row_count, width)
        row = state["exp_avg_sq_row"].reshape(row_count)
        col = state["exp_avg_sq_col"]
        momentum_rows = state["exp_avg"].reshape(row_count, width)

        col_sum = torch.zeros_like(col)
        for start in range(0, row_count, rows_per_chunk):
            stop = min(start + rows_per_chunk, row_count)
            grad = gradient_rows[start:stop].to(torch.float32)
            grad_square = grad.square()
            row[start:stop].mul_(beta2).add_(
                grad_square.mean(dim=-1), alpha=1 - beta2,
            )
            col_sum.add_(grad_square.sum(dim=0))
        col.mul_(beta2).add_(col_sum / row_count, alpha=1 - beta2)

        row_mean = row.mean().clamp_min(group["eps"])
        first_bias = 1 - beta1**step
        second_bias = 1 - beta2**step
        for start in range(0, row_count, rows_per_chunk):
            stop = min(start + rows_per_chunk, row_count)
            grad = gradient_rows[start:stop].to(torch.float32)
            momentum_rows[start:stop].mul_(beta1).add_(grad, alpha=1 - beta1)

        def update_chunk(start: int, stop: int) -> torch.Tensor:
            variance = row[start:stop].unsqueeze(-1) * col / row_mean
            variance.div_(second_bias)
            numerator = momentum_rows[start:stop] / first_bias
            return numerator / variance.sqrt().add_(group["eps"])

        update_square_sum = 0.0
        for start in range(0, row_count, rows_per_chunk):
            stop = min(start + rows_per_chunk, row_count)
            update = update_chunk(start, stop)
            norm = float(torch.linalg.vector_norm(update).detach().cpu())
            update_square_sum += norm * norm
        update_rms = math.sqrt(update_square_sum / parameter.numel())
        clip_divisor = 1.0
        if group["rms_clip"] is not None:
            clip_divisor = max(update_rms / group["rms_clip"], 1.0)

        gradient_abs_sum = 0.0
        gradient_square_sum = 0.0
        final_update_square_sum = 0.0
        parameter_square_sum = 0.0
        gradient_update_dot = 0.0
        for start in range(0, row_count, rows_per_chunk):
            stop = min(start + rows_per_chunk, row_count)
            grad = gradient_rows[start:stop].to(torch.float32)
            parameter_value = parameter_rows[start:stop].to(torch.float32)
            update = update_chunk(start, stop)
            if clip_divisor != 1.0:
                update.div_(clip_divisor)
            if group["weight_decay"]:
                update.add_(parameter_value, alpha=group["weight_decay"])
            if self.diagnostic_statistics_callback is not None:
                gradient_abs_sum += float(torch.sum(torch.abs(grad)).detach().cpu())
                grad_norm = float(torch.linalg.vector_norm(grad).detach().cpu())
                update_norm = float(torch.linalg.vector_norm(update).detach().cpu())
                parameter_norm = float(torch.linalg.vector_norm(parameter_value).detach().cpu())
                gradient_square_sum += grad_norm * grad_norm
                final_update_square_sum += update_norm * update_norm
                parameter_square_sum += parameter_norm * parameter_norm
                gradient_update_dot += float(torch.dot(grad.reshape(-1), update.reshape(-1)).detach().cpu())
            target = parameter_value.add(update, alpha=-group["lr"])
            if group["stochastic_rounding"] and parameter.dtype == torch.bfloat16:
                self._copy_stochastic_bf16_(parameter_rows[start:stop], target)
            else:
                parameter_rows[start:stop].copy_(target.to(parameter.dtype))

        if self.diagnostic_statistics_callback is not None:
            gradient_norm = math.sqrt(gradient_square_sum)
            update_norm = math.sqrt(final_update_square_sum)
            parameter_norm = math.sqrt(parameter_square_sum)
            movement_norm = update_norm * group["lr"]
            denominator = gradient_norm * update_norm
            self.diagnostic_statistics_callback(parameter, {
                "gradient_mean_abs": gradient_abs_sum / parameter.numel(),
                "gradient_rms": math.sqrt(gradient_square_sum / parameter.numel()),
                "gradient_norm": gradient_norm,
                "nonfinite_gradient_count": 0,
                "optimizer_update_norm_before_lr": update_norm,
                "intended_movement_norm": movement_norm,
                "descent_to_optimizer_movement_cosine": (
                    None if denominator == 0.0 else gradient_update_dot / denominator
                ),
                "update_to_parameter_norm_ratio": (
                    None if parameter_norm == 0.0 else movement_norm / parameter_norm
                ),
            })

    @staticmethod
    def _stochastic_bf16(value: torch.Tensor) -> torch.Tensor:
        """Dither before bf16 conversion; explicit approximation, not exact SR."""
        ulp = value.abs().clamp_min(torch.finfo(torch.float32).tiny) * (2.0**-7)
        noise = (torch.rand_like(value) - 0.5) * ulp
        return (value + noise).to(torch.bfloat16)

    @classmethod
    def _copy_stochastic_bf16_(
        cls, destination: torch.Tensor, value: torch.Tensor,
    ) -> None:
        """Stochastically convert into BF16 with tensor-size-independent VRAM."""
        flat_destination = destination.reshape(-1)
        flat_value = value.reshape(-1)
        for start in range(0, value.numel(), STOCHASTIC_ROUNDING_CHUNK_ELEMENTS):
            stop = min(start + STOCHASTIC_ROUNDING_CHUNK_ELEMENTS, value.numel())
            flat_destination[start:stop].copy_(
                cls._stochastic_bf16(flat_value[start:stop]),
            )

    def state_bytes(self) -> int:
        return sum(
            value.numel() * value.element_size()
            for state in self.state.values()
            for value in state.values()
            if isinstance(value, torch.Tensor)
        )

    def load_state_dict(
        self,
        state_dict: dict,
        *,
        preserve_current_hyperparameters: bool = False,
    ) -> None:
        """Restore optimizer statistics, optionally keeping the commissioned recipe.

        ``Optimizer.load_state_dict`` normally restores parameter-group options as
        well as moments.  That is useful for an exact resume, but it silently defeats
        a new experiment when the caller deliberately constructs the optimizer with a
        different learning rate or update policy.  Cortex continuation blocks use the
        latter behavior: keep the newly commissioned options while carrying forward
        only the accumulated optimizer statistics.
        """
        current_groups = None
        if preserve_current_hyperparameters:
            current_groups = [
                {
                    key: value
                    for key, value in group.items()
                    if key != "params"
                }
                for group in self.param_groups
            ]
        super().load_state_dict(state_dict)
        if current_groups is not None:
            if len(current_groups) != len(self.param_groups):
                raise ValueError(
                    "loaded optimizer state has a different parameter-group count"
                )
            for group, current in zip(self.param_groups, current_groups, strict=True):
                group.update(current)
        for parameter, state in self.state.items():
            for key, value in tuple(state.items()):
                if isinstance(value, torch.Tensor) and value.is_floating_point():
                    state[key] = value.to(device=parameter.device, dtype=torch.float32)

    def policy(self) -> dict[str, object]:
        group = self.param_groups[0]
        return {
            "policy_version": self.policy_version,
            "momentum": bool(group["momentum"]),
            "second_moment": "factored_for_large_matrices",
            "rms_clip": group["rms_clip"],
            "stochastic_rounding": bool(group["stochastic_rounding"]),
            "weight_decay": float(group["weight_decay"]),
        }
