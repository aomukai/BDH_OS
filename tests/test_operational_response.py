from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.errors import RemoteJobError
from mission_hub.lab import LabStore
from mission_hub.operations_workflow import OperationalResponseCoordinator, _human_on_call_failure_message, _human_on_call_message
from mission_hub.handlers.operations import OperationalResponseHandler, _deterministic_blocker, _deterministic_queue_expiry, _deterministic_repairable_incident, _notice_contradiction, _response_contradiction
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


def test_failed_on_call_job_posts_an_explanation_without_false_human_escalation(tmp_path: Path) -> None:
    store, bundle = ready(tmp_path)
    thread_id = LabStore(store).system_notice("A notice", "Something happened.")
    coordinator = OperationalResponseCoordinator(store, bundle)
    assert coordinator.tick(actor="test") == 1
    with store.transaction() as db:
        response = db.execute("SELECT job_id FROM operational_responses").fetchone()
        db.execute("UPDATE jobs SET status='failed' WHERE id=?", (response["job_id"],))

    assert coordinator.tick(actor="test") == 1
    thread = LabStore(store).thread(thread_id, mark_read=False)
    assert "I could not complete the on-call assessment" in thread["messages"][-1]["body"]
    with store._connect() as db:
        response = db.execute("SELECT * FROM operational_responses").fetchone()
    assert response["status"] == "failed"
    assert response["disposition"] is None
    assert response["action"] is None


def test_unavailable_on_call_pauses_pipeline_and_retries_later(tmp_path: Path) -> None:
    store, bundle = ready(tmp_path)
    active_config = store.active_config()
    deployment_id = store.register_deployment({
        "machine_id": "mission-hub", "role": "mission_hub", "release_id": "on-call-release",
        "source_sha256": "1" * 64, "environment_sha256": "2" * 64,
        "config_snapshot_id": active_config["id"],
    }, actor="test", activate=True)
    store.request_pipeline_state("running", actor="test")
    store.apply_pipeline_state(actor="test")
    thread_id = LabStore(store).system_notice("A critical notice", "Something happened.")
    coordinator = OperationalResponseCoordinator(store, bundle)
    assert coordinator.tick(actor="test") == 1
    with store.transaction() as db:
        response = db.execute("SELECT * FROM operational_responses").fetchone()
        db.execute("UPDATE jobs SET status='failed' WHERE id=?", (response["job_id"],))
        db.execute(
            """INSERT INTO runs
               (id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,
                lease_expires_at,started_at,heartbeat_at,finished_at,failure_class,failure_code,failure_json)
               VALUES('run-on-call-down',?,1,'mission-hub',?,'failed',?,
                      '2099-01-01T00:00:00Z',?,?,?,'capability_transient',
                      'provider_capability_unavailable',?)""",
            (
                response["job_id"], deployment_id, "0" * 64, utc_now(), utc_now(), utc_now(),
                json.dumps({
                    "class": "capability_transient",
                    "code": "provider_capability_unavailable",
                    "message": "Selected on-call model is at capacity.",
                }),
            ),
        )

    assert coordinator.tick(actor="test") == 1

    control = store.pipeline_control()
    assert control["desired_state"] == "paused"
    assert control["applied_state"] == "paused"
    with store._connect() as db:
        response = db.execute("SELECT * FROM operational_responses").fetchone()
    assert response["status"] == "pending"
    assert response["job_id"] is None
    assert response["next_check_at"] is not None
    assert response["wait_check_count"] == 1
    thread = LabStore(store).thread(thread_id, mark_read=False)
    assert "On-call is temporarily unavailable" in thread["messages"][-1]["body"]
    assert "paused all new dispatch" in thread["messages"][-1]["body"]
    assert "will try on-call again" in thread["messages"][-1]["body"]


