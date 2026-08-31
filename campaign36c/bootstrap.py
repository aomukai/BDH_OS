from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from cortex.config import CortexConfig
from cortex.intention import IntentionHead
from cortex.lfm import LFMExpressionCortex
from cortex.siglip2 import (
    BoundedVisualResampler,
    Siglip2ProjectorConfig,
    VISUAL_PROJECTOR_SCHEMA,
)

from .config import CellOptimizerConfig
from .learning import ExecutedSubgraphTrainer
from .organism import Campaign36COrganism, OrganismConfig, OrganismThought
from .persistence import PackedCellStore


BOOTSTRAP_MANIFEST_IDENTITY = (
    "e1d760e264717d05676076429a2e13e46cd05da6d8376169feaad579121ac2fb"
)
CAMPAIGN36C_BOOTSTRAP_SNAPSHOT_SCHEMA = "ninereeds_campaign36c_bootstrap_snapshot_v1"
CAMPAIGN36C_VISUAL_STUDENT_SCHEMA = "ninereeds_campaign36c_visual_student_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_source(path_text: str, manifest_root: Path) -> Path:
    declared = Path(path_text)
    if declared.is_file():
        return declared
    candidate = manifest_root / declared.name
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"bootstrap source is unavailable: {path_text}")


def load_features(
    path: Path,
) -> dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
    result: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]] = {}
    with np.load(path, allow_pickle=False) as values:
        hashes = [str(item) for item in values["asset_sha256"].tolist()]
        for index, digest in enumerate(hashes):
            result[digest] = (
                torch.from_numpy(values[f"patch_{index:04d}"]),
                torch.from_numpy(values[f"mask_{index:04d}"]),
                torch.from_numpy(values[f"shape_{index:04d}"]),
            )
    if not result:
        raise ValueError("visual feature archive is empty")
    return result


def load_frozen_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version": "ninereeds_foundation_visual_material_v1",
        "input_manifest_sha256": BOOTSTRAP_MANIFEST_IDENTITY,
        "event_count": 30_220,
        "session_count": 31,
        "order_policy": "declared_only",
        "shuffle_allowed": False,
    }
    mismatches = {
        key: {"expected": expected, "observed": manifest.get(key)}
        for key, expected in required.items()
        if manifest.get(key) != expected
    }
    if mismatches:
        raise ValueError(f"bootstrap manifest is not the frozen course: {mismatches}")
    if len(manifest.get("sessions", [])) != 31:
        raise ValueError("frozen bootstrap manifest does not contain 31 sessions")
    return manifest


@dataclass(frozen=True)
class VisualObjectiveResult:
    loss: torch.Tensor
    thought: OrganismThought
    attention_mask: torch.Tensor
    target_token_exact: bool
    target_probability: float

    @property
    def internal_residual(self) -> float:
        return 1.0 - self.target_probability


