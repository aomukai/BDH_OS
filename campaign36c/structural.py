from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

import torch
import torch.nn.functional as F
from torch import nn

from .wave import IngressReceptor, NeighborPort, SparseWaveSubstrate, WaveCell


CAMPAIGN36C_STRUCTURAL_SCHEMA = "ninereeds_campaign36c_structural_event_v0"


class StructuralPressure(str, Enum):
    PACKING = "packing"
    FUSION = "fusion"
    FISSION = "fission"
    REPAIR = "repair"
    BUDDING = "budding"
    REPLACEMENT = "replacement"


class CompositeStage(str, Enum):
    REVERSIBLE = "reversible"
    HEALING = "healing"
    RIGID = "rigid"
    DEOPTIMIZED = "deoptimized"
    RETIRED = "retired"


@dataclass(frozen=True)
class FusionPolicyConfig:
    minimum_rigidity: float = 0.70
    minimum_conductance: float = 0.75
    minimum_conditional_coparticipation: float = 0.80
    maximum_independent_use: float = 0.15
    maximum_recent_error: float = 0.02
    minimum_dispatch_savings: float = 0.05
    behavior_tolerance: float = 1e-5
    maximum_composite_leaves: int = 8
    maximum_fusion_depth: int = 4
    maximum_composite_parameter_bytes: int = 64 * 1024 * 1024
    maximum_seam_regression: float = 1e-4
    rigidity_increment: float = 0.05
    rigidity_error_decrement: float = 0.15
    minimum_negative_transfer: float = 0.01
    minimum_fission_epochs: int = 3
    minimum_fission_lineages: int = 2
    minimum_fission_regimes: int = 2
    semantic_healing_enabled: bool = False

    def validate(self) -> None:
        probabilities = (
            "minimum_rigidity",
            "minimum_conductance",
            "minimum_conditional_coparticipation",
            "maximum_independent_use",
            "maximum_recent_error",
            "minimum_dispatch_savings",
            "rigidity_increment",
            "rigidity_error_decrement",
        )
        for name in probabilities:
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.behavior_tolerance < 0 or self.maximum_seam_regression < 0:
            raise ValueError("behavior tolerances must be non-negative")
        if self.minimum_negative_transfer <= 0:
            raise ValueError("negative-transfer threshold must be positive")
        if min(
            self.maximum_composite_leaves,
            self.maximum_fusion_depth,
            self.maximum_composite_parameter_bytes,
            self.minimum_fission_epochs,
            self.minimum_fission_lineages,
            self.minimum_fission_regimes,
        ) <= 0:
            raise ValueError("structural count and size bounds must be positive")
        if not isinstance(self.semantic_healing_enabled, bool):
            raise ValueError("semantic_healing_enabled must be boolean")


@dataclass(frozen=True)
class ConditionalTrustProfile:
    predecessor_uid: int
    context_key: str
    positive_authority: float
    negative_history: float
    calibration_error: float

    def validate(self) -> None:
        if self.predecessor_uid < 0 or not self.context_key:
            raise ValueError("trust profiles require a UID and context key")
        for name in (
            "positive_authority",
            "negative_history",
            "calibration_error",
        ):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True)
class FusionEvidence:
    left_uid: int
    right_uid: int
    left_lifecycle: str
    right_lifecycle: str
    left_rigidity: float
    right_rigidity: float
    conductance: float
    conditional_coparticipation: float
    left_independent_use: float
    right_independent_use: float
    recent_error: float
    measured_dispatch_savings: float
    thought_epochs: tuple[int, ...]
    evidence_lineages: tuple[str, ...]
    trust_profiles: tuple[ConditionalTrustProfile, ...] = ()

    def validate(self) -> None:
        if self.left_uid < 0 or self.right_uid < 0 or self.left_uid == self.right_uid:
            raise ValueError("fusion evidence requires two distinct UIDs")
        for name in (
            "left_rigidity",
            "right_rigidity",
            "conductance",
            "conditional_coparticipation",
            "left_independent_use",
            "right_independent_use",
            "recent_error",
            "measured_dispatch_savings",
        ):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if len(set(self.thought_epochs)) < 2 or len(set(self.evidence_lineages)) < 2:
            raise ValueError("fusion requires repeated, independently grounded evidence")
        for profile in self.trust_profiles:
            profile.validate()


@dataclass(frozen=True)
class FusionProbe:
    state: torch.Tensor
    entry_uid: int

    def validate(self, width: int) -> None:
        if self.entry_uid < 0 or self.state.ndim != 3 or self.state.size(0) != 1:
            raise ValueError("fusion probes require one thought and a valid entry UID")
        if self.state.size(-1) != width:
            raise ValueError("fusion probe width does not match the candidate")


