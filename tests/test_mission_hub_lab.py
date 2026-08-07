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
from mission_hub.lab import LabStore, rebase_settings_payload, settings_payload
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
    status, _, _ = request(port, "GET", "/lab/observatory/view?artifact=art-0000000000000000&view=mri")
    assert status == 401

    cookie, csrf = setup_session(port)
    status, _, raw = request(port, "GET", "/", headers={"Cookie": cookie})
    assert status == 200 and b"Operational threads" in raw
    assert b"Model Observatory" in raw
    status, headers, raw = request(
        port, "GET", "/lab/observatory/view?artifact=art-0000000000000000&view=mri",
        headers={"Cookie": cookie},
    )
    assert status == 200 and b"Reading immutable evaluation evidence" in raw
    assert "unsafe-inline" not in headers["content-security-policy"]
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


def test_pipeline_start_and_pause_are_durable_safe_boundary_requests(lab_api) -> None:
    port, store, _ = lab_api
    cookie, csrf = setup_session(port)
    status, _, raw = request(port, "GET", "/lab/api/dashboard", headers={"Cookie": cookie})
    assert status == 200
    assert json.loads(raw)["pipeline"]["effective_state"] == "paused"

    headers = {"Cookie": cookie, "X-CSRF-Token": csrf, "Origin": f"http://127.0.0.1:{port}"}
    status, _, raw = request(port, "POST", "/lab/api/pipeline", payload={"desired_state": "running"}, headers=headers)
    assert status == 200
    assert json.loads(raw)["pipeline"]["effective_state"] == "starting"
    applied = store.apply_pipeline_state(actor="test-daemon")
    assert applied["effective_state"] == "running"

    status, _, raw = request(port, "POST", "/lab/api/pipeline", payload={"desired_state": "paused"}, headers=headers)
    assert status == 200
    assert json.loads(raw)["pipeline"]["effective_state"] == "paused"
    events = [row["event_type"] for row in store.list_rows("events")]
    assert "pipeline.running_requested" in events
    assert "pipeline.paused_requested" in events


def test_dashboard_exposes_next_scheduled_job(lab_api) -> None:
    port, store, bundle = lab_api
    cookie, _ = setup_session(port)
    job = store.create_job(
        bundle,
        job_type="system.healthcheck",
        input_payload={"include_gpu": True},
        idempotency_key="lab-next-job",
        created_by="test",
        requested_machine_id="trainbox",
        available_at="2099-01-02T03:04:05Z",
    )
    status, _, raw = request(port, "GET", "/lab/api/dashboard", headers={"Cookie": cookie})
    assert status == 200
    dashboard = json.loads(raw)
    assert dashboard["next_job"]["id"] == job["id"]
    assert dashboard["next_job"]["available_at"] == "2099-01-02T03:04:05Z"
    assert dashboard["current_job"] is None


def test_observatory_is_evidence_backed_and_empty_state_is_explicit(lab_api) -> None:
    port, _, _ = lab_api
    cookie, _ = setup_session(port)
    status, _, raw = request(port, "GET", "/lab/api/observatory", headers={"Cookie": cookie})
    assert status == 200
    observatory = json.loads(raw)
    assert observatory["active_campaign"] is None
    assert observatory["campaign_scan"] == {
        "required": 0,
        "complete": 0,
        "ready": False,
        "policy": "The terminal chat-and-MRI evaluation of every declared branch forms the campaign-completion scan. Loss remains telemetry only.",
    }
    assert observatory["statistics"]["things_taught"] == 0
    assert observatory["route_statistics"] == []


def test_cortex_progress_counts_training_and_evaluation_stages() -> None:
    workflow = {
        "id": "workflow-1",
        "status": "active",
        "specification": {"branch_id": "branch-3", "sessions": [{"id": "one"}, {"id": "two"}, {"id": "three"}]},
        "jobs": [
            {"stage_key": "s00:train", "status": "succeeded"},
            {"stage_key": "s00:evaluate", "status": "succeeded"},
            {"stage_key": "s01:train", "status": "running"},
        ],
    }
    progress = MissionHubAPI._cortex_progress(workflow)
    assert progress == {
        "workflow_id": "workflow-1", "workflow_status": "active", "branch_id": "branch-3",
        "block_index": 2, "blocks_total": 3,
        "completed_stages": 2, "total_stages": 6, "percent": 33,
        "stage": "training", "stage_status": "running",
    }


def test_completed_cortex_progress_remains_visible_at_one_hundred_percent() -> None:
    workflow = {
        "id": "workflow-complete",
        "status": "succeeded",
        "specification": {"branch_id": "branch-3", "sessions": [{"id": "one"}, {"id": "two"}]},
        "jobs": [
            {"stage_key": f"s{index:02d}:{stage}", "status": "succeeded"}
            for index in range(2) for stage in ("train", "evaluate")
        ],
    }
    progress = MissionHubAPI._cortex_progress(workflow)
    assert progress["workflow_status"] == "succeeded"
    assert progress["block_index"] == 2
    assert progress["percent"] == 100
    assert progress["stage"] == "complete"


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


def test_stale_draft_rebase_preserves_choices_and_adds_new_defaults(lab_api) -> None:
    _, _, bundle = lab_api
    stale = settings_payload(bundle)
    stale["base_config_sha256"] = "old"
    stale["jobs"] = [item for item in stale["jobs"] if not item["id"].startswith("visual.")]
    next(item for item in stale["jobs"] if item["id"] == "campaign.decide")["enabled"] = True
    stale.pop("orchestration")
    stale.pop("visual")
    stale.pop("budget")
    next(item for item in stale["jobs"] if item["id"] == "system.healthcheck")["prompt_id"] = "none"
    rebased = rebase_settings_payload(bundle, stale)
    assert rebased["base_config_sha256"] == bundle.sha256
    assert next(item for item in rebased["jobs"] if item["id"] == "campaign.decide")["enabled"] is True
    assert next(item for item in rebased["jobs"] if item["id"] == "visual.generate")["enabled"] is True
    assert rebased["visual"]["shadow_mode"] is True
    assert rebased["budget"]["external_calls_enabled"] is True
    assert next(item for item in rebased["jobs"] if item["id"] == "system.healthcheck")["prompt_id"] == "system-healthcheck-v1"


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
        "weights": "", "device": "remote", "modality": "text", "revision": "",
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


def test_checkpoint_chat_is_pinned_and_invocation_is_queued(lab_api) -> None:
    port, store, _ = lab_api
    cookie, csrf = setup_session(port)
    now = utc_now()
    digest = "a" * 64
    artifact_id = "art-a1b2c3d4e5f60718"
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
    assert invocation["status"] == "queued"
    assert invocation["checkpoint_sha256"] == digest
    assert invocation["failure"] is None
    assert invocation["job_id"]
    assert invocation["rendered_prompt"] == "Can you play with me?"