class Campaign36CVisualStudent(nn.Module):
    """Frozen speech organ around the 25M continuity core and sparse tissue."""

    def __init__(
        self,
        organism: Campaign36COrganism,
        resampler: BoundedVisualResampler,
        intention: IntentionHead,
        expression: LFMExpressionCortex,
        *,
        cortex_config: CortexConfig,
        donor_identity: Mapping[str, Any],
    ) -> None:
        super().__init__()
        self.organism = organism
        self.resampler = resampler
        self.intention = intention
        self.expression = expression
        self.cortex_config = cortex_config
        self.donor_identity = dict(donor_identity)

    @classmethod
    def from_organ_donor(
        cls,
        parent: Path,
        *,
        organism_config: OrganismConfig | None = None,
        frozen_dtype: torch.dtype = torch.bfloat16,
        local_files_only: bool = True,
    ) -> "Campaign36CVisualStudent":
        document = torch.load(parent, map_location="cpu", weights_only=True)
        visual = document.get("visual_state")
        if not visual or visual.get("schema_version") != VISUAL_PROJECTOR_SCHEMA:
            raise ValueError("organ donor lacks the frozen visual resampler state")
        bridge = document.get("organ_bridge_state")
        if not isinstance(bridge, dict):
            raise ValueError("organ donor lacks organ bridge state")
        cortex_config = CortexConfig(**document.get("cortex_config", {}))
        config = organism_config or OrganismConfig()
        cortex_config.validate_for_ninereeds(config.width)
        organism = Campaign36COrganism.embryo(config)
        visual_config = Siglip2ProjectorConfig(**visual["config"])
        resampler = BoundedVisualResampler(visual_config)
        resampler.load_state_dict(visual["resampler_state"], strict=True)
        intention = IntentionHead(
            config.width,
            num_tokens=cortex_config.intention_tokens,
            num_heads=8,
        )
        intention.load_state_dict(bridge["intention"], strict=True)
        expression = LFMExpressionCortex(
            config.width,
            config=cortex_config,
            dtype=frozen_dtype,
            local_files_only=local_files_only,
        )
        expression.projector.load_state_dict(
            bridge["expression_projector"], strict=True
        )
        return cls(
            organism,
            resampler,
            intention,
            expression,
            cortex_config=cortex_config,
            donor_identity={
                "path": str(parent),
                "sha256": sha256(parent),
                "role": "organ_initialization_only_no_tissue_or_training_ancestry",
            },
        )

    @classmethod
    def from_snapshot(
        cls,
        shared_document: Mapping[str, Any],
        substrate: Any,
        *,
        frozen_dtype: torch.dtype = torch.bfloat16,
        local_files_only: bool = True,
    ) -> "Campaign36CVisualStudent":
        state = shared_document["student"]
        if state.get("schema_version") != CAMPAIGN36C_VISUAL_STUDENT_SCHEMA:
            raise ValueError("snapshot does not contain a Campaign 36C visual student")
        config = OrganismConfig(**state["organism_config"])
        embryo = Campaign36COrganism.embryo(config)
        embryo.core.load_state_dict(state["core_state"], strict=True)
        organism = Campaign36COrganism(
            embryo.core,
            substrate,
            ingress_uids=state["ingress_uids"],
            config=config,
        )
        cortex_config = CortexConfig(**state["cortex_config"])
        visual_config = Siglip2ProjectorConfig(**state["visual_config"])
        resampler = BoundedVisualResampler(visual_config)
        resampler.load_state_dict(state["visual_resampler_state"], strict=True)
        intention = IntentionHead(
            config.width,
            num_tokens=cortex_config.intention_tokens,
            num_heads=8,
        )
        intention.load_state_dict(state["intention_state"], strict=True)
        expression = LFMExpressionCortex(
            config.width,
            config=cortex_config,
            dtype=frozen_dtype,
            local_files_only=local_files_only,
        )
        expression.projector.load_state_dict(
            state["expression_projector_state"], strict=True
        )
        return cls(
            organism,
            resampler,
            intention,
            expression,
            cortex_config=cortex_config,
            donor_identity=state["donor_identity"],
        )

    def train(self, mode: bool = True) -> "Campaign36CVisualStudent":
        super().train(mode)
        self.expression.model.eval()
        return self

    def place(
        self,
        *,
        core_device: torch.device,
        tissue_device: torch.device,
        dtype: torch.dtype = torch.bfloat16,
    ) -> dict[str, Any]:
        inventory = self.organism.place(
            core_device=core_device,
            tissue_device=tissue_device,
            dtype=dtype,
        )
        self.resampler.to(device=core_device, dtype=dtype)
        self.intention.to(device=tissue_device, dtype=dtype)
        self.expression.to(device=tissue_device, dtype=dtype)
        self.expression.model.requires_grad_(False)
        return {
            "core_device": str(core_device),
            "tissue_device": str(tissue_device),
            "dtype": str(dtype),
            **inventory,
        }

    def shared_trainable_parameters(self) -> tuple[nn.Parameter, ...]:
        return tuple(
            parameter
            for parameter in (
                *self.organism.continuity_parameters(),
                *self.resampler.parameters(),
                *self.intention.parameters(),
                *self.expression.projector.parameters(),
            )
            if parameter.requires_grad
        )

    def visual_objective(
        self,
        feature: tuple[torch.Tensor, torch.Tensor, torch.Tensor],
        completion: str,
        *,
        claim_address: str,
        evidence_lineage: tuple[str, ...],
        novelty: float,
        retain_terminal_gradient: bool = False,
    ) -> VisualObjectiveResult:
        patch, mask, shape = feature
        visual_parameter = next(self.resampler.parameters())
        observed, observed_mask = self.resampler(
            patch.unsqueeze(0).to(
                device=visual_parameter.device, dtype=visual_parameter.dtype
            ),
            mask.unsqueeze(0).to(visual_parameter.device),
            shape.unsqueeze(0).to(visual_parameter.device),
        )
        thought = self.organism.think(
            observed,
            attention_mask=observed_mask,
            novelty=novelty,
            claim_address=claim_address,
            evidence_lineage=evidence_lineage,
        )
        if retain_terminal_gradient:
            thought.result.state.retain_grad()
        tissue_mask = observed_mask.to(thought.result.state.device)
        intentions = self.intention(thought.result.state, tissue_mask)
        encoded = self.expression.tokenizer(
            [completion],
            add_special_tokens=False,
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )
        response_ids = encoded["input_ids"]
        response_mask = encoded.get(
            "attention_mask", torch.ones_like(response_ids)
        )
        prefix = self.expression.prefix_embeddings(intentions)
        model_parameter = next(self.expression.model.parameters())
        model_device = model_parameter.device
        prefix = prefix.to(device=model_device, dtype=model_parameter.dtype)
        response_ids = response_ids.to(model_device)
        response_mask = response_mask.to(model_device)
        token_embeddings = self.expression.model.get_input_embeddings()(response_ids)
        inputs_embeds = torch.cat([prefix, token_embeddings], dim=1)
        prefix_mask = torch.ones(
            prefix.shape[:2], dtype=response_mask.dtype, device=model_device
        )
        attention_mask = torch.cat([prefix_mask, response_mask], dim=1)
        outputs = self.expression.model(
            inputs_embeds=inputs_embeds,
            attention_mask=attention_mask,
            use_cache=False,
            return_dict=True,
        )
        prefix_length = prefix.size(1)
        logits = outputs.logits[
            :, prefix_length - 1 : prefix_length - 1 + response_ids.size(1), :
        ]
        flat_logits = logits.reshape(-1, logits.size(-1))
        flat_targets = response_ids.reshape(-1)
        flat_mask = response_mask.reshape(-1).bool()
        selected_logits = flat_logits[flat_mask]
        selected_targets = flat_targets[flat_mask]
        if selected_targets.numel() == 0:
            raise ValueError("visual completion tokenized to no supervised tokens")
        loss = F.cross_entropy(selected_logits.float(), selected_targets)
        with torch.no_grad():
            probabilities = selected_logits.float().softmax(dim=-1)
            target_probability = probabilities.gather(
                1, selected_targets.unsqueeze(1)
            ).mean()
            exact = bool(torch.equal(selected_logits.argmax(dim=-1), selected_targets))
        return VisualObjectiveResult(
            loss=loss,
            thought=thought,
            attention_mask=tissue_mask,
            target_token_exact=exact,
            target_probability=float(target_probability.cpu()),
        )

    def shared_state(self) -> dict[str, Any]:
        return {
            "schema_version": CAMPAIGN36C_VISUAL_STUDENT_SCHEMA,
            "organism_config": dataclasses.asdict(self.organism.organism_config),
            "ingress_uids": list(self.organism.ingress_uids),
            "cortex_config": dataclasses.asdict(self.cortex_config),
            "donor_identity": self.donor_identity,
            "core_state": self.organism.core.state_dict(),
            "visual_config": dataclasses.asdict(self.resampler.config),
            "visual_resampler_state": self.resampler.state_dict(),
            "intention_state": self.intention.state_dict(),
            "expression_projector_state": self.expression.projector.state_dict(),
        }


