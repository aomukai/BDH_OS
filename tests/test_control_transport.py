from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest

from training.pipeline.control.ledger import ControlLedger, LedgerError
from training.pipeline.control.trainbox_remote import handle_command
from training.pipeline.control.transport import SshControlTransport


def plan(ledger: ControlLedger) -> dict:
    return ledger.create_plan(
        kind="phase_block",
        mode="shadow",
        payload={"phase_id": "phase_0_form", "runner_args": []},
        created_by="orchestrator:test",
        plan_id="plan-transport",
    )


def test_restricted_remote_import_is_idempotent_and_rejects_shell(
    tmp_path: Path,
) -> None:
    local = ControlLedger(tmp_path / "local")
    remote = ControlLedger(tmp_path / "remote")
    envelope = plan(local)
    wake_count = 0

    def wake():
        nonlocal wake_count
        wake_count += 1
        return {"ok": True, "service": "test"}

    for _ in range(2):
        status, response = handle_command(
            "submit-and-wake",
            ledger=remote,
            stdin=io.BytesIO(json.dumps(envelope).encode()),
            wake=wake,
        )
        assert status == 0
        assert response["plan_sha256"] == envelope["content_sha256"]
    assert len(list(remote.plans_dir.glob("*.json"))) == 1
    assert wake_count == 2

    status, response = handle_command(
        "bash -c id",
        ledger=remote,
        stdin=io.BytesIO(),
    )
    assert status == 126
    assert response["error"] == "command not permitted"


def test_transport_dispatch_and_terminal_sync(tmp_path: Path) -> None:
    local = ControlLedger(tmp_path / "local")
    remote = ControlLedger(tmp_path / "remote")
    envelope = plan(local)

    def runner(command, *, input, **_kwargs):
        remote_command = command[-1]
        status, response = handle_command(
            remote_command,
            ledger=remote,
            stdin=io.BytesIO(input or b""),
            wake=lambda: {"ok": True, "service": "test"},
        )
        return subprocess.CompletedProcess(
            command,
            status,
            stdout=json.dumps(response).encode(),
            stderr=b"",
        )

    transport = SshControlTransport(local, runner=runner)
    transport.dispatch(envelope["plan_id"])
    assert remote.plan(envelope["plan_id"]) == envelope

    assert remote.claim(envelope["plan_id"], "worker:test", 60) is not None
    remote.mark_running(envelope["plan_id"], "worker:test")
    remote.complete(
        envelope["plan_id"],
        "worker:test",
        status="succeeded",
        result={"shadow": True},
    )
    transport.sync(envelope["plan_id"])
    assert local.receipt(envelope["plan_id"])["status"] == "completed"
    assert local.report(envelope["plan_id"])["result"] == {"shadow": True}


def test_transport_syncs_reportless_remote_dead_letter(tmp_path: Path) -> None:
    local = ControlLedger(tmp_path / "local")
    remote = ControlLedger(tmp_path / "remote")
    envelope = local.create_plan(
        kind="executor_job",
        mode="shadow",
        payload={"job_id": "terminal-failure"},
        created_by="orchestrator:test",
        plan_id="plan-terminal-failure",
        max_attempts=1,
    )
    remote.import_plan(envelope)
    assert remote.claim(envelope["plan_id"], "worker", 60) is not None
    remote.mark_running(envelope["plan_id"], "worker")
    remote.fail_retryable(envelope["plan_id"], "worker", "synthetic failure")

    def runner(command, *, input, **_kwargs):
        status, response = handle_command(
            command[-1],
            ledger=remote,
            stdin=io.BytesIO(input or b""),
            wake=lambda: {"ok": True, "service": "test"},
        )
        return subprocess.CompletedProcess(
            command,
            status,
            stdout=json.dumps(response).encode(),
            stderr=b"",
        )

    SshControlTransport(local, runner=runner).sync(envelope["plan_id"])

    receipt = local.receipt(envelope["plan_id"])
    assert receipt["status"] == "dead_letter"
    assert receipt["attempt_count"] == 1
    assert receipt["last_error"] == "synthetic failure"
    assert local.report(envelope["plan_id"]) is None


def test_transport_rejects_conflicting_remote_plan(tmp_path: Path) -> None:
    local = ControlLedger(tmp_path / "local")
    envelope = plan(local)

    def runner(command, **_kwargs):
        conflicting = dict(envelope)
        conflicting["created_by"] = "attacker"
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "ok": True,
                    "plan": conflicting,
                    "receipt": None,
                    "report": None,
                }
            ).encode(),
            stderr=b"",
        )

    with pytest.raises(LedgerError, match="differs"):
        SshControlTransport(local, runner=runner).sync(envelope["plan_id"])
