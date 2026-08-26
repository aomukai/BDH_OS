#!/usr/bin/env python3
"""Start or resume the durable Campaign 35 image-material controller."""

from pathlib import Path
import sys

# Make the documented direct-script invocation work from the repository root as
# well as an installed environment.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from image_registry.campaign35_word_loop_controller import main


if __name__ == "__main__":
    raise SystemExit(main())
