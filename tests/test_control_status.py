from __future__ import annotations

import json
import subprocess

from lab.backend.control.status import ControlStatusService
from training.pipeline.control.ledger import ControlLedger
from training.pipeline.control.timing_log import PipelineTimingLog
from tests.helpers import make_lab_config


def test_control_status_sanitizes_local_and_remote_ledgers(tmp_path, monkeypatch) -> None:
    config = make_lab_config(tmp_path)
    ledger = ControlLedger(config.orchestrator_control_root)
    ledger.create_plan(
        kind="status_refresh",
        mode="shadow",
        payload={"secret_prompt": "must not reach the Lab"},
        created_by="test",
        plan_id="plan-control-status-test",
    )
    remote_snapshot = {
        "schema_version": "ninereeds_control_snapshot_v1",
        "root": "/private/trainbox/path",
        "counts": {"completed": 2},
        "latest_receipts": [
            {
                "plan_id": "plan-remote-test",
                "status": "completed",
                "attempt_count": 1,
                "updated_at": "2026-07-25T00:00:00Z",
                "progress": {
                    "kind": "cortex_curriculum",
                    "phase": "generating",
                    "completed_chunks": 6,
                    "active_chunk": 7,
                    "completed_examples": 300,
                    "target_examples": 500,
                    "semantic_attempt": 2,
                    "active_executor": "deepseek:deepseek-v4-flash",
                    "private_note": "must not reach the Lab",
                },
                "history": [{"detail": "private worker detail"}],
            }
        ],
    }

    def fake_run(args, **kwargs):
        if args[0] == "/usr/bin/ssh":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"ok": True, "snapshot": remote_snapshot}),
                stderr="",
            )
        if "list-timers" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(
                    [
                        {
                            "next": 1785046568134635,
                            "last": 1785042968128865,
                            "unit": "ninereeds-orchestrator-supervisor.timer",
                        }
                    ]
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ControlStatusService(config).status(force=True)

    assert result["ok"] is True
    assert result["local"]["counts"] == {"queued": 1}
    assert result["trainbox"]["counts"] == {"completed": 2}
    assert result["trainbox"]["latest_receipts"][0]["progress"][
        "active_executor"
    ] == "deepseek:deepseek-v4-flash"
    assert result["schedule"] == {
        "available": True,
        "status": "waiting_for_due_work",
        "next_run_at": 1785046568.134635,
        "last_run_at": 1785042968.128865,
        "unit": "ninereeds-orchestrator-supervisor.timer",
    }
    serialized = json.dumps(result)
    assert "secret_prompt" not in serialized
    assert "private worker detail" not in serialized
    assert "private_note" not in serialized
    assert "/private/trainbox/path" not in serialized


def test_control_status_handles_unreachable_trainbox(tmp_path, monkeypatch) -> None:
    config = make_lab_config(tmp_path)

    def fake_run(args, **kwargs):
        if args[0] == "/usr/bin/ssh":
            return subprocess.CompletedProcess(
                args=args, returncode=255, stdout="", stderr="network unavailable"
            )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ControlStatusService(config).status(force=True)

    assert result["ok"] is False
    assert result["local"]["ok"] is True
    assert result["trainbox"]["reachable"] is False


def test_control_status_handles_unscheduled_timer(tmp_path, monkeypatch) -> None:
    config = make_lab_config(tmp_path)

    def fake_run(args, **kwargs):
        if args[0] == "/usr/bin/ssh":
            return subprocess.CompletedProcess(
                args=args,
                returncode=255,
                stdout="",
                stderr="network unavailable",
            )
        if "list-timers" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="[]",
                stderr="",
            )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ControlStatusService(config).status(force=True)

    assert result["schedule"]["available"] is False
    assert result["schedule"]["status"] == "unavailable"
    assert result["schedule"]["next_run_at"] is None


