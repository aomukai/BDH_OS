from __future__ import annotations

import json
import subprocess
from pathlib import Path

from training.pipeline.control.emergency_recovery import EmergencyRecoveryPolicy


ROOT = Path(__file__).resolve().parents[1]


class NoticeStore:
    def __init__(self) -> None:
        self.notices: list[dict] = []

    def write_system_notice(self, event_id, title, body, *, metadata=None):
        self.notices.append(
            {
                "event_id": event_id,
                "title": title,
                "body": body,
                "metadata": metadata,
            }
        )
        return self.notices[-1]


def decision(action: str = "retry_supervisor") -> str:
    return json.dumps(
        {
            "action": action,
            "rationale": "Retry the idempotent reconciliation pass.",
            "user_message": None,
            "budget_extension": None,
        }
    )


def incident() -> dict:
    return {
        "schema_version": "ninereeds_orchestrator_incident_v1",
        "errors": [
            {
                "plan_id": "plan-test",
                "error_type": "OSError",
                "error": "temporary sync failure",
            }
        ],
        "campaign": None,
        "current": None,
    }


def test_emergency_notifies_then_calls_openai_sol(tmp_path: Path) -> None:
    notices = NoticeStore()
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=decision(), stderr="")

    policy = EmergencyRecoveryPolicy(
        tmp_path / "control",
        repo_root=ROOT,
        message_store=notices,  # type: ignore[arg-type]
        command_runner=run,
    )

    result = policy.handle(incident(), campaign_controller=None)

    assert result["called"] is True
    assert result["provider"] == "openai"
    assert result["action"] == "retry_supervisor"
    assert notices.notices[0]["title"] == "Emergency: SOL was called"
    assert notices.notices[1]["title"] == "SOL restarted orchestration"
    assert "temporary sync failure" in notices.notices[1]["body"]
    assert "No checkpoint or weights were changed" in notices.notices[1]["body"]
    assert notices.notices[1]["metadata"]["recovery_succeeded"] is True
    assert "gpt-5.6-sol" in calls[0][0]
    assert "read-only" in calls[0][0]
    assert (tmp_path / "control/plans/.wake").exists()

    repeated = policy.handle(incident(), campaign_controller=None)
    assert repeated == {"called": False, "action": "already_escalated"}
    assert len(calls) == 1
    assert len(notices.notices) == 2


def test_openai_availability_failure_falls_back_to_openrouter_sol(
    tmp_path: Path, monkeypatch
) -> None:
    notices = NoticeStore()
    requests = []
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    def run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="rate limit exceeded",
        )

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": decision()}}]}
            ).encode("utf-8")

    def opener(request, **kwargs):
        requests.append(json.loads(request.data.decode("utf-8")))
        return Response()

    policy = EmergencyRecoveryPolicy(
        tmp_path / "control",
        repo_root=ROOT,
        message_store=notices,  # type: ignore[arg-type]
        command_runner=run,
        remote_opener=opener,
    )

    result = policy.handle(incident(), campaign_controller=None)

    assert result["provider"] == "openrouter"
    assert result["action"] == "retry_supervisor"
    assert requests[0]["model"] == "openai/gpt-5.6-sol"
    assert requests[0]["reasoning"] == {"effort": "high", "exclude": True}
    assert "max_tokens" not in requests[0]
    assert len(notices.notices) == 2
    assert notices.notices[1]["title"] == "SOL restarted orchestration"


def test_failed_recovery_application_explains_the_outcome(tmp_path: Path) -> None:
    notices = NoticeStore()

    def run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=decision("create_recovery_boundary"),
            stderr="",
        )

    policy = EmergencyRecoveryPolicy(
        tmp_path / "control",
        repo_root=ROOT,
        message_store=notices,  # type: ignore[arg-type]
        command_runner=run,
    )

    result = policy.handle(incident(), campaign_controller=None)

    assert result["action"] == "failed"
    assert result["error"] == "no campaign controller is configured"
    assert notices.notices[1]["title"] == "SOL recovery did not apply"
    assert "SOL's proposed recovery was rejected" in notices.notices[1]["body"]
    assert notices.notices[1]["metadata"]["recovery_succeeded"] is False


def test_technical_sol_failure_does_not_consume_binding_decision(tmp_path: Path) -> None:
    notices = NoticeStore()
    attempts = 0

    def run(command, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="invalid structured-output schema",
            )
        return subprocess.CompletedProcess(command, 0, stdout=decision(), stderr="")

    policy = EmergencyRecoveryPolicy(
        tmp_path / "control",
        repo_root=ROOT,
        message_store=notices,  # type: ignore[arg-type]
        command_runner=run,
    )

    first = policy.handle(incident(), campaign_controller=None)
    second = policy.handle(incident(), campaign_controller=None)

    assert first["decision"] is None
    assert second["action"] == "retry_supervisor"
    assert attempts == 2
    assert notices.notices[-1]["title"] == "SOL restarted orchestration"
    assert notices.notices[-1]["event_id"].endswith(":retry_supervisor")


def test_budget_review_expands_silently_and_resumes_campaign(tmp_path: Path) -> None:
    notices = NoticeStore()
    output = json.dumps(
        {
            "action": "expand_campaign_budget",
            "rationale": "The remaining experiments are likely to add information.",
            "user_message": None,
            "budget_extension": {
                "strategic_boundaries": 128,
                "phase_blocks": 0,
                "executor_jobs": 128,
                "trainer_sessions": 0,
            },
        }
    )

    def run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    class Controller:
        def __init__(self):
            self.calls = []

        def extend_budgets(self, requested, *, reason):
            self.calls.append(("extend", requested, reason))

        def set_status(self, status, reason):
            self.calls.append(("status", status, reason))

    controller = Controller()
    policy = EmergencyRecoveryPolicy(
        tmp_path / "control",
        repo_root=ROOT,
        message_store=notices,  # type: ignore[arg-type]
        command_runner=run,
    )
    value = incident()
    value["incident_type"] = "campaign_budget"

    result = policy.handle(value, campaign_controller=controller)  # type: ignore[arg-type]

    assert result["action"] == "expand_campaign_budget"
    assert controller.calls[0][1]["strategic_boundaries"] == 128
    assert controller.calls[1][1] == "running"
    assert notices.notices == []
