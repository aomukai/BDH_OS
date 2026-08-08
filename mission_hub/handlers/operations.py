"""Provider-backed, bounded on-call assessment of operator notices."""

from __future__ import annotations

import json
from pathlib import Path

from ..errors import RemoteJobError
from ..schema import load_schema, validate
from .contracts import _declaration, _object_file
from .visual_provider import ProviderFailure, _codex, _http


class OperationalResponseHandler:
    def execute(self, payload, context):
        prompt = context["prompt"]
        prompt_text = prompt["system"].strip() + "\n\n" + prompt["template"].strip() + "\n\nExact notice:\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        repo = Path(context["release_root"])
        schema_path = repo / prompt["output_schema"]
        schema = load_schema(repo, prompt["output_schema"])
        run_root = Path(context["state_root"]) / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        attempts, result, selected = [], None, None
        for index, model in enumerate(context["route_models"]):
            provider = context["providers"][model["provider"]]
            try:
                if not model["enabled"] or not provider["enabled"]:
                    raise ProviderFailure("configured responder model or provider is disabled", "capability_transient")
                if provider["kind"] == "codex_cli":
                    value, transcript = _codex(provider, model, prompt_text, schema_path, [], run_root)
                elif provider["kind"] in {"openai_compatible", "local_openai_compatible"}:
                    value, transcript = _http(provider, model, prompt_text, context["route"]["max_total_tokens"])
                else:
                    raise ProviderFailure("unsupported responder provider", "capability_transient")
                errors = validate(value, schema)
                if errors:
                    raise ProviderFailure("responder output failed schema validation: " + "; ".join(errors), "repairable_output")
                result, selected = value, model
                attempts.append({"model_id": model["id"], "status": "succeeded", "transcript": transcript})
                break
            except ProviderFailure as exc:
                attempts.append({"model_id": model["id"], "status": "failed", "failure_class": exc.failure_class, "message": str(exc)})
                if index + 1 >= len(context["route_models"]) or exc.failure_class not in context["route"]["fallback_failure_classes"]:
                    break
        if result is None:
            last = attempts[-1] if attempts else {}
            raise RemoteJobError("operational responder exhausted its configured route", failure_class=last.get("failure_class", "capability_transient"), code="provider_capability_unavailable")
        document = {
            **result, "schema_version": "ninereeds_operational_response_v1",
            "thread_id": payload["thread_id"], "trigger_message_id": payload["message_id"],
            "model_id": selected["exact_name"], "route_id": context["route"]["id"],
        }
        path, digest, size = _object_file(context["state_root"], (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())
        return {**result, "status": "succeeded", "artifacts": [_declaration("operational_response", path, digest, size, document)]}
