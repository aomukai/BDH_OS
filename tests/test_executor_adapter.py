from __future__ import annotations

import io
import json
import time
from pathlib import Path

import pytest

from training.pipeline.control.executor_adapter import (
    ExecutorAdapter,
    ExecutorAdapterError,
)


def config(path: Path) -> Path:
    value = {
        "schema_version": "executor_models_v1",
        "executor_root": str(path.parent / "executor"),
        "visible_cuda_devices": "0",
        "models": {
            "qwen3.6-35b-a3b-q4-k-m-turboquant": {
                "runtime": "qwen-turboquant-server",
                "model": "qwen-q4-k-m.gguf",
                "context": 256000,
                "context_fallbacks": [128000],
                "gpu_layers": 999,
            },
            "gemma-4-26b-a4b": {
                "runtime": "gemma-server",
                "model": "gemma.gguf",
                "context": 32768,
                "gpu_layers": "auto",
            },
            "ternary-bonsai-27b": {
                "runtime": "bonsai-server",
                "model": "bonsai.gguf",
                "context": 131072,
                "gpu_layers": 99,
            },
            "qwen3.6-35b-a3b": {
                "runtime": "qwen-server",
                "model": "qwen.gguf",
                "context": 32768,
                "gpu_layers": "auto",
            },
        },
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def task() -> dict:
    return {
        "job_id": "test-job",
        "title": "Test",
        "instructions": "Return one bounded proposal.",
        "context_files": [],
        "allowed_artifact_paths": [],
        "allowed_actions": [],
        "max_tokens": 128,
    }


def test_adapter_repairs_once_and_defaults_to_qwen_turboquant(tmp_path: Path) -> None:
    attempts = 0

    def run_task(_model, _port, _task, *, attempt, prior_result=None):
        nonlocal attempts
        attempts += 1
        return {
            "attempt": attempt,
            "valid": attempt == 2,
            "validation_errors": [] if attempt == 2 else ["synthetic"],
            "proposal": {"artifacts": []} if attempt == 2 else None,
            "elapsed_seconds": 1,
            "peak_gpu_memory_mib": 1,
            "usage": {},
            "timings": {},
        }

    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
        server_starter=lambda *_args: (object(), 1234),
        server_stopper=lambda _process: None,
        task_runner=run_task,
    )
    result = adapter.execute(execution_id="exec-test", task=task())
    assert result["model_id"] == "qwen3.6-35b-a3b-q4-k-m-turboquant"
    assert result["valid"] is True
    assert result["attempt_count"] == 2
    assert result["executor_ladder"] == [
        "qwen3.6-35b-a3b-q4-k-m-turboquant",
        "ternary-bonsai-27b",
        "gemma-4-26b-a4b",
        "openrouter:deepseek-v4-flash",
        "deepseek:deepseek-v4-pro",
    ]
    assert attempts == 2


def test_adapter_allows_five_repairs_before_escalating_model(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, int]] = []

    def run_task(model_id, _port, _task, *, attempt, prior_result=None):
        calls.append((model_id, attempt))
        valid = model_id == "qwen3.6-35b-a3b-q4-k-m-turboquant" and attempt == 5
        return {
            "attempt": attempt,
            "valid": valid,
            "validation_errors": [] if valid else ["keep repairing this step"],
            "proposal": {"artifacts": []} if valid else None,
            "elapsed_seconds": 1,
            "peak_gpu_memory_mib": 1,
            "usage": {},
            "timings": {},
        }

    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
        server_starter=lambda *_args: (object(), 1234),
        server_stopper=lambda _process: None,
        task_runner=run_task,
    )
    result = adapter.execute(
        execution_id="exec-five-repairs",
        task=task(),
        max_model_attempts=5,
    )

    assert result["valid"] is True
    assert result["model_id"] == "qwen3.6-35b-a3b-q4-k-m-turboquant"
    assert result["attempt_count"] == 5
    assert calls == [
        ("qwen3.6-35b-a3b-q4-k-m-turboquant", attempt)
        for attempt in range(1, 6)
    ]


