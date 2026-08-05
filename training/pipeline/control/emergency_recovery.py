from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lab.backend.config import LabConfig
from lab.backend.messages.store import MessageStore

from .campaign_controller import CampaignController, CampaignError


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_SOL_MODEL = "openai/gpt-5.6-sol"
OPENAI_UNAVAILABLE_MARKERS = (
    "rate limit",
    "rate_limit",
    "usage limit",
    "quota",
    "429",
    "service unavailable",
    "temporarily unavailable",
    "timeout",
    "timed out",
    "connection",
    "network",
    "503",
    "502",
)


class EmergencyRecoveryError(RuntimeError):
    pass


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_env_value(repo_root: Path, key: str) -> str | None:
    value = os.environ.get(key)
    if value:
        return value
    for path in (Path("/home/aomukai/.config/ninereeds/provider.env"), repo_root / ".env"):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            if raw.lstrip().startswith("#") or "=" not in raw:
                continue
            name, candidate = raw.split("=", 1)
            if name.strip() == key:
                return candidate.strip().strip("\"'") or None
    return None


class EmergencyRecoveryPolicy:
    """Escalate repeated orchestration failures to a schema-bound SOL decision."""

    def __init__(
        self,
        control_root: Path,
        *,
        repo_root: Path,
        message_store: MessageStore | None = None,
        codex_executable: str = "/home/aomukai/.local/bin/codex",
        codex_model: str = "gpt-5.6-sol",
        openrouter_model: str = OPENROUTER_SOL_MODEL,
        timeout_seconds: int = 1200,
        command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        remote_opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.control_root = control_root.resolve()
        self.repo_root = repo_root.resolve()
        self.state_path = self.control_root / "emergency/state.json"
        self.schema_path = (
            self.repo_root / "training/pipeline/emergency_recovery_schema.json"
        )
        self.message_store = message_store or MessageStore(LabConfig.from_env())
        self.codex_executable = codex_executable
        self.codex_model = codex_model
        self.openrouter_model = openrouter_model
        self.timeout_seconds = timeout_seconds
        self.command_runner = command_runner
        self.remote_opener = remote_opener

    def handle(
        self,
        incident: dict[str, Any],
        *,
        campaign_controller: CampaignController | None,
    ) -> dict[str, Any]:
        fingerprint = hashlib.sha256(
            json.dumps(incident, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        previous = self._read_state()
        # A successful adjudication is idempotent. A provider/schema/transport
        # failure is only a technical attempt and must never consume the one
        # binding SOL decision for this incident.
        if (
            previous.get("fingerprint") == fingerprint
            and previous.get("error") is None
            and previous.get("decision") is not None
        ):
            return {"called": False, "action": "already_escalated"}

        summary = self._summary(incident)
        budget_review = incident.get("incident_type") == "campaign_budget"
        if not budget_review:
            self.message_store.write_system_notice(
                f"orchestrator-sol-called:{fingerprint}",
                "Emergency: SOL was called",
                (
                    "The orchestrator's immediate recovery attempt failed, so SOL was "
                    f"called automatically.\n\nObserved problem: {summary}"
                ),
                metadata={"incident_fingerprint": fingerprint},
            )

        provider = "openai"
        try:
            decision = self._call_openai(incident)
        except EmergencyRecoveryError as exc:
            if not self._openai_unavailable(str(exc)):
                result = self._record(
                    fingerprint, incident, provider, None, error=str(exc)
                )
                self._notify_result(
                    fingerprint,
                    summary=summary,
                    provider=provider,
                    decision=None,
                    action=None,
                    error=str(exc),
                )
                return {"called": True, "provider": provider, **result}
            provider = "openrouter"
            try:
                decision = self._call_openrouter(incident)
            except EmergencyRecoveryError as fallback_exc:
                result = self._record(
                    fingerprint, incident, provider, None, error=str(fallback_exc)
                )
                self._notify_result(
                    fingerprint,
                    summary=summary,
                    provider=provider,
                    decision=None,
                    action=None,
                    error=str(fallback_exc),
                )
                return {"called": True, "provider": provider, **result}

        try:
            action = self._apply(decision, campaign_controller=campaign_controller)
        except (EmergencyRecoveryError, CampaignError, OSError) as exc:
            result = self._record(
                fingerprint, incident, provider, decision, error=str(exc)
            )
            self._notify_result(
                fingerprint,
                summary=summary,
                provider=provider,
                decision=decision,
                action="failed",
                error=str(exc),
            )
            return {"called": True, "provider": provider, "action": "failed", **result}
        result = self._record(fingerprint, incident, provider, decision, error=None)
        if not budget_review or action != "expand_campaign_budget":
            self._notify_result(
                fingerprint,
                summary=summary,
                provider=provider,
                decision=decision,
                action=action,
                error=None,
            )
        return {"called": True, "provider": provider, "action": action, **result}

    def _notify_result(
        self,
        fingerprint: str,
        *,
        summary: str,
        provider: str,
        decision: dict[str, Any] | None,
        action: str | None,
        error: str | None,
    ) -> None:
        if decision is None:
            title = "SOL recovery failed"
            explanation = "SOL could not return a usable recovery decision."
            outcome = f"The campaign was not changed. Error: {self._brief(error)}"
        else:
            explanation = self._brief(
                decision.get("user_message") or decision.get("rationale")
            )
            if error is not None or action == "failed":
                title = "SOL recovery did not apply"
                outcome = (
                    "SOL's proposed recovery was rejected, so it did not change the "
                    f"campaign. Error: {self._brief(error)}"
                )
            elif action == "create_recovery_boundary":
                title = "SOL recovered the orchestrator"
                outcome = (
                    "A fresh strategic boundary was created and the campaign can "
                    "continue from its preserved state."
                )
            elif action == "retry_supervisor":
                title = "SOL restarted orchestration"
                outcome = (
                    "A new idempotent supervisor pass was queued. No checkpoint or "
                    "weights were changed by SOL."
                )
            elif action == "expand_campaign_budget":
                title = "SOL expanded the campaign budget"
                outcome = (
                    "The research allowance was increased and orchestration resumed. "
                    "The governance decision did not itself change model weights."
                )
            elif action in {
                "continue_as_proposed",
                "continue_with_conditions",
                "require_replan",
                "start_new_branch",
                "terminate_branch",
            }:
                title = "SOL adjudicated an adversarial review"
                outcome = (
                    f"SOL selected {action}. The decision was recorded as governance "
                    "and did not itself change model weights."
                )
            else:
                title = "SOL requested your help"
                outcome = (
                    "SOL did not change the campaign and requested human review."
                )
        self.message_store.write_system_notice(
            # Keep a failed technical invocation and the later binding result as
            # distinct inbox events. Otherwise the idempotent message store can
            # hide the judgment that eventually succeeded.
            f"orchestrator-sol-result:{fingerprint}:{action or 'technical-failure'}",
            title,
            (
                f"Problem: {summary}\n\n"
                f"SOL's assessment: {explanation}\n\n"
                f"Outcome: {outcome}"
            ),
            metadata={
                "incident_fingerprint": fingerprint,
                "provider": provider,
                "recovery_action": action,
                "recovery_succeeded": error is None and action != "failed",
            },
        )

    def _call_openai(self, incident: dict[str, Any]) -> dict[str, Any]:
        command = [
            self.codex_executable,
            "--ask-for-approval",
            "never",
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--model",
            self.codex_model,
            "--sandbox",
            "read-only",
            "--output-schema",
            str(self.schema_path),
            "--color",
            "never",
            "-C",
            str(self.repo_root),
            "-",
        ]
        try:
            completed = self.command_runner(
                command,
                input=self._prompt(incident),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise EmergencyRecoveryError(f"OpenAI SOL invocation failed: {exc}") from exc
        if completed.returncode != 0:
            detail = "\n".join((completed.stderr or "", completed.stdout or ""))[-3000:]
            raise EmergencyRecoveryError(
                f"OpenAI SOL exited {completed.returncode}: {detail.strip()}"
            )
        return self._validate_decision_text(completed.stdout)

    def _call_openrouter(self, incident: dict[str, Any]) -> dict[str, Any]:
        key = _load_env_value(self.repo_root, "OPENROUTER_API_KEY")
        if not key:
            raise EmergencyRecoveryError("OPENROUTER_API_KEY is unavailable")
        schema = self.schema_path.read_text(encoding="utf-8")
        body = {
            "model": self.openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are SOL, the emergency recovery controller for Ninereeds. "
                        "Return exactly one schema-conforming JSON object."
                    ),
                },
                {
                    "role": "user",
                    "content": self._prompt(incident) + "\n\nJSON schema:\n" + schema,
                },
            ],
            "reasoning": {"effort": "high", "exclude": True},
            "response_format": {"type": "json_object"},
        }
        request = Request(
            OPENROUTER_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "X-Title": "Ninereeds Emergency Recovery",
            },
            method="POST",
        )
        try:
            with self.remote_opener(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise EmergencyRecoveryError(f"OpenRouter SOL invocation failed: {exc}") from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise EmergencyRecoveryError("OpenRouter SOL returned an invalid response") from exc
        return self._validate_decision_text(content)

    def _prompt(self, incident: dict[str, Any]) -> str:
        if incident.get("incident_type") == "campaign_budget":
            return (
                "The autonomous research campaign reached a configured research budget. "
                "This is governance, not a technical or teaching failure. Review the completed "
                "research outcomes, technical attempts, objective, deadline, and remaining work. "
                "Choose expand_campaign_budget only when more research is likely to produce new "
                "information. budget_extension must contain all four absolute ceilings, may only increase "
                "current values, and must stay at or below 1000. Otherwise choose request_human "
                "and explain why expansion is refused. Loss is technical telemetry only and must "
                "never be used to judge model quality or research success.\n\nINCIDENT\n"
                + json.dumps(incident, ensure_ascii=False, indent=2)
            )
        if incident.get("incident_type") == "adversarial_review":
            return (
                "An advocatus diaboli rejected the strategic orchestrator's defence. "
                "Adjudicate the disagreement from the recorded actions, behavioral evidence, "
                "critique, and defence. Choose one of continue_as_proposed, "
                "continue_with_conditions, require_replan, start_new_branch, pause_for_human, "
                "or terminate_branch. Your rationale is binding and must state concrete "
                "conditions when applicable. Do not use loss magnitude or direction to judge "
                "model quality; loss is technical telemetry only.\n\nINCIDENT\n"
                + json.dumps(incident, ensure_ascii=False, indent=2)
            )
        return (
            "An orchestration problem survived one immediate deterministic recovery "
            "attempt. Diagnose only from the incident snapshot below and choose the "
            "smallest safe recovery action. create_recovery_boundary is valid only for "
            "a blocked autonomous campaign whose immutable current boundary cannot be "
            "reused. retry_supervisor requests another idempotent reconciliation pass. "
            "Use request_human when neither action is safe. Never claim that weights "
            "changed unless the snapshot says so.\n\nINCIDENT\n"
            + json.dumps(incident, ensure_ascii=False, indent=2)
        )

    @staticmethod
    def _validate_decision_text(text: str) -> dict[str, Any]:
        try:
            value = json.loads(text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise EmergencyRecoveryError("SOL returned invalid JSON") from exc
        if not isinstance(value, dict) or frozenset(value) not in {
            frozenset({"action", "rationale", "user_message"}),
            frozenset({"action", "rationale", "user_message", "budget_extension"}),
        }:
            raise EmergencyRecoveryError("SOL decision fields do not match the schema")
        if value["action"] not in {
            "create_recovery_boundary",
            "retry_supervisor",
            "expand_campaign_budget",
            "continue_as_proposed",
            "continue_with_conditions",
            "require_replan",
            "start_new_branch",
            "pause_for_human",
            "terminate_branch",
            "request_human",
        }:
            raise EmergencyRecoveryError("SOL returned an unsupported recovery action")
        if not isinstance(value["rationale"], str) or not value["rationale"].strip():
            raise EmergencyRecoveryError("SOL rationale is empty")
        if value["user_message"] is not None and not isinstance(
            value["user_message"], str
        ):
            raise EmergencyRecoveryError("SOL user_message is invalid")
        extension = value.get("budget_extension")
        if value["action"] == "expand_campaign_budget":
            valid = {"strategic_boundaries", "phase_blocks", "executor_jobs", "trainer_sessions"}
            if (
                not isinstance(extension, dict)
                or not extension
                or not set(extension).issubset(valid)
                or any(
                    isinstance(amount, bool)
                    or not isinstance(amount, int)
                    or not 0 <= amount <= 1_000
                    for amount in extension.values()
                )
            ):
                raise EmergencyRecoveryError("SOL budget extension is invalid")
        elif extension is not None:
            raise EmergencyRecoveryError(
                "budget_extension is valid only for expand_campaign_budget"
            )
        return value

    def _apply(
        self,
        decision: dict[str, Any],
        *,
        campaign_controller: CampaignController | None,
    ) -> str:
        action = decision["action"]
        if action == "create_recovery_boundary":
            if campaign_controller is None:
                raise EmergencyRecoveryError("no campaign controller is configured")
            campaign_controller.recover_from_emergency(decision["rationale"])
            return action
        if action == "retry_supervisor":
            wake = self.control_root / "plans/.wake"
            wake.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            wake.touch()
        if action == "expand_campaign_budget":
            if campaign_controller is None:
                raise EmergencyRecoveryError("no campaign controller is configured")
            campaign_controller.extend_budgets(
                decision["budget_extension"],
                reason=f"SOL budget adjudication: {decision['rationale']}",
            )
            campaign_controller.set_status(
                "running",
                "SOL approved an expanded research allowance.",
            )
            wake = self.control_root / "plans/.wake"
            wake.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            wake.touch()
        if action in {
            "continue_as_proposed",
            "continue_with_conditions",
            "require_replan",
            "start_new_branch",
            "pause_for_human",
            "terminate_branch",
        }:
            if campaign_controller is None:
                raise EmergencyRecoveryError("no campaign controller is configured")
            campaign_controller.apply_governance_decision(
                action,
                decision["rationale"],
            )
            if action not in {"pause_for_human", "terminate_branch"}:
                wake = self.control_root / "plans/.wake"
                wake.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                wake.touch()
        if action == "request_human" and campaign_controller is not None:
            campaign_controller.apply_governance_decision(
                "pause_for_human",
                decision["rationale"],
            )
        return action

    def _record(
        self,
        fingerprint: str,
        incident: dict[str, Any],
        provider: str,
        decision: dict[str, Any] | None,
        *,
        error: str | None,
    ) -> dict[str, Any]:
        state = {
            "schema_version": "ninereeds_emergency_recovery_v1",
            "fingerprint": fingerprint,
            "observed_at": time.time(),
            "provider": provider,
            "incident": incident,
            "decision": decision,
            "error": error,
        }
        _atomic_json(self.state_path, state)
        return {"decision": decision, "error": error}

    def _read_state(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _openai_unavailable(error: str) -> bool:
        lowered = error.lower()
        return any(marker in lowered for marker in OPENAI_UNAVAILABLE_MARKERS)

    @staticmethod
    def _summary(incident: dict[str, Any]) -> str:
        review = incident.get("adversarial_review")
        if isinstance(review, dict):
            verdict = review.get("verdict")
            rationale = verdict.get("rationale") if isinstance(verdict, dict) else None
            return (
                f"Advocatus rejected {review.get('review_id', 'an adversarial review')}: "
                f"{rationale or 'the orchestrator defence left material objections unresolved'}"
            )[:800]
        errors = incident.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                return re.sub(r"\s+", " ", str(first.get("error") or first))[:800]
        campaign = incident.get("campaign")
        if isinstance(campaign, dict):
            return str(campaign.get("stop_reason") or campaign.get("status"))[:800]
        return "Persistent orchestration failure"

    @staticmethod
    def _brief(value: Any, limit: int = 1200) -> str:
        text = re.sub(r"\s+", " ", str(value or "No additional detail was provided."))
        return text[:limit]
