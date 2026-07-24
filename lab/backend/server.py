from __future__ import annotations

import argparse
import json
import mimetypes
import queue
import re
import secrets
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from lab.backend.auth.service import AuthService
from lab.backend.artifacts.indexer import ArtifactIndex
from lab.backend.chat.service import ChatService
from lab.backend.config import LabConfig
from lab.backend.git.service import GitService
from lab.backend.messages.store import MessageStore
from lab.backend.notifications.hub import EventHub
from lab.backend.orchestrator.client import OrchestratorClient
from lab.backend.trainbox.status import TrainboxStatusService


class LabRuntime:
    def __init__(self, config: LabConfig) -> None:
        self.config = config
        self.index = ArtifactIndex(config)
        self.git = GitService(config)
        self.auth = AuthService(config)
        self.messages = MessageStore(config)
        self.hub = EventHub()
        self.chat = ChatService(config, self.index)
        self.orchestrator = OrchestratorClient(config, self.index)
        self.trainbox = TrainboxStatusService(config)
        self.sessions: dict[str, float] = {}
        self.login_failures: dict[str, list[float]] = {}
        self.login_lock = threading.Lock()
        self._stop = threading.Event()

    def start(self) -> None:
        self.config.ensure_dirs()
        self.scan_and_notify("startup")
        thread = threading.Thread(target=self._background_loop, name="lab-sync", daemon=True)
        thread.start()

    def stop(self) -> None:
        self._stop.set()

    def scan_and_notify(self, reason: str) -> dict[str, Any]:
        result = self.index.scan()
        if result["new_artifact_ids"]:
            self.hub.publish("artifacts_indexed", {"reason": reason, **result})
        return result

    def _background_loop(self) -> None:
        while not self._stop.wait(self.config.git_pull_interval_seconds):
            pull_result = None
            if self.config.git_pull_enabled:
                pull_result = self.git.pull(reason="scheduled")
                self.hub.publish("git_pull", pull_result)
            scan_result = self.scan_and_notify("scheduled")
            self.hub.publish("scan_complete", {"pull": pull_result, "scan": scan_result})


class LabHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], handler: type[BaseHTTPRequestHandler], runtime: LabRuntime):
        super().__init__(server_address, handler)
        self.runtime = runtime