def test_on_call_waits_durably_for_busy_mission_hub_and_rechecks(tmp_path: Path) -> None:
    store, bundle = ready(tmp_path)
    active_config = store.active_config()
    deployment_id = store.register_deployment({
        "machine_id": "mission-hub", "role": "mission_hub", "release_id": "test-release",
        "source_sha256": "1" * 64, "environment_sha256": "2" * 64,
        "config_snapshot_id": active_config["id"],
    }, actor="test", activate=True)
    store.request_pipeline_state("running", actor="test")
    store.apply_pipeline_state(actor="test")
    ordinary = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="busy-mission-hub", created_by="test",
        requested_machine_id="mission-hub", approved=True,
    )
    run_id = "run-busy-mission-hub"
    with store.transaction() as db:
        db.execute("UPDATE jobs SET status='running' WHERE id=?", (ordinary["id"],))
        db.execute(
            """INSERT INTO runs
               (id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,
                lease_expires_at,started_at,heartbeat_at)
               VALUES(?,?,1,'mission-hub',?,'running',?,'2099-01-01T00:00:00Z',?,?)""",
            (run_id, ordinary["id"], deployment_id, "0" * 64, utc_now(), utc_now()),
        )
    thread_id = LabStore(store).system_notice("A notice", "Something needs assessment.")
    coordinator = OperationalResponseCoordinator(store, bundle)

    assert coordinator.tick(actor="test") == 1
    with store._connect() as db:
        response = db.execute("SELECT * FROM operational_responses").fetchone()
    assert response["status"] == "pending"
    assert response["job_id"] is None
    assert response["wait_started_at"] is not None
    assert response["next_check_at"] is not None
    assert response["wait_check_count"] == 1
    assert ordinary["id"] in response["wait_reason"]
    thread = LabStore(store).thread(thread_id, mark_read=False)
    assert "I was invoked" in thread["messages"][-1]["body"]
    assert "I will check again" in thread["messages"][-1]["body"]
    listed = next(item for item in LabStore(store).list_threads() if item["id"] == thread_id)
    assert listed["on_call_next_check_at"] == response["next_check_at"]

    with store.transaction() as db:
        db.execute("UPDATE runs SET status='succeeded',finished_at=? WHERE id=?", (utc_now(), run_id))
        db.execute("UPDATE jobs SET status='succeeded',updated_at=? WHERE id=?", (utc_now(), ordinary["id"]))
    store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="ordinary-must-yield-to-waiting-on-call", created_by="test",
        requested_machine_id="mission-hub", approved=True,
    )
    assert store.lease_next(
        bundle, machine_id="mission-hub", deployment_id=deployment_id, actor="agent",
    ) is None

    with store.transaction() as db:
        db.execute("UPDATE operational_responses SET next_check_at='2000-01-01T00:00:00Z'")

    assert coordinator.tick(actor="test") == 1
    with store._connect() as db:
        response = db.execute("SELECT * FROM operational_responses").fetchone()
    assert response["status"] == "queued"
    assert response["job_id"] is not None
    assert response["next_check_at"] is None


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


def test_on_call_can_apply_typed_queue_expiry_recovery(tmp_path: Path, monkeypatch) -> None:
    store, bundle = ready(tmp_path)
    job = store.create_job(
        bundle, job_type="system.healthcheck", input_payload={},
        idempotency_key="queue-expired-auto-recovery", created_by="test",
        requested_machine_id="mission-hub", approved=True,
    )
    with store.transaction() as db:
        db.execute("UPDATE jobs SET status='blocked' WHERE id=?", (job["id"],))
    called = {}

    def recover(bundle_arg, job_id, *, reason, actor):
        called.update({"bundle": bundle_arg, "job_id": job_id, "reason": reason, "actor": actor})
        return {"id": "cortex-resumed"}

    monkeypatch.setattr(store, "recover_queue_expired_cortex_stage", recover)
    result = OperationalResponseCoordinator(store, bundle)._act({
        "action": "allow_automatic_recovery", "disposition": "automatic_recovery",
        "target_job_id": job["id"], "assessment": "Queue expiry.",
        "reasoning": "Resume the exact untouched frontier.",
    }, actor="test")

    assert result["applied"] is True
    assert "resumed without retraining" in result["summary"]
    assert called["job_id"] == job["id"]
    assert called["actor"] == "mission-hub:on-call"


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


