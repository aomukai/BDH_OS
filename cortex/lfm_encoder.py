from __future__ import annotations

from contextlib import contextmanager
from importlib.metadata import PackageNotFoundError, version
import sys
from threading import RLock
from typing import Any

import torch
from torch import nn

from .config import CortexConfig


_LFM_PATCH_LOCK = RLock()


def _transformers_major_version() -> int:
    try:
        return int(version("transformers").split(".", 1)[0])
    except (PackageNotFoundError, ValueError):
        return 0


class LFMEncoderIngress(nn.Module):
    """Frozen bidirectional LFM2.5 with a trainable Ninereeds afferent path."""

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
                "LFM2.5 Encoder requires Transformers 5.x. Use the isolated "
                "cortex environment."
            )
        cfg = config or CortexConfig()
        cfg.validate_for_ninereeds(ninereeds_width)
        try:
            from transformers import AutoModelForMaskedLM, AutoTokenizer
            from transformers.models.lfm2 import modeling_lfm2
        except ImportError as exc:
            raise RuntimeError(
                "LFMEncoderIngress requires the cortex environment; "
                "install cortex/requirements.txt"
            ) from exc

        self.config = cfg
        self.tokenizer = AutoTokenizer.from_pretrained(
            cfg.encoder_model_id,
            revision=cfg.encoder_revision,
            trust_remote_code=True,
            local_files_only=local_files_only,
        )
        self._native_lfm2_module = modeling_lfm2
        self._native_create_causal_mask = modeling_lfm2.create_causal_mask
        self._native_shortconv_forward = modeling_lfm2.Lfm2ShortConv.forward
        self._native_shortconv_slow_forward = modeling_lfm2.Lfm2ShortConv.slow_forward
        model_kwargs: dict[str, Any] = {
            "revision": cfg.encoder_revision,
            "trust_remote_code": True,
            "local_files_only": local_files_only,
        }
        if dtype is not None:
            model_kwargs["dtype"] = dtype
        with _LFM_PATCH_LOCK:
            masked_lm = AutoModelForMaskedLM.from_pretrained(
                cfg.encoder_model_id,
                **model_kwargs,
            )
            self.encoder = masked_lm.lfm2
            self._remote_module = sys.modules[self.encoder.__class__.__module__]
            self._restore_causal_runtime()
        self.encoder.requires_grad_(False)
        self.encoder.eval()
        self.projector = nn.Sequential(
            nn.LayerNorm(cfg.encoder_width),
            nn.Linear(cfg.encoder_width, ninereeds_width),
        )

    def _install_bidirectional_runtime(self) -> None:
        self._native_lfm2_module.create_causal_mask = (
            self._remote_module._bidirectional_mask
        )
        self._native_lfm2_module.Lfm2ShortConv.slow_forward = (
            self._remote_module._noncausal_shortconv_forward
        )
        self._native_lfm2_module.Lfm2ShortConv.forward = (
            self._remote_module._shortconv_forward
        )

    def _restore_causal_runtime(self) -> None:
        self._native_lfm2_module.create_causal_mask = self._native_create_causal_mask
        self._native_lfm2_module.Lfm2ShortConv.slow_forward = (
            self._native_shortconv_slow_forward
        )
        self._native_lfm2_module.Lfm2ShortConv.forward = (
            self._native_shortconv_forward
        )

    @contextmanager
    def _bidirectional_runtime(self):
        with _LFM_PATCH_LOCK:
            self._install_bidirectional_runtime()
            try:
                yield
            finally:
                self._restore_causal_runtime()

    def causal_runtime_is_restored(self) -> bool:
        """Report whether Liquid's process-global patches are currently absent."""
        return (
            self._native_lfm2_module.create_causal_mask
            is self._native_create_causal_mask
            and self._native_lfm2_module.Lfm2ShortConv.forward
            is self._native_shortconv_forward
            and self._native_lfm2_module.Lfm2ShortConv.slow_forward
            is self._native_shortconv_slow_forward
        )

    def train(self, mode: bool = True) -> "LFMEncoderIngress":
        super().train(mode)
        self.encoder.eval()
        return self

    def tokenize(self, texts: list[str] | tuple[str, ...], **overrides: Any) -> dict[str, torch.Tensor]:
        options: dict[str, Any] = {
            "padding": True,
            "truncation": True,
            "max_length": self.config.encoder_max_length,
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
        # LFM2.5 does not consume BERT token-type IDs. The optional argument remains
        # in this boundary so callers can pass tokenizer dictionaries generically.
        with self._bidirectional_runtime(), torch.no_grad():
            outputs = self.encoder(**kwargs)
            states = outputs.hidden_states[self.config.encoder_layer].detach()
        projector_parameter = next(self.projector.parameters())
        projector_device = projector_parameter.device
        projected = self.projector(
            states.to(device=projector_device, dtype=projector_parameter.dtype)
        )
        return projected, attention_mask.to(projector_device)
