from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.errors import RemoteJobError
from mission_hub.lab import LabStore
from mission_hub.operations_workflow import OperationalResponseCoordinator
from mission_hub.handlers.operations import OperationalResponseHandler, _deterministic_blocker, _notice_contradiction, _response_contradiction
from mission_hub.handlers.visual_provider import ProviderFailure
from mission_hub.store import MissionHubStore, utc_now


REPO = Path(__file__).resolve().parents[1]


def ready(tmp_path: Path):
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    for machine in bundle.machines.values():
        machine["state_root"] = str(tmp_path / machine["id"])
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    return store, bundle


def test_system_notice_queues_exactly_one_configurable_on_call_job(tmp_path: Path) -> None:
    store, bundle = ready(tmp_path)
    thread_id = LabStore(store).system_notice("A notice", "Something happened.")
    coordinator = OperationalResponseCoordinator(store, bundle)
    assert coordinator.tick(actor="test") == 1
    assert coordinator.tick(actor="test") == 0
    with store._connect() as db:
        response = db.execute("SELECT * FROM operational_responses").fetchone()
        job = db.execute("SELECT * FROM jobs WHERE id=?", (response["job_id"],)).fetchone()
    assert response["thread_id"] == thread_id
    assert job["job_type"] == "operations.respond"
    assert job["requested_machine_id"] == "mission-hub"
    assert json.loads(job["input_json"])["subject"] == "A notice"


def test_on_call_pauses_only_for_a_structured_human_blocker(tmp_path: Path) -> None:
    store, bundle = ready(tmp_path)
    coordinator = OperationalResponseCoordinator(store, bundle)
    store.request_pipeline_state("running", actor="test")
    refused_pause = coordinator._act({
        "action": "pause_pipeline", "disposition": "automatic_recovery",
        "human_blocker": None,
    }, actor="test")
    assert refused_pause["applied"] is False
    assert store.pipeline_control()["desired_state"] == "running"
    paused = coordinator._act({
        "action": "pause_pipeline", "disposition": "operator_required",
        "human_blocker": "physical_hardware",
    }, actor="test")
    assert paused["applied"] is True
    assert store.pipeline_control()["desired_state"] == "paused"
    refused = coordinator._act({"action": "operator_required"}, actor="test")
    assert refused["applied"] is False


def test_on_call_does_not_claim_automatic_recovery_for_a_terminal_job(tmp_path: Path) -> None:
    store, bundle = ready(tmp_path)
    job = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="failed-auto-recovery", created_by="test",
        requested_machine_id="mission-hub", approved=True,
    )
    with store.transaction() as db:
        db.execute("UPDATE jobs SET status='failed' WHERE id=?", (job["id"],))

    result = OperationalResponseCoordinator(store, bundle)._act({
        "action": "allow_automatic_recovery", "target_job_id": job["id"],
    }, actor="test")

    assert result["applied"] is False
    assert "remains failed" in result["summary"]
    assert "explicit retry" in result["summary"]


def test_on_call_does_not_claim_no_repair_needed_for_a_terminal_job(tmp_path: Path) -> None:
    store, bundle = ready(tmp_path)
    job = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="failed-no-action", created_by="test",
        requested_machine_id="mission-hub", approved=True,
    )
    with store.transaction() as db:
        db.execute("UPDATE jobs SET status='failed' WHERE id=?", (job["id"],))

    result = OperationalResponseCoordinator(store, bundle)._act({
        "action": "no_action", "disposition": "no_action_needed",
        "target_job_id": job["id"],
    }, actor="test")

    assert result["applied"] is False
    assert "remains failed" in result["summary"]
    assert "repair" in result["summary"]


def test_followup_system_message_invokes_on_call_but_on_call_reply_does_not_recurse(tmp_path: Path) -> None:
    store, bundle = ready(tmp_path)
    lab = LabStore(store)
    thread_id = lab.system_notice("A notice", "First message.")
    lab.add_thread_message(thread_id, "New system information.", sender="mission_hub", actor="mission-hub:test")
    lab.add_thread_message(thread_id, "On-call result.", sender="mission_hub", actor="mission-hub:on-call")
    with store._connect() as db:
        rows = db.execute("SELECT trigger_message_id FROM operational_responses ORDER BY created_at").fetchall()
    assert len(rows) == 2


def test_schema_valid_but_contradictory_recovery_claims_are_rejected() -> None:
    assert _response_contradiction({
        "action": "no_action", "disposition": "repaired", "target_job_id": "job-x",
        "incident_id": "inc-x", "recovery_attempt_id": None, "blocker_reason": None,
    }) is not None
    notice = {"body": "Job: job-x\nRecovery incident: inc-x\nRecovery state: classified (software)\n"}
    assert _notice_contradiction(notice, {
        "action": "no_action", "disposition": "no_action_needed", "target_job_id": "job-x",
        "incident_id": "inc-x", "recovery_attempt_id": None, "blocker_reason": None,
    }) == "a classified recoverable incident requires a repair or structured blocker"


def test_on_call_provider_failure_preserves_matching_machine_actionable_code(tmp_path: Path, monkeypatch) -> None:
    _, bundle = ready(tmp_path)

    def unavailable(*args, **kwargs):
        raise ProviderFailure(
            "temporary local provider outage", "operational_transient",
            "resource_temporarily_unavailable",
        )

    monkeypatch.setattr("mission_hub.handlers.operations._http", unavailable)
    prompt = bundle.prompts[bundle.jobs["operations.respond"]["prompt_id"]]
    context = {
        "prompt": prompt, "release_root": str(REPO), "state_root": str(tmp_path),
        "run": {"id": "run-provider-failure"},
        "route": {"max_total_tokens": 256, "fallback_failure_classes": []},
        "route_models": [{"id": "model-test", "provider": "provider-test", "enabled": True}],
        "providers": {"provider-test": {"kind": "openai_compatible", "enabled": True}},
    }
    with pytest.raises(RemoteJobError) as caught:
        OperationalResponseHandler().execute(
            {"thread_id": "thread-x", "message_id": "message-x"}, context,
        )

    assert caught.value.failure_class == "operational_transient"
    assert caught.value.code == "resource_temporarily_unavailable"


def test_no_usable_visual_candidate_is_a_structured_research_intent_boundary() -> None:
    response = _deterministic_blocker({
        "body": "Reason: independent review found no usable candidate\nDo not retry unchanged.",
    })

    assert response["action"] == "operator_required"
    assert response["human_blocker"] == "unresolved_research_intent"
    assert response["blocker_reason"]["code"] == "new_visual_material_authorization_required"
    assert _response_contradiction(response) is None
