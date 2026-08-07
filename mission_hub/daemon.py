"""Mission Hub-owned scheduling, lease expiry, and dispatch loop."""

from __future__ import annotations

import logging
import signal
import threading
import time

from .config import ConfigBundle
from .errors import MissionHubError
from .scheduler import Scheduler
from .service import MissionHubService
from .store import MissionHubStore
from .transport import SSHDispatcher
from .visual_workflow import VisualWorkflowCoordinator
from .cortex_workflow import CortexWorkflowCoordinator
from .chat_workflow import ChatCoordinator
from .retention import RetentionManager


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
        expired = self.store.expire_leases(self.bundle, actor="mission-hub-daemon")
        control = self.store.apply_pipeline_state(actor="mission-hub-daemon")
        chat_closed = ChatCoordinator(self.store, self.bundle).tick(actor="mission-hub-daemon")
        if hasattr(self.bundle, "retention"):
            try:
                RetentionManager(self.store, self.bundle).automatic_tick(
                    machine_id="trainbox", actor="mission-hub-daemon:retention",
                )
            except MissionHubError as exc:
                self.log.info("automatic retention unavailable: %s", exc)
            except Exception as exc:
                self.log.exception("automatic retention failed closed: %s", exc)
        running = control["desired_state"] == "running"
        scheduled = len(Scheduler(self.store, self.bundle).tick(actor="mission-hub-daemon")) if running else 0
        running = running and self.store.pipeline_control()["desired_state"] == "running"
        if not running:
            self.store.apply_pipeline_state(actor="mission-hub-daemon")
        visual_advanced = len(VisualWorkflowCoordinator(self.store, self.bundle).tick(actor="mission-hub-daemon")) if running else 0
        cortex_advanced = len(CortexWorkflowCoordinator(self.store, self.bundle).tick(actor="mission-hub-daemon")) if running else 0
        dispatched = 0
        for machine_id, machine in self.bundle.machines.items():
            if running and self.store.pipeline_control()["desired_state"] != "running":
                self.store.apply_pipeline_state(actor="mission-hub-daemon")
                break
            if not machine["enabled"] or machine["maintenance_mode"] or machine["transport"] not in {"local", "restricted_ssh"}:
                continue
            try:
                deployment = self.store.active_deployment(machine_id)
                service = MissionHubService(self.store, self.bundle)
                envelope = service.lease_envelope(machine_id=machine_id, deployment_id=deployment["id"], actor="mission-hub-daemon")
            except MissionHubError as exc:
                # A missing or configuration-stale deployment is an expected
                # stopped/commissioning state. The safety boundary refuses a
                # lease; the daemon remains available for other machines.
                self.log.info("dispatch unavailable for %s: %s", machine_id, exc)
                continue
            if envelope is None:
                continue
            self.store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="mission-hub-daemon")
            try:
                status = service.execute_and_record(machine_id, envelope, actor=f"agent:{machine_id}")
                dispatched += int(status == "succeeded")
            except Exception as exc:
                # At this point the shared lifecycle closer itself failed (for
                # example, durable incident logging was unavailable). The run
                # intentionally remains live and will expire rather than being
                # silently closed without its required evidence.
                self.log.exception("could not close dispatch lifecycle for %s: %s", machine_id, exc)
        chat_closed += ChatCoordinator(self.store, self.bundle).tick(actor="mission-hub-daemon")
        return {"expired": expired, "scheduled": scheduled, "visual_advanced": visual_advanced, "cortex_advanced": cortex_advanced, "chat_closed": chat_closed, "dispatched": dispatched}


def run_daemon(store: MissionHubStore, bundle: ConfigBundle) -> None:
    daemon = MissionHubDaemon(store, bundle)
    signal.signal(signal.SIGTERM, lambda *_: daemon.stop.set())
    signal.signal(signal.SIGINT, lambda *_: daemon.stop.set())
    daemon.run()
