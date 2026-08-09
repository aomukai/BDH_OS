"""Mission Hub-owned scheduling, lease expiry, and dispatch loop."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import signal
import threading
import time

from .config import ConfigBundle
from .config import bundle_from_snapshot, machine_id_for_role
from .errors import MissionHubError
from .scheduler import Scheduler
from .service import MissionHubService
from .store import MissionHubStore
from .transport import SSHDispatcher
from .visual_workflow import VisualWorkflowCoordinator
from .material_workflow import MaterialWorkflowCoordinator
from .cortex_workflow import CortexWorkflowCoordinator
from .campaign35_workflow import Campaign35Coordinator
from .chat_workflow import ChatCoordinator
from .retention import RetentionManager
from .operations_workflow import OperationalResponseCoordinator
from .recovery import RecoveryCoordinator
from .repair_driver import BoundedCodexRepairDriver
from .lab import LabStore


class MissionHubDaemon:
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store = store
        self.bundle = bundle
        self.stop = threading.Event()
        self.log = logging.getLogger("mission_hub.daemon")

    def run(self) -> None:
        while not self.stop.is_set():
            self.tick()
            self.stop.wait(self.bundle.base["scheduler"]["poll_seconds"])

    def tick(self) -> dict[str, int]:
        if hasattr(self.store, "active_config"):
            active = self.store.active_config()
            if active["sha256"] != self.bundle.sha256:
                self.bundle = bundle_from_snapshot(self.bundle.root, active["payload"])
        lab = LabStore(self.store, self.bundle) if hasattr(self.store, "_connect") else None
        if lab is not None:
            lab.apply_pending_settings(self.bundle, actor="mission-hub-daemon:settings")
        bundle = lab.effective_bundle(self.bundle) if lab is not None else self.bundle
        expired = self.store.expire_leases(bundle, actor="mission-hub-daemon")
        control = self.store.apply_pipeline_state(actor="mission-hub-daemon")
        operations_closed = OperationalResponseCoordinator(self.store, bundle).tick(actor="mission-hub-daemon:on-call")
        recoveries_advanced = 0
        if hasattr(self.store, "_connect") and hasattr(bundle, "recovery"):
            recoveries_advanced = RecoveryCoordinator(
                self.store, bundle, BoundedCodexRepairDriver(self.store, bundle),
            ).tick(actor="mission-hub-daemon:recovery")
        chat_closed = ChatCoordinator(self.store, bundle).tick(actor="mission-hub-daemon")
        if hasattr(bundle, "retention"):
            try:
                RetentionManager(self.store, bundle).automatic_tick(
                    machine_id=machine_id_for_role(bundle, "trainbox"), actor="mission-hub-daemon:retention",
                )
            except MissionHubError as exc:
                self.log.info("automatic retention unavailable: %s", exc)
            except Exception as exc:
                self.log.exception("automatic retention failed closed: %s", exc)
        running = control["desired_state"] == "running"
        scheduled = len(Scheduler(self.store, bundle).tick(actor="mission-hub-daemon")) if running else 0
        running = running and self.store.pipeline_control()["desired_state"] == "running"
        if not running:
            self.store.apply_pipeline_state(actor="mission-hub-daemon")
        campaign35_advanced = len(Campaign35Coordinator(self.store, bundle).tick(actor="mission-hub-daemon")) if running else 0
        visual_advanced = len(VisualWorkflowCoordinator(self.store, bundle).tick(actor="mission-hub-daemon")) if running else 0
        material_advanced = len(MaterialWorkflowCoordinator(self.store, bundle).tick(actor="mission-hub-daemon")) if running else 0
        cortex_advanced = len(CortexWorkflowCoordinator(self.store, bundle).tick(actor="mission-hub-daemon")) if running else 0
        dispatchable = [
            (machine_id, machine) for machine_id, machine in bundle.machines.items()
            if machine["enabled"] and not machine["maintenance_mode"]
            and machine["transport"] in {"local", "restricted_ssh"}
        ]
        # Machines are independent execution lanes. Running them serially let
        # a provider-backed Mission Hub job starve the trainbox queue even when
        # the trainbox was idle. Each lane still enforces its own configured
        # concurrency in lease_next; this only removes cross-machine blocking.
        with ThreadPoolExecutor(max_workers=max(1, len(dispatchable)), thread_name_prefix="mission-hub-dispatch") as pool:
            dispatched = sum(pool.map(
                lambda item: self._dispatch_one(bundle, *item), dispatchable,
            )) if dispatchable else 0
        if lab is not None and lab.apply_pending_settings(self.bundle, actor="mission-hub-daemon:settings"):
            bundle = lab.effective_bundle(self.bundle)
        chat_closed += ChatCoordinator(self.store, bundle).tick(actor="mission-hub-daemon")
        operations_closed += OperationalResponseCoordinator(self.store, bundle).tick(actor="mission-hub-daemon:on-call")
        return {"expired": expired, "scheduled": scheduled, "campaign35_advanced": campaign35_advanced, "visual_advanced": visual_advanced, "material_advanced": material_advanced, "cortex_advanced": cortex_advanced, "chat_closed": chat_closed, "operations_closed": operations_closed, "recoveries_advanced": recoveries_advanced, "dispatched": dispatched}

    def _dispatch_one(self, bundle: ConfigBundle, machine_id: str, machine: dict) -> int:
        if self.store.pipeline_control()["desired_state"] != "running":
            self.store.apply_pipeline_state(actor="mission-hub-daemon")
            return 0
        try:
            deployment = self.store.active_deployment(machine_id)
            service = MissionHubService(self.store, bundle)
            envelope = service.lease_envelope(
                machine_id=machine_id, deployment_id=deployment["id"], actor="mission-hub-daemon",
            )
        except MissionHubError as exc:
            # A missing or configuration-stale deployment is an expected
            # stopped/commissioning state. The safety boundary refuses a
            # lease; the daemon remains available for other machines.
            self.log.info("dispatch unavailable for %s: %s", machine_id, exc)
            return 0
        if envelope is None:
            return 0
        self.store.start_run(
            envelope["run"]["id"], envelope["lease"]["token"], actor="mission-hub-daemon",
        )
        try:
            status = service.execute_and_record(machine_id, envelope, actor=f"agent:{machine_id}")
            return int(status == "succeeded")
        except Exception as exc:
            # At this point the shared lifecycle closer itself failed (for
            # example, durable incident logging was unavailable). The run
            # intentionally remains live and will expire rather than being
            # silently closed without its required evidence.
            self.log.exception("could not close dispatch lifecycle for %s: %s", machine_id, exc)
            return 0


def run_daemon(store: MissionHubStore, bundle: ConfigBundle) -> None:
    daemon = MissionHubDaemon(store, bundle)
    signal.signal(signal.SIGTERM, lambda *_: daemon.stop.set())
    signal.signal(signal.SIGINT, lambda *_: daemon.stop.set())
    daemon.run()
