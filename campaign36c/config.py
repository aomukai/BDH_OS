from __future__ import annotations

from dataclasses import dataclass


CAMPAIGN36C_LATENT_ABI = "ninereeds_width512_latent_abi_v0"
CAMPAIGN36C_CELL_ABI = "ninereeds_campaign36c_bdh_cell_v0"
CAMPAIGN36C_WAVE_ABI = "ninereeds_campaign36c_sparse_wave_v0"


@dataclass(frozen=True)
class BDHCellConfig:
    """Mechanical contract for one independently executable 36C cell.

    ``rotary_pairs`` is the logical cohort-size variable from the Campaign 36C
    handoff.  Every pair owns two aligned multiplicative gates.
    """

    width: int = 512
    rotary_pairs: int = 8
    residual_scale: float = 0.25
    rope_theta: float = float(2**16)
    normalization_epsilon: float = 1e-5
    initialization_seed: int = 36_003
    latent_abi: str = CAMPAIGN36C_LATENT_ABI
    cell_abi: str = CAMPAIGN36C_CELL_ABI

    @property
    def gate_width(self) -> int:
        return 2 * self.rotary_pairs

    def validate(self) -> None:
        if self.width <= 0:
            raise ValueError("width must be positive")
        if self.rotary_pairs <= 0:
            raise ValueError("rotary_pairs must be positive")
        if not 0.0 < self.residual_scale <= 1.0:
            raise ValueError("residual_scale must be in (0, 1]")
        if self.rope_theta <= 1.0:
            raise ValueError("rope_theta must be greater than one")
        if self.normalization_epsilon <= 0:
            raise ValueError("normalization_epsilon must be positive")
        if self.initialization_seed < 0:
            raise ValueError("initialization_seed must be non-negative")
        if not self.latent_abi or not self.cell_abi:
            raise ValueError("latent_abi and cell_abi must be non-empty")


@dataclass(frozen=True)
class CellOptimizerConfig:
    """Explicit UID-local full-moment optimizer policy for Stage 1.

    Factored moments in the existing dense Cortex can cross neuron ownership
    boundaries.  The first independent cell therefore uses ordinary AdamW
    moments that are wholly owned by that cell.
    """

    learning_rate: float = 3e-3
    betas: tuple[float, float] = (0.9, 0.999)
    epsilon: float = 1e-8
    weight_decay: float = 0.0
    amsgrad: bool = False
    policy: str = "torch_adamw_uid_local_full_moments_v1"

    def validate(self) -> None:
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if len(self.betas) != 2 or not all(0.0 <= value < 1.0 for value in self.betas):
            raise ValueError("betas must contain two values in [0, 1)")
        if self.epsilon <= 0:
            raise ValueError("epsilon must be positive")
        if self.weight_decay < 0:
            raise ValueError("weight_decay must be non-negative")
        if self.policy != "torch_adamw_uid_local_full_moments_v1":
            raise ValueError(f"unsupported optimizer policy: {self.policy}")


@dataclass(frozen=True)
class ReceptorConfig:
    """Cheap, independently calibrated admission thresholds for one cell."""

    temperature: float = 0.25
    route_content_threshold: float = 0.60
    write_familiarity_threshold: float = 0.80
    write_coverage_threshold: float = 0.75
    known_route_threshold: float = 0.70
    initialization_seed: int = 36_020

    def validate(self) -> None:
        if self.temperature <= 0:
            raise ValueError("temperature must be positive")
        for name in (
            "route_content_threshold",
            "write_familiarity_threshold",
            "write_coverage_threshold",
            "known_route_threshold",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.route_content_threshold > self.write_familiarity_threshold:
            raise ValueError("route threshold cannot exceed the write threshold")
        if self.initialization_seed < 0:
            raise ValueError("initialization_seed must be non-negative")


@dataclass(frozen=True)
class SparseWaveConfig:
    """Fixed-graph limits for the Campaign 36C physical wave experiment.

    The limits are deliberately mechanical.  They guard serviceability and
    prevent Campaign 36B-style dense activation; they are not a claim that a
    tiny thought should outrun a fully resident transformer.
    """

    initial_route_energy: float = 64.0
    receptor_probe_cost: float = 0.05
    full_transform_cost: float = 1.0
    route_only_cost: float = 0.05
    branch_energy_floor: float = 0.10
    max_waves: int = 32
    max_total_activations: int = 256
    max_receptor_probes: int = 1_024
    max_frontier_width: int = 64
    max_degree: int = 16
    max_fanout: int = 4
    max_uid_activations: int = 3
    provenance_hops: int = 8
    provenance_tails: int = 4
    accumulation_dtype: str = "float32"
    wave_abi: str = CAMPAIGN36C_WAVE_ABI

    def validate(self) -> None:
        positive_floats = (
            "initial_route_energy",
            "receptor_probe_cost",
            "full_transform_cost",
            "route_only_cost",
            "branch_energy_floor",
        )
        for name in positive_floats:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        positive_ints = (
            "max_waves",
            "max_total_activations",
            "max_receptor_probes",
            "max_frontier_width",
            "max_degree",
            "max_fanout",
            "max_uid_activations",
            "provenance_hops",
            "provenance_tails",
        )
        for name in positive_ints:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_fanout > self.max_degree:
            raise ValueError("max_fanout cannot exceed max_degree")
        if self.accumulation_dtype not in {"float32", "float64"}:
            raise ValueError("accumulation_dtype must be float32 or float64")
        if not self.wave_abi:
            raise ValueError("wave_abi must be non-empty")
