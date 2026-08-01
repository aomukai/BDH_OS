from __future__ import annotations

import json
import subprocess
from pathlib import Path

from training.pipeline.control.ledger import ControlLedger
from training.pipeline.control.trainbox_worker import TrainboxWorker
from tests.test_msm_trainer import script, setup_repo


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


def test_live_phase_uses_commissioned_torch_python(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="phase_block",
        mode="live",
        payload={
            "phase_id": "phase_0_form",
            "runner_args": ["--device", "cuda:1"],
        },
        created_by="orchestrator:test",
        plan_id="plan-live-python",
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    )
    calls: list[list[str]] = []
    worker = TrainboxWorker(
        ledger,
        repo_root=repo,
        worker_id="worker:test",
        allow_live=True,
        command_runner=fake_phase_runner(repo, calls),
    )
    assert worker.drain()["completed"] == 1
    assert calls[0][0] == str(
        Path("/home/aomukai/.unsloth/studio/unsloth_studio/bin/python")
    )


def test_shadow_cortex_block_is_validated_without_loading_models(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    data = repo / "training/pipeline/cortex/bootstrap.jsonl"
    data.parent.mkdir(parents=True)
    data.write_text('{"prompt":"x","completion":"y"}\\n', encoding="utf-8")
    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="cortex_block",
        mode="shadow",
        payload={
            "jsonl_path": "training/pipeline/cortex/bootstrap.jsonl",
            "output_checkpoint": "core/cortex/bootstrap.pt",
            "runner_args": ["--epochs", "1"],
        },
        created_by="orchestrator:test",
        plan_id="plan-cortex-shadow",
    )
    worker = TrainboxWorker(ledger, repo_root=repo, worker_id="worker:test")
    assert worker.drain()["completed"] == 1
    report = ledger.report(plan["plan_id"])
    assert report["result"]["status"] == "planned"
    assert report["result"]["kind"] == "cortex_block"


def test_shadow_cortex_block_accepts_finalized_msm_script_inline(
    tmp_path: Path,
) -> None:
    repo = setup_repo(tmp_path)
    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="cortex_block",
        mode="shadow",
        payload={
            "script": script("session-cortex-inline"),
            "output_checkpoint": "core/cortex/inline.pt",
            "runner_args": ["--epochs", "1"],
        },
        created_by="orchestrator:test",
        plan_id="plan-cortex-inline",
    )
    worker = TrainboxWorker(ledger, repo_root=repo, worker_id="worker:test")
    assert worker.drain()["completed"] == 1
    result = ledger.report(plan["plan_id"])["result"]
    assert result["training_source"] == {
        "type": "msm_script",
        "script_id": "script-test",
        "session_id": "session-cortex-inline",
    }
    assert not (repo / "core/cortex").exists()


