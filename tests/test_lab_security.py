from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path

import pytest

from lab.backend.config import LabConfig
from lab.backend.git.service import GitService
from lab.backend.messages.store import MessageStore
from lab.backend.server import LabHandler, LabHTTPServer, LabRuntime


REPO_ROOT = Path(__file__).resolve().parents[1]


def make_config(tmp_path: Path, *, password: str | None = "correct horse battery staple") -> LabConfig:
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
        auth_password=password,
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


def request(
    port: int,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    payload = response.read()
    result = response.status, {key.lower(): value for key, value in response.getheaders()}, payload
    connection.close()
    return result


@pytest.fixture
def lab_server(tmp_path: Path):
    config = make_config(tmp_path)
    config.ensure_dirs()
    report = tmp_path / "training/logs/report.md"
    report.parent.mkdir(parents=True)
    report.write_text("# Safe report\n", encoding="utf-8")
    (config.state_dir / "auth.json").write_text('{"secret": true}\n', encoding="utf-8")

    runtime = LabRuntime(config)
    runtime.start()
    server = LabHTTPServer(("127.0.0.1", 0), LabHandler, runtime)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1], config
    finally:
        server.shutdown()
        server.server_close()
        runtime.stop()
        thread.join(timeout=3)


def test_non_loopback_bind_requires_authentication(tmp_path: Path) -> None:
    config = make_config(tmp_path, password=None)
    config.validate_bind("127.0.0.1")
    with pytest.raises(RuntimeError, match="Refusing non-loopback"):
        config.validate_bind("0.0.0.0")

    config.ensure_dirs()
    (config.state_dir / "auth.json").write_text("{}\n", encoding="utf-8")
    config.validate_bind("0.0.0.0")


def test_repo_paths_are_limited_to_serve_roots(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    safe = tmp_path / "training/logs/report.md"
    safe.parent.mkdir(parents=True)
    safe.write_text("ok", encoding="utf-8")

    assert config.resolve_repo_path("training/logs/report.md") == safe
    with pytest.raises(ValueError, match="outside configured"):
        config.resolve_repo_path("lab/state/auth.json")
    with pytest.raises(ValueError, match="escapes repository"):
        config.resolve_repo_path("../outside")


def test_authenticated_api_security_boundaries(lab_server) -> None:
    port, _ = lab_server
    status, headers, _ = request(port, "GET", "/api/status")
    assert status == 401
    assert headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in headers["content-security-policy"]

    login_body = json.dumps({"password": "correct horse battery staple"}).encode()
    status, headers, _ = request(
        port,
        "POST",
        "/api/login",
        body=login_body,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(login_body)),
            "Origin": f"http://127.0.0.1:{port}",
        },
    )
    assert status == 200
    cookie = headers["set-cookie"].split(";", 1)[0]

    status, _, payload = request(
        port,
        "GET",
        "/repo/training/logs/report.md",
        headers={"Cookie": cookie},
    )
    assert status == 200
    assert payload == b"# Safe report\n"

    status, _, _ = request(
        port,
        "GET",
        "/repo/lab/state/auth.json",
        headers={"Cookie": cookie},
    )
    assert status == 400

    status, _, _ = request(
        port,
        "POST",
        "/api/git/pull",
        body=b"{}",
        headers={
            "Content-Type": "application/json",
            "Content-Length": "2",
            "Cookie": cookie,
            "Origin": "https://attacker.invalid",
        },
    )
    assert status == 403

    message_body = json.dumps({"title": "API test", "body": "hello worker"}).encode()
    status, _, payload = request(
        port,
        "POST",
        "/api/messages/outbox",
        body=message_body,
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(message_body)),
            "Cookie": cookie,
            "Origin": f"http://127.0.0.1:{port}",
        },
    )
    assert status == 201
    created = json.loads(payload)["message"]
    assert created["schema_version"] == "lab_message_v1"
    assert created["status"] == "queued"

    status, _, payload = request(
        port,
        "GET",
        f"/api/messages/{created['id']}/receipt",
        headers={"Cookie": cookie},
    )
    assert status == 200
    assert json.loads(payload)["receipt"]["status"] == "queued"


def test_login_throttling_and_body_limit(lab_server) -> None:
    port, _ = lab_server
    oversized = b"x" * 257
    status, _, _ = request(
        port,
        "POST",
        "/api/login",
        body=oversized,
        headers={"Content-Type": "application/json", "Content-Length": str(len(oversized))},
    )
    assert status == 400

    bad_body = json.dumps({"password": "wrong"}).encode()
    common = {"Content-Type": "application/json", "Content-Length": str(len(bad_body))}
    for _ in range(5):
        status, _, _ = request(port, "POST", "/api/login", body=bad_body, headers=common)
        assert status == 401
    status, headers, _ = request(port, "POST", "/api/login", body=bad_body, headers=common)
    assert status == 429
    assert headers["retry-after"] == "300"


def test_message_writes_are_atomic_and_collision_resistant(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.ensure_dirs()
    store = MessageStore(config)
    first = store.write_outbox("Same title", "one")
    second = store.write_outbox("Same title", "two")

    assert first.path != second.path
    assert not list((config.messages_dir / "outbox").glob(".*.tmp"))


def test_git_pull_rejects_unexpected_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    service = GitService(make_config(tmp_path))

    def fake_run(args: list[str], timeout: int):
        assert timeout > 0
        if args == ["git", "branch", "--show-current"]:
            return {"ok": True, "stdout": "experiment\n", "stderr": "", "returncode": 0}
        raise AssertionError(f"unexpected command: {args}")

    monkeypatch.setattr(service, "_run", fake_run)
    result = service.pull()
    assert result["skipped"] is True
    assert result["reason"] == "unexpected git branch"
    assert result["expected"] == "main"
