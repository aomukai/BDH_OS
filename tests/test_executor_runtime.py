from __future__ import annotations

from pathlib import Path

from training.executor import run_bakeoff
from training.executor.run_bakeoff import (
    build_server_command,
    context_candidates,
    start_server,
)


def test_context_candidates_preserve_preference_and_job_minimum() -> None:
    model = {
        "context": 256000,
        "context_fallbacks": [128000, 128000],
        "_minimum_context": 100000,
    }
    assert context_candidates(model) == [256000, 128000]

    model["_minimum_context"] = 200000
    assert context_candidates(model) == [256000]


def test_docker_server_command_preserves_executor_contract() -> None:
    config = {
        "executor_root": "/home/aomukai/executor",
        "visible_cuda_devices": "0",
    }
    model = {
        "runtime_kind": "docker",
        "container_image": "nvidia/cuda:12.4.1-devel-ubuntu22.04",
        "runtime": "runtimes/turbo/build/bin/llama-server",
        "model": "models/qwen.gguf",
        "gpu_layers": 999,
        "server_args": [
            "-ctk",
            "turbo4",
            "-ctv",
            "turbo3",
            "--n-cpu-moe",
            "36",
            "--no-mmap",
            "--mlock",
        ],
    }

    command, container_name = build_server_command(
        "qwen3.6-35b-a3b-q4-k-m-turboquant",
        model,
        config,
        port=43123,
        context=256000,
    )

    assert command[:3] == ["docker", "run", "--rm"]
    assert container_name == (
        "ninereeds-executor-qwen3-6-35b-a3b-q4-k-m-turboquant-43123"
    )
    assert ["--network", "host"] == command[
        command.index("--network") : command.index("--network") + 2
    ]
    assert ["--gpus", "device=0"] == command[
        command.index("--gpus") : command.index("--gpus") + 2
    ]
    assert "memlock=-1:-1" in command
    assert "--cap-add=IPC_LOCK" in command
    assert (
        "type=bind,src=/home/aomukai/executor,"
        "dst=/home/aomukai/executor,readonly"
    ) in command
    assert command[-10:] == [
        "-ngl",
        "999",
        "-ctk",
        "turbo4",
        "-ctv",
        "turbo3",
        "--n-cpu-moe",
        "36",
        "--no-mmap",
        "--mlock",
    ]
    assert command[command.index("-c") + 1] == "256000"


def test_host_server_command_remains_supported() -> None:
    command, container_name = build_server_command(
        "bonsai",
        {
            "runtime": "runtimes/bonsai/llama-server",
            "model": "models/bonsai.gguf",
            "gpu_layers": 99,
        },
        {
            "executor_root": "/srv/executor",
            "visible_cuda_devices": "0",
        },
        port=41000,
        context=131072,
    )
    assert container_name is None
    assert command[0] == "/srv/executor/runtimes/bonsai/llama-server"
    assert "docker" not in command


def test_start_server_falls_back_and_records_actual_context(
    tmp_path: Path, monkeypatch
) -> None:
    commands: list[list[str]] = []

    class Process:
        def __init__(self, return_code):
            self.return_code = return_code

        def poll(self):
            return self.return_code

    processes = [Process(1), Process(None)]

    def popen(command, **_kwargs):
        commands.append(command)
        return processes.pop(0)

    monkeypatch.setattr(run_bakeoff.subprocess, "Popen", popen)
    monkeypatch.setattr(run_bakeoff, "free_port", lambda: 42111)
    monkeypatch.setattr(run_bakeoff, "http_json", lambda *_args, **_kwargs: {"status": "ok"})

    process, port = start_server(
        "qwen-test",
        {
            "runtime": "runtime/llama-server",
            "model": "models/qwen.gguf",
            "context": 256000,
            "context_fallbacks": [128000],
            "gpu_layers": 999,
        },
        {
            "executor_root": str(tmp_path / "executor"),
            "visible_cuda_devices": "0",
        },
        tmp_path / "server.log",
    )

    assert port == 42111
    assert getattr(process, "_ninereeds_context") == 128000
    assert [command[command.index("-c") + 1] for command in commands] == [
        "256000",
        "128000",
    ]
    getattr(process, "_ninereeds_log_handle").close()