def _cpu_value(value: Any) -> Any:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().clone()
    if isinstance(value, dict):
        return {key: _cpu_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_cpu_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_cpu_value(item) for item in value)
    return value


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with temporary.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _atomic_torch_save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        torch.save(value, temporary)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class OrganismSnapshotStore:
    """Atomic shared-state plus packed-cell snapshots for a living organism."""

    def __init__(self, root: Path, *, page_capacity: int = 20) -> None:
        self.root = root
        self.shared_root = root / "shared"
        self.snapshot_root = root / "snapshots"
        self.packed = PackedCellStore(root / "cells", page_capacity=page_capacity)
        self.shared_root.mkdir(parents=True, exist_ok=True)
        self.snapshot_root.mkdir(parents=True, exist_ok=True)

    @property
    def latest_path(self) -> Path:
        return self.root / "latest.json"

    def save(
        self,
        name: str,
        student: Campaign36CVisualStudent,
        sparse_trainer: ExecutedSubgraphTrainer,
        shared_optimizer: torch.optim.Optimizer,
        *,
        progress: Mapping[str, Any],
        next_uid: int,
        developmental_state: Mapping[str, Any] | None = None,
        developmental_summary: Mapping[str, Any] | None = None,
    ) -> Path:
        if not name or any(
            character
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for character in name
        ):
            raise ValueError("snapshot names use letters, digits, hyphen, underscore")
        optimizer_configs = {
            uid: sparse_trainer.optimizer_config
            for uid in sparse_trainer.optimizers
        }
        commit = self.packed.commit_substrate(
            student.organism.substrate,
            optimizers=sparse_trainer.optimizers,
            optimizer_configs=optimizer_configs,
            reason=f"organism_snapshot:{name}",
        )
        packed_snapshot = self.packed.create_snapshot(name)
        shared_path = self.shared_root / f"{name}.pt"
        shared_document = {
            "schema_version": CAMPAIGN36C_BOOTSTRAP_SNAPSHOT_SCHEMA,
            "snapshot_name": name,
            "created_unix_ns": time.time_ns(),
            "student": _cpu_value(student.shared_state()),
            "shared_optimizer_state": _cpu_value(shared_optimizer.state_dict()),
            "progress": dict(progress),
            "next_uid": int(next_uid),
            "developmental_state": _cpu_value(dict(developmental_state or {})),
            "developmental_summary": dict(developmental_summary or {}),
            "runtime_state": {
                "cpu_rng_state": torch.random.get_rng_state(),
                "cuda_rng_states": (
                    torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []
                ),
            },
        }
        _atomic_torch_save(shared_path, shared_document)
        document = {
            "schema_version": CAMPAIGN36C_BOOTSTRAP_SNAPSHOT_SCHEMA,
            "snapshot_name": name,
            "created_unix_ns": shared_document["created_unix_ns"],
            "shared_path": str(shared_path),
            "shared_sha256": sha256(shared_path),
            "shared_bytes": shared_path.stat().st_size,
            "packed_snapshot_path": str(packed_snapshot),
            "packed_manifest_sha256": commit.manifest_sha256,
            "packed_commit_epoch": commit.commit_epoch,
            "active_uids": sorted(int(uid) for uid in student.organism.substrate.cells),
            "next_uid": int(next_uid),
            "progress": dict(progress),
        }
        path = self.snapshot_root / f"{name}.json"
        _atomic_json(path, document)
        _atomic_json(self.latest_path, document)
        return path

    def latest(self) -> dict[str, Any] | None:
        if not self.latest_path.is_file():
            return None
        value = json.loads(self.latest_path.read_text(encoding="utf-8"))
        if value.get("schema_version") != CAMPAIGN36C_BOOTSTRAP_SNAPSHOT_SCHEMA:
            raise ValueError("latest organism snapshot has the wrong schema")
        shared_path = Path(value["shared_path"])
        if not shared_path.is_file() or sha256(shared_path) != value["shared_sha256"]:
            raise ValueError("latest organism shared state is missing or corrupt")
        return value

    def restore_tissue(
        self,
        name: str,
        *,
        device: torch.device,
    ) -> tuple[Any, dict[int, torch.optim.AdamW]]:
        self.packed.restore_snapshot(name)
        substrate, optimizers, _configs, _anatomy = self.packed.load_substrate(
            device=device, restore_rng=False
        )
        return substrate, optimizers

    def load_shared(self, name: str) -> dict[str, Any]:
        path = self.shared_root / f"{name}.pt"
        value = torch.load(path, map_location="cpu", weights_only=True)
        if value.get("schema_version") != CAMPAIGN36C_BOOTSTRAP_SNAPSHOT_SCHEMA:
            raise ValueError("organism shared snapshot has the wrong schema")
        return value


def clip_by_device(parameters: Iterable[nn.Parameter], maximum: float) -> None:
    grouped: dict[torch.device, list[nn.Parameter]] = {}
    for parameter in parameters:
        if parameter.grad is not None:
            grouped.setdefault(parameter.device, []).append(parameter)
    for values in grouped.values():
        torch.nn.utils.clip_grad_norm_(values, maximum, foreach=False)


def clear_gradients(parameters: Iterable[nn.Parameter]) -> None:
    for parameter in parameters:
        parameter.grad = None
