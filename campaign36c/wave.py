from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any

import torch
import torch.nn.functional as F
from torch import nn

from .cell import StandaloneBDHCell, batched_cell_transform
from .config import ReceptorConfig, SparseWaveConfig
from .epistemics import (
    EligibilityRecord,
    LatentPatch,
    PatchReducer,
    ReceiptDisposition,
    ReceiptRecord,
    ResolutionEnvelope,
    make_latent_patch,
)


class Admission(str, Enum):
    REJECT = "reject"
    ROUTE_ONLY = "route_only"
    WRITE = "write"


class WaveStatus(str, Enum):
    QUIESCENT = "quiescent"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True)
class ReceptorAssessment:
    admission: Admission
    familiarity: float
    coverage: float
    unresolved_residual: float
    route_familiarity: float


@dataclass(frozen=True)
class NeighborPort:
    destination_uid: int
    conductance: float = 1.0
    route_familiarity: float = 0.5
    enabled: bool = True
    entry_alias_uid: int | None = None

    def validate(self) -> None:
        if self.destination_uid < 0:
            raise ValueError("destination_uid must be non-negative")
        if self.conductance <= 0:
            raise ValueError("conductance must be positive")
        if not 0.0 <= self.route_familiarity <= 1.0:
            raise ValueError("route_familiarity must be in [0, 1]")
        if self.entry_alias_uid is not None and self.entry_alias_uid < 0:
            raise ValueError("entry_alias_uid must be non-negative")


@dataclass(frozen=True)
class WaveRNA:
    """Bounded per-wave evidence; never a persistent episode log."""

    thought_epoch: int
    wave_index: int
    state: torch.Tensor
    route_energy: float
    root_signature: torch.Tensor
    direct_predecessors: tuple[int, ...]
    provenance_tails: tuple[tuple[int, ...], ...]
    novelty: float = 0.0
    write_authorized: bool = True
    entry_alias_uid: int | None = None
    ownership: float = 1.0
    coverage: float = 1.0
    unresolved_residual: float = 0.0
    dependency_patch_ids: tuple[str, ...] = ()
    evidence_lineage: tuple[str, ...] = ()
    claim_address: str = "latent:unaddressed"
    expected_merge_mode: str = "single_value"


@dataclass(frozen=True)
class _Transmission:
    sender_uid: int
    destination_uid: int
    rna: WaveRNA


@dataclass
class WaveTelemetry:
    unique_uids: set[int] = field(default_factory=set)
    activation_sequence: list[int] = field(default_factory=list)
    total_activations: int = 0
    recurrent_activations: int = 0
    recurrence_suppressed: int = 0
    full_transforms: int = 0
    route_only_activations: int = 0
    receptor_probes: int = 0
    receptor_acceptances: int = 0
    receptor_rejections: int = 0
    convergence_groups: int = 0
    transmissions: int = 0
    terminations: int = 0
    hardware_transform_batches: int = 0
    composite_activations: int = 0
    constituent_full_transforms: int = 0
    saved_dispatch_boundaries: int = 0
    stale_route_references: int = 0
    energy_consumed: float = 0.0
    terminal_energy: float = 0.0
    energy_conservation_error: float = 0.0
    frontier_widths: list[int] = field(default_factory=list)
    wave_depth: int = 0
    peak_frontier_width: int = 0
    exhaustion_reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["unique_uids"] = sorted(self.unique_uids)
        result["unique_uid_count"] = len(self.unique_uids)
        widths = self.frontier_widths
        result["mean_frontier_width"] = (
            sum(widths) / len(widths) if widths else 0.0
        )
        return result


@dataclass(frozen=True)
class WaveResult:
    state: torch.Tensor
    status: WaveStatus
    terminal_count: int
    telemetry: dict[str, Any]
    trace: tuple[dict[str, Any], ...]
    resolution: ResolutionEnvelope
    patches: tuple[LatentPatch, ...]
    eligibility: tuple[EligibilityRecord, ...]
    receipts: tuple[ReceiptRecord, ...]

    @property
    def naturally_quiescent(self) -> bool:
        return self.status is WaveStatus.QUIESCENT


