"""Bounded provider-backed lesson material generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..errors import RemoteJobError, SafetyError
from ..lesson_policy import policy_sha256, require_lesson_material
from ..schema import require_supported_schema, validate
from .contracts import _declaration, _object_file
from .visual import _verified_inputs
from .visual_provider import ProviderFailure, _codex, _evidence, _http


def require_bounded_material_output(value: Any, maximum_items: int) -> None:
    """Enforce the same repeated-item ceiling after provider generation."""
    stack = [value]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            if len(node) > maximum_items:
                raise ProviderFailure(
                    "lesson output exceeds the declared one-unit item bound",
                    "repairable_output", code="output_schema_invalid",
                )
            stack.extend(node)
        elif isinstance(node, dict):
            stack.extend(node.values())


class ExecutorGenerateHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        inputs = _verified_inputs(context, payload["input_artifact_ids"])
        prompt = context.get("prompt")
        if not prompt:
            raise SafetyError("lesson generation has no configured prompt")
        output_contract = require_supported_schema(
            payload["output_contract"], location="executor.generate output_contract",
        )
        task_data = {
            "specification": payload["specification"],
            "input_artifacts": _evidence(inputs),
            "output_contract": output_contract,
            "limits": payload["limits"],
        }
        prompt_text = (
            prompt["system"].strip()
            + "\n\nTask template:\n"
            + prompt["template"].strip()
            + "\n\nExact task data:\n"
            + json.dumps(task_data, ensure_ascii=False, sort_keys=True)
        )
        if len(prompt_text.encode("utf-8")) > max(4096, context["route"]["max_total_tokens"] * 6):
            raise SafetyError("lesson-generation prompt exceeds the route input bound")

        run_root = Path(context["state_root"]).resolve() / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        contract_path = run_root / "lesson-output-contract.json"
        contract_path.write_text(
            json.dumps(output_contract, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        attempts: list[dict[str, Any]] = []
        material: dict[str, Any] | None = None
        selected: dict[str, Any] | None = None
        for index, model in enumerate(context["route_models"]):
            provider = context["providers"][model["provider"]]
            try:
                if not model["enabled"] or not provider["enabled"]:
                    raise ProviderFailure(
                        "configured route contains a disabled model or provider", "capability_transient",
                    )
                if provider["kind"] == "codex_cli":
                    value, transcript = _codex(
                        provider, model, prompt_text, contract_path, [], run_root,
                    )
                elif provider["kind"] in {"openai_compatible", "local_openai_compatible"}:
                    value, transcript = _http(
                        provider, model, prompt_text, context["route"]["max_total_tokens"],
                    )
                else:
                    raise ProviderFailure(
                        f"unsupported lesson provider kind: {provider['kind']}", "capability_transient",
                    )
                errors = validate(value, output_contract)
                if errors:
                    raise ProviderFailure(
                        "lesson output failed its contract: " + "; ".join(errors), "repairable_output",
                    )
                require_lesson_material(value, context["identity_policy"])
                require_bounded_material_output(value, payload["limits"]["max_output_items"])
                material, selected = value, model
                attempts.append({
                    "model_id": model["id"], "provider_id": provider["id"],
                    "status": "succeeded", "transcript": transcript,
                })
                break
            except ProviderFailure as exc:
                attempts.append({
                    "model_id": model["id"], "provider_id": provider["id"],
                    "status": "failed", "failure_class": exc.failure_class,
                    "failure_code": exc.code, "message": str(exc),
                })
                if (
                    index + 1 >= len(context["route_models"])
                    or exc.failure_class not in context["route"]["fallback_failure_classes"]
                ):
                    break

        transcript_doc = {
            "schema_version": "ninereeds_provider_transcript_v1",
            "stage": "executor.generate", "prompt_id": prompt["id"],
            "prompt_version": prompt["version"], "attempts": attempts,
            "campaign_id": context["campaign_id"],
            "campaign_contract_sha256": payload["specification"]["campaign_contract_sha256"],
        }
        transcript_path, transcript_sha, transcript_size = _object_file(
            context["state_root"],
            (json.dumps(transcript_doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        if material is None or selected is None:
            last = attempts[-1] if attempts else {}
            raise RemoteJobError(
                f"lesson generation exhausted its configured route; transcript: {transcript_path}",
                failure_class=last.get("failure_class", "capability_transient"),
                code=last.get("failure_code", "resource_temporarily_unavailable"),
            )

        specification = payload["specification"]
        material_path, material_sha, material_size = _object_file(
            context["state_root"],
            (json.dumps(material, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        manifest = {
            "schema_version": "ninereeds_generated_lesson_v2",
            "campaign_id": context["campaign_id"],
            "campaign_contract_sha256": specification["campaign_contract_sha256"],
            "training_mode": specification["training_mode"],
            "development_stage": specification["development_stage"],
            "campaign_purpose": specification["campaign_purpose"],
            "target_capability": specification["target_capability"],
            "identity_scope": specification["identity_scope"],
            "lesson_policy_status": "passed",
            "lesson_policy_id": context["identity_policy"]["id"],
            "lesson_policy_version": context["identity_policy"]["version"],
            "lesson_policy_sha256": policy_sha256(context["identity_policy"]),
            "model_id": selected["exact_name"], "route_id": context["route"]["id"],
            "prompt_id": prompt["id"], "prompt_version": prompt["version"],
            "source_artifact_ids": payload["input_artifact_ids"],
        }
        return {
            "status": "succeeded", "material": material,
            "validation": {
                "schema": "passed", "identity_and_lesson_policy": "passed",
                "campaign_context": "passed",
            },
            "artifacts": [
                _declaration("generated_material", material_path, material_sha, material_size, manifest),
                _declaration("provider_transcript", transcript_path, transcript_sha, transcript_size, {
                    "stage": "executor.generate", "attempt_count": len(attempts),
                    "selected_model_id": selected["exact_name"],
                    "campaign_contract_sha256": specification["campaign_contract_sha256"],
                }),
            ],
            "failure": None,
        }
