"""Provider-backed, bounded on-call assessment of operator notices."""

from __future__ import annotations

import json
from pathlib import Path
import re

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
        deterministic = (
            _deterministic_operator_resume(payload)
            or _deterministic_monitoring_incident(payload)
            or _deterministic_queue_expiry(payload)
            or _deterministic_repairable_incident(payload)
            or _deterministic_authoritative_repair(payload)
            or _deterministic_blocker(payload)
        )
        if deterministic is not None:
            errors = validate(deterministic, schema)
            if errors:
                raise RuntimeError("deterministic operational response violates its schema: " + "; ".join(errors))
            document = {
                **deterministic, "schema_version": "ninereeds_operational_response_v1",
                "thread_id": payload["thread_id"], "trigger_message_id": payload["message_id"],
                "model_id": "deterministic-policy-v1", "route_id": context["route"]["id"],
            }
            path, digest, size = _object_file(
                context["state_root"],
                (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
            )
            return {
                **deterministic, "status": "succeeded",
                "artifacts": [_declaration("operational_response", path, digest, size, document)],
            }
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
                    raise ProviderFailure("responder output failed schema validation: " + "; ".join(errors), "repairable_output", "structured_response_invalid")
                contradiction = _response_contradiction(value)
                contradiction = contradiction or _notice_contradiction(payload, value)
                if contradiction:
                    raise ProviderFailure("responder output is operationally contradictory: " + contradiction, "repairable_output", "structured_response_invalid")
                result, selected = value, model
                attempts.append({"model_id": model["id"], "status": "succeeded", "transcript": transcript})
                break
            except ProviderFailure as exc:
                attempts.append({
                    "model_id": model["id"], "status": "failed",
                    "failure_class": exc.failure_class, "failure_code": exc.code,
                    "message": str(exc),
                })
                if index + 1 >= len(context["route_models"]) or exc.failure_class not in context["route"]["fallback_failure_classes"]:
                    break
        if result is None:
            last = attempts[-1] if attempts else {}
            raise RemoteJobError(
                str(last.get("message") or "operational responder exhausted its configured route"),
                failure_class=last.get("failure_class", "capability_transient"),
                code=last.get("failure_code", "provider_capability_unavailable"),
            )
        document = {
            **result, "schema_version": "ninereeds_operational_response_v1",
            "thread_id": payload["thread_id"], "trigger_message_id": payload["message_id"],
            "model_id": selected["exact_name"], "route_id": context["route"]["id"],
        }
        path, digest, size = _object_file(context["state_root"], (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())
        return {**result, "status": "succeeded", "artifacts": [_declaration("operational_response", path, digest, size, document)]}


def _response_contradiction(value: dict) -> str | None:
    action, disposition = value.get("action"), value.get("disposition")
    target, incident = value.get("target_job_id"), value.get("incident_id")
    workflow = value.get("target_workflow_id")
    attempt, blocker = value.get("recovery_attempt_id"), value.get("blocker_reason")
    if action == "no_action" and disposition != "no_action_needed":
        return "no_action requires no_action_needed disposition"
    if action == "allow_automatic_recovery" and disposition != "automatic_recovery":
        return "allow_automatic_recovery requires automatic_recovery disposition"
    if action == "recommission_visual_workflow" and (disposition != "automatic_recovery" or not workflow or blocker):
        return "visual recommission requires automatic_recovery, an exact workflow, and no human blocker"
    if action == "begin_repair" and (disposition != "automatic_recovery" or not target or not incident or attempt or blocker):
        return "begin_repair requires target job and incident, with no completed attempt or blocker"
    if action == "retry_failed_job" and (disposition != "repaired" or not target or not incident or not attempt or blocker):
        return "retry_failed_job requires repaired disposition and exact incident/attempt identities"
    if disposition == "repaired" and action != "retry_failed_job":
        return "repaired disposition requires a verified retry action"
    if disposition == "operator_required" and not blocker:
        return "operator_required requires a machine-readable blocker_reason"
    if disposition != "operator_required" and blocker is not None:
        return "blocker_reason is only valid for operator_required disposition"
    if action in {"pause_pipeline", "operator_required"} and disposition != "operator_required":
        return "human actions require operator_required disposition"
    return None


def _deterministic_blocker(payload: dict) -> dict | None:
    """Recommission a review-exhausted visual workflow without false escalation."""
    body = str(payload.get("body") or "").lower()
    if "independent review found no usable candidate" not in body:
        return None
    workflow = re.search(r"^workflow:\s*(\S+)$", body, re.MULTILINE)
    if workflow is None:
        return None
    result = re.search(r"^review result:\s*(.+)$", body, re.MULTILINE)
    assessment = result.group(1).strip().capitalize() if result else "The exact visual pack is incomplete after independent review."
    return {
        "disposition": "automatic_recovery", "action": "recommission_visual_workflow",
        "assessment": assessment,
        "reasoning": (
            "The preserved review evidence identifies which candidates failed and why. Sol has standing authority "
            "to commission deterministic replacement visual material while preserving the rejected evidence."
        ),
        "target_job_id": None, "target_workflow_id": workflow.group(1),
        "incident_id": None, "recovery_attempt_id": None,
        "human_blocker": None, "blocker_reason": None,
    }


def _deterministic_queue_expiry(payload: dict) -> dict | None:
    """Recover an untouched scheduler-expired Cortex frontier without model drift."""
    body = str(payload.get("body") or "")
    if "Queue condition: queue_age_exceeded" not in body:
        return None
    job = re.search(r"^Job: (\S+)$", body, re.MULTILINE)
    if job is None:
        return None
    return {
        "disposition": "automatic_recovery",
        "action": "allow_automatic_recovery",
        "assessment": "The Cortex evaluation never ran and expired only because it remained queued.",
        "reasoning": (
            "Reauthorize the exact untouched job under the active configuration, preserve its input hash and "
            "successful predecessors, and resume the same workflow without another training run."
        ),
        "target_job_id": job.group(1), "incident_id": None, "recovery_attempt_id": None,
        "target_workflow_id": None,
        "human_blocker": None, "blocker_reason": None,
    }


def _deterministic_monitoring_incident(payload: dict) -> dict | None:
    """Describe an already queued retry without asking the model to reclassify it."""
    body = str(payload.get("body") or "")
    job = re.search(r"^Job: (\S+)$", body, re.MULTILINE)
    incident = re.search(r"^Recovery incident: (\S+)$", body, re.MULTILINE)
    state = re.search(r"^Recovery state: monitoring \(([^)]+)\)$", body, re.MULTILINE)
    if not job or not incident or not state:
        return None
    return {
        "disposition": "automatic_recovery", "action": "allow_automatic_recovery",
        "assessment": "The failed task is already queued for an unchanged retry. No new repair has been started.",
        "reasoning": (
            f"Incident {incident.group(1)} is monitoring the configured retry for {job.group(1)}. "
            "Preserve the failed run and verify the queued successor."
        ),
        "target_job_id": job.group(1), "incident_id": incident.group(1),
        "target_workflow_id": None, "recovery_attempt_id": None,
        "human_blocker": None, "blocker_reason": None,
    }


def _deterministic_operator_resume(payload: dict) -> dict | None:
    """Honor an explicit request to resume a retry identified in thread context."""
    body = str(payload.get("body") or "").lower()
    if not re.search(r"\b(start|restart|resume)\b.{0,40}\bpipeline\b", body):
        return None
    messages = payload.get("context_messages")
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        notice = str(message.get("body") or "") if isinstance(message, dict) else ""
        job = re.search(r"^Job: (\S+)$", notice, re.MULTILINE)
        incident = re.search(r"^Recovery incident: (\S+)$", notice, re.MULTILINE)
        state = re.search(r"^Recovery state: monitoring \(([^)]+)\)$", notice, re.MULTILINE)
        if job and incident and state:
            return {
                "disposition": "automatic_recovery", "action": "allow_automatic_recovery",
                "assessment": "Yes. The failed task is already queued for an unchanged retry, and I’m restarting the pipeline so it can continue.",
                "reasoning": (
                    f"The operator explicitly requested pipeline resume. Incident {incident.group(1)} is already "
                    f"monitoring the configured retry for {job.group(1)}; do not start a duplicate repair."
                ),
                "target_job_id": job.group(1), "incident_id": incident.group(1),
                "target_workflow_id": None, "recovery_attempt_id": None,
                "human_blocker": None, "blocker_reason": None,
            }
    return None


def _deterministic_repairable_incident(payload: dict) -> dict | None:
    """Start bounded repair for an exact, persisted repairable incident."""
    body = str(payload.get("body") or "")
    job = re.search(r"^Job: (\S+)$", body, re.MULTILINE)
    incident = re.search(r"^Recovery incident: (\S+)$", body, re.MULTILINE)
    state = re.search(r"^Recovery state: classified \(([^)]+)\)$", body, re.MULTILINE)
    failure = re.search(r"^Failure: (\S+) \((\S+)\)$", body, re.MULTILINE)
    if not job or not incident or not state or not failure:
        return None
    category = state.group(1)
    if category not in {"software", "configuration", "contract", "infrastructure"}:
        return None
    job_type = re.search(r"^Critical job (\S+) failed\.$", body, re.MULTILINE)
    failure_code = failure.group(1)
    subject = job_type.group(1) if job_type else "The job"
    concrete_causes = {
        "provider_capability_unavailable": (
            f"{subject} could not obtain a model response because the configured provider capability "
            "was unavailable (for example, the selected model was at capacity)."
        ),
        "provider_rate_limited": (
            f"{subject} could not obtain a model response because the provider rate limit was reached."
        ),
        "transport_unavailable": f"{subject} could not reach its configured execution provider.",
        "resource_temporarily_unavailable": f"{subject} stopped because a required local resource was unavailable.",
        "configuration_invalid": f"{subject} could not start with the active Mission Hub configuration.",
        "artifact_contract_invalid": f"{subject} produced evidence that did not satisfy its artifact contract.",
        "output_schema_invalid": f"{subject} returned output that did not satisfy its required schema.",
    }
    assessment = concrete_causes.get(
        failure_code,
        f"{subject} stopped because of {failure_code}; Mission Hub classified it as a repairable {category} failure.",
    )
    return {
        "disposition": "automatic_recovery", "action": "begin_repair",
        "assessment": assessment,
        "reasoning": (
            f"Mission Hub persisted incident {incident.group(1)} as classified and repairable after "
            f"{failure.group(1)}. Preserve its evidence, validate the repair, deploy it, and retry the exact job input."
        ),
        "target_job_id": job.group(1), "incident_id": incident.group(1),
        "target_workflow_id": None, "recovery_attempt_id": None, "human_blocker": None, "blocker_reason": None,
    }


def _deterministic_authoritative_repair(payload: dict) -> dict | None:
    """Re-enter an exhausted machine-repairable incident under Sol's authority."""
    body = str(payload.get("body") or "")
    job = re.search(r"^Job: (\S+)$", body, re.MULTILINE)
    incident = re.search(r"^(?:Recovery incident|Incident): (\S+)$", body, re.MULTILINE)
    state = re.search(r"^Recovery state: (blocked|escalated)(?: \([^)]+\))?$", body, re.MULTILINE)
    exhausted = "Recovery for " in body and " exhausted its autonomous budget." in body
    if not job or not incident or (not state and not exhausted):
        return None
    lowered = body.lower()
    human_only = {
        "physical_hardware": "physical hardware intervention is required",
        "unavailable_credentials": "credentials unavailable to the machine are required",
        "external_budget_or_legal_authority": "external budget or legal authority is required",
        "irreversible_evidence_destruction": "irreversible evidence destruction requires explicit authorization",
    }
    for blocker, explanation in human_only.items():
        if blocker in lowered:
            return {
                "disposition": "operator_required", "action": "operator_required",
                "assessment": explanation.capitalize() + ".",
                "reasoning": "The next act crosses a genuine human-only authority or physical boundary.",
                "target_job_id": job.group(1), "incident_id": incident.group(1),
                "target_workflow_id": None, "recovery_attempt_id": None,
                "human_blocker": blocker,
                "blocker_reason": {"code": blocker, "detail": explanation},
            }
    failure = re.search(r"^(?:Failure|Last failure): (\S+)(?: \([^)]+\))?$", body, re.MULTILINE)
    code = failure.group(1) if failure else "exhausted_recovery"
    return {
        "disposition": "automatic_recovery", "action": "begin_repair",
        "assessment": (
            "The automatic attempt ceiling was reached, but the underlying problem is still machine-repairable. "
            "I authorized another evidence-preserving repair attempt."
        ),
        "reasoning": (
            f"Incident {incident.group(1)} stopped after {code}. Retry ceilings bound unattended machinery; "
            "they do not overrule a principal-tier operational decision. Preserve all earlier attempts, repair "
            "the cause, validate and deploy the change, then retry the exact immutable job."
        ),
        "target_job_id": job.group(1), "incident_id": incident.group(1),
        "target_workflow_id": None, "recovery_attempt_id": None,
        "human_blocker": None, "blocker_reason": None,
    }
def _notice_contradiction(payload: dict, value: dict) -> str | None:
    body = str(payload.get("body", ""))
    incident = re.search(r"^Recovery incident: (\S+)$", body, re.MULTILINE)
    job = re.search(r"^Job: (\S+)$", body, re.MULTILINE)
    state = re.search(r"^Recovery state: (\S+)", body, re.MULTILINE)
    if job and value.get("target_job_id") != job.group(1):
        return "response does not name the exact job from the notice"
    if not incident:
        return None
    if value.get("incident_id") != incident.group(1) or not job or value.get("target_job_id") != job.group(1):
        return "response does not name the exact persisted incident and job from the notice"
    recovery_state = state.group(1) if state else "unknown"
    if recovery_state == "classified" and value.get("action") not in {"begin_repair", "operator_required", "pause_pipeline"}:
        return "a classified recoverable incident requires a repair or structured blocker"
    if recovery_state == "monitoring" and value.get("action") != "allow_automatic_recovery":
        return "a deterministic retry already in progress must be verified as automatic recovery"
    if recovery_state in {"blocked", "escalated"} and value.get("action") not in {
        "begin_repair", "operator_required", "pause_pipeline",
    }:
        return "a blocked or exhausted incident requires authorized repair or a genuine human-only blocker"
    return None
