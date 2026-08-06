from __future__ import annotations

from types import SimpleNamespace

from mission_hub.daemon import MissionHubDaemon
from mission_hub.errors import ConflictError


def test_stale_deployment_refusal_does_not_stop_daemon_tick(monkeypatch) -> None:
    class Store:
        @staticmethod
        def expire_leases(bundle, *, actor):
            return 0

        @staticmethod
        def active_deployment(machine_id):
            return {"id": "dep-stale"}

    class Service:
        def __init__(self, store, bundle):
            pass

        @staticmethod
        def lease_envelope(**kwargs):
            raise ConflictError("agent requested a lease with a non-active configuration")

    monkeypatch.setattr("mission_hub.daemon.Scheduler", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: []))
    monkeypatch.setattr("mission_hub.daemon.VisualWorkflowCoordinator", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: []))
    monkeypatch.setattr("mission_hub.daemon.MissionHubService", Service)
    bundle = SimpleNamespace(machines={
        "trainbox": {"enabled": True, "maintenance_mode": False, "transport": "restricted_ssh"},
    })
    daemon = MissionHubDaemon(Store(), bundle)
    assert daemon.tick() == {"expired": 0, "scheduled": 0, "visual_advanced": 0, "dispatched": 0}
