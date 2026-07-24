#!/usr/bin/env python3
"""Run a Cortex script while reusing the commissioned trainbox PyTorch install."""

from __future__ import annotations

import os
import runpy
import site
import sys
from pathlib import Path


DEFAULT_TORCH_SITE = Path(
    "/home/aomukai/.unsloth/studio/unsloth_studio/lib/python3.13/site-packages"
)


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: cortex_runtime.py SCRIPT [ARGS...]")
    torch_site = Path(os.environ.get("NINEREEDS_TORCH_SITE", str(DEFAULT_TORCH_SITE)))
    if not torch_site.is_dir():
        raise SystemExit(f"commissioned PyTorch site-packages is missing: {torch_site}")
    site.addsitedir(str(torch_site))
    script = Path(sys.argv[1]).resolve()
    if not script.is_file():
        raise SystemExit(f"Cortex script is missing: {script}")
    sys.path.insert(0, str(Path.cwd()))
    sys.argv = [str(script), *sys.argv[2:]]
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