def test_adapter_escalates_across_local_models_without_orchestrator(
    tmp_path: Path,
) -> None:
    started: list[str] = []
    calls: list[tuple[str, int]] = []

    def start(model_id, *_args):
        started.append(model_id)
        return object(), len(started)

    def run(model_id, _port, _task, *, attempt, prior_result=None):
        calls.append((model_id, attempt))
        valid = model_id == "gemma-4-26b-a4b" and attempt == 6
        return {
            "model_id": model_id,
            "attempt": attempt,
            "valid": valid,
            "validation_errors": [] if valid else ["synthetic"],
            "proposal": {"artifacts": []} if valid else None,
            "raw_response": "",
            "elapsed_seconds": 1,
            "peak_gpu_memory_mib": 1,
            "usage": {},
            "timings": {},
        }

    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
        server_starter=start,
        server_stopper=lambda _process: None,
        task_runner=run,
    )
    result = adapter.execute(execution_id="exec-local-ladder", task=task())
    assert result["valid"] is True
    assert result["model_id"] == "gemma-4-26b-a4b"
    assert result["attempt_count"] == 6
    assert started == [
        "qwen3.6-35b-a3b-q4-k-m-turboquant",
        "ternary-bonsai-27b",
        "gemma-4-26b-a4b",
    ]
    assert calls == [
        ("qwen3.6-35b-a3b-q4-k-m-turboquant", 1),
        ("qwen3.6-35b-a3b-q4-k-m-turboquant", 2),
        ("ternary-bonsai-27b", 3),
        ("ternary-bonsai-27b", 4),
        ("gemma-4-26b-a4b", 5),
        ("gemma-4-26b-a4b", 6),
    ]


def test_adapter_uses_openrouter_fallback_without_official_deepseek(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "OPENROUTER_API_KEY=openrouter-test\n",
        encoding="utf-8",
    )
    remote_models: list[str] = []

    def run_local(model_id, _port, _task, *, attempt, prior_result=None):
        return {
            "model_id": model_id,
            "attempt": attempt,
            "valid": False,
            "validation_errors": ["synthetic"],
            "proposal": None,
            "raw_response": "",
            "elapsed_seconds": 1,
            "peak_gpu_memory_mib": 1,
            "usage": {},
            "timings": {},
        }

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def open_remote(request, timeout):
        payload = json.loads(request.data)
        remote_models.append(payload["model"])
        attempt = len(remote_models) + 6
        proposal = {
            "protocol_version": "ninereeds_executor_v1",
            "job_id": "test-job",
            "attempt": attempt,
            "status": "SUCCESS",
            "reasoning_summary": "Valid proposal.",
            "assumptions": [],
            "artifacts": [],
            "requested_actions": [],
            "expected_validation": [],
            "risk_flags": [],
        }
        if payload["model"] != "deepseek-v4-pro":
            proposal["job_id"] = "wrong"
        response = {
            "choices": [{"message": {"content": json.dumps(proposal)}}],
            "usage": {},
        }
        return Response(json.dumps(response).encode())

    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
        server_starter=lambda *_args: (object(), 1234),
        server_stopper=lambda _process: None,
        task_runner=run_local,
        remote_opener=open_remote,
    )
    result = adapter.execute(execution_id="exec-remote-ladder", task=task())
    assert result["valid"] is False
    assert result["attempt_count"] == 9
    assert remote_models == [
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v4-flash",
    ]
    assert "DEEPSEEK_API_KEY is unavailable" in result["validation_errors"][0]


