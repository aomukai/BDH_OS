from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

import torch
from torch import nn

from .config import CortexConfig


def _transformers_major_version() -> int:
    try:
        return int(version("transformers").split(".", 1)[0])
    except (PackageNotFoundError, ValueError):
        return 0


class LFMExpressionCortex(nn.Module):
    """Frozen LFM speech cortex driven only by Ninereeds intention vectors."""

    def __init__(
        self,
        ninereeds_width: int,
        *,
        config: CortexConfig | None = None,
        dtype: torch.dtype | None = None,
        local_files_only: bool = False,
    ) -> None:
        super().__init__()
        if _transformers_major_version() < 5:
            raise RuntimeError(
                "LFM2.5 requires Transformers 5.x. Use the isolated cortex environment."
            )
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "LFMExpressionCortex requires the cortex environment; "
                "install cortex/requirements.txt"
            ) from exc

        cfg = config or CortexConfig()
        cfg.validate_for_ninereeds(ninereeds_width)
        self.config = cfg
        self.tokenizer = AutoTokenizer.from_pretrained(
            cfg.lfm_model_id,
            local_files_only=local_files_only,
        )
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        model_kwargs: dict[str, Any] = {"local_files_only": local_files_only}
        if dtype is not None:
            model_kwargs["dtype"] = dtype
        self.model = AutoModelForCausalLM.from_pretrained(cfg.lfm_model_id, **model_kwargs)
        self.model.requires_grad_(False)
        self.model.eval()
        self.projector = nn.Sequential(
            nn.LayerNorm(ninereeds_width),
            nn.Linear(ninereeds_width, cfg.lfm_width),
        )

    def train(self, mode: bool = True) -> "LFMExpressionCortex":
        super().train(mode)
        self.model.eval()
        return self

    def prefix_embeddings(self, intentions: torch.Tensor) -> torch.Tensor:
        if intentions.ndim != 3:
            raise ValueError("intentions must have shape [batch, tokens, width]")
        return self.projector(intentions)

    def response_loss(
        self,
        intentions: torch.Tensor,
        response_input_ids: torch.Tensor,
        response_attention_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Teacher-force a response while masking all virtual intention positions."""
        prefix = self.prefix_embeddings(intentions)
        model_parameter = next(self.model.parameters())
        model_device = model_parameter.device
        prefix = prefix.to(device=model_device, dtype=model_parameter.dtype)
        response_input_ids = response_input_ids.to(model_device)
        if response_attention_mask is None:
            response_attention_mask = torch.ones_like(response_input_ids)
        else:
            response_attention_mask = response_attention_mask.to(model_device)

        # The speech model is frozen, but this operation must remain in autograd:
        # gradients pass through LFM into the projector and Ninereeds intentions.
        token_embeddings = self.model.get_input_embeddings()(response_input_ids)
        inputs_embeds = torch.cat([prefix, token_embeddings], dim=1)
        prefix_mask = torch.ones(prefix.shape[:2], dtype=response_attention_mask.dtype, device=model_device)
        attention_mask = torch.cat([prefix_mask, response_attention_mask], dim=1)
        ignore = torch.full(prefix.shape[:2], -100, dtype=response_input_ids.dtype, device=model_device)
        response_labels = response_input_ids.masked_fill(response_attention_mask == 0, -100)
        labels = torch.cat([ignore, response_labels], dim=1)
        outputs = self.model(
            inputs_embeds=inputs_embeds,
            attention_mask=attention_mask,
            labels=labels,
            use_cache=False,
            return_dict=True,
        )
        return outputs.loss

    @torch.no_grad()
    def generate(
        self,
        intentions: torch.Tensor,
        *,
        max_new_tokens: int = 64,
        **generation_kwargs: Any,
    ) -> torch.Tensor:
        prefix = self.prefix_embeddings(intentions)
        model_parameter = next(self.model.parameters())
        model_device = model_parameter.device
        prefix = prefix.to(device=model_device, dtype=model_parameter.dtype)
        attention_mask = torch.ones(prefix.shape[:2], dtype=torch.long, device=model_device)
        return self.model.generate(
            inputs_embeds=prefix,
            attention_mask=attention_mask,
            max_new_tokens=max_new_tokens,
            **generation_kwargs,
        )
