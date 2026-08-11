"""Cross-process ownership for the trainbox GPU resource."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
from pathlib import Path
from typing import Iterator, TextIO


GPU_JOB_TYPES = {
    "system.gpu_probe", "model.initialize", "model.train", "model.evaluate",
    "model.multimodal_evaluate", "model.chat", "model.visual_train",
    "model.multimodal_train", "model.merge", "checkpoint.probe",
    "checkpoint.compare", "executor.generate", "visual.generate",
    "visual.inspect", "visual.caption", "visual.review", "visual.encode",
    "visual.features_finalize",
}


class GPUResourceBusy(RuntimeError):
    pass


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