def test_official_deepseek_flash_is_primary_when_configured(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "DEEPSEEK_API_KEY=deepseek-test\n",
        encoding="utf-8",
    )
    requests: list[dict] = []
    timeouts: list[int] = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def open_remote(request, timeout):
        payload = json.loads(request.data)
        requests.append(payload)
        timeouts.append(timeout)
        proposal = {
            "protocol_version": "ninereeds_executor_v1",
            "job_id": "test-job",
            "attempt": 1,
            "status": "SUCCESS",
            "reasoning_summary": "Valid proposal.",
            "assumptions": [],
            "artifacts": [],
            "requested_actions": [],
            "expected_validation": [],
            "risk_flags": [],
        }
        response = {
            "choices": [{"message": {"content": json.dumps(proposal)}}],
            "usage": {},
        }
        return Response(json.dumps(response).encode())

    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
        server_starter=lambda *_args: pytest.fail("local fallback should not start"),
        server_stopper=lambda _process: None,
        task_runner=lambda model_id, _port, _task, *, attempt, prior_result=None: {
            "model_id": model_id,
            "attempt": attempt,
            "valid": False,
            "validation_errors": ["force remote fallback"],
        },
        remote_opener=open_remote,
    )
    active_rungs = []
    result = adapter.execute(
        execution_id="exec-official-flash",
        task=task(),
        rung_callback=active_rungs.append,
    )

    assert result["valid"] is True
    assert result["model_id"] == "deepseek:deepseek-v4-flash"
    assert result["attempt_count"] == 1
    assert result["executor_ladder"] == [
        "deepseek:deepseek-v4-flash",
        "qwen3.6-35b-a3b-q4-k-m-turboquant",
        "ternary-bonsai-27b",
        "gemma-4-26b-a4b",
        "deepseek:deepseek-v4-pro",
    ]
    assert requests[0]["model"] == "deepseek-v4-flash"
    assert requests[0]["thinking"] == {"type": "enabled"}
    assert requests[0]["reasoning_effort"] == "max"
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert "max_tokens" not in requests[0]
    assert timeouts == [3600]
    assert active_rungs == ["deepseek:deepseek-v4-flash"]


def test_qwen_turboquant_is_immediate_fallback_after_official_flash(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "DEEPSEEK_API_KEY=deepseek-test\n",
        encoding="utf-8",
    )
    started: list[str] = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def open_remote(request, timeout):
        payload = json.loads(request.data)
        proposal = {
            "protocol_version": "ninereeds_executor_v1",
            "job_id": "wrong",
            "attempt": 1 if not started else 2,
            "status": "SUCCESS",
            "reasoning_summary": "Force the local fallback.",
            "assumptions": [],
            "artifacts": [],
            "requested_actions": [],
            "expected_validation": [],
            "risk_flags": [],
        }
        return Response(
            json.dumps(
                {
                    "choices": [{"message": {"content": json.dumps(proposal)}}],
                    "usage": {},
                }
            ).encode()
        )

    def start_local(model_id, *_args):
        started.append(model_id)
        return object(), 1234

    def run_local(model_id, _port, _task, *, attempt, prior_result=None):
        return {
            "model_id": model_id,
            "attempt": attempt,
            "valid": True,
            "validation_errors": [],
            "proposal": {"artifacts": []},
            "elapsed_seconds": 1,
            "peak_gpu_memory_mib": 1,
            "usage": {},
            "timings": {},
        }

    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
        server_starter=start_local,
        server_stopper=lambda _process: None,
        task_runner=run_local,
        remote_opener=open_remote,
    )
    result = adapter.execute(
        execution_id="exec-qwen-fallback",
        task=task(),
        max_model_attempts=1,
    )

    assert result["valid"] is True
    assert result["model_id"] == "qwen3.6-35b-a3b-q4-k-m-turboquant"
    assert result["attempt_count"] == 2
    assert started == ["qwen3.6-35b-a3b-q4-k-m-turboquant"]


