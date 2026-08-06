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
