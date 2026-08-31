from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

import torch

from .cell import StandaloneBDHCell
from .checkpoint import build_cell_optimizer, tensor_storage_bytes
from .config import (
    BDHCellConfig,
    CellOptimizerConfig,
    ReceptorConfig,
    SparseWaveConfig,
)
from .wave import NeighborPort, SparseWaveSubstrate, WaveCell


PACKED_STORE_SCHEMA = "ninereeds_campaign36c_packed_store_v0"
PACKED_SEGMENT_SCHEMA = "ninereeds_campaign36c_packed_segment_v0"
PACKED_RECORD_SCHEMA = "ninereeds_campaign36c_cell_record_v0"
PACKED_SNAPSHOT_SCHEMA = "ninereeds_campaign36c_packed_snapshot_v0"


class FaultPoint(str, Enum):
    AFTER_PREPARE = "after_prepare"
    AFTER_WRITE = "after_write"
    AFTER_VALIDATE = "after_validate"
    AFTER_COMMIT = "after_commit"
    AFTER_PUBLISH = "after_publish"


class InjectedCrash(RuntimeError):
    pass


class CorruptStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecordLocation:
    segment_id: str
    record_index: int
    record_generation: int
    record_bytes: int


@dataclass(frozen=True)
class CommitResult:
    transaction_id: str
    commit_epoch: int
    journal_sequence: int
    written_uids: tuple[int, ...]
    segment_ids: tuple[str, ...]
    bytes_written: int
    manifest_sha256: str


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


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


def _dtype_name(dtype: torch.dtype) -> str:
    name = str(dtype)
    if not name.startswith("torch."):
        raise ValueError(f"unsupported torch dtype: {dtype}")
    return name.removeprefix("torch.")


def _resolve_dtype(name: str) -> torch.dtype:
    result = getattr(torch, name, None)
    if not isinstance(result, torch.dtype):
        raise ValueError(f"unsupported packed-record dtype: {name}")
    return result


