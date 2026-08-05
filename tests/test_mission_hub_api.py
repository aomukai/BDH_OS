from __future__ import annotations

import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from mission_hub.api import MissionHubAPI
from mission_hub.config import load_config_bundle
from mission_hub.store import MissionHubStore


REPO = Path(__file__).resolve().parents[1]


def request(url: str, token: str | None = None, payload: dict | None = None):
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    if data is not None:
        headers["Content-Type"] = "application/json"
    return urlopen(Request(url, headers=headers, data=data), timeout=2)


def test_api_is_loopback_authenticated_and_readable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NINEREEDS_MISSION_HUB_API_TOKEN", "test-secret")
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.base["api"]["port"] = 0
    artifact_source = tmp_path / "allowed" / "commissioning.txt"
    artifact_source.parent.mkdir()
    artifact_source.write_text("api-artifact\n", encoding="utf-8")
    bundle.machines["mission-hub"]["state_root"] = str(tmp_path / "state")
    bundle.machines["mission-hub"]["artifact_roots"] = [str(artifact_source.parent)]
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    server = MissionHubAPI(store, bundle).server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with request(base + "/v1/health") as response:
            assert json.load(response) == {"ok": True, "service": "mission-hub"}
        try:
            request(base + "/v1/status")
        except HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("status endpoint accepted an unauthenticated request")
        with request(base + "/v1/status", "test-secret") as response:
            body = json.load(response)
            assert body["integrity"]["sqlite_integrity"] == "ok"
            assert body["config"]["sha256"] == bundle.sha256
        with request(
            base + "/v1/artifacts/ingest",
            "test-secret",
            {
                "kind": "commissioning_input",
                "source_path": str(artifact_source),
                "lifecycle": "observed",
                "manifest": {"source": "api-test"},
            },
        ) as response:
            artifact = json.load(response)
            assert response.status == 201
            assert artifact["kind"] == "commissioning_input"
            assert Path(artifact["uri"]).read_bytes() == artifact_source.read_bytes()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