class IngressReceptor(nn.Module):
    """A cheap local receptor evaluated before a destination's BDH cell.

    Familiarity, coverage, and residual use separate learned directions.  The
    values are therefore not forced to be complements or folded into one gate.
    """

    def __init__(
        self,
        *,
        width: int,
        uid: int,
        config: ReceptorConfig | None = None,
    ) -> None:
        super().__init__()
        if width <= 0 or uid < 0:
            raise ValueError("width must be positive and uid non-negative")
        self.width = width
        self.uid = uid
        self.config = config or ReceptorConfig()
        self.config.validate()
        generator = torch.Generator(device="cpu")
        generator.manual_seed(self.config.initialization_seed + uid)
        self.content_prototype = nn.Parameter(torch.empty(width))
        self.coverage_prototype = nn.Parameter(torch.empty(width))
        self.residual_prototype = nn.Parameter(torch.empty(width))
        self.register_buffer("calibration_bias", torch.zeros(()), persistent=True)
        with torch.no_grad():
            self.content_prototype.normal_(generator=generator)
            self.coverage_prototype.normal_(generator=generator)
            self.residual_prototype.normal_(generator=generator)

    @torch.no_grad()
    def tune_to(
        self,
        state: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        *,
        residual_direction: torch.Tensor | None = None,
    ) -> None:
        """Set deterministic laboratory prototypes from one representative state."""

        pooled = _pool_states(state.unsqueeze(0), attention_mask)[0]
        self.content_prototype.copy_(pooled.to(self.content_prototype))
        self.coverage_prototype.copy_(pooled.to(self.coverage_prototype))
        if residual_direction is not None:
            if residual_direction.shape != (self.width,):
                raise ValueError("residual_direction must match receptor width")
            self.residual_prototype.copy_(
                residual_direction.to(self.residual_prototype)
            )


def _pool_states(
    states: torch.Tensor,
    attention_masks: torch.Tensor | None,
) -> torch.Tensor:
    if states.ndim != 4:
        raise ValueError("states must have shape [offer,batch,token,width]")
    if states.size(1) != 1:
        raise ValueError("the Stage-2 wave protocol carries one thought per RNA")
    normalized = F.layer_norm(states, (states.size(-1),))
    if attention_masks is None:
        return normalized.mean(dim=(1, 2))
    if attention_masks.ndim == 2:
        attention_masks = attention_masks.unsqueeze(0).expand(
            states.size(0), -1, -1
        )
    if attention_masks.shape != states.shape[:3]:
        raise ValueError("attention masks must match offer, batch, and token")
    weights = attention_masks.to(device=states.device, dtype=states.dtype).unsqueeze(-1)
    return (normalized * weights).sum(dim=(1, 2)) / weights.sum(
        dim=(1, 2)
    ).clamp_min(1)


def probe_receptors(
    receptors: Sequence[IngressReceptor],
    states: torch.Tensor,
    route_familiarities: Sequence[float],
    attention_masks: torch.Tensor | None = None,
) -> list[ReceptorAssessment]:
    """Vectorized receptor checks for only the locally offered destinations."""

    if not receptors or len(receptors) != states.size(0):
        raise ValueError("one receptor is required for every offered state")
    if len(route_familiarities) != len(receptors):
        raise ValueError("route familiarity count must match receptors")
    width = receptors[0].width
    if states.size(-1) != width:
        raise ValueError("offered state width does not match receptor width")
    for receptor in receptors:
        if receptor.width != width:
            raise ValueError("a receptor batch must have one width")
        if (
            receptor.content_prototype.device != states.device
            or receptor.content_prototype.dtype != states.dtype
        ):
            raise ValueError("receptors and offered states must share device and dtype")

    pooled = _pool_states(states, attention_masks)
    content = torch.stack([r.content_prototype for r in receptors])
    coverage = torch.stack([r.coverage_prototype for r in receptors])
    residual = torch.stack([r.residual_prototype for r in receptors])
    temperatures = torch.tensor(
        [r.config.temperature for r in receptors],
        device=states.device,
        dtype=states.dtype,
    )

    biases = torch.stack([r.calibration_bias for r in receptors]).to(states.dtype)

    def calibrated(prototypes: torch.Tensor) -> torch.Tensor:
        cosine = F.cosine_similarity(pooled, prototypes, dim=-1)
        return torch.sigmoid(cosine / temperatures + biases)

    familiarity_values = calibrated(content).float().detach().cpu().tolist()
    coverage_values = calibrated(coverage).float().detach().cpu().tolist()
    residual_values = calibrated(residual).float().detach().cpu().tolist()
    assessments: list[ReceptorAssessment] = []
    for index, receptor in enumerate(receptors):
        familiarity = familiarity_values[index]
        coverage_value = coverage_values[index]
        route_familiarity = float(route_familiarities[index])
        if (
            familiarity >= receptor.config.write_familiarity_threshold
            and coverage_value >= receptor.config.write_coverage_threshold
        ):
            admission = Admission.WRITE
        elif (
            familiarity >= receptor.config.route_content_threshold
            or route_familiarity >= receptor.config.known_route_threshold
        ):
            admission = Admission.ROUTE_ONLY
        else:
            admission = Admission.REJECT
        assessments.append(
            ReceptorAssessment(
                admission=admission,
                familiarity=familiarity,
                coverage=coverage_value,
                unresolved_residual=residual_values[index],
                route_familiarity=route_familiarity,
            )
        )
    return assessments


