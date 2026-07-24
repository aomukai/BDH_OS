from __future__ import annotations

import json
import subprocess

from lab.backend.control.status import ControlStatusService
from training.pipeline.control.ledger import ControlLedger
from tests.helpers import make_lab_config


def test_control_status_sanitizes_local_and_remote_ledgers(tmp_path, monkeypatch) -> None:
    config = make_lab_config(tmp_path)
    ledger = ControlLedger(config.orchestrator_control_root)
    ledger.create_plan(
        kind="status_refresh",
        mode="shadow",
        payload={"secret_prompt": "must not reach the Lab"},
        created_by="test",
        plan_id="plan-control-status-test",
    )
    remote_snapshot = {
        "schema_version": "ninereeds_control_snapshot_v1",
        "root": "/private/trainbox/path",
        "counts": {"completed": 2},
        "latest_receipts": [
            {
                "plan_id": "plan-remote-test",
                "status": "completed",
                "attempt_count": 1,
                "updated_at": "2026-07-25T00:00:00Z",
                "history": [{"detail": "private worker detail"}],
            }
        ],
    }

    def fake_run(args, **kwargs):
        if args[0] == "/usr/bin/ssh":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"ok": True, "snapshot": remote_snapshot}),
                stderr="",
            )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ControlStatusService(config).status(force=True)

    assert result["ok"] is True
    assert result["local"]["counts"] == {"queued": 1}
    assert result["trainbox"]["counts"] == {"completed": 2}
    serialized = json.dumps(result)
    assert "secret_prompt" not in serialized
    assert "private worker detail" not in serialized
    assert "/private/trainbox/path" not in serialized


def test_control_status_handles_unreachable_trainbox(tmp_path, monkeypatch) -> None:
    config = make_lab_config(tmp_path)

    def fake_run(args, **kwargs):
        if args[0] == "/usr/bin/ssh":
            return subprocess.CompletedProcess(
                args=args, returncode=255, stdout="", stderr="network unavailable"
            )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ControlStatusService(config).status(force=True)

    assert result["ok"] is False
    assert result["local"]["ok"] is True
    assert result["trainbox"]["reachable"] is False
