from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisualModel:
    """A pinned external model used by the visual curriculum toolchain."""

    repo_id: str
    revision: str
    role: str
    gated: bool = False
    ignore_patterns: tuple[str, ...] = ()


# Keep these revisions explicit. A changed receptor or judge is a changed
# experiment, even when the upstream repository keeps the same friendly name.
VISUAL_MODELS: dict[str, VisualModel] = {
    "flux4b": VisualModel(
        repo_id="black-forest-labs/FLUX.2-klein-4B",
        revision="e7b7dc27f91deacad38e78976d1f2b499d76a294",
        role="default local curriculum image generator",
        # The repository publishes the transformer twice: once as a standalone
        # checkpoint and once in Diffusers layout. Keep only Diffusers assets.
        ignore_patterns=(
            "flux-2-klein-4b.safetensors",
            "*.jpg",
            "*.png",
        ),
    ),
    "flux9b": VisualModel(
        repo_id="black-forest-labs/FLUX.2-klein-9B",
        revision="92196c8e11f7b6cf2b7493e037d8c5345c559216",
        role="optional quality benchmark image generator",
        gated=True,
        ignore_patterns=(
            "flux-2-klein-9b.safetensors",
            "*.jpg",
            "*.png",
        ),
    ),
    "siglip2": VisualModel(
        repo_id="google/siglip2-base-patch16-naflex",
        revision="b53b807d3a2d5e2b3911292f2d69e5341cdc064c",
        role="permanent frozen visual receptor",
    ),
    "gemma": VisualModel(
        repo_id="google/gemma-4-E4B-it",
        revision="ee0ef6023621cff504d758262d4e04895a5af4a2",
        role="local multimodal image-quality judge",
    ),
    "gemma_e2b": VisualModel(
        repo_id="google/gemma-4-E2B-it",
        revision="3e22461f65e89153144f8adb70e3b8c2cc9845a7",
        role="full-precision single-GPU instruction-tuned visual-judge bakeoff candidate",
    ),
}

DEFAULT_VISUAL_MODELS = ("flux4b", "siglip2", "gemma")
