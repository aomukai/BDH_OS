from __future__ import annotations

import math
from typing import Iterable

import torch
from torch.optim import Optimizer


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
                grad = parameter.grad.detach().float()
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
                target = parameter.detach().float().add(
                    update,
                    alpha=-group["lr"],
                )
                if group["stochastic_rounding"] and parameter.dtype == torch.bfloat16:
                    parameter.copy_(self._stochastic_bf16(target))
                else:
                    parameter.copy_(target.to(parameter.dtype))
        return loss

    @staticmethod
    def _stochastic_bf16(value: torch.Tensor) -> torch.Tensor:
        """Dither before bf16 conversion; explicit approximation, not exact SR."""
        ulp = value.abs().clamp_min(torch.finfo(torch.float32).tiny) * (2.0**-7)
        noise = (torch.rand_like(value) - 0.5) * ulp
        return (value + noise).to(torch.bfloat16)

    def state_bytes(self) -> int:
        return sum(
            value.numel() * value.element_size()
            for state in self.state.values()
            for value in state.values()
            if isinstance(value, torch.Tensor)
        )

    def load_state_dict(self, state_dict: dict) -> None:
        """Restore fp32 optimizer statistics for bf16 model parameters."""
        super().load_state_dict(state_dict)
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
