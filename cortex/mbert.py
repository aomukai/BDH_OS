from __future__ import annotations

from typing import Any

import torch
from torch import nn

from .config import CortexConfig


class MultilingualBertIngress(nn.Module):
    """Frozen multilingual BERT with a trainable Ninereeds afferent path."""

    def __init__(
        self,
        ninereeds_width: int,
        *,
        config: CortexConfig | None = None,
        dtype: torch.dtype | None = None,
        local_files_only: bool = False,
    ) -> None:
        super().__init__()
        cfg = config or CortexConfig()
        cfg.validate_for_ninereeds(ninereeds_width)
        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "MultilingualBertIngress requires the cortex environment; "
                "install cortex/requirements.txt"
            ) from exc

        self.config = cfg
        self.tokenizer = AutoTokenizer.from_pretrained(
            cfg.mbert_model_id,
            local_files_only=local_files_only,
        )
        model_kwargs: dict[str, Any] = {"local_files_only": local_files_only}
        if dtype is not None:
            model_kwargs["dtype"] = dtype
        self.encoder = AutoModel.from_pretrained(cfg.mbert_model_id, **model_kwargs)
        self.encoder.requires_grad_(False)
        self.encoder.eval()
        self.projector = nn.Sequential(
            nn.LayerNorm(cfg.mbert_width),
            nn.Linear(cfg.mbert_width, ninereeds_width),
        )

    def train(self, mode: bool = True) -> "MultilingualBertIngress":
        super().train(mode)
        self.encoder.eval()
        return self

    def tokenize(self, texts: list[str] | tuple[str, ...], **overrides: Any) -> dict[str, torch.Tensor]:
        options: dict[str, Any] = {
            "padding": True,
            "truncation": True,
            "max_length": self.config.mbert_max_length,
            "return_tensors": "pt",
        }
        options.update(overrides)
        return self.tokenizer(list(texts), **options)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        token_type_ids: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        encoder_device = next(self.encoder.parameters()).device
        kwargs = {
            "input_ids": input_ids.to(encoder_device),
            "attention_mask": attention_mask.to(encoder_device),
            "output_hidden_states": True,
            "return_dict": True,
        }
        if token_type_ids is not None:
            kwargs["token_type_ids"] = token_type_ids.to(encoder_device)
        with torch.no_grad():
            outputs = self.encoder(**kwargs)
            states = outputs.hidden_states[self.config.mbert_layer].detach()
        projector_parameter = next(self.projector.parameters())
        projector_device = projector_parameter.device
        projected = self.projector(
            states.to(device=projector_device, dtype=projector_parameter.dtype)
        )
        return projected, attention_mask.to(projector_device)
