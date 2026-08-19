#!/usr/bin/env python3
"""Wait for trainbox encoding, retrieve ledgers, and start Campaign 35 M2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time


REMOTE_OUTPUT = "/home/aomukai/.local/share/ninereeds/trainbox-agent/campaign35-m2/output"


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=check)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default="ninereeds-trainbox")
    parser.add_argument(
        "--local-output", type=Path,
        default=Path.home() / ".local/share/ninereeds/mission-hub/campaign35-m2-material",
    )
    parser.add_argument("--poll-seconds", type=int, default=30)
    args = parser.parse_args()
    args.local_output.mkdir(parents=True, exist_ok=True)

    while True:
        manifest = run([
            "ssh", args.remote, "test", "-f", f"{REMOTE_OUTPUT}/manifest.json",
        ], check=False)
        if manifest.returncode == 0:
            break
        state = run([
            "ssh", args.remote, "systemctl", "--user", "is-active",
            "campaign35-m2-feature-build.service",
        ], check=False)
        if state.stdout.strip() != "active":
            evidence = run([
                "ssh", args.remote, "journalctl", "--user", "-u",
                "campaign35-m2-feature-build.service", "-n", "120", "--no-pager",
            ], check=False)
            raise RuntimeError("M2 feature build stopped before its manifest:\n" + evidence.stdout[-12000:])
        time.sleep(args.poll_seconds)

    run([
        "rsync", "-a",
        "--include=manifest.json", "--include=*-experience.json",
        "--include=*-m2-events.json", "--exclude=*",
        f"{args.remote}:{REMOTE_OUTPUT}/",
        str(args.local_output) + "/",
    ])
    material = json.loads((args.local_output / "manifest.json").read_text(encoding="utf-8"))
    if material.get("event_count") != 14_397 or material.get("session_count") != 15:
        raise RuntimeError("retrieved M2 manifest fails the frozen event/session contract")
    completed = run([
        "/usr/bin/python3", "-m", "meta.scripts.commission_campaign35_m2",
        "--manifest", str(args.local_output / "manifest.json"),
        "--local-experiences", str(args.local_output),
    ])
    print(completed.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
