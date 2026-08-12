"""Cross-process ownership for the trainbox GPU resource."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
from pathlib import Path
import shutil
import subprocess
from typing import Iterator, TextIO


GPU_JOB_TYPES = {
    "system.gpu_probe", "system.image_review_probe", "model.initialize", "model.train", "model.evaluate",
    "model.multimodal_evaluate", "model.chat", "model.visual_train",
    "model.multimodal_train", "model.merge", "checkpoint.probe",
    "checkpoint.compare", "executor.generate", "visual.generate",
    "visual.inspect", "visual.caption", "visual.review", "visual.encode",
    "visual.features_finalize",
}

GPU_PREFLIGHT_JOB_TYPES = GPU_JOB_TYPES - {"system.gpu_probe"}
GPU_REQUIRED_DEVICE_INDICES = [0, 1]
GPU_MINIMUM_FREE_MEMORY_MIB = 10240
GPU_PREFLIGHT_TIMEOUT_SECONDS = 5


class GPUResourceBusy(RuntimeError):
    pass


class GPUCapacityUnavailable(OSError):
    """The commissioned GPUs do not have enough free memory to start safely."""


def require_gpu_capacity(
    required_device_indices: list[int], minimum_free_memory_mib: int, *,
    timeout_seconds: int, runner=subprocess.run,
) -> list[dict[str, int | str]]:
    """Refuse a GPU launch before model loading when VRAM is already occupied.

    The advisory file lock coordinates Ninereeds processes.  This check covers
    CUDA consumers outside that lock (including manually launched or orphaned
    processes) and makes the refusal an operational/transient failure.
    """
    executable = shutil.which("nvidia-smi")
    if executable is None:
        raise GPUCapacityUnavailable("GPU preflight could not find nvidia-smi")
    command = [
        executable,
        "--query-gpu=index,name,memory.total,memory.free",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = runner(
            command, capture_output=True, text=True,
            timeout=timeout_seconds, check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GPUCapacityUnavailable(f"GPU preflight could not inspect CUDA memory: {exc}") from exc
    observations: dict[int, dict[str, int | str]] = {}
    try:
        for line in completed.stdout.splitlines():
            fields = [field.strip() for field in line.split(",")]
            if len(fields) != 4:
                continue
            index, name, total, free = fields
            observations[int(index)] = {
                "index": int(index), "name": name,
                "memory_total_mib": int(total), "memory_free_mib": int(free),
            }
    except ValueError as exc:
        raise GPUCapacityUnavailable("GPU preflight received malformed nvidia-smi output") from exc
    missing = sorted(set(required_device_indices) - set(observations))
    if missing:
        raise GPUCapacityUnavailable(
            "GPU preflight is missing commissioned device indices: "
            + ", ".join(str(index) for index in missing)
        )
    insufficient = [
        observations[index] for index in required_device_indices
        if int(observations[index]["memory_free_mib"]) < minimum_free_memory_mib
    ]
    if insufficient:
        detail = "; ".join(
            f"cuda:{item['index']} has {item['memory_free_mib']} MiB free of "
            f"{item['memory_total_mib']} MiB"
            for item in insufficient
        )
        raise GPUCapacityUnavailable(
            f"GPU preflight requires at least {minimum_free_memory_mib} MiB free on every "
            f"commissioned device; {detail}"
        )
    return [observations[index] for index in required_device_indices]


@contextmanager
def gpu_resource(state_root: str | Path, *, wait: bool) -> Iterator[TextIO]:
    root = Path(state_root)
    root.mkdir(parents=True, exist_ok=True)
    handle = (root / "gpu-resource.lock").open("a+", encoding="utf-8")
    operation = fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB)
    try:
        try:
            fcntl.flock(handle.fileno(), operation)
        except BlockingIOError as exc:
            raise GPUResourceBusy("the training GPU is currently assigned to another job") from exc
        yield handle
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