class PackedCellStore:
    """Copy-on-write page store with storage-location-independent cell UIDs.

    A segment is one physical page containing several independently
    checksummed records.  Cognitive edges remain inside records and the
    manifest's compact adjacency index; segment co-location grants no route.
    """

    def __init__(self, root: str | Path, *, page_capacity: int = 20) -> None:
        if page_capacity <= 1:
            raise ValueError("packed pages must contain capacity for multiple cells")
        self.root = Path(root)
        self.page_capacity = int(page_capacity)
        self.segment_root = self.root / "segments"
        self.snapshot_root = self.root / "snapshots"
        self.manifest_path = self.root / "manifest.json"
        self.journal_path = self.root / "journal.jsonl"
        self.uid_high_watermark_path = self.root / "uid-high-watermark"
        self.root.mkdir(parents=True, exist_ok=True)
        self.segment_root.mkdir(parents=True, exist_ok=True)
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        if not self.journal_path.exists():
            _atomic_write(self.journal_path, b"")
        if not self.manifest_path.exists():
            manifest = {
                "schema_version": PACKED_STORE_SCHEMA,
                "store_id": uuid.uuid4().hex,
                "commit_epoch": 0,
                "journal_sequence": 0,
                "parent_manifest_sha256": None,
                "created_unix_ns": time.time_ns(),
                "page_capacity": self.page_capacity,
                "substrate_config": None,
                "substrate_graph_version": 0,
                "substrate_thought_epoch": 0,
                "segments": [],
                "uid_index": {},
                "quarantine_index": {},
                "quarantine": {},
                "uid_generations": {},
                "adjacency": {},
                "lifecycle": {},
                "aliases": {},
                "retired_uids": [],
                "torch_rng_state": None,
                "cuda_rng_state": [],
            }
            self._write_manifest(manifest)
        self._manifest = self._read_manifest()
        if int(self._manifest["page_capacity"]) != self.page_capacity:
            raise ValueError("page capacity differs from the committed store")
        if not self.uid_high_watermark_path.exists():
            next_uid = 0
            if self._manifest["uid_index"]:
                next_uid = max(int(uid) for uid in self._manifest["uid_index"]) + 1
            _atomic_write(self.uid_high_watermark_path, f"{next_uid}\n".encode())
        self._aborted_uids = self._recover_aborted_uids()

    @property
    def manifest(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._manifest))

    @property
    def manifest_sha256(self) -> str:
        return str(self._manifest["manifest_sha256"])

    @property
    def aborted_uids(self) -> tuple[int, ...]:
        return tuple(sorted(self._aborted_uids))

    @property
    def next_uid(self) -> int:
        return int(self.uid_high_watermark_path.read_text(encoding="utf-8").strip())

    def allocate_uid(self) -> int:
        uid = self.next_uid
        _atomic_write(self.uid_high_watermark_path, f"{uid + 1}\n".encode())
        self._append_journal({
            "sequence": self._manifest["journal_sequence"],
            "phase": "ALLOCATE_UID",
            "uid": uid,
            "unix_ns": time.time_ns(),
        })
        self._aborted_uids.add(uid)
        return uid

    def _reserve_observed_uids(self, uids: Iterable[int]) -> None:
        values = tuple(uids)
        if not values:
            return
        required = max(values) + 1
        if required > self.next_uid:
            _atomic_write(self.uid_high_watermark_path, f"{required}\n".encode())

    @staticmethod
    def _manifest_digest(manifest: Mapping[str, Any]) -> str:
        payload = dict(manifest)
        payload.pop("manifest_sha256", None)
        return _sha256_bytes(_canonical_json(payload))

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        value = dict(manifest)
        value["manifest_sha256"] = self._manifest_digest(value)
        _atomic_write(self.manifest_path, _canonical_json(value))

    def _read_manifest(self) -> dict[str, Any]:
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CorruptStoreError("packed-store manifest is unreadable") from exc
        if value.get("schema_version") != PACKED_STORE_SCHEMA:
            raise CorruptStoreError("unsupported packed-store manifest")
        if value.get("manifest_sha256") != self._manifest_digest(value):
            raise CorruptStoreError("packed-store manifest checksum mismatch")
        return value

    def _append_journal(self, event: dict[str, Any]) -> None:
        payload = _canonical_json(event)
        with self.journal_path.open("ab") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    def journal_events(self) -> tuple[dict[str, Any], ...]:
        events: list[dict[str, Any]] = []
        with self.journal_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise CorruptStoreError(
                        f"journal record {line_number} is corrupt"
                    ) from exc
                events.append(event)
        return tuple(events)

    def _recover_aborted_uids(self) -> set[int]:
        aborted: set[int] = set()
        committed_uids = {
            *(int(uid) for uid in self._manifest["uid_index"]),
            *(int(uid) for uid in self._manifest.get("quarantine_index", {})),
        }
        events = self.journal_events()
        committed_transactions = {
            str(event.get("transaction_id"))
            for event in events
            if event.get("phase") == "COMMIT"
        }
        for event in events:
            if event.get("phase") == "ALLOCATE_UID":
                uid = int(event["uid"])
                if uid not in committed_uids:
                    aborted.add(uid)
            if (
                event.get("phase") == "PREPARE"
                and str(event.get("transaction_id")) not in committed_transactions
            ):
                aborted.update(
                    int(uid)
                    for uid in event.get("new_uids", [])
                    if int(uid) not in committed_uids
                )
        return aborted

    @staticmethod
    def _fault(point: FaultPoint | None, expected: FaultPoint) -> None:
        if point is expected:
            raise InjectedCrash(expected.value)

    @staticmethod
    def _cell_blueprint(cell: WaveCell) -> dict[str, Any]:
        from .structural import ReversibleCompositeCell

        common = {
            "uid": cell.uid,
            "max_degree": cell.max_degree,
            "max_fanout": cell.max_fanout,
            "ports": [asdict(cell.ports[uid]) for uid in sorted(cell.ports)],
            "structural_history": _cpu_value(
                getattr(cell, "structural_history", [])
            ),
        }
        if isinstance(cell, ReversibleCompositeCell):
            return {
                **common,
                "kind": "reversible_composite",
                "left": PackedCellStore._cell_blueprint(cell.left_cell),
                "right": PackedCellStore._cell_blueprint(cell.right_cell),
                "trust_profiles": [asdict(item) for item in cell.trust_profiles],
                "optimizer_partitions": _cpu_value(cell.optimizer_partitions),
                "stage": cell.stage.value,
                "rigidity": cell.rigidity,
                "counterfactual_regression": cell.counterfactual_regression,
            }
        return {
            **common,
            "kind": "wave_cell",
            "cell_config": asdict(cell.transform.config),
            "receptor_config": asdict(cell.receptor.config),
            "contribution_scale": float(cell.contribution_scale.item()),
        }

    @staticmethod
    def _materialize_blueprint(
        blueprint: Mapping[str, Any],
        *,
        device: str | torch.device,
        dtype: torch.dtype,
    ) -> WaveCell:
        kind = str(blueprint["kind"])
        if kind == "wave_cell":
            cell = WaveCell(
                StandaloneBDHCell(
                    BDHCellConfig(**blueprint["cell_config"]),
                    uid=int(blueprint["uid"]),
                ),
                receptor_config=ReceptorConfig(**blueprint["receptor_config"]),
                max_degree=int(blueprint["max_degree"]),
                max_fanout=int(blueprint["max_fanout"]),
                contribution_scale=float(blueprint.get("contribution_scale", 1.0)),
            ).to(device=device, dtype=dtype)
        elif kind == "reversible_composite":
            from .structural import (
                CompositeStage,
                ConditionalTrustProfile,
                ReversibleCompositeCell,
            )

            left = PackedCellStore._materialize_blueprint(
                blueprint["left"], device=device, dtype=dtype
            )
            right = PackedCellStore._materialize_blueprint(
                blueprint["right"], device=device, dtype=dtype
            )
            cell = ReversibleCompositeCell(
                uid=int(blueprint["uid"]),
                left_cell=left,
                right_cell=right,
                trust_profiles=tuple(
                    ConditionalTrustProfile(**item)
                    for item in blueprint.get("trust_profiles", [])
                ),
                optimizer_partitions=blueprint.get("optimizer_partitions", {}),
                stage=CompositeStage(str(blueprint.get("stage", "reversible"))),
                rigidity=float(blueprint.get("rigidity", 0.0)),
                maximum_degree=int(blueprint["max_degree"]),
                maximum_fanout=int(blueprint["max_fanout"]),
            ).to(device=device, dtype=dtype)
            cell.counterfactual_regression = float(
                blueprint.get("counterfactual_regression", 0.0)
            )
        else:
            raise CorruptStoreError(f"unknown packed cell kind: {kind}")
        cell.ports.clear()
        for item in blueprint.get("ports", []):
            cell.connect(NeighborPort(**item))
        cell.structural_history = list(blueprint.get("structural_history", []))
        return cell

    @staticmethod
    def _record_payload(
        cell: WaveCell,
        *,
        generation: int,
        commit_epoch: int,
        journal_sequence: int,
        optimizer: torch.optim.Optimizer | None,
        optimizer_config: CellOptimizerConfig | None,
        metadata: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        parameter = next(cell.transform.parameters())
        bounded_metadata = dict(metadata or {})
        route_ring = list(bounded_metadata.get("route_ring", []))
        if len(route_ring) > 64:
            raise ValueError("route-history ring exceeds the bounded record allowance")
        raw_lifecycle = bounded_metadata.get("lifecycle", "admitted")
        lifecycle = str(getattr(raw_lifecycle, "value", raw_lifecycle))
        blueprint = PackedCellStore._cell_blueprint(cell)
        fusion_tree = bounded_metadata.get("fusion_tree")
        if fusion_tree is None and hasattr(cell, "fusion_tree"):
            fusion_tree = cell.fusion_tree
        predecessor_aliases = bounded_metadata.get("predecessor_aliases")
        if predecessor_aliases is None and hasattr(cell, "constituent_uids"):
            predecessor_aliases = list(cell.constituent_uids)
        return {
            "schema_version": PACKED_RECORD_SCHEMA,
            "header": {
                "canonical_uid": cell.uid,
                "record_generation": generation,
                "latent_abi": cell.transform.config.latent_abi,
                "cell_abi": cell.transform.config.cell_abi,
                "lifecycle": lifecycle,
                "rigidity": bounded_metadata.get(
                    "rigidity", getattr(cell, "rigidity", "plastic")
                ),
                "commit_epoch": commit_epoch,
                "journal_sequence": journal_sequence,
                "parameter_dtype": _dtype_name(parameter.dtype),
            },
            "transform": {
                "cell_config": asdict(cell.transform.config),
                "wave_cell_state": _cpu_value(cell.state_dict()),
                "cell_kind": blueprint["kind"],
                "cell_blueprint": blueprint,
                "max_degree": cell.max_degree,
                "max_fanout": cell.max_fanout,
                "receptor_config": asdict(cell.receptor.config),
            },
            "learning": {
                "optimizer_config": (
                    asdict(optimizer_config) if optimizer_config is not None else None
                ),
                "optimizer_state": (
                    _cpu_value(optimizer.state_dict()) if optimizer is not None else None
                ),
                "calibration": bounded_metadata.get("calibration", {}),
                "evidence_influence": bounded_metadata.get("evidence_influence", {}),
                "local_update_step": bounded_metadata.get("local_update_step", 0),
            },
            "topology": {
                "ports": [
                    asdict(cell.ports[uid]) for uid in sorted(cell.ports)
                ],
                "route_ring": route_ring,
            },
            "lineage": {
                "predecessor_aliases": list(
                    predecessor_aliases or []
                ),
                "fusion_tree": fusion_tree,
                "rollback_obligations": list(
                    bounded_metadata.get("rollback_obligations", [])
                ),
            },
            "private": {
                "persistent_state": _cpu_value(
                    bounded_metadata.get("private_persistent_state")
                ),
                "usage": bounded_metadata.get("usage", {}),
                "refractory": bounded_metadata.get("refractory", {}),
                "homeostasis": bounded_metadata.get("homeostasis", {}),
            },
        }

    @staticmethod
    def _serialize_record(payload: dict[str, Any]) -> bytes:
        buffer = io.BytesIO()
        torch.save(payload, buffer)
        return buffer.getvalue()

    @staticmethod
    def _deserialize_record(
        blob: bytes,
        *,
        device: str | torch.device = "cpu",
    ) -> dict[str, Any]:
        value = torch.load(io.BytesIO(blob), map_location=device, weights_only=True)
        if not isinstance(value, dict) or value.get("schema_version") != PACKED_RECORD_SCHEMA:
            raise CorruptStoreError("unsupported packed cell record")
        return value

    def _write_segment(
        self,
        records: list[tuple[int, int, bytes]],
        *,
        transaction_id: str,
        page_index: int,
        commit_epoch: int,
        storage_class: str = "active",
    ) -> dict[str, Any]:
        if storage_class not in {"active", "quarantine"}:
            raise ValueError("unknown packed segment storage class")
        entries = [
            {
                "uid": uid,
                "record_generation": generation,
                "record_bytes": len(blob),
                "record_sha256": _sha256_bytes(blob),
                "blob": blob,
            }
            for uid, generation, blob in records
        ]
        document = {
            "schema_version": PACKED_SEGMENT_SCHEMA,
            "transaction_id": transaction_id,
            "page_index": page_index,
            "commit_epoch": commit_epoch,
            "storage_class": storage_class,
            "records": entries,
        }
        buffer = io.BytesIO()
        torch.save(document, buffer)
        payload = buffer.getvalue()
        checksum = _sha256_bytes(payload)
        segment_id = f"segment-{checksum[:24]}"
        path = self.segment_root / f"{segment_id}.pt"
        if path.exists():
            if _sha256_file(path) != checksum:
                raise CorruptStoreError("content-addressed segment collision")
        else:
            _atomic_write(path, payload)
        return {
            "segment_id": segment_id,
            "path": path.name,
            "sha256": checksum,
            "byte_size": len(payload),
            "record_count": len(entries),
            "uids": [uid for uid, _, _ in records],
            "commit_epoch": commit_epoch,
            "storage_class": storage_class,
        }

    def load_segment(
        self,
        segment_id: str,
        *,
        device: str | torch.device = "cpu",
    ) -> tuple[dict[str, Any], ...]:
        matches = [
            item for item in self._manifest["segments"]
            if item["segment_id"] == segment_id
        ]
        if len(matches) != 1:
            raise CorruptStoreError(f"manifest does not uniquely name segment {segment_id}")
        declaration = matches[0]
        path = self.segment_root / declaration["path"]
        if not path.is_file() or _sha256_file(path) != declaration["sha256"]:
            raise CorruptStoreError(f"segment checksum mismatch: {segment_id}")
        document = torch.load(path, map_location="cpu", weights_only=True)
        if (
            not isinstance(document, dict)
            or document.get("schema_version") != PACKED_SEGMENT_SCHEMA
        ):
            raise CorruptStoreError(f"segment schema mismatch: {segment_id}")
        records: list[dict[str, Any]] = []
        for entry in document.get("records", []):
            blob = entry.get("blob")
            if (
                not isinstance(blob, bytes)
                or len(blob) != int(entry.get("record_bytes", -1))
                or _sha256_bytes(blob) != entry.get("record_sha256")
            ):
                raise CorruptStoreError(
                    f"cell record checksum mismatch in segment {segment_id}"
                )
            record = self._deserialize_record(blob, device=device)
            header = record["header"]
            if (
                int(header["canonical_uid"]) != int(entry["uid"])
                or int(header["record_generation"])
                != int(entry["record_generation"])
            ):
                raise CorruptStoreError("segment header and cell record disagree")
            records.append(record)
        if len(records) != int(declaration["record_count"]):
            raise CorruptStoreError("segment record count mismatch")
        return tuple(records)

    def load_record(
        self,
        uid: int,
        *,
        device: str | torch.device = "cpu",
    ) -> dict[str, Any]:
        location = self._manifest["uid_index"].get(str(uid))
        if location is None:
            raise KeyError(f"unknown packed cell UID {uid}")
        records = self.load_segment(location["segment_id"], device=device)
        index = int(location["record_index"])
        if not 0 <= index < len(records):
            raise CorruptStoreError("UID index points outside its packed page")
        record = records[index]
        if int(record["header"]["canonical_uid"]) != uid:
            raise CorruptStoreError("UID index points to a different cell")
        return record

    def load_quarantine_record(
        self,
        uid: int,
        *,
        device: str | torch.device = "cpu",
    ) -> dict[str, Any]:
        location = self._manifest.get("quarantine_index", {}).get(str(uid))
        if location is None:
            raise KeyError(f"unknown quarantined cell UID {uid}")
        records = self.load_segment(location["segment_id"], device=device)
        index = int(location["record_index"])
        if not 0 <= index < len(records):
            raise CorruptStoreError("quarantine index points outside its packed page")
        record = records[index]
        if int(record["header"]["canonical_uid"]) != uid:
            raise CorruptStoreError("quarantine index points to a different cell")
        if record["header"]["lifecycle"] != "quarantined":
            raise CorruptStoreError("quarantine index points to active tissue")
        return record

    def commit_cells(
        self,
        cells: Mapping[int, WaveCell],
        *,
        optimizers: Mapping[int, torch.optim.Optimizer] | None = None,
        optimizer_configs: Mapping[int, CellOptimizerConfig] | None = None,
        metadata: Mapping[int, Mapping[str, Any]] | None = None,
        substrate_config: SparseWaveConfig | None = None,
        substrate_graph_version: int | None = None,
        substrate_thought_epoch: int | None = None,
        aliases: Mapping[int, int] | None = None,
        alias_view: Mapping[int, int] | None = None,
        deactivate_uids: Iterable[int] = (),
        retired_uids: Iterable[int] = (),
        quarantine_cells: Mapping[int, WaveCell] | None = None,
        quarantine_optimizers: Mapping[int, torch.optim.Optimizer] | None = None,
        quarantine_optimizer_configs: Mapping[int, CellOptimizerConfig] | None = None,
        quarantine_metadata: Mapping[int, Mapping[str, Any]] | None = None,
        purge_uids: Iterable[int] = (),
        reason: str = "learning_flush",
        fault_at: FaultPoint | None = None,
    ) -> CommitResult:
        quarantine_cells = quarantine_cells or {}
        purge_values = tuple(purge_uids)
        if not cells and not quarantine_cells and not purge_values:
            raise ValueError("at least one dirty or structural cell is required")
        ordered_uids = tuple(sorted(cells))
        ordered_quarantine_uids = tuple(sorted(quarantine_cells))
        deactivated = tuple(sorted(set(deactivate_uids)))
        retired = tuple(sorted(set(retired_uids)))
        purged = tuple(sorted(set(purge_values)))
        if any(uid < 0 or cells[uid].uid != uid for uid in ordered_uids):
            raise ValueError("cell mapping must use matching non-negative UIDs")
        if any(
            uid < 0 or quarantine_cells[uid].uid != uid
            for uid in ordered_quarantine_uids
        ):
            raise ValueError("quarantine mapping must use matching non-negative UIDs")
        if any(uid < 0 for uid in (*deactivated, *retired, *purged)):
            raise ValueError("deactivated, retired, and purged UIDs must be non-negative")
        if set(ordered_uids).intersection(deactivated):
            raise ValueError("a UID cannot be written and deactivated together")
        if set(ordered_uids).intersection(ordered_quarantine_uids):
            raise ValueError("a UID cannot be active and quarantined together")
        if set(purged).intersection((*ordered_uids, *ordered_quarantine_uids)):
            raise ValueError("a UID cannot be written and purged together")
        if aliases is not None and alias_view is not None:
            raise ValueError("aliases and alias_view are mutually exclusive")
        self._reserve_observed_uids((*ordered_uids, *ordered_quarantine_uids))
        optimizers = optimizers or {}
        optimizer_configs = optimizer_configs or {}
        metadata = metadata or {}
        quarantine_optimizers = quarantine_optimizers or {}
        quarantine_optimizer_configs = quarantine_optimizer_configs or {}
        quarantine_metadata = quarantine_metadata or {}
        current_index = self._manifest["uid_index"]
        current_quarantine_index = self._manifest.get("quarantine_index", {})
        known_before = {*map(int, current_index), *map(int, current_quarantine_index)}
        new_uids = tuple(
            uid
            for uid in (*ordered_uids, *ordered_quarantine_uids)
            if uid not in known_before
        )
        sequence = int(self._manifest["journal_sequence"]) + 1
        epoch = int(self._manifest["commit_epoch"]) + 1
        transaction_id = f"tx-{sequence}-{uuid.uuid4().hex[:12]}"
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "PREPARE",
            "reason": reason,
            "uids": list(ordered_uids),
            "quarantine_uids": list(ordered_quarantine_uids),
            "new_uids": list(new_uids),
            "deactivate_uids": list(deactivated),
            "retired_uids": list(retired),
            "purge_uids": list(purged),
            "parent_manifest_sha256": self.manifest_sha256,
            "unix_ns": time.time_ns(),
        })
        self._fault(fault_at, FaultPoint.AFTER_PREPARE)

        serialized: list[tuple[int, int, bytes]] = []
        generation_watermarks = dict(self._manifest.get("uid_generations", {}))
        for uid in ordered_uids:
            previous_generation = int(generation_watermarks.get(str(uid), 0))
            previous_location = current_index.get(str(uid)) or current_quarantine_index.get(str(uid))
            if previous_location is not None:
                previous_generation = max(
                    previous_generation,
                    int(previous_location["record_generation"]),
                )
            generation = previous_generation + 1
            generation_watermarks[str(uid)] = generation
            optimizer = optimizers.get(uid)
            optimizer_config = optimizer_configs.get(uid)
            if (optimizer is None) != (optimizer_config is None):
                raise ValueError("optimizer and optimizer config must be supplied together")
            record = self._record_payload(
                cells[uid],
                generation=generation,
                commit_epoch=epoch,
                journal_sequence=sequence,
                optimizer=optimizer,
                optimizer_config=optimizer_config,
                metadata=metadata.get(uid),
            )
            serialized.append((uid, generation, self._serialize_record(record)))

        serialized_quarantine: list[tuple[int, int, bytes]] = []
        for uid in ordered_quarantine_uids:
            previous_generation = int(generation_watermarks.get(str(uid), 0))
            previous_location = current_quarantine_index.get(str(uid)) or current_index.get(str(uid))
            if previous_location is not None:
                previous_generation = max(
                    previous_generation,
                    int(previous_location["record_generation"]),
                )
            generation = previous_generation + 1
            generation_watermarks[str(uid)] = generation
            optimizer = quarantine_optimizers.get(uid)
            optimizer_config = quarantine_optimizer_configs.get(uid)
            if (optimizer is None) != (optimizer_config is None):
                raise ValueError(
                    "quarantine optimizer and optimizer config must be supplied together"
                )
            bounded_metadata = dict(quarantine_metadata.get(uid, {}))
            bounded_metadata["lifecycle"] = "quarantined"
            record = self._record_payload(
                quarantine_cells[uid],
                generation=generation,
                commit_epoch=epoch,
                journal_sequence=sequence,
                optimizer=optimizer,
                optimizer_config=optimizer_config,
                metadata=bounded_metadata,
            )
            serialized_quarantine.append(
                (uid, generation, self._serialize_record(record))
            )

        segment_declarations: list[dict[str, Any]] = []
        for page_index, start in enumerate(range(0, len(serialized), self.page_capacity)):
            segment_declarations.append(self._write_segment(
                serialized[start : start + self.page_capacity],
                transaction_id=transaction_id,
                page_index=page_index,
                commit_epoch=epoch,
            ))
        quarantine_segment_declarations: list[dict[str, Any]] = []
        for page_index, start in enumerate(
            range(0, len(serialized_quarantine), self.page_capacity)
        ):
            quarantine_segment_declarations.append(self._write_segment(
                serialized_quarantine[start : start + self.page_capacity],
                transaction_id=transaction_id,
                page_index=page_index,
                commit_epoch=epoch,
                storage_class="quarantine",
            ))
        all_new_segments = [
            *segment_declarations,
            *quarantine_segment_declarations,
        ]
        bytes_written = sum(item["byte_size"] for item in all_new_segments)
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "WRITE",
            "segments": [item["segment_id"] for item in all_new_segments],
            "bytes_written": bytes_written,
            "unix_ns": time.time_ns(),
        })
        self._fault(fault_at, FaultPoint.AFTER_WRITE)

        candidate_index = dict(current_index)
        candidate_quarantine_index = dict(current_quarantine_index)
        candidate_quarantine = dict(self._manifest.get("quarantine", {}))
        candidate_lifecycle = dict(self._manifest.get("lifecycle", {}))
        for segment in segment_declarations:
            records = self.load_uncommitted_segment(segment)
            for index, record in enumerate(records):
                uid = int(record["header"]["canonical_uid"])
                candidate_index[str(uid)] = {
                    "segment_id": segment["segment_id"],
                    "record_index": index,
                    "record_generation": int(record["header"]["record_generation"]),
                    "record_bytes": int(segment["record_bytes"][index]),
                }
                candidate_quarantine_index.pop(str(uid), None)
                candidate_quarantine.pop(str(uid), None)
                candidate_lifecycle[str(uid)] = str(record["header"]["lifecycle"])
        for segment in quarantine_segment_declarations:
            records = self.load_uncommitted_segment(segment)
            for index, record in enumerate(records):
                uid = int(record["header"]["canonical_uid"])
                candidate_quarantine_index[str(uid)] = {
                    "segment_id": segment["segment_id"],
                    "record_index": index,
                    "record_generation": int(record["header"]["record_generation"]),
                    "record_bytes": int(segment["record_bytes"][index]),
                }
                candidate_index.pop(str(uid), None)
                candidate_quarantine[str(uid)] = _cpu_value(
                    dict(quarantine_metadata.get(uid, {}))
                )
                candidate_lifecycle[str(uid)] = "quarantined"
        for uid in deactivated:
            candidate_index.pop(str(uid), None)
            if str(uid) not in candidate_quarantine_index:
                candidate_lifecycle[str(uid)] = (
                    "retired" if uid in retired else "subsumed"
                )
        for uid in purged:
            candidate_index.pop(str(uid), None)
            candidate_quarantine_index.pop(str(uid), None)
            candidate_quarantine.pop(str(uid), None)
            candidate_lifecycle[str(uid)] = "purged"
        adjacency = dict(self._manifest["adjacency"])
        for uid in ordered_uids:
            adjacency[str(uid)] = [
                int(destination) for destination in sorted(cells[uid].ports)
            ]
        for uid in (*deactivated, *ordered_quarantine_uids, *purged):
            adjacency.pop(str(uid), None)
        known = {int(uid) for uid in candidate_index}
        known_quarantine = {int(uid) for uid in candidate_quarantine_index}
        candidate_retired = set(map(int, self._manifest.get("retired_uids", [])))
        candidate_retired.update(retired)
        candidate_retired.update(purged)
        addressable = known | known_quarantine | candidate_retired
        for source, destinations in adjacency.items():
            if int(source) not in known or any(
                int(value) not in addressable for value in destinations
            ):
                raise ValueError("candidate topology contains a missing cell reference")
        candidate_aliases = (
            {str(alias): int(canonical) for alias, canonical in alias_view.items()}
            if alias_view is not None
            else dict(self._manifest.get("aliases", {}))
        )
        if aliases:
            for alias, canonical in aliases.items():
                if canonical not in known | known_quarantine:
                    raise ValueError("alias target is absent from candidate inventory")
                candidate_aliases[str(alias)] = canonical
        candidate_aliases = {
            alias: int(canonical)
            for alias, canonical in candidate_aliases.items()
            if int(alias) not in candidate_retired
            and int(canonical) not in candidate_retired
        }
        if any(
            int(canonical) not in known | known_quarantine
            for canonical in candidate_aliases.values()
        ):
            raise ValueError("alias view targets absent tissue")
        for alias in candidate_aliases:
            visited: set[int] = set()
            current = int(alias)
            while str(current) in candidate_aliases:
                if current in visited:
                    raise ValueError("candidate alias view contains a cycle")
                visited.add(current)
                current = int(candidate_aliases[str(current)])
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "VALIDATE",
            "record_count": len(serialized) + len(serialized_quarantine),
            "unix_ns": time.time_ns(),
        })
        self._fault(fault_at, FaultPoint.AFTER_VALIDATE)

        referenced_segment_ids = {
            value["segment_id"]
            for value in (
                *candidate_index.values(),
                *candidate_quarantine_index.values(),
            )
        }
        reclaim_declarations = [
            item
            for item in self._manifest["segments"]
            if purged
            and item.get("storage_class", "active") == "quarantine"
            and item["segment_id"] not in referenced_segment_ids
        ]
        reclaim_ids = {item["segment_id"] for item in reclaim_declarations}
        retained_segments = [
            item
            for item in self._manifest["segments"]
            if item["segment_id"] not in reclaim_ids
        ]
        candidate = dict(self._manifest)
        candidate.pop("manifest_sha256", None)
        candidate.update({
            "commit_epoch": epoch,
            "journal_sequence": sequence,
            "parent_manifest_sha256": self.manifest_sha256,
            "page_capacity": self.page_capacity,
            "segments": [*retained_segments, *all_new_segments],
            "uid_index": candidate_index,
            "quarantine_index": candidate_quarantine_index,
            "quarantine": candidate_quarantine,
            "uid_generations": generation_watermarks,
            "adjacency": adjacency,
            "lifecycle": candidate_lifecycle,
            "aliases": candidate_aliases,
            "retired_uids": sorted(candidate_retired),
            "substrate_config": (
                asdict(substrate_config)
                if substrate_config is not None
                else self._manifest.get("substrate_config")
            ),
            "substrate_graph_version": (
                substrate_graph_version
                if substrate_graph_version is not None
                else self._manifest.get("substrate_graph_version", 0)
            ),
            "substrate_thought_epoch": (
                substrate_thought_epoch
                if substrate_thought_epoch is not None
                else self._manifest.get("substrate_thought_epoch", 0)
            ),
            "torch_rng_state": torch.get_rng_state().tolist(),
            "cuda_rng_state": [
                value.tolist()
                for value in (
                    torch.cuda.get_rng_state_all()
                    if torch.cuda.is_available() and torch.cuda.is_initialized()
                    else []
                )
            ],
        })
        self._write_manifest(candidate)
        committed = self._read_manifest()
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "COMMIT",
            "manifest_sha256": committed["manifest_sha256"],
            "unix_ns": time.time_ns(),
        })
        self._fault(fault_at, FaultPoint.AFTER_COMMIT)
        self._manifest = committed
        self._aborted_uids.difference_update(new_uids)
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "PUBLISH",
            "unix_ns": time.time_ns(),
        })
        self._fault(fault_at, FaultPoint.AFTER_PUBLISH)
        for declaration in reclaim_declarations:
            path = self.segment_root / declaration["path"]
            if path.exists():
                path.unlink()
        if reclaim_declarations:
            _fsync_directory(self.segment_root)
            self._append_journal({
                "sequence": sequence,
                "transaction_id": transaction_id,
                "phase": "RECLAIM",
                "segment_ids": sorted(reclaim_ids),
                "bytes_reclaimed": sum(
                    int(item["byte_size"]) for item in reclaim_declarations
                ),
                "unix_ns": time.time_ns(),
            })
        return CommitResult(
            transaction_id=transaction_id,
            commit_epoch=epoch,
            journal_sequence=sequence,
            written_uids=ordered_uids,
            segment_ids=tuple(item["segment_id"] for item in all_new_segments),
            bytes_written=bytes_written,
            manifest_sha256=self.manifest_sha256,
        )

    def load_uncommitted_segment(
        self,
        declaration: Mapping[str, Any],
    ) -> tuple[dict[str, Any], ...]:
        path = self.segment_root / str(declaration["path"])
        if _sha256_file(path) != declaration["sha256"]:
            raise CorruptStoreError("uncommitted segment checksum mismatch")
        document = torch.load(path, map_location="cpu", weights_only=True)
        records: list[dict[str, Any]] = []
        record_bytes: list[int] = []
        for entry in document["records"]:
            blob = entry["blob"]
            if _sha256_bytes(blob) != entry["record_sha256"]:
                raise CorruptStoreError("uncommitted cell checksum mismatch")
            records.append(self._deserialize_record(blob))
            record_bytes.append(len(blob))
        # Internal transient metadata used while constructing the UID index.
        if isinstance(declaration, dict):
            declaration["record_bytes"] = record_bytes
        return tuple(records)

    def _record_blob(self, uid: int) -> tuple[int, bytes]:
        location = self._manifest["uid_index"].get(str(uid))
        if location is None:
            raise KeyError(f"unknown packed cell UID {uid}")
        declaration = next(
            item for item in self._manifest["segments"]
            if item["segment_id"] == location["segment_id"]
        )
        path = self.segment_root / declaration["path"]
        if _sha256_file(path) != declaration["sha256"]:
            raise CorruptStoreError("cannot repack a corrupt source segment")
        document = torch.load(path, map_location="cpu", weights_only=True)
        entry = document["records"][int(location["record_index"])]
        blob = entry["blob"]
        if _sha256_bytes(blob) != entry["record_sha256"]:
            raise CorruptStoreError("cannot repack a corrupt source record")
        return int(location["record_generation"]), blob

    def repack(
        self,
        uid_order: Iterable[int],
        *,
        reason: str = "physical_repack",
        fault_at: FaultPoint | None = None,
    ) -> CommitResult:
        """Change physical co-location without changing UID or record generation."""

        ordered_uids = tuple(uid_order)
        active_uids = {int(uid) for uid in self._manifest["uid_index"]}
        if len(ordered_uids) != len(set(ordered_uids)) or set(ordered_uids) != active_uids:
            raise ValueError("repack order must name every active UID exactly once")
        sequence = int(self._manifest["journal_sequence"]) + 1
        epoch = int(self._manifest["commit_epoch"]) + 1
        transaction_id = f"repack-{sequence}-{uuid.uuid4().hex[:12]}"
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "PREPARE",
            "reason": reason,
            "uids": list(ordered_uids),
            "new_uids": [],
            "parent_manifest_sha256": self.manifest_sha256,
            "unix_ns": time.time_ns(),
        })
        self._fault(fault_at, FaultPoint.AFTER_PREPARE)
        serialized = [
            (uid, *self._record_blob(uid)) for uid in ordered_uids
        ]
        declarations: list[dict[str, Any]] = []
        for page_index, start in enumerate(range(0, len(serialized), self.page_capacity)):
            declarations.append(self._write_segment(
                serialized[start : start + self.page_capacity],
                transaction_id=transaction_id,
                page_index=page_index,
                commit_epoch=epoch,
            ))
        bytes_written = sum(item["byte_size"] for item in declarations)
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "WRITE",
            "segments": [item["segment_id"] for item in declarations],
            "bytes_written": bytes_written,
            "unix_ns": time.time_ns(),
        })
        self._fault(fault_at, FaultPoint.AFTER_WRITE)
        candidate_index: dict[str, dict[str, Any]] = {}
        for declaration in declarations:
            records = self.load_uncommitted_segment(declaration)
            for record_index, record in enumerate(records):
                uid = int(record["header"]["canonical_uid"])
                candidate_index[str(uid)] = {
                    "segment_id": declaration["segment_id"],
                    "record_index": record_index,
                    "record_generation": int(record["header"]["record_generation"]),
                    "record_bytes": int(declaration["record_bytes"][record_index]),
                }
        if set(map(int, candidate_index)) != active_uids:
            raise CorruptStoreError("repack validation lost part of the inventory")
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "VALIDATE",
            "record_count": len(candidate_index),
            "unix_ns": time.time_ns(),
        })
        self._fault(fault_at, FaultPoint.AFTER_VALIDATE)
        candidate = dict(self._manifest)
        candidate.pop("manifest_sha256", None)
        candidate.update({
            "commit_epoch": epoch,
            "journal_sequence": sequence,
            "parent_manifest_sha256": self.manifest_sha256,
            "segments": [*self._manifest["segments"], *declarations],
            "uid_index": candidate_index,
        })
        self._write_manifest(candidate)
        committed = self._read_manifest()
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "COMMIT",
            "manifest_sha256": committed["manifest_sha256"],
            "unix_ns": time.time_ns(),
        })
        self._fault(fault_at, FaultPoint.AFTER_COMMIT)
        self._manifest = committed
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "PUBLISH",
            "unix_ns": time.time_ns(),
        })
        self._fault(fault_at, FaultPoint.AFTER_PUBLISH)
        return CommitResult(
            transaction_id=transaction_id,
            commit_epoch=epoch,
            journal_sequence=sequence,
            written_uids=ordered_uids,
            segment_ids=tuple(item["segment_id"] for item in declarations),
            bytes_written=bytes_written,
            manifest_sha256=self.manifest_sha256,
        )

    def commit_substrate(
        self,
        substrate: SparseWaveSubstrate,
        *,
        optimizers: Mapping[int, torch.optim.Optimizer] | None = None,
        optimizer_configs: Mapping[int, CellOptimizerConfig] | None = None,
        metadata: Mapping[int, Mapping[str, Any]] | None = None,
        reason: str = "substrate_snapshot",
        deactivate_missing: bool = True,
        fault_at: FaultPoint | None = None,
    ) -> CommitResult:
        if not substrate.ready_for_next_turn:
            raise RuntimeError("persistent commit requires a quiescent substrate")
        cells = {
            int(uid): substrate.cells[uid]  # type: ignore[assignment]
            for uid in substrate.cells
        }
        active_uids = set(cells)
        deactivated = (
            {int(uid) for uid in self._manifest["uid_index"]}.difference(active_uids)
            if deactivate_missing
            else set()
        )
        return self.commit_cells(
            cells,
            optimizers=optimizers,
            optimizer_configs=optimizer_configs,
            metadata=metadata,
            substrate_config=substrate.config,
            substrate_graph_version=substrate.graph_version,
            substrate_thought_epoch=substrate._thought_epoch,
            alias_view=substrate.aliases,
            deactivate_uids=deactivated,
            retired_uids=substrate.retired_uids,
            reason=reason,
            fault_at=fault_at,
        )

    def commit_hygiene(
        self,
        substrate: SparseWaveSubstrate,
        *,
        quarantine_cells: Mapping[int, WaveCell],
        quarantine_metadata: Mapping[int, Mapping[str, Any]],
        active_optimizers: Mapping[int, torch.optim.Optimizer] | None = None,
        active_optimizer_configs: Mapping[int, CellOptimizerConfig] | None = None,
        quarantine_optimizers: Mapping[int, torch.optim.Optimizer] | None = None,
        quarantine_optimizer_configs: Mapping[int, CellOptimizerConfig] | None = None,
        dirty_active_uids: Iterable[int] = (),
        purge_uids: Iterable[int] = (),
        reason: str = "hygiene_cycle",
        fault_at: FaultPoint | None = None,
    ) -> CommitResult:
        """Atomically publish active/quarantine membership and permanent death."""

        if not substrate.ready_for_next_turn:
            raise RuntimeError("persistent hygiene requires a quiescent substrate")
        active = {
            int(uid): substrate.cells[uid]  # type: ignore[assignment]
            for uid in substrate.cells
        }
        dirty = set(dirty_active_uids)
        dirty.update(
            uid
            for uid in active
            if str(uid) not in self._manifest["uid_index"]
            or str(uid) in self._manifest.get("quarantine_index", {})
        )
        unknown_dirty = dirty - set(active)
        if unknown_dirty:
            raise ValueError(f"dirty hygiene UIDs are not active: {sorted(unknown_dirty)}")
        active_writes = {uid: active[uid] for uid in sorted(dirty)}
        active_optimizers = active_optimizers or {}
        active_optimizer_configs = active_optimizer_configs or {}
        current_active = {int(uid) for uid in self._manifest["uid_index"]}
        deactivated = current_active - set(active)
        return self.commit_cells(
            active_writes,
            optimizers={
                uid: active_optimizers[uid]
                for uid in active_writes
                if uid in active_optimizers
            },
            optimizer_configs={
                uid: active_optimizer_configs[uid]
                for uid in active_writes
                if uid in active_optimizer_configs
            },
            substrate_config=substrate.config,
            substrate_graph_version=substrate.graph_version,
            substrate_thought_epoch=substrate._thought_epoch,
            alias_view=substrate.aliases,
            deactivate_uids=deactivated,
            retired_uids=substrate.retired_uids,
            quarantine_cells=quarantine_cells,
            quarantine_optimizers=quarantine_optimizers,
            quarantine_optimizer_configs=quarantine_optimizer_configs,
            quarantine_metadata=quarantine_metadata,
            purge_uids=purge_uids,
            reason=reason,
            fault_at=fault_at,
        )

    def materialize_cell(
        self,
        record: Mapping[str, Any],
        *,
        device: str | torch.device = "cpu",
    ) -> tuple[WaveCell, torch.optim.AdamW | None, CellOptimizerConfig | None]:
        header = record["header"]
        transform = record["transform"]
        dtype = _resolve_dtype(str(header["parameter_dtype"]))
        blueprint = transform.get("cell_blueprint")
        if blueprint is not None:
            cell = self._materialize_blueprint(
                blueprint, device=device, dtype=dtype
            )
        else:
            cell_config = BDHCellConfig(**transform["cell_config"])
            cell = WaveCell(
                StandaloneBDHCell(
                    cell_config,
                    uid=int(header["canonical_uid"]),
                ),
                receptor_config=ReceptorConfig(**transform["receptor_config"]),
                max_degree=int(transform["max_degree"]),
                max_fanout=int(transform["max_fanout"]),
            ).to(device=device, dtype=dtype)
        cell.load_state_dict(transform["wave_cell_state"], strict=True)
        if blueprint is None:
            for item in record["topology"]["ports"]:
                cell.connect(NeighborPort(**item))
        learning = record["learning"]
        optimizer: torch.optim.AdamW | None = None
        optimizer_config: CellOptimizerConfig | None = None
        if learning["optimizer_state"] is not None:
            optimizer_config = CellOptimizerConfig(**learning["optimizer_config"])
            optimizer = build_cell_optimizer(cell.transform.parameters(), optimizer_config)
            optimizer.load_state_dict(learning["optimizer_state"])
        return cell, optimizer, optimizer_config

    def load_substrate(
        self,
        *,
        device: str | torch.device = "cpu",
        restore_rng: bool = False,
    ) -> tuple[
        SparseWaveSubstrate,
        dict[int, torch.optim.AdamW],
        dict[int, CellOptimizerConfig],
        dict[int, dict[str, Any]],
    ]:
        config_value = self._manifest.get("substrate_config")
        if config_value is None:
            raise RuntimeError("packed store has no committed substrate")
        substrate = SparseWaveSubstrate(SparseWaveConfig(**config_value)).to(device=device)
        optimizers: dict[int, torch.optim.AdamW] = {}
        optimizer_configs: dict[int, CellOptimizerConfig] = {}
        anatomy: dict[int, dict[str, Any]] = {}
        page_cache: dict[str, tuple[dict[str, Any], ...]] = {}
        for uid_text, location in sorted(
            self._manifest["uid_index"].items(), key=lambda item: int(item[0])
        ):
            segment_id = location["segment_id"]
            if segment_id not in page_cache:
                page_cache[segment_id] = self.load_segment(segment_id)
            records = page_cache[segment_id]
            record = records[int(location["record_index"])]
            cell, optimizer, optimizer_config = self.materialize_cell(
                record, device=device
            )
            substrate.add_cell(cell)
            uid = int(uid_text)
            if optimizer is not None and optimizer_config is not None:
                optimizers[uid] = optimizer
                optimizer_configs[uid] = optimizer_config
            anatomy[uid] = {
                "header": dict(record["header"]),
                "learning": {
                    key: value
                    for key, value in record["learning"].items()
                    if key != "optimizer_state"
                },
                "lineage": record["lineage"],
                "private": record["private"],
                "route_ring": record["topology"]["route_ring"],
            }
        substrate.graph_version = int(self._manifest["substrate_graph_version"])
        substrate._thought_epoch = int(self._manifest["substrate_thought_epoch"])
        substrate.aliases = {
            int(alias): int(canonical)
            for alias, canonical in self._manifest.get("aliases", {}).items()
        }
        substrate.retired_uids = set(map(int, self._manifest.get("retired_uids", [])))
        if restore_rng and self._manifest.get("torch_rng_state") is not None:
            torch.set_rng_state(
                torch.tensor(self._manifest["torch_rng_state"], dtype=torch.uint8)
            )
            cuda_states = self._manifest.get("cuda_rng_state", [])
            if cuda_states and torch.cuda.is_available():
                torch.cuda.set_rng_state_all([
                    torch.tensor(value, dtype=torch.uint8) for value in cuda_states
                ])
        return substrate, optimizers, optimizer_configs, anatomy

    def load_quarantine(
        self,
        *,
        device: str | torch.device = "cpu",
    ) -> tuple[
        dict[int, WaveCell],
        dict[int, torch.optim.AdamW],
        dict[int, CellOptimizerConfig],
        dict[int, dict[str, Any]],
    ]:
        cells: dict[int, WaveCell] = {}
        optimizers: dict[int, torch.optim.AdamW] = {}
        optimizer_configs: dict[int, CellOptimizerConfig] = {}
        metadata: dict[int, dict[str, Any]] = {}
        page_cache: dict[str, tuple[dict[str, Any], ...]] = {}
        for uid_text, location in sorted(
            self._manifest.get("quarantine_index", {}).items(),
            key=lambda item: int(item[0]),
        ):
            segment_id = location["segment_id"]
            if segment_id not in page_cache:
                page_cache[segment_id] = self.load_segment(segment_id)
            record = page_cache[segment_id][int(location["record_index"])]
            cell, optimizer, optimizer_config = self.materialize_cell(
                record, device=device
            )
            uid = int(uid_text)
            cells[uid] = cell
            if optimizer is not None and optimizer_config is not None:
                optimizers[uid] = optimizer
                optimizer_configs[uid] = optimizer_config
            metadata[uid] = dict(
                self._manifest.get("quarantine", {}).get(uid_text, {})
            )
        return cells, optimizers, optimizer_configs, metadata

    def inventory(self) -> dict[int, RecordLocation]:
        return {
            int(uid): RecordLocation(
                segment_id=value["segment_id"],
                record_index=int(value["record_index"]),
                record_generation=int(value["record_generation"]),
                record_bytes=int(value["record_bytes"]),
            )
            for uid, value in self._manifest["uid_index"].items()
        }

    def rebuild_index_from_segments(self) -> dict[int, RecordLocation]:
        rebuilt: dict[int, RecordLocation] = {}
        active_uids = {int(uid) for uid in self._manifest["uid_index"]}
        for segment in self._manifest["segments"]:
            records = self.load_segment(segment["segment_id"])
            for index, record in enumerate(records):
                uid = int(record["header"]["canonical_uid"])
                if uid not in active_uids:
                    continue
                generation = int(record["header"]["record_generation"])
                current = rebuilt.get(uid)
                # Later declarations win generation ties. Repacking intentionally
                # preserves record generations while replacing physical locations.
                if current is None or generation >= current.record_generation:
                    rebuilt[uid] = RecordLocation(
                        segment_id=segment["segment_id"],
                        record_index=index,
                        record_generation=generation,
                        record_bytes=int(segment["record_bytes"][index]),
                    )
        return rebuilt

    def create_snapshot(self, name: str) -> Path:
        if not name or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in name):
            raise ValueError("snapshot names use only letters, digits, hyphen, and underscore")
        document = {
            "schema_version": PACKED_SNAPSHOT_SCHEMA,
            "created_unix_ns": time.time_ns(),
            "manifest": self._manifest,
        }
        path = self.snapshot_root / f"{name}.json"
        _atomic_write(path, _canonical_json(document))
        return path

    def restore_snapshot(self, name: str) -> None:
        path = self.snapshot_root / f"{name}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema_version") != PACKED_SNAPSHOT_SCHEMA:
            raise CorruptStoreError("unsupported packed snapshot")
        snapshot = value["manifest"]
        for segment in snapshot["segments"]:
            path = self.segment_root / segment["path"]
            if not path.is_file() or _sha256_file(path) != segment["sha256"]:
                raise CorruptStoreError("snapshot references a missing or corrupt segment")
        sequence = int(self._manifest["journal_sequence"]) + 1
        epoch = int(self._manifest["commit_epoch"]) + 1
        transaction_id = f"restore-{sequence}-{uuid.uuid4().hex[:8]}"
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "PREPARE",
            "reason": "snapshot_restore",
            "snapshot": name,
            "new_uids": [],
        })
        restored = dict(snapshot)
        restored.pop("manifest_sha256", None)
        restored["commit_epoch"] = epoch
        restored["journal_sequence"] = sequence
        restored["parent_manifest_sha256"] = self.manifest_sha256
        self._write_manifest(restored)
        self._manifest = self._read_manifest()
        self._append_journal({
            "sequence": sequence,
            "transaction_id": transaction_id,
            "phase": "COMMIT",
            "manifest_sha256": self.manifest_sha256,
        })


