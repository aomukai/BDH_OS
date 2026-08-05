"""Mission Hub-owned scheduling, lease expiry, and dispatch loop."""

from __future__ import annotations

import logging
import signal
import threading
import time

from .config import ConfigBundle
from .errors import MissionHubError, RemoteJobError
from .scheduler import Scheduler
from .service import MissionHubService
from .store import MissionHubStore
from .transport import SSHDispatcher


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
        scheduled = len(Scheduler(self.store, self.bundle).tick(actor="mission-hub-daemon"))
        dispatched = 0
        for machine_id, machine in self.bundle.machines.items():
            if not machine["enabled"] or machine["maintenance_mode"] or machine["transport"] not in {"local", "restricted_ssh"}:
                continue
            try:
                deployment = self.store.active_deployment(machine_id)
            except MissionHubError:
                continue
            service = MissionHubService(self.store, self.bundle)
            envelope = service.lease_envelope(machine_id=machine_id, deployment_id=deployment["id"], actor="mission-hub-daemon")
            if envelope is None:
                continue
            self.store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="mission-hub-daemon")
            try:
                result = service.execute_envelope(machine_id, envelope)
                service.accept_result(envelope, result, actor=f"agent:{machine_id}")
                dispatched += 1
            except RemoteJobError as exc:
                service.record_failure(
                    envelope, failure_class=exc.failure_class, code=exc.code,
                    message=str(exc), actor="mission-hub-daemon",
                )
                self.log.warning("remote job failed for %s: %s", machine_id, exc)
            except MissionHubError as exc:
                service.record_transport_failure(envelope, message=str(exc), actor="mission-hub-daemon")
                self.log.warning("dispatch failed for %s: %s", machine_id, exc)
            except Exception as exc:
                service.record_failure(
                    envelope, failure_class="deterministic_specification",
                    code="unexpected_internal_error",
                    message=f"{type(exc).__name__}: {exc}", actor="mission-hub-daemon",
                )
                self.log.exception("unexpected dispatch failure for %s", machine_id)
        return {"expired": expired, "scheduled": scheduled, "dispatched": dispatched}


def run_daemon(store: MissionHubStore, bundle: ConfigBundle) -> None:
    daemon = MissionHubDaemon(store, bundle)
    signal.signal(signal.SIGTERM, lambda *_: daemon.stop.set())
    signal.signal(signal.SIGINT, lambda *_: daemon.stop.set())
    daemon.run()