def test_remote_inference_renews_progress_while_waiting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".env").write_text(
        "DEEPSEEK_API_KEY=deepseek-test\n",
        encoding="utf-8",
    )
    renewals = 0

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def open_remote(request, timeout):
        time.sleep(0.04)
        proposal = {
            "protocol_version": "ninereeds_executor_v1",
            "job_id": "test-job",
            "attempt": 1,
            "status": "SUCCESS",
            "reasoning_summary": "Valid proposal.",
            "assumptions": [],
            "artifacts": [],
            "requested_actions": [],
            "expected_validation": [],
            "risk_flags": [],
        }
        return Response(
            json.dumps(
                {
                    "choices": [{"message": {"content": json.dumps(proposal)}}],
                    "usage": {},
                }
            ).encode()
        )

    def progress() -> None:
        nonlocal renewals
        renewals += 1

    monkeypatch.setattr(
        "training.pipeline.control.executor_adapter.REMOTE_HEARTBEAT_SECONDS",
        0.01,
    )
    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
        server_starter=lambda *_args: pytest.fail("local fallback should not start"),
        server_stopper=lambda _process: None,
        task_runner=lambda model_id, _port, _task, *, attempt, prior_result=None: {
            "model_id": model_id,
            "attempt": attempt,
            "valid": False,
            "validation_errors": ["force remote fallback"],
        },
        remote_opener=open_remote,
    )

    result = adapter.execute(
        execution_id="exec-heartbeat",
        task=task(),
        progress_callback=progress,
    )

    assert result["valid"] is True
    assert renewals >= 3


def test_adapter_reports_block_only_after_entire_ladder_is_exhausted(
    tmp_path: Path,
) -> None:
    def run_local(model_id, _port, _task, *, attempt, prior_result=None):
        return {
            "model_id": model_id,
            "attempt": attempt,
            "valid": False,
            "validation_errors": ["invalid proposal"],
            "proposal": None,
            "raw_response": "",
            "elapsed_seconds": 1,
            "peak_gpu_memory_mib": 1,
            "usage": {},
            "timings": {},
        }

    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
        server_starter=lambda *_args: (object(), 1234),
        server_stopper=lambda _process: None,
        task_runner=run_local,
    )
    result = adapter.execute(execution_id="exec-exhausted", task=task())
    assert result["valid"] is False
    assert result["attempt_count"] == 8
    assert [attempt["model_id"] for attempt in result["attempts"]] == [
        "qwen3.6-35b-a3b-q4-k-m-turboquant",
        "qwen3.6-35b-a3b-q4-k-m-turboquant",
        "ternary-bonsai-27b",
        "ternary-bonsai-27b",
        "gemma-4-26b-a4b",
        "gemma-4-26b-a4b",
        "openrouter:deepseek-v4-flash",
        "deepseek:deepseek-v4-pro",
    ]
    assert "DEEPSEEK_API_KEY is unavailable" in result["validation_errors"][0]
    assert result["failure_report"]["status"] == "fallback"
    assert result["failure_report"]["author_executor"] == "deterministic-harness"
    assert result["failure_report"]["attempt_count"] == 8