def test_review_exhausted_visual_workflow_is_autonomously_recommissioned() -> None:
    response = _deterministic_blocker({
        "body": (
            "Workflow: visual-x\nReason: independent review found no usable candidate\n"
            "Review result: 52 of 76 candidates were usable; 24 were rejected.\n"
            "Do not retry unchanged."
        ),
    })

    assert response["action"] == "recommission_visual_workflow"
    assert response["disposition"] == "automatic_recovery"
    assert response["target_workflow_id"] == "visual-x"
    assert response["human_blocker"] is None
    assert response["blocker_reason"] is None
    assert _response_contradiction(response) is None


def test_queue_expired_cortex_notice_has_deterministic_recovery_action() -> None:
    response = _deterministic_queue_expiry({
        "body": (
            "Workflow: cortex-x\nStage: s05:evaluate\nJob: job-x\nStatus: failed\n"
            "Reason: s05:evaluate:blocked\nQueue condition: queue_age_exceeded\n"
        ),
    })

    assert response["action"] == "allow_automatic_recovery"
    assert response["target_job_id"] == "job-x"
    assert response["incident_id"] is None
    assert _response_contradiction(response) is None
    assert _notice_contradiction({"body": "Job: job-x\n"}, response) is None


def test_classified_contract_incident_has_deterministic_begin_repair_action() -> None:
    notice = {"body": (
        "Critical job visual.decide failed.\nJob: job-x\nRun: run-x\n"
        "Failure: artifact_contract_invalid (deterministic_specification)\n"
        "visual decision evidence is incomplete\nRecovery incident: inc-x\n"
        "Recovery state: classified (contract)\n"
    )}

    response = _deterministic_repairable_incident(notice)

    assert response["action"] == "begin_repair"
    assert response["target_job_id"] == "job-x"
    assert response["incident_id"] == "inc-x"
    assert _response_contradiction(response) is None
    assert _notice_contradiction(notice, response) is None


def test_provider_capacity_incident_names_the_concrete_problem() -> None:
    notice = {"body": (
        "Critical job visual.review failed.\nJob: job-x\nRun: run-x\n"
        "Failure: provider_capability_unavailable (capability_transient)\n"
        "visual.review local runtime failed\nRecovery incident: inc-x\n"
        "Recovery state: classified (infrastructure)\n"
    )}

    response = _deterministic_repairable_incident(notice)

    assert response["action"] == "begin_repair"
    assert response["assessment"].startswith("visual.review could not obtain a model response")
    assert "selected model was at capacity" in response["assessment"]
    assert "eligible for bounded autonomous repair" not in response["assessment"]


def test_on_call_message_leads_with_plain_english_summary() -> None:
    message = _human_on_call_message(
        {
            "assessment": "The evaluation never started because its queue permission became stale.",
            "reasoning": "The completed training checkpoint is safe and the evaluation has no run history.",
        },
        {"summary": "I requeued the unchanged evaluation. Training will not be repeated."},
    )

    assert message.startswith("Sol's on-call update\n\nShort version:\nThe evaluation never started")
    assert "What I found:" in message
    assert "What I did:\nI requeued the unchanged evaluation." in message


def test_failed_on_call_response_explains_its_own_failure() -> None:
    message = _human_on_call_failure_message("failed", {
        "id": "run-response", "failure_code": "structured_response_invalid",
        "failure_json": json.dumps({"message": "response did not match schema"}),
    })

    assert "I could not complete the on-call assessment" in message
    assert "did not fit the system's required action format" in message
    assert "original problem remains safely contained" in message
    assert "Failure code: structured_response_invalid" in message
    assert "Validation detail: response did not match schema" in message
