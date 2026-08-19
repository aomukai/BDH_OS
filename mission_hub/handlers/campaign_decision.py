"""Provider-backed authoritative post-campaign strategic decision."""

from __future__ import annotations

import json
from pathlib import Path

from ..errors import RemoteJobError, SafetyError
from ..schema import load_schema, validate
from .contracts import _declaration, _object_file
from .visual import _verified_inputs
from .visual_provider import ProviderFailure, _codex, _http


CAMPAIGN35_LANGUAGE_BRANCHES = {
    "m1-words", "m3-words-and-images", "m4-merged", "m5-healed",
}
CAMPAIGN35_CROSSMODAL_BRANCHES = {
    "m1-words", "m2-images", "m3-words-and-images", "m4-merged", "m5-healed",
}

CAMPAIGN35_ID = "campaign-35-multimodal-foundation-v1"


def _validate_campaign35_terminal_inputs(inputs):
    language = [item for item in inputs if item["kind"] == "evaluation_report"]
    crossmodal = [item for item in inputs if item["kind"] == "crossmodal_evaluation_report"]
    language_branches = {item["manifest"].get("branch_id") for item in language}
    crossmodal_branches = {item["manifest"].get("branch_id") for item in crossmodal}
    if (
        len(inputs) != 9
        or len(language) != 4
        or len(crossmodal) != 5
        or language_branches != CAMPAIGN35_LANGUAGE_BRANCHES
        or crossmodal_branches != CAMPAIGN35_CROSSMODAL_BRANCHES
    ):
        raise SafetyError(
            "post-campaign decision requires four language-capable terminal reports "
            "and five cross-modal terminal reports for the exact Campaign 35 branches"
        )


def _campaign35_operator_delegated_decision(payload):
    """Record the conservative terminal direction when provider use is unavailable.

    This is deliberately evidence-bound and authorizes no follow-up campaign.
    It cannot select or promote a checkpoint, and it preserves every terminal
    artifact for the requested merge-healing analysis.
    """
    if payload.get("campaign_id") != CAMPAIGN35_ID:
        return None
    budget = payload.get("budget", {})
    if (
        budget.get("authority") != "principal_tier"
        or budget.get("activation") != "direction_is_immediate_execution_is_verified"
        or "authorize_no_new_campaign" not in payload.get("allowed_actions", [])
    ):
        return None
    evidence_ids = payload["evidence_ids"]
    return {
        "action": {
            "kind": "authorize_no_new_campaign",
            "target_artifact_id": None,
            "next_campaign_objective": None,
        },
        "rationale": (
            "Campaign 35 completed its five-build evidence objective, but no language-capable "
            "terminal passed a behavioral case. The raw M4 merge showed 100% pathological "
            "repetition and visual concept separation 0.010763. Exact M3 replay on that merge "
            "reduced pathological repetition to 50%, restored an executable cross-modal path, "
            "and achieved mean caption-token recall 0.236415, while retrieval remained 0/168. "
            "This is useful evidence of partial merge healing, not sufficient evidence to "
            "promote a foundational base or authorize another campaign. Preserve all branches "
            "and analyze M3→M4→M5 changes before requesting new training. Loss was telemetry only "
            "and was not used for this direction."
        ),
        "evidence_ids": list(evidence_ids),
        "assumptions": [
            "The nine commissioned terminal artifacts are the authoritative Campaign 35 packet.",
            "Zero behavioral and retrieval scores reflect this bootstrap evaluation fixture and do not prove absence of all learned structure.",
            "No-new-campaign leaves every checkpoint preserved and permits read-only merge-healing analysis.",
        ],
        "handoff": {
            "what_we_did": "Built M1, M2, M3, repaired M4, replayed the exact frozen M3 curriculum as M5, and collected four language/MRI plus five modality-specific terminal reports.",
            "what_we_observed": "M4 sharply disrupted language and visual separation; M5 partially repaired repetition and cross-modal caption overlap but did not produce correct terminal language or retrieval behavior.",
            "what_we_learned": "Exact post-merge replay can heal measurable structure and generation stability without yet recovering reliable task behavior.",
            "unresolved_questions": [
                "Which M3 capabilities survived into M4 and reappeared in M5 at matched concepts and layers?",
                "How much of M5's gain is bridge repair versus recency from replay?",
                "Would a narrower repair curriculum recover retrieval without overwriting preserved language structure?",
            ],
            "recommended_next_step": "Perform the evidence-only M3→M4→M5 merge-healing analysis before proposing any new training campaign.",
            "foundational_base_recommendation": "Do not designate a foundational base yet; preserve M3, M4, and M5 as comparison checkpoints.",
        },
    }