def test_deepseek_pro_writes_report_after_full_ladder_exhaustion(
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "OPENROUTER_API_KEY=openrouter-test\nDEEPSEEK_API_KEY=deepseek-test\n",
        encoding="utf-8",
    )
    script_responses = 0
    diagnostic_requests = 0

    def run_local(model_id, _port, _task, *, attempt, prior_result=None):
        return {
            "model_id": model_id,
            "attempt": attempt,
            "valid": False,
            "validation_errors": [f"{model_id} invalid"],
            "proposal": None,
            "raw_response": "invalid local response",
            "elapsed_seconds": 1,
            "peak_gpu_memory_mib": 1,
            "usage": {},
            "timings": {},
        }

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def open_remote(request, timeout):
        nonlocal script_responses, diagnostic_requests
        payload = json.loads(request.data)
        system = payload["messages"][0]["content"]
        if "postmortem" in system:
            diagnostic_requests += 1
            content = {
                "summary": "All script proposals failed their deterministic contracts.",
                "attempted_approaches": [
                    "Local models attempted schema-conforming envelopes.",
                    "Remote models attempted validation-informed repairs.",
                ],
                "failure_causes": [
                    "Envelope identity and artifact serialization remained invalid."
                ],
                "recommended_orchestrator_action": (
                    "Reduce the task contract and inspect serialization constraints."
                ),
            }
        else:
            script_responses += 1
            content = {
                "protocol_version": "ninereeds_executor_v1",
                "job_id": "wrong",
                "attempt": script_responses + 6,
                "status": "SUCCESS",
                "reasoning_summary": "Invalid proposal.",
                "assumptions": [],
                "artifacts": [],
                "requested_actions": [],
                "expected_validation": [],
                "risk_flags": [],
            }
        response = {
            "choices": [{"message": {"content": json.dumps(content)}}],
            "usage": {},
        }
        return Response(json.dumps(response).encode())

    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
        server_starter=lambda *_args: (object(), 1234),
        server_stopper=lambda _process: None,
        task_runner=run_local,
        remote_opener=open_remote,
    )
    result = adapter.execute(execution_id="exec-postmortem", task=task())
    report = result["failure_report"]
    assert result["valid"] is False
    assert result["attempt_count"] == 10
    assert script_responses == 4
    assert diagnostic_requests == 1
    assert report["status"] == "completed"
    assert report["author_executor"] == "deepseek:deepseek-v4-pro"
    assert report["diagnostic_error"] is None
    assert report["attempt_count"] == 10
    assert "deterministic contracts" in report["summary"]


def test_long_context_routes_to_qwen_turboquant(tmp_path: Path) -> None:
    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
    )
    assert adapter.select_model(None, 50000) == "qwen3.6-35b-a3b-q4-k-m-turboquant"
    with pytest.raises(ExecutorAdapterError, match="above 32K"):
        adapter.select_model("gemma-4-26b-a4b", 50000)


def test_adapter_rejects_context_outside_material_roots(tmp_path: Path) -> None:
    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
    )
    value = task()
    value["context_files"] = [".env"]
    with pytest.raises(ExecutorAdapterError, match="material allowlist"):
        adapter.validate_task(value)


def test_adapter_can_read_training_data_but_still_cannot_write_there(
    tmp_path: Path,
) -> None:
    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
    )
    material = tmp_path / "training_data/concepts/box.md"
    material.parent.mkdir(parents=True)
    material.write_text("A box is a container.", encoding="utf-8")
    value = task()
    value["context_files"] = ["training_data/concepts/box.md"]
    adapter.validate_task(value)

    value["allowed_artifact_paths"] = ["training_data/generated.json"]
    with pytest.raises(ExecutorAdapterError, match="training root"):
        adapter.validate_task(value)


def test_adapter_can_generate_ephemeral_material_before_executor_call(
    tmp_path: Path,
) -> None:
    class Generator:
        def generate(self, request):
            assert request["provider_order"] == ["deepseek", "openrouter", "nvidia"]
            return {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "text": "Generated teaching evidence.",
            }

    def run_task(_model, _port, value, *, attempt, prior_result=None):
        assert value["generated_material"] == "Generated teaching evidence."
        return {
            "attempt": attempt,
            "valid": True,
            "validation_errors": [],
            "proposal": {"artifacts": []},
            "elapsed_seconds": 1,
            "peak_gpu_memory_mib": 1,
            "usage": {},
            "timings": {},
        }

    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
        server_starter=lambda *_args: (object(), 1234),
        server_stopper=lambda _process: None,
        task_runner=run_task,
        material_generator=Generator(),
    )
    value = task()
    value["material_generation"] = {
        "prompt": "Create missing material.",
        "provider_order": ["deepseek", "openrouter", "nvidia"],
        "max_tokens": 256,
    }
    result = adapter.execute(execution_id="exec-material", task=value)
    assert result["material_generation"]["provider"] == "deepseek"
