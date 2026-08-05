from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

from training.pipeline.control.ledger import ControlLedger, LedgerError


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "meta/scripts/run_allowlist_wave.py"
SPEC = importlib.util.spec_from_file_location("run_allowlist_wave", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RecordingTransport:
    def __init__(self, sync_action=None) -> None:
        self.sync_action = sync_action
        self.synced: list[str] = []
        self.dispatched: list[str] = []

    def sync(self, plan_id: str):
        self.synced.append(plan_id)
        if self.sync_action is not None:
            return self.sync_action(plan_id)
        return {}

    def dispatch(self, plan_id: str):
        self.dispatched.append(plan_id)
        return {}


def test_reconcile_imports_existing_remote_result_without_redispatch(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path)
    plan = ledger.create_plan(
        kind="cortex_evaluation",
        mode="live",
        payload={},
        created_by="test",
        plan_id="plan-existing",
        authorization={
            "allow_weight_updates": False,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    )

    def complete_locally(plan_id: str):
        receipt = ledger.claim(plan_id, "remote", 60)
        assert receipt is not None
        ledger.mark_running(plan_id, "remote")
        ledger.complete(plan_id, "remote", status="succeeded", result={})
        return {"plan": plan}

    transport = RecordingTransport(complete_locally)
    MODULE._reconcile_current_plan(ledger, transport, plan["plan_id"])

    assert ledger.receipt(plan["plan_id"])["status"] == "completed"
    assert transport.synced == [plan["plan_id"]]
    assert transport.dispatched == []


def test_reconcile_preserves_queue_during_transport_unavailability(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path)
    plan = ledger.create_plan(
        kind="cortex_evaluation",
        mode="live",
        payload={},
        created_by="test",
        plan_id="plan-queued",
        authorization={
            "allow_weight_updates": False,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    )

    class UnavailableTransport(RecordingTransport):
        def sync(self, plan_id: str):
            self.synced.append(plan_id)
            raise subprocess.TimeoutExpired("ssh", 30)

        def dispatch(self, plan_id: str):
            self.dispatched.append(plan_id)
            raise LedgerError("provider unavailable")

    transport = UnavailableTransport()
    MODULE._reconcile_current_plan(ledger, transport, plan["plan_id"])

    receipt = ledger.receipt(plan["plan_id"])
    assert receipt["status"] == "queued"
    assert receipt["attempt_count"] == 0
    assert transport.synced == [plan["plan_id"]]
    assert transport.dispatched == [plan["plan_id"]]


def test_terminal_wave_disables_its_persistent_timer(monkeypatch) -> None:
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(MODULE.subprocess, "run", run)

    assert MODULE._stop_persistent_wake_cycle() is True
    assert calls[0][0] == [
        "/usr/bin/systemctl",
        "--user",
        "disable",
        "--now",
        "ninereeds-allowlist-wave.timer",
    ]
    assert calls[0][1]["timeout"] == 10
