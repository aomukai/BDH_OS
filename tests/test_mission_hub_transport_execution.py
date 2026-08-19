from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from mission_hub.agent_cli import _bounded_failed_run_evidence
from mission_hub.config import load_config_bundle
from mission_hub.errors import RemoteJobError
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


class ImmediateProcess:
    def __init__(self, args, response, returncode=2, **kwargs):
        del kwargs
        self.args = args
        self.response = response
        self.returncode = returncode

    def communicate(self, input=None, timeout=None):
        del input, timeout
        return (json.dumps(self.response), "")

    def terminate(self):
        pass

    def wait(self, timeout=None):
        del timeout
        return self.returncode

    def kill(self):
        pass


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


def test_remote_failure_evidence_is_verified_and_centralized(tmp_path: Path, monkeypatch) -> None:
    bundle = load_config_bundle(REPO / "config/mission_hub")
    bundle.machines["mission-hub"]["state_root"] = str(tmp_path / "hub-state")
    payload = b'{"schema_version":"ninereeds_failed_run_evidence_v1","files":[]}\n'
    digest = hashlib.sha256(payload).hexdigest()
    response = {
        "ok": False,
        "error": "RemoteJobError",
        "message": "provider unavailable",
        "failure_class": "capability_transient",
        "failure_code": "provider_capability_unavailable",
        "failure_evidence": {
            "kind": "failed_output_evidence",
            "sha256": digest,
            "byte_size": len(payload),
            "payload_base64": base64.b64encode(payload).decode("ascii"),
            "manifest": {"run_id": "run-remote-failure", "file_count": 0},
        },
    }
    monkeypatch.setattr(
        "mission_hub.transport.subprocess.Popen",
        lambda args, **kwargs: ImmediateProcess(args, response, **kwargs),
    )

    with pytest.raises(RemoteJobError) as raised:
        SSHDispatcher(bundle).execute("trainbox", {"job": {"type": "model.train"}})

    evidence = raised.value.evidence["remote_failure_evidence"]
    assert evidence["sha256"] == digest
    assert Path(evidence["uri"]).read_bytes() == payload
    assert Path(evidence["uri"]).is_relative_to(tmp_path / "hub-state")


def test_trainbox_failure_bundle_contains_exact_bounded_run_logs(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config/mission_hub")
    bundle.machines["trainbox"]["state_root"] = str(tmp_path / "trainbox-state")
    run_root = tmp_path / "trainbox-state" / "runs" / "run-evidence"
    run_root.mkdir(parents=True)
    (run_root / "visual-runtime-log.json").write_text('{"cause":"oom"}\n', encoding="utf-8")
    (run_root / "ignored.bin").write_bytes(b"not exported")

    declaration = _bounded_failed_run_evidence(
        bundle, "trainbox", {"job": {"id": "job-evidence"}, "run": {"id": "run-evidence"}},
    )

    assert declaration is not None
    decoded = json.loads(base64.b64decode(declaration["payload_base64"]))
    assert decoded["machine_id"] == "trainbox"
    assert decoded["job_id"] == "job-evidence"
    assert decoded["run_id"] == "run-evidence"
    assert [item["path"] for item in decoded["files"]] == ["visual-runtime-log.json"]
    assert base64.b64decode(decoded["files"][0]["content_base64"]) == b'{"cause":"oom"}\n'


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
