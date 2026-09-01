from __future__ import annotations

from dataclasses import dataclass


CORTEX_ARCHITECTURE = (
    "lfm2_5_encoder_230m_frozen__ninereeds_1_2b__lfm2_5_230m_frozen"
)


@dataclass(frozen=True)
class CortexConfig:
    """Model IDs and stable dimensional contracts for the LFM Cortex."""

    encoder_model_id: str = "LiquidAI/LFM2.5-Encoder-230M"
    encoder_revision: str = "0b649ad0c684378b03d4d8304f7577a662ab89bc"
    encoder_width: int = 1024
    encoder_layer: int = -1
    encoder_num_hidden_layers: int = 14
    encoder_max_length: int = 512
    lfm_model_id: str = "LiquidAI/LFM2.5-230M"
    lfm_revision: str = "37b30cce3446f3f2e26a0d3f8c67c9167f5079d7"
    lfm_width: int = 1024
    intention_tokens: int = 8

    def validate_for_ninereeds(self, ninereeds_width: int) -> None:
        if ninereeds_width <= 0:
            raise ValueError("ninereeds_width must be positive")
        if self.encoder_width <= 0:
            raise ValueError("encoder_width must be positive")
        if self.encoder_num_hidden_layers <= 0:
            raise ValueError("encoder_num_hidden_layers must be positive")
        if not -1 <= self.encoder_layer <= self.encoder_num_hidden_layers:
            raise ValueError(
                "encoder_layer must be -1 or a hidden-state index between 0 and "
                "encoder_num_hidden_layers"
            )
        if self.encoder_max_length <= 0 or self.encoder_max_length > 8192:
            raise ValueError("encoder_max_length must be between 1 and 8192")
        if self.intention_tokens <= 0:
            raise ValueError("intention_tokens must be positive")
