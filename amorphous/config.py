from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CellSubstrateConfig:
    """Frozen tensor and execution contract for one amorphous substrate."""

    width: int = 512
    rank: int = 16
    seed_cells: int = 256
    birth_cohort_size: int = 4
    propagation_steps: int = 2
    residual_scale: float = 0.25
    provisional_scale: float = 0.1
    gate_temperature: float = 1.0
    activation_threshold: float = 0.5
    initialization_seed: int = 36002
    max_cells: int = 65_536

    def validate(self) -> None:
        if self.width <= 0:
            raise ValueError("width must be positive")
        if self.rank <= 0 or self.rank > self.width:
            raise ValueError("rank must be positive and no greater than width")
        if self.seed_cells < 0:
            raise ValueError("seed_cells must be non-negative")
        if self.birth_cohort_size <= 0:
            raise ValueError("birth_cohort_size must be positive")
        if self.propagation_steps <= 0:
            raise ValueError("propagation_steps must be positive")
        if not 0.0 < self.residual_scale <= 1.0:
            raise ValueError("residual_scale must be in (0, 1]")
        if not 0.0 < self.provisional_scale <= 1.0:
            raise ValueError("provisional_scale must be in (0, 1]")
        if self.gate_temperature <= 0:
            raise ValueError("gate_temperature must be positive")
        if not 0.0 <= self.activation_threshold <= 1.0:
            raise ValueError("activation_threshold must be in [0, 1]")
        if self.initialization_seed < 0:
            raise ValueError("initialization_seed must be non-negative")
        if self.max_cells < max(self.seed_cells, 1):
            raise ValueError("max_cells must accommodate the seed population")


@dataclass(frozen=True)
class GrowthPolicyConfig:
    """Preregisterable first-generation cell-birth policy."""

    residual_threshold: float = 0.25
    qualifying_observations: int = 8
    cooldown_observations: int = 8
    require_external_failure: bool = True
    require_capacity_saturation: bool = True

    def validate(self) -> None:
        if self.residual_threshold < 0:
            raise ValueError("residual_threshold must be non-negative")
        if self.qualifying_observations <= 0:
            raise ValueError("qualifying_observations must be positive")
        if self.cooldown_observations < 0:
            raise ValueError("cooldown_observations must be non-negative")
