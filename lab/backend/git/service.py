from __future__ import annotations

import subprocess
import time
from typing import Any

from lab.backend.config import LabConfig


class GitService:
    def __init__(self, config: LabConfig) -> None:
        self.config = config
        self.last_pull: dict[str, Any] | None = None

    def status(self) -> dict[str, Any]:
        branch = self._run(["git", "branch", "--show-current"], timeout=5)
        dirty = self._run(["git", "status", "--porcelain"], timeout=8)
        return {
            "branch": branch["stdout"].strip() if branch["ok"] else None,
            "dirty": bool(dirty["stdout"].strip()) if dirty["ok"] else None,
            "dirty_paths": dirty["stdout"].splitlines() if dirty["ok"] else [],
            "last_pull": self.last_pull,
            "pull_enabled": self.config.git_pull_enabled,
            "pull_interval_seconds": self.config.git_pull_interval_seconds,
        }

    def pull(self, reason: str = "manual") -> dict[str, Any]:
        started = time.time()
        dirty = self._run(["git", "status", "--porcelain"], timeout=8)
        if not dirty["ok"]:
            result = {"ok": False, "skipped": True, "reason": "git status failed", "detail": dirty}
            self.last_pull = result | {"started_at": started, "finished_at": time.time()}
            return self.last_pull
        dirty_paths = dirty["stdout"].splitlines()
        if dirty_paths and not self.config.git_pull_allow_dirty:
            result = {
                "ok": False,
                "skipped": True,
                "reason": "worktree has local changes; set LAB_GIT_ALLOW_DIRTY=1 to override",
                "dirty_paths": dirty_paths,
            }
            self.last_pull = result | {"started_at": started, "finished_at": time.time()}
            return self.last_pull
        result = self._run(["git", "pull", "--ff-only"], timeout=45)
        self.last_pull = {
            "ok": result["ok"],
            "skipped": False,
            "reason": reason,
            "stdout": result["stdout"],
            "stderr": result["stderr"],
            "returncode": result["returncode"],
            "started_at": started,
            "finished_at": time.time(),
        }
        return self.last_pull

    def _run(self, args: list[str], timeout: int) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                args,
                cwd=self.config.repo_root,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "stdout": "", "stderr": str(exc), "returncode": None}
        return {
            "ok": completed.returncode == 0,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
        }
