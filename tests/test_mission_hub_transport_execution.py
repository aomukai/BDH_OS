from __future__ import annotations

import json
from pathlib import Path
import subprocess

from mission_hub.config import load_config_bundle
from mission_hub.transport import SSHDispatcher


REPO = Path(__file__).resolve().parents[1]


class DelayedProcess:
    def __init__(self, args, **kwargs):
        del kwargs
        self.args = args
        self.returncode = None
        self.calls = 0
        self.terminated = False

    def communicate(self, input=None, timeout=None):
        self.calls += 1
        if self.calls == 1:
            assert input is not None
            raise subprocess.TimeoutExpired(self.args, timeout)
        assert input is None
        self.returncode = 0
        return ("\n" + json.dumps({"result": "complete"}) + "\n", "")

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        del timeout
        self.returncode = -15
        return self.returncode

    def kill(self):
        self.returncode = -9


def test_long_ssh_execution_heartbeats_and_accepts_whitespace_keepalives(monkeypatch) -> None:
    bundle = load_config_bundle(REPO / "config/mission_hub")
    created: list[DelayedProcess] = []

    def popen(args, **kwargs):
        process = DelayedProcess(args, **kwargs)
        created.append(process)
        return process

    monkeypatch.setattr("mission_hub.transport.subprocess.Popen", popen)
    heartbeats: list[bool] = []
    envelope = {"job": {"type": "model.train"}}

    result = SSHDispatcher(bundle).execute(
        "trainbox", envelope, heartbeat=lambda: heartbeats.append(True),
    )

    assert result == {"result": "complete"}
    assert heartbeats == [True]
    assert created[0].args[:4] == ["ssh", "-o", "ConnectTimeout=60", "--"]
    assert created[0].terminated is False


def test_remote_release_install_and_activation_require_exact_receipts(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    archive = tmp_path / "release.tar.gz"
    archive.write_bytes(b"bounded-release")
    deployment = {"id": "dep-repair", "release_id": "release-repair"}
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        if "release-install" in command:
            assert kwargs["stdin"].read() == b"bounded-release"
            body = {
                "ok": True, "installed": True, "idempotent": False,
                "deployment_id": deployment["id"], "release_id": deployment["release_id"],
                "config_sha256": bundle.sha256, "install_root": "/bounded/release",
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(body).encode(), b"")
        body = {
            "ok": True, "activated": True, "deployment_id": deployment["id"],
            "release_id": deployment["release_id"], "config_sha256": bundle.sha256,
            "active_release": "/bounded/release",
        }
        return subprocess.CompletedProcess(command, 0, json.dumps(body), "")

    dispatcher = SSHDispatcher(bundle, runner=runner)
    installed = dispatcher.install_release("trainbox", deployment, {
        "path": str(archive), "sha256": "a" * 64, "byte_size": archive.stat().st_size,
    })
    activated = dispatcher.activate_release("trainbox", deployment)

    assert installed["installed"] is True
    assert activated["activated"] is True
    assert calls[0][3:5] == ["release-install", "release-repair"]
    assert calls[1][3:5] == ["release-activate", "dep-repair"]
