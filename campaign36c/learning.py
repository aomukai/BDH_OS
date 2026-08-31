from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn.functional as F

from .config import CellOptimizerConfig
from .epistemics import (
    CreditEvent,
    CreditGrade,
    CreditRole,
    CreditTargetKind,
    ReceiptDisposition,
)
from .wave import NeighborPort, SparseWaveSubstrate, WaveResult


@dataclass(frozen=True)
class LearningExample:
    root_state: torch.Tensor
    target_state: torch.Tensor
    ingress_uids: int | tuple[int, ...]
    claim_address: str
    evidence_lineage: tuple[str, ...]
    attention_mask: torch.Tensor | None = None
    expected_merge_mode: str = "single_value"
    novelty: float = 0.0

    def validate(self) -> None:
        if self.root_state.shape != self.target_state.shape:
            raise ValueError("root and target states must have identical shapes")
        if self.root_state.ndim != 3 or self.root_state.size(0) != 1:
            raise ValueError("Stage-3 examples carry one [1,token,width] thought")
        if not self.claim_address or not self.evidence_lineage:
            raise ValueError("claim address and evidence lineage are required")


@dataclass(frozen=True)
class RetentionProbe:
    example: LearningExample
    maximum_absolute_regression: float = 1e-4

    def __post_init__(self) -> None:
        if self.maximum_absolute_regression < 0:
            raise ValueError("retention regression bound must be non-negative")


@dataclass(frozen=True)
class CreditPolicyConfig:
    content_ownership_threshold: float = 0.70
    route_learning_rate: float = 0.05
    receptor_learning_rate: float = 0.05
    maximum_gradient_norm: float = 1.0

    def validate(self) -> None:
        if not 0.0 <= self.content_ownership_threshold <= 1.0:
            raise ValueError("content ownership threshold must be in [0, 1]")
        if not 0.0 <= self.route_learning_rate <= 1.0:
            raise ValueError("route learning rate must be in [0, 1]")
        if not 0.0 <= self.receptor_learning_rate <= 1.0:
            raise ValueError("receptor learning rate must be in [0, 1]")
        if self.maximum_gradient_norm <= 0:
            raise ValueError("maximum gradient norm must be positive")


@dataclass(frozen=True)
class TrainStepResult:
    thought_result: WaveResult
    loss_before_update: float
    loss_after_update: float
    updated_uids: tuple[int, ...]
    updated_edges: tuple[tuple[int, int], ...]
    updated_receptor_uids: tuple[int, ...]
    credit_events: tuple[CreditEvent, ...]
    outcome_applied: bool
    retention_rollback: bool
    retention_losses_before: tuple[float, ...]
    retention_losses_after: tuple[float, ...]


@dataclass(frozen=True)
class ExternalCreditResult:
    """Sparse ownership applied to a loss produced by a downstream organ."""

    updated_uids: tuple[int, ...]
    updated_edges: tuple[tuple[int, int], ...]
    credit_events: tuple[CreditEvent, ...]


