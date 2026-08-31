from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

import torch
from torch import nn

from bdh import BDH, BDHConfig

from .cell import StandaloneBDHCell
from .config import BDHCellConfig, SparseWaveConfig
from .wave import SparseWaveSubstrate, WaveCell, WaveResult


CAMPAIGN36C_ORGANISM_SCHEMA = "ninereeds_campaign36c_organism_v1"


@dataclass(frozen=True)
class OrganismConfig:
    """The bounded Stage-8 embryo around the width-512 latent ABI.

    The first real bootstrap deliberately starts with the smallest historical
    continuity-core candidate: four per-layer BDH blocks at multiplier eight.
    It is a 25.4M-parameter resident core, not a reduced copy of Campaign 36A.
    Core sizing remains an experiment and is recorded in every snapshot.
    """

    width: int = 512
    core_layers: int = 4
    core_heads: int = 8
    core_multiplier: int = 8
    seed_ingress_cells: int = 8
    cell_rotary_pairs: int = 2
    initialization_seed: int = 36_008
    dropout: float = 0.0

    def validate(self) -> None:
        positive = (
            self.width,
            self.core_layers,
            self.core_heads,
            self.core_multiplier,
            self.seed_ingress_cells,
            self.cell_rotary_pairs,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("organism dimensions must be positive")
        if self.width % self.core_heads:
            raise ValueError("organism width must be divisible by core heads")
        if self.initialization_seed < 0:
            raise ValueError("organism initialization seed must be non-negative")
        if not 0.0 <= self.dropout < 1.0:
            raise ValueError("organism dropout must be in [0, 1)")

    def core_config(self) -> BDHConfig:
        self.validate()
        return BDHConfig(
            n_layer=self.core_layers,
            n_embd=self.width,
            n_head=self.core_heads,
            mlp_internal_dim_multiplier=self.core_multiplier,
            vocab_size=256,
            per_layer_weights=True,
            dropout=self.dropout,
        )


@dataclass(frozen=True)
class OrganismThought:
    root_state: torch.Tensor
    result: WaveResult


class Campaign36COrganism(nn.Module):
    """A small continuity core feeding one sparse, UID-addressed organism.

    Shared sensory and expression organs live outside this class.  This class
    owns the always-active continuity core and the dynamically growing tissue.
    The core emits one root latent state; it never scores or selects cells.
    Every tissue route begins through the same fixed bounded ingress set.
    """

    def __init__(
        self,
        core: BDH,
        substrate: SparseWaveSubstrate,
        *,
        ingress_uids: Iterable[int],
        config: OrganismConfig,
    ) -> None:
        super().__init__()
        config.validate()
        if core.config.n_embd != config.width:
            raise ValueError("continuity core width does not match organism ABI")
        ingress = tuple(sorted(set(int(uid) for uid in ingress_uids)))
        if len(ingress) != config.seed_ingress_cells:
            raise ValueError("ingress UID count does not match organism configuration")
        for uid in ingress:
            substrate._cell(uid)
        self.core = core
        self.substrate = substrate
        self.ingress_uids = ingress
        self.organism_config = config
        # The byte embedding and byte LM head do not participate in the latent
        # continuity path.  Keeping them frozen prevents an unused parameter
        # family from acquiring optimizer ownership.
        self.core.embed.requires_grad_(False)
        self.core.lm_head.requires_grad_(False)

    @classmethod
    def embryo(
        cls,
        config: OrganismConfig | None = None,
        *,
        wave_config: SparseWaveConfig | None = None,
    ) -> "Campaign36COrganism":
        value = config or OrganismConfig()
        value.validate()
        # Isolate deterministic initialization from the caller's RNG stream.
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(value.initialization_seed)
            core = BDH(value.core_config())
            substrate = SparseWaveSubstrate(wave_config)
            for uid in range(value.seed_ingress_cells):
                cell_config = BDHCellConfig(
                    width=value.width,
                    rotary_pairs=value.cell_rotary_pairs,
                    initialization_seed=value.initialization_seed + 1 + uid,
                )
                substrate.add_cell(
                    WaveCell(
                        StandaloneBDHCell(cell_config, uid=uid),
                        max_degree=min(16, substrate.config.max_degree),
                        max_fanout=min(4, substrate.config.max_fanout),
                    )
                )
        return cls(
            core,
            substrate,
            ingress_uids=range(value.seed_ingress_cells),
            config=value,
        )

    @property
    def core_parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.core.parameters())

    @property
    def trainable_core_parameter_count(self) -> int:
        return sum(
            parameter.numel()
            for parameter in self.core.parameters()
            if parameter.requires_grad
        )

    @property
    def tissue_parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.substrate.parameters())

    def place(
        self,
        *,
        core_device: str | torch.device,
        tissue_device: str | torch.device,
        dtype: torch.dtype = torch.bfloat16,
    ) -> dict[str, Any]:
        self.core.to(device=core_device, dtype=dtype)
        # BDH's rotary-frequency table is a numerical reference buffer, not a
        # model weight.  ``Module.to(dtype=...)`` casts buffers as well as
        # parameters, but Attention deliberately performs its phase arithmetic
        # in float32 (and asserts that contract on every forward pass).
        self.core.attn.freqs = self.core.attn.freqs.to(
            device=core_device,
            dtype=torch.float32,
        )
        self.substrate.to(device=tissue_device, dtype=dtype)
        return self.inventory()

    @property
    def tissue_device(self) -> torch.device:
        return next(self.substrate.parameters()).device

    def continuity_parameters(self) -> tuple[nn.Parameter, ...]:
        return tuple(
            parameter
            for parameter in self.core.parameters()
            if parameter.requires_grad
        )

    def emit_root(self, projected_observation: torch.Tensor) -> torch.Tensor:
        return self.core.encode_embeds(projected_observation)

    def think(
        self,
        projected_observation: torch.Tensor,
        *,
        attention_mask: torch.Tensor | None = None,
        novelty: float = 0.0,
        claim_address: str = "latent:unaddressed",
        evidence_lineage: tuple[str, ...] = (),
        collect_trace: bool = False,
    ) -> OrganismThought:
        root = self.emit_root(projected_observation)
        tissue_root = root.to(self.tissue_device)
        tissue_mask = (
            attention_mask.to(self.tissue_device)
            if attention_mask is not None
            else None
        )
        result = self.substrate.run_thought(
            tissue_root,
            ingress_uids=self.ingress_uids,
            attention_mask=tissue_mask,
            novelty=novelty,
            claim_address=claim_address,
            evidence_lineage=evidence_lineage,
            collect_trace=collect_trace,
        )
        return OrganismThought(root_state=tissue_root, result=result)

    def inventory(self) -> dict[str, Any]:
        core_parameters = self.core_parameter_count
        trainable_core = self.trainable_core_parameter_count
        tissue_parameters = self.tissue_parameter_count
        return {
            "schema_version": CAMPAIGN36C_ORGANISM_SCHEMA,
            "config": asdict(self.organism_config),
            "ingress_uids": list(self.ingress_uids),
            "core": {
                "parameters": core_parameters,
                "trainable_parameters": trainable_core,
                "parameter_bytes": sum(
                    parameter.numel() * parameter.element_size()
                    for parameter in self.core.parameters()
                ),
            },
            "tissue": {
                "active_uids": sorted(int(uid) for uid in self.substrate.cells),
                "active_uid_count": len(self.substrate.cells),
                "parameters": tissue_parameters,
                "parameter_bytes": sum(
                    parameter.numel() * parameter.element_size()
                    for parameter in self.substrate.parameters()
                ),
                "graph_version": self.substrate.graph_version,
                "thought_epoch": self.substrate._thought_epoch,
            },
        }
