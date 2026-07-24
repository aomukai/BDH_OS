from __future__ import annotations

import torch
from torch import nn


class IntentionHead(nn.Module):
    """Compress contextual Ninereeds states into a short intention sequence.

    Learned queries attend to Ninereeds' states.  This creates a stable output
    contract whose length does not depend on the input utterance and which can be
    fitted to more than one frozen speech generator later.
    """

    def __init__(self, width: int, num_tokens: int = 8, num_heads: int = 8) -> None:
        super().__init__()
        if width <= 0 or num_tokens <= 0:
            raise ValueError("width and num_tokens must be positive")
        if width % num_heads != 0:
            raise ValueError("width must be divisible by num_heads")
        self.width = width
        self.num_tokens = num_tokens
        self.queries = nn.Parameter(torch.empty(num_tokens, width))
        self.attention = nn.MultiheadAttention(width, num_heads, batch_first=True)
        self.norm = nn.LayerNorm(width)
        nn.init.normal_(self.queries, std=0.02)

    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        if hidden_states.ndim != 3 or hidden_states.size(-1) != self.width:
            raise ValueError(
                f"hidden_states must be [batch, sequence, {self.width}], "
                f"got {tuple(hidden_states.shape)}"
            )
        batch = hidden_states.size(0)
        queries = self.queries.unsqueeze(0).expand(batch, -1, -1)
        key_padding_mask = None
        if attention_mask is not None:
            if attention_mask.shape != hidden_states.shape[:2]:
                raise ValueError("attention_mask must match batch and sequence dimensions")
            key_padding_mask = ~attention_mask.to(dtype=torch.bool)
        attended, _ = self.attention(
            queries,
            hidden_states,
            hidden_states,
            key_padding_mask=key_padding_mask,
            need_weights=False,
        )
        return self.norm(attended + queries)
