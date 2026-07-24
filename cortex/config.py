from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CortexConfig:
    """Model IDs and stable dimensional contracts for the first cortex probes."""

    mbert_model_id: str = "google-bert/bert-base-multilingual-cased"
    mbert_width: int = 768
    mbert_layer: int = 8
    mbert_max_length: int = 512
    lfm_model_id: str = "LiquidAI/LFM2.5-230M"
    lfm_width: int = 1024
    intention_tokens: int = 8

    def validate_for_ninereeds(self, ninereeds_width: int) -> None:
        if ninereeds_width <= 0:
            raise ValueError("ninereeds_width must be positive")
        if not 0 <= self.mbert_layer <= 12:
            raise ValueError("mbert_layer must be between 0 and 12 inclusive")
        if self.intention_tokens <= 0:
            raise ValueError("intention_tokens must be positive")