class WaveCell(nn.Module):
    """One Stage-2 logical cell: receptor, transform, and bounded ports."""

    def __init__(
        self,
        transform: StandaloneBDHCell,
        *,
        receptor_config: ReceptorConfig | None = None,
        max_degree: int = 16,
        max_fanout: int = 4,
        contribution_scale: float = 1.0,
    ) -> None:
        super().__init__()
        if max_degree <= 0 or max_fanout <= 0 or max_fanout > max_degree:
            raise ValueError("degree/fanout limits are invalid")
        if not 0.0 < contribution_scale <= 1.0:
            raise ValueError("contribution_scale must be in (0, 1]")
        self.transform = transform
        self.receptor = IngressReceptor(
            width=transform.config.width,
            uid=transform.uid,
            config=receptor_config,
        )
        self.max_degree = max_degree
        self.max_fanout = max_fanout
        self.register_buffer(
            "contribution_scale",
            torch.tensor(float(contribution_scale)),
            persistent=True,
        )
        self.ports: dict[int, NeighborPort] = {}

    @property
    def uid(self) -> int:
        return self.transform.uid

    def connect(self, port: NeighborPort) -> None:
        port.validate()
        if port.destination_uid not in self.ports and len(self.ports) >= self.max_degree:
            raise ValueError(f"cell {self.uid} has reached its degree bound")
        self.ports[port.destination_uid] = port

    @torch.no_grad()
    def set_contribution_scale(self, value: float) -> None:
        """Set bounded developmental authority without changing cell content."""

        if not 0.0 < value <= 1.0:
            raise ValueError("contribution scale must be in (0, 1]")
        self.contribution_scale.fill_(float(value))


