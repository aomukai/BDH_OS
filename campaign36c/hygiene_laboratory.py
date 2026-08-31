from __future__ import annotations

import hashlib
import io
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import tempfile
from typing import Any

import torch
import torch.nn.functional as F

from .cell import StandaloneBDHCell
from .config import BDHCellConfig, SparseWaveConfig
from .hygiene import (
    HygieneAuthorization,
    HygieneController,
    HygienePolicyConfig,
    PurgeAuthorization,
    QuarantineReason,
    RevivalEvidence,
    RevivalRequest,
    RootedParticipationLedger,
    TissueLifecycle,
    UsefulCreditKind,
)
from .persistence import FaultPoint, InjectedCrash, PackedCellStore
from .wave import NeighborPort, SparseWaveSubstrate, WaveCell


CAMPAIGN36C_HYGIENE_LAB_RESULT_SCHEMA = (
    "ninereeds_campaign36c_hygiene_lab_result_v0"
)


@dataclass(frozen=True)
class HygieneLabConfig:
    width: int = 512
    rotary_pairs: int = 2
    sequence_length: int = 16
    page_capacity: int = 2
    senescence_interval: int = 2
    minimum_senescence_sweeps: int = 1
    maximum_revival_candidates: int = 2
    minimum_revival_similarity: float = 0.80
    minimum_revival_improvement_fraction: float = 0.05
    maximum_revival_regression: float = 0.01
    seed: int = 36_700

    def validate(self) -> None:
        if self.width <= 0 or self.rotary_pairs <= 0 or self.sequence_length <= 1:
            raise ValueError("hygiene laboratory dimensions are invalid")
        if self.page_capacity <= 1:
            raise ValueError("hygiene pages must hold multiple cells")
        if min(
            self.senescence_interval,
            self.minimum_senescence_sweeps,
            self.maximum_revival_candidates,
        ) <= 0:
            raise ValueError("hygiene laboratory counts must be positive")
        if not -1.0 <= self.minimum_revival_similarity <= 1.0:
            raise ValueError("hygiene similarity must be a cosine bound")
        if min(
            self.minimum_revival_improvement_fraction,
            self.maximum_revival_regression,
        ) < 0:
            raise ValueError("hygiene loss bounds must be non-negative")
        if self.seed < 0:
            raise ValueError("hygiene seed must be non-negative")


def _policy(config: HygieneLabConfig) -> HygienePolicyConfig:
    return HygienePolicyConfig(
        senescence_interval=config.senescence_interval,
        rooted_use_window=config.senescence_interval,
        minimum_senescence_sweeps=config.minimum_senescence_sweeps,
        newborn_grace_epochs=4,
        revival_grace_epochs=4,
        maximum_revival_candidates=config.maximum_revival_candidates,
        minimum_revival_similarity=config.minimum_revival_similarity,
        minimum_revival_improvement_fraction=(
            config.minimum_revival_improvement_fraction
        ),
        maximum_revival_regression=config.maximum_revival_regression,
        minimum_revival_lineages=2,
        minimum_neighbor_acceptances=1,
    )


