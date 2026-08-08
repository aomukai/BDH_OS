"""Provider-backed, recommendation-only post-campaign handoff fixture."""

from __future__ import annotations

import json
from pathlib import Path

from ..errors import RemoteJobError, SafetyError
from ..schema import load_schema, validate
from .contracts import _declaration, _object_file
from .visual import _verified_inputs
from .visual_provider import ProviderFailure, _codex, _http


class CampaignDecisionHandler:
    def execute(self, payload, context):
        inputs = _verified_inputs(context, payload["evidence_ids"])
        kinds = [item["kind"] for item in inputs]
        if kinds.count("evaluation_report") != 5 or kinds.count("crossmodal_evaluation_report") != 5 or len(inputs) != 10:
            raise SafetyError("post-campaign recommendation requires five text/MRI and five cross-modal terminal reports")
        evidence = []
        for item in inputs:
            raw = Path(item["uri"]).read_text(encoding="utf-8")
            evidence.append({"id": item["id"], "sha256": item["sha256"], "manifest": item["manifest"], "report": json.loads(raw)})
        prompt = context["prompt"]
        prompt_text = prompt["system"].strip() + "\n\n" + prompt["template"].strip() + "\n\nExact campaign evidence:\n" + json.dumps({
            "campaign_id": payload["campaign_id"], "evidence": evidence,
            "allowed_actions": payload["allowed_actions"], "budget": payload["budget"],
            "required_handoff_sections": ["what_we_did", "what_we_observed", "what_we_learned", "unresolved_questions", "recommended_next_step", "foundational_base_recommendation"],
            "authority": "recommendation_only_no_activation_no_promotion",
        }, ensure_ascii=False, sort_keys=True)
        repo = Path(context["release_root"])
        schema_path = repo / prompt["output_schema"]
        schema = load_schema(repo, prompt["output_schema"])
        run_root = Path(context["state_root"]) / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        attempts, result, selected = [], None, None
        for index, model in enumerate(context["route_models"]):
            provider = context["providers"][model["provider"]]
            try:
                if provider["kind"] == "codex_cli":
                    value, transcript = _codex(provider, model, prompt_text, schema_path, [], run_root)
                elif provider["kind"] in {"openai_compatible", "local_openai_compatible"}:
                    value, transcript = _http(provider, model, prompt_text, context["route"]["max_total_tokens"])
                else:
                    raise ProviderFailure("unsupported campaign-planning provider", "capability_transient")
                errors = validate(value, schema)
                if errors: raise ProviderFailure("campaign recommendation failed schema validation: " + "; ".join(errors), "repairable_output")
                result, selected = value, model
                attempts.append({"model_id": model["id"], "status": "succeeded", "transcript": transcript})
                break
            except ProviderFailure as exc:
                attempts.append({"model_id": model["id"], "status": "failed", "failure_class": exc.failure_class, "message": str(exc)})
                if index + 1 >= len(context["route_models"]) or exc.failure_class not in context["route"]["fallback_failure_classes"]: break
        if result is None:
            raise RemoteJobError("campaign recommendation exhausted its provider route", failure_class=attempts[-1].get("failure_class", "capability_transient"), code="provider_capability_unavailable")
        document = {**result, "schema_version": "ninereeds_post_campaign_recommendation_v1", "campaign_id": payload["campaign_id"], "model_id": selected["exact_name"], "evidence_ids": payload["evidence_ids"], "authority": "recommendation_only"}
        path, digest, size = _object_file(context["state_root"], (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
        declaration = _declaration("decision_proposal", path, digest, size, document)
        return {"status": "succeeded", "action": result["action"], "rationale": result["rationale"], "evidence_ids": payload["evidence_ids"], "assumptions": result["assumptions"], "artifacts": [declaration]}