@dataclass(frozen=True)
class FusionAudit:
    maximum_absolute_difference: float
    probes: int
    leaf_count: int
    fusion_depth: int
    parameter_bytes: int
    passed: bool


@dataclass(frozen=True)
class FusionDecision:
    admitted: bool
    action: str
    successor_uid: int | None
    failed_gates: tuple[str, ...]
    audit: FusionAudit | None


@dataclass(frozen=True)
class HealingProbe:
    state: torch.Tensor
    target_state: torch.Tensor
    entry_uid: int

    def validate(self, width: int) -> None:
        if self.state.shape != self.target_state.shape:
            raise ValueError("healing state and target must have identical shape")
        FusionProbe(self.state, self.entry_uid).validate(width)


@dataclass(frozen=True)
class HealingAuthorization:
    equivalent_addressed_effects: bool
    no_material_independent_residual: bool
    shadow_consolidation_passed: bool
    evidence_lineages: tuple[str, ...]

    def validate(self) -> None:
        if len(set(self.evidence_lineages)) < 2:
            raise ValueError("healing requires independent evidence lineages")
        if not (
            self.equivalent_addressed_effects
            and self.no_material_independent_residual
            and self.shadow_consolidation_passed
        ):
            raise ValueError("semantic healing evidence gates did not pass")


@dataclass(frozen=True)
class RigidityAudit:
    enabled_loss: float
    masked_loss: float
    counterfactual_regression: float
    extractable: bool
    stage: CompositeStage


@dataclass(frozen=True)
class FissionEvidence:
    composite_uid: int
    thought_epochs: tuple[int, ...]
    evidence_lineages: tuple[str, ...]
    regimes: tuple[str, ...]
    negative_transfer: float
    left_regime_useful: bool
    right_regime_useful: bool
    left_boundary_regression: float
    right_boundary_regression: float
    routing_calibrated: bool
    shadow_specialists_win_after_cost: bool
    universally_invalid: bool = False
    successor_obligations_closed: bool = False

    def validate(self) -> None:
        if self.composite_uid < 0 or self.negative_transfer < 0:
            raise ValueError("fission evidence has invalid UID or transfer")
        if self.left_boundary_regression < 0 or self.right_boundary_regression < 0:
            raise ValueError("boundary regressions must be non-negative")


@dataclass(frozen=True)
class FissionDecision:
    admitted: bool
    action: str
    restored_uids: tuple[int, ...]
    retired_successor_uid: int | None
    failed_gates: tuple[str, ...]


@dataclass(frozen=True)
class StructuralEvent:
    sequence: int
    pressure: StructuralPressure
    action: str
    source_uids: tuple[int, ...]
    result_uids: tuple[int, ...]
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CAMPAIGN36C_STRUCTURAL_SCHEMA,
            **asdict(self),
            "pressure": self.pressure.value,
        }


class CoAccessTracker:
    """Bounded co-access evidence for physical repacking only."""

    def __init__(self, *, maximum_pairs: int = 4096) -> None:
        if maximum_pairs <= 0:
            raise ValueError("maximum_pairs must be positive")
        self.maximum_pairs = maximum_pairs
        self._counts: dict[tuple[int, int], int] = {}

    def observe(self, active_uids: Iterable[int]) -> None:
        values = sorted(set(active_uids))
        for index, left in enumerate(values):
            for right in values[index + 1 :]:
                pair = (left, right)
                self._counts[pair] = self._counts.get(pair, 0) + 1
        if len(self._counts) > self.maximum_pairs:
            retained = sorted(
                self._counts.items(), key=lambda item: (-item[1], item[0])
            )[: self.maximum_pairs]
            self._counts = dict(retained)

    def count(self, left_uid: int, right_uid: int) -> int:
        return self._counts.get(tuple(sorted((left_uid, right_uid))), 0)

    def repack_order(self, active_uids: Iterable[int]) -> tuple[int, ...]:
        remaining = set(active_uids)
        order: list[int] = []
        for (left, right), _ in sorted(
            self._counts.items(), key=lambda item: (-item[1], item[0])
        ):
            for uid in (left, right):
                if uid in remaining:
                    order.append(uid)
                    remaining.remove(uid)
        return tuple([*order, *sorted(remaining)])


