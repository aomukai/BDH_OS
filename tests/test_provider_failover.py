from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from lab.backend.messages.store import MessageStore
from tests.helpers import make_lab_config
from training.pipeline.control.provider_failover import (
    BothProvidersLimitedError,
    ProviderMonitor,
    ProviderRouter,
    ProviderUnavailableError,
    RateLimitNotifier,
)


def limits(*, used: int = 10, reached: str | None = None) -> dict:
    snapshot = {
        "limitId": "codex",
        "limitName": None,
        "primary": {
            "usedPercent": used,
            "windowDurationMins": 10080,
            "resetsAt": 1785523802,
        },
        "secondary": None,
        "spendControlReached": False,
        "rateLimitReachedType": reached,
        "planType": "plus",
    }
    return {
        "rateLimits": snapshot,
        "rateLimitsByLimitId": {"codex": snapshot},
    }


def test_monitor_persists_structured_status_and_notifies_once(
    tmp_path: Path,
) -> None:
    config = make_lab_config(tmp_path)
    notifier = RateLimitNotifier(config.messages_dir)
    monitor = ProviderMonitor(
        tmp_path / "control/provider/status.json",
        reader=lambda: limits(used=100, reached="primary"),
        notifier=notifier,
    )

    first = monitor.refresh()
    second = monitor.refresh()

    assert first["codex"]["state"] == "limited"
    assert first["selected_provider"] == "fugu"
    assert second["codex"]["limit_event_id"] == first["codex"]["limit_event_id"]
    inbox = MessageStore(config).list_messages("inbox")
    assert len(inbox) == 1
    assert inbox[0].title == "Codex rate limit reached"
    assert "Fugu" in inbox[0].body


def test_router_uses_codex_when_available(tmp_path: Path) -> None:
    monitor = ProviderMonitor(
        tmp_path / "status.json",
        reader=lambda: limits(),
    )
    commands: list[list[str]] = []

    def run(command, **_kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    router = ProviderRouter(
        monitor,
        repo_root=tmp_path,
        command_runner=run,
    )
    result = router.run("prompt", tmp_path / "schema.json")

    assert result.provider == "codex"
    assert "--ignore-user-config" in commands[0]
    assert "/home/aomukai/.local/bin/codex-fugu" not in commands[0]


def test_router_uses_fugu_at_preobserved_codex_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAKANA_API_KEY", "configured-for-test")
    monitor = ProviderMonitor(
        tmp_path / "status.json",
        reader=lambda: limits(used=100, reached="primary"),
    )
    commands: list[list[str]] = []

    def run(command, **kwargs):
        commands.append(command)
        assert kwargs["env"]["CODEX_FUGU_NO_UPDATE"] == "1"
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"ok": True}),
            stderr="",
        )

    result = ProviderRouter(
        monitor,
        repo_root=tmp_path,
        command_runner=run,
    ).run("prompt", tmp_path / "schema.json")

    assert result.provider == "fugu"
    assert result.failover_reason == "codex_rate_limited"
    assert commands[0][:5] == [
        "/home/aomukai/.local/bin/codex-fugu",
        "--no-update",
        "--ask-for-approval",
        "never",
        "exec",
    ]


def test_router_fails_over_after_codex_429(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAKANA_API_KEY", "configured-for-test")
    monitor = ProviderMonitor(tmp_path / "status.json", reader=lambda: limits())
    calls = 0

    def run(command, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return subprocess.CompletedProcess(
                command, 1, stdout="", stderr="HTTP 429 rate limit reached"
            )
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps({"ok": True}), stderr=""
        )

    result = ProviderRouter(
        monitor,
        repo_root=tmp_path,
        command_runner=run,
    ).run("prompt", tmp_path / "schema.json")

    assert result.provider == "fugu"
    assert result.failover_reason == "codex_command_rate_limited"
    assert calls == 2


def test_router_reports_both_providers_limited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SAKANA_API_KEY", "configured-for-test")
    monitor = ProviderMonitor(
        tmp_path / "status.json",
        reader=lambda: limits(used=100, reached="primary"),
    )

    def run(command, **_kwargs):
        return subprocess.CompletedProcess(
            command, 1, stdout="", stderr="too many requests (429)"
        )

    router = ProviderRouter(
        monitor,
        repo_root=tmp_path,
        command_runner=run,
    )
    with pytest.raises(BothProvidersLimitedError):
        router.run("prompt", tmp_path / "schema.json")


def test_unknown_codex_status_does_not_guess(tmp_path: Path) -> None:
    def unavailable():
        raise ProviderUnavailableError("offline")

    monitor = ProviderMonitor(tmp_path / "status.json", reader=unavailable)
    router = ProviderRouter(monitor, repo_root=tmp_path)

    with pytest.raises(ProviderUnavailableError, match="refusing to guess"):
        router.run("prompt", tmp_path / "schema.json")
