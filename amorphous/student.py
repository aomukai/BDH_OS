from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Iterable

import torch
from torch import nn

from cortex.config import CortexConfig
from cortex.intention import IntentionHead
from cortex.lfm import LFMExpressionCortex
from cortex.lfm_encoder import LFMEncoderIngress

from .config import CellSubstrateConfig, GrowthPolicyConfig
from .growth import GrowthController
from .substrate import AmorphousSubstrate


AMORPHOUS_CORTEX_ARCHITECTURE = (
    "lfm2_5_encoder_230m_frozen__ninereeds_amorphous_cells__"
    "lfm2_5_230m_frozen"
)
AMORPHOUS_CORTEX_CHECKPOINT_SCHEMA = "ninereeds_amorphous_cortex_checkpoint_v1"


class AmorphousCortexStudent(nn.Module):
    """Independent LFM-organ student whose cognitive core is a cell substrate."""

    def __init__(
        self,
        substrate: AmorphousSubstrate,
        *,
        cortex_config: CortexConfig | None = None,
        frozen_dtype: torch.dtype | None = None,
        local_files_only: bool = True,
    ) -> None:
        super().__init__()
        self.substrate = substrate
        self.cortex_config = cortex_config or CortexConfig()
        width = substrate.config.width
        self.cortex_config.validate_for_ninereeds(width)
        self.ingress = LFMEncoderIngress(
            width,
            config=self.cortex_config,
            dtype=frozen_dtype,
            local_files_only=local_files_only,
        )
        self.intention = IntentionHead(
            width,
            num_tokens=self.cortex_config.intention_tokens,
            num_heads=8,
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
        substrate_device: torch.device,
        trainable_dtype: torch.dtype = torch.bfloat16,
    ) -> dict[str, Any]:
        self.ingress.encoder.to(ingress_device)
        self.ingress.projector.to(device=ingress_device, dtype=trainable_dtype)
        self.substrate.to(device=substrate_device, dtype=trainable_dtype)
        self.intention.to(device=substrate_device, dtype=trainable_dtype)
        self.expression.to(device=substrate_device, dtype=trainable_dtype)
        return {
            "ingress_device": str(ingress_device),
            "substrate_device": str(substrate_device),
            "cell_cohorts": len(self.substrate.cohorts),
            **self.substrate.anatomy(),
        }

    def train(self, mode: bool = True) -> "AmorphousCortexStudent":
        super().train(mode)
        self.ingress.encoder.eval()
        self.expression.model.eval()
        return self

    def latent_states(
        self,
        prompts: list[str],
        *,
        collect_trace: bool = False,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any] | None]:
        encoded = self.ingress.tokenize(prompts)
        projected, attention_mask = self.ingress(
            encoded["input_ids"],
            encoded["attention_mask"],
            encoded.get("token_type_ids"),
        )
        result = self.substrate(
            projected,
            attention_mask,
            collect_trace=collect_trace,
        )
        if collect_trace:
            hidden, trace = result
        else:
            hidden, trace = result, None
        return hidden, attention_mask.to(hidden.device), trace

    def intentions(
        self,
        prompts: list[str],
        *,
        collect_trace: bool = False,
    ) -> torch.Tensor | tuple[torch.Tensor, dict[str, Any]]:
        hidden, attention_mask, trace = self.latent_states(
            prompts, collect_trace=collect_trace
        )
        intentions = self.intention(hidden, attention_mask)
        if not collect_trace:
            return intentions
        assert trace is not None
        return intentions, trace

    def response_loss(
        self,
        prompts: list[str],
        responses: list[str],
    ) -> torch.Tensor:
        if len(prompts) != len(responses) or not prompts:
            raise ValueError("prompts and responses must be non-empty equal-length lists")
        intentions = self.intentions(prompts)
        assert isinstance(intentions, torch.Tensor)
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
    def generate_text(
        self,
        prompts: list[str],
        *,
        max_new_tokens: int = 32,
    ) -> list[str]:
        was_training = self.training
        self.eval()
        try:
            intentions = self.intentions(prompts)
            assert isinstance(intentions, torch.Tensor)
            generated = self.expression.generate(
                intentions,
                max_new_tokens=max_new_tokens,
                do_sample=False,
            )
            return self.expression.tokenizer.batch_decode(
                generated, skip_special_tokens=True
            )
        finally:
            self.train(was_training)

    def trainable_parameters(self) -> Iterable[nn.Parameter]:
        return (parameter for parameter in self.parameters() if parameter.requires_grad)

    def optimizer_parameter_groups(self) -> list[dict[str, Any]]:
        """Return stable groups so newly born cohorts can be appended on resume."""
        organ_bridge = [
            *self.ingress.projector.parameters(),
            *self.intention.parameters(),
            *self.expression.projector.parameters(),
        ]
        groups = [{"params": organ_bridge, "component": "organ_bridge"}]
        for index, cohort in enumerate(self.substrate.cohorts):
            groups.append({
                "params": list(cohort.parameters()),
                "component": "cell_cohort",
                "cohort_index": index,
                "cell_ids": list(cohort.cell_ids),
            })
        return groups

    def ownership_report(self) -> dict[str, Any]:
        return {
            "architecture": AMORPHOUS_CORTEX_ARCHITECTURE,
            "frozen_encoder_parameters": sum(
                parameter.numel() for parameter in self.ingress.encoder.parameters()
            ),
            "frozen_lfm_parameters": sum(
                parameter.numel() for parameter in self.expression.model.parameters()
            ),
            "organ_bridge_parameters": sum(
                parameter.numel()
                for module in (
                    self.ingress.projector,
                    self.intention,
                    self.expression.projector,
                )
                for parameter in module.parameters()
            ),
            "encoder_parameters_with_gradients": sum(
                parameter.grad is not None
                for parameter in self.ingress.encoder.parameters()
            ),
            "lfm_parameters_with_gradients": sum(
                parameter.grad is not None
                for parameter in self.expression.model.parameters()
            ),
            **self.substrate.anatomy(),
        }