class RigidityLedger:
    """Participation-conditioned rigidity; inactivity is deliberately a no-op."""

    def __init__(self, policy: FusionPolicyConfig) -> None:
        self.policy = policy
        self._values: dict[int, float] = {}

    def value(self, uid: int) -> float:
        return self._values.get(uid, 0.0)

    def set(self, uid: int, value: float) -> None:
        self._values[uid] = min(1.0, max(0.0, value))

    def record(
        self,
        uid: int,
        *,
        participated: bool,
        low_error: bool = False,
        implicated_error: bool = False,
    ) -> float:
        current = self.value(uid)
        if not participated:
            return current
        if implicated_error:
            current -= self.policy.rigidity_error_decrement
        elif low_error:
            current += self.policy.rigidity_increment
        self.set(uid, current)
        return self.value(uid)


def _identity_uids(cell: WaveCell | ReversibleCompositeCell) -> set[int]:
    if isinstance(cell, ReversibleCompositeCell):
        return set(cell.constituent_uids) | {cell.uid}
    return {cell.uid}


def _execute_cell(
    cell: WaveCell | ReversibleCompositeCell,
    state: torch.Tensor,
    *,
    entry_alias_uid: int,
    attention_mask: torch.Tensor | None,
) -> torch.Tensor:
    if isinstance(cell, ReversibleCompositeCell):
        return cell.execute_composite(
            state,
            entry_alias_uid=entry_alias_uid,
            attention_mask=attention_mask,
        )
    return cell.transform(state, attention_mask)