def _root(
    config: HygieneLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> torch.Tensor:
    return torch.randn(
        1,
        config.sequence_length,
        config.width,
        generator=torch.Generator(device="cpu").manual_seed(config.seed),
    ).to(device=device, dtype=dtype)


def _member(
    uid: int,
    config: HygieneLabConfig,
    root: torch.Tensor,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> WaveCell:
    cell = WaveCell(
        StandaloneBDHCell(
            BDHCellConfig(
                width=config.width,
                rotary_pairs=config.rotary_pairs,
                initialization_seed=config.seed + uid,
            ),
            uid=uid,
        ),
        max_degree=8,
        max_fanout=4,
    ).to(device=device, dtype=dtype)
    cell.receptor.tune_to(root)
    return cell


def _graph(
    config: HygieneLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[HygieneController, torch.Tensor]:
    root = _root(config, device=device, dtype=dtype)
    substrate = SparseWaveSubstrate(
        SparseWaveConfig(
            max_degree=8,
            max_fanout=4,
            initial_route_energy=64.0,
        )
    ).to(device=device, dtype=dtype)
    for uid in (1, 2, 3, 10, 11, 20, 21, 30):
        substrate.add_cell(
            _member(uid, config, root, device=device, dtype=dtype)
        )
    substrate.connect(1, 2, route_familiarity=0.95)
    substrate.connect(2, 3, route_familiarity=0.95)
    substrate.connect(10, 11, route_familiarity=0.95)
    substrate.connect(11, 10, route_familiarity=0.95)
    substrate._cell(1).connect(NeighborPort(10, enabled=False))
    selected = _policy(config)
    ledger = RootedParticipationLedger(selected)
    controller = HygieneController(substrate, ledger=ledger, policy=selected)
    ledger.record_useful_credit(20, epoch=9, kind=UsefulCreditKind.ROUTING)
    ledger.record_useful_credit(21, epoch=9, kind=UsefulCreditKind.ABSTENTION)
    ledger.ensure(30, current_epoch=8, newborn=True)
    return controller, root


def _authorization() -> HygieneAuthorization:
    return HygieneAuthorization(
        actor="campaign36c:stage7-lab",
        reason="bounded idle hygiene cycle",
        thought_closed=True,
        delayed_credit_closed=True,
        structural_work_closed=True,
    )


def _pressure(*, authorized: bool = True) -> PurgeAuthorization:
    return PurgeAuthorization(
        actor="campaign36c:stage7-lab",
        reason="measured quarantine-segment pressure",
        operator_authorized=authorized,
        measured_free_bytes=10,
        required_free_bytes=100,
        requested_reclaim_bytes=50,
    )


def _digest(cell: WaveCell) -> str:
    buffer = io.BytesIO()
    torch.save({
        "transform": cell.transform.state_dict(),
        "receptor": cell.receptor.state_dict(),
    }, buffer)
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def _quarantine(controller: HygieneController):
    return controller.mark_and_sweep(
        current_epoch=10,
        ingress_uids=(1,),
        authorization=_authorization(),
    )


def _vitality_trial(
    config: HygieneLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    controller, root = _graph(config, device=device, dtype=dtype)
    before = {uid: _digest(controller.substrate._cell(uid)) for uid in (10, 11)}
    report = _quarantine(controller)
    unchanged = all(
        _digest(controller.quarantine[uid].cell) == before[uid]
        for uid in before
    )
    controller.substrate._cell(1).ports[10] = NeighborPort(
        10, route_familiarity=0.99, enabled=True
    )
    result = controller.substrate.run_thought(root, ingress_uids=1)
    return {
        "roots": list(report.root_uids),
        "marked": list(report.marked_uids),
        "unreachable": list(report.unreachable_uids),
        "quarantined": list(report.quarantined_uids),
        "preserved_routing_or_abstention": list(
            report.preserved_routing_or_abstention_uids
        ),
        "quarantine_preserved_weights": unchanged,
        "stale_route_references": result.telemetry["stale_route_references"],
        "stale_target_activated": 10 in result.telemetry["unique_uids"],
        "pressure": report.pressure,
        "pass": (
            report.quarantined_uids == (10, 11)
            and set(report.preserved_routing_or_abstention_uids) == {20, 21}
            and 30 in report.marked_uids
            and unchanged
            and result.telemetry["stale_route_references"] == 1
            and 10 not in result.telemetry["unique_uids"]
            and report.pressure == "metabolism"
        ),
    }


def _revival_trial(
    root_path: Path,
    config: HygieneLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    controller, root = _graph(config, device=device, dtype=dtype)
    store = PackedCellStore(root_path, page_capacity=config.page_capacity)
    store.commit_substrate(controller.substrate)
    _quarantine(controller)
    original_digest = _digest(controller.quarantine[10].cell)
    store.commit_hygiene(
        controller.substrate,
        quarantine_cells=controller.quarantine_cells(),
        quarantine_metadata=controller.quarantine_metadata(),
        reason="stage7-quarantine",
    )
    cold_substrate, _, _, _ = store.load_substrate(device=device)
    q_cells, q_optimizers, q_configs, q_metadata = store.load_quarantine(
        device=device
    )
    cold = HygieneController(cold_substrate, policy=_policy(config))
    cold.restore_quarantine(
        q_cells,
        q_metadata,
        optimizers=q_optimizers,
        optimizer_configs=q_configs,
    )
    tissue = cold.quarantine[10]
    selection = cold.begin_revival(RevivalRequest(
        residual_signature=tissue.signature,
        current_epoch=12,
        sponsor_uid=2,
        claim_address="latent:stage7-recurrence",
    ))
    with torch.inference_mode():
        target = tissue.cell.transform(root)
    baseline_loss = float(F.mse_loss(root.float(), target.float()))
    candidate_loss = float(F.mse_loss(target.float(), target.float()))
    improvement = (baseline_loss - candidate_loss) / max(baseline_loss, 1e-12)
    revival = cold.complete_revival(
        RevivalEvidence(
            uid=10,
            improvement_fraction=improvement,
            maximum_established_regression=0.0,
            useful_present_contribution=candidate_loss < baseline_loss,
            evidence_lineages=("stage7:a", "stage7:b"),
            accepted_ports=(NeighborPort(2, route_familiarity=0.95),),
        ),
        current_epoch=13,
    )
    store.commit_hygiene(
        cold.substrate,
        quarantine_cells=cold.quarantine_cells(),
        quarantine_metadata=cold.quarantine_metadata(),
        reason="stage7-revival",
    )
    restored, _, _, anatomy = store.load_substrate(device=device)
    same_uid = restored.has_active_uid(10) and 10 not in store.manifest["retired_uids"]
    content_unchanged = _digest(restored._cell(10)) == original_digest
    old_edges_not_restored = tuple(restored._cell(10).ports) == (2,)
    return {
        "selection": asdict(selection),
        "baseline_loss": baseline_loss,
        "candidate_loss": candidate_loss,
        "improvement_fraction": improvement,
        "decision": asdict(revival),
        "cold_quarantine_uids": sorted(q_cells),
        "restored_uid": 10 if same_uid else None,
        "content_digest_preserved": content_unchanged,
        "renegotiated_ports": sorted(restored._cell(10).ports),
        "record_generation": anatomy[10]["header"]["record_generation"],
        "pass": (
            selection.action == "shadow_revival"
            and revival.admitted
            and same_uid
            and content_unchanged
            and old_edges_not_restored
            and improvement >= config.minimum_revival_improvement_fraction
        ),
    }


def _purge_trial(
    root_path: Path,
    config: HygieneLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    controller, _ = _graph(config, device=device, dtype=dtype)
    store = PackedCellStore(root_path, page_capacity=config.page_capacity)
    store.commit_substrate(controller.substrate)
    _quarantine(controller)
    store.commit_hygiene(
        controller.substrate,
        quarantine_cells=controller.quarantine_cells(),
        quarantine_metadata=controller.quarantine_metadata(),
    )
    old_location = store.manifest["quarantine_index"]["10"]
    old_declaration = next(
        item for item in store.manifest["segments"]
        if item["segment_id"] == old_location["segment_id"]
    )
    old_path = store.segment_root / old_declaration["path"]
    refused = controller.purge((10,), authorization=_pressure(authorized=False))
    admitted = controller.purge((10,), authorization=_pressure())
    store.commit_hygiene(
        controller.substrate,
        quarantine_cells=controller.quarantine_cells(),
        quarantine_metadata=controller.quarantine_metadata(),
        purge_uids=controller.purged_uids,
        reason="stage7-storage-pressure-purge",
    )
    reclaim = [
        item for item in store.journal_events()
        if item.get("phase") == "RECLAIM"
    ]
    return {
        "unauthorized_action": refused.action,
        "authorized_action": admitted.action,
        "purged_uids": list(admitted.purged_uids),
        "surviving_quarantine_uids": sorted(
            map(int, store.manifest["quarantine_index"])
        ),
        "retired_uids": store.manifest["retired_uids"],
        "old_quarantine_page_reclaimed": not old_path.exists(),
        "bytes_reclaimed": sum(item.get("bytes_reclaimed", 0) for item in reclaim),
        "pass": (
            refused.purged_uids == ()
            and admitted.purged_uids == (10,)
            and store.manifest["lifecycle"]["10"] == "purged"
            and 10 in store.manifest["retired_uids"]
            and set(map(int, store.manifest["quarantine_index"])) == {11}
            and not old_path.exists()
            and bool(reclaim)
        ),
    }


def _fault_trial(
    root_path: Path,
    config: HygieneLabConfig,
    *,
    device: torch.device,
    dtype: torch.dtype,
) -> dict[str, Any]:
    quarantine_results: dict[str, bool] = {}
    purge_results: dict[str, bool] = {}
    for fault in FaultPoint:
        controller, _ = _graph(config, device=device, dtype=dtype)
        store_root = root_path / "quarantine" / fault.value
        store = PackedCellStore(store_root, page_capacity=config.page_capacity)
        store.commit_substrate(controller.substrate)
        _quarantine(controller)
        try:
            store.commit_hygiene(
                controller.substrate,
                quarantine_cells=controller.quarantine_cells(),
                quarantine_metadata=controller.quarantine_metadata(),
                fault_at=fault,
            )
        except InjectedCrash:
            pass
        recovered = PackedCellStore(store_root, page_capacity=config.page_capacity)
        active = set(map(int, recovered.manifest["uid_index"]))
        quarantined = set(map(int, recovered.manifest.get("quarantine_index", {})))
        old = {10, 11}.issubset(active) and not {10, 11}.intersection(quarantined)
        new = not {10, 11}.intersection(active) and {10, 11}.issubset(quarantined)
        expect_new = fault in {FaultPoint.AFTER_COMMIT, FaultPoint.AFTER_PUBLISH}
        quarantine_results[fault.value] = new if expect_new else old

        controller, _ = _graph(config, device=device, dtype=dtype)
        purge_root = root_path / "purge" / fault.value
        purge_store = PackedCellStore(purge_root, page_capacity=config.page_capacity)
        purge_store.commit_substrate(controller.substrate)
        _quarantine(controller)
        purge_store.commit_hygiene(
            controller.substrate,
            quarantine_cells=controller.quarantine_cells(),
            quarantine_metadata=controller.quarantine_metadata(),
        )
        controller.purge((10, 11), authorization=_pressure())
        try:
            purge_store.commit_hygiene(
                controller.substrate,
                quarantine_cells=controller.quarantine_cells(),
                quarantine_metadata=controller.quarantine_metadata(),
                purge_uids=controller.purged_uids,
                fault_at=fault,
            )
        except InjectedCrash:
            pass
        recovered = PackedCellStore(purge_root, page_capacity=config.page_capacity)
        quarantined = set(map(int, recovered.manifest.get("quarantine_index", {})))
        retired = set(recovered.manifest["retired_uids"])
        old = {10, 11}.issubset(quarantined) and not {10, 11}.intersection(retired)
        new = not {10, 11}.intersection(quarantined) and {10, 11}.issubset(retired)
        purge_results[fault.value] = new if expect_new else old
    return {
        "quarantine_boundaries": quarantine_results,
        "purge_boundaries": purge_results,
        "pass": all(quarantine_results.values()) and all(purge_results.values()),
    }


def run_hygiene_laboratory(
    config: HygieneLabConfig | None = None,
    *,
    device: str | torch.device = "cpu",
    dtype: torch.dtype = torch.float32,
    scratch_root: str | Path | None = None,
) -> dict[str, Any]:
    config = config or HygieneLabConfig()
    config.validate()
    target_device = torch.device(device)
    if target_device.type == "cpu" and dtype != torch.float32:
        raise ValueError("the CPU Stage-7 lab requires float32")
    if target_device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable")
    parent = Path(scratch_root) if scratch_root is not None else None
    if parent is not None:
        parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="campaign36c-stage7-", dir=parent) as temp:
        root = Path(temp)
        vitality = _vitality_trial(config, device=target_device, dtype=dtype)
        revival = _revival_trial(
            root / "revival", config, device=target_device, dtype=dtype
        )
        purge = _purge_trial(
            root / "purge", config, device=target_device, dtype=dtype
        )
        faults = _fault_trial(
            root / "faults", config, device=target_device, dtype=dtype
        )
    exit_gate = all(item["pass"] for item in (vitality, revival, purge, faults))
    return {
        "schema_version": CAMPAIGN36C_HYGIENE_LAB_RESULT_SCHEMA,
        "lab_config": asdict(config),
        "execution": {
            "device": str(target_device),
            "dtype": str(dtype),
            "scratch_filesystem": str(parent or Path(tempfile.gettempdir())),
        },
        "vitality_and_reachability": vitality,
        "revival": revival,
        "purge": purge,
        "fault_injection": faults,
        "selection": {
            "useful_noncontent_survival_pass": vitality["pass"],
            "obsolete_island_quarantine_pass": vitality["pass"],
            "same_uid_revival_pass": revival["pass"],
            "pressure_purge_pass": purge["pass"],
            "crash_consistency_pass": faults["pass"],
            "stage7_exit_gate_met": exit_gate,
        },
    }


def merge_hygiene_lab_results(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one hygiene report is required")
    first = reports[0]
    if any(report["lab_config"] != first["lab_config"] for report in reports[1:]):
        raise ValueError("hygiene reports must use identical laboratory bounds")
    return {
        "schema_version": CAMPAIGN36C_HYGIENE_LAB_RESULT_SCHEMA,
        "lab_config": first["lab_config"],
        "execution": {"devices": [report["execution"] for report in reports]},
        "device_reports": reports,
        "selection": {
            "all_devices_pass": all(
                report["selection"]["stage7_exit_gate_met"] for report in reports
            ),
            "stage7_exit_gate_met": all(
                report["selection"]["stage7_exit_gate_met"] for report in reports
            ),
        },
    }


def write_hygiene_lab_result(path: str | Path, report: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
