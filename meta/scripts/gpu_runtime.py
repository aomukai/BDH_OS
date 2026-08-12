#!/usr/bin/env python3
"""Run a GPU Python script and terminate it if its Mission Hub agent dies."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import runpy
import signal
import sys


def _die_with_agent() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM) != 0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), "could not install parent-death signal")
    if os.getppid() == 1:
        os.kill(os.getpid(), signal.SIGTERM)


def main() -> int:
    _die_with_agent()
    if len(sys.argv) < 2:
        raise SystemExit("usage: gpu_runtime.py SCRIPT [ARGS...]")
    script = Path(sys.argv[1]).resolve()
    if not script.is_file():
        raise SystemExit(f"GPU script is missing: {script}")
    sys.argv = [str(script), *sys.argv[2:]]
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
