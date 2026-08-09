"""Minimal authenticated Mission Hub JSON API for future clients."""

from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import unquote

from .config import ConfigBundle, machine_id_for_role
from .errors import MissionHubError, NotFoundError
from .store import MissionHubStore
from .service import MissionHubService
from .lab import LabStore, SESSION_SECONDS, rebase_settings_payload
from .runtime_settings import bundle_with_settings, settings_payload
from .observatory import Observatory


QUERY_ENTITIES = {
    "config-snapshots": "config_snapshots",
    "machines": "machines",
    "deployments": "deployments",
    "campaigns": "campaigns",
    "decisions": "decisions",
    "jobs": "jobs",
    "recovery_incidents": "recovery_incidents",
    "recovery_attempts": "recovery_attempts",
    "recovery_actions": "recovery_actions",
    "campaign_blocks": "campaign_blocks",
    "runs": "runs",
    "artifacts": "artifacts",
    "evidence-sources": "evidence_sources",
    "events": "events",
    "knowledge-records": "knowledge_records",
    "training-session-plans": "training_session_plans",
    "cortex-workflows": "cortex_workflows",
    "cortex-workflow-jobs": "cortex_workflow_jobs",
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
        self.lab = LabStore(store, bundle)
        self.lab_assets = Path(__file__).resolve().parent / "lab_assets"
        self._login_failures: dict[str, list[float]] = {}

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
            if self._handle_lab(request, method):
                return
            if request.path == "/v1/health" and method == "GET":
                self._send(request, HTTPStatus.OK, {"ok": True, "service": "mission-hub"})
                return
            self._authorize(request)
            path = request.path.split("?", 1)[0]
            if method == "GET" and path == "/v1/status":
                with self.store._connect() as db:
                    recovery = {
                        "active_incidents": db.execute("SELECT COUNT(*) FROM recovery_incidents WHERE state NOT IN ('recovered','blocked','escalated')").fetchone()[0],
                        "blocked_incidents": db.execute("SELECT COUNT(*) FROM recovery_incidents WHERE state IN ('blocked','escalated')").fetchone()[0],
                        "active_campaign_blocks": db.execute("SELECT COUNT(*) FROM campaign_blocks WHERE state='active'").fetchone()[0],
                    }
                self._send(request, HTTPStatus.OK, {"config": self.store.active_config(), "integrity": self.store.integrity_report(), "recovery": recovery})
                return
            if method == "GET" and path.startswith("/v1/"):
                entity = QUERY_ENTITIES.get(path.removeprefix("/v1/"))
                if entity:
                    self._send(request, HTTPStatus.OK, {"items": self.store.list_rows(entity)})
                    return
            if method == "POST" and path == "/v1/jobs":
                body = self._body(request)
                runtime_bundle = self.lab.effective_bundle(self.bundle)
                row = self.store.create_job(
                    runtime_bundle,
                    job_type=body["job_type"],
                    input_payload=body["input"],
                    idempotency_key=body["idempotency_key"],
                    created_by="mission-hub-api",
                    campaign_id=body.get("campaign_id"),
                    requested_machine_id=body.get("machine_id"),
                )
                self._send(request, HTTPStatus.CREATED, row)
                return
            if method == "POST" and path == "/v1/cortex-workflows":
                body = self._body(request)
                row = self.store.create_cortex_workflow(
                    self.lab.effective_bundle(self.bundle), body["specification"], actor="mission-hub-api",
                )
                self._send(request, HTTPStatus.CREATED, row)
                return
            if method == "POST" and path == "/v1/artifacts/ingest":
                body = self._body(request)
                artifact = MissionHubService(self.store, self.bundle).ingest_artifact(
                    kind=body["kind"],
                    source_path=body["source_path"],
                    lifecycle=body.get("lifecycle", "observed"),
                    manifest=body.get("manifest", {}),
                    actor="mission-hub-api",
                )
                self._send(request, HTTPStatus.CREATED, artifact)
                return
            artifact_match = re.fullmatch(r"/v1/artifacts/(art-[0-9a-f]{16})/(materialize|retrieve)", path)
            if method == "POST" and artifact_match:
                body = self._body(request)
                artifact_id, action = artifact_match.groups()
                service = MissionHubService(self.store, self.bundle)
                if action == "materialize":
                    artifact = service.materialize_artifact(
                        artifact_id, machine_id=body["machine_id"], actor="mission-hub-api",
                    )
                else:
                    artifact = service.retrieve_artifact(
                        artifact_id, machine_id=body["machine_id"], actor="mission-hub-api",
                    )
                self._send(request, HTTPStatus.OK, artifact)
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

    def _handle_lab(self, request: BaseHTTPRequestHandler, method: str) -> bool:
        path = unquote(request.path.split("?", 1)[0])
        if method == "GET" and path in {"/lab.css", "/lab.js", "/login.js", "/manifest.webmanifest", "/scan.css", "/scan.js"}:
            self._static(request, path.removeprefix("/"))
            return True
        if method == "GET" and path in {"/", "/login"}:
            session = self._lab_session(request)
            if path == "/" and session is None:
                self._redirect(request, "/login")
            elif path == "/login" and session is not None:
                self._redirect(request, "/")
            else:
                self._static(request, "index.html" if path == "/" else "login.html")
            return True
        if not path.startswith("/lab/api/") and path != "/lab/observatory/view":
            return False

        if method == "GET" and path == "/lab/api/bootstrap":
            self._send(request, HTTPStatus.OK, {"setup_required": not self.lab.has_users()})
            return True
        if method == "POST" and path in {"/lab/api/setup", "/lab/api/login"}:
            self._check_origin(request)
            body = self._body(request)
            client = request.client_address[0]
            if self._login_throttled(client):
                self._send(request, HTTPStatus.TOO_MANY_REQUESTS, {"error": "login_throttled"}, extra_headers={"Retry-After": "300"})
                return True
            username = str(body.get("username", ""))
            password = str(body.get("password", ""))
            if path.endswith("setup"):
                user = self.lab.setup_user(username, password)
            else:
                user = self.lab.authenticate(username, password)
                if user is None:
                    self._record_login_failure(client)
                    self._send(request, HTTPStatus.UNAUTHORIZED, {"error": "invalid_credentials"})
                    return True
            self._login_failures.pop(client, None)
            token, session = self.lab.create_session(user["id"])
            self._send(
                request, HTTPStatus.OK, {"session": session},
                extra_headers={"Set-Cookie": self._session_cookie(request, token)},
            )
            return True

        session = self._require_lab_session(request)
        actor = f"lab:{session['username']}"
        if method == "POST":
            self._check_origin(request)
            if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), session["csrf_token"]):
                self._send(request, HTTPStatus.FORBIDDEN, {"error": "csrf_failed"})
                return True

        if method == "GET" and path == "/lab/api/session":
            self._send(request, HTTPStatus.OK, {"session": session, "setup_required": False})
            return True
        if method == "POST" and path == "/lab/api/logout":
            self.lab.end_session(self._session_token(request))
            self._send(
                request, HTTPStatus.OK, {"ok": True},
                extra_headers={"Set-Cookie": self._session_cookie(request, "", max_age=0)},
            )
            return True
        if method == "GET" and path == "/lab/api/dashboard":
            self._send(request, HTTPStatus.OK, self._dashboard())
            return True
        if method == "GET" and path == "/lab/api/observatory":
            self._send(request, HTTPStatus.OK, Observatory(self.store).summary())
            return True
        if method == "GET" and path == "/lab/api/retention":
            self._send(request, HTTPStatus.OK, self.store.retention_inventory(
                machine_id=machine_id_for_role(self.bundle, "trainbox"),
                roots=self.bundle.retention["build_roots"],
            ))
            return True
        protect_match = re.fullmatch(r"/lab/api/artifacts/(art-[0-9a-f]{16})/protect", path)
        if method == "POST" and protect_match:
            body = self._body(request)
            self._send(request, HTTPStatus.CREATED, self.store.protect_artifact(
                protect_match.group(1), protection_key="operator-pin",
                reason=str(body.get("reason", "Operator marked this checkpoint as a keeper.")),
                actor=actor, source="operator",
            ))
            return True
        release_match = re.fullmatch(r"/lab/api/artifact-protections/(protect-[0-9a-f]{16})/release", path)
        if method == "POST" and release_match:
            self._send(request, HTTPStatus.OK, self.store.release_artifact_protection(
                release_match.group(1), actor=actor,
            ))
            return True
        evaluation_match = re.fullmatch(r"/lab/api/observatory/evaluations/(art-[0-9a-f]{16})", path)
        if method == "GET" and evaluation_match:
            self._send(request, HTTPStatus.OK, Observatory(self.store).evaluation(evaluation_match.group(1)))
            return True
        if method == "GET" and path == "/lab/observatory/view":
            self._static(request, "scan.html")
            return True
        if method == "POST" and path == "/lab/api/pipeline":
            body = self._body(request)
            self._send(request, HTTPStatus.OK, {
                "pipeline": self.store.request_pipeline_state(str(body.get("desired_state", "")), actor=actor),
            })
            return True
        if method == "GET" and path == "/lab/api/cortex-workflows":
            self._send(request, HTTPStatus.OK, {"items": self.store.list_rows("cortex_workflows")})
            return True
        if method == "POST" and path == "/lab/api/cortex-workflows":
            body = self._body(request)
            self._send(
                request, HTTPStatus.CREATED,
                self.store.create_cortex_workflow(self.bundle, body["specification"], actor=actor),
            )
            return True
        if method == "GET" and path == "/lab/api/threads":
            self._send(request, HTTPStatus.OK, {"items": self.lab.list_threads(), "unread_count": self.lab.unread_count()})
            return True
        if method == "POST" and path == "/lab/api/threads":
            body = self._body(request)
            self._send(request, HTTPStatus.CREATED, self.lab.create_thread(body.get("subject"), body.get("body"), actor=actor))
            return True
        thread_match = re.fullmatch(r"/lab/api/threads/(thread-[0-9a-f-]+)(/messages)?", path)
        if thread_match and method == "GET" and thread_match.group(2) is None:
            self._send(request, HTTPStatus.OK, self.lab.thread(thread_match.group(1)))
            return True
        if thread_match and method == "POST" and thread_match.group(2):
            body = self._body(request)
            self._send(request, HTTPStatus.CREATED, {"message": self.lab.add_thread_message(thread_match.group(1), body.get("body"), sender="operator", actor=actor)})
            return True
        if method == "GET" and path == "/lab/api/checkpoints":
            self._send(request, HTTPStatus.OK, {"items": self.lab.checkpoints()})
            return True
        if method == "GET" and path == "/lab/api/chats":
            self._send(request, HTTPStatus.OK, {"items": self.lab.list_chats()})
            return True
        if method == "POST" and path == "/lab/api/chats":
            body = self._body(request)
            self._send(request, HTTPStatus.CREATED, self.lab.create_chat(body.get("checkpoint_artifact_id"), body.get("title"), actor=actor))
            return True
        chat_match = re.fullmatch(r"/lab/api/chats/(chat-[0-9a-f-]+)(/messages)?", path)
        if chat_match and method == "GET" and chat_match.group(2) is None:
            self._send(request, HTTPStatus.OK, self.lab.chat(chat_match.group(1)))
            return True
        if chat_match and method == "POST" and chat_match.group(2):
            body = self._body(request)
            self._send(request, HTTPStatus.CREATED, self.lab.add_chat_message(chat_match.group(1), body.get("body"), actor=actor))
            return True
        if method == "GET" and path == "/lab/api/settings":
            self._send(request, HTTPStatus.OK, {
                "active": self.lab.active_settings(self.bundle),
                "pending": self.lab.pending_settings(self.bundle),
                "activity": self.lab.settings_activity(),
            })
            return True
        if method == "GET" and path == "/lab/api/settings/review":
            self._send(request, HTTPStatus.OK, self.lab.review_draft(self.bundle))
            return True
        if method == "GET" and path == "/lab/api/codex/models":
            self._send(request, HTTPStatus.OK, self._codex_models())
            return True
        if method == "GET" and path == "/lab/api/providers/models":
            self._send(request, HTTPStatus.OK, self._provider_models())
            return True
        if method == "POST" and path == "/lab/api/settings/draft":
            payload = self._body(request)
            rebased = payload.get("base_config_sha256") != self.bundle.sha256
            if rebased:
                payload = rebase_settings_payload(self.bundle, payload)
            self._send(request, HTTPStatus.CREATED, {
                "draft": self.lab.save_draft(self.bundle, payload, actor=actor),
                "rebased": rebased,
            })
            return True
        if method == "POST" and path == "/lab/api/settings/save":
            body = self._body(request)
            payload = body.get("settings")
            if not isinstance(payload, dict):
                raise ValueError("settings save requires a complete settings object")
            if payload.get("base_config_sha256") != self.bundle.sha256:
                payload = rebase_settings_payload(self.bundle, payload)
            self._send(
                request, HTTPStatus.OK,
                self.lab.save_settings(self.bundle, payload, action=body.get("action"), actor=actor),
            )
            return True
        if method == "POST" and path == "/lab/api/settings/commissioning-request":
            body = self._body(request)
            if body.get("acknowledgement") != "reviewed_not_activated":
                raise ValueError("commissioning request requires explicit review acknowledgement")
            self._send(
                request, HTTPStatus.CREATED,
                self.lab.request_draft_commissioning(self.bundle, body.get("draft_id"), actor=actor),
            )
            return True
        campaign_match = re.fullmatch(r"/lab/api/campaigns/([^/]+)/objective", path)
        if method == "POST" and campaign_match:
            body = self._body(request)
            self._send(request, HTTPStatus.OK, {"campaign": self.lab.update_campaign_objective(campaign_match.group(1), body.get("objective"), actor=actor)})
            return True
        self._send(request, HTTPStatus.NOT_FOUND, {"error": "not_found"})
        return True

    def _codex_models(self) -> dict[str, Any]:
        provider = next((item for item in self.bundle.providers.values() if item["kind"] == "codex_cli"), None)
        if provider is None:
            return {"items": [], "available": False, "message": "Headless Codex is not configured."}
        try:
            completed = subprocess.run(
                [provider["endpoint"], "debug", "models"], text=True,
                capture_output=True, timeout=20, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"items": [], "available": False, "message": f"Codex model discovery failed: {type(exc).__name__}"}
        if completed.returncode != 0:
            return {"items": [], "available": False, "message": "Codex could not refresh its model catalog."}
        try:
            raw_models = json.loads(completed.stdout).get("models", [])
        except (AttributeError, json.JSONDecodeError):
            return {"items": [], "available": False, "message": "Codex returned an invalid model catalog."}
        items = []
        for model in raw_models:
            if not isinstance(model, dict) or model.get("visibility") != "list" or not isinstance(model.get("slug"), str):
                continue
            reasoning = [value.get("effort") for value in model.get("supported_reasoning_levels", []) if isinstance(value, dict) and isinstance(value.get("effort"), str)]
            input_modalities = [
                value for value in model.get("input_modalities", [])
                if value in {"text", "image"}
            ]
            items.append({
                "id": model["slug"],
                "name": model.get("display_name") or model["slug"],
                "description": model.get("description") or "Available through Codex.",
                "context_tokens": int(model.get("context_window") or model.get("max_context_window") or 128000),
                "reasoning_levels": reasoning,
                "default_reasoning_level": model.get("default_reasoning_level") if isinstance(model.get("default_reasoning_level"), str) else "",
                "input_modalities": input_modalities,
            })
        return {"items": items, "available": True, "message": f"{len(items)} models available through the current Codex login."}

    @staticmethod
    def _catalog_config_id(provider_id: str, exact_name: str) -> str:
        digest = hashlib.sha256(exact_name.encode("utf-8")).hexdigest()[:12]
        return f"catalog-{provider_id[:40]}-{digest}"[:63]

    @staticmethod
    def _models_endpoint(endpoint: str) -> str:
        suffix = "/chat/completions"
        return endpoint[:-len(suffix)] + "/models" if endpoint.rstrip("/").endswith(suffix) else endpoint.rstrip("/") + "/models"

    @staticmethod
    def _catalog_modality(model: dict[str, Any]) -> str:
        architecture = model.get("architecture") if isinstance(model.get("architecture"), dict) else {}
        inputs = architecture.get("input_modalities", [])
        outputs = architecture.get("output_modalities", [])
        inputs = {str(value).lower() for value in inputs} if isinstance(inputs, list) else set()
        outputs = {str(value).lower() for value in outputs} if isinstance(outputs, list) else set()
        description = " ".join(str(model.get(key, "")).lower() for key in ("id", "name", "description"))
        if "image" in outputs or any(word in description for word in ("image generation", "text-to-image", "flux")):
            return "image_generation"
        if "image" in inputs:
            return "vision_language"
        return "text"

    def _http_provider_models(self, provider: dict[str, Any]) -> dict[str, Any]:
        endpoint = self._models_endpoint(provider["endpoint"])
        headers = {"Accept": "application/json", "User-Agent": "Ninereeds-Mission-Hub/1"}
        credential = os.environ.get(provider["credential_env"], "") if provider["credential_env"] else ""
        if credential:
            headers["Authorization"] = f"Bearer {credential}"
        try:
            request = urllib.request.Request(endpoint, headers=headers)
            with urllib.request.urlopen(request, timeout=min(provider["timeout_seconds"], 10)) as response:
                document = json.loads(response.read(32 * 1024 * 1024))
            raw_items = document.get("data", [])
            if not isinstance(raw_items, list):
                raise ValueError("catalog data is not a list")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return {"provider_id": provider["id"], "available": False, "message": f"Catalog unavailable: {type(exc).__name__}", "items": []}
        items = []
        for raw in raw_items:
            if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
                continue
            exact_name = raw["id"]
            context = raw.get("context_length") or raw.get("context_window")
            try:
                provider_context = max(1, int(context)) if context is not None else None
            except (TypeError, ValueError):
                provider_context = None
            top_provider = raw.get("top_provider") if isinstance(raw.get("top_provider"), dict) else {}
            provider_output = top_provider.get("max_completion_tokens")
            try:
                provider_output = max(1, int(provider_output)) if provider_output is not None else None
            except (TypeError, ValueError):
                provider_output = None
            requested_context = self.bundle.model_defaults["unlisted_context_tokens"]
            requested_output = self.bundle.model_defaults["unlisted_output_tokens"]
            items.append({
                "id": self._catalog_config_id(provider["id"], exact_name),
                "provider": provider["id"], "exact_name": exact_name,
                "name": raw.get("name") or exact_name,
                "description": raw.get("description") or f"Available from {provider['id']}.",
                "enabled": False, "local": provider["kind"] == "local_openai_compatible",
                "context_tokens": min(provider_context, requested_context) if provider_context else requested_context,
                "output_tokens": min(provider_output, requested_output) if provider_output else requested_output,
                "provider_context_tokens": provider_context, "provider_output_tokens": provider_output,
                "structured_output": True, "runtime": "api", "weights": "",
                "device": "remote" if provider["kind"] == "openai_compatible" else "local endpoint",
                "modality": self._catalog_modality(raw), "revision": "",
            })
        return {"provider_id": provider["id"], "available": True, "message": f"{len(items)} models returned by the service.", "items": items}

    def _provider_models(self) -> dict[str, Any]:
        providers = list(self.bundle.providers.values())

        def discover(provider: dict[str, Any]) -> dict[str, Any]:
            if provider["kind"] == "codex_cli":
                catalog = self._codex_models()
                items = [{
                    "id": self._catalog_config_id(provider["id"], item["id"]),
                    "provider": provider["id"], "exact_name": item["id"],
                    "name": item["name"], "description": item["description"],
                    "enabled": False, "local": False,
                    "context_tokens": min(item["context_tokens"], self.bundle.model_defaults["unlisted_context_tokens"]),
                    "output_tokens": self.bundle.model_defaults["unlisted_output_tokens"],
                    "provider_context_tokens": item["context_tokens"], "provider_output_tokens": None,
                    "structured_output": True, "runtime": "codex exec", "weights": "",
                    "device": "remote",
                    "modality": "vision_language" if "image" in item["input_modalities"] else "text",
                    "revision": "",
                    "reasoning_levels": item["reasoning_levels"],
                } for item in catalog["items"]]
                return {"provider_id": provider["id"], "available": catalog["available"], "message": catalog["message"], "items": items}
            if provider["kind"] in {"openai_compatible", "local_openai_compatible"}:
                return self._http_provider_models(provider)
            return {"provider_id": provider["id"], "available": False, "message": "This provider does not expose a model catalog endpoint.", "items": []}

        with ThreadPoolExecutor(max_workers=min(5, len(providers))) as pool:
            catalogs = list(pool.map(discover, providers))
        return {"providers": catalogs, "items": [item for catalog in catalogs for item in catalog["items"]]}

    def _dashboard(self) -> dict[str, Any]:
        jobs = self.store.list_rows("jobs", limit=60)
        runs = self.store.list_rows("runs", limit=60)
        machines = self.store.list_rows("machines", limit=20)
        campaigns = self.store.list_rows("campaigns", limit=20)
        deployments = self.store.list_rows("deployments", limit=20)
        artifacts = self.store.list_rows("artifacts", limit=20)
        for machine in machines:
            machine["config"] = json.loads(machine.pop("config_json"))
            machine["last_observation"] = json.loads(machine.pop("last_observation_json")) if machine.get("last_observation_json") else None
        def present_job(job: dict[str, Any]) -> None:
            job["input"] = json.loads(job.pop("input_json"))
            try:
                _, pinned = self.lab.runtime_settings_for_job(self.bundle, job["id"])
                view = bundle_with_settings(self.bundle, pinned)
            except (MissionHubError, ValueError):
                view = self.bundle
            definition = view.jobs.get(job["job_type"], {})
            route_id = definition.get("provider_route", "")
            route = view.routes.get(route_id, {})
            model_ids = list(route.get("ordered_model_ids", []))
            job["route_id"] = route_id
            job["model_ids"] = model_ids
            job["model_names"] = [
                view.models[model_id]["exact_name"]
                for model_id in model_ids if model_id in view.models
            ]
        for job in jobs:
            present_job(job)
        for run in runs:
            run["output"] = json.loads(run.pop("output_json")) if run.get("output_json") else None
            run["failure"] = json.loads(run.pop("failure_json")) if run.get("failure_json") else None
        for campaign in campaigns:
            campaign["metadata"] = json.loads(campaign.pop("metadata_json"))
        for deployment in deployments:
            deployment["manifest"] = json.loads(deployment.pop("manifest_json"))
        for artifact in artifacts:
            artifact["manifest"] = json.loads(artifact.pop("manifest_json"))
        live_row = self.store.current_job()
        live = next((job for job in jobs if live_row and job["id"] == live_row["id"]), None)
        if live_row and live is None:
            present_job(live_row)
            live = live_row
            jobs.insert(0, live)
        next_job_row = self.store.next_queued_job()
        next_job = next((job for job in jobs if job["id"] == next_job_row["id"]), None) if next_job_row else None
        if next_job_row and next_job is None:
            present_job(next_job_row)
            next_job = next_job_row
        last_row = self.store.latest_terminal_job()
        last = next((job for job in jobs if job["id"] == last_row["id"]), None) if last_row else None
        if last_row and last is None:
            present_job(last_row)
            last = last_row
        active_campaign = next((item for item in campaigns if item["state"] == "active"), None) or (campaigns[0] if campaigns else None)
        active_workflows = self.store.active_cortex_workflows()
        active_visual_workflows = self.store.active_visual_workflows()
        progress_workflow = None
        progress_kind = None
        scheduled_job_id = (live or next_job or {}).get("id")
        for kind, workflows in (("cortex", active_workflows), ("visual", active_visual_workflows)):
            owner = next(
                (workflow for workflow in workflows if any(job["id"] == scheduled_job_id for job in workflow["jobs"])),
                None,
            )
            if owner:
                progress_workflow, progress_kind = owner, kind
                break
        if progress_workflow is None and len(active_workflows) + len(active_visual_workflows) == 1:
            if active_workflows:
                progress_workflow, progress_kind = active_workflows[0], "cortex"
            else:
                progress_workflow, progress_kind = active_visual_workflows[0], "visual"
        if not active_workflows and not active_visual_workflows:
            historical = [
                (row, kind)
                for kind, table in (("cortex", "cortex_workflows"), ("visual", "visual_workflows"))
                for row in self.store.list_rows(table, limit=100)
                if active_campaign is None or row["campaign_id"] == active_campaign["id"]
            ]
            if historical:
                latest, progress_kind = max(historical, key=lambda item: item[0]["created_at"])
                progress_workflow = (
                    self.store.cortex_workflow(latest["id"])
                    if progress_kind == "cortex"
                    else self.store.visual_workflow(latest["id"])
                )
        workflow_progress = None
        if active_campaign and isinstance(active_campaign.get("metadata", {}).get("campaign35_execution"), dict):
            campaign_cortex = [
                self.store.cortex_workflow(row["id"])
                for row in self.store.list_rows("cortex_workflows", limit=1000)
                if row["campaign_id"] == active_campaign["id"]
            ]
            campaign_visual = [
                self.store.visual_workflow(row["id"])
                for row in self.store.list_rows("visual_workflows", limit=1000)
                if row["campaign_id"] == active_campaign["id"]
            ]
            campaign_jobs = [
                dict(row) for row in self.store.list_rows("jobs", limit=5000)
                if row["campaign_id"] == active_campaign["id"]
            ]
            workflow_progress = self._campaign35_progress(
                active_campaign, campaign_cortex, campaign_visual, campaign_jobs,
            )
        elif progress_kind == "cortex":
            workflow_progress = self._cortex_progress(progress_workflow)
        elif progress_kind == "visual":
            workflow_progress = self._visual_progress(progress_workflow, shadow_mode=self.bundle.visual["shadow_mode"])
        return {
            "server_time": time.time(),
            "scheduler": {"poll_seconds": self.bundle.base["scheduler"]["poll_seconds"]},
            "config": {"sha256": self.bundle.sha256, "active": self.store.active_config()},
            "safety": self.bundle.base["safety"],
            "pipeline": self.store.pipeline_control(),
            "unread_count": self.lab.unread_count(),
            "current_job": live,
            "next_job": next_job,
            "last_job": last,
            "workflow_progress": workflow_progress,
            "active_campaign": active_campaign,
            "jobs": jobs,
            "runs": runs,
            "machines": machines,
            "deployments": deployments,
            "artifacts": artifacts,
        }

    @staticmethod
    def _campaign35_progress(campaign, cortex_workflows, visual_workflows, jobs):
        execution = campaign["metadata"]["campaign35_execution"]
        visual_workflows = [item for item in visual_workflows if item["specification"].get("plan", {}).get("authority", {}).get("exact_material") is True]
        # A repaired batch keeps the failed workflow as immutable evidence and
        # creates a newer workflow with the same exact plan. Present only the
        # newest authorization for each plan so preserved failures do not make
        # healthy replacement work look permanently blocked.
        visual_by_plan = {}
        for item in sorted(visual_workflows, key=lambda value: value.get("created_at", "")):
            plan = item["specification"].get("plan", {})
            visual_by_plan[plan.get("plan_id") or item["id"]] = item
        visual_workflows = list(visual_by_plan.values())
        # Include terminal workflows too; active lists alone would make
        # completed batches disappear from the aggregate.
        required = execution.get("required_outputs", [])
        cortex_workflows = [item for item in cortex_workflows if item["specification"].get("branch_id") in required]
        graph_job_ids = {
            job["id"]
            for workflow in [*visual_workflows, *cortex_workflows]
            for job in workflow.get("jobs", [])
        }
        all_jobs = [
            job for job in jobs
            if job.get("id") in graph_job_ids
            or str(job.get("idempotency_key", "")).startswith("campaign35:")
        ]
        # A pre-training material repair preserves the blocked predecessor and
        # authorizes a newer workflow. Present the newest ledger entry for the
        # branch; never let an older preserved failure overwrite it.
        branch_by_id = {
            item["specification"].get("branch_id"): item
            for item in sorted(cortex_workflows, key=lambda value: value.get("created_at", ""))
        }
        builds = []
        for branch in required:
            workflow = branch_by_id.get(branch)
            crossmodal = next((job for job in all_jobs if job.get("idempotency_key") == f"campaign35:{branch}:crossmodal-evaluate:v1"), None)
            if branch == "m4-merged":
                merge = next((job for job in all_jobs if job.get("idempotency_key") == "campaign35:m4:merge:v1"), None)
                evaluation = next((job for job in all_jobs if job.get("idempotency_key") == "campaign35:m4:evaluate:v1"), None)
                status = "succeeded" if merge and evaluation and crossmodal and merge["status"] == evaluation["status"] == crossmodal["status"] == "succeeded" else (crossmodal or merge or evaluation or {}).get("status", "pending")
            else:
                status = "succeeded" if workflow and workflow.get("status") == "succeeded" and crossmodal and crossmodal.get("status") == "succeeded" else (crossmodal or workflow or {}).get("status", "pending")
            builds.append({"id": branch, "status": status})
        visual_total = int(execution.get("batches") and len(execution["batches"]) or 0)
        visual_done = sum(item.get("status") == "succeeded" for item in visual_workflows)
        visual_plans_done = sum(
            any(
                job.get("stage_key") == "plan" and job.get("status") == "succeeded"
                for job in item.get("jobs", [])
            )
            for item in visual_workflows
        )
        completed_job_count = sum(job.get("status") == "succeeded" for job in all_jobs)
        # Root + visual pipeline + four 100-session train/eval workflows +
        # merge/text scan + five cross-modal terminal probes + handoff.
        expected_jobs = 1 + visual_total * 9 + 100 * 2 * 4 + 2 + 5 + 1
        completed = min(completed_job_count, expected_jobs)
        status = execution.get("status", "authorized_paused")
        failed = any(job.get("status") in {"failed", "blocked", "cancelled"} for job in all_jobs) or status == "blocked"
        workflow_status = "blocked" if failed else "succeeded" if status == "complete" else "active"
        if not any(job.get("idempotency_key") == "campaign35:neutral-root:v1" and job.get("status") == "succeeded" for job in all_jobs):
            stage = "neutral root"
            activity = "Preparing the common zero-state checkpoint"
        elif visual_done < visual_total:
            stage = "visual material"
            activity = f"{visual_plans_done}/{visual_total} exact plans · {visual_done}/{visual_total} complete visual lesson packs"
        else:
            active_build = next((item for item in builds if item["status"] != "succeeded"), None)
            stage = active_build["id"] if active_build else "post-campaign recommendation"
            activity = None
        return {
            "workflow_id": campaign["id"], "workflow_kind": "campaign35",
            "workflow_status": workflow_status, "branch_id": "campaign-35-five-build",
            "unit_label": "Step", "unit_index": min(completed + 1, expected_jobs),
            "units_total": expected_jobs, "completed_stages": completed,
            "total_stages": expected_jobs, "percent": round(completed * 100 / expected_jobs),
            "stage": stage, "stage_status": status, "builds": builds,
            "activity": activity,
            "visual_plans_complete": visual_plans_done,
            "visual_batches_complete": visual_done, "visual_batches_total": visual_total,
        }

    @staticmethod
    def _cortex_progress(workflow: dict[str, Any]) -> dict[str, Any]:
        """Return a small, presentation-safe summary of an authorized branch."""
        sessions = workflow["specification"].get("sessions", [])
        jobs = {job["stage_key"]: job for job in workflow.get("jobs", [])}
        completed_stages = 0
        block_index = len(sessions) if sessions else 0
        stage = "complete"
        stage_status = workflow.get("status", "active")
        for index, _session in enumerate(sessions):
            train = jobs.get(f"s{index:02d}:train")
            evaluate = jobs.get(f"s{index:02d}:evaluate")
            if train and train.get("status") == "succeeded":
                completed_stages += 1
            if evaluate and evaluate.get("status") == "succeeded":
                completed_stages += 1
            if block_index == len(sessions) and not (evaluate and evaluate.get("status") == "succeeded"):
                block_index = index + 1
                training_complete = bool(train and train.get("status") == "succeeded")
                current = evaluate if training_complete else train
                stage = "evaluation" if training_complete else "training"
                stage_status = current.get("status", "pending") if current else "pending"
        total_stages = len(sessions) * 2
        return {
            "workflow_id": workflow["id"],
            "workflow_status": workflow.get("status", "active"),
            "branch_id": workflow["specification"].get("branch_id"),
            "block_index": block_index,
            "blocks_total": len(sessions),
            "completed_stages": completed_stages,
            "total_stages": total_stages,
            "percent": round(completed_stages * 100 / total_stages) if total_stages else 0,
            "stage": stage,
            "stage_status": stage_status,
        }

    @staticmethod
    def _visual_progress(workflow: dict[str, Any], *, shadow_mode: bool) -> dict[str, Any]:
        """Summarize a visual workflow without pretending its stages are training blocks."""
        jobs = {job["stage_key"]: job for job in workflow.get("jobs", [])}
        fixed_stages = ["plan", "generate", "inspect", "caption", "decide"]
        terminal_stages = [] if shadow_mode else ["pack", "encode", "experience"]
        review_jobs = [job for key, job in jobs.items() if key == "review" or key.startswith("review:")]
        completed_stages = sum(
            1 for stage in fixed_stages if jobs.get(stage, {}).get("status") == "succeeded"
        )
        review_complete = bool(review_jobs) and all(job.get("status") == "succeeded" for job in review_jobs)
        if review_complete:
            completed_stages += 1
        completed_stages += sum(
            1 for stage in terminal_stages if jobs.get(stage, {}).get("status") == "succeeded"
        )
        stages = [*fixed_stages, "review", *terminal_stages]
        terminal = workflow.get("status") in {"shadow_complete", "succeeded"}
        if terminal:
            completed_stages = len(stages)
            stage = "complete"
            stage_status = workflow["status"]
            stage_index = len(stages)
        else:
            stage = next(
                (name for name in fixed_stages if jobs.get(name, {}).get("status") != "succeeded"),
                None,
            )
            if stage is None and not review_complete:
                stage = "review"
            if stage is None:
                stage = next(
                    (name for name in terminal_stages if jobs.get(name, {}).get("status") != "succeeded"),
                    "complete",
                )
            relevant = review_jobs if stage == "review" else [jobs.get(stage, {})]
            current = next((job for job in relevant if job.get("status") != "succeeded"), relevant[-1] if relevant else {})
            stage_status = current.get("status", "pending")
            stage_index = min(completed_stages + 1, len(stages))
        return {
            "workflow_id": workflow["id"],
            "workflow_kind": "visual",
            "workflow_status": workflow.get("status", "active"),
            "branch_id": workflow["specification"].get("branch_id"),
            "unit_label": "Stage",
            "unit_index": stage_index,
            "units_total": len(stages),
            "completed_stages": completed_stages,
            "total_stages": len(stages),
            "percent": round(completed_stages * 100 / len(stages)),
            "stage": stage,
            "stage_status": stage_status,
        }

    def _lab_session(self, request: BaseHTTPRequestHandler) -> dict[str, Any] | None:
        return self.lab.session(self._session_token(request))

    def _require_lab_session(self, request: BaseHTTPRequestHandler) -> dict[str, Any]:
        session = self._lab_session(request)
        if session is None:
            self._send(request, HTTPStatus.UNAUTHORIZED, {"error": "authentication_required"})
            raise _ResponseSent
        return session

    @staticmethod
    def _session_token(request: BaseHTTPRequestHandler) -> str:
        cookie = SimpleCookie()
        try:
            cookie.load(request.headers.get("Cookie", ""))
        except Exception:
            return ""
        value = cookie.get("nr_lab_session")
        return "" if value is None else value.value

    @staticmethod
    def _session_cookie(request: BaseHTTPRequestHandler, token: str, *, max_age: int = SESSION_SECONDS) -> str:
        secure = request.headers.get("X-Forwarded-Proto", "").lower() == "https"
        parts = [f"nr_lab_session={token}", "Path=/", "HttpOnly", "SameSite=Strict", f"Max-Age={max_age}"]
        if secure:
            parts.append("Secure")
        return "; ".join(parts)

    def _check_origin(self, request: BaseHTTPRequestHandler) -> None:
        origin = request.headers.get("Origin")
        if not origin:
            return
        host = request.headers.get("Host", "")
        if not re.fullmatch(r"https?://" + re.escape(host), origin):
            self._send(request, HTTPStatus.FORBIDDEN, {"error": "origin_not_allowed"})
            raise _ResponseSent

    def _login_throttled(self, client: str) -> bool:
        cutoff = time.time() - 300
        attempts = [item for item in self._login_failures.get(client, []) if item >= cutoff]
        self._login_failures[client] = attempts
        return len(attempts) >= 5

    def _record_login_failure(self, client: str) -> None:
        self._login_failures.setdefault(client, []).append(time.time())

    def _static(self, request: BaseHTTPRequestHandler, name: str) -> None:
        allowed = {
            "index.html": "text/html; charset=utf-8", "login.html": "text/html; charset=utf-8",
            "lab.css": "text/css; charset=utf-8", "lab.js": "text/javascript; charset=utf-8",
            "login.js": "text/javascript; charset=utf-8", "manifest.webmanifest": "application/manifest+json",
            "scan.html": "text/html; charset=utf-8", "scan.css": "text/css; charset=utf-8",
            "scan.js": "text/javascript; charset=utf-8",
        }
        if name not in allowed:
            self._send(request, HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        path = self.lab_assets / name
        if not path.is_file():
            self._send(request, HTTPStatus.NOT_FOUND, {"error": "asset_not_found"})
            return
        self._send_bytes(request, HTTPStatus.OK, path.read_bytes(), allowed[name])

    @staticmethod
    def _redirect(request: BaseHTTPRequestHandler, location: str) -> None:
        request.send_response(HTTPStatus.SEE_OTHER)
        request.send_header("Location", location)
        MissionHubAPI._security_headers(request)
        request.send_header("Content-Length", "0")
        request.end_headers()

    @staticmethod
    def _security_headers(request: BaseHTTPRequestHandler) -> None:
        request.send_header("Cache-Control", "no-store")
        request.send_header("X-Content-Type-Options", "nosniff")
        request.send_header("X-Frame-Options", "DENY")
        request.send_header("Referrer-Policy", "no-referrer")
        request.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        request.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")

    @staticmethod
    def _send_bytes(request: BaseHTTPRequestHandler, status: HTTPStatus, payload: bytes, content_type: str) -> None:
        request.send_response(status)
        request.send_header("Content-Type", content_type)
        request.send_header("Content-Length", str(len(payload)))
        MissionHubAPI._security_headers(request)
        request.end_headers()
        request.wfile.write(payload)

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
    def _send(
        request: BaseHTTPRequestHandler,
        status: HTTPStatus,
        payload: dict[str, Any],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        request.send_response(status)
        request.send_header("Content-Type", "application/json; charset=utf-8")
        request.send_header("Content-Length", str(len(encoded)))
        MissionHubAPI._security_headers(request)
        for key, value in (extra_headers or {}).items():
            request.send_header(key, value)
        request.end_headers()
        request.wfile.write(encoded)


def serve(store: MissionHubStore, bundle: ConfigBundle) -> None:
    server = MissionHubAPI(store, bundle).server()
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
