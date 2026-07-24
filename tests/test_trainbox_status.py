from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lab.backend.config import LabConfig
from lab.backend.trainbox.status import TrainboxStatusService


REPO_ROOT = Path(__file__).resolve().parents[1]


def make_config(tmp_path: Path) -> LabConfig:
    lab_root = tmp_path / "lab"
    return LabConfig(
        repo_root=tmp_path,
        lab_root=lab_root,
        frontend_root=REPO_ROOT / "lab/frontend",
        state_dir=lab_root / "state",
        messages_dir=lab_root / "messages",
        published_dir=lab_root / "published",
        scan_roots=("training/logs",),
        serve_roots=("training/logs",),
        git_pull_interval_seconds=3600,
        git_pull_enabled=False,
        git_pull_allow_dirty=False,
        git_expected_branch="main",
        git_expected_remote="origin",
        orchestrator_url=None,
        orchestrator_api_key=None,
        auth_password="test-password",
        auth_secret="test-secret",
        auth_cookie_secure=False,
        max_request_body_bytes=256,
        trusted_origins=(),
        trainbox_ssh_target="ninereeds-trainbox-status",
        trainbox_status_timeout_seconds=1,
        trainbox_status_cache_seconds=5,
        trainbox_status_stale_seconds=180,
        trainbox_control_ssh_target="ninereeds-trainbox-control",
        orchestrator_control_root=tmp_path / "control",
        control_status_timeout_seconds=1,
        control_status_cache_seconds=5,
        message_codex_executable="/home/aomukai/.local/bin/codex",
        message_codex_model="gpt-5.6-sol",
        message_codex_timeout_seconds=30,
        message_lease_seconds=60,
        message_max_attempts=3,
    )


def status_document(generated_at: str) -> dict:
    return {
        "schema_version": "ninereeds_trainbox_status_v1",
        "role": "trainbox",
        "generated_at": generated_at,
        "ok": True,
        "capabilities": {
            "read_only_status": True,
            "heartbeat_write": True,
            "training_dispatch": False,
            "plan_claiming": False,
        },
        "repo": {"ok": True, "clean": True, "head": "abc123"},
        "pipeline": {"ok": True, "next_safe_action": "run_phase_block"},
        "gpu": {"ok": True, "gpus": []},
        "services": {"ssh_socket_active": True},
        "system": {"uptime_seconds": 10},
    }


def completed(document: dict, *, returncode: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(
        args=["ssh"],
        returncode=returncode,
        stdout=json.dumps(document) if returncode == 0 else "",
        stderr=stderr,
    )


def test_trainbox_status_is_validated_and_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generated = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: completed(status_document(generated)),
    )
    result = TrainboxStatusService(make_config(tmp_path)).status(force=True)

    assert result["reachable"] is True
    assert result["ok"] is True
    assert result["stale"] is False
    assert result["status"]["capabilities"]["training_dispatch"] is False


def test_trainbox_status_marks_old_heartbeat_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generated = datetime.fromtimestamp(time.time() - 240, timezone.utc).isoformat()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: completed(status_document(generated)),
    )
    result = TrainboxStatusService(make_config(tmp_path)).status(force=True)

    assert result["reachable"] is True
    assert result["stale"] is True
    assert result["age_seconds"] >= 239


def test_trainbox_status_reports_unreachable_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: completed({}, returncode=255, stderr="connection refused"),
    )
    result = TrainboxStatusService(make_config(tmp_path)).status(force=True)

    assert result["reachable"] is False
    assert result["error"]["code"] == "unreachable"
    assert "connection refused" in result["error"]["message"]


def test_trainbox_status_rejects_expanded_authority(tmp_path: Path) -> None:
    document = status_document("2026-07-25T00:00:00Z")
    document["capabilities"]["training_dispatch"] = True
    error = TrainboxStatusService(make_config(tmp_path))._validate(document)
    assert error == "Trainbox status unexpectedly permits training dispatch."
