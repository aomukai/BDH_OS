"""Bounded provider-backed visual planning, policy, and pixel-review stages."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any
import urllib.error
import urllib.request

from ..errors import ProtocolError, RemoteJobError, SafetyError
from ..schema import load_schema, validate
from .contracts import _declaration, _object_file
from .visual import _verified_inputs


class ProviderFailure(RuntimeError):
    def __init__(
        self, message: str, failure_class: str, code: str | None = None,
        *, transcript: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.failure_class = failure_class
        self.transcript = transcript
        self.code = code or {
            "repairable_output": "output_schema_invalid",
            "capability_transient": "provider_capability_unavailable",
            "operational_transient": "resource_temporarily_unavailable",
        }.get(failure_class, "unexpected_internal_error")


def _json_from_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ProviderFailure("provider response is not one JSON object", "repairable_output") from exc
    if not isinstance(value, dict):
        raise ProviderFailure("provider response JSON is not an object", "repairable_output")
    return value


def _evidence(inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result, total = [], 0
    for artifact in inputs:
        row = {
            "id": artifact["id"], "kind": artifact["kind"], "sha256": artifact["sha256"],
            "byte_size": artifact["byte_size"], "manifest": artifact["manifest"],
        }
        if artifact["kind"] not in {"visual_candidate", "visual_features", "log", "provider_transcript"}:
            raw = Path(artifact["uri"]).read_bytes()
            total += len(raw)
            if len(raw) <= 2 * 1024 * 1024 and total <= 8 * 1024 * 1024:
                try:
                    row["content"] = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    row["content_omitted"] = "not_json"
            else:
                row["content_omitted"] = "provider_evidence_byte_limit"
        result.append(row)
    return result


def _render_prompt(prompt: dict[str, Any], payload: dict[str, Any], inputs: list[dict[str, Any]], stage: str) -> str:
    evidence = _evidence(inputs)
    body = {
        "stage": stage, "specification": payload["specification"],
        "evidence": evidence, "limits": payload["limits"],
    }
    return prompt["system"].strip() + "\n\nTask template:\n" + prompt["template"].strip() + "\n\nExact task data:\n" + json.dumps(body, ensure_ascii=False, sort_keys=True)


def _codex_schema(schema_path: Path, run_root: Path) -> Path:
    """Write the provider subset while retaining full local validation.

    Codex structured output currently rejects JSON Schema ``uniqueItems``.
    The canonical schema is still applied to the returned value below, so
    removing the keyword from the provider hint does not weaken the contract.
    """
    def compatible(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: compatible(item) for key, item in value.items() if key != "uniqueItems"}
        if isinstance(value, list):
            return [compatible(item) for item in value]
        return value

    path = run_root / "codex-output-schema.json"
    path.write_text(
        json.dumps(compatible(json.loads(schema_path.read_text(encoding="utf-8"))), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _codex(provider: dict[str, Any], model: dict[str, Any], prompt: str, schema_path: Path, images: list[Path], run_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    output_path = run_root / "codex-final.json"
    provider_schema_path = _codex_schema(schema_path, run_root)
    command = [
        provider["endpoint"], "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
        "--sandbox", "read-only", "--skip-git-repo-check", "-C", str(run_root),
        "--model", model["exact_name"], "--output-schema", str(provider_schema_path),
        "--output-last-message", str(output_path), "--color", "never",
    ]
    for image in images:
        command.extend(["--image", str(image)])
    command.append("-")
    try:
        completed = subprocess.run(
            command, input=prompt, text=True, capture_output=True,
            timeout=provider["timeout_seconds"], check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProviderFailure("Codex provider timed out", "operational_transient", transcript={
            "command": command[:-1] + ["<prompt-on-stdin>"], "timeout": True,
            "stdout": exc.stdout or "", "stderr": exc.stderr or "",
        }) from exc
    except OSError as exc:
        raise ProviderFailure(f"Codex provider is unavailable: {exc}", "capability_transient", transcript={
            "command": command[:-1] + ["<prompt-on-stdin>"], "os_error": f"{type(exc).__name__}: {exc}",
        }) from exc
    transcript = {"command": command[:-1] + ["<prompt-on-stdin>"], "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    if completed.returncode != 0 or not output_path.is_file():
        lowered = (completed.stderr + completed.stdout).lower()
        failure_class = "operational_transient" if any(word in lowered for word in ("timeout", "rate limit", "temporarily", "connection")) else "capability_transient"
        raise ProviderFailure("Codex provider failed", failure_class, transcript=transcript)
    return _json_from_text(output_path.read_text(encoding="utf-8")), transcript


def _http(provider: dict[str, Any], model: dict[str, Any], prompt: str, route_token_limit: int) -> tuple[dict[str, Any], dict[str, Any]]:
    credential = os.environ.get(provider["credential_env"], "") if provider["credential_env"] else ""
    if provider["credential_env"] and not credential:
        raise ProviderFailure(f"provider credential {provider['credential_env']} is unavailable", "capability_transient")
    request_body = {
        "model": model["exact_name"],
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": min(model["output_tokens"], route_token_limit), "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json"}
    if credential:
        headers["Authorization"] = f"Bearer {credential}"
    request = urllib.request.Request(provider["endpoint"], data=json.dumps(request_body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=provider["timeout_seconds"]) as response:
            raw = response.read(16 * 1024 * 1024)
            status = response.status
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise ProviderFailure("provider HTTP 429 rate limit", "capability_transient", "provider_rate_limited") from exc
        failure_class = "operational_transient" if exc.code >= 500 else "capability_transient"
        raise ProviderFailure(f"provider HTTP {exc.code}", failure_class) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderFailure(f"provider request failed: {exc}", "operational_transient") from exc
    try:
        response_doc = json.loads(raw)
        content = response_doc["choices"][0]["message"]["content"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        raise ProviderFailure("provider returned an invalid chat-completions envelope", "repairable_output") from exc
    transcript = {"endpoint": provider["endpoint"], "status": status, "model": model["exact_name"], "response": response_doc}
    return _json_from_text(content), transcript


class _VisualProviderHandler:
    stage = ""
    artifact_kind = ""

    def validate_inputs(self, inputs: list[dict[str, Any]]) -> None:
        return None

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        inputs = _verified_inputs(context, payload["input_artifact_ids"])
        self.validate_inputs(inputs)
        prompt = context.get("prompt")
        if not prompt:
            raise SafetyError(f"{self.stage} has no configured prompt")
        prompt_text = _render_prompt(prompt, payload, inputs, self.stage)
        if len(prompt_text.encode("utf-8")) > max(4096, context["route"]["max_total_tokens"] * 6):
            raise SafetyError("visual provider prompt exceeds the route input bound")
        candidates = [Path(item["uri"]) for item in inputs if item["kind"] == "visual_candidate"]
        if self.stage == "visual.review" and len(candidates) != 1:
            raise SafetyError("independent visual review requires exactly one candidate image")
        if self.stage != "visual.review" and candidates and self.stage == "visual.plan":
            raise SafetyError("visual planning does not accept candidate pixels")
        repo_root = Path(context["release_root"]).resolve()
        schema_path = (repo_root / prompt["output_schema"]).resolve()
        schema = load_schema(repo_root, prompt["output_schema"])
        run_root = Path(context["state_root"]).resolve() / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        attempts, result, selected = [], None, None
        for index, model in enumerate(context["route_models"]):
            provider = context["providers"][model["provider"]]
            try:
                if not model["enabled"] or not provider["enabled"]:
                    raise ProviderFailure("configured route contains a disabled model or provider", "capability_transient")
                if provider["kind"] == "codex_cli":
                    value, transcript = _codex(provider, model, prompt_text, schema_path, candidates, run_root)
                elif provider["kind"] in {"openai_compatible", "local_openai_compatible"}:
                    if candidates:
                        raise ProviderFailure("this HTTP provider path has no commissioned image attachment contract", "capability_transient")
                    value, transcript = _http(provider, model, prompt_text, context["route"]["max_total_tokens"])
                else:
                    raise ProviderFailure(f"unsupported provider kind: {provider['kind']}", "capability_transient")
                errors = validate(value, schema)
                if errors:
                    raise ProviderFailure("provider output failed schema validation: " + "; ".join(errors), "repairable_output")
                if len(json.dumps(value, ensure_ascii=False).encode("utf-8")) > max(4096, context["route"]["max_total_tokens"] * 6):
                    raise ProviderFailure("provider output exceeds the route bound", "repairable_output")
                result, selected = value, model
                attempts.append({"model_id": model["id"], "provider_id": provider["id"], "status": "succeeded", "transcript": transcript})
                break
            except ProviderFailure as exc:
                attempts.append({
                    "model_id": model["id"], "provider_id": provider["id"],
                    "status": "failed", "failure_class": exc.failure_class,
                    "failure_code": exc.code, "message": str(exc),
                    **({"transcript": exc.transcript} if exc.transcript is not None else {}),
                })
                if index + 1 >= len(context["route_models"]) or exc.failure_class not in context["route"]["fallback_failure_classes"]:
                    break
        transcript_doc = {
            "schema_version": "ninereeds_provider_transcript_v1", "stage": self.stage,
            "prompt_id": prompt["id"], "prompt_version": prompt["version"], "attempts": attempts,
        }
        transcript_path, transcript_sha, transcript_size = _object_file(
            context["state_root"], (json.dumps(transcript_doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        if result is None or selected is None:
            last = attempts[-1] if attempts else {}
            raise RemoteJobError(
                f"{self.stage} exhausted its configured provider route; transcript: {transcript_path}",
                failure_class=last.get("failure_class", "capability_transient"),
                code=last.get("failure_code", "resource_temporarily_unavailable"),
            )
        manifest = dict(result)
        manifest.update({
            "schema_version": f"ninereeds_{self.stage.replace('.', '_')}_v1",
            "model_id": selected["exact_name"], "route_id": context["route"]["id"],
            "prompt_id": prompt["id"], "prompt_version": prompt["version"],
            "source_artifact_ids": payload["input_artifact_ids"],
        })
        if self.stage == "visual.review":
            candidate = next(item for item in inputs if item["kind"] == "visual_candidate")
            if manifest["asset_sha256"] != candidate["sha256"]:
                raise SafetyError("visual reviewer returned a different asset hash")
            if manifest["asset_status"] == "usable" and not manifest["accepted_uses"]:
                raise SafetyError("usable visual review requires exact accepted uses")
            if manifest["asset_status"] == "unusable" and manifest["accepted_uses"]:
                raise SafetyError("unusable visual review may not declare accepted uses")
            if len(manifest["accepted_uses"]) != len(set(manifest["accepted_uses"])):
                raise SafetyError("visual review accepted uses must be unique")
            manifest["reviewer"] = "sol"
        result_path, result_sha, result_size = _object_file(
            context["state_root"], (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        return {
            "status": "succeeded", "stage": self.stage,
            "metrics": {"provider_attempts": len(attempts), "model_id": selected["exact_name"]},
            "artifacts": [
                _declaration(self.artifact_kind, result_path, result_sha, result_size, manifest),
                _declaration("provider_transcript", transcript_path, transcript_sha, transcript_size, {
                    "stage": self.stage, "attempt_count": len(attempts), "selected_model_id": selected["exact_name"],
                }),
            ],
            "failure": None,
        }


class VisualPlanHandler(_VisualProviderHandler):
    stage = "visual.plan"
    artifact_kind = "visual_plan"

    def validate_inputs(self, inputs: list[dict[str, Any]]) -> None:
        if any(item["kind"] == "visual_candidate" for item in inputs):
            raise SafetyError("visual planning may not inspect candidate pixels")

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        result = super().execute(payload, context)
        plan = next(item for item in result["artifacts"] if item["kind"] == "visual_plan")["manifest"]
        for item in plan["items"]:
            if len(item["seeds"]) != len(set(item["seeds"])):
                raise SafetyError("visual plan repeats a generation seed within one item")
        return result


class VisualDecisionHandler(_VisualProviderHandler):
    stage = "visual.decide"
    artifact_kind = "visual_decision_report"

    def validate_inputs(self, inputs: list[dict[str, Any]]) -> None:
        kinds = [item["kind"] for item in inputs]
        if "visual_candidate" in kinds:
            raise SafetyError("visual policy decision may not receive pixels")
        if (
            kinds.count("visual_generation_report") != 1
            or kinds.count("visual_inspection_report") != 1
            or kinds.count("visual_caption_report") != 1
            or any(kind not in {
                "visual_generation_report", "visual_inspection_report", "visual_caption_report",
            } for kind in kinds)
        ):
            raise SafetyError("visual policy decision requires generation, inspection, and caption evidence")


class VisualReviewHandler(_VisualProviderHandler):
    stage = "visual.review"
    artifact_kind = "visual_review_report"

    def validate_inputs(self, inputs: list[dict[str, Any]]) -> None:
        kinds = [item["kind"] for item in inputs]
        if kinds.count("visual_candidate") != 1 or kinds.count("visual_inspection_report") != 1 or kinds.count("visual_decision_report") != 1:
            raise SafetyError("independent review requires one candidate, inspection report, and policy decision")
