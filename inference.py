from __future__ import annotations

from pathlib import Path
from typing import Iterable

import torch

from bdh import BDH, BDHConfig


class BDHInference:
    """Minimal wrapper for loading BDH and running generation.

    Assumptions:
    - The checkpoint is compatible with BDH(BDHConfig())
    - Tokenization is byte-level because vocab_size defaults to 256
    """

    def __init__(
        self,
        checkpoint_path: str | Path,
        *,
        max_new_tokens: int = 96,
        temperature: float = 0.8,
        top_k: int | None = 40,
        device: str | None = None,
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path)
        if not self.checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {self.checkpoint_path}")

        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_k = top_k
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))

        self.model = self._load_model()
        self.model.eval()

    def _load_model(self) -> BDH:
        model = BDH(BDHConfig())
        checkpoint = torch.load(self.checkpoint_path, map_location=self.device)

        if isinstance(checkpoint, dict):
            if "model" in checkpoint and isinstance(checkpoint["model"], dict):
                state_dict = checkpoint["model"]
            elif "state_dict" in checkpoint and isinstance(checkpoint["state_dict"], dict):
                state_dict = checkpoint["state_dict"]
            else:
                state_dict = checkpoint
        else:
            raise TypeError("Unsupported checkpoint format: expected dict-like object")

        model.load_state_dict(state_dict, strict=False)
        model.to(self.device)
        return model

    @staticmethod
    def _encode_bytes(text: str) -> list[int]:
        return list(text.encode("utf-8", errors="replace"))

    @staticmethod
    def _decode_bytes(tokens: Iterable[int]) -> str:
        return bytes(int(t) % 256 for t in tokens).decode("utf-8", errors="replace")

    def generate_text(self, prompt: str) -> str:
        token_ids = self._encode_bytes(prompt)
        idx = torch.tensor([token_ids], dtype=torch.long, device=self.device)
        out = self.model.generate(
            idx,
            max_new_tokens=self.max_new_tokens,
            temperature=self.temperature,
            top_k=self.top_k,
        )
        decoded = self._decode_bytes(out[0].tolist())

        if decoded.startswith(prompt):
            return decoded[len(prompt) :].strip() or decoded.strip()
        return decoded.strip()