class ReversibleCompositeTransform(nn.Module):
    """Two isolated constituent executions plus one explicit healing boundary."""

    is_reversible_composite = True

    def __init__(
        self,
        *,
        uid: int,
        left_cell: WaveCell | ReversibleCompositeCell,
        right_cell: WaveCell | ReversibleCompositeCell,
    ) -> None:
        super().__init__()
        if left_cell.transform.config.latent_abi != right_cell.transform.config.latent_abi:
            raise ValueError("fusion requires one latent ABI")
        if left_cell.transform.config.width != right_cell.transform.config.width:
            raise ValueError("fusion requires one latent width")
        self.uid = uid
        self.config = left_cell.transform.config
        self.left_cell = left_cell
        self.right_cell = right_cell
        self.healing_adapter = nn.Linear(self.config.width, self.config.width, bias=False)
        nn.init.zeros_(self.healing_adapter.weight)
        self.register_buffer("healing_strength", torch.zeros(()), persistent=True)
        self.register_buffer(
            "healing_update_count", torch.zeros((), dtype=torch.long), persistent=True
        )

    @property
    def leaf_count(self) -> int:
        return int(getattr(self.left_cell, "execution_units", 1)) + int(
            getattr(self.right_cell, "execution_units", 1)
        )

    @property
    def fusion_depth(self) -> int:
        return 1 + max(
            int(getattr(self.left_cell, "fusion_depth", 0)),
            int(getattr(self.right_cell, "fusion_depth", 0)),
        )

    def forward(
        self,
        state: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        return self.execute(
            state,
            entry_alias_uid=self.left_cell.uid,
            attention_mask=attention_mask,
        )

    def execute(
        self,
        state: torch.Tensor,
        *,
        entry_alias_uid: int,
        attention_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        left_identities = _identity_uids(self.left_cell)
        right_identities = _identity_uids(self.right_cell)
        if entry_alias_uid in right_identities and entry_alias_uid not in left_identities:
            return _execute_cell(
                self.right_cell,
                state,
                entry_alias_uid=entry_alias_uid,
                attention_mask=attention_mask,
            )
        if entry_alias_uid not in left_identities and entry_alias_uid != self.uid:
            raise KeyError(f"UID {entry_alias_uid} is not an entry alias for composite {self.uid}")
        state = _execute_cell(
            self.left_cell,
            state,
            entry_alias_uid=self.left_cell.uid,
            attention_mask=attention_mask,
        )
        if float(self.healing_strength.item()) > 0.0:
            state = F.layer_norm(
                state + self.healing_strength.to(state) * self.healing_adapter(state),
                (state.size(-1),),
                eps=self.config.normalization_epsilon,
            )
        return _execute_cell(
            self.right_cell,
            state,
            entry_alias_uid=self.right_cell.uid,
            attention_mask=attention_mask,
        )


class ReversibleCompositeCell(nn.Module):
    """One canonical active UID with an extractable binary constituent seam."""

    def __init__(
        self,
        *,
        uid: int,
        left_cell: WaveCell | ReversibleCompositeCell,
        right_cell: WaveCell | ReversibleCompositeCell,
        trust_profiles: Iterable[ConditionalTrustProfile] = (),
        optimizer_partitions: Mapping[int, Mapping[str, Any]] | None = None,
        stage: CompositeStage = CompositeStage.REVERSIBLE,
        rigidity: float = 0.0,
        maximum_degree: int | None = None,
        maximum_fanout: int | None = None,
    ) -> None:
        super().__init__()
        if uid < 0 or left_cell.uid == right_cell.uid:
            raise ValueError("composite identity or constituent identities are invalid")
        self.transform = ReversibleCompositeTransform(
            uid=uid,
            left_cell=left_cell,
            right_cell=right_cell,
        )
        self.receptor = copy.deepcopy(left_cell.receptor)
        self.max_degree = maximum_degree or max(left_cell.max_degree, right_cell.max_degree)
        self.max_fanout = maximum_fanout or max(left_cell.max_fanout, right_cell.max_fanout)
        self.register_buffer("contribution_scale", torch.ones(()), persistent=True)
        self.ports: dict[int, NeighborPort] = {
            destination: copy.copy(port)
            for destination, port in right_cell.ports.items()
            if destination not in _identity_uids(left_cell)
        }
        profiles = tuple(trust_profiles)
        for profile in profiles:
            profile.validate()
        self.trust_profiles = profiles
        self.optimizer_partitions = {
            int(key): copy.deepcopy(dict(value))
            for key, value in (optimizer_partitions or {}).items()
        }
        self.stage = stage
        self.rigidity = float(rigidity)
        self.counterfactual_regression = 0.0
        self.seam_id = f"seam:{left_cell.uid}:{right_cell.uid}->{uid}"
        self.structural_history: list[dict[str, Any]] = []

    @property
    def uid(self) -> int:
        return self.transform.uid

    @property
    def left_cell(self) -> WaveCell | ReversibleCompositeCell:
        return self.transform.left_cell

    @property
    def right_cell(self) -> WaveCell | ReversibleCompositeCell:
        return self.transform.right_cell

    @property
    def execution_units(self) -> int:
        return self.transform.leaf_count

    @property
    def fusion_depth(self) -> int:
        return self.transform.fusion_depth

    @property
    def constituent_uids(self) -> tuple[int, ...]:
        values = _identity_uids(self.left_cell) | _identity_uids(self.right_cell)
        values.discard(self.uid)
        return tuple(sorted(values))

    @property
    def fusion_tree(self) -> dict[str, Any]:
        def node(cell: WaveCell | ReversibleCompositeCell) -> dict[str, Any]:
            if isinstance(cell, ReversibleCompositeCell):
                return cell.fusion_tree
            return {"uid": cell.uid, "kind": "leaf"}

        return {
            "uid": self.uid,
            "kind": "reversible_composite",
            "stage": self.stage.value,
            "seam_id": self.seam_id,
            "left": node(self.left_cell),
            "right": node(self.right_cell),
        }

    def receptor_for(self, entry_alias_uid: int) -> IngressReceptor:
        child = (
            self.right_cell
            if entry_alias_uid in _identity_uids(self.right_cell)
            else self.left_cell
        )
        if isinstance(child, ReversibleCompositeCell):
            return child.receptor_for(entry_alias_uid)
        return child.receptor

    def execute_composite(
        self,
        state: torch.Tensor,
        *,
        entry_alias_uid: int | None,
        attention_mask: torch.Tensor | None,
    ) -> torch.Tensor:
        return self.transform.execute(
            state,
            entry_alias_uid=entry_alias_uid or self.uid,
            attention_mask=attention_mask,
        )

    def connect(self, port: NeighborPort) -> None:
        port.validate()
        if port.destination_uid not in self.ports and len(self.ports) >= self.max_degree:
            raise ValueError(f"composite {self.uid} has reached its degree bound")
        self.ports[port.destination_uid] = port

    def inherited_trust(self, context_key: str) -> dict[str, float]:
        matches = [item for item in self.trust_profiles if item.context_key == context_key]
        if not matches:
            return {
                "positive_authority": 0.0,
                "negative_history": 0.0,
                "calibration_error": 1.0,
            }
        # Profiles retain their identities. Authority is bounded by the strongest
        # matching predecessor and cannot grow merely because aliases multiplied.
        return {
            "positive_authority": max(item.positive_authority for item in matches),
            "negative_history": max(item.negative_history for item in matches),
            "calibration_error": max(item.calibration_error for item in matches),
        }


class StructuralController:
    """Pairwise fusion, explicit healing, rigidity audit, and early fission."""

    def __init__(
        self,
        substrate: SparseWaveSubstrate,
        *,
        next_uid: int,
        policy: FusionPolicyConfig | None = None,
    ) -> None:
        if next_uid < 0:
            raise ValueError("next_uid must be non-negative")
        self.substrate = substrate
        self.policy = policy or FusionPolicyConfig()
        self.policy.validate()
        self.next_uid = next_uid
        self.rigidity = RigidityLedger(self.policy)
        self.events: list[StructuralEvent] = []

    def _allocate_uid(self) -> int:
        occupied = {
            *map(int, self.substrate.cells.keys()),
            *self.substrate.aliases.keys(),
            *self.substrate.retired_uids,
        }
        while self.next_uid in occupied:
            self.next_uid += 1
        uid = self.next_uid
        self.next_uid += 1
        return uid

    @staticmethod
    def _parameter_bytes(cell: nn.Module) -> int:
        return sum(
            parameter.numel() * parameter.element_size()
            for parameter in cell.parameters()
        ) + sum(
            buffer.numel() * buffer.element_size()
            for buffer in cell.buffers()
        )

    def _record_event(
        self,
        pressure: StructuralPressure,
        action: str,
        source_uids: tuple[int, ...],
        result_uids: tuple[int, ...],
        evidence: Mapping[str, Any],
    ) -> StructuralEvent:
        event = StructuralEvent(
            sequence=len(self.events) + 1,
            pressure=pressure,
            action=action,
            source_uids=source_uids,
            result_uids=result_uids,
            evidence=dict(evidence),
        )
        self.events.append(event)
        return event

    def _fusion_gates(self, evidence: FusionEvidence) -> tuple[str, ...]:
        policy = self.policy
        gates = {
            "left_mature": evidence.left_lifecycle == "mature",
            "right_mature": evidence.right_lifecycle == "mature",
            "left_rigid": evidence.left_rigidity >= policy.minimum_rigidity,
            "right_rigid": evidence.right_rigidity >= policy.minimum_rigidity,
            "conductance": evidence.conductance >= policy.minimum_conductance,
            "coparticipation": (
                evidence.conditional_coparticipation
                >= policy.minimum_conditional_coparticipation
            ),
            "left_independence": (
                evidence.left_independent_use <= policy.maximum_independent_use
            ),
            "right_independence": (
                evidence.right_independent_use <= policy.maximum_independent_use
            ),
            "low_error": evidence.recent_error <= policy.maximum_recent_error,
            "measured_savings": (
                evidence.measured_dispatch_savings
                >= policy.minimum_dispatch_savings
            ),
        }
        return tuple(name for name, passed in gates.items() if not passed)

    @staticmethod
    def _direct_pair_output(
        left: WaveCell | ReversibleCompositeCell,
        right: WaveCell | ReversibleCompositeCell,
        probe: FusionProbe,
    ) -> torch.Tensor:
        if probe.entry_uid in _identity_uids(right):
            return _execute_cell(
                right,
                probe.state,
                entry_alias_uid=probe.entry_uid,
                attention_mask=None,
            )
        state = _execute_cell(
            left,
            probe.state,
            entry_alias_uid=probe.entry_uid,
            attention_mask=None,
        )
        return _execute_cell(
            right,
            state,
            entry_alias_uid=right.uid,
            attention_mask=None,
        )

    def _audit_fusion(
        self,
        composite: ReversibleCompositeCell,
        probes: tuple[FusionProbe, ...],
    ) -> FusionAudit:
        if not probes:
            raise ValueError("fusion requires bounded behavior probes")
        differences: list[float] = []
        with torch.inference_mode():
            for probe in probes:
                probe.validate(composite.transform.config.width)
                expected = self._direct_pair_output(
                    composite.left_cell, composite.right_cell, probe
                )
                observed = composite.execute_composite(
                    probe.state,
                    entry_alias_uid=probe.entry_uid,
                    attention_mask=None,
                )
                differences.append(
                    float((observed.float() - expected.float()).abs().max().cpu())
                )
        parameter_bytes = self._parameter_bytes(composite)
        maximum = max(differences)
        passed = (
            maximum <= self.policy.behavior_tolerance
            and composite.execution_units <= self.policy.maximum_composite_leaves
            and composite.fusion_depth <= self.policy.maximum_fusion_depth
            and parameter_bytes <= self.policy.maximum_composite_parameter_bytes
        )
        return FusionAudit(
            maximum_absolute_difference=maximum,
            probes=len(probes),
            leaf_count=composite.execution_units,
            fusion_depth=composite.fusion_depth,
            parameter_bytes=parameter_bytes,
            passed=passed,
        )

    def fuse(
        self,
        evidence: FusionEvidence,
        probes: tuple[FusionProbe, ...],
        *,
        optimizer_partitions: Mapping[int, Mapping[str, Any]] | None = None,
    ) -> FusionDecision:
        evidence.validate()
        if not self.substrate.ready_for_next_turn:
            raise RuntimeError("fusion requires a quiescent substrate")
        left_uid = self.substrate.resolve_uid(evidence.left_uid)
        right_uid = self.substrate.resolve_uid(evidence.right_uid)
        if (left_uid, right_uid) != (evidence.left_uid, evidence.right_uid):
            raise ValueError("fusion evidence must name current canonical UIDs")
        left = self.substrate._cell(left_uid)
        right = self.substrate._cell(right_uid)
        failed = list(self._fusion_gates(evidence))
        enabled_left_ports = {
            uid for uid, port in left.ports.items() if port.enabled
        }
        if enabled_left_ports != {right_uid}:
            failed.append("isolated_pair_path")
        if left_uid in right.ports:
            failed.append("no_immediate_reverse")
        for uid_text, cell in self.substrate.cells.items():
            uid = int(uid_text)
            if uid not in {left_uid, right_uid} and {
                left_uid, right_uid
            }.issubset(cell.ports):
                failed.append("unambiguous_neighbor_entry")
                break
        if failed:
            return FusionDecision(False, "retain_separate_tissue", None, tuple(failed), None)

        successor_uid = self._allocate_uid()
        composite = ReversibleCompositeCell(
            uid=successor_uid,
            left_cell=left,
            right_cell=right,
            trust_profiles=evidence.trust_profiles,
            optimizer_partitions=optimizer_partitions,
            maximum_degree=self.substrate.config.max_degree,
            maximum_fanout=self.substrate.config.max_fanout,
        )
        reference_parameter = next(left.transform.parameters())
        composite.to(
            device=reference_parameter.device,
            dtype=reference_parameter.dtype,
        )
        audit = self._audit_fusion(composite, probes)
        if not audit.passed:
            failed_audit: list[str] = []
            if audit.maximum_absolute_difference > self.policy.behavior_tolerance:
                failed_audit.append("behavior_preservation")
            if audit.leaf_count > self.policy.maximum_composite_leaves:
                failed_audit.append("leaf_budget")
            if audit.fusion_depth > self.policy.maximum_fusion_depth:
                failed_audit.append("depth_budget")
            if audit.parameter_bytes > self.policy.maximum_composite_parameter_bytes:
                failed_audit.append("parameter_budget")
            return FusionDecision(
                False,
                "retain_separate_tissue",
                None,
                tuple(failed_audit),
                audit,
            )

        old_aliases = dict(self.substrate.aliases)
        incoming: dict[int, list[NeighborPort]] = {}
        try:
            self.substrate.cells.pop(str(left_uid))
            self.substrate.cells.pop(str(right_uid))
            self.substrate.cells[str(successor_uid)] = composite
            for uid_text, cell in self.substrate.cells.items():
                uid = int(uid_text)
                if uid == successor_uid:
                    continue
                replaced = [
                    cell.ports.pop(target)
                    for target in (left_uid, right_uid)
                    if target in cell.ports
                ]
                if not replaced:
                    continue
                incoming[uid] = replaced
                original = replaced[0]
                entry_alias = original.entry_alias_uid or original.destination_uid
                cell.connect(
                    NeighborPort(
                        destination_uid=successor_uid,
                        conductance=max(port.conductance for port in replaced),
                        route_familiarity=max(
                            port.route_familiarity for port in replaced
                        ),
                        enabled=any(port.enabled for port in replaced),
                        entry_alias_uid=entry_alias,
                    )
                )
            predecessor_aliases = {
                alias
                for alias in old_aliases
                if self.substrate.resolve_uid(alias) in {left_uid, right_uid}
            }
            self.substrate.aliases = {
                alias: target
                for alias, target in old_aliases.items()
                if alias not in predecessor_aliases
            }
            for alias in predecessor_aliases | {left_uid, right_uid}:
                self.substrate.aliases[alias] = successor_uid
            self.substrate.graph_version += 1
        except Exception:
            self.substrate.aliases = old_aliases
            self.substrate.cells.pop(str(successor_uid), None)
            self.substrate.cells[str(left_uid)] = left
            self.substrate.cells[str(right_uid)] = right
            for uid, ports in incoming.items():
                cell = self.substrate._cell(uid)
                cell.ports.pop(successor_uid, None)
                for port in ports:
                    cell.ports[port.destination_uid] = port
            raise
        self.rigidity.set(successor_uid, min(evidence.left_rigidity, evidence.right_rigidity))
        event = self._record_event(
            StructuralPressure.FUSION,
            "admit_reversible_composite",
            (left_uid, right_uid),
            (successor_uid,),
            {
                "audit": asdict(audit),
                "thought_epochs": list(evidence.thought_epochs),
                "evidence_lineages": list(evidence.evidence_lineages),
                "fusion_tree": composite.fusion_tree,
            },
        )
        composite.structural_history.append(event.as_dict())
        return FusionDecision(True, "admit_reversible_composite", successor_uid, (), audit)

    def train_healing(
        self,
        composite_uid: int,
        probes: tuple[HealingProbe, ...],
        *,
        authorization: HealingAuthorization,
        steps: int = 32,
        learning_rate: float = 0.01,
    ) -> None:
        if not self.policy.semantic_healing_enabled:
            raise RuntimeError("semantic healing is disabled by structural policy")
        authorization.validate()
        cell = self.substrate._cell(composite_uid)
        if not isinstance(cell, ReversibleCompositeCell):
            raise TypeError("healing requires a reversible composite")
        if not probes or steps <= 0 or learning_rate <= 0:
            raise ValueError("healing requires probes and positive optimizer bounds")
        for probe in probes:
            probe.validate(cell.transform.config.width)
        cell.stage = CompositeStage.HEALING
        cell.transform.healing_strength.fill_(1.0)
        optimizer = torch.optim.AdamW(
            cell.transform.healing_adapter.parameters(), lr=learning_rate
        )
        for step in range(steps):
            probe = probes[step % len(probes)]
            optimizer.zero_grad(set_to_none=True)
            output = cell.execute_composite(
                probe.state,
                entry_alias_uid=probe.entry_uid,
                attention_mask=None,
            )
            loss = F.mse_loss(output.float(), probe.target_state.float())
            loss.backward()
            optimizer.step()
            cell.transform.healing_update_count.add_(1)

    def audit_rigidity(
        self,
        composite_uid: int,
        probes: tuple[HealingProbe, ...],
    ) -> RigidityAudit:
        cell = self.substrate._cell(composite_uid)
        if not isinstance(cell, ReversibleCompositeCell):
            raise TypeError("rigidity audit requires a reversible composite")
        for probe in probes:
            probe.validate(cell.transform.config.width)
        if not probes:
            raise ValueError("rigidity audit requires probes")
        with torch.inference_mode():
            enabled_losses = [
                float(
                    F.mse_loss(
                        cell.execute_composite(
                            probe.state,
                            entry_alias_uid=probe.entry_uid,
                            attention_mask=None,
                        ).float(),
                        probe.target_state.float(),
                    ).cpu()
                )
                for probe in probes
            ]
            strength = cell.transform.healing_strength.detach().clone()
            cell.transform.healing_strength.zero_()
            try:
                masked_losses = [
                    float(
                        F.mse_loss(
                            cell.execute_composite(
                                probe.state,
                                entry_alias_uid=probe.entry_uid,
                                attention_mask=None,
                            ).float(),
                            probe.target_state.float(),
                        ).cpu()
                    )
                    for probe in probes
                ]
            finally:
                cell.transform.healing_strength.copy_(strength)
        enabled = sum(enabled_losses) / len(enabled_losses)
        masked = sum(masked_losses) / len(masked_losses)
        regression = max(0.0, masked - enabled)
        cell.counterfactual_regression = regression
        extractable = regression <= self.policy.maximum_seam_regression
        if extractable:
            cell.stage = CompositeStage.HEALING if float(strength) else CompositeStage.REVERSIBLE
        else:
            cell.stage = CompositeStage.RIGID
        cell.rigidity = min(
            1.0,
            regression / max(self.policy.maximum_seam_regression, 1e-12),
        )
        self.rigidity.set(cell.uid, cell.rigidity)
        return RigidityAudit(enabled, masked, regression, extractable, cell.stage)

    def fission(self, evidence: FissionEvidence) -> FissionDecision:
        evidence.validate()
        if not self.substrate.ready_for_next_turn:
            raise RuntimeError("fission requires a quiescent substrate")
        canonical = self.substrate.resolve_uid(evidence.composite_uid)
        cell = self.substrate._cell(canonical)
        if not isinstance(cell, ReversibleCompositeCell):
            raise TypeError("fission evidence must name a reversible composite")
        was_rigid = (
            cell.stage is CompositeStage.RIGID
            or self.rigidity.value(canonical) >= 1.0
        )
        cell.stage = CompositeStage.DEOPTIMIZED
        if evidence.universally_invalid:
            decision = FissionDecision(
                False, "replace_whole_composite", (), None, ("old_regime_not_useful",)
            )
            self._record_event(
                StructuralPressure.REPLACEMENT,
                decision.action,
                (canonical,),
                (),
                asdict(evidence),
            )
            return decision
        gates = {
            "epochs": len(set(evidence.thought_epochs)) >= self.policy.minimum_fission_epochs,
            "lineages": len(set(evidence.evidence_lineages)) >= self.policy.minimum_fission_lineages,
            "regimes": len(set(evidence.regimes)) >= self.policy.minimum_fission_regimes,
            "negative_transfer": evidence.negative_transfer >= self.policy.minimum_negative_transfer,
            "left_useful": evidence.left_regime_useful,
            "right_useful": evidence.right_regime_useful,
            "left_seam": evidence.left_boundary_regression <= self.policy.maximum_seam_regression,
            "right_seam": evidence.right_boundary_regression <= self.policy.maximum_seam_regression,
            "counterfactual_seam": cell.counterfactual_regression <= self.policy.maximum_seam_regression,
            "not_rigid": not was_rigid,
            "routing": evidence.routing_calibrated,
            "shadow_value": evidence.shadow_specialists_win_after_cost,
            "obligations_closed": evidence.successor_obligations_closed,
        }
        failed = tuple(name for name, passed in gates.items() if not passed)
        if failed:
            action = (
                "repair_in_place_or_bud"
                if any(name in failed for name in ("left_seam", "right_seam", "counterfactual_seam", "not_rigid"))
                else "retain_deoptimized_composite"
            )
            pressure = (
                StructuralPressure.REPAIR
                if action == "repair_in_place_or_bud"
                else StructuralPressure.FISSION
            )
            self._record_event(
                pressure,
                action,
                (canonical,),
                (),
                {**asdict(evidence), "failed_gates": list(failed)},
            )
            return FissionDecision(False, action, (), None, failed)

        left = cell.left_cell
        right = cell.right_cell
        left_identities = _identity_uids(left)
        right_identities = _identity_uids(right)
        rewired: list[tuple[int, NeighborPort]] = []
        for uid_text, neighbor in self.substrate.cells.items():
            uid = int(uid_text)
            if uid == canonical or canonical not in neighbor.ports:
                continue
            port = neighbor.ports[canonical]
            entry = port.entry_alias_uid
            if entry is None or entry == canonical:
                raise RuntimeError(
                    "successor traffic lacks a constituent entry alias; migration is unsafe"
                )
            destination = left.uid if entry in left_identities else right.uid
            rewired.append(
                (
                    uid,
                    NeighborPort(
                        destination_uid=destination,
                        conductance=port.conductance,
                        route_familiarity=port.route_familiarity,
                        enabled=port.enabled,
                        entry_alias_uid=(entry if entry != destination else None),
                    ),
                )
            )
        self.substrate.cells.pop(str(canonical))
        self.substrate.cells[str(left.uid)] = left
        self.substrate.cells[str(right.uid)] = right
        for uid, replacement in rewired:
            neighbor = self.substrate._cell(uid)
            neighbor.ports.pop(canonical, None)
            neighbor.connect(replacement)
        aliases_to_successor = {
            alias
            for alias in tuple(self.substrate.aliases)
            if self.substrate.resolve_uid(alias) == canonical
        }
        for alias in aliases_to_successor:
            if alias == left.uid or alias == right.uid:
                self.substrate.aliases.pop(alias, None)
            elif alias in left_identities:
                self.substrate.aliases[alias] = left.uid
            elif alias in right_identities:
                self.substrate.aliases[alias] = right.uid
            else:
                raise RuntimeError("a predecessor alias cannot be assigned to a fission child")
        self.substrate.aliases.pop(canonical, None)
        self.substrate.retired_uids.add(canonical)
        self.substrate.graph_version += 1
        self.rigidity.set(left.uid, max(0.0, self.rigidity.value(canonical) * 0.5))
        self.rigidity.set(right.uid, max(0.0, self.rigidity.value(canonical) * 0.5))
        event = self._record_event(
            StructuralPressure.FISSION,
            "restore_constituents_and_retire_successor",
            (canonical,),
            (left.uid, right.uid),
            asdict(evidence),
        )
        for restored in (left, right):
            history = list(getattr(restored, "structural_history", []))
            history.append(event.as_dict())
            restored.structural_history = history
        return FissionDecision(
            True,
            "restore_constituents_and_retire_successor",
            (left.uid, right.uid),
            canonical,
            (),
        )
