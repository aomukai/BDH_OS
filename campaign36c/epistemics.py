from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from typing import Any

import torch
import torch.nn.functional as F


class ResultGrade(str, Enum):
    SUPPORTED = "supported"
    REFUTED = "refuted"
    UNRESOLVED = "unresolved"


class PatchRelationship(str, Enum):
    SEQUENTIAL = "sequential"
    EQUIVALENT = "equivalent"
    SUBSUMING = "subsuming"
    REINFORCING = "reinforcing"
    COMPLEMENTARY = "complementary"
    CONDITIONAL = "conditional"
    CONTRADICTORY = "contradictory"


class ReceiptDisposition(str, Enum):
    REJECTED = "rejected"
    ABSORBED = "absorbed"
    FORWARDED = "forwarded"
    UNRESOLVED = "unresolved"


class CreditTargetKind(str, Enum):
    DELTA = "delta"
    DEPENDENCY = "dependency"
    EDGE = "edge"
    RECEPTOR = "receptor"
    STRUCTURAL_CANDIDATE = "structural_candidate"


class CreditRole(str, Enum):
    TRANSFORM = "transform"
    ROUTE = "route"
    CALIBRATION = "calibration"
    INQUIRY = "inquiry"
    STRUCTURAL = "structural"
    COMPUTE_HARM = "compute_harm"
    EVIDENCE_INDEPENDENCE = "evidence_independence"


class CreditGrade(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    PENDING = "pending"


@dataclass(frozen=True)
class LatentPatch:
    patch_id: str
    source_uid: int
    base_version: str
    claim_address: str
    expected_merge_mode: str
    read_footprint: tuple[int, ...]
    write_footprint: tuple[int, ...]
    operation_delta: torch.Tensor
    effect_signature: tuple[tuple[int, int], ...]
    applicability_conditions: tuple[str, ...]
    dependency_ids: tuple[str, ...]
    evidence_lineage: tuple[str, ...]
    route_provenance: tuple[tuple[int, ...], ...]
    support: float
    calibration: float


@dataclass(frozen=True)
class EligibilityRecord:
    thought_epoch: int
    wave_index: int
    uid: int
    patch_id: str | None
    direct_predecessors: tuple[int, ...]
    dependency_patch_ids: tuple[str, ...]
    outgoing_destinations: tuple[int, ...]
    ownership: float
    coverage: float
    unresolved_residual: float
    delta_norm: float
    full_transform: bool
    disposition: ReceiptDisposition


@dataclass(frozen=True)
class ReceiptRecord:
    thought_epoch: int
    wave_index: int
    source_uid: int
    destination_uid: int
    disposition: ReceiptDisposition
    ownership: float
    coverage: float
    unresolved_residual: float


@dataclass(frozen=True)
class CandidateHypothesis:
    patch_ids: tuple[str, ...]
    support: float
    evidence_lineages: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class ResolutionEnvelope:
    grade: ResultGrade
    consensus_patch_ids: tuple[str, ...]
    hypotheses: tuple[CandidateHypothesis, ...]
    unresolved_mass: float
    conflict_summary: tuple[tuple[str, str, str], ...]
    retained_patch_ids: tuple[str, ...]


@dataclass(frozen=True)
class CreditEvent:
    thought_id: int
    target_kind: CreditTargetKind
    target_id: str
    claim_address: str
    role: CreditRole
    grade: CreditGrade
    magnitude: float
    grade_confidence: float
    evidence_lineage: tuple[str, ...]
    dependency_group: tuple[str, ...]
    reason_code: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "thought_id": self.thought_id,
            "target_kind": self.target_kind.value,
            "target_id": self.target_id,
            "claim_address": self.claim_address,
            "role": self.role.value,
            "grade": self.grade.value,
            "magnitude": self.magnitude,
            "grade_confidence": self.grade_confidence,
            "evidence_lineage": list(self.evidence_lineage),
            "dependency_group": list(self.dependency_group),
            "reason_code": self.reason_code,
        }


def make_latent_patch(
    *,
    patch_id: str,
    source_uid: int,
    base_version: str,
    claim_address: str,
    expected_merge_mode: str,
    state_before: torch.Tensor,
    operation_delta: torch.Tensor,
    dependency_ids: tuple[str, ...],
    evidence_lineage: tuple[str, ...],
    route_provenance: tuple[tuple[int, ...], ...],
    ownership: float,
    coverage: float,
    footprint_size: int = 16,
    applicability_conditions: tuple[str, ...] = (),
) -> LatentPatch:
    if operation_delta.ndim != 3 or state_before.shape != operation_delta.shape:
        raise ValueError("patch state and delta must share [batch,token,width] shape")
    width = operation_delta.size(-1)
    count = min(max(1, footprint_size), width)
    read_scores = state_before.detach().float().abs().mean(dim=(0, 1))
    write_scores = operation_delta.detach().float().abs().mean(dim=(0, 1))
    read = tuple(sorted(torch.topk(read_scores, count).indices.cpu().tolist()))
    write_ranked = torch.topk(write_scores, count).indices.cpu().tolist()
    write = tuple(sorted(write_ranked))
    signs = operation_delta.detach().float().mean(dim=(0, 1))
    signature = tuple(
        sorted((int(index), 1 if float(signs[index]) >= 0 else -1) for index in write)
    )
    return LatentPatch(
        patch_id=patch_id,
        source_uid=source_uid,
        base_version=base_version,
        claim_address=claim_address,
        expected_merge_mode=expected_merge_mode,
        read_footprint=read,
        write_footprint=write,
        operation_delta=operation_delta,
        effect_signature=signature,
        applicability_conditions=applicability_conditions,
        dependency_ids=dependency_ids,
        evidence_lineage=evidence_lineage,
        route_provenance=route_provenance,
        support=max(0.0, min(1.0, ownership * coverage)),
        calibration=max(0.0, min(1.0, ownership)),
    )


