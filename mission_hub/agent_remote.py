"""Forced-command wrapper for the restricted trainbox SSH key."""

from __future__ import annotations

import os
import shlex
import sys

from .agent_cli import main as agent_main


def main() -> int:
    required = {
        "config": os.environ.get("NINEREEDS_AGENT_CONFIG"),
        "machine": os.environ.get("NINEREEDS_AGENT_MACHINE_ID"),
        "manifest": os.environ.get("NINEREEDS_AGENT_DEPLOYMENT_MANIFEST"),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        print(f"agent boundary is missing environment: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        original = shlex.split(os.environ.get("SSH_ORIGINAL_COMMAND", ""))
    except ValueError:
        return 2
    valid = original in (["ping"], ["execute"])
    if original and original[0] == "artifact-put" and len(original) == 7:
        valid = True
    if original and original[0] == "artifact-get" and len(original) == 8:
        valid = True
    if not valid:
        print("command refused", file=sys.stderr)
        return 2
    sys.argv = [
        "ninereeds-agent",
        "--config", required["config"],
        "--machine-id", required["machine"],
        "--deployment-manifest", required["manifest"],
        *original,
    ]
    return agent_main()


if __name__ == "__main__":
    raise SystemExit(main())
