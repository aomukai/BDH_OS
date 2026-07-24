from __future__ import annotations

import json
import subprocess
from pathlib import Path

from training.pipeline.control.ledger import ControlLedger
from training.pipeline.control.trainbox_worker import TrainboxWorker


def fake_phase_runner(repo: Path, calls: list[list[str]]):
    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        phase_id = command[command.index("--phase-id") + 1]
        block_id = f"{phase_id}_block_0001"
        relative = (
            Path("training/pipeline/msm/phase_blocks")
            / phase_id
            / block_id
        )
        directory = repo / relative
        directory.mkdir(parents=True)
        frontload = directory / "frontload.jsonl"
        probes = directory / "probes.jsonl"
        frontload.write_text("{}\n", encoding="utf-8")
        probes.write_text("{}\n", encoding="utf-8")
        report = {
            "schema_version": "msm_phase_block_report_v1",
            "phase_id": phase_id,
            "block_id": block_id,
            "status": "planned",
            "gate_status": "not_evaluated",
            "local_recommendation": "escalate_orchestrator",
            "artifacts": {
                "frontload_jsonl": (relative / "frontload.jsonl").as_posix(),
                "probe_jsonl": (relative / "probes.jsonl").as_posix(),
                "probe_results_jsonl": None,
                "train_stdout": None,
                "report_json": (relative / "block_report.json").as_posix(),
            },
        }
        report_path = directory / "block_report.json"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        stdout = json.dumps({"block_report": report["artifacts"]["report_json"]})
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    return run


def test_shadow_phase_plan_forces_dry_run_and_completes_once(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="phase_block",
        mode="shadow",
        payload={"phase_id": "phase_0_form", "runner_args": ["--examples", "4"]},
        created_by="orchestrator:test",
        plan_id="plan-shadow",
    )
    calls: list[list[str]] = []
    worker = TrainboxWorker(
        ledger,
        repo_root=repo,
        worker_id="worker:test",
        command_runner=fake_phase_runner(repo, calls),
    )
    result = worker.drain()
    assert result["completed"] == 1
    assert "--dry-run" in calls[0]
    assert ledger.receipt(plan["plan_id"])["status"] == "completed"
    assert ledger.report(plan["plan_id"])["result"]["block_status"] == "planned"

    assert worker.drain()["processed"] == 0
    assert len(calls) == 1


def test_live_phase_plan_is_blocked_by_machine_gate(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="phase_block",
        mode="live",
        payload={"phase_id": "phase_0_form", "runner_args": []},
        created_by="orchestrator:test",
        plan_id="plan-live",
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    )
    worker = TrainboxWorker(
        ledger,
        repo_root=repo,
        worker_id="worker:test",
        allow_live=False,
        command_runner=lambda command: (_ for _ in ()).throw(
            AssertionError("runner must not execute")
        ),
    )
    result = worker.drain()
    assert result["blocked"] == 1
    assert ledger.receipt(plan["plan_id"])["status"] == "blocked"
    assert "machine gate" in ledger.report(plan["plan_id"])["result"]["error"]


def test_executor_job_is_validated_and_persisted(tmp_path: Path) -> None:
    class FakeAdapter:
        def execute(self, **_kwargs):
            return {
                "schema_version": "ninereeds_executor_job_result_v1",
                "execution_id": "plan-executor",
                "job_id": "job",
                "model_id": "gemma-4-26b-a4b",
                "valid": True,
                "attempt_count": 1,
                "attempts": [],
                "proposal": {"artifacts": []},
                "validation_errors": [],
                "artifact_hashes": {"proposal": "a" * 64},
                "server_log": "/tmp/server.log",
            }

    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="executor_job",
        mode="shadow",
        payload={
            "task": {"job_id": "job"},
            "model_id": None,
            "required_context_tokens": 0,
            "max_model_attempts": 2,
        },
        created_by="orchestrator:test",
        plan_id="plan-executor",
    )
    worker = TrainboxWorker(
        ledger,
        repo_root=tmp_path,
        worker_id="worker:test",
        executor_adapter=FakeAdapter(),
    )
    assert worker.drain()["completed"] == 1
    report = ledger.report(plan["plan_id"])
    assert report["result"]["valid"] is True
    assert report["artifact_hashes"] == {"proposal": "a" * 64}


def test_trainer_shadow_plan_uses_deterministic_trainer(tmp_path: Path) -> None:
    class FakeTrainer:
        def run(self, **kwargs):
            assert kwargs["mode"] == "shadow"
            return (
                {
                    "schema_version": "msm_trainer_result_v1",
                    "session_id": "session",
                    "mode": "shadow",
                    "status": "planned",
                    "event_count": 0,
                    "artifacts": {},
                },
                {"script.json": "b" * 64},
            )

    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="trainer_session",
        mode="shadow",
        payload={"script": {}, "checkpoint_path": None, "inference": {}},
        created_by="orchestrator:test",
        plan_id="plan-trainer",
    )
    worker = TrainboxWorker(
        ledger,
        repo_root=tmp_path,
        worker_id="worker:test",
        msm_trainer=FakeTrainer(),
    )
    assert worker.drain()["completed"] == 1
    assert ledger.report(plan["plan_id"])["result"]["status"] == "planned"
