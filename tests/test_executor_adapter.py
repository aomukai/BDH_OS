from __future__ import annotations

import json
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


def test_adapter_repairs_once_and_defaults_to_gemma(tmp_path: Path) -> None:
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
    assert result["model_id"] == "gemma-4-26b-a4b"
    assert result["valid"] is True
    assert result["attempt_count"] == 2
    assert attempts == 2


def test_long_context_routes_to_bonsai(tmp_path: Path) -> None:
    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
    )
    assert adapter.select_model(None, 50000) == "ternary-bonsai-27b"
    with pytest.raises(ExecutorAdapterError, match="above 32K"):
        adapter.select_model("gemma-4-26b-a4b", 50000)


def test_adapter_rejects_context_outside_training_root(tmp_path: Path) -> None:
    adapter = ExecutorAdapter(
        repo_root=tmp_path,
        config_path=config(tmp_path / "models.json"),
    )
    value = task()
    value["context_files"] = [".env"]
    with pytest.raises(ExecutorAdapterError, match="escapes"):
        adapter.validate_task(value)
