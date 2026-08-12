"""Bounded Codex-backed candidate repair and local role deployment.

The model works only in a detached recovery worktree. Deterministic code then
checks every changed path, patch size, test command, source manifest, and active
deployment identity before Mission Hub may retry immutable work.
"""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable, Iterator

from .config import ConfigBundle, bundle_from_snapshot, load_config_bundle
from .deployment import DeploymentBuilder
from .errors import SafetyError
from .jsonutil import canonical_json
from .store import MissionHubStore
from .transport import SSHDispatcher


Runner = Callable[..., subprocess.CompletedProcess[str]]


class BoundedCodexRepairDriver:
    def __init__(
        self, store: MissionHubStore, bundle: ConfigBundle, *, runner: Runner = subprocess.run,
        repo_root: Path | None = None,
    ):
        self.store, self.bundle, self.runner = store, bundle, runner
        self.repo_root = (repo_root or Path(bundle.recovery["source_repository_root"])).resolve()
        self.policy = bundle.recovery

    def repair(self, context: dict[str, Any]) -> dict[str, Any]:
        if context["attempt"]["strategy"] == "principal_authorized_active_deployment_retry":
            return self._validate_active_replacement(context)
        if context["incident"]["category"] == "configuration":
            return self._rollback_configuration(context)
        attempt_id = context["attempt"]["id"]
        root = Path(self.bundle.base["hub"]["state_root"]).resolve() / "recovery" / "workspaces" / attempt_id
        actions: list[dict[str, Any]] = []
        root.parent.mkdir(parents=True, exist_ok=True)
        if root.exists():
            return self._failure("repair_workspace_exists", f"recovery workspace already exists: {root}")
        try:
            failed_manifest = json.loads(context["failed_deployment"]["manifest_json"])
            base_ref = failed_manifest.get("source", {}).get("git_head")
            if not isinstance(base_ref, str) or len(base_ref) < 7:
                return self._failure("failed_release_source_unavailable", "failed deployment does not preserve its exact Git source identity")
            self._run(["git", "cat-file", "-e", f"{base_ref}^{{commit}}"], cwd=self.repo_root, timeout=30)
            self._run(["git", "worktree", "add", "--detach", str(root), base_ref], cwd=self.repo_root, timeout=60)
            prompt_path = self._write_evidence(attempt_id, "repair-request.json", canonical_json({
                "schema_version": "ninereeds_bounded_repair_request_v1",
                "incident": context["incident"], "job": {
                    "id": context["job"]["id"], "type": context["job"]["job_type"],
                    "input_sha256": context["job"]["input_sha256"],
                }, "run": {
                    "id": context["run"]["id"], "deployment_id": context["run"]["deployment_id"],
                    "attempt": context["run"]["attempt"],
                }, "failure": context["failure"], "allowed_source_roots": self.policy["allowed_source_roots"],
                "protected_paths": self.policy["protected_paths"],
            }).encode("utf-8") + b"\n")
            codex_log = self._invoke_codex(root, prompt_path, attempt_id)
            changed = self._changed_files(root)
            self._validate_changed_files(changed)
            patch = self._git_bytes(root, "diff", "--binary", "--", *changed)
            if not patch:
                return self._failure("repair_made_no_change", "Codex completed without a source or configuration change")
            if len(patch) > self.policy["max_patch_bytes"]:
                raise SafetyError("repair patch exceeds configured byte bound")
            patch_path = self._write_evidence(attempt_id, "candidate.patch", patch)
            actions = [self._patch_action(changed, patch_path)]
            for scope, commands in (
                ("targeted", self.policy["targeted_test_commands"]),
                ("regression", self.policy["regression_test_commands"]),
            ):
                fixture_context = self._regression_fixtures(root) if scope == "regression" else nullcontext()
                with fixture_context:
                    for index, command in enumerate(commands, start=1):
                        completed = self._run(command, cwd=root, timeout=self.policy["attempt_timeout_seconds"], check=False)
                        transcript = (
                            f"command={json.dumps(command)}\nexit_code={completed.returncode}\n"
                            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n"
                        ).encode("utf-8", errors="replace")
                        transcript_path = self._write_evidence(attempt_id, f"{scope}-{index}.log", transcript)
                        action = self._test_action(scope, command, completed.returncode, transcript_path)
                        actions.append(action)
                        if completed.returncode != 0:
                            return {
                                "succeeded": False, "failure_code": f"{scope}_tests_failed",
                                "summary": f"{scope} validation failed with exit {completed.returncode}",
                                "actions": actions,
                            }
            self._run(["git", "add", "--", *changed], cwd=root, timeout=30)
            self._run([
                "git", "-c", "user.name=Ninereeds Recovery", "-c", "user.email=recovery@localhost",
                "commit", "-m", f"recovery: {context['incident']['failure_code']} ({attempt_id})",
            ], cwd=root, timeout=60)
            deployment_action = self._deploy_local_candidate(root, context)
            actions.append(deployment_action)
            return {
                "succeeded": True, "summary": "bounded source repair, targeted/regression validation, and candidate activation succeeded",
                "actions": actions,
            }
        except (OSError, subprocess.SubprocessError, SafetyError, ValueError, KeyError) as exc:
            return self._failure("repair_driver_exception", f"{type(exc).__name__}: {exc}", actions=actions)

    def _validate_active_replacement(self, context: dict[str, Any]) -> dict[str, Any]:
        """Adopt a newer already-active release without inventing a mutation.

        An incident can outlive the source repair and deployment that fixes it.
        In that case rolling configuration backward is both unnecessary and
        dangerous.  This path proves that the checkout exactly matches the
        distinct active deployment, reruns the configured test scopes, and
        hands the original immutable job back to normal recovery verification.
        """
        attempt_id = context["attempt"]["id"]
        actions: list[dict[str, Any]] = []
        try:
            active_config = self.store.active_config()
            active_deployment = self.store.active_deployment(context["job"]["requested_machine_id"])
            if active_deployment["id"] == context["failed_deployment"]["id"]:
                raise SafetyError("active-deployment retry requires a distinct replacement release")
            if active_deployment["config_snapshot_id"] != active_config["id"]:
                raise SafetyError("active replacement deployment does not use the active configuration")
            role_ids = [
                role_id for role_id, role in self.bundle.deployment_roles.items()
                if role["role"] == active_deployment["role"]
            ]
            if len(role_ids) != 1:
                raise SafetyError("active replacement deployment role is ambiguous")
            source = DeploymentBuilder(self.repo_root, self.bundle).source_manifest(role_ids[0])
            if not source["git_clean"] or source["source_sha256"] != active_deployment["source_sha256"]:
                raise SafetyError("current clean source does not match the active replacement deployment")
            for scope, commands in (
                ("targeted", self.policy["targeted_test_commands"]),
                ("regression", self.policy["regression_test_commands"]),
            ):
                # Unlike source-patch repair, this validates the canonical
                # checkout rather than an empty detached worktree. Its real
                # protected fixture roots already exist and must remain
                # untouched; the suite reads them in place.
                with nullcontext():
                    for index, command in enumerate(commands, start=1):
                        completed = self._run(
                            command, cwd=self.repo_root,
                            timeout=self.policy["attempt_timeout_seconds"], check=False,
                        )
                        transcript = (
                            f"command={json.dumps(command)}\nexit_code={completed.returncode}\n"
                            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n"
                        ).encode("utf-8", errors="replace")
                        transcript_path = self._write_evidence(
                            attempt_id, f"active-replacement-{scope}-{index}.log", transcript,
                        )
                        action = self._test_action(scope, command, completed.returncode, transcript_path)
                        actions.append(action)
                        if completed.returncode != 0:
                            return {
                                "succeeded": False, "failure_code": f"{scope}_tests_failed",
                                "summary": f"{scope} validation failed with exit {completed.returncode}",
                                "actions": actions,
                            }
            actions.append({"kind": "deployment", "status": "succeeded", "evidence": {
                "before_deployment_id": context["failed_deployment"]["id"],
                "after_deployment_id": active_deployment["id"], "active": True,
                "source_sha256": active_deployment["source_sha256"],
                "release_id": active_deployment["release_id"],
                "mode": "verified_already_active_replacement",
            }})
            return {
                "succeeded": True,
                "summary": "newer active deployment matched clean source and passed targeted/regression validation",
                "actions": actions,
            }
        except (OSError, subprocess.SubprocessError, SafetyError, ValueError, KeyError) as exc:
            return self._failure(
                "active_replacement_validation_failed", f"{type(exc).__name__}: {exc}", actions=actions,
            )

    def _rollback_configuration(self, context: dict[str, Any]) -> dict[str, Any]:
        attempt_id = context["attempt"]["id"]
        failed_snapshot_id = context["job"]["config_snapshot_id"]
        try:
            with self.store._connect() as db:
                rows = db.execute(
                    "SELECT * FROM config_snapshots WHERE state='superseded' ORDER BY activated_at DESC,created_at DESC",
                ).fetchall()
            selected = None
            for row in rows:
                payload = json.loads(row["payload_json"])
                try:
                    candidate = bundle_from_snapshot(self.bundle.root, payload)
                except Exception:
                    continue
                enabled = [key for key, value in candidate.machines.items() if value["enabled"]]
                with self.store._connect() as db:
                    retained = all(db.execute(
                        """SELECT 1 FROM deployments WHERE machine_id=? AND config_snapshot_id=?
                           AND status IN ('active','retired','candidate')""", (machine_id, row["id"]),
                    ).fetchone() is not None for machine_id in enabled)
                if retained:
                    selected = (dict(row), candidate)
                    break
            if selected is None:
                return self._failure("known_good_configuration_unavailable", "no validated superseded configuration with retained role deployments exists")
            target, candidate = selected
            integrity = self.store.integrity_report()
            targeted = self._write_evidence(
                attempt_id, "configuration-targeted.log",
                (json.dumps({"check": "bundle_from_snapshot", "bundle_sha256": candidate.sha256, "passed": True}, sort_keys=True) + "\n").encode(),
            )
            regression = self._write_evidence(
                attempt_id, "configuration-regression.log",
                (json.dumps({"check": "database_integrity", **integrity, "passed": integrity["sqlite_integrity"] == "ok" and integrity["event_chain_ok"]}, sort_keys=True) + "\n").encode(),
            )
            if integrity["sqlite_integrity"] != "ok" or not integrity["event_chain_ok"] or integrity["foreign_key_errors"]:
                return self._failure("known_good_validation_failed", "database integrity prevents safe configuration rollback")
            rollback = self.store.rollback_config(
                failed_snapshot_id=failed_snapshot_id, known_good_snapshot_id=target["id"],
                incident_id=context["incident"]["id"], reason="automatic rollback to latest validated retained configuration",
                actor="mission-hub:on-call-repair",
            )
            machine_id = context["job"]["requested_machine_id"]
            active_deployment = self.store.active_deployment(machine_id)
            return {
                "succeeded": True, "summary": "invalid configuration rolled back to the latest validated retained snapshot",
                "actions": [
                    {"kind": "configuration_change", "status": "succeeded", "evidence": {
                        "before_sha256": self.bundle.sha256, "after_sha256": candidate.sha256,
                        "failed_snapshot_id": failed_snapshot_id, "known_good_snapshot_id": target["id"],
                    }},
                    self._internal_test_action("targeted", ["internal", "bundle_from_snapshot"], targeted),
                    self._internal_test_action("regression", ["internal", "database_integrity"], regression),
                    {"kind": "deployment", "status": "succeeded", "evidence": {
                        "before_deployment_id": context["failed_deployment"]["id"],
                        "after_deployment_id": active_deployment["id"], "active": True,
                        "source_sha256": active_deployment["source_sha256"], "release_id": active_deployment["release_id"],
                    }},
                ],
            }
        except (OSError, SafetyError, ValueError, KeyError) as exc:
            return self._failure("configuration_rollback_failed", f"{type(exc).__name__}: {exc}")

    def _invoke_codex(self, worktree: Path, request_path: Path, attempt_id: str) -> Path:
        route = self.bundle.routes["operational-response"]
        model = self.bundle.models[route["ordered_model_ids"][0]]
        provider = self.bundle.providers[model["provider"]]
        if provider["kind"] != "codex_cli" or not provider["enabled"] or not model["enabled"]:
            raise SafetyError("bounded repair requires an enabled Codex CLI operational model")
        # Codex's final-message file is recovery evidence, not candidate
        # source. Keep it outside the detached Git worktree so an otherwise
        # valid repair cannot fail changed-path validation on our own file.
        final_path = self._evidence_directory(attempt_id) / "codex-final.txt"
        prompt = (
            "You are executing a bounded Ninereeds on-call software repair. Inspect the persisted request below and the repository. "
            "Repair the root cause inside the allowed source roots. Do not edit protected paths, Git configuration, evidence, credentials, "
            "checkpoints, training data, or archives. Do not commit, deploy, retry jobs, or claim success; deterministic machinery performs "
            "those steps. Make the smallest robust change and add or update targeted tests.\n\n"
            + request_path.read_text(encoding="utf-8")
        )
        command = [
            provider["endpoint"], "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--approve-for-me", "--skip-git-repo-check",
            "-C", str(worktree), "--model", model["exact_name"], "--output-last-message", str(final_path),
            "--color", "never", "-",
        ]
        completed = self.runner(
            command, input=prompt, text=True, capture_output=True,
            timeout=min(provider["timeout_seconds"], self.policy["attempt_timeout_seconds"]), check=False,
        )
        transcript = (
            f"returncode={completed.returncode}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n"
        ).encode("utf-8", errors="replace")
        log = self._write_evidence(attempt_id, "codex.log", transcript)
        if completed.returncode != 0:
            raise SafetyError(f"Codex repair process failed with exit {completed.returncode}; transcript={log}")
        return log

    def _deploy_local_candidate(self, root: Path, context: dict[str, Any]) -> dict[str, Any]:
        machine_id = context["job"]["requested_machine_id"]
        machine = self.bundle.machines[machine_id]
        repaired_bundle = load_config_bundle(root / "config" / "mission_hub")
        active = self.store.active_config()
        if repaired_bundle.sha256 != active["sha256"]:
            raise SafetyError("configuration-changing repairs require the configuration rollback/activation path")
        role_ids = [key for key, value in repaired_bundle.deployment_roles.items() if value["role"] == machine["role"]]
        if len(role_ids) != 1:
            raise SafetyError("executor role does not map to exactly one deployment role")
        old_manifest = json.loads(context["failed_deployment"]["manifest_json"])
        environment = old_manifest.get("environment")
        if not isinstance(environment, dict) or not environment:
            raise SafetyError("failed deployment has no reusable environment attestation")
        builder = DeploymentBuilder(root, repaired_bundle)
        manifest = builder.deployment_manifest(
            role_ids[0], machine_id=machine_id, config_snapshot_id=active["id"],
            environment=environment, allow_dirty_candidate=False,
        )
        if machine["transport"] == "local":
            manifest["installed_root"] = str(root)
        deployment_id = self.store.register_deployment(manifest, actor="mission-hub:on-call-repair", activate=False)
        manifest["id"] = deployment_id
        manifest_path = root / "RELEASE-MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        deployment_receipt: dict[str, Any]
        if machine["transport"] == "local":
            self.store.activate_registered_deployment(deployment_id, actor="mission-hub:on-call-repair")
            deployment_receipt = {"mode": "local_release_root", "installed_root": str(root)}
        elif machine["transport"] == "restricted_ssh":
            archive_path = self._evidence_directory(context["attempt"]["id"]) / f"{manifest['release_id']}.tar.gz"
            archive = builder.build_archive(manifest, archive_path)
            dispatcher = SSHDispatcher(repaired_bundle)
            installed = dispatcher.install_release(machine_id, manifest, archive)
            activated = dispatcher.activate_release(machine_id, manifest)
            self.store.activate_registered_deployment(deployment_id, actor="mission-hub:on-call-repair")
            deployment_receipt = {
                "mode": "restricted_ssh_atomic_release", "archive_sha256": archive["sha256"],
                "archive_bytes": archive["byte_size"], "install_receipt": installed,
                "activation_receipt": activated,
            }
        else:
            raise SafetyError("repair deployment requires local or restricted SSH transport")
        return {"kind": "deployment", "status": "succeeded", "evidence": {
            "before_deployment_id": context["failed_deployment"]["id"],
            "after_deployment_id": deployment_id, "active": True,
            "source_sha256": manifest["source_sha256"], "release_id": manifest["release_id"],
            "commit": self._git_text(root, "rev-parse", "HEAD"), **deployment_receipt,
        }}

    def _validate_changed_files(self, changed: list[str]) -> None:
        if not changed or len(changed) > self.policy["max_changed_files"]:
            raise SafetyError("repair changed zero or too many files")
        allowed = [Path(value) for value in self.policy["allowed_source_roots"]]
        protected = [Path(value) for value in self.policy["protected_paths"]]
        for value in changed:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts or not any(path == root or root in path.parents for root in allowed):
                raise SafetyError(f"repair changed a path outside the allowlist: {value}")
            if any(path == root or root in path.parents for root in protected):
                raise SafetyError(f"repair changed a protected path: {value}")

    def _changed_files(self, root: Path) -> list[str]:
        # Do not parse porcelain text after _git_text(): that helper strips
        # the leading status-space and can silently remove the first filename
        # character. NUL-delimited Git path output is unambiguous and keeps
        # tracked and untracked repairs separate from status decoration.
        tracked = self._git_bytes(root, "diff", "--name-only", "-z", "HEAD", "--")
        untracked = self._git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z")
        values = [value for value in (tracked + untracked).split(b"\0") if value]
        return sorted({value.decode("utf-8") for value in values})

    @contextmanager
    def _regression_fixtures(self, root: Path) -> Iterator[None]:
        """Copy declared archived fixtures needed by the full test suite.

        Archives are intentionally absent from detached repair worktrees and
        are protected from candidate changes. Copying only declared files keeps
        verification isolated from the canonical archive; the temporary tree
        is always removed before commit and deployment validation.
        """
        fixture_roots = [root / "archive", root / "training_data"]
        if any(path.exists() or path.is_symlink() for path in fixture_roots):
            raise SafetyError("detached repair worktree unexpectedly contains a protected fixture tree")
        fixtures: set[Path] = set()

        def collect(value: Any) -> None:
            if isinstance(value, dict):
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
            elif isinstance(value, str) and value.startswith(("archive/", "training_data/")):
                relative = Path(value)
                if relative.is_absolute() or ".." in relative.parts:
                    raise SafetyError(f"campaign declares an unsafe protected fixture: {value}")
                fixtures.add(relative)

        specifications = self.repo_root / "config" / "mission_hub" / "campaigns"
        for specification in sorted(specifications.glob("*.json")):
            collect(json.loads(specification.read_text(encoding="utf-8")))
        if len(fixtures) > 64:
            raise SafetyError("campaigns declare too many protected regression fixtures")
        total_bytes = 0
        total_files = 0
        for relative in sorted(fixtures):
            source = self.repo_root / relative
            if not source.is_file() and not source.is_dir():
                raise SafetyError(f"required protected regression fixture is unavailable: {source}")
            target = root / relative
            sources = [source] if source.is_file() else sorted(source.rglob("*"))
            for candidate in sources:
                if candidate.is_symlink():
                    raise SafetyError(f"protected regression fixture contains a symbolic link: {candidate}")
                if candidate.is_file():
                    total_files += 1
                    total_bytes += candidate.stat().st_size
            if total_files > 1024 or total_bytes > 64 * 1024 * 1024:
                raise SafetyError("protected regression fixtures exceed the copy bound")
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            else:
                shutil.copytree(source, target, dirs_exist_ok=True)
        try:
            yield
        finally:
            for fixture_root in fixture_roots:
                if fixture_root.is_symlink():
                    fixture_root.unlink()
                elif fixture_root.exists():
                    shutil.rmtree(fixture_root)

    def _patch_action(self, changed: list[str], path: Path) -> dict[str, Any]:
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        return {"kind": "source_patch", "status": "succeeded", "evidence": {
            "changed_files": changed, "patch_sha256": digest, "patch_uri": str(path), "patch_bytes": len(payload),
        }}

    @staticmethod
    def _test_action(scope: str, command: list[str], exit_code: int, path: Path) -> dict[str, Any]:
        payload = path.read_bytes()
        return {"kind": "tests", "status": "succeeded" if exit_code == 0 else "failed", "evidence": {
            "scope": scope, "command": command, "exit_code": exit_code, "passed": exit_code == 0,
            "transcript_uri": str(path), "transcript_sha256": hashlib.sha256(payload).hexdigest(),
            "transcript_bytes": len(payload),
        }}

    @staticmethod
    def _internal_test_action(scope: str, command: list[str], path: Path) -> dict[str, Any]:
        return BoundedCodexRepairDriver._test_action(scope, command, 0, path)

    def _write_evidence(self, attempt_id: str, name: str, payload: bytes) -> Path:
        directory = self._evidence_directory(attempt_id)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o440)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path

    def _evidence_directory(self, attempt_id: str) -> Path:
        directory = Path(self.bundle.base["hub"]["state_root"]).resolve() / "recovery" / "evidence" / attempt_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _run(self, command: list[str], *, cwd: Path, timeout: int, check: bool = True) -> subprocess.CompletedProcess[str]:
        return self.runner(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=check)

    def _git_text(self, root: Path, *args: str) -> str:
        return self._run(["git", *args], cwd=root, timeout=30).stdout.strip()

    def _git_bytes(self, root: Path, *args: str) -> bytes:
        completed = subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30, check=True)
        return completed.stdout

    @staticmethod
    def _failure(code: str, summary: str, *, actions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {"succeeded": False, "failure_code": code, "summary": summary, "actions": actions or []}
