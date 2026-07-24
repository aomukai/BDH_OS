from __future__ import annotations

from pathlib import Path

from lab.backend.config import LabConfig


REPO_ROOT = Path(__file__).resolve().parents[1]


def make_lab_config(tmp_path: Path) -> LabConfig:
    lab_root = tmp_path / "lab"
    return LabConfig(
        repo_root=tmp_path,
        lab_root=lab_root,
        frontend_root=REPO_ROOT / "lab/frontend",
        state_dir=lab_root / "state",
        messages_dir=lab_root / "messages",
        published_dir=lab_root / "published",
        scan_roots=("training/logs", "lab/messages"),
        serve_roots=("training/logs", "lab/messages"),
        git_pull_interval_seconds=3600,
        git_pull_enabled=False,
        git_pull_allow_dirty=False,
        git_expected_branch="main",
        git_expected_remote="origin",
        orchestrator_url=None,
        orchestrator_api_key=None,
        auth_password="correct horse battery staple",
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
