"""Minimal authenticated Mission Hub JSON API for future clients."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
import secrets
from typing import Any

from .config import ConfigBundle
from .errors import MissionHubError, NotFoundError
from .store import MissionHubStore


QUERY_ENTITIES = {
    "config-snapshots": "config_snapshots",
    "machines": "machines",
    "deployments": "deployments",
    "campaigns": "campaigns",
    "decisions": "decisions",
    "jobs": "jobs",
    "runs": "runs",
    "artifacts": "artifacts",
    "evidence-sources": "evidence_sources",
    "events": "events",
}


class _ResponseSent(Exception):
    pass


class MissionHubAPI:
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store = store
        self.bundle = bundle
        token_env = bundle.base["api"]["auth_token_env"]
        self.token = os.environ.get(token_env, "")
        if not self.token:
            raise RuntimeError(f"API token environment variable is required: {token_env}")

    def server(self) -> ThreadingHTTPServer:
        application = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "NinereedsMissionHub/1"

            def do_GET(self) -> None:
                application._handle(self, "GET")

            def do_POST(self) -> None:
                application._handle(self, "POST")

            def log_message(self, format: str, *args: Any) -> None:
                return

        api = self.bundle.base["api"]
        return ThreadingHTTPServer((api["host"], api["port"]), Handler)

    def _handle(self, request: BaseHTTPRequestHandler, method: str) -> None:
        try:
            if request.path == "/v1/health" and method == "GET":
                self._send(request, HTTPStatus.OK, {"ok": True, "service": "mission-hub"})
                return
            self._authorize(request)
            path = request.path.split("?", 1)[0]
            if method == "GET" and path == "/v1/status":
                self._send(request, HTTPStatus.OK, {"config": self.store.active_config(), "integrity": self.store.integrity_report()})
                return
            if method == "GET" and path.startswith("/v1/"):
                entity = QUERY_ENTITIES.get(path.removeprefix("/v1/"))
                if entity:
                    self._send(request, HTTPStatus.OK, {"items": self.store.list_rows(entity)})
                    return
            if method == "POST" and path == "/v1/jobs":
                body = self._body(request)
                row = self.store.create_job(
                    self.bundle,
                    job_type=body["job_type"],
                    input_payload=body["input"],
                    idempotency_key=body["idempotency_key"],
                    created_by="mission-hub-api",
                    campaign_id=body.get("campaign_id"),
                    requested_machine_id=body.get("machine_id"),
                )
                self._send(request, HTTPStatus.CREATED, row)
                return
            match = re.fullmatch(r"/v1/jobs/([^/]+)/(approve|cancel)", path)
            if method == "POST" and match:
                body = self._body(request)
                job_id, action = match.groups()
                actor = "mission-hub-api"
                if action == "approve":
                    self.store.approve_job(job_id, actor=actor)
                else:
                    self.store.cancel_job(job_id, reason=body["reason"], actor=actor)
                self._send(request, HTTPStatus.OK, {"job_id": job_id, "action": action})
                return
            self._send(request, HTTPStatus.NOT_FOUND, {"error": "not_found"})
        except _ResponseSent:
            return
        except NotFoundError as exc:
            self._send(request, HTTPStatus.NOT_FOUND, {"error": type(exc).__name__, "message": str(exc)})
        except (MissionHubError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._send(request, HTTPStatus.BAD_REQUEST, {"error": type(exc).__name__, "message": str(exc)})

    def _authorize(self, request: BaseHTTPRequestHandler) -> None:
        supplied = request.headers.get("Authorization", "")
        expected = f"Bearer {self.token}"
        if not secrets.compare_digest(supplied, expected):
            self._send(request, HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            raise _ResponseSent

    def _body(self, request: BaseHTTPRequestHandler) -> dict[str, Any]:
        length = int(request.headers.get("Content-Length", "0"))
        limit = self.bundle.base["api"]["max_request_bytes"]
        if length < 1 or length > limit:
            raise ValueError("invalid request body size")
        parsed = json.loads(request.rfile.read(length))
        if not isinstance(parsed, dict):
            raise ValueError("request body must be a JSON object")
        return parsed

    @staticmethod
    def _send(request: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        request.send_response(status)
        request.send_header("Content-Type", "application/json; charset=utf-8")
        request.send_header("Content-Length", str(len(encoded)))
        request.send_header("Cache-Control", "no-store")
        request.end_headers()
        request.wfile.write(encoded)


def serve(store: MissionHubStore, bundle: ConfigBundle) -> None:
    server = MissionHubAPI(store, bundle).server()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