def save_amorphous_cortex_checkpoint(
    path: Path,
    student: AmorphousCortexStudent,
    *,
    growth_controller: GrowthController,
    parent: str,
    metadata: dict[str, Any],
    optimizer_state: dict[str, Any] | None = None,
    visual_state: dict[str, Any] | None = None,
    runtime_state: dict[str, Any] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "schema_version": AMORPHOUS_CORTEX_CHECKPOINT_SCHEMA,
        "architecture": AMORPHOUS_CORTEX_ARCHITECTURE,
        "cortex_config": dataclasses.asdict(student.cortex_config),
        "substrate": student.substrate.checkpoint(
            growth_controller=growth_controller,
            metadata={"parent": parent},
        ),
        "organ_bridge_state": {
            "ingress_projector": student.ingress.projector.state_dict(),
            "intention": student.intention.state_dict(),
            "expression_projector": student.expression.projector.state_dict(),
        },
        "parent": parent,
        "optimizer_state": optimizer_state,
        "metadata": metadata,
    }
    if visual_state is not None:
        document["visual_state"] = visual_state
    if runtime_state is not None:
        document["runtime_state"] = runtime_state
    torch.save(document, path)


def build_amorphous_student(
    parent: Path | None,
    *,
    substrate_config: CellSubstrateConfig | None = None,
    growth_config: GrowthPolicyConfig | None = None,
    frozen_dtype: torch.dtype | None,
    local_files_only: bool,
) -> tuple[
    AmorphousCortexStudent,
    GrowthController,
    dict[str, Any] | None,
]:
    if parent is None:
        substrate = AmorphousSubstrate(substrate_config)
        return (
            AmorphousCortexStudent(
                substrate,
                frozen_dtype=frozen_dtype,
                local_files_only=local_files_only,
            ),
            GrowthController(growth_config),
            None,
        )

    value = torch.load(parent, map_location="cpu", weights_only=True)
    if value.get("schema_version") != AMORPHOUS_CORTEX_CHECKPOINT_SCHEMA:
        raise ValueError("parent is not an amorphous Cortex checkpoint")
    substrate, controller = AmorphousSubstrate.from_checkpoint(value["substrate"])
    if controller is None:
        raise ValueError("amorphous parent lacks its growth-controller state")
    student = AmorphousCortexStudent(
        substrate,
        cortex_config=CortexConfig(**value["cortex_config"]),
        frozen_dtype=frozen_dtype,
        local_files_only=local_files_only,
    )
    bridge = value["organ_bridge_state"]
    student.ingress.projector.load_state_dict(bridge["ingress_projector"], strict=True)
    student.intention.load_state_dict(bridge["intention"], strict=True)
    student.expression.projector.load_state_dict(
        bridge["expression_projector"], strict=True
    )
    return student, controller, value.get("optimizer_state")