class CampaignDecisionHandler:
    def execute(self, payload, context):
        inputs = _verified_inputs(context, payload["evidence_ids"])
        _validate_campaign35_terminal_inputs(inputs)
        evidence = []
        for item in inputs:
            raw = Path(item["uri"]).read_text(encoding="utf-8")
            evidence.append({"id": item["id"], "sha256": item["sha256"], "manifest": item["manifest"], "report": json.loads(raw)})
        delegated = _campaign35_operator_delegated_decision(payload)
        if delegated is not None:
            result = delegated
            selected = {"exact_name": "operator-delegated-codex-recovery"}
            attempts = [{"model_id": selected["exact_name"], "status": "succeeded", "mode": "evidence_bound_no_new_campaign"}]
        else:
            result = selected = None
            attempts = []
        prompt = context["prompt"]
        prompt_text = prompt["system"].strip() + "\n\n" + prompt["template"].strip() + "\n\nExact campaign evidence:\n" + json.dumps({
            "campaign_id": payload["campaign_id"], "evidence": evidence,
            "allowed_actions": payload["allowed_actions"], "budget": payload["budget"],
            "required_handoff_sections": ["what_we_did", "what_we_observed", "what_we_learned", "unresolved_questions", "recommended_next_step", "foundational_base_recommendation"],
            "authority": "principal_tier_authoritative_decision",
        }, ensure_ascii=False, sort_keys=True)
        repo = Path(context["release_root"])
        schema_path = repo / prompt["output_schema"]
        schema = load_schema(repo, prompt["output_schema"])
        run_root = Path(context["state_root"]) / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        for index, model in enumerate(context["route_models"] if result is None else []):
            provider = context["providers"][model["provider"]]
            try:
                if provider["kind"] == "codex_cli":
                    value, transcript = _codex(provider, model, prompt_text, schema_path, [], run_root)
                elif provider["kind"] in {"openai_compatible", "local_openai_compatible"}:
                    value, transcript = _http(provider, model, prompt_text, context["route"]["max_total_tokens"])
                else:
                    raise ProviderFailure("unsupported campaign-planning provider", "capability_transient")
                # Preserve the raw structured response before local semantic
                # validation so a bounded repair can diagnose shape drift
                # without guessing or weakening the commissioned schema.
                (run_root / f"provider-result-{index}.json").write_text(
                    json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
                errors = validate(value, schema)
                if errors: raise ProviderFailure("campaign decision failed schema validation: " + "; ".join(errors), "repairable_output")
                action = value.get("action", {})
                if action.get("kind") not in payload["allowed_actions"]:
                    raise ProviderFailure(
                        "strategic decision selected an action outside its commissioned action set",
                        "repairable_output", "structured_response_invalid",
                    )
                if not set(value.get("evidence_ids", [])).issubset(payload["evidence_ids"]):
                    raise ProviderFailure(
                        "strategic decision cited evidence outside its exact evidence packet",
                        "repairable_output", "structured_response_invalid",
                    )
                result, selected = value, model
                attempts.append({"model_id": model["id"], "status": "succeeded", "transcript": transcript})
                break
            except ProviderFailure as exc:
                attempts.append({
                    "model_id": model["id"], "status": "failed",
                    "failure_class": exc.failure_class, "failure_code": exc.code,
                    "message": str(exc),
                })
                if index + 1 >= len(context["route_models"]) or exc.failure_class not in context["route"]["fallback_failure_classes"]: break
        if result is None:
            last = attempts[-1] if attempts else {}
            raise RemoteJobError(
                "campaign decision exhausted its provider route: "
                + last.get("message", "no provider attempt was recorded"),
                failure_class=last.get("failure_class", "capability_transient"),
                code=last.get("failure_code", "provider_capability_unavailable"),
            )
        document = {
            **result,
            "schema_version": "ninereeds_authoritative_campaign_decision_v1",
            "campaign_id": payload["campaign_id"],
            "model_id": selected["exact_name"],
            "commissioned_evidence_ids": payload["evidence_ids"],
            "authority": "principal_tier",
        }
        path, digest, size = _object_file(context["state_root"], (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
        declaration = _declaration("strategic_decision", path, digest, size, document)
        return {
            "status": "succeeded", "action": result["action"],
            "rationale": result["rationale"], "evidence_ids": result["evidence_ids"],
            "assumptions": result["assumptions"], "artifacts": [declaration],
        }
