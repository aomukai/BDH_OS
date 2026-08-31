from __future__ import annotations

import subprocess

import pytest

from mission_hub.gpu_lock import (
    GPUCapacityUnavailable, GPUResourceBusy, gpu_resource, require_gpu_capacity,
)

def test_gpu_resource_refuses_a_second_owner(tmp_path) -> None:
    with gpu_resource(tmp_path, wait=False):
        with pytest.raises(GPUResourceBusy):
            with gpu_resource(tmp_path, wait=False):
                pass


def test_gpu_preflight_requires_both_commissioned_devices(monkeypatch) -> None:
    monkeypatch.setattr("mission_hub.gpu_lock.shutil.which", lambda _name: "/usr/bin/nvidia-smi")

    def runner(command, **kwargs):
        assert command[1:] == [
            "--query-gpu=index,name,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ]
        assert kwargs["timeout"] == 5
        return subprocess.CompletedProcess(
            command, 0,
            "0, NVIDIA GeForce RTX 3060, 11915, 11020\n"
            "1, NVIDIA GeForce RTX 3060, 11915, 10888\n",
            "",
        )

    observed = require_gpu_capacity([0, 1], 10240, timeout_seconds=5, runner=runner)

    assert [item["index"] for item in observed] == [0, 1]


def test_gpu_preflight_refuses_external_vram_pressure(monkeypatch) -> None:
    monkeypatch.setattr("mission_hub.gpu_lock.shutil.which", lambda _name: "/usr/bin/nvidia-smi")

    def runner(command, **_kwargs):
        return subprocess.CompletedProcess(
            command, 0,
            "0, NVIDIA GeForce RTX 3060, 11915, 46\n"
            "1, NVIDIA GeForce RTX 3060, 11915, 11000\n",
            "",
        )

    with pytest.raises(GPUCapacityUnavailable, match=r"cuda:0 has 46 MiB free"):
        require_gpu_capacity([0, 1], 10240, timeout_seconds=5, runner=runner)


def test_gpu_preflight_refuses_a_missing_second_gpu(monkeypatch) -> None:
    monkeypatch.setattr("mission_hub.gpu_lock.shutil.which", lambda _name: "/usr/bin/nvidia-smi")

    def runner(command, **_kwargs):
        return subprocess.CompletedProcess(
            command, 0, "0, NVIDIA GeForce RTX 3060, 11915, 11000\n", "",
        )

    with pytest.raises(GPUCapacityUnavailable, match="missing commissioned device indices: 1"):
        require_gpu_capacity([0, 1], 10240, timeout_seconds=5, runner=runner)
