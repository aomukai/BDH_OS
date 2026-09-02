"""Schema-bound Sol decision for one durable research-lab activation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..errors import RemoteJobError, SafetyError
from ..schema import load_schema, validate
from .contracts import _declaration, _object_file
from .visual_provider import ProviderFailure, _codex, _http


class ResearchDecisionHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        prompt = context.get("prompt")
        if not prompt:
            raise SafetyError("research conductor has no configured prompt")
        stable_prefix = (
            prompt["system"].strip()
            + "\n\nTask contract:\n"
            + prompt["template"].strip()
        )
        task = {
            "lab_id": payload["lab_id"],
            "campaign_id": payload["campaign_id"],
            "campaign_number": payload["campaign_number"],
            "activation_id": payload["activation_id"],
            "goal": payload["goal"],
            "todo": payload["todo"],
            "observation": payload["observation"],
            "recent_reports": payload["recent_reports"],
            "available_datasets": payload["available_datasets"],
            "allowed_actions": payload["allowed_actions"],
        }
        prompt_text = stable_prefix + "\n\nCurrent activation data:\n" + json.dumps(
            task, ensure_ascii=False, sort_keys=True,
        )
        release_root = Path(context["release_root"]).resolve()
        schema_path = (release_root / prompt["output_schema"]).resolve()
        schema = load_schema(release_root, prompt["output_schema"])
        run_root = Path(context["state_root"]).resolve() / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        attempts: list[dict[str, Any]] = []
        result = None
        selected = None
        for index, model in enumerate(context["route_models"]):
            provider = context["providers"][model["provider"]]
            try:
                if not model["enabled"] or not provider["enabled"]:
                    raise ProviderFailure(
                        "research route contains a disabled model or provider",
                        "capability_transient",
                    )
                if provider["kind"] == "codex_cli":
                    value, transcript = _codex(
                        provider, model, prompt_text, schema_path, [], run_root,
                    )
                elif provider["kind"] in {"openai_compatible", "local_openai_compatible"}:
                    value, transcript = _http(
                        provider, model, prompt_text, context["route"]["max_total_tokens"],
                    )
                else:
                    raise ProviderFailure(
                        "unsupported research-conductor provider", "capability_transient",
                    )
                errors = validate(value, schema)
                if errors:
                    raise ProviderFailure(
                        "research decision failed schema validation: " + "; ".join(errors),
                        "repairable_output", "structured_response_invalid",
                    )
                self._validate_semantics(value, payload["allowed_actions"])
                result = value
                selected = model
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
                    **({"transcript": exc.transcript} if exc.transcript is not None else {}),
                })
                if (
                    index + 1 >= len(context["route_models"])
                    or exc.failure_class not in context["route"]["fallback_failure_classes"]
                ):
                    break
        if result is None or selected is None:
            last = attempts[-1] if attempts else {}
            raise RemoteJobError(
                "research conductor exhausted its Sol route: "
                + last.get("message", "no provider attempt was recorded"),
                failure_class=last.get("failure_class", "capability_transient"),
                code=last.get("failure_code", "provider_capability_unavailable"),
            )
        decision_document = {
            "schema_version": "ninereeds_research_decision_v1",
            "campaign_id": payload["campaign_id"],
            "campaign_number": payload["campaign_number"],
            "lab_id": payload["lab_id"],
            "activation_id": payload["activation_id"],
            "model_id": selected["id"],
            "model_exact_name": selected["exact_name"],
            "allowed_actions": payload["allowed_actions"],
            "observation": payload["observation"],
            **result,
        }
        decision_path, decision_sha, decision_size = _object_file(
            context["state_root"],
            (json.dumps(decision_document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        transcript_document = {
            "schema_version": "ninereeds_research_provider_transcript_v1",
            "activation_id": payload["activation_id"],
            "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            "attempts": attempts,
        }
        transcript_path, transcript_sha, transcript_size = _object_file(
            context["state_root"],
            (json.dumps(transcript_document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        manifest = {
            "campaign_id": payload["campaign_id"],
            "lab_id": payload["lab_id"],
            "activation_id": payload["activation_id"],
            "action": result["action"]["kind"],
            "model_id": selected["id"],
        }
        return {
            "status": "succeeded",
            "action": result["action"],
            "message": result["message"],
            "rationale": result["rationale"],
            "updated_todo": result["updated_todo"],
            "artifacts": [
                _declaration(
                    "research_decision", decision_path, decision_sha, decision_size,
                    {"schema_version": "ninereeds_research_decision_v1", **manifest},
                ),
                _declaration(
                    "provider_transcript", transcript_path, transcript_sha, transcript_size,
                    {"schema_version": "ninereeds_research_provider_transcript_v1", **manifest},
                ),
            ],
        }

    @staticmethod
    def _validate_semantics(value: dict[str, Any], allowed_actions: list[str]) -> None:
        action = value["action"]
        kind = action["kind"]
        if kind not in allowed_actions:
            raise ProviderFailure(
                "research decision selected an action outside the authoritative state boundary",
                "repairable_output", "structured_response_invalid",
            )
        acquisition = action["dataset_acquisition"]
        if kind == "acquire_dataset":
            if acquisition is None:
                raise ProviderFailure(
                    "acquire_dataset omitted its immutable source and adapter contract",
                    "repairable_output", "structured_response_invalid",
                )
            archive = acquisition["archive_format"]
            modality = acquisition["modality"]
            objective = acquisition["objective"]
            structured = acquisition["dataset_format"] != "text"
            invalid_adapter = any((
                (archive in {"zip", "tar"}) != (acquisition["records_member"] is not None),
                acquisition["dataset_format"] == "parquet" and archive != "none",
                modality == "image_text" and archive not in {"zip", "tar"},
                modality == "image_text" and (
                    acquisition["image_field"] is None or acquisition["caption_field"] is None
                ),
                modality == "text" and (
                    acquisition["image_field"] is not None or acquisition["caption_field"] is not None
                ),
                modality == "text" and objective == "prompt_completion" and (
                    acquisition["prompt_field"] is None
                    or acquisition["completion_field"] is None
                ),
                modality == "text" and structured and objective != "prompt_completion"
                and acquisition["text_field"] is None,
            ))
            if invalid_adapter:
                raise ProviderFailure(
                    "acquire_dataset supplied an inconsistent format, archive, modality, or field adapter",
                    "repairable_output", "structured_response_invalid",
                )
        elif acquisition is not None:
            raise ProviderFailure(
                f"{kind} supplied dataset-acquisition-only fields",
                "repairable_output", "structured_response_invalid",
            )
        launch_fields = (
            "experiment_title", "hypothesis", "dataset_id", "epochs",
            "order_policy", "order_seed", "intervention_type", "controls",
        )
        optional_launch_fields = (
            "control_experiment_id", "max_sessions", "max_events_per_session",
            "max_records_per_epoch",
        )
        if kind == "launch_experiment":
            if any(action[name] is None for name in launch_fields):
                raise ProviderFailure(
                    "launch_experiment omitted a required bounded experiment field",
                    "repairable_output", "structured_response_invalid",
                )
            if action["dataset_id"] == "builtin:foundation-visual-3022-v1":
                if (
                    action["max_sessions"] is None
                    or action["max_events_per_session"] is None
                    or action["max_records_per_epoch"] is not None
                    or action["epochs"] != 1
                    or action["order_policy"] != "declared"
                ):
                    raise ProviderFailure(
                        "the frozen bootstrap requires one declared-order epoch and session/event bounds",
                        "repairable_output", "structured_response_invalid",
                    )
                if action["max_events_per_session"] % 10:
                    raise ProviderFailure(
                        "bootstrap event bound must preserve complete ten-image concept blocks",
                        "repairable_output", "structured_response_invalid",
                    )
            elif (
                not action["dataset_id"].startswith("art-")
                or action["max_records_per_epoch"] is None
                or action["max_sessions"] is not None
                or action["max_events_per_session"] is not None
            ):
                raise ProviderFailure(
                    "registered datasets require an artifact id and record exposure instead of bootstrap session bounds",
                    "repairable_output", "structured_response_invalid",
                )
            if (
                action["intervention_type"] != "baseline"
                and action["control_experiment_id"] is None
            ):
                raise ProviderFailure(
                    "a non-baseline intervention must name its exact control experiment",
                    "repairable_output", "structured_response_invalid",
                )
            if action["controls"]["max_fanout"] > action["controls"]["max_degree"]:
                raise ProviderFailure(
                    "experiment max_fanout cannot exceed max_degree",
                    "repairable_output", "structured_response_invalid",
                )
        elif any(action[name] is not None for name in (*launch_fields, *optional_launch_fields)):
            raise ProviderFailure(
                f"{kind} supplied launch-only experiment fields",
                "repairable_output", "structured_response_invalid",
            )
        code_fields = (
            "code_change_title", "code_change_hypothesis", "code_change_objective",
            "code_change_acceptance_criteria", "code_change_scopes",
        )
        if kind == "modify_code":
            if any(action[name] is None for name in code_fields):
                raise ProviderFailure(
                    "modify_code omitted a required bounded code-change field",
                    "repairable_output", "structured_response_invalid",
                )
            if len(set(action["code_change_scopes"])) != len(action["code_change_scopes"]):
                raise ProviderFailure(
                    "modify_code repeated a source scope",
                    "repairable_output", "structured_response_invalid",
                )
        elif any(action[name] is not None for name in code_fields):
            raise ProviderFailure(
                f"{kind} supplied code-change-only fields",
                "repairable_output", "structured_response_invalid",
            )
        conclusion_fields = (
            "campaign_report", "next_campaign_title", "next_campaign_goal",
        )
        if kind == "conclude_campaign":
            if any(action[name] is None for name in conclusion_fields):
                raise ProviderFailure(
                    "campaign conclusion omitted its report or successor goal",
                    "repairable_output", "structured_response_invalid",
                )
        elif any(action[name] is not None for name in conclusion_fields):
            raise ProviderFailure(
                f"{kind} supplied conclusion-only fields",
                "repairable_output", "structured_response_invalid",
            )