def test_control_status_prefers_live_allowlist_wave_campaign(tmp_path) -> None:
    config = make_lab_config(tmp_path)
    state_path = (
        config.orchestrator_control_root
        / "derived/allowlist-0501-2000-v1-state.json"
    )
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "schema_version": "ninereeds_allowlist_wave_state_v1",
                "wave_id": "allowlist-0501-2000-v1",
                "status": "running",
                "phase": "evaluating",
                "block_index": 3,
                "attempt_index": 1,
                "parent_checkpoint": "core/cortex/parent.pt",
                "current_plan_id": "plan-wave-eval-block-03",
                "accepted_blocks": [{}, {}],
                "rejected_attempts": [{}],
            }
        ),
        encoding="utf-8",
    )

    campaign = ControlStatusService(config)._campaign_snapshot()

    assert campaign["campaign_id"] == "allowlist-0501-2000-v1"
    assert campaign["current_plan_id"] == "plan-wave-eval-block-03"
    assert campaign["boundary_index"] == 3
    assert campaign["wave"] == {
        "concepts_total": 1500,
        "concepts_admitted": 250,
        "blocks_total": 12,
        "blocks_admitted": 2,
        "attempt_index": 1,
        "phase": "evaluating",
        "parent_checkpoint": "core/cortex/parent.pt",
    }


def test_control_status_does_not_let_terminal_wave_shadow_newer_campaign(
    tmp_path,
) -> None:
    config = make_lab_config(tmp_path)
    wave_path = (
        config.orchestrator_control_root
        / "derived/allowlist-0501-2000-v1-state.json"
    )
    wave_path.parent.mkdir(parents=True)
    wave_path.write_text(
        json.dumps(
            {
                "schema_version": "ninereeds_allowlist_wave_state_v1",
                "wave_id": "allowlist-0501-2000-v1",
                "status": "blocked",
                "phase": "evaluation_gate_failed",
                "block_index": 1,
                "accepted_blocks": [],
                "rejected_attempts": [{}, {}],
            }
        ),
        encoding="utf-8",
    )
    campaign_path = config.orchestrator_control_root / "campaign/state.json"
    campaign_path.parent.mkdir(parents=True, exist_ok=True)
    campaign_path.write_text(
        json.dumps(
            {
                "schema_version": "ninereeds_autonomous_campaign_v1",
                "campaign_id": "allowlist-0501-2000-foundation-recovery-v2",
                "status": "waiting",
                "current_plan_id": "plan-campaign-recovery-b0005",
                "boundary_index": 5,
                "deadline_at": None,
                "stop_reason": "Waiting for the commissioned executor.",
                "budgets": {"strategic_boundaries": 24, "executor_jobs": 24},
                "usage": {"strategic_boundaries": 5, "executor_jobs": 4},
            }
        ),
        encoding="utf-8",
    )
    wave_mtime = wave_path.stat().st_mtime
    campaign_path.touch()
    assert campaign_path.stat().st_mtime >= wave_mtime

    campaign = ControlStatusService(config)._campaign_snapshot()

    assert campaign["campaign_id"] == "allowlist-0501-2000-foundation-recovery-v2"
    assert campaign["current_plan_id"] == "plan-campaign-recovery-b0005"
    assert campaign["boundary_index"] == 5
    assert "wave" not in campaign


def test_control_timing_exposes_only_bounded_operational_events(tmp_path) -> None:
    config = make_lab_config(tmp_path)
    timing = PipelineTimingLog(config.orchestrator_control_root)
    timing.record(
        "plan.report",
        "control-ledger",
        plan_id="plan-safe",
        model="gpt-5.6-luna",
        attempt_count=2,
        runtime_ms=1234,
    )

    result = ControlStatusService(config).timing(limit=10)

    assert result["retention_days"] == 7
    assert result["events"] == [
        {
            "schema_version": "ninereeds_pipeline_timing_v1",
            "timestamp": result["events"][0]["timestamp"],
            "epoch_seconds": result["events"][0]["epoch_seconds"],
            "event": "plan.report",
            "component": "control-ledger",
            "plan_id": "plan-safe",
            "model": "gpt-5.6-luna",
            "attempt_count": 2,
            "runtime_ms": 1234,
        }
    ]
