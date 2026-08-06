from __future__ import annotations

import http.client
import json
from pathlib import Path
import threading
from types import SimpleNamespace

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


def test_configuration_draft_accepts_browser_integer_for_decimal_zero(lab_api) -> None:
    port, _, bundle = lab_api
    cookie, csrf = setup_session(port)
    draft = settings_payload(bundle)
    # JSON.stringify turns JavaScript's numeric 0.0 into the token `0`.
    draft["routes"][0]["max_cost_usd"] = 0
    status, _, raw = request(
        port, "POST", "/lab/api/settings/draft", payload=draft,
        headers={"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 201
    saved = json.loads(raw)["draft"]["payload"]
    assert saved["routes"][0]["max_cost_usd"] == 0.0


def test_configuration_draft_can_add_inert_custom_service_and_model(lab_api) -> None:
    port, store, bundle = lab_api
    cookie, csrf = setup_session(port)
    draft = settings_payload(bundle)
    draft["providers"].append({
        "id": "my-provider", "kind": "openai_compatible", "enabled": False,
        "endpoint": "https://models.example.invalid/v1/chat/completions",
        "credential_env": "MY_PROVIDER_API_KEY", "timeout_seconds": 3600,
        "max_attempts": 1, "concurrency": 1,
    })
    draft["models"].append({
        "id": "my-model", "provider": "my-provider", "exact_name": "model-v1",
        "enabled": False, "local": False, "context_tokens": 32000,
        "output_tokens": 4096, "structured_output": True, "runtime": "api",
        "weights": "", "device": "remote",
    })
    status, _, raw = request(
        port, "POST", "/lab/api/settings/draft", payload=draft,
        headers={"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 201
    saved = json.loads(raw)["draft"]["payload"]
    assert any(item["id"] == "my-provider" and not item["enabled"] for item in saved["providers"])
    assert any(item["id"] == "my-model" and not item["enabled"] for item in saved["models"])
    assert store.active_config()["sha256"] == bundle.sha256


def test_configuration_review_and_commissioning_request_are_explicit_and_inert(lab_api) -> None:
    port, store, bundle = lab_api
    cookie, csrf = setup_session(port)
    draft = settings_payload(bundle)
    campaign = next(item for item in draft["jobs"] if item["id"] == "campaign.decide")
    campaign["enabled"] = True
    status, _, raw = request(
        port, "POST", "/lab/api/settings/draft", payload=draft,
        headers={"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 201
    draft_id = json.loads(raw)["draft"]["id"]

    status, _, raw = request(port, "GET", "/lab/api/settings/review", headers={"Cookie": cookie})
    assert status == 200
    review = json.loads(raw)
    assert review["change_count"] == 1
    assert review["ready_for_activation"] is False
    assert {item["code"] for item in review["blockers"]} == {"job_handler_uncommissioned", "route_disabled"}
    pointers = {item["code"]: item["setting"] for item in review["blockers"]}
    assert pointers["job_handler_uncommissioned"] == {
        "section": "jobs", "id": "campaign.decide", "field": "enabled", "label": "Requested availability",
    }
    assert pointers["route_disabled"] == {
        "section": "routes", "id": "strategic-decision", "field": "enabled", "label": "Execution path available",
    }

    status, _, _ = request(
        port, "POST", "/lab/api/settings/commissioning-request",
        payload={"draft_id": draft_id, "acknowledgement": "wrong"},
        headers={"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 400
    request_payload = {"draft_id": draft_id, "acknowledgement": "reviewed_not_activated"}
    status, _, raw = request(
        port, "POST", "/lab/api/settings/commissioning-request", payload=request_payload,
        headers={"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 201
    thread_id = json.loads(raw)["thread"]["thread"]["id"]
    assert json.loads(raw)["thread"]["messages"][1]["sender"] == "mission_hub"
    status, _, raw = request(port, "GET", "/lab/api/threads", headers={"Cookie": cookie})
    assert status == 200 and json.loads(raw)["unread_count"] == 1

    status, _, raw = request(
        port, "POST", "/lab/api/settings/commissioning-request", payload=request_payload,
        headers={"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"},
    )
    assert status == 201 and json.loads(raw)["thread"]["thread"]["id"] == thread_id
    assert store.active_config()["sha256"] == bundle.sha256


def test_codex_catalog_exposes_only_safe_selectable_model_metadata(lab_api, monkeypatch) -> None:
    port, _, _ = lab_api
    cookie, _ = setup_session(port)
    catalog = {
        "models": [
            {
                "slug": "gpt-visible", "display_name": "GPT Visible",
                "description": "Selectable model.", "visibility": "list",
                "context_window": 64000, "default_reasoning_level": "medium",
                "supported_reasoning_levels": [{"effort": "low"}, {"effort": "medium"}],
                "base_instructions": "must never reach the browser",
            },
            {"slug": "gpt-hidden", "display_name": "Hidden", "visibility": "hide"},
        ],
    }
    monkeypatch.setattr(
        "mission_hub.api.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(catalog), stderr=""),
    )
    status, _, raw = request(port, "GET", "/lab/api/codex/models", headers={"Cookie": cookie})
    assert status == 200
    result = json.loads(raw)
    assert result["available"] is True
    assert result["items"] == [{
        "id": "gpt-visible", "name": "GPT Visible", "description": "Selectable model.",
        "context_tokens": 64000, "reasoning_levels": ["low", "medium"],
        "default_reasoning_level": "medium",
    }]
    assert b"base_instructions" not in raw


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