class DirtyCellBuffer:
    """RAM-only coalescer: repeated updates become one record generation."""

    def __init__(self, store: PackedCellStore) -> None:
        self.store = store
        self._cells: dict[int, WaveCell] = {}
        self._optimizers: dict[int, torch.optim.Optimizer] = {}
        self._optimizer_configs: dict[int, CellOptimizerConfig] = {}
        self._metadata: dict[int, Mapping[str, Any]] = {}
        self.update_events = 0

    @property
    def dirty_uids(self) -> tuple[int, ...]:
        return tuple(sorted(self._cells))

    def mark(
        self,
        cell: WaveCell,
        *,
        optimizer: torch.optim.Optimizer | None = None,
        optimizer_config: CellOptimizerConfig | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if (optimizer is None) != (optimizer_config is None):
            raise ValueError("optimizer and config must be marked together")
        self._cells[cell.uid] = cell
        if optimizer is not None and optimizer_config is not None:
            self._optimizers[cell.uid] = optimizer
            self._optimizer_configs[cell.uid] = optimizer_config
        if metadata is not None:
            self._metadata[cell.uid] = metadata
        self.update_events += 1

    def flush(self, *, reason: str = "coalesced_dirty_flush") -> CommitResult | None:
        if not self._cells:
            return None
        result = self.store.commit_cells(
            self._cells,
            optimizers=self._optimizers,
            optimizer_configs=self._optimizer_configs,
            metadata=self._metadata,
            reason=reason,
        )
        self._cells.clear()
        self._optimizers.clear()
        self._optimizer_configs.clear()
        self._metadata.clear()
        return result