class ExecutedSubgraphTrainer:
    """Conventional backprop with UID-local, typed sparse update ownership."""

    def __init__(
        self,
        substrate: SparseWaveSubstrate,
        *,
        optimizer_config: CellOptimizerConfig | None = None,
        credit_policy: CreditPolicyConfig | None = None,
    ) -> None:
        self.substrate = substrate
        self.optimizer_config = optimizer_config or CellOptimizerConfig()
        self.optimizer_config.validate()
        self.credit_policy = credit_policy or CreditPolicyConfig()
        self.credit_policy.validate()
        self._optimizers: dict[int, torch.optim.AdamW] = {}
        self._last_gradient_uids: set[int] = set()

    @property
    def optimizer_uids(self) -> tuple[int, ...]:
        return tuple(sorted(self._optimizers))

    def _optimizer(self, uid: int) -> torch.optim.AdamW:
        if uid not in self._optimizers:
            config = self.optimizer_config
            self._optimizers[uid] = torch.optim.AdamW(
                self.substrate._cell(uid).transform.parameters(),
                lr=config.learning_rate,
                betas=config.betas,
                eps=config.epsilon,
                weight_decay=config.weight_decay,
                amsgrad=config.amsgrad,
            )
        return self._optimizers[uid]

    @property
    def optimizers(self) -> dict[int, torch.optim.AdamW]:
        """Return a shallow UID map for durable organism snapshots."""

        return dict(self._optimizers)

    def install_optimizer(self, uid: int, optimizer: torch.optim.AdamW) -> None:
        """Adopt the optimizer of a shadow-trained cell after atomic admission."""

        expected = {id(item) for item in self.substrate._cell(uid).transform.parameters()}
        observed = {
            id(item)
            for group in optimizer.param_groups
            for item in group["params"]
        }
        if expected != observed:
            raise ValueError("optimizer does not own exactly the admitted cell transform")
        self._optimizers[uid] = optimizer

    def load_optimizers(self, optimizers: dict[int, torch.optim.AdamW]) -> None:
        unknown = set(optimizers).difference(int(uid) for uid in self.substrate.cells)
        if unknown:
            raise ValueError(f"optimizer map references unknown UIDs: {sorted(unknown)}")
        self._optimizers = dict(optimizers)

    def _clear_sparse_gradients(self) -> None:
        for uid in self._last_gradient_uids:
            for parameter in self.substrate._cell(uid).transform.parameters():
                parameter.grad = None
        self._last_gradient_uids.clear()

    def _run(self, example: LearningExample, *, gradients: bool) -> WaveResult:
        context = torch.enable_grad() if gradients else torch.inference_mode()
        with context:
            return self.substrate.run_thought(
                example.root_state,
                ingress_uids=example.ingress_uids,
                attention_mask=example.attention_mask,
                novelty=example.novelty,
                claim_address=example.claim_address,
                expected_merge_mode=example.expected_merge_mode,
                evidence_lineage=example.evidence_lineage,
            )

    def evaluate_loss(self, example: LearningExample) -> float:
        example.validate()
        result = self._run(example, gradients=False)
        return float(F.mse_loss(result.state.float(), example.target_state.float()).cpu())

    @staticmethod
    def _patch_uids(result: WaveResult) -> dict[str, int]:
        return {patch.patch_id: patch.source_uid for patch in result.patches}

    def _pending_events(self, result: WaveResult, example: LearningExample) -> list[CreditEvent]:
        events: list[CreditEvent] = []
        for record in result.eligibility:
            events.append(
                CreditEvent(
                    thought_id=record.thought_epoch,
                    target_kind=(
                        CreditTargetKind.DELTA
                        if record.patch_id is not None
                        else CreditTargetKind.RECEPTOR
                    ),
                    target_id=record.patch_id or f"uid:{record.uid}:receptor",
                    claim_address=example.claim_address,
                    role=(
                        CreditRole.TRANSFORM
                        if record.patch_id is not None
                        else CreditRole.CALIBRATION
                    ),
                    grade=CreditGrade.PENDING,
                    magnitude=0.0,
                    grade_confidence=0.0,
                    evidence_lineage=example.evidence_lineage,
                    dependency_group=record.dependency_patch_ids,
                    reason_code="outcome_unknown_no_persistent_update",
                )
            )
        return events

    def apply_external_loss(
        self,
        result: WaveResult,
        loss: torch.Tensor,
        *,
        claim_address: str,
        evidence_lineage: tuple[str, ...],
        invalid_dependency_uids: tuple[int, ...] = (),
    ) -> ExternalCreditResult:
        """Backpropagate a terminal loss without granting global cell ownership.

        The frozen expression cortex can produce a language loss far downstream
        from the wave substrate.  This method applies that loss to retained
        patches only, creates AdamW state only for those UIDs, and strengthens
        only receipts that actually reached retained tissue.  Shared organs and
        the resident core are intentionally left for their separate optimizer.
        """

        if loss.ndim != 0 or not bool(torch.isfinite(loss.detach())):
            raise ValueError("external loss must be one finite scalar")
        if not claim_address or not evidence_lineage:
            raise ValueError("external credit requires claim and evidence lineage")
        self._clear_sparse_gradients()
        retained = set(result.resolution.retained_patch_ids)
        invalid = set(invalid_dependency_uids)
        eligible_records = [
            record
            for record in result.eligibility
            if record.full_transform
            and record.patch_id in retained
            and record.uid not in invalid
        ]
        eligible_uids = tuple(sorted({record.uid for record in eligible_records}))
        executed_uids = {
            record.uid for record in result.eligibility if record.full_transform
        }
        loss.backward()
        self._last_gradient_uids.update(executed_uids)
        for uid in executed_uids.difference(eligible_uids):
            for parameter in self.substrate._cell(uid).transform.parameters():
                parameter.grad = None
        parameters = [
            parameter
            for uid in eligible_uids
            for parameter in self.substrate._cell(uid).transform.parameters()
            if parameter.grad is not None
        ]
        if parameters:
            torch.nn.utils.clip_grad_norm_(
                parameters, self.credit_policy.maximum_gradient_norm
            )
        for uid in eligible_uids:
            self._optimizer(uid).step()

        events = [
            CreditEvent(
                thought_id=record.thought_epoch,
                target_kind=CreditTargetKind.DELTA,
                target_id=record.patch_id or f"uid:{record.uid}",
                claim_address=claim_address,
                role=CreditRole.TRANSFORM,
                grade=CreditGrade.POSITIVE,
                magnitude=max(0.0, record.delta_norm),
                grade_confidence=record.ownership,
                evidence_lineage=evidence_lineage,
                dependency_group=record.dependency_patch_ids,
                reason_code="terminal_language_loss_retained_patch",
            )
            for record in eligible_records
        ]
        patch_uids = self._patch_uids(result)
        retained_uids = {
            patch_uids[patch_id]
            for patch_id in retained
            if patch_id in patch_uids
        }
        updated_edges: set[tuple[int, int]] = set()
        for receipt in result.receipts:
            if (
                receipt.disposition
                not in {ReceiptDisposition.FORWARDED, ReceiptDisposition.ABSORBED}
                or receipt.destination_uid not in retained_uids
            ):
                continue
            source = self.substrate._cell(receipt.source_uid)
            if receipt.destination_uid not in source.ports:
                continue
            edge = (receipt.source_uid, receipt.destination_uid)
            if edge in updated_edges:
                continue
            port = source.ports[receipt.destination_uid]
            source.ports[receipt.destination_uid] = NeighborPort(
                destination_uid=port.destination_uid,
                conductance=port.conductance,
                route_familiarity=port.route_familiarity
                + self.credit_policy.route_learning_rate
                * (1.0 - port.route_familiarity),
                enabled=port.enabled,
                entry_alias_uid=port.entry_alias_uid,
            )
            updated_edges.add(edge)
            events.append(
                CreditEvent(
                    thought_id=receipt.thought_epoch,
                    target_kind=CreditTargetKind.EDGE,
                    target_id=f"{receipt.source_uid}->{receipt.destination_uid}",
                    claim_address=claim_address,
                    role=CreditRole.ROUTE,
                    grade=CreditGrade.POSITIVE,
                    magnitude=1.0,
                    grade_confidence=receipt.ownership,
                    evidence_lineage=evidence_lineage,
                    dependency_group=(),
                    reason_code="terminal_language_loss_routed_usefully",
                )
            )
        for uid in executed_uids:
            for parameter in self.substrate._cell(uid).transform.parameters():
                parameter.grad = None
        self._last_gradient_uids.clear()
        return ExternalCreditResult(
            updated_uids=eligible_uids,
            updated_edges=tuple(sorted(updated_edges)),
            credit_events=tuple(events),
        )

    def train_step(
        self,
        example: LearningExample,
        *,
        outcome_available: bool = True,
        resolved_elsewhere: bool = False,
        invalid_dependency_uids: tuple[int, ...] = (),
        retention_probes: tuple[RetentionProbe, ...] = (),
    ) -> TrainStepResult:
        example.validate()
        self._clear_sparse_gradients()
        retention_before = tuple(
            self.evaluate_loss(probe.example) for probe in retention_probes
        )
        result = self._run(example, gradients=outcome_available)
        loss = F.mse_loss(result.state.float(), example.target_state.float())
        loss_before = float(loss.detach().cpu())
        if not outcome_available:
            events = tuple(self._pending_events(result, example))
            return TrainStepResult(
                thought_result=result,
                loss_before_update=loss_before,
                loss_after_update=loss_before,
                updated_uids=(),
                updated_edges=(),
                updated_receptor_uids=(),
                credit_events=events,
                outcome_applied=False,
                retention_rollback=False,
                retention_losses_before=retention_before,
                retention_losses_after=retention_before,
            )

        retained = set(result.resolution.retained_patch_ids)
        invalid_uids = set(invalid_dependency_uids)
        eligible_records = [
            record
            for record in result.eligibility
            if record.full_transform
            and record.patch_id in retained
            and record.uid not in invalid_uids
            and not (
                resolved_elsewhere
                and record.ownership < self.credit_policy.content_ownership_threshold
            )
        ]
        eligible_uids = tuple(sorted({record.uid for record in eligible_records}))
        executed_uids = {
            record.uid for record in result.eligibility if record.full_transform
        }
        loss.backward()
        self._last_gradient_uids.update(executed_uids)
        for uid in executed_uids.difference(eligible_uids):
            for parameter in self.substrate._cell(uid).transform.parameters():
                parameter.grad = None

        parameter_snapshots = {
            uid: [
                parameter.detach().clone()
                for parameter in self.substrate._cell(uid).transform.parameters()
            ]
            for uid in eligible_uids
        }
        optimizer_existed = {uid: uid in self._optimizers for uid in eligible_uids}
        optimizer_snapshots = {
            uid: (
                copy.deepcopy(self._optimizers[uid].state_dict())
                if uid in self._optimizers
                else None
            )
            for uid in eligible_uids
        }
        parameters = [
            parameter
            for uid in eligible_uids
            for parameter in self.substrate._cell(uid).transform.parameters()
            if parameter.grad is not None
        ]
        if parameters:
            torch.nn.utils.clip_grad_norm_(
                parameters, self.credit_policy.maximum_gradient_norm
            )
        for uid in eligible_uids:
            self._optimizer(uid).step()

        patch_uids = self._patch_uids(result)
        retained_uids = {
            patch_uids[patch_id]
            for patch_id in retained
            if patch_id in patch_uids
        }
        port_snapshots: dict[tuple[int, int], NeighborPort] = {}
        receptor_snapshots: dict[int, torch.Tensor] = {}
        updated_receptors: list[int] = []
        updated_edges: list[tuple[int, int]] = []
        credited_edges: set[tuple[int, int]] = set()
        events: list[CreditEvent] = []
        for record in eligible_records:
            events.append(
                CreditEvent(
                    thought_id=record.thought_epoch,
                    target_kind=CreditTargetKind.DELTA,
                    target_id=record.patch_id or f"uid:{record.uid}",
                    claim_address=example.claim_address,
                    role=CreditRole.TRANSFORM,
                    grade=CreditGrade.POSITIVE,
                    magnitude=max(0.0, record.delta_norm),
                    grade_confidence=record.ownership,
                    evidence_lineage=example.evidence_lineage,
                    dependency_group=record.dependency_patch_ids,
                    reason_code="contribution_retained",
                )
            )
        for record in result.eligibility:
            if (
                resolved_elsewhere
                and record.ownership < self.credit_policy.content_ownership_threshold
            ):
                receptor = self.substrate._cell(record.uid).receptor
                receptor_snapshots.setdefault(
                    record.uid, receptor.calibration_bias.detach().clone()
                )
                with torch.no_grad():
                    receptor.calibration_bias.sub_(
                        self.credit_policy.receptor_learning_rate
                        * (1.0 - record.ownership)
                    )
                updated_receptors.append(record.uid)
                events.append(
                    CreditEvent(
                        thought_id=record.thought_epoch,
                        target_kind=CreditTargetKind.RECEPTOR,
                        target_id=f"uid:{record.uid}:receptor",
                        claim_address=example.claim_address,
                        role=CreditRole.CALIBRATION,
                        grade=CreditGrade.POSITIVE,
                        magnitude=1.0 - record.ownership,
                        grade_confidence=record.coverage,
                        evidence_lineage=example.evidence_lineage,
                        dependency_group=record.dependency_patch_ids,
                        reason_code="resolved_elsewhere_boundary_only",
                    )
                )
        for uid in invalid_uids.intersection(executed_uids):
            events.append(
                CreditEvent(
                    thought_id=result.eligibility[0].thought_epoch,
                    target_kind=CreditTargetKind.DEPENDENCY,
                    target_id=f"uid:{uid}:dependency",
                    claim_address=example.claim_address,
                    role=CreditRole.CALIBRATION,
                    grade=CreditGrade.NEGATIVE,
                    magnitude=1.0,
                    grade_confidence=1.0,
                    evidence_lineage=example.evidence_lineage,
                    dependency_group=(),
                    reason_code="correct_result_invalid_dependency",
                )
            )
        for receipt in result.receipts:
            if (
                receipt.disposition
                not in {ReceiptDisposition.FORWARDED, ReceiptDisposition.ABSORBED}
                or receipt.destination_uid not in retained_uids
            ):
                continue
            source = self.substrate._cell(receipt.source_uid)
            if receipt.destination_uid not in source.ports:
                continue
            edge = (receipt.source_uid, receipt.destination_uid)
            if edge in credited_edges:
                continue
            credited_edges.add(edge)
            port = source.ports[receipt.destination_uid]
            port_snapshots.setdefault(edge, port)
            source.ports[receipt.destination_uid] = NeighborPort(
                destination_uid=port.destination_uid,
                conductance=port.conductance,
                route_familiarity=port.route_familiarity
                + self.credit_policy.route_learning_rate
                * (1.0 - port.route_familiarity),
                enabled=port.enabled,
            )
            updated_edges.append(edge)
            events.append(
                CreditEvent(
                    thought_id=receipt.thought_epoch,
                    target_kind=CreditTargetKind.EDGE,
                    target_id=f"{receipt.source_uid}->{receipt.destination_uid}",
                    claim_address=example.claim_address,
                    role=CreditRole.ROUTE,
                    grade=CreditGrade.POSITIVE,
                    magnitude=1.0,
                    grade_confidence=receipt.ownership,
                    evidence_lineage=example.evidence_lineage,
                    dependency_group=(),
                    reason_code="routed_usefully",
                )
            )

        retention_after = tuple(
            self.evaluate_loss(probe.example) for probe in retention_probes
        )
        rollback = any(
            after > before + probe.maximum_absolute_regression
            for before, after, probe in zip(
                retention_before, retention_after, retention_probes
            )
        )
        if rollback:
            with torch.no_grad():
                for uid, snapshots in parameter_snapshots.items():
                    for parameter, snapshot in zip(
                        self.substrate._cell(uid).transform.parameters(), snapshots
                    ):
                        parameter.copy_(snapshot)
            for edge, port in port_snapshots.items():
                self.substrate._cell(edge[0]).ports[edge[1]] = port
            with torch.no_grad():
                for uid, snapshot in receptor_snapshots.items():
                    self.substrate._cell(uid).receptor.calibration_bias.copy_(snapshot)
            for uid in eligible_uids:
                if optimizer_existed[uid]:
                    assert optimizer_snapshots[uid] is not None
                    self._optimizers[uid].load_state_dict(optimizer_snapshots[uid])
                else:
                    self._optimizers.pop(uid, None)
            updated_uids: tuple[int, ...] = ()
            final_edges: tuple[tuple[int, int], ...] = ()
            final_receptors: tuple[int, ...] = ()
            retention_after = tuple(
                self.evaluate_loss(probe.example) for probe in retention_probes
            )
            events = [
                CreditEvent(
                    **{
                        **event.__dict__,
                        "grade": CreditGrade.NEUTRAL,
                        "reason_code": "retention_guard_rollback",
                    }
                )
                for event in events
            ]
        else:
            updated_uids = eligible_uids
            final_edges = tuple(sorted(set(updated_edges)))
            final_receptors = tuple(sorted(set(updated_receptors)))
        loss_after = self.evaluate_loss(example)
        for uid in executed_uids:
            for parameter in self.substrate._cell(uid).transform.parameters():
                parameter.grad = None
        self._last_gradient_uids.clear()
        return TrainStepResult(
            thought_result=result,
            loss_before_update=loss_before,
            loss_after_update=loss_after,
            updated_uids=updated_uids,
            updated_edges=final_edges,
            updated_receptor_uids=final_receptors,
            credit_events=tuple(events),
            outcome_applied=not rollback,
            retention_rollback=rollback,
            retention_losses_before=retention_before,
            retention_losses_after=retention_after,
        )

    def optimizer_state_telemetry(self) -> dict[str, Any]:
        return {
            "optimizer_uids": list(self.optimizer_uids),
            "optimizer_uid_count": len(self._optimizers),
            "policy": self.optimizer_config.policy,
            "state_tensor_count": sum(
                sum(
                    isinstance(value, torch.Tensor)
                    for state in optimizer.state.values()
                    for value in state.values()
                )
                for optimizer in self._optimizers.values()
            ),
        }