class PatchReducer:
    """Bounded, deterministic reducer for the Stage-3 credit skeleton."""

    def __init__(self, *, contradiction_cosine: float = -0.25) -> None:
        self.contradiction_cosine = contradiction_cosine

    @staticmethod
    def _cosine(left: LatentPatch, right: LatentPatch) -> float:
        left_delta = left.operation_delta.detach().float().reshape(-1)
        right_delta = right.operation_delta.detach().float().reshape(-1)
        return float(F.cosine_similarity(left_delta, right_delta, dim=0).cpu())

    def classify(
        self,
        left: LatentPatch,
        right: LatentPatch,
    ) -> PatchRelationship:
        if left.patch_id in right.dependency_ids or right.patch_id in left.dependency_ids:
            return PatchRelationship.SEQUENTIAL
        if left.claim_address != right.claim_address:
            return PatchRelationship.COMPLEMENTARY
        if left.applicability_conditions != right.applicability_conditions:
            return PatchRelationship.CONDITIONAL
        left_write = set(left.write_footprint)
        right_write = set(right.write_footprint)
        if not left_write.intersection(right_write):
            return PatchRelationship.COMPLEMENTARY
        if left.effect_signature == right.effect_signature:
            if left.evidence_lineage == right.evidence_lineage:
                return PatchRelationship.EQUIVALENT
            return PatchRelationship.REINFORCING
        cosine = self._cosine(left, right)
        if (
            left.expected_merge_mode == "single_value"
            and right.expected_merge_mode == "single_value"
            and cosine <= self.contradiction_cosine
        ):
            return PatchRelationship.CONTRADICTORY
        if left_write <= right_write or right_write <= left_write:
            return PatchRelationship.SUBSUMING
        if cosine >= 0.8:
            return PatchRelationship.REINFORCING
        return PatchRelationship.COMPLEMENTARY

    @staticmethod
    def _dependency_closure(
        patch_id: str,
        by_id: dict[str, LatentPatch],
    ) -> set[str]:
        retained: set[str] = set()
        stack = [patch_id]
        while stack:
            current = stack.pop()
            if current in retained or current not in by_id:
                continue
            retained.add(current)
            stack.extend(by_id[current].dependency_ids)
        return retained

    def reduce(
        self,
        patches: tuple[LatentPatch, ...],
        *,
        terminal_patch_ids: tuple[str, ...] | None = None,
        exhausted: bool = False,
    ) -> ResolutionEnvelope:
        ordered = tuple(sorted(patches, key=lambda patch: patch.patch_id))
        by_id = {patch.patch_id: patch for patch in ordered}
        terminal_ids = terminal_patch_ids or tuple(by_id)
        retained: set[str] = set()
        for patch_id in terminal_ids:
            retained.update(self._dependency_closure(patch_id, by_id))
        retained_patches = tuple(
            patch for patch in ordered if patch.patch_id in retained
        )
        relationships = [
            (left, right, self.classify(left, right))
            for left, right in combinations(retained_patches, 2)
        ]
        conflicts = tuple(
            (left.patch_id, right.patch_id, relationship.value)
            for left, right, relationship in relationships
            if relationship is PatchRelationship.CONTRADICTORY
        )
        if exhausted or conflicts or not retained_patches:
            hypotheses = tuple(
                CandidateHypothesis(
                    patch_ids=(patch.patch_id,),
                    support=patch.support,
                    evidence_lineages=(patch.evidence_lineage,),
                )
                for patch in retained_patches
                if any(patch.patch_id in conflict[:2] for conflict in conflicts)
            )
            return ResolutionEnvelope(
                grade=ResultGrade.UNRESOLVED,
                consensus_patch_ids=(),
                hypotheses=hypotheses,
                unresolved_mass=1.0 if exhausted or not retained_patches else 0.5,
                conflict_summary=conflicts,
                retained_patch_ids=tuple(sorted(retained)),
            )

        representatives: list[LatentPatch] = []
        grouped: set[str] = set()
        for patch in retained_patches:
            if patch.patch_id in grouped:
                continue
            equivalent = [patch]
            for candidate in retained_patches:
                if candidate.patch_id == patch.patch_id or candidate.patch_id in grouped:
                    continue
                relationship = self.classify(patch, candidate)
                if relationship in {
                    PatchRelationship.EQUIVALENT,
                    PatchRelationship.REINFORCING,
                }:
                    equivalent.append(candidate)
            representative = max(
                equivalent,
                key=lambda item: (item.support, item.calibration, item.patch_id),
            )
            representatives.append(representative)
            grouped.update(item.patch_id for item in equivalent)
        return ResolutionEnvelope(
            grade=ResultGrade.SUPPORTED,
            consensus_patch_ids=tuple(
                sorted(patch.patch_id for patch in representatives)
            ),
            hypotheses=(),
            unresolved_mass=0.0,
            conflict_summary=(),
            retained_patch_ids=tuple(sorted(retained)),
        )
