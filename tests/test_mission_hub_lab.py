from __future__ import annotations

import http.client
import json
from pathlib import Path
import threading

import pytest

from mission_hub.api import MissionHubAPI
from mission_hub.config import load_config_bundle
from mission_hub.jsonutil import canonical_json
from mission_hub.lab import LabStore, settings_payload
from mission_hub.store import MissionHubStore, utc_now


REPO = Path(__file__).resolve().parents[1]


def request(port: int, method: str, path: str, *, payload=None, headers=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    supplied = dict(headers or {})
    if body is not None:
        supplied.update({"Content-Type": "application/json", "Content-Length": str(len(body))})
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    connection.request(method, path, body=body, headers=supplied)
    response = connection.getresponse()
    raw = response.read()
    result = response.status, {key.lower(): value for key, value in response.getheaders()}, raw
    connection.close()
    return result


@pytest.fixture
def lab_api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("NINEREEDS_MISSION_HUB_API_TOKEN", "internal-token")
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.base["api"]["port"] = 0
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    server = MissionHubAPI(store, bundle).server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port, store, bundle
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def setup_session(port: int):
    status, _, raw = request(port, "GET", "/lab/api/bootstrap")
    assert status == 200 and json.loads(raw)["setup_required"] is True
    status, headers, raw = request(
        port,
        "POST",
        "/lab/api/setup",
        payload={"username": "andi", "password": "correct horse battery staple"},
        headers={"Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 200
    cookie = headers["set-cookie"].split(";", 1)[0]
    session = json.loads(raw)["session"]
    return cookie, session["csrf_token"]


def test_lab_setup_session_static_security_and_csrf(lab_api) -> None:
    port, _, _ = lab_api
    status, headers, _ = request(port, "GET", "/")
    assert status == 303 and headers["location"] == "/login"
    status, headers, raw = request(port, "GET", "/login")
    assert status == 200 and b"The Lab" in raw
    assert "unsafe-inline" not in headers["content-security-policy"]

    cookie, csrf = setup_session(port)
    status, _, raw = request(port, "GET", "/", headers={"Cookie": cookie})
    assert status == 200 and b"Operational threads" in raw
    status, _, _ = request(
        port, "POST", "/lab/api/threads",
        payload={"subject": "No token", "body": "must fail"},
        headers={"Cookie": cookie, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 403
    status, _, raw = request(
        port, "POST", "/lab/api/threads",
        payload={"subject": "Commissioning", "body": "The first durable thread."},
        headers={"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 201
    assert json.loads(raw)["thread"]["subject"] == "Commissioning"


def test_threads_unread_and_configuration_draft(lab_api) -> None:
    port, store, bundle = lab_api
    cookie, csrf = setup_session(port)
    lab = LabStore(store)
    thread_id = lab.system_notice("Critical job", "Sol advisory is ready.", sender="sol")
    status, _, raw = request(port, "GET", "/lab/api/threads", headers={"Cookie": cookie})
    assert status == 200 and json.loads(raw)["unread_count"] == 1
    status, _, raw = request(port, "GET", f"/lab/api/threads/{thread_id}", headers={"Cookie": cookie})
    assert status == 200 and json.loads(raw)["messages"][0]["sender"] == "sol"
    status, _, raw = request(port, "GET", "/lab/api/threads", headers={"Cookie": cookie})
    assert json.loads(raw)["unread_count"] == 0

    draft = settings_payload(bundle)
    draft["providers"][0]["endpoint"] = "https://example.invalid/v1/chat/completions"
    status, _, raw = request(
        port, "POST", "/lab/api/settings/draft", payload=draft,
        headers={"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 201
    saved = json.loads(raw)["draft"]
    assert saved["state"] == "draft"
    assert saved["base_config_sha256"] == bundle.sha256
    assert store.active_config()["sha256"] == bundle.sha256


def test_checkpoint_chat_is_pinned_and_invocation_is_truthfully_blocked(lab_api) -> None:
    port, store, _ = lab_api
    cookie, csrf = setup_session(port)
    now = utc_now()
    digest = "a" * 64
    artifact_id = "art-certified-chat"
    manifest = {
        "schema_version": "ninereeds_checkpoint_certification_v1",
        "lineage_label": "play-branch-2",
        "certification_scope": "byte_identity_only",
        "compatibility_certified": False,
    }
    with store.transaction() as db:
        db.execute(
            "INSERT INTO artifacts(id,kind,sha256,byte_size,lifecycle,manifest_json,created_at) VALUES(?,'checkpoint',?,123,'candidate',?,?)",
            (artifact_id, digest, canonical_json(manifest), now),
        )
        db.execute(
            "INSERT INTO artifact_locations(artifact_id,machine_id,uri,observed_at,available) VALUES(?,'trainbox','/home/aomukai/Ninereeds/checkpoints/branch2.pt',?,1)",
            (artifact_id, now),
        )
    status, _, raw = request(
        port, "POST", "/lab/api/chats",
        payload={"checkpoint_artifact_id": artifact_id, "title": "Branch two"},
        headers={"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 201
    chat = json.loads(raw)
    assert chat["thread"]["checkpoint_sha256"] == digest
    chat_id = chat["thread"]["id"]
    status, _, raw = request(
        port, "POST", f"/lab/api/chats/{chat_id}/messages",
        payload={"body": "Can you play with me?"},
        headers={"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 201
    invocation = json.loads(raw)["invocations"][0]
    assert invocation["status"] == "blocked"
    assert invocation["checkpoint_sha256"] == digest
    assert invocation["failure"]["code"] == "inference_not_commissioned"
