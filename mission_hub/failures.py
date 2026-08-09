"""Durable critical-job incidents and bounded, advisory-only Sol escalation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Callable

from .config import ConfigBundle
from .jsonutil import canonical_json, content_hash
from .schema import load_schema, validate


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


class CriticalFailureRecorder:
    """Write one operational incident per critical run and optionally ask Sol.

    The database/event chain remains the permanent lifecycle evidence. These
    bounded files are the human-facing seven-day diagnostic window. Sol is a
    read-only adviser: its response cannot perform or authorize a transition.
    """

    def __init__(self, bundle: ConfigBundle, *, runner: Runner = subprocess.run):
        self.bundle = bundle
        self.settings = bundle.failure_logging
        self.emergency = bundle.emergency
        self.root = Path(self.settings["root"]).resolve()
        self.runner = runner

    def record(
        self,
        *,
        job: dict[str, Any],
        run: dict[str, Any],
        failure: dict[str, Any],
        actor: str,
        phase: str,
        invoke_emergency: bool = True,
    ) -> Path | None:
        definition = self.bundle.jobs.get(job["job_type"])
        if not self.settings["enabled"] or definition is None or not definition["critical"]:
            return None
        observed = _now()
        self._prune(observed)
        message = str(failure.get("message", ""))[: self.settings["max_message_characters"]]
        safe_failure = {
            "class": str(failure.get("class", "")),
            "code": str(failure.get("code", "")),
            "message": message,
        }
        for key in ("failed_output_artifact_id", "failed_output_sha256"):
            if failure.get(key):
                safe_failure[key] = str(failure[key])
        incident: dict[str, Any] = {
            "schema_version": "ninereeds_critical_job_failure_v1",
            "observed_at": _stamp(observed),
            "phase": phase,
            "actor": actor,
            "config_sha256": self.bundle.sha256,
            "job": {
                "id": job["id"],
                "type": job["job_type"],
                "version": job["job_version"],
                "input_sha256": job["input_sha256"],
                "critical": True,
            },
            "run": {
                "id": run["id"],
                "attempt": run["attempt"],
                "machine_id": run["machine_id"],
                "deployment_id": run["deployment_id"],
            },
            "failure": safe_failure,
            "emergency": {"mode": self.emergency["mode"], "invoked": False},
        }
        incident["fingerprint"] = content_hash({
            "job_type": job["job_type"], "run_id": run["id"], "failure": safe_failure,
        })
        path = self.root / observed.strftime("%Y-%m-%d") / (
            observed.strftime("%Y%m%dT%H%M%S.%fZ") + f"--{run['id']}.json"
        )
        self._atomic_json(path, incident)
        if invoke_emergency:
            self.escalate(path)
        return path

    def escalate(self, path: Path | None) -> None:
        if path is None or self.emergency["mode"] != "sol_advisory" or not self.emergency["invoke_on_critical_failure"]:
            return
        incident = json.loads(path.read_text(encoding="utf-8"))
        incident["emergency"] = self._invoke_sol(incident)
        self._atomic_json(path, incident)

    def _invoke_sol(self, incident: dict[str, Any]) -> dict[str, Any]:
        encoded = canonical_json(incident).encode("utf-8")
        if len(encoded) > self.emergency["max_incident_bytes"]:
            return {"mode": "sol_advisory", "invoked": False, "error": "incident exceeds configured bound"}
        repo_root = self.bundle.root.parent.parent
        schema_path = (repo_root / self.emergency["response_schema"]).resolve()
        command = [
            self.emergency["executable"], "--ask-for-approval", "never", "exec",
            "--ephemeral", "--ignore-user-config", "--model", self.emergency["model"],
            "--sandbox", "read-only", "--skip-git-repo-check", "--output-schema", str(schema_path),
            "--color", "never", "-C", str(repo_root), "-",
        ]
        prompt = (
            "You are Sol, the emergency diagnostic adviser for the Ninereeds Mission Hub. "
            "Diagnose the immutable incident below. Return only the schema-bound JSON. "
            "You have no authority to retry work, mutate files or state, change budgets, "
            "wake campaigns, or approve training. Recommend operator actions only.\n\n"
            + encoded.decode("utf-8")
        )
        environment = dict(os.environ)
        # The daemon deliberately runs with ProtectHome=read-only.  Codex still
        # needs a small writable state directory to initialize its app-server
        # and PATH aliases, so keep that state inside Mission Hub's already
        # writable boundary.  Authentication remains the operator-owned file;
        # the link grants no broader write access to the home directory.
        sol_home = self.root.parent / "sol-codex-home"
        sol_home.mkdir(mode=0o700, parents=True, exist_ok=True)
        auth_source = Path.home() / ".codex" / "auth.json"
        auth_link = sol_home / "auth.json"
        if auth_source.is_file() and not auth_link.exists():
            auth_link.symlink_to(auth_source)
        environment["CODEX_HOME"] = str(sol_home)
        try:
            completed = self.runner(
                command, input=prompt, text=True, capture_output=True,
                timeout=self.emergency["timeout_seconds"], check=False,
                env=environment,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"mode": "sol_advisory", "invoked": True, "error": f"{type(exc).__name__}: {exc}"}
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "")[-3000:].strip()
            return {"mode": "sol_advisory", "invoked": True, "error": f"exit {completed.returncode}: {detail}"}
        try:
            advisory = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            return {"mode": "sol_advisory", "invoked": True, "error": f"invalid JSON: {exc}"}
        errors = validate(advisory, load_schema(repo_root, self.emergency["response_schema"]))
        if errors:
            return {"mode": "sol_advisory", "invoked": True, "error": "invalid advisory: " + "; ".join(errors)}
        return {"mode": "sol_advisory", "invoked": True, "advisory": advisory}

    def _prune(self, observed: datetime) -> None:
        cutoff = observed - timedelta(days=self.settings["retention_days"])
        if not self.root.exists():
            return
        for path in self.root.glob("*/*.json"):
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                path.relative_to(self.root)
                if modified < cutoff:
                    path.unlink()
            except (OSError, ValueError):
                continue
        for directory in self.root.iterdir():
            if directory.is_dir():
                try:
                    directory.rmdir()
                except OSError:
                    pass

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
