from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Iterable

import torch
from torch import nn

from bdh import BDH, BDHConfig

from .config import CortexConfig
from .intention import IntentionHead
from .lfm import LFMExpressionCortex
from .mbert import MultilingualBertIngress


CORTEX_CHECKPOINT_SCHEMA = "ninereeds_cortex_checkpoint_v1"
CORTEX_1_2B_CONFIG = BDHConfig(
    n_layer=12,
    n_embd=512,
    n_head=8,
    mlp_internal_dim_multiplier=128,
    vocab_size=256,
    per_layer_weights=True,
)


class CortexStudent(nn.Module):
    """Frozen language cortices connected through the plastic Ninereeds core."""

    def __init__(
        self,
        core: BDH,
        *,
        cortex_config: CortexConfig | None = None,
        frozen_dtype: torch.dtype | None = None,
        local_files_only: bool = True,
    ) -> None:
        super().__init__()
        self.core = core
        self.cortex_config = cortex_config or CortexConfig()
        width = core.config.n_embd
        self.ingress = MultilingualBertIngress(
            width,
            config=self.cortex_config,
            dtype=frozen_dtype,
            local_files_only=local_files_only,
        )
        self.intention = IntentionHead(
            width,
            num_tokens=self.cortex_config.intention_tokens,
            num_heads=core.config.n_head,
        )
        self.expression = LFMExpressionCortex(
            width,
            config=self.cortex_config,
            dtype=frozen_dtype,
            local_files_only=local_files_only,
        )

    def place(
        self,
        *,
        ingress_device: torch.device,
        core_device: torch.device,
        trainable_dtype: torch.dtype = torch.bfloat16,
    ) -> dict[str, Any]:
        self.ingress.encoder.to(ingress_device)
        self.ingress.projector.to(device=ingress_device, dtype=trainable_dtype)
        partition = self.core.partition_layers(
            [ingress_device, core_device],
            split_at=self.core.config.n_layer // 2,
            dtype=trainable_dtype,
        )
        self.intention.to(device=core_device, dtype=trainable_dtype)
        self.expression.to(device=core_device, dtype=trainable_dtype)
        self.core.embed.requires_grad_(False)
        self.core.lm_head.requires_grad_(False)
        return partition

    @property
    def core_device(self) -> torch.device:
        return next(self.core.parameters()).device

    def train(self, mode: bool = True) -> "CortexStudent":
        super().train(mode)
        self.ingress.encoder.eval()
        self.expression.model.eval()
        return self

    def intentions(self, prompts: list[str]) -> torch.Tensor:
        encoded = self.ingress.tokenize(prompts)
        projected, attention_mask = self.ingress(
            encoded["input_ids"],
            encoded["attention_mask"],
            encoded.get("token_type_ids"),
        )
        hidden = self.core.encode_embeds(projected)
        attention_mask = attention_mask.to(hidden.device)
        return self.intention(hidden, attention_mask)

    @torch.no_grad()
    def trace_representations(self, prompts: list[str]) -> dict[str, Any]:
        """Trace the active Cortex path without exposing frozen model internals."""
        was_training = self.training
        self.eval()
        try:
            encoded = self.ingress.tokenize(prompts)
            projected, attention_mask = self.ingress(
                encoded["input_ids"],
                encoded["attention_mask"],
                encoded.get("token_type_ids"),
            )
            hidden, diagnostics = self.core.encode_embeds_with_diagnostics(projected)
            mask = attention_mask.to(hidden.device, dtype=hidden.dtype).unsqueeze(-1)
            denominator = mask.sum(dim=1).clamp_min(1)
            pooled_ingress = (projected.to(hidden.device) * mask).sum(dim=1) / denominator
            pooled_core = (hidden * mask).sum(dim=1) / denominator
            intentions = self.intention(hidden, attention_mask.to(hidden.device))
            return {
                "ingress": pooled_ingress.detach().to(torch.float32).cpu(),
                "core": pooled_core.detach().to(torch.float32).cpu(),
                "intentions": intentions.mean(dim=1).detach().to(torch.float32).cpu(),
                "intention_tokens": intentions.detach().to(torch.float32).cpu(),
                "diagnostics": diagnostics,
            }
        finally:
            self.train(was_training)

    def response_loss(self, prompts: list[str], responses: list[str]) -> torch.Tensor:
        if len(prompts) != len(responses) or not prompts:
            raise ValueError("prompts and responses must be non-empty equal-length lists")
        intentions = self.intentions(prompts)
        encoded = self.expression.tokenizer(
            responses,
            add_special_tokens=False,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )
        return self.expression.response_loss(
            intentions,
            encoded["input_ids"],
            encoded.get("attention_mask"),
        )

    @torch.no_grad()
    def generate_text(self, prompts: list[str], *, max_new_tokens: int = 32) -> list[str]:
        was_training = self.training
        self.eval()
        try:
            generated = self.expression.generate(
                self.intentions(prompts),
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
            return self.expression.tokenizer.batch_decode(
                generated,
                skip_special_tokens=True,
            )
        finally:
            self.train(was_training)

    def trainable_parameters(self) -> Iterable[nn.Parameter]:
        return (parameter for parameter in self.parameters() if parameter.requires_grad)

    def ownership_report(self) -> dict[str, int]:
        return {
            "frozen_mbert_parameters": sum(
                parameter.numel() for parameter in self.ingress.encoder.parameters()
            ),
            "frozen_lfm_parameters": sum(
                parameter.numel() for parameter in self.expression.model.parameters()
            ),
            "trainable_parameters": sum(
                parameter.numel() for parameter in self.parameters() if parameter.requires_grad
            ),
            "mbert_parameters_with_gradients": sum(
                parameter.grad is not None for parameter in self.ingress.encoder.parameters()
            ),
            "lfm_parameters_with_gradients": sum(
                parameter.grad is not None for parameter in self.expression.model.parameters()
            ),
        }

    def trainable_state(self) -> dict[str, dict[str, torch.Tensor]]:
        return {
            "core": self.core.state_dict(),
            "ingress_projector": self.ingress.projector.state_dict(),
            "intention": self.intention.state_dict(),
            "expression_projector": self.expression.projector.state_dict(),
        }

    def load_trainable_state(self, state: dict[str, Any]) -> None:
        self.core.load_state_dict(state["core"], strict=True)
        self.ingress.projector.load_state_dict(state["ingress_projector"], strict=True)
        self.intention.load_state_dict(state["intention"], strict=True)
        self.expression.projector.load_state_dict(state["expression_projector"], strict=True)


def load_byte_core(path: Path) -> tuple[BDH, BDHConfig]:
    torch.serialization.add_safe_globals([BDHConfig])
    value = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(value, dict) or not isinstance(value.get("config"), BDHConfig):
        raise ValueError("byte-core checkpoint lacks a BDHConfig")
    core = BDH(value["config"])
    core.load_state_dict(value["model_state_dict"], strict=True)
    return core, value["config"]


def build_student(
    parent: Path | None,
    *,
    frozen_dtype: torch.dtype | None,
    local_files_only: bool,
) -> tuple[CortexStudent, str, dict[str, Any] | None]:
    if parent is None:
        return (
            CortexStudent(
                BDH(CORTEX_1_2B_CONFIG),
                frozen_dtype=frozen_dtype,
                local_files_only=local_files_only,
            ),
            "scratch_1_2b",
            None,
        )
    torch.serialization.add_safe_globals([BDHConfig])
    value = torch.load(parent, map_location="cpu", weights_only=True)
    if isinstance(value, dict) and value.get("schema_version") == CORTEX_CHECKPOINT_SCHEMA:
        core_config = BDHConfig(**value["core_config"])
        cortex_config = CortexConfig(**value["cortex_config"])
        student = CortexStudent(
            BDH(core_config),
            cortex_config=cortex_config,
            frozen_dtype=frozen_dtype,
            local_files_only=local_files_only,
        )
        student.load_trainable_state(value["trainable_state"])
        return student, "cortex", value.get("optimizer_state")
    core, _ = load_byte_core(parent)
    return (
        CortexStudent(
            core,
            frozen_dtype=frozen_dtype,
            local_files_only=local_files_only,
        ),
        "byte_core",
        None,
    )


def save_cortex_checkpoint(
    path: Path,
    student: CortexStudent,
    *,
    parent: str,
    metadata: dict[str, Any],
    optimizer_state: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": CORTEX_CHECKPOINT_SCHEMA,
            "core_config": dataclasses.asdict(student.core.config),
            "cortex_config": dataclasses.asdict(student.cortex_config),
            "parent": parent,
            "trainable_state": student.trainable_state(),
            "optimizer_state": optimizer_state,
            "metadata": metadata,
        },
        path,
    )
