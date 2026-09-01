from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import torch
from torch import nn

from .student import CortexStudent


VISUAL_PROJECTOR_SCHEMA = "ninereeds_siglip2_projector_v1"


@dataclass(frozen=True)
class Siglip2ProjectorConfig:
    receptor_model_id: str = "google/siglip2-base-patch16-naflex"
    receptor_revision: str = "b53b807d3a2d5e2b3911292f2d69e5341cdc064c"
    receptor_width: int = 768
    cortex_width: int = 512
    observation_tokens: int = 16
    attention_heads: int = 8


class BoundedVisualResampler(nn.Module):
    """Project variable NaFlex patches into a fixed, spatially aware observation."""

    def __init__(self, config: Siglip2ProjectorConfig) -> None:
        super().__init__()
        self.config = config
        self.patch_norm = nn.LayerNorm(config.receptor_width)
        self.patch_projector = nn.Linear(config.receptor_width, config.cortex_width)
        self.position_projector = nn.Linear(2, config.cortex_width, bias=False)
        self.modality = nn.Parameter(torch.empty(config.cortex_width))
        self.queries = nn.Parameter(
            torch.empty(config.observation_tokens, config.cortex_width)
        )
        self.attention = nn.MultiheadAttention(
            config.cortex_width,
            config.attention_heads,
            batch_first=True,
        )
        self.output_norm = nn.LayerNorm(config.cortex_width)
        nn.init.normal_(self.modality, std=0.02)
        nn.init.normal_(self.queries, std=0.02)

    def forward(
        self,
        patch_states: torch.Tensor,
        patch_mask: torch.Tensor,
        spatial_shapes: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        if patch_states.ndim != 3 or patch_states.size(-1) != self.config.receptor_width:
            raise ValueError("patch_states have the wrong shape")
        if patch_mask.shape != patch_states.shape[:2]:
            raise ValueError("patch_mask must match patch sequence dimensions")
        if spatial_shapes.shape != (patch_states.size(0), 2):
            raise ValueError("spatial_shapes must be [batch, 2]")
        positions = self._positions(
            spatial_shapes,
            patch_states.size(1),
            device=patch_states.device,
            dtype=patch_states.dtype,
        )
        patches = self.patch_projector(self.patch_norm(patch_states))
        patches = patches + self.position_projector(positions) + self.modality
        queries = self.queries.unsqueeze(0).expand(patches.size(0), -1, -1)
        observed, _ = self.attention(
            queries,
            patches,
            patches,
            key_padding_mask=~patch_mask.to(dtype=torch.bool),
            need_weights=False,
        )
        observed = self.output_norm(observed + queries)
        mask = torch.ones(
            observed.shape[:2], device=observed.device, dtype=torch.bool
        )
        return observed, mask

    @staticmethod
    def _positions(
        spatial_shapes: torch.Tensor,
        sequence: int,
        *,
        device: torch.device,
        dtype: torch.dtype,
    ) -> torch.Tensor:
        result = torch.zeros(
            spatial_shapes.size(0), sequence, 2, device=device, dtype=dtype
        )
        for index, shape in enumerate(spatial_shapes.tolist()):
            rows, columns = int(shape[0]), int(shape[1])
            count = min(rows * columns, sequence)
            if rows <= 0 or columns <= 0 or count == 0:
                continue
            flat = torch.arange(count, device=device)
            result[index, :count, 0] = (flat // columns).to(dtype) / max(rows - 1, 1)
            result[index, :count, 1] = (flat % columns).to(dtype) / max(columns - 1, 1)
        return result.mul_(2).sub_(1)


class Siglip2VisualIngress(nn.Module):
    """Frozen SigLIP2 visual cortex with a trainable width-512 afferent."""

    def __init__(
        self,
        *,
        config: Siglip2ProjectorConfig | None = None,
        receptor_snapshot: str | Path | None = None,
        receptor_dtype: torch.dtype = torch.bfloat16,
        local_files_only: bool = True,
    ) -> None:
        super().__init__()
        from transformers import AutoModel, AutoProcessor

        self.config = config or Siglip2ProjectorConfig()
        self.receptor_source = (
            str(receptor_snapshot)
            if receptor_snapshot is not None
            else self.config.receptor_model_id
        )
        source_kwargs: dict[str, Any] = {"local_files_only": local_files_only}
        if receptor_snapshot is None:
            source_kwargs["revision"] = self.config.receptor_revision
        self.processor = AutoProcessor.from_pretrained(
            self.receptor_source,
            **source_kwargs,
        )
        receptor = AutoModel.from_pretrained(
            self.receptor_source,
            dtype=receptor_dtype,
            **source_kwargs,
        )
        self.receptor = receptor.vision_model
        self.resampler = BoundedVisualResampler(self.config)
        self.receptor.requires_grad_(False).eval()

    def train(self, mode: bool = True) -> "Siglip2VisualIngress":
        super().train(mode)
        self.receptor.eval()
        return self

    def place(
        self,
        *,
        receptor_device: torch.device,
        projector_device: torch.device,
        trainable_dtype: torch.dtype,
    ) -> None:
        self.receptor.to(receptor_device)
        self.resampler.to(device=projector_device, dtype=trainable_dtype)
        self.receptor.requires_grad_(False)

    def preprocess(self, images: list[Any]) -> dict[str, torch.Tensor]:
        if not images:
            raise ValueError("visual ingress requires at least one image")
        values = self.processor(images=images, return_tensors="pt")
        device = next(self.receptor.parameters()).device
        return {key: value.to(device) for key, value in values.items()}

    @torch.no_grad()
    def receptor_features(
        self, images: list[Any]
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        inputs = self.preprocess(images)
        output = self.receptor(
            pixel_values=inputs["pixel_values"],
            attention_mask=inputs["pixel_attention_mask"],
            spatial_shapes=inputs["spatial_shapes"],
            return_dict=True,
        )
        return (
            output.last_hidden_state.detach(),
            inputs["pixel_attention_mask"],
            inputs["spatial_shapes"],
        )

    def project_features(
        self,
        patch_states: torch.Tensor,
        patch_mask: torch.Tensor,
        spatial_shapes: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        parameter = next(self.resampler.parameters())
        return self.resampler(
            patch_states.to(device=parameter.device, dtype=parameter.dtype),
            patch_mask.to(parameter.device),
            spatial_shapes.to(parameter.device),
        )

    def forward(self, images: list[Any]) -> tuple[torch.Tensor, torch.Tensor]:
        return self.project_features(*self.receptor_features(images))

    def ownership_report(self) -> dict[str, int]:
        return {
            "frozen_receptor_parameters": sum(
                parameter.numel() for parameter in self.receptor.parameters()
            ),
            "visual_receptor_trainable_parameters": sum(
                parameter.numel()
                for parameter in self.receptor.parameters()
                if parameter.requires_grad
            ),
            "trainable_resampler_parameters": sum(
                parameter.numel() for parameter in self.resampler.parameters()
                if parameter.requires_grad
            ),
            "receptor_parameters_with_gradients": sum(
                parameter.grad is not None for parameter in self.receptor.parameters()
            ),
        }


class Siglip2CortexProjector(nn.Module):
    """Frozen SigLIP2 receptor feeding a frozen language Cortex through a sidecar."""

    def __init__(
        self,
        student: CortexStudent,
        receptor_snapshot: str,
        *,
        config: Siglip2ProjectorConfig | None = None,
        receptor_dtype: torch.dtype = torch.float16,
    ) -> None:
        super().__init__()
        from transformers import AutoModel, AutoProcessor

        self.student = student
        self.config = config or Siglip2ProjectorConfig()
        self.processor = AutoProcessor.from_pretrained(
            receptor_snapshot, local_files_only=True
        )
        receptor = AutoModel.from_pretrained(
            receptor_snapshot,
            local_files_only=True,
            dtype=receptor_dtype,
        )
        self.receptor = receptor.vision_model
        self.resampler = BoundedVisualResampler(self.config)
        self.receptor.requires_grad_(False).eval()
        self.student.requires_grad_(False).eval()

    def train(self, mode: bool = True) -> "Siglip2CortexProjector":
        super().train(mode)
        self.receptor.eval()
        self.student.eval()
        self.resampler.train(mode)
        return self

    def place(
        self,
        *,
        receptor_device: torch.device,
        core_device: torch.device,
        dtype: torch.dtype = torch.bfloat16,
    ) -> dict[str, Any]:
        partition = self.student.place(
            ingress_device=receptor_device,
            core_device=core_device,
            trainable_dtype=dtype,
        )
        self.receptor.to(device=receptor_device)
        self.resampler.to(device=receptor_device, dtype=dtype)
        self.student.requires_grad_(False)
        return partition

    def preprocess(self, images: list[Any]) -> dict[str, torch.Tensor]:
        values = self.processor(images=images, return_tensors="pt")
        device = next(self.receptor.parameters()).device
        return {key: value.to(device) for key, value in values.items()}

    def visual_intentions(self, images: list[Any]) -> torch.Tensor:
        patches, mask, shapes = self.receptor_features(images)
        return self.visual_intentions_from_features(patches, mask, shapes)

    @torch.no_grad()
    def receptor_features(
        self, images: list[Any]
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        inputs = self.preprocess(images)
        output = self.receptor(
            pixel_values=inputs["pixel_values"],
            attention_mask=inputs["pixel_attention_mask"],
            spatial_shapes=inputs["spatial_shapes"],
            return_dict=True,
        )
        return (
            output.last_hidden_state.detach(),
            inputs["pixel_attention_mask"],
            inputs["spatial_shapes"],
        )

    def visual_intentions_from_features(
        self,
        patch_states: torch.Tensor,
        patch_mask: torch.Tensor,
        spatial_shapes: torch.Tensor,
    ) -> torch.Tensor:
        parameter = next(self.resampler.parameters())
        device = parameter.device
        observed, mask = self.resampler(
            patch_states.to(device=device, dtype=parameter.dtype),
            patch_mask.to(device),
            spatial_shapes.to(device),
        )
        hidden = self.student.core.encode_embeds(observed)
        return self.student.intention(hidden, mask.to(hidden.device))

    @torch.no_grad()
    def text_targets(self, phrases: list[str]) -> torch.Tensor:
        return self.student.intentions(phrases).detach()

    def alignment_loss(self, images: list[Any], phrases: list[str]) -> torch.Tensor:
        if len(images) != len(phrases) or not images:
            raise ValueError("images and phrases must be non-empty equal-length lists")
        target = self.text_targets(phrases)
        visual = self.visual_intentions(images)
        return nn.functional.mse_loss(visual, target.to(visual.device))

    def trainable_parameters(self) -> Iterable[nn.Parameter]:
        return self.resampler.parameters()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_visual_projector(
    path: Path,
    projector: Siglip2CortexProjector,
    *,
    base_checkpoint: Path,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema_version": VISUAL_PROJECTOR_SCHEMA,
            "config": dataclasses.asdict(projector.config),
            "base_checkpoint": str(base_checkpoint),
            "base_checkpoint_sha256": file_sha256(base_checkpoint),
            "resampler_state": projector.resampler.state_dict(),
            "metadata": metadata,
        },
        path,
    )