class SparseWaveSubstrate(nn.Module):
    """Fixed in-memory graph implementing the Campaign 36C-0 wave protocol."""

    def __init__(self, config: SparseWaveConfig | None = None) -> None:
        super().__init__()
        self.config = config or SparseWaveConfig()
        self.config.validate()
        self.cells = nn.ModuleDict()
        self.graph_version = 0
        self._thought_epoch = 0
        self._running = False
        self._active_uid_table: dict[int, WaveRNA] = {}
        self.aliases: dict[int, int] = {}
        self.retired_uids: set[int] = set()

    @staticmethod
    def _key(uid: int) -> str:
        if uid < 0:
            raise ValueError("UIDs must be non-negative")
        return str(uid)

    @property
    def ready_for_next_turn(self) -> bool:
        return not self._running and not self._active_uid_table

    def add_cell(self, cell: WaveCell) -> None:
        if self._running:
            raise RuntimeError("the graph snapshot cannot change during a thought")
        key = self._key(cell.uid)
        if cell.uid in self.retired_uids:
            raise ValueError(f"retired UID {cell.uid} cannot be reused")
        if key in self.cells:
            raise ValueError(f"UID {cell.uid} already exists")
        if cell.max_degree > self.config.max_degree:
            raise ValueError("cell degree exceeds substrate governor")
        if cell.max_fanout > self.config.max_fanout:
            raise ValueError("cell fanout exceeds substrate governor")
        self.cells[key] = cell
        self.graph_version += 1

    def connect(
        self,
        source_uid: int,
        destination_uid: int,
        *,
        conductance: float = 1.0,
        route_familiarity: float = 0.5,
        enabled: bool = True,
    ) -> None:
        if self._running:
            raise RuntimeError("the graph snapshot cannot change during a thought")
        source = self._cell(source_uid)
        canonical_destination = self.resolve_uid(destination_uid)
        self._cell(canonical_destination)
        source.connect(
            NeighborPort(
                destination_uid=canonical_destination,
                conductance=conductance,
                route_familiarity=route_familiarity,
                enabled=enabled,
                entry_alias_uid=(
                    destination_uid
                    if destination_uid != canonical_destination
                    else None
                ),
            )
        )
        self.graph_version += 1

    def resolve_uid(self, uid: int) -> int:
        """Resolve an inbound historical UID without changing its provenance."""

        if uid < 0:
            raise ValueError("UIDs must be non-negative")
        path: list[int] = []
        current = uid
        while current in self.aliases:
            if current in path:
                raise RuntimeError("UID alias cycle detected")
            path.append(current)
            current = self.aliases[current]
        for alias in path:
            self.aliases[alias] = current
        return current

    def add_alias(self, alias_uid: int, canonical_uid: int) -> None:
        if not self.ready_for_next_turn:
            raise RuntimeError("alias mutation requires a quiescent substrate")
        canonical = self.resolve_uid(canonical_uid)
        if alias_uid == canonical:
            self.aliases.pop(alias_uid, None)
            return
        if self._key(canonical) not in self.cells:
            raise KeyError(f"unknown canonical Campaign 36C UID {canonical}")
        if self._key(alias_uid) in self.cells:
            raise ValueError("an active canonical UID cannot also be an alias")
        self.aliases[alias_uid] = canonical
        if self.resolve_uid(alias_uid) != canonical:
            raise RuntimeError("UID alias did not resolve to its declared successor")
        self.graph_version += 1

    def resolve_credit_target(self, original_uid: int) -> tuple[int, int]:
        """Return current owner plus immutable historical contribution identity."""

        return self.resolve_uid(original_uid), original_uid

    def has_active_uid(self, uid: int) -> bool:
        """Return whether an address currently resolves to routable tissue.

        Quarantine deliberately leaves bounded stale neighbour memories behind.
        Those references must fail closed during ordinary propagation rather
        than forcing an organism-wide reverse-edge rewrite.
        """

        try:
            canonical = self.resolve_uid(uid)
        except RuntimeError:
            return False
        return self._key(canonical) in self.cells

    def _cell(self, uid: int) -> WaveCell:
        key = self._key(self.resolve_uid(uid))
        if key not in self.cells:
            raise KeyError(f"unknown Campaign 36C cell UID {uid}")
        return self.cells[key]  # type: ignore[return-value]

    def _accumulation_dtype(self) -> torch.dtype:
        return (
            torch.float64
            if self.config.accumulation_dtype == "float64"
            else torch.float32
        )

    def _merge_transmissions(
        self,
        transmissions: Sequence[_Transmission],
        *,
        destination_uid: int,
        wave_index: int,
    ) -> WaveRNA:
        ordered = sorted(
            transmissions,
            key=lambda item: (
                item.sender_uid,
                item.rna.provenance_tails,
                item.rna.write_authorized,
            ),
        )
        total_energy = sum(item.rna.route_energy for item in ordered)
        if total_energy <= 0:
            raise RuntimeError("convergence received no route energy")
        dtype = self._accumulation_dtype()
        accumulator = torch.zeros_like(ordered[0].rna.state, dtype=dtype)
        novelty = 0.0
        for item in ordered:
            weight = item.rna.route_energy / total_energy
            accumulator = accumulator + item.rna.state.to(dtype) * weight
            novelty += item.rna.novelty * weight
        state = accumulator.to(ordered[0].rna.state.dtype)
        predecessors = tuple(sorted({item.sender_uid for item in ordered}))
        tails = sorted(
            {
                tail
                for item in ordered
                for tail in item.rna.provenance_tails
            }
        )[: self.config.provenance_tails]
        dependency_patch_ids = tuple(
            sorted(
                {
                    patch_id
                    for item in ordered
                    for patch_id in item.rna.dependency_patch_ids
                }
            )
        )
        evidence_lineage = tuple(
            sorted(
                {
                    lineage
                    for item in ordered
                    for lineage in item.rna.evidence_lineage
                }
            )
        )
        ownership = sum(
            item.rna.ownership * item.rna.route_energy for item in ordered
        ) / total_energy
        coverage = sum(
            item.rna.coverage * item.rna.route_energy for item in ordered
        ) / total_energy
        unresolved_residual = sum(
            item.rna.unresolved_residual * item.rna.route_energy for item in ordered
        ) / total_energy
        entry_aliases = {
            item.rna.entry_alias_uid
            for item in ordered
            if item.rna.entry_alias_uid is not None
        }
        return WaveRNA(
            thought_epoch=ordered[0].rna.thought_epoch,
            wave_index=wave_index,
            state=state,
            route_energy=total_energy,
            root_signature=ordered[0].rna.root_signature,
            direct_predecessors=predecessors,
            provenance_tails=tuple(tails),
            novelty=novelty,
            write_authorized=any(item.rna.write_authorized for item in ordered),
            entry_alias_uid=(
                next(iter(entry_aliases))
                if len(entry_aliases) == 1
                else destination_uid
            ),
            ownership=ownership,
            coverage=coverage,
            unresolved_residual=unresolved_residual,
            dependency_patch_ids=dependency_patch_ids,
            evidence_lineage=evidence_lineage,
            claim_address=ordered[0].rna.claim_address,
            expected_merge_mode=ordered[0].rna.expected_merge_mode,
        )

    def _execute_write_cells(
        self,
        write_uids: Sequence[int],
        active: dict[int, WaveRNA],
        attention_mask: torch.Tensor | None,
        telemetry: WaveTelemetry,
    ) -> tuple[dict[int, torch.Tensor], dict[int, torch.Tensor]]:
        outputs: dict[int, torch.Tensor] = {}
        deltas: dict[int, torch.Tensor] = {}
        groups: dict[tuple[Any, ...], list[int]] = defaultdict(list)
        composites: list[int] = []
        for uid in write_uids:
            cell = self._cell(uid)
            if hasattr(cell, "execute_composite"):
                composites.append(uid)
                continue
            transform = cell.transform
            config = transform.config
            key = (
                config.width,
                config.gate_width,
                config.residual_scale,
                config.normalization_epsilon,
                transform.encoder.device,
                transform.encoder.dtype,
            )
            groups[key].append(uid)
        for uids in groups.values():
            ordered = sorted(uids)
            transforms = [self._cell(uid).transform for uid in ordered]
            states = torch.stack([active[uid].state for uid in ordered])
            result = batched_cell_transform(transforms, states, attention_mask)
            for index, uid in enumerate(ordered):
                scale = float(self._cell(uid).contribution_scale.item())
                if scale == 1.0:
                    outputs[uid] = result.state[index]
                    deltas[uid] = result.delta[index]
                else:
                    incoming = active[uid].state
                    outputs[uid] = F.layer_norm(
                        incoming + scale * (result.state[index] - incoming),
                        (incoming.size(-1),),
                        eps=transforms[index].config.normalization_epsilon,
                    )
                    deltas[uid] = scale * result.delta[index]
            telemetry.hardware_transform_batches += 1
            telemetry.constituent_full_transforms += len(ordered)
        for uid in sorted(composites):
            cell = self._cell(uid)
            incoming = active[uid].state
            output = cell.execute_composite(  # type: ignore[attr-defined]
                incoming,
                entry_alias_uid=active[uid].entry_alias_uid,
                attention_mask=attention_mask,
            )
            outputs[uid] = output
            deltas[uid] = output - incoming
            leaves = int(getattr(cell, "execution_units", 1))
            telemetry.hardware_transform_batches += 1
            telemetry.composite_activations += 1
            telemetry.constituent_full_transforms += leaves
            telemetry.saved_dispatch_boundaries += max(0, leaves - 1)
        return outputs, deltas

    def run_thought(
        self,
        root_state: torch.Tensor,
        *,
        ingress_uids: int | Iterable[int],
        attention_mask: torch.Tensor | None = None,
        novelty: float = 0.0,
        claim_address: str = "latent:unaddressed",
        expected_merge_mode: str = "single_value",
        evidence_lineage: tuple[str, ...] = (),
        collect_trace: bool = False,
    ) -> WaveResult:
        if self._running:
            raise RuntimeError("this substrate is already executing a thought")
        if root_state.ndim != 3 or root_state.size(0) != 1:
            raise ValueError("root_state must have shape [1, token, width]")
        if attention_mask is not None and attention_mask.shape != root_state.shape[:2]:
            raise ValueError("attention_mask must match root batch and token dimensions")
        ingress = (
            (ingress_uids,) if isinstance(ingress_uids, int) else tuple(ingress_uids)
        )
        ingress = tuple(sorted(set(ingress)))
        if not ingress:
            raise ValueError("at least one ingress UID is required")
        ingress_entries: dict[int, list[int]] = defaultdict(list)
        for entry_uid in ingress:
            canonical_uid = self.resolve_uid(entry_uid)
            ingress_entries[canonical_uid].append(entry_uid)
            cell = self._cell(canonical_uid)
            if cell.transform.config.width != root_state.size(-1):
                raise ValueError("root state and ingress cell widths differ")

        self._running = True
        self._thought_epoch += 1
        epoch = self._thought_epoch
        telemetry = WaveTelemetry()
        trace: list[dict[str, Any]] = []
        terminals: list[WaveRNA] = []
        patches: dict[str, LatentPatch] = {}
        eligibility: list[EligibilityRecord] = []
        receipts: list[ReceiptRecord] = []
        activation_counts: dict[int, int] = defaultdict(int)
        initial_share = self.config.initial_route_energy / len(ingress_entries)
        root_signature = _pool_states(root_state.unsqueeze(0), attention_mask)[0].detach()
        active = {
            uid: WaveRNA(
                thought_epoch=epoch,
                wave_index=0,
                state=root_state,
                route_energy=initial_share,
                root_signature=root_signature,
                direct_predecessors=(),
                provenance_tails=((uid,),),
                novelty=novelty,
                write_authorized=True,
                entry_alias_uid=(
                    uid
                    if uid in entry_uids
                    else min(entry_uids)
                ),
                ownership=1.0,
                coverage=1.0,
                unresolved_residual=novelty,
                dependency_patch_ids=(),
                evidence_lineage=(
                    evidence_lineage
                    if evidence_lineage
                    else (f"thought:{epoch}:root",)
                ),
                claim_address=claim_address,
                expected_merge_mode=expected_merge_mode,
            )
            for uid, entry_uids in sorted(ingress_entries.items())
        }
        status = WaveStatus.QUIESCENT

        def consume(amount: float) -> None:
            telemetry.energy_consumed += amount

        def abort(reason: str, rnas: Iterable[WaveRNA]) -> None:
            nonlocal status
            status = WaveStatus.EXHAUSTED
            telemetry.exhaustion_reason = reason
            terminals.extend(rnas)

        try:
            wave_index = 0
            while active:
                self._active_uid_table = active
                if wave_index >= self.config.max_waves:
                    abort("max_waves", active.values())
                    break
                if len(active) > self.config.max_frontier_width:
                    abort("max_frontier_width", active.values())
                    break
                if (
                    telemetry.total_activations + len(active)
                    > self.config.max_total_activations
                ):
                    abort("max_total_activations", active.values())
                    break

                active_uids = sorted(active)
                telemetry.frontier_widths.append(len(active_uids))
                telemetry.peak_frontier_width = max(
                    telemetry.peak_frontier_width, len(active_uids)
                )
                telemetry.wave_depth = wave_index + 1
                for uid in active_uids:
                    if activation_counts[uid]:
                        telemetry.recurrent_activations += 1
                    activation_counts[uid] += 1
                    telemetry.unique_uids.add(uid)
                    telemetry.activation_sequence.append(uid)
                telemetry.total_activations += len(active_uids)

                write_uids: list[int] = []
                route_only_uids: list[int] = []
                remaining_energy: dict[int, float] = {}
                activation_costs = {
                    uid: (
                        self.config.full_transform_cost
                        * int(getattr(self._cell(uid), "execution_units", 1))
                        if active[uid].write_authorized
                        else self.config.route_only_cost
                    )
                    for uid in active_uids
                }
                if any(
                    active[uid].route_energy + 1e-12 < activation_costs[uid]
                    for uid in active_uids
                ):
                    abort("insufficient_activation_energy", active.values())
                    break
                for uid in active_uids:
                    rna = active[uid]
                    cost = activation_costs[uid]
                    remaining_energy[uid] = rna.route_energy - cost
                    consume(cost)
                    if rna.write_authorized:
                        write_uids.append(uid)
                    else:
                        route_only_uids.append(uid)
                transformed, raw_deltas = self._execute_write_cells(
                    write_uids, active, attention_mask, telemetry
                )
                telemetry.full_transforms += len(write_uids)
                telemetry.route_only_activations += len(route_only_uids)
                output_states = {
                    uid: transformed.get(uid, active[uid].state) for uid in active_uids
                }
                current_patch_ids: dict[int, tuple[str, ...]] = {}
                emitted_patch_ids: dict[int, str] = {}
                for uid in active_uids:
                    if uid not in write_uids:
                        current_patch_ids[uid] = active[uid].dependency_patch_ids
                        continue
                    patch_id = f"thought:{epoch}:wave:{wave_index}:uid:{uid}"
                    operation_delta = output_states[uid] - active[uid].state
                    patch = make_latent_patch(
                        patch_id=patch_id,
                        source_uid=uid,
                        base_version=f"thought:{epoch}:root",
                        claim_address=active[uid].claim_address,
                        expected_merge_mode=active[uid].expected_merge_mode,
                        state_before=active[uid].state,
                        operation_delta=operation_delta,
                        dependency_ids=active[uid].dependency_patch_ids,
                        evidence_lineage=active[uid].evidence_lineage,
                        route_provenance=active[uid].provenance_tails,
                        ownership=active[uid].ownership,
                        coverage=active[uid].coverage,
                    )
                    patches[patch_id] = patch
                    emitted_patch_ids[uid] = patch_id
                    current_patch_ids[uid] = tuple(
                        sorted({*active[uid].dependency_patch_ids, patch_id})
                    )
                current_rnas = {
                    uid: replace(
                        active[uid],
                        state=output_states[uid],
                        route_energy=remaining_energy[uid],
                        dependency_patch_ids=current_patch_ids[uid],
                    )
                    for uid in active_uids
                }

                candidates: list[tuple[int, NeighborPort]] = []
                recurrence_blocked_by_source: dict[int, int] = defaultdict(int)
                for uid in active_uids:
                    cell = self._cell(uid)
                    predecessors = set(active[uid].direct_predecessors)
                    for destination_uid in sorted(cell.ports):
                        port = cell.ports[destination_uid]
                        if (
                            not port.enabled
                            or destination_uid == uid
                            or destination_uid in predecessors
                        ):
                            continue
                        if not self.has_active_uid(port.destination_uid):
                            telemetry.stale_route_references += 1
                            continue
                        if (
                            activation_counts[destination_uid]
                            >= self.config.max_uid_activations
                        ):
                            telemetry.recurrence_suppressed += 1
                            recurrence_blocked_by_source[uid] += 1
                            continue
                        candidates.append((uid, port))

                if (
                    telemetry.receptor_probes + len(candidates)
                    > self.config.max_receptor_probes
                ):
                    abort(
                        "max_receptor_probes",
                        (current_rnas[uid] for uid in active_uids),
                    )
                    break

                candidate_counts: dict[int, int] = defaultdict(int)
                for source_uid, _ in candidates:
                    candidate_counts[source_uid] += 1
                energy_short = [
                    uid
                    for uid, count in candidate_counts.items()
                    if remaining_energy[uid]
                    + 1e-12
                    < count * self.config.receptor_probe_cost
                ]
                if energy_short:
                    abort(
                        "insufficient_probe_energy",
                        (current_rnas[uid] for uid in active_uids),
                    )
                    break

                for uid, count in candidate_counts.items():
                    cost = count * self.config.receptor_probe_cost
                    remaining_energy[uid] -= cost
                    consume(cost)
                    current_rnas[uid] = replace(
                        current_rnas[uid], route_energy=remaining_energy[uid]
                    )
                telemetry.receptor_probes += len(candidates)

                assessments: list[ReceptorAssessment] = []
                if candidates:
                    receptors = [
                        (
                            self._cell(port.destination_uid).receptor_for(
                                port.entry_alias_uid or port.destination_uid
                            )
                            if hasattr(
                                self._cell(port.destination_uid), "receptor_for"
                            )
                            else self._cell(port.destination_uid).receptor
                        )
                        for _, port in candidates
                    ]
                    offered_states = torch.stack(
                        [output_states[source_uid] for source_uid, _ in candidates]
                    )
                    route_familiarities = [
                        port.route_familiarity for _, port in candidates
                    ]
                    assessments = probe_receptors(
                        receptors,
                        offered_states,
                        route_familiarities,
                        attention_mask,
                    )

                accepted_by_source: dict[
                    int, list[tuple[NeighborPort, ReceptorAssessment, float]]
                ] = defaultdict(list)
                offer_trace: list[dict[str, Any]] = []
                for (source_uid, port), assessment in zip(candidates, assessments):
                    accepted = assessment.admission is not Admission.REJECT
                    if accepted:
                        telemetry.receptor_acceptances += 1
                        score = port.conductance * max(
                            assessment.familiarity, assessment.route_familiarity
                        )
                        accepted_by_source[source_uid].append(
                            (port, assessment, score)
                        )
                    else:
                        telemetry.receptor_rejections += 1
                        receipts.append(
                            ReceiptRecord(
                                thought_epoch=epoch,
                                wave_index=wave_index,
                                source_uid=source_uid,
                                destination_uid=port.destination_uid,
                                disposition=ReceiptDisposition.REJECTED,
                                ownership=assessment.familiarity,
                                coverage=assessment.coverage,
                                unresolved_residual=assessment.unresolved_residual,
                            )
                        )
                    if collect_trace:
                        offer_trace.append(
                            {
                                "source_uid": source_uid,
                                "destination_uid": port.destination_uid,
                                "admission": assessment.admission.value,
                                "familiarity": assessment.familiarity,
                                "coverage": assessment.coverage,
                                "unresolved_residual": assessment.unresolved_residual,
                                "route_familiarity": assessment.route_familiarity,
                            }
                        )

                outgoing: dict[int, list[_Transmission]] = defaultdict(list)
                for uid in active_uids:
                    options = sorted(
                        accepted_by_source.get(uid, []),
                        key=lambda item: (-item[2], item[0].destination_uid),
                    )[: self._cell(uid).max_fanout]
                    emitted_destinations: list[int] = []
                    if not options:
                        terminals.append(current_rnas[uid])
                        telemetry.terminations += 1
                    else:
                        score_total = sum(option[2] for option in options)
                        for port, assessment, score in options:
                            share = remaining_energy[uid] * score / score_total
                            if share < self.config.branch_energy_floor:
                                terminals.append(
                                    replace(current_rnas[uid], route_energy=share)
                                )
                                telemetry.terminations += 1
                                continue
                            tails = tuple(
                                sorted(
                                    {
                                        (*tail, port.destination_uid)[
                                            -self.config.provenance_hops :
                                        ]
                                        for tail in active[uid].provenance_tails
                                    }
                                )[: self.config.provenance_tails]
                            )
                            child = WaveRNA(
                                thought_epoch=epoch,
                                wave_index=wave_index + 1,
                                state=output_states[uid],
                                route_energy=share,
                                root_signature=active[uid].root_signature,
                                direct_predecessors=(uid,),
                                provenance_tails=tails,
                                novelty=active[uid].novelty,
                                write_authorized=assessment.admission is Admission.WRITE,
                                entry_alias_uid=(
                                    port.entry_alias_uid or port.destination_uid
                                ),
                                ownership=assessment.familiarity,
                                coverage=assessment.coverage,
                                unresolved_residual=assessment.unresolved_residual,
                                dependency_patch_ids=current_patch_ids[uid],
                                evidence_lineage=active[uid].evidence_lineage,
                                claim_address=active[uid].claim_address,
                                expected_merge_mode=active[uid].expected_merge_mode,
                            )
                            outgoing[port.destination_uid].append(
                                _Transmission(uid, port.destination_uid, child)
                            )
                            emitted_destinations.append(port.destination_uid)
                            telemetry.transmissions += 1

                    disposition = (
                        ReceiptDisposition.FORWARDED
                        if emitted_destinations
                        else ReceiptDisposition.UNRESOLVED
                        if active[uid].novelty >= 0.5
                        else ReceiptDisposition.ABSORBED
                    )
                    for predecessor in active[uid].direct_predecessors:
                        receipts.append(
                            ReceiptRecord(
                                thought_epoch=epoch,
                                wave_index=wave_index,
                                source_uid=predecessor,
                                destination_uid=uid,
                                disposition=disposition,
                                ownership=active[uid].ownership,
                                coverage=active[uid].coverage,
                                unresolved_residual=active[uid].unresolved_residual,
                            )
                        )
                    eligibility.append(
                        EligibilityRecord(
                            thought_epoch=epoch,
                            wave_index=wave_index,
                            uid=uid,
                            patch_id=(
                                emitted_patch_ids.get(uid)
                            ),
                            direct_predecessors=active[uid].direct_predecessors,
                            dependency_patch_ids=active[uid].dependency_patch_ids,
                            outgoing_destinations=tuple(sorted(emitted_destinations)),
                            ownership=active[uid].ownership,
                            coverage=active[uid].coverage,
                            unresolved_residual=active[uid].unresolved_residual,
                            delta_norm=(
                                float(raw_deltas[uid].detach().float().norm().cpu())
                                if uid in write_uids
                                else 0.0
                            ),
                            full_transform=uid in write_uids,
                            disposition=disposition,
                        )
                    )

                next_active: dict[int, WaveRNA] = {}
                for destination_uid in sorted(outgoing):
                    messages = outgoing[destination_uid]
                    if len(messages) > 1:
                        telemetry.convergence_groups += 1
                    next_active[destination_uid] = self._merge_transmissions(
                        messages,
                        destination_uid=destination_uid,
                        wave_index=wave_index + 1,
                    )
                if len(next_active) > self.config.max_frontier_width:
                    abort("max_frontier_width", next_active.values())
                    break

                if collect_trace:
                    trace.append(
                        {
                            "wave_index": wave_index,
                            "active_uids": active_uids,
                            "write_uids": sorted(write_uids),
                            "route_only_uids": sorted(route_only_uids),
                            "offers": offer_trace,
                            "next_uids": sorted(next_active),
                            "graph_version": self.graph_version,
                        }
                    )
                active = next_active
                wave_index += 1

            telemetry.terminal_energy = sum(rna.route_energy for rna in terminals)
            telemetry.energy_conservation_error = abs(
                self.config.initial_route_energy
                - telemetry.energy_consumed
                - telemetry.terminal_energy
            )
            if terminals:
                ordered_terminals = sorted(
                    terminals,
                    key=lambda rna: (rna.provenance_tails, rna.entry_alias_uid or -1),
                )
                total = telemetry.terminal_energy
                dtype = self._accumulation_dtype()
                if total > 0:
                    result_state = torch.zeros_like(root_state, dtype=dtype)
                    for terminal in ordered_terminals:
                        result_state = result_state + terminal.state.to(dtype) * (
                            terminal.route_energy / total
                        )
                    result_state = result_state.to(root_state.dtype)
                else:
                    result_state = torch.stack(
                        [terminal.state for terminal in ordered_terminals]
                    ).mean(dim=0)
            else:
                result_state = root_state
            terminal_patch_ids = tuple(
                sorted(
                    {
                        patch_id
                        for terminal in terminals
                        for patch_id in terminal.dependency_patch_ids
                    }
                )
            )
            resolution = PatchReducer().reduce(
                tuple(patches.values()),
                terminal_patch_ids=terminal_patch_ids,
                exhausted=status is WaveStatus.EXHAUSTED,
            )
            return WaveResult(
                state=result_state,
                status=status,
                terminal_count=len(terminals),
                telemetry=telemetry.as_dict(),
                trace=tuple(trace),
                resolution=resolution,
                patches=tuple(sorted(patches.values(), key=lambda patch: patch.patch_id)),
                eligibility=tuple(eligibility),
                receipts=tuple(receipts),
            )
        finally:
            self._active_uid_table = {}
            self._running = False