class LabHandler(BaseHTTPRequestHandler):
    server_version = "TheLab/0.1"

    @property
    def runtime(self) -> LabRuntime:
        return self.server.runtime  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if not self._allow_request(path):
            self._reject_or_login(path)
            return
        if path == "/login":
            self._redirect("/")
            return
        if path == "/ws" and self.headers.get("Upgrade", "").lower() == "websocket":
            self._handle_websocket()
            return
        if path == "/api/events":
            self._handle_sse()
            return
        if path.startswith("/api/"):
            self._handle_api_get(path, parse_qs(parsed.query))
            return
        if path.startswith("/repo/"):
            self._serve_repo_file(unquote(path.removeprefix("/repo/")))
            return
        self._serve_frontend(path)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if not self._allow_request(path):
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.end_headers()
            return
        if path.startswith("/repo/"):
            self._serve_repo_file(unquote(path.removeprefix("/repo/")), head_only=True)
            return
        self._serve_frontend(path, head_only=True)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not self._origin_allowed():
            self._send_json({"error": "untrusted request origin"}, HTTPStatus.FORBIDDEN)
            return
        if parsed.path == "/api/login":
            self._handle_login()
            return
        if parsed.path == "/api/logout":
            self._handle_logout()
            return
        if not self._allow_request(parsed.path):
            self._send_json({"error": "authentication required"}, HTTPStatus.UNAUTHORIZED)
            return
        if not parsed.path.startswith("/api/"):
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        self._handle_api_post(parsed.path)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[lab] {self.address_string()} {fmt % args}")

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'none'; object-src 'none'; "
            "frame-ancestors 'self'; frame-src 'self'; "
            "img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self' ws: wss:; form-action 'self'",
        )
        super().end_headers()

    def _allow_request(self, path: str) -> bool:
        if not self.runtime.auth.enabled():
            return True
        public_paths = {"/login", "/login.js", "/styles.css", "/manifest.webmanifest"}
        if path in public_paths or path.startswith("/icons/"):
            return True
        return self._authenticated()

    def _authenticated(self) -> bool:
        cookie = self.headers.get("Cookie", "")
        token = None
        for part in cookie.split(";"):
            key, _, value = part.strip().partition("=")
            if key == "lab_session":
                token = value
                break
        if not token:
            return False
        expiry = self.runtime.sessions.get(token)
        if not expiry or expiry < time.time():
            self.runtime.sessions.pop(token, None)
            return False
        return True

    def _handle_login(self) -> None:
        if self._login_is_throttled():
            self._send_json(
                {"ok": False, "error": "too many login attempts; try again later"},
                HTTPStatus.TOO_MANY_REQUESTS,
                headers={"Retry-After": "300"},
            )
            return
        try:
            body = self._read_json()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        expected = self.runtime.config.auth_password
        password = str(body.get("password") or "")
        if not expected and not self.runtime.auth.enabled():
            self._send_json({"ok": False, "error": "password is not configured"}, HTTPStatus.UNAUTHORIZED)
            return
        if not self.runtime.auth.verify(password):
            self._record_login_failure()
            self._send_json({"ok": False, "error": "invalid password"}, HTTPStatus.UNAUTHORIZED)
            return
        self._clear_login_failures()
        token = secrets.token_urlsafe(32)
        self.runtime.sessions[token] = time.time() + 60 * 60 * 24 * 30
        secure = "; Secure" if self.runtime.config.auth_cookie_secure else ""
        self._send_json(
            {"ok": True},
            headers={
                "Set-Cookie": (
                    f"lab_session={token}; Path=/; Max-Age={60 * 60 * 24 * 30}; "
                    f"HttpOnly; SameSite=Lax{secure}"
                )
            },
        )

    def _handle_logout(self) -> None:
        cookie = self.headers.get("Cookie", "")
        for part in cookie.split(";"):
            key, _, value = part.strip().partition("=")
            if key == "lab_session":
                self.runtime.sessions.pop(value, None)
        self._send_json(
            {"ok": True},
            headers={"Set-Cookie": "lab_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"},
        )

    def _handle_api_get(self, path: str, query: dict[str, list[str]]) -> None:
        index = self.runtime.index
        if path == "/api/status":
            self._send_json(
                {
                    "name": "The Lab",
                    "time": time.time(),
                    "git": self.runtime.git.status(),
                    "dashboard": index.dashboard(self.runtime.chat.current_build()),
                }
            )
            return
        if path == "/api/trainbox/status":
            force = self._first(query, "refresh") == "1"
            self._send_json({"trainbox": self.runtime.trainbox.status(force=force)})
            return
        if path == "/api/artifacts":
            artifact_type = self._first(query, "type")
            artifacts = [artifact.to_dict() for artifact in index.all_artifacts()]
            if artifact_type:
                artifacts = [artifact for artifact in artifacts if artifact["type"] == artifact_type]
            self._send_json({"artifacts": artifacts})
            return
        artifact_match = re.fullmatch(r"/api/artifacts/([0-9a-f]+)(/content)?", path)
        if artifact_match:
            artifact = index.get_artifact(artifact_match.group(1))
            if artifact is None:
                self._send_json({"error": "artifact not found"}, HTTPStatus.NOT_FOUND)
                return
            if artifact_match.group(2):
                self._serve_repo_file(artifact.path, forced_type=artifact.media_type)
            else:
                self._send_json({"artifact": artifact.to_dict()})
            return
        if path == "/api/campaigns":
            self._send_json({"campaigns": [campaign.to_dict() for campaign in index.campaigns()]})
            return
        campaign_match = re.fullmatch(r"/api/campaigns/([^/]+)", path)
        if campaign_match:
            campaign = index.get_campaign(unquote(campaign_match.group(1)).lower())
            if campaign is None:
                self._send_json({"error": "campaign not found"}, HTTPStatus.NOT_FOUND)
            else:
                self._send_json({"campaign": campaign.to_dict()})
            return
        if path == "/api/timeline":
            limit = int(self._first(query, "limit") or "300")
            self._send_json({"events": [event.to_dict() for event in index.timeline(limit=limit)]})
            return
        if path == "/api/search":
            self._send_json({"results": index.search(self._first(query, "q") or "")})
            return
        if path == "/api/messages":
            box = self._first(query, "box") or "inbox"
            try:
                messages = self.runtime.messages.list_messages(box)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json({"messages": [message.to_dict() for message in messages]})
            return
        if path == "/api/builds":
            self._send_json({"current": self.runtime.chat.current_build(), "builds": self.runtime.chat.builds()})
            return
        if path == "/api/auth/status":
            self._send_json({"auth": self.runtime.auth.status()})
            return
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _handle_api_post(self, path: str) -> None:
        try:
            body = self._read_json()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if path == "/api/auth/password":
            if self.runtime.auth.enabled() and not self._authenticated():
                self._send_json({"error": "authentication required"}, HTTPStatus.UNAUTHORIZED)
                return
            if not self.runtime.auth.enabled() and not self._client_is_local():
                self._send_json({"error": "initial password setup must be done from localhost"}, HTTPStatus.FORBIDDEN)
                return
            try:
                status = self.runtime.auth.set_password(str(body.get("password") or ""))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            token = secrets.token_urlsafe(32)
            self.runtime.sessions[token] = time.time() + 60 * 60 * 24 * 30
            secure = "; Secure" if self.runtime.config.auth_cookie_secure else ""
            self._send_json(
                {"auth": status},
                headers={
                    "Set-Cookie": (
                        f"lab_session={token}; Path=/; Max-Age={60 * 60 * 24 * 30}; "
                        f"HttpOnly; SameSite=Lax{secure}"
                    )
                },
            )
            return
        if path == "/api/git/pull":
            result = self.runtime.git.pull(reason="manual")
            scan = self.runtime.scan_and_notify("manual-pull")
            self.runtime.hub.publish("git_pull", result)
            self._send_json({"pull": result, "scan": scan})
            return
        if path == "/api/messages/outbox":
            title = str(body.get("title") or "Message")
            content = str(body.get("body") or "")
            message = self.runtime.messages.write_outbox(title, content)
            self.runtime.scan_and_notify("message-outbox")
            self.runtime.hub.publish("message_outbox", message.to_dict())
            self._send_json({"message": message.to_dict()}, HTTPStatus.CREATED)
            return
        if path == "/api/builds/publish":
            try:
                build = self.runtime.chat.publish(
                    str(body.get("checkpoint_artifact_id") or ""),
                    label=body.get("label") if isinstance(body.get("label"), str) else None,
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self.runtime.hub.publish("build_published", build)
            self._send_json({"build": build})
            return
        if path == "/api/chat/ninereeds":
            self._send_json(self.runtime.chat.chat_ninereeds(str(body.get("prompt") or "")))
            return
        if path == "/api/chat/orchestrator":
            self._send_json(self.runtime.orchestrator.chat(str(body.get("prompt") or "")))
            return
        self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def _handle_sse(self) -> None:
        client = self.runtime.hub.add_sse()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            self.wfile.write(b": connected\n\n")
            self.wfile.flush()
            while True:
                try:
                    event = client.get(timeout=20)
                    payload = json.dumps(event)
                    self.wfile.write(f"event: {event['type']}\ndata: {payload}\n\n".encode("utf-8"))
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.runtime.hub.remove_sse(client)

    def _handle_websocket(self) -> None:
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self._send_json({"error": "missing websocket key"}, HTTPStatus.BAD_REQUEST)
            return
        accept = self.runtime.hub.websocket_accept(key)
        self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        sock = self.request
        sock.settimeout(30)
        self.runtime.hub.add_ws(sock)
        self.runtime.hub.publish("websocket_connected", {"time": time.time()})
        try:
            while True:
                data = sock.recv(1024)
                if not data:
                    break
        except OSError:
            pass
        finally:
            self.runtime.hub.remove_ws(sock)

    def _serve_frontend(self, path: str, head_only: bool = False) -> None:
        if path in {"", "/"}:
            relative = "index.html"
        else:
            relative = unquote(path.lstrip("/"))
        try:
            candidate = (self.runtime.config.frontend_root / relative).resolve()
            root = self.runtime.config.frontend_root.resolve()
            if candidate != root and root not in candidate.parents:
                raise ValueError
            if not candidate.exists() or candidate.is_dir():
                candidate = root / "index.html"
        except ValueError:
            self._send_json({"error": "invalid path"}, HTTPStatus.BAD_REQUEST)
            return
        self._send_file(candidate, head_only=head_only)

    def _serve_login(self) -> None:
        self._send_file(self.runtime.config.frontend_root / "login.html")

    def _reject_or_login(self, path: str) -> None:
        if path.startswith("/api/") or path.startswith("/repo/") or path == "/ws":
            self._send_json({"error": "authentication required"}, HTTPStatus.UNAUTHORIZED)
            return
        self._serve_login()

    def _serve_repo_file(self, relative_path: str, forced_type: str | None = None, head_only: bool = False) -> None:
        try:
            path = self.runtime.config.resolve_repo_path(relative_path)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        if not path.exists() or not path.is_file():
            self._send_json({"error": "file not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_file(path, forced_type=forced_type, head_only=head_only)

    def _send_file(self, path: Path, forced_type: str | None = None, head_only: bool = False) -> None:
        content_type = forced_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            size = path.stat().st_size
            data = b"" if head_only else path.read_bytes()
        except OSError:
            self._send_json({"error": "could not read file"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        if path.name in {"service-worker.js", "manifest.webmanifest"}:
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def _send_json(
        self,
        data: Any,
        status: HTTPStatus = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        payload = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length > self.runtime.config.max_request_body_bytes:
            raise ValueError(
                f"request body exceeds {self.runtime.config.max_request_body_bytes} bytes"
            )
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("invalid JSON body") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _first(self, query: dict[str, list[str]], key: str) -> str | None:
        values = query.get(key)
        return values[0] if values else None

    def _client_is_local(self) -> bool:
        host = self.client_address[0]
        return host in {"127.0.0.1", "::1", "localhost"} or host.startswith("127.")

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        normalized = origin.rstrip("/")
        if normalized in self.runtime.config.trusted_origins:
            return True
        parsed = urlparse(normalized)
        return parsed.scheme in {"http", "https"} and parsed.netloc == self.headers.get("Host", "")

    def _login_is_throttled(self) -> bool:
        now = time.time()
        host = self.client_address[0]
        with self.runtime.login_lock:
            recent = [
                timestamp
                for timestamp in self.runtime.login_failures.get(host, [])
                if timestamp > now - 300
            ]
            self.runtime.login_failures[host] = recent
            return len(recent) >= 5

    def _record_login_failure(self) -> None:
        host = self.client_address[0]
        with self.runtime.login_lock:
            self.runtime.login_failures.setdefault(host, []).append(time.time())

    def _clear_login_failures(self) -> None:
        with self.runtime.login_lock:
            self.runtime.login_failures.pop(self.client_address[0], None)


def run(host: str, port: int) -> None:
    config = LabConfig.from_env()
    config.validate_bind(host)
    runtime = LabRuntime(config)
    server = LabHTTPServer((host, port), LabHandler, runtime)
    runtime.start()
    print(f"The Lab serving {config.repo_root} at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        runtime.stop()
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run The Lab web server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run(args.host, args.port)


if __name__ == "__main__":
    main()