def test_cortex_corpus_chunks_assemble_before_training(tmp_path: Path) -> None:
    import hashlib

    from training.pipeline.control.ledger import canonical_json

    repo = tmp_path / "repo"
    repo.mkdir()
    ledger = ControlLedger(tmp_path / "control")
    chunks = [
        [
            {"prompt": "Where is the key?", "completion": "It is in the box.", "stage": "replay"},
            {"prompt": "Is it outside?", "completion": "No, it is inside.", "stage": "new"},
        ],
        [
            {"prompt": "What is empty?", "completion": "The box is empty.", "stage": "special"},
        ],
    ]
    curriculum_hash = hashlib.sha256(
        canonical_json([value for chunk in chunks for value in chunk])
    ).hexdigest()
    paths = []
    for index, examples in enumerate(chunks, 1):
        output_path = (
            f"core/cortex/curricula/test-curriculum/chunk-{index:04d}.jsonl"
        )
        paths.append(output_path)
        ledger.create_plan(
            kind="cortex_corpus_chunk",
            mode="live",
            payload={
                "curriculum_id": "test-curriculum",
                "chunk_index": index,
                "chunk_count": len(chunks),
                "examples": examples,
                "chunk_sha256": hashlib.sha256(
                    canonical_json(examples)
                ).hexdigest(),
                "curriculum_sha256": curriculum_hash,
                "output_path": output_path,
            },
            created_by="orchestrator:test",
            plan_id=f"plan-corpus-{index:04d}",
        )
    worker = TrainboxWorker(ledger, repo_root=repo, worker_id="worker:test")
    assert worker.drain()["completed"] == 2

    plan = ledger.create_plan(
        kind="cortex_block",
        mode="shadow",
        payload={
            "jsonl_paths": paths,
            "curriculum_id": "test-curriculum",
            "curriculum_sha256": curriculum_hash,
            "concept": "container",
            "output_checkpoint": "core/cortex/test-curriculum.pt",
            "runner_args": ["--epochs", "1"],
        },
        created_by="orchestrator:test",
        plan_id="plan-train-curriculum",
    )
    assert worker.drain()["completed"] == 1
    report = ledger.report(plan["plan_id"])
    assert report["result"]["training_source"]["type"] == "chunked_jsonl"
    assembled = repo / "core/cortex/curricula/test-curriculum/assembled.jsonl"
    assert len(assembled.read_text(encoding="utf-8").splitlines()) == 3


def test_lease_runner_does_not_deadlock_on_large_child_output(tmp_path: Path) -> None:
    worker = TrainboxWorker(
        ControlLedger(tmp_path / "control"),
        repo_root=tmp_path,
        worker_id="worker:test",
    )
    completed = worker._run_with_lease(
        [
            "python3",
            "-c",
            "import sys; print('x' * 262144); print('y' * 262144, file=sys.stderr)",
        ],
        "unused-short-process",
    )
    assert completed.returncode == 0
    assert len(completed.stdout) == 262145
    assert len(completed.stderr) == 262145


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


def test_cortex_authoring_executor_carries_but_does_not_use_weight_authority(
    tmp_path: Path,
) -> None:
    class FakeAdapter:
        def execute(self, **_kwargs):
            return {
                "schema_version": "ninereeds_executor_job_result_v1",
                "execution_id": "plan-author-cortex",
                "job_id": "job",
                "model_id": "ternary-bonsai-27b",
                "valid": True,
                "attempt_count": 1,
                "attempts": [],
                "proposal": {"artifacts": []},
                "validation_errors": [],
                "artifact_hashes": {},
                "server_log": "/tmp/server.log",
            }

    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={
            "task": {"job_id": "job"},
            "model_id": "ternary-bonsai-27b",
            "required_context_tokens": 0,
            "max_model_attempts": 2,
            "workflow": {"type": "cortex_train"},
        },
        created_by="orchestrator:test",
        plan_id="plan-author-cortex",
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    )
    worker = TrainboxWorker(
        ledger,
        repo_root=tmp_path,
        worker_id="worker:test",
        executor_adapter=FakeAdapter(),
    )
    assert worker.drain()["completed"] == 1
    assert ledger.report(plan["plan_id"])["result"]["valid"] is True


def test_cortex_authoring_rejects_oversized_output_budget(tmp_path: Path) -> None:
    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={
            "task": {"job_id": "job", "max_tokens": 8192},
            "model_id": "ternary-bonsai-27b",
            "required_context_tokens": 0,
            "max_model_attempts": 2,
            "workflow": {"type": "cortex_train"},
        },
        created_by="orchestrator:test",
        plan_id="plan-author-cortex-too-large",
        authorization={
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_auto_advance": False,
        },
    )
    worker = TrainboxWorker(
        ledger,
        repo_root=tmp_path,
        worker_id="worker:test",
        executor_adapter=object(),
    )
    assert worker.drain()["blocked"] == 1
    assert "4096" in ledger.report(plan["plan_id"])["result"]["error"]


