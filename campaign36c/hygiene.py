from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

import torch
import torch.nn.functional as F

from .config import CellOptimizerConfig
from .wave import NeighborPort, SparseWaveSubstrate, WaveCell, WaveResult


CAMPAIGN36C_HYGIENE_SCHEMA = "ninereeds_campaign36c_hygiene_v0"


class TissueLifecycle(str, Enum):
    ACTIVE = "active"
    SENESCENT = "senescent"
    QUARANTINED = "quarantined"
    REVIVAL_SHADOW = "revival_shadow"
    REVIVAL_PROBATION = "revival_probation"
    PURGED = "purged"


class UsefulCreditKind(str, Enum):
    CONTENT = "content"
    ROUTING = "routing"
    CALIBRATION = "calibration"
    INQUIRY = "inquiry"
    PROTECTIVE = "protective"
    ABSTENTION = "abstention"


class QuarantineReason(str, Enum):
    DISUSE = "disuse"
    SUBSUMED_BY_FUSION = "subsumed_by_fusion"
    OBSOLETE_AFTER_MODEL_CHANGE = "obsolete_after_model_change"
    HARMFUL_CALIBRATION = "harmful_calibration"
    CORRUPTION = "corruption"


@dataclass(frozen=True)
class HygienePolicyConfig:
    """Conservative lifecycle bounds; inactivity never implies deletion."""

    senescence_interval: int = 16
    rooted_use_window: int = 16
    minimum_senescence_sweeps: int = 2
    newborn_grace_epochs: int = 8
    revival_grace_epochs: int = 8
    maximum_edge_history: int = 32
    maximum_revival_candidates: int = 3
    minimum_revival_similarity: float = 0.50
    minimum_revival_improvement_fraction: float = 0.02
    maximum_revival_regression: float = 1e-4
    minimum_revival_lineages: int = 2
    minimum_neighbor_acceptances: int = 1
    revival_contribution_scale: float = 0.10

    def validate(self) -> None:
        positive = (
            self.senescence_interval,
            self.rooted_use_window,
            self.minimum_senescence_sweeps,
            self.newborn_grace_epochs,
            self.revival_grace_epochs,
            self.maximum_edge_history,
            self.maximum_revival_candidates,
            self.minimum_revival_lineages,
            self.minimum_neighbor_acceptances,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("hygiene counts and windows must be positive")
        if not -1.0 <= self.minimum_revival_similarity <= 1.0:
            raise ValueError("revival similarity must be a cosine bound")
        if self.minimum_revival_improvement_fraction < 0:
            raise ValueError("revival improvement must be non-negative")
        if self.maximum_revival_regression < 0:
            raise ValueError("revival regression must be non-negative")
        if not 0.0 < self.revival_contribution_scale <= 1.0:
            raise ValueError("revival contribution scale must be in (0, 1]")


@dataclass
class VitalityRecord:
    uid: int
    lifecycle: TissueLifecycle = TissueLifecycle.ACTIVE
    last_rooted_participation_epoch: int = -1
    last_rooted_ingress_epoch: int = -1
    last_rooted_egress_epoch: int = -1
    last_useful_credit_epoch: int = -1
    useful_credit: dict[str, float] = field(default_factory=dict)
    edge_history: list[dict[str, Any]] = field(default_factory=list)
    grace_until_epoch: int = -1
    senescence_sweeps: int = 0
    protected: bool = False
    pinned: bool = False
    pending_credit: int = 0
    obligations: set[str] = field(default_factory=set)

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["lifecycle"] = self.lifecycle.value
        value["obligations"] = sorted(self.obligations)
        return value


class RootedParticipationLedger:
    """Bounded vitality evidence produced by real organism-rooted activity."""

    def __init__(self, policy: HygienePolicyConfig | None = None) -> None:
        self.policy = policy or HygienePolicyConfig()
        self.policy.validate()
        self.records: dict[int, VitalityRecord] = {}

    def ensure(
        self,
        uid: int,
        *,
        current_epoch: int = 0,
        newborn: bool = False,
    ) -> VitalityRecord:
        if uid < 0 or current_epoch < 0:
            raise ValueError("UID and epoch must be non-negative")
        record = self.records.setdefault(uid, VitalityRecord(uid=uid))
        if newborn:
            record.grace_until_epoch = max(
                record.grace_until_epoch,
                current_epoch + self.policy.newborn_grace_epochs,
            )
        return record

    def set_protected(self, uid: int, value: bool = True) -> None:
        self.ensure(uid).protected = bool(value)

    def set_pinned(self, uid: int, value: bool = True) -> None:
        self.ensure(uid).pinned = bool(value)

    def set_pending_credit(self, uid: int, count: int) -> None:
        if count < 0:
            raise ValueError("pending credit count must be non-negative")
        self.ensure(uid).pending_credit = count

    def set_obligation(self, uid: int, obligation: str, active: bool = True) -> None:
        if not obligation:
            raise ValueError("obligation identity is required")
        record = self.ensure(uid)
        if active:
            record.obligations.add(obligation)
        else:
            record.obligations.discard(obligation)

    def grant_grace(self, uid: int, until_epoch: int) -> None:
        if until_epoch < 0:
            raise ValueError("grace epoch must be non-negative")
        record = self.ensure(uid)
        record.grace_until_epoch = max(record.grace_until_epoch, until_epoch)

    def record_useful_credit(
        self,
        uid: int,
        *,
        epoch: int,
        kind: UsefulCreditKind,
        value: float = 1.0,
        rooted: bool = True,
    ) -> None:
        if epoch < 0 or not math.isfinite(value) or value < 0:
            raise ValueError("credit epoch and value are invalid")
        if not rooted:
            return
        record = self.ensure(uid)
        record.last_useful_credit_epoch = max(record.last_useful_credit_epoch, epoch)
        record.last_rooted_participation_epoch = max(
            record.last_rooted_participation_epoch, epoch
        )
        record.useful_credit[kind.value] = (
            record.useful_credit.get(kind.value, 0.0) + value
        )
        record.senescence_sweeps = 0
        if record.lifecycle is TissueLifecycle.SENESCENT:
            record.lifecycle = TissueLifecycle.ACTIVE

    def _edge_event(
        self,
        source_uid: int,
        destination_uid: int,
        *,
        epoch: int,
        rooted: bool,
    ) -> None:
        if not rooted:
            return
        record = self.ensure(source_uid)
        record.edge_history.append({
            "peer_uid": destination_uid,
            "epoch": epoch,
            "rooted": True,
        })
        if len(record.edge_history) > self.policy.maximum_edge_history:
            del record.edge_history[: -self.policy.maximum_edge_history]

    def record_thought(
        self,
        result: WaveResult,
        *,
        ingress_uids: Iterable[int],
        substrate: SparseWaveSubstrate,
        rooted: bool = True,
    ) -> None:
        """Record a completed externally rooted thought, never background chatter."""

        if not rooted or not substrate.ready_for_next_turn:
            if not rooted:
                return
            raise RuntimeError("vitality accounting requires a completed thought")
        epochs = [item.thought_epoch for item in result.eligibility]
        epoch = max(epochs, default=substrate._thought_epoch)
        for entry_uid in ingress_uids:
            canonical = substrate.resolve_uid(entry_uid)
            record = self.ensure(canonical)
            record.last_rooted_ingress_epoch = max(
                record.last_rooted_ingress_epoch, epoch
            )
            record.last_rooted_participation_epoch = max(
                record.last_rooted_participation_epoch, epoch
            )
            record.senescence_sweeps = 0
        for item in result.eligibility:
            record = self.ensure(item.uid)
            record.last_rooted_participation_epoch = max(
                record.last_rooted_participation_epoch, item.thought_epoch
            )
            if item.outgoing_destinations:
                record.last_rooted_egress_epoch = max(
                    record.last_rooted_egress_epoch, item.thought_epoch
                )
            record.senescence_sweeps = 0
            if record.lifecycle is TissueLifecycle.SENESCENT:
                record.lifecycle = TissueLifecycle.ACTIVE
            for destination_uid in item.outgoing_destinations:
                self._edge_event(
                    item.uid,
                    destination_uid,
                    epoch=item.thought_epoch,
                    rooted=True,
                )

    def is_root(self, uid: int, *, current_epoch: int) -> bool:
        record = self.ensure(uid)
        if record.protected or record.pinned or record.pending_credit:
            return True
        if record.obligations or current_epoch <= record.grace_until_epoch:
            return True
        latest = max(
            record.last_rooted_participation_epoch,
            record.last_useful_credit_epoch,
        )
        return latest >= 0 and current_epoch - latest <= self.policy.rooted_use_window

    def note_unrooted(self, uid: int, *, current_epoch: int) -> bool:
        """Return whether repeated, obligation-free inactivity is senescent."""

        record = self.ensure(uid)
        if self.is_root(uid, current_epoch=current_epoch):
            record.senescence_sweeps = 0
            if record.lifecycle is TissueLifecycle.SENESCENT:
                record.lifecycle = TissueLifecycle.ACTIVE
            return False
        latest = max(
            record.last_rooted_participation_epoch,
            record.last_useful_credit_epoch,
            record.last_rooted_ingress_epoch,
            record.last_rooted_egress_epoch,
        )
        if latest >= 0 and current_epoch - latest < self.policy.senescence_interval:
            return False
        record.senescence_sweeps += 1
        record.lifecycle = TissueLifecycle.SENESCENT
        return record.senescence_sweeps >= self.policy.minimum_senescence_sweeps


@dataclass(frozen=True)
class HygieneAuthorization:
    actor: str
    reason: str
    thought_closed: bool
    delayed_credit_closed: bool
    structural_work_closed: bool
    allow_quarantine: bool = True

    def validate(self) -> None:
        if not self.actor or not self.reason:
            raise ValueError("hygiene requires an actor and reason")
        if not (
            self.thought_closed
            and self.delayed_credit_closed
            and self.structural_work_closed
        ):
            raise RuntimeError("hygiene requires a fully quiescent lifecycle boundary")


@dataclass
class QuarantinedTissue:
    uid: int
    cell: WaveCell
    reason: QuarantineReason
    quarantined_epoch: int
    signature: torch.Tensor
    former_ports: tuple[NeighborPort, ...]
    former_incoming_uids: tuple[int, ...]
    optimizer: torch.optim.Optimizer | None = None
    optimizer_config: CellOptimizerConfig | None = None
    failed_revival_attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def manifest_metadata(self) -> dict[str, Any]:
        return {
            "schema_version": CAMPAIGN36C_HYGIENE_SCHEMA,
            "lifecycle": TissueLifecycle.QUARANTINED.value,
            "reason": self.reason.value,
            "quarantined_epoch": self.quarantined_epoch,
            "signature": self.signature.detach().float().cpu().tolist(),
            "former_ports": [asdict(item) for item in self.former_ports],
            "former_incoming_uids": list(self.former_incoming_uids),
            "failed_revival_attempts": self.failed_revival_attempts,
            **copy.deepcopy(self.metadata),
        }


@dataclass(frozen=True)
class HygieneReport:
    current_epoch: int
    root_uids: tuple[int, ...]
    marked_uids: tuple[int, ...]
    unreachable_uids: tuple[int, ...]
    senescent_uids: tuple[int, ...]
    quarantined_uids: tuple[int, ...]
    preserved_routing_or_abstention_uids: tuple[int, ...]
    pressure: str = "metabolism"


@dataclass(frozen=True)
class RevivalRequest:
    residual_signature: torch.Tensor
    current_epoch: int
    sponsor_uid: int
    claim_address: str

    def validate(self) -> None:
        if self.current_epoch < 0 or self.sponsor_uid < 0 or not self.claim_address:
            raise ValueError("revival request identity is incomplete")
        if self.residual_signature.ndim != 1:
            raise ValueError("revival residual signature must be one-dimensional")
        if not torch.isfinite(self.residual_signature).all():
            raise ValueError("revival residual signature must be finite")


@dataclass(frozen=True)
class RevivalTrial:
    uid: int
    similarity: float
    scanned_candidates: int
    diagnostic_only: bool
    current_epoch: int


@dataclass(frozen=True)
class RevivalEvidence:
    uid: int
    improvement_fraction: float
    maximum_established_regression: float
    useful_present_contribution: bool
    evidence_lineages: tuple[str, ...]
    accepted_ports: tuple[NeighborPort, ...]

    def validate(self) -> None:
        if self.uid < 0 or self.improvement_fraction < 0:
            raise ValueError("revival evidence identity or improvement is invalid")
        if self.maximum_established_regression < 0:
            raise ValueError("revival regression must be non-negative")
        for port in self.accepted_ports:
            port.validate()


@dataclass(frozen=True)
class RevivalDecision:
    admitted: bool
    action: str
    uid: int | None
    scanned_candidates: int
    failed_gates: tuple[str, ...] = ()


@dataclass(frozen=True)
class PurgeAuthorization:
    actor: str
    reason: str
    operator_authorized: bool
    measured_free_bytes: int
    required_free_bytes: int
    requested_reclaim_bytes: int
    explicit_decision: bool = False

    @property
    def storage_pressure(self) -> bool:
        return self.measured_free_bytes < self.required_free_bytes

    def validate(self) -> None:
        if not self.actor or not self.reason:
            raise ValueError("purge authorization requires actor and reason")
        if min(
            self.measured_free_bytes,
            self.required_free_bytes,
            self.requested_reclaim_bytes,
        ) < 0:
            raise ValueError("purge byte measurements must be non-negative")
        if self.requested_reclaim_bytes <= 0:
            raise ValueError("purge must request positive reclamation")


@dataclass(frozen=True)
class PurgeDecision:
    purged_uids: tuple[int, ...]
    refused_uids: tuple[int, ...]
    action: str
    pressure: str = "metabolism"


class HygieneController:
    """Idle-cycle reachability, recoverable quarantine, revival, and death."""

    def __init__(
        self,
        substrate: SparseWaveSubstrate,
        *,
        ledger: RootedParticipationLedger | None = None,
        policy: HygienePolicyConfig | None = None,
    ) -> None:
        self.substrate = substrate
        self.policy = policy or HygienePolicyConfig()
        self.policy.validate()
        self.ledger = ledger or RootedParticipationLedger(self.policy)
        self.quarantine: dict[int, QuarantinedTissue] = {}
        self.revival_trials: dict[int, RevivalTrial] = {}
        self.purged_uids: set[int] = set()
        for uid in map(int, substrate.cells.keys()):
            self.ledger.ensure(uid)

    def restore_quarantine(
        self,
        cells: Mapping[int, WaveCell],
        metadata: Mapping[int, Mapping[str, Any]],
        *,
        optimizers: Mapping[int, torch.optim.Optimizer] | None = None,
        optimizer_configs: Mapping[int, CellOptimizerConfig] | None = None,
    ) -> None:
        """Restore cold quarantined records without making them routable."""

        optimizers = optimizers or {}
        optimizer_configs = optimizer_configs or {}
        for uid in sorted(cells):
            if self.substrate.has_active_uid(uid) or uid in self.substrate.retired_uids:
                raise ValueError("quarantine restore conflicts with active or retired UID")
            value = dict(metadata.get(uid, {}))
            signature = torch.tensor(
                value.get("signature", []), dtype=torch.float32
            )
            if signature.numel() == 0:
                signature = self._signature(cells[uid])
            former_ports = tuple(
                NeighborPort(**item)
                for item in value.get(
                    "former_ports",
                    [asdict(cells[uid].ports[key]) for key in sorted(cells[uid].ports)],
                )
            )
            tissue = QuarantinedTissue(
                uid=uid,
                cell=cells[uid],
                reason=QuarantineReason(value.get("reason", QuarantineReason.DISUSE.value)),
                quarantined_epoch=int(value.get("quarantined_epoch", 0)),
                signature=F.normalize(signature, dim=0, eps=1e-12),
                former_ports=former_ports,
                former_incoming_uids=tuple(
                    map(int, value.get("former_incoming_uids", ()))
                ),
                optimizer=optimizers.get(uid),
                optimizer_config=optimizer_configs.get(uid),
                failed_revival_attempts=int(value.get("failed_revival_attempts", 0)),
                metadata={
                    key: copy.deepcopy(item)
                    for key, item in value.items()
                    if key not in {
                        "schema_version",
                        "lifecycle",
                        "reason",
                        "quarantined_epoch",
                        "signature",
                        "former_ports",
                        "former_incoming_uids",
                        "failed_revival_attempts",
                    }
                },
            )
            self.quarantine[uid] = tissue
            self.ledger.ensure(uid).lifecycle = TissueLifecycle.QUARANTINED

    def _canonical_active(self, uid: int) -> int | None:
        try:
            canonical = self.substrate.resolve_uid(uid)
        except RuntimeError:
            return None
        return canonical if self.substrate.has_active_uid(canonical) else None

    def _roots(
        self,
        *,
        current_epoch: int,
        ingress_uids: Iterable[int],
        explicit_root_uids: Iterable[int],
    ) -> set[int]:
        roots: set[int] = set()
        for uid in (*tuple(ingress_uids), *tuple(explicit_root_uids)):
            canonical = self._canonical_active(uid)
            if canonical is not None:
                roots.add(canonical)
        for uid in map(int, self.substrate.cells.keys()):
            if self.ledger.is_root(uid, current_epoch=current_epoch):
                roots.add(uid)
        return roots

    def _mark(self, roots: Iterable[int]) -> set[int]:
        marked: set[int] = set()
        frontier = list(sorted(set(roots), reverse=True))
        while frontier:
            uid = frontier.pop()
            if uid in marked or not self.substrate.has_active_uid(uid):
                continue
            marked.add(uid)
            cell = self.substrate._cell(uid)
            destinations = [
                port.destination_uid
                for port in cell.ports.values()
                if port.enabled and self.substrate.has_active_uid(port.destination_uid)
            ]
            frontier.extend(sorted(set(destinations) - marked, reverse=True))
        return marked

    def _signature(self, cell: WaveCell) -> torch.Tensor:
        value = cell.receptor.content_prototype.detach().float().cpu()
        return F.normalize(value, dim=0, eps=1e-12)

    def _quarantine(
        self,
        uid: int,
        *,
        current_epoch: int,
        reason: QuarantineReason,
        optimizer: torch.optim.Optimizer | None = None,
        optimizer_config: CellOptimizerConfig | None = None,
    ) -> None:
        if not self.substrate.ready_for_next_turn:
            raise RuntimeError("quarantine cannot mutate a live thought")
        if (optimizer is None) != (optimizer_config is None):
            raise ValueError("quarantine optimizer and config must be paired")
        cell = self.substrate._cell(uid)
        incoming = tuple(sorted(
            source_uid
            for source_uid in map(int, self.substrate.cells.keys())
            if source_uid != uid
            and any(
                self.substrate.resolve_uid(port.destination_uid) == uid
                for port in self.substrate._cell(source_uid).ports.values()
            )
        ))
        tissue = QuarantinedTissue(
            uid=uid,
            cell=cell,
            reason=reason,
            quarantined_epoch=current_epoch,
            signature=self._signature(cell),
            former_ports=tuple(copy.copy(cell.ports[key]) for key in sorted(cell.ports)),
            former_incoming_uids=incoming,
            optimizer=optimizer,
            optimizer_config=optimizer_config,
        )
        del self.substrate.cells[self.substrate._key(uid)]
        self.substrate.graph_version += 1
        self.quarantine[uid] = tissue
        record = self.ledger.ensure(uid)
        record.lifecycle = TissueLifecycle.QUARANTINED

    def mark_and_sweep(
        self,
        *,
        current_epoch: int,
        ingress_uids: Iterable[int] = (),
        explicit_root_uids: Iterable[int] = (),
        authorization: HygieneAuthorization,
        quarantine_reasons: Mapping[int, QuarantineReason] | None = None,
        optimizers: Mapping[int, torch.optim.Optimizer] | None = None,
        optimizer_configs: Mapping[int, CellOptimizerConfig] | None = None,
    ) -> HygieneReport:
        authorization.validate()
        if current_epoch < 0 or not self.substrate.ready_for_next_turn:
            raise RuntimeError("hygiene requires a non-negative idle epoch")
        roots = self._roots(
            current_epoch=current_epoch,
            ingress_uids=ingress_uids,
            explicit_root_uids=explicit_root_uids,
        )
        marked = self._mark(roots)
        active = set(map(int, self.substrate.cells.keys()))
        unreachable = active - marked
        confirmed: list[int] = []
        for uid in sorted(unreachable):
            if self.ledger.note_unrooted(uid, current_epoch=current_epoch):
                confirmed.append(uid)
        quarantine_reasons = quarantine_reasons or {}
        optimizers = optimizers or {}
        optimizer_configs = optimizer_configs or {}
        quarantined: list[int] = []
        if authorization.allow_quarantine:
            for uid in confirmed:
                self._quarantine(
                    uid,
                    current_epoch=current_epoch,
                    reason=quarantine_reasons.get(uid, QuarantineReason.DISUSE),
                    optimizer=optimizers.get(uid),
                    optimizer_config=optimizer_configs.get(uid),
                )
                quarantined.append(uid)
        preserved_special = tuple(sorted(
            uid
            for uid in marked
            if any(
                self.ledger.ensure(uid).useful_credit.get(kind.value, 0.0) > 0
                for kind in (UsefulCreditKind.ROUTING, UsefulCreditKind.ABSTENTION)
            )
        ))
        return HygieneReport(
            current_epoch=current_epoch,
            root_uids=tuple(sorted(roots)),
            marked_uids=tuple(sorted(marked)),
            unreachable_uids=tuple(sorted(unreachable)),
            senescent_uids=tuple(confirmed),
            quarantined_uids=tuple(quarantined),
            preserved_routing_or_abstention_uids=preserved_special,
        )

    def begin_revival(self, request: RevivalRequest) -> RevivalDecision:
        request.validate()
        if not self.substrate.ready_for_next_turn:
            raise RuntimeError("revival selection requires an idle substrate")
        signature = F.normalize(
            request.residual_signature.detach().float().cpu(), dim=0, eps=1e-12
        )
        scored: list[tuple[float, int]] = []
        for uid, tissue in self.quarantine.items():
            if tissue.signature.shape != signature.shape:
                continue
            similarity = float(F.cosine_similarity(
                tissue.signature.unsqueeze(0), signature.unsqueeze(0)
            ).item())
            scored.append((similarity, uid))
        scored.sort(key=lambda item: (-item[0], item[1]))
        bounded = scored[: self.policy.maximum_revival_candidates]
        eligible = [
            item for item in bounded
            if item[0] >= self.policy.minimum_revival_similarity
        ]
        if not eligible:
            return RevivalDecision(
                admitted=False,
                action="permit_birth_after_bounded_quarantine_search",
                uid=None,
                scanned_candidates=len(bounded),
                failed_gates=("quarantine_match",),
            )
        similarity, uid = eligible[0]
        tissue = self.quarantine[uid]
        diagnostic_only = tissue.reason in {
            QuarantineReason.HARMFUL_CALIBRATION,
            QuarantineReason.CORRUPTION,
        }
        trial = RevivalTrial(
            uid=uid,
            similarity=similarity,
            scanned_candidates=len(bounded),
            diagnostic_only=diagnostic_only,
            current_epoch=request.current_epoch,
        )
        self.revival_trials[uid] = trial
        self.ledger.ensure(uid).lifecycle = TissueLifecycle.REVIVAL_SHADOW
        return RevivalDecision(
            admitted=False,
            action="diagnostic_shadow" if diagnostic_only else "shadow_revival",
            uid=uid,
            scanned_candidates=len(bounded),
        )

    def complete_revival(
        self,
        evidence: RevivalEvidence,
        *,
        current_epoch: int,
    ) -> RevivalDecision:
        evidence.validate()
        trial = self.revival_trials.get(evidence.uid)
        tissue = self.quarantine.get(evidence.uid)
        if trial is None or tissue is None:
            raise KeyError("UID has no active revival shadow trial")
        failed: list[str] = []
        if trial.diagnostic_only:
            failed.append("diagnostic_only_reason")
        if evidence.improvement_fraction < self.policy.minimum_revival_improvement_fraction:
            failed.append("current_value")
        if evidence.maximum_established_regression > self.policy.maximum_revival_regression:
            failed.append("established_harm")
        if not evidence.useful_present_contribution:
            failed.append("useful_present_contribution")
        if len(set(evidence.evidence_lineages)) < self.policy.minimum_revival_lineages:
            failed.append("independent_lineages")
        accepted = tuple(
            port for port in evidence.accepted_ports
            if self.substrate.has_active_uid(port.destination_uid)
        )
        if len(accepted) < self.policy.minimum_neighbor_acceptances:
            failed.append("neighbor_acceptance")
        if failed:
            tissue.failed_revival_attempts += 1
            self.revival_trials.pop(evidence.uid, None)
            self.ledger.ensure(evidence.uid).lifecycle = TissueLifecycle.QUARANTINED
            return RevivalDecision(
                admitted=False,
                action="remain_quarantined",
                uid=evidence.uid,
                scanned_candidates=trial.scanned_candidates,
                failed_gates=tuple(failed),
            )
        tissue.cell.ports.clear()
        for port in accepted:
            tissue.cell.connect(copy.copy(port))
        if hasattr(tissue.cell, "set_contribution_scale"):
            tissue.cell.set_contribution_scale(  # type: ignore[attr-defined]
                self.policy.revival_contribution_scale
            )
        else:
            with torch.no_grad():
                tissue.cell.contribution_scale.fill_(
                    self.policy.revival_contribution_scale
                )
        self.substrate.add_cell(tissue.cell)
        self.quarantine.pop(evidence.uid)
        self.revival_trials.pop(evidence.uid, None)
        record = self.ledger.ensure(evidence.uid)
        record.lifecycle = TissueLifecycle.REVIVAL_PROBATION
        record.senescence_sweeps = 0
        record.last_rooted_participation_epoch = current_epoch
        record.grace_until_epoch = max(
            record.grace_until_epoch,
            current_epoch + self.policy.revival_grace_epochs,
        )
        return RevivalDecision(
            admitted=True,
            action="restore_original_uid_in_probation",
            uid=evidence.uid,
            scanned_candidates=trial.scanned_candidates,
        )

    def purge(
        self,
        uids: Iterable[int],
        *,
        authorization: PurgeAuthorization,
    ) -> PurgeDecision:
        authorization.validate()
        requested = tuple(sorted(set(uids)))
        if not authorization.operator_authorized or not (
            authorization.storage_pressure or authorization.explicit_decision
        ):
            return PurgeDecision((), requested, "refuse_without_authorized_pressure")
        purged: list[int] = []
        refused: list[int] = []
        for uid in requested:
            tissue = self.quarantine.get(uid)
            record = self.ledger.ensure(uid)
            if (
                tissue is None
                or uid in self.revival_trials
                or record.pending_credit
                or record.obligations
                or record.protected
                or record.pinned
            ):
                refused.append(uid)
                continue
            self.quarantine.pop(uid)
            self.substrate.retired_uids.add(uid)
            self.substrate.aliases = {
                alias: canonical
                for alias, canonical in self.substrate.aliases.items()
                if canonical != uid and alias != uid
            }
            record.lifecycle = TissueLifecycle.PURGED
            self.purged_uids.add(uid)
            purged.append(uid)
        if purged:
            self.substrate.graph_version += 1
        return PurgeDecision(
            tuple(purged),
            tuple(refused),
            "purge_and_retire_uid" if purged else "no_eligible_quarantine",
        )

    def quarantine_cells(self) -> dict[int, WaveCell]:
        return {uid: tissue.cell for uid, tissue in self.quarantine.items()}

    def quarantine_metadata(self) -> dict[int, dict[str, Any]]:
        return {
            uid: tissue.manifest_metadata()
            for uid, tissue in self.quarantine.items()
        }

    def quarantine_optimizers(self) -> dict[int, torch.optim.Optimizer]:
        return {
            uid: tissue.optimizer
            for uid, tissue in self.quarantine.items()
            if tissue.optimizer is not None
        }

    def quarantine_optimizer_configs(self) -> dict[int, CellOptimizerConfig]:
        return {
            uid: tissue.optimizer_config
            for uid, tissue in self.quarantine.items()
            if tissue.optimizer_config is not None
        }
