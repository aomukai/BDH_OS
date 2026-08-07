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

from .config import ConfigBundle
from .errors import MissionHubError, NotFoundError
from .store import MissionHubStore
from .service import MissionHubService
from .lab import LabStore, SESSION_SECONDS, settings_payload
from .observatory import Observatory


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
            if method == "POST" and path == "/v1/cortex-workflows":
                body = self._body(request)
                row = self.store.create_cortex_workflow(
                    self.bundle, body["specification"], actor="mission-hub-api",
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
            self._send(request, HTTPStatus.OK, {"active": settings_payload(self.bundle), "draft": self.lab.latest_draft(base_config_sha256=self.bundle.sha256)})
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
            self._send(request, HTTPStatus.CREATED, {"draft": self.lab.save_draft(self.bundle, self._body(request), actor=actor)})
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
            items.append({
                "id": model["slug"],
                "name": model.get("display_name") or model["slug"],
                "description": model.get("description") or "Available through Codex.",
                "context_tokens": int(model.get("context_window") or model.get("max_context_window") or 128000),
                "reasoning_levels": reasoning,
                "default_reasoning_level": model.get("default_reasoning_level") if isinstance(model.get("default_reasoning_level"), str) else "",
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
                    "device": "remote", "modality": "text", "revision": "",
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
            definition = self.bundle.jobs.get(job["job_type"], {})
            route_id = definition.get("provider_route", "")
            route = self.bundle.routes.get(route_id, {})
            model_ids = list(route.get("ordered_model_ids", []))
            job["route_id"] = route_id
            job["model_ids"] = model_ids
            job["model_names"] = [
                self.bundle.models[model_id]["exact_name"]
                for model_id in model_ids if model_id in self.bundle.models
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
        live = next((job for job in jobs if job["status"] in {"leased", "running"}), None)
        next_job_row = self.store.next_queued_job()
        next_job = next((job for job in jobs if job["id"] == next_job_row["id"]), None) if next_job_row else None
        if next_job_row and next_job is None:
            present_job(next_job_row)
            next_job = next_job_row
        last = next((job for job in jobs if job["status"] in {"succeeded", "failed", "blocked", "cancelled"}), None)
        active_campaign = next((item for item in campaigns if item["state"] == "active"), None) or (campaigns[0] if campaigns else None)
        active_workflows = self.store.active_cortex_workflows()
        progress_workflow = active_workflows[0] if len(active_workflows) == 1 else None
        if not active_workflows:
            workflow_rows = self.store.list_rows("cortex_workflows", limit=100)
            latest = next(
                (
                    row for row in workflow_rows
                    if active_campaign is None or row["campaign_id"] == active_campaign["id"]
                ),
                None,
            )
            progress_workflow = self.store.cortex_workflow(latest["id"]) if latest else None
        return {
            "server_time": time.time(),
            "config": {"sha256": self.bundle.sha256, "active": self.store.active_config()},
            "safety": self.bundle.base["safety"],
            "pipeline": self.store.pipeline_control(),
            "unread_count": self.lab.unread_count(),
            "current_job": live,
            "next_job": next_job,
            "last_job": last,
            "workflow_progress": self._cortex_progress(progress_workflow) if progress_workflow else None,
            "active_campaign": active_campaign,
            "jobs": jobs,
            "runs": runs,
            "machines": machines,
            "deployments": deployments,
            "artifacts": artifacts,
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