def test_cortex_curriculum_authors_durable_append_steps(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    schema = repo / "training/pipeline/cortex/curriculum_chunk_schema.json"
    schema.parent.mkdir(parents=True)
    schema.write_text(
        (
            Path(__file__).resolve().parents[1]
            / "training/pipeline/cortex/curriculum_chunk_schema.json"
        ).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    calls: list[dict] = []
    active_executors: list[str | None] = []

    class FakeAdapter:
        def execute(self, **kwargs):
            calls.append(kwargs)
            kwargs["rung_callback"]("deepseek:deepseek-v4-flash")
            active_executors.append(
                ledger.receipt("plan-curriculum-author")["progress"][
                    "active_executor"
                ]
            )
            chunk_index = len(calls)
            artifact_path = kwargs["task"]["allowed_artifact_paths"][0]
            count = 2 if chunk_index == 1 else 1
            examples = [
                {
                    "prompt": f"prompt-{chunk_index}-{index}",
                    "completion": f"answer-{chunk_index}-{index}",
                    "stage": "new",
                }
                for index in range(count)
            ]
            return {
                "valid": True,
                "model_id": "ternary-bonsai-27b",
                "attempt_count": 1,
                "executor_ladder": ["ternary-bonsai-27b"],
                "proposal": {
                    "artifacts": [
                        {
                            "path": artifact_path,
                            "content": json.dumps(
                                {
                                    "schema_version": (
                                        "ninereeds_cortex_curriculum_chunk_v1"
                                    ),
                                    "chunk_index": chunk_index,
                                    "examples": examples,
                                }
                            ),
                        }
                    ]
                },
            }

    ledger = ControlLedger(tmp_path / "control")
    plan = ledger.create_plan(
        kind="executor_job",
        mode="live",
        payload={
            "task": {
                "job_id": "curriculum",
                "title": "Curriculum",
                "instructions": "Create varied examples.",
                "context_files": [
                    "training/pipeline/cortex/curriculum_chunk_schema.json"
                ],
                "allowed_artifact_paths": [],
                "allowed_actions": [
                    "VALIDATE_JSON",
                    "RETURN_VALIDATION_ERRORS",
                ],
                "artifact_json_schemas": {},
                "max_tokens": 4096,
            },
            "model_id": "ternary-bonsai-27b",
            "required_context_tokens": 0,
            "max_model_attempts": 5,
            "workflow": {
                "type": "cortex_curriculum",
                "session_id": "append-test",
                "parent_checkpoint": "core/cortex/parent.pt",
                "output_checkpoint": "core/cortex/child.pt",
                "runner_args": ["--epochs", "1"],
                "artifact_root": (
                    "training/pipeline/msm/proposals/append-test"
                ),
                "target_examples": 3,
                "chunk_examples": 2,
                "concept": "foundation",
            },
        },
        created_by="orchestrator:test",
        plan_id="plan-curriculum-author",
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
        executor_adapter=FakeAdapter(),
    )

    assert worker.drain()["completed"] == 1
    result = ledger.report(plan["plan_id"])["result"]
    assert result["examples"] == 3
    assert result["chunks"] == 2
    assert result["resume_supported"] is True
    assert len(calls) == 2
    assert all(call["max_model_attempts"] == 5 for call in calls)
    assert all(call.get("progress_callback") is not None for call in calls)
    assert active_executors == [
        "deepseek:deepseek-v4-flash",
        "deepseek:deepseek-v4-flash",
    ]
    assert ledger.receipt(plan["plan_id"])["progress"] == {
        "kind": "cortex_curriculum",
        "phase": "chunk_completed",
        "completed_chunks": 2,
        "active_chunk": None,
        "completed_examples": 3,
        "target_examples": 3,
        "semantic_attempt": 0,
        "active_executor": None,
    }
    for relative in result["jsonl_paths"]:
        assert (repo / relative).is_file()


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
