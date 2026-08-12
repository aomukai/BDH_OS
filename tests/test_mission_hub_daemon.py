from __future__ import annotations

from types import SimpleNamespace
import threading

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

        @staticmethod
        def apply_pipeline_state(*, actor):
            return {"desired_state": "running"}

        @staticmethod
        def pipeline_control():
            return {"desired_state": "running"}

    class Service:
        def __init__(self, store, bundle):
            pass

        @staticmethod
        def lease_envelope(**kwargs):
            raise ConflictError("agent requested a lease with a non-active configuration")

    monkeypatch.setattr("mission_hub.daemon.Scheduler", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: []))
    monkeypatch.setattr("mission_hub.daemon.VisualWorkflowCoordinator", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: []))
    monkeypatch.setattr("mission_hub.daemon.MaterialWorkflowCoordinator", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: []))
    monkeypatch.setattr("mission_hub.daemon.CortexWorkflowCoordinator", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: []))
    monkeypatch.setattr("mission_hub.daemon.Campaign35Coordinator", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: []))
    monkeypatch.setattr("mission_hub.daemon.ChatCoordinator", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: 0))
    monkeypatch.setattr("mission_hub.daemon.MissionHubService", Service)
    bundle = SimpleNamespace(machines={
        "trainbox": {"enabled": True, "maintenance_mode": False, "transport": "restricted_ssh"},
    })
    daemon = MissionHubDaemon(Store(), bundle)
    assert daemon.tick() == {"expired": 0, "scheduled": 0, "campaign35_advanced": 0, "visual_advanced": 0, "material_advanced": 0, "cortex_advanced": 0, "chat_closed": 0, "operations_closed": 0, "recoveries_advanced": 0, "dispatched": 0}


def test_machine_lane_survives_an_unexpected_dispatch_failure(monkeypatch) -> None:
    machine = {"enabled": True, "maintenance_mode": False, "transport": "local"}
    bundle = SimpleNamespace(
        machines={"mission-hub": machine},
        base={"scheduler": {"poll_seconds": 0}},
    )
    daemon = MissionHubDaemon(object(), bundle)

    def fail_once(*args):
        daemon.stop.set()
        raise ValueError("invalid stale runtime settings")

    monkeypatch.setattr(daemon, "_dispatch_one", fail_once)

    daemon._machine_loop("mission-hub")


def test_paused_pipeline_performs_housekeeping_but_starts_no_campaign_work(monkeypatch) -> None:
    class Store:
        @staticmethod
        def expire_leases(bundle, *, actor):
            return 2

        @staticmethod
        def apply_pipeline_state(*, actor):
            return {"desired_state": "paused"}

    monkeypatch.setattr("mission_hub.daemon.Scheduler", lambda *args: (_ for _ in ()).throw(AssertionError("scheduler ran while paused")))
    monkeypatch.setattr("mission_hub.daemon.VisualWorkflowCoordinator", lambda *args: (_ for _ in ()).throw(AssertionError("workflow ran while paused")))
    monkeypatch.setattr("mission_hub.daemon.MaterialWorkflowCoordinator", lambda *args: (_ for _ in ()).throw(AssertionError("material workflow ran while paused")))
    monkeypatch.setattr("mission_hub.daemon.ChatCoordinator", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: 0))
    daemon = MissionHubDaemon(Store(), SimpleNamespace(machines={}))
    assert daemon.tick() == {"expired": 2, "scheduled": 0, "campaign35_advanced": 0, "visual_advanced": 0, "material_advanced": 0, "cortex_advanced": 0, "chat_closed": 0, "operations_closed": 0, "recoveries_advanced": 0, "dispatched": 0}


def test_paused_pipeline_still_dispatches_independent_on_call_work(monkeypatch) -> None:
    class Store:
        @staticmethod
        def pipeline_control(): return {"desired_state": "paused"}
        @staticmethod
        def apply_pipeline_state(*, actor): return {"desired_state": "paused"}
        @staticmethod
        def active_deployment(machine_id): return {"id": "dep-on-call"}
        @staticmethod
        def start_run(run_id, token, *, actor): return None

    class Service:
        def __init__(self, store, bundle): pass
        @staticmethod
        def lease_envelope(*, machine_id, deployment_id, actor):
            return {
                "job": {"type": "operations.respond"},
                "run": {"id": "run-on-call"}, "lease": {"token": "token-on-call"},
            }
        @staticmethod
        def execute_and_record(machine_id, envelope, *, actor): return "succeeded"

    monkeypatch.setattr("mission_hub.daemon.MissionHubService", Service)
    machine = {"enabled": True, "maintenance_mode": False, "transport": "local"}
    daemon = MissionHubDaemon(Store(), SimpleNamespace(machines={"mission-hub": machine}))

    assert daemon._dispatch_one(daemon.bundle, "mission-hub", machine) == 1


def test_slow_retention_is_not_run_inside_the_scheduler_tick(monkeypatch) -> None:
    class Store:
        @staticmethod
        def expire_leases(bundle, *, actor): return 0
        @staticmethod
        def apply_pipeline_state(*, actor): return {"desired_state": "paused"}

    monkeypatch.setattr(
        "mission_hub.daemon.RetentionManager",
        lambda *args: (_ for _ in ()).throw(AssertionError("retention blocked scheduler tick")),
    )
    monkeypatch.setattr("mission_hub.daemon.ChatCoordinator", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: 0))
    bundle = SimpleNamespace(machines={}, retention={}, recovery=None)

    result = MissionHubDaemon(Store(), bundle).tick(dispatch=False)

    assert result["scheduled"] == 0


def test_enabled_machine_lanes_dispatch_without_cross_machine_starvation(monkeypatch) -> None:
    barrier = threading.Barrier(2)

    class Store:
        @staticmethod
        def expire_leases(bundle, *, actor): return 0
        @staticmethod
        def apply_pipeline_state(*, actor): return {"desired_state": "running"}
        @staticmethod
        def pipeline_control(): return {"desired_state": "running"}
        @staticmethod
        def active_deployment(machine_id): return {"id": f"dep-{machine_id}"}
        @staticmethod
        def start_run(run_id, token, *, actor): return None

    class Service:
        def __init__(self, store, bundle): pass
        @staticmethod
        def lease_envelope(*, machine_id, deployment_id, actor):
            return {"run": {"id": f"run-{machine_id}"}, "lease": {"token": f"token-{machine_id}"}}
        @staticmethod
        def execute_and_record(machine_id, envelope, *, actor):
            barrier.wait(timeout=2)
            return "succeeded"

    for name in (
        "Scheduler", "VisualWorkflowCoordinator", "MaterialWorkflowCoordinator",
        "CortexWorkflowCoordinator", "Campaign35Coordinator",
    ):
        monkeypatch.setattr(f"mission_hub.daemon.{name}", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: []))
    monkeypatch.setattr("mission_hub.daemon.ChatCoordinator", lambda store, bundle: SimpleNamespace(tick=lambda **kwargs: 0))
    monkeypatch.setattr("mission_hub.daemon.MissionHubService", Service)
    machine = {"enabled": True, "maintenance_mode": False, "transport": "local"}
    bundle = SimpleNamespace(machines={"mission-hub": machine, "trainbox": machine})

    result = MissionHubDaemon(Store(), bundle).tick()

    assert result["dispatched"] == 2
