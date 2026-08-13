#!/usr/bin/env python3
"""Serve the commissioned Gemma image reviewer on both trainbox GPUs."""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import threading

from mission_hub.gpu_lock import (
    GPU_MINIMUM_FREE_MEMORY_MIB,
    GPU_PREFLIGHT_TIMEOUT_SECONDS,
    GPU_REQUIRED_DEVICE_INDICES,
    gpu_resource,
    require_gpu_capacity,
)
from mission_hub.handlers.image_review_probe import (
    MODEL_BYTES,
    MODEL_SHA256,
    PROJECTOR_BYTES,
    PROJECTOR_SHA256,
    _sha256,
    _start_server,
    _stop_server,
)


MODEL_DIRECTORY = "gemma-4-26b-a4b-it-q4km-c099eb48"
MODEL_FILENAME = "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"
PROJECTOR_FILENAME = "mmproj-BF16.gguf"


def _validated(path: Path, expected_bytes: int, expected_sha256: str) -> Path:
    if not path.is_file() or path.stat().st_size != expected_bytes:
        raise RuntimeError(f"commissioned model file is absent or has the wrong size: {path}")
    if _sha256(path) != expected_sha256:
        raise RuntimeError(f"commissioned model file has the wrong SHA-256: {path}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--port-gpu0", type=int, default=8792)
    parser.add_argument("--port-gpu1", type=int, default=8793)
    args = parser.parse_args()

    model_root = args.state_root / "models" / MODEL_DIRECTORY
    model = _validated(model_root / MODEL_FILENAME, MODEL_BYTES, MODEL_SHA256)
    projector = _validated(
        model_root / PROJECTOR_FILENAME, PROJECTOR_BYTES, PROJECTOR_SHA256
    )
    log_root = args.state_root / "image-review-api"
    log_root.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda _signum, _frame: stop.set())

    with gpu_resource(args.state_root, wait=False):
        require_gpu_capacity(
            GPU_REQUIRED_DEVICE_INDICES,
            GPU_MINIMUM_FREE_MEMORY_MIB,
            timeout_seconds=GPU_PREFLIGHT_TIMEOUT_SECONDS,
        )
        first = _start_server(model, projector, 0, args.port_gpu0, log_root / "gpu0.log")
        second = None
        try:
            second = _start_server(model, projector, 1, args.port_gpu1, log_root / "gpu1.log")
            while not stop.wait(2):
                failed = [
                    label
                    for label, process in (("gpu0", first), ("gpu1", second))
                    if process.poll() is not None
                ]
                if failed:
                    raise RuntimeError(
                        "image review subprocess exited unexpectedly: "
                        + ", ".join(failed)
                    )
        finally:
            _stop_server(first)
            if second is not None:
                _stop_server(second)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
