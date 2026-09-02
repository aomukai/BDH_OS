"""Bounded Sol-authored experimental source changes for the research lab."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterator

from ..config import load_config_bundle, machine_id_for_role
from ..deployment import DeploymentBuilder
from ..errors import RemoteJobError, SafetyError
from ..store import MissionHubStore
from ..transport import SSHDispatcher
from .contracts import _declaration


_SCOPE_ROOTS: dict[str, tuple[str, ...]] = {
    "organism": ("campaign36c", "bdh.py"),
    "training_runtime": (
        "meta/scripts/train_campaign36c_bootstrap.py",
        "meta/scripts/cortex_runtime.py",
        "training/optim",
        "training/diagnostics",
    ),
    "telemetry": (
        "campaign36c",
        "meta/scripts/train_campaign36c_bootstrap.py",
        "mission_hub/handlers/campaign36c.py",
    ),
    "evaluation": (
        "campaign36c",
        "meta/scripts/evaluate_cortex.py",
        "meta/scripts/evaluate_multimodal_cortex.py",
        "meta/scripts/probe_cortex_checkpoint.py",
    ),
    "data_adapter": (
        "meta/scripts/train_campaign36c_bootstrap.py",
        "mission_hub/handlers/campaign36c.py",
    ),
}
_TEST_ROOT = Path("tests")
_MAX_CHANGED_FILES = 24
_MAX_PATCH_BYTES = 256 * 1024
_MAX_FIXTURE_FILES = 4096
_MAX_FIXTURE_BYTES = 256 * 1024 * 1024
_TARGETED_TESTS = (
    "tests/test_campaign36c_development.py",
    "tests/test_campaign36c_mission_hub.py",
    "tests/test_campaign36c_multimodal_organs.py",
    "tests/test_research_lab.py",
)


class ResearchCodeChangeHandler:
    """Let Sol edit only experimental code in an isolated, validated worktree.

    The handler deliberately cannot modify its own conductor, schemas, active
    configuration, training data, checkpoints, credentials, or archives.  A
    clean committed candidate is installed and activated on Trainbox only
    after targeted and full regression tests pass.
    """

    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if context["machine_id"] != "mission-hub":
            raise SafetyError("research code changes may execute only on Mission Hub")
        release_root = Path(context["release_root"]).resolve()
        bundle = load_config_bundle(release_root / "config" / "mission_hub")
        database = Path(bundle.base["hub"]["state_root"]) / bundle.base["hub"]["database_name"]
        store = MissionHubStore(database, busy_timeout_ms=bundle.base["hub"]["busy_timeout_ms"])
        active_config = store.active_config()
        if active_config["sha256"] != bundle.sha256:
            raise SafetyError("research code change release does not match active configuration")

        trainbox_id = machine_id_for_role(bundle, "trainbox")
        active = store.active_deployment(trainbox_id)
        active_manifest = json.loads(active["manifest_json"])
        source = active_manifest.get("source") or {}
        if active["id"] != payload["expected_trainbox_deployment_id"]:
            raise SafetyError("Trainbox deployment changed after Sol authorized the code change")
        if source.get("git_head") != payload["expected_source_git_head"]:
            raise SafetyError("Trainbox source commit changed after Sol authorized the code change")

        run_root = Path(context["state_root"]).resolve() / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        repo_root = Path(bundle.recovery["source_repository_root"]).resolve()
        workspace = (
            Path(context["state_root"]).resolve()
            / "research-code" / "workspaces" / payload["change_id"]
        )
        workspace.parent.mkdir(parents=True, exist_ok=True)
        if workspace.exists():
            raise SafetyError(f"research code workspace already exists: {workspace}")
        branch = f"research/campaign-{payload['campaign_number']}-{payload['change_id']}"
        allowed = self.allowed_roots(payload["scopes"])

        self._run(["git", "cat-file", "-e", f"{payload['expected_source_git_head']}^{{commit}}"], cwd=repo_root, timeout=30)
        self._run(
            ["git", "worktree", "add", "--detach", str(workspace), payload["expected_source_git_head"]],
            cwd=repo_root, timeout=60,
        )
        self._run(["git", "switch", "-c", branch], cwd=workspace, timeout=30)

        request = {
            "schema_version": "ninereeds_research_code_change_request_v1",
            "campaign_id": payload["campaign_id"],
            "campaign_number": payload["campaign_number"],
            "lab_id": payload["lab_id"],
            "change_id": payload["change_id"],
            "title": payload["title"],
            "hypothesis": payload["hypothesis"],
            "objective": payload["objective"],
            "acceptance_criteria": payload["acceptance_criteria"],
            "scopes": payload["scopes"],
            "allowed_source_roots": [path.as_posix() for path in allowed],
            "protected": [
                "mission_hub/research_lab.py", "mission_hub/store.py",
                "config/mission_hub", "schemas/mission_hub", ".git",
                "training_data", "checkpoints", "archive", "credentials",
            ],
            "base_deployment_id": active["id"],
            "base_git_head": payload["expected_source_git_head"],
        }
        request_path = self._write(run_root / "request.json", self._json_bytes(request))
        transcript_path = self._invoke_sol(
            workspace, request_path, run_root, context,
        )

        sol_changed = self._changed_files(workspace)
        self.validate_changed_files(sol_changed, allowed)
        provenance_changed = self._refresh_registered_source_hashes(workspace, sol_changed)
        changed = sorted(set(sol_changed) | set(provenance_changed))
        if len(changed) > _MAX_CHANGED_FILES:
            raise SafetyError("research code change plus provenance touched too many files")
        self._run(["git", "add", "--", *changed], cwd=workspace, timeout=30)
        patch = self._git_bytes(workspace, "diff", "--cached", "--binary", "--", *changed)
        if not patch:
            raise SafetyError("Sol completed the code task without a source change")
        if len(patch) > _MAX_PATCH_BYTES:
            raise SafetyError("research code patch exceeds the configured byte bound")
        patch_path = self._write(run_root / "candidate.patch", patch)

        test_logs = self._run_tests(workspace, run_root, active_manifest)
        if self._changed_files(workspace) != changed:
            raise SafetyError("validation changed the candidate source tree")
        self._run(
            [
                "git", "-c", "user.name=Sol Research Lab",
                "-c", "user.email=sol-research@localhost", "commit", "-m",
                f"research: campaign {payload['campaign_number']} {payload['title']}",
            ],
            cwd=workspace, timeout=60,
        )
        candidate_commit = self._git_text(workspace, "rev-parse", "HEAD")
        candidate_bundle = load_config_bundle(workspace / "config" / "mission_hub")
        if candidate_bundle.sha256 != active_config["sha256"]:
            raise SafetyError("experimental source changes may not alter active Mission Hub configuration")

        deployment, archive, receipts = self._deploy_trainbox(
            store, candidate_bundle, workspace, active, active_manifest,
            run_root=run_root, actor=f"sol:research-code:{payload['change_id']}",
        )
        report = {
            "schema_version": "ninereeds_research_code_change_report_v1",
            "campaign_id": payload["campaign_id"],
            "change_id": payload["change_id"],
            "title": payload["title"],
            "hypothesis": payload["hypothesis"],
            "objective": payload["objective"],
            "acceptance_criteria": payload["acceptance_criteria"],
            "scopes": payload["scopes"],
            "changed_files": changed,
            "sol_changed_files": sol_changed,
            "provenance_changed_files": provenance_changed,
            "base_git_head": payload["expected_source_git_head"],
            "candidate_git_head": candidate_commit,
            "branch": branch,
            "workspace": str(workspace),
            "tests": test_logs,
            "deployment": {
                "id": deployment["id"], "release_id": deployment["release_id"],
                "source_sha256": deployment["source_sha256"],
                "install_receipt": receipts["install"],
                "activation_receipt": receipts["activation"],
            },
        }
        report_path = self._write(run_root / "report.json", self._json_bytes(report))
        manifest = {
            "campaign_id": payload["campaign_id"], "lab_id": payload["lab_id"],
            "change_id": payload["change_id"], "candidate_git_head": candidate_commit,
            "deployment_id": deployment["id"], "release_id": deployment["release_id"],
        }
        artifacts = [
            self._artifact("research_code_patch", patch_path, manifest),
            self._artifact("research_code_report", report_path, manifest),
            self._artifact("research_code_transcript", transcript_path, manifest),
            self._artifact("research_code_release", Path(archive["path"]), manifest),
        ]
        artifacts.extend(
            self._artifact("research_code_test_log", Path(item["uri"]), {
                **manifest, "scope": item["scope"], "command": item["command"],
            })
            for item in test_logs
        )
        return {
            "status": "succeeded",
            "artifacts": artifacts,
            "metrics": report,
            "failure": None,
        }

    @staticmethod
    def allowed_roots(scopes: list[str]) -> tuple[Path, ...]:
        unknown = sorted(set(scopes) - set(_SCOPE_ROOTS))
        if unknown:
            raise SafetyError("unknown research code scope: " + ", ".join(unknown))
        roots = {_TEST_ROOT}
        for scope in scopes:
            roots.update(Path(value) for value in _SCOPE_ROOTS[scope])
        return tuple(sorted(roots, key=lambda item: item.as_posix()))

    @staticmethod
    def validate_changed_files(changed: list[str], allowed: tuple[Path, ...]) -> None:
        if not changed or len(changed) > _MAX_CHANGED_FILES:
            raise SafetyError("research code change touched zero or too many files")
        changed_paths = [Path(value) for value in changed]
        for path in changed_paths:
            if path.is_absolute() or ".." in path.parts:
                raise SafetyError(f"research code change produced an unsafe path: {path}")
            if not any(path == root or root in path.parents for root in allowed):
                raise SafetyError(f"research code change escaped its authorized scope: {path}")
        if not any(path != _TEST_ROOT and _TEST_ROOT not in path.parents for path in changed_paths):
            raise SafetyError("research code change modified tests without experimental source")

    def _invoke_sol(
        self, workspace: Path, request_path: Path, run_root: Path,
        context: dict[str, Any],
    ) -> Path:
        selected = None
        provider = None
        for model in context["route_models"]:
            candidate = context["providers"][model["provider"]]
            if model["enabled"] and candidate["enabled"] and candidate["kind"] == "codex_cli":
                selected, provider = model, candidate
                break
        if selected is None or provider is None:
            raise SafetyError("research code change requires the enabled Sol Codex route")
        final_path = run_root / "sol-final.txt"
        prompt = (
            "You are Sol, implementing one bounded Ninereeds experimental source change. "
            "Read the exact request below and inspect the detached worktree. Make the smallest robust change "
            "that tests the hypothesis and satisfy the acceptance criteria. Add or update focused tests. "
            "Do not touch anything outside allowed_source_roots. Do not modify the conductor, safety policy, "
            "configuration, schemas, Git metadata, training data, checkpoints, archives, credentials, or the "
            "canonical checkout. Do not commit, deploy, download datasets, or claim validation; deterministic "
            "machinery performs those steps.\n\n"
            + request_path.read_text(encoding="utf-8")
        )
        command = [
            provider["endpoint"], "exec", "--ephemeral", "--ignore-user-config",
            "--ignore-rules", "--approve-for-me", "--skip-git-repo-check",
            "-C", str(workspace), "--model", selected["exact_name"],
            "--output-last-message", str(final_path), "--color", "never", "-",
        ]
        completed = subprocess.run(
            command, input=prompt, text=True, capture_output=True,
            timeout=min(provider["timeout_seconds"], context["timeout_seconds"]), check=False,
        )
        transcript = self._json_bytes({
            "schema_version": "ninereeds_research_code_transcript_v1",
            "model_id": selected["id"], "model_exact_name": selected["exact_name"],
            "returncode": completed.returncode, "stdout": completed.stdout,
            "stderr": completed.stderr,
            "final_message": final_path.read_text(encoding="utf-8") if final_path.is_file() else None,
        })
        transcript_path = self._write(run_root / "codex-transcript.json", transcript)
        if completed.returncode != 0:
            raise RemoteJobError(
                f"Sol code process failed with exit {completed.returncode}",
                failure_class="operational_transient", code="process_interrupted",
            )
        return transcript_path

    def _refresh_registered_source_hashes(
        self, workspace: Path, sol_changed: list[str],
    ) -> list[str]:
        """Deterministically maintain pinned wiki hashes for changed sources.

        Sol cannot edit the research source registry.  When an authorized
        source file is already registered, the validator first proves the
        pinned hash describes the immutable base commit and then replaces only
        that entry with the candidate's content hash.  A stale base registry or
        a missing candidate is refused rather than silently normalized.
        """
        registry_relative = Path("mission_hub/research/sources.json")
        registry_path = workspace / registry_relative
        if not registry_path.is_file() or registry_path.is_symlink():
            raise SafetyError("research source registry is unavailable")
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        sources = registry.get("sources")
        if not isinstance(sources, list):
            raise SafetyError("research source registry has no source array")
        changed = set(sol_changed)
        updated = False
        for source in sources:
            if not isinstance(source, dict) or source.get("path") not in changed:
                continue
            relative = Path(source["path"])
            candidate = workspace / relative
            if not candidate.is_file() or candidate.is_symlink():
                raise SafetyError(f"registered research source candidate is unavailable: {relative}")
            try:
                base = self._git_bytes(workspace, "show", f"HEAD:{relative.as_posix()}")
            except subprocess.CalledProcessError as exc:
                raise SafetyError(f"registered research source is absent from the base commit: {relative}") from exc
            expected = hashlib.sha256(base).hexdigest()
            if source.get("sha256") != expected:
                raise SafetyError(f"research source registry was stale before the candidate change: {relative}")
            candidate_sha = self._sha256(candidate)
            if candidate_sha != expected:
                source["sha256"] = candidate_sha
                updated = True
        if not updated:
            return []
        registry_path.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        return [registry_relative.as_posix()]

    def _run_tests(
        self, workspace: Path, run_root: Path, active_manifest: dict[str, Any],
    ) -> list[dict[str, Any]]:
        executable = active_manifest.get("environment", {}).get("python_executable")
        if not isinstance(executable, str) or not Path(executable).is_file():
            raise SafetyError("active Trainbox deployment has no available test interpreter")
        commands = [
            ("targeted", [executable, "-m", "pytest", "-q", *_TARGETED_TESTS]),
            ("regression", [executable, "-m", "pytest", "-q"]),
        ]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(filter(None, (
            str(workspace), environment.get("PYTHONPATH", ""),
        )))
        results = []
        for index, (scope, command) in enumerate(commands, 1):
            fixture_context = (
                self._regression_fixtures(workspace)
                if scope == "regression" else nullcontext()
            )
            with fixture_context:
                completed = subprocess.run(
                    command, cwd=workspace, capture_output=True, text=True, env=environment,
                    timeout=1800, check=False,
                )
            log = self._write(
                run_root / f"tests-{index}-{scope}.log",
                (
                    f"command={json.dumps(command)}\nexit_code={completed.returncode}\n"
                    f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}\n"
                ).encode("utf-8", errors="replace"),
            )
            result = {
                "scope": scope, "command": command, "exit_code": completed.returncode,
                "passed": completed.returncode == 0, "uri": str(log),
                "sha256": self._sha256(log), "byte_size": log.stat().st_size,
            }
            results.append(result)
            if completed.returncode != 0:
                raise RemoteJobError(
                    f"Sol code change failed {scope} tests with exit {completed.returncode}",
                    failure_class="deterministic_specification", code="job_spec_invalid",
                )
        return results

    @contextmanager
    def _regression_fixtures(self, workspace: Path) -> Iterator[None]:
        """Copy protected local fixtures only after Sol has left the worktree.

        Detached Git worktrees intentionally omit ignored archive, campaign
        material, and generated training fixtures.  The full suite nevertheless
        validates contracts against those canonical surfaces.  Copying the
        bounded declared/censused subset gives the trusted validator an
        isolated snapshot without exposing Mission Hub's originals to Sol or
        allowing a test to mutate them.  Every copied file is removed before
        source validation, commit, and deployment.
        """
        repo_root = Path(
            load_config_bundle(workspace / "config" / "mission_hub")
            .recovery["source_repository_root"]
        ).resolve()
        protected_prefixes = (
            "archive/", "training_data/", "config/mission_hub/campaign_material/",
        )
        fixtures: set[Path] = set()

        def add_path(value: str) -> None:
            relative = Path(value)
            if relative.is_absolute() or ".." in relative.parts:
                raise SafetyError(f"declared regression fixture has an unsafe path: {value}")
            fixtures.add(relative)

        def collect(value: Any) -> None:
            if isinstance(value, dict):
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
            elif isinstance(value, str) and value.startswith(protected_prefixes):
                add_path(value)

        specifications = repo_root / "config" / "mission_hub" / "campaigns"
        for specification in sorted(specifications.glob("*.json")):
            collect(json.loads(specification.read_text(encoding="utf-8")))

        sources = repo_root / "mission_hub" / "research" / "sources.json"
        if sources.is_file():
            registry = json.loads(sources.read_text(encoding="utf-8"))
            for source in registry.get("sources", []):
                if (
                    isinstance(source, dict)
                    and source.get("availability", "repository") == "repository"
                    and isinstance(source.get("path"), str)
                ):
                    add_path(source["path"])
        census = repo_root / "mission_hub" / "research" / "intake" / "source-census.json"
        if census.is_file():
            inventory = json.loads(census.read_text(encoding="utf-8"))
            for candidate in inventory.get("candidates", []):
                if isinstance(candidate, dict) and isinstance(candidate.get("path"), str):
                    add_path(candidate["path"])

        # Campaign 35 derives paths beneath this ignored directory at runtime,
        # so its individual files are not all named in the campaign contract.
        material_root = repo_root / "config" / "mission_hub" / "campaign_material"
        if material_root.is_dir():
            fixtures.add(Path("config/mission_hub/campaign_material"))

        source_files: dict[Path, Path] = {}
        total_bytes = 0
        for relative in sorted(fixtures):
            source = (repo_root / relative).resolve()
            if source != repo_root and repo_root not in source.parents:
                raise SafetyError(f"regression fixture escapes the source repository: {relative}")
            if not source.is_file() and not source.is_dir():
                raise SafetyError(f"required protected regression fixture is unavailable: {source}")
            candidates = [source] if source.is_file() else sorted(source.rglob("*"))
            for candidate in candidates:
                if candidate.is_symlink():
                    raise SafetyError(f"protected regression fixture contains a symbolic link: {candidate}")
                if not candidate.is_file():
                    continue
                candidate_relative = candidate.relative_to(repo_root)
                if candidate_relative in source_files:
                    continue
                source_files[candidate_relative] = candidate
                total_bytes += candidate.stat().st_size
                if len(source_files) > _MAX_FIXTURE_FILES or total_bytes > _MAX_FIXTURE_BYTES:
                    raise SafetyError("protected regression fixtures exceed the copy bound")

        tracked_files = {
            Path(value.decode("utf-8"))
            for value in self._git_bytes(workspace, "ls-files", "-z").split(b"\0")
            if value
        }
        created_files: list[Path] = []
        created_directories: set[Path] = set()
        try:
            for relative, source in sorted(source_files.items()):
                target = workspace / relative
                # Repository source records may point at files Sol is expressly
                # allowed to change.  They are already present in the detached
                # worktree and must remain the candidate version; fixture
                # provisioning is only for ignored files absent from Git.
                if relative in tracked_files:
                    if not target.is_file() or target.is_symlink():
                        raise SafetyError(f"tracked worktree source is unavailable: {relative}")
                    continue
                if target.exists() or target.is_symlink():
                    if target.is_symlink() or not target.is_file():
                        raise SafetyError(f"regression fixture collides with worktree path: {relative}")
                    if target.read_bytes() != source.read_bytes():
                        raise SafetyError(f"worktree fixture differs from canonical source: {relative}")
                    continue
                missing_parents = []
                parent = target.parent
                while parent != workspace and not parent.exists():
                    missing_parents.append(parent)
                    parent = parent.parent
                target.parent.mkdir(parents=True, exist_ok=True)
                created_directories.update(missing_parents)
                shutil.copyfile(source, target)
                created_files.append(target)
            yield
        finally:
            for target in reversed(created_files):
                target.unlink(missing_ok=True)
            for directory in sorted(created_directories, key=lambda value: len(value.parts), reverse=True):
                try:
                    directory.rmdir()
                except OSError:
                    pass

    def _deploy_trainbox(
        self, store: MissionHubStore, bundle, workspace: Path,
        old_deployment: dict[str, Any], old_manifest: dict[str, Any],
        *, run_root: Path, actor: str,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        trainbox_id = machine_id_for_role(bundle, "trainbox")
        role_ids = [
            role_id for role_id, role in bundle.deployment_roles.items()
            if role["role"] == "trainbox"
        ]
        if len(role_ids) != 1:
            raise SafetyError("Trainbox does not map to exactly one deployment role")
        environment = old_manifest.get("environment")
        if not isinstance(environment, dict) or not environment:
            raise SafetyError("active Trainbox deployment lacks reusable environment attestation")
        builder = DeploymentBuilder(workspace, bundle)
        manifest = builder.deployment_manifest(
            role_ids[0], machine_id=trainbox_id,
            config_snapshot_id=store.active_config()["id"], environment=environment,
            allow_dirty_candidate=False,
        )
        deployment_id = store.register_deployment(manifest, actor=actor, activate=False)
        manifest["id"] = deployment_id
        archive = builder.build_archive(manifest, run_root / f"{manifest['release_id']}.tar.gz")
        dispatcher = SSHDispatcher(bundle)
        remote_activated = False
        try:
            install = dispatcher.install_release(trainbox_id, manifest, archive)
            activation = dispatcher.activate_release(trainbox_id, manifest)
            remote_activated = True
            store.activate_registered_deployment(deployment_id, actor=actor)
        except Exception:
            if remote_activated:
                rollback = dict(old_manifest)
                rollback["id"] = old_deployment["id"]
                try:
                    dispatcher.activate_release(trainbox_id, rollback)
                except Exception:
                    pass
            try:
                store.reject_deployment(
                    deployment_id, reason="research code deployment did not activate atomically", actor=actor,
                )
            except Exception:
                pass
            raise
        return manifest, archive, {"install": install, "activation": activation}

    @staticmethod
    def _changed_files(root: Path) -> list[str]:
        tracked = ResearchCodeChangeHandler._git_bytes(root, "diff", "--name-only", "-z", "HEAD", "--")
        untracked = ResearchCodeChangeHandler._git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z")
        return sorted({
            value.decode("utf-8")
            for value in (tracked + untracked).split(b"\0") if value
        })

    @staticmethod
    def _run(command: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=True,
        )

    @staticmethod
    def _git_bytes(root: Path, *args: str) -> bytes:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, timeout=30, check=True,
        ).stdout

    @classmethod
    def _git_text(cls, root: Path, *args: str) -> str:
        return cls._git_bytes(root, *args).decode("utf-8").strip()

    @staticmethod
    def _write(path: Path, payload: bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
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

    @staticmethod
    def _json_bytes(value: dict[str, Any]) -> bytes:
        return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _artifact(cls, kind: str, path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
        return _declaration(kind, path, cls._sha256(path), path.stat().st_size, {
            "schema_version": f"ninereeds_{kind}_v1", **manifest,
        })
