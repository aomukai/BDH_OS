from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LabConfig:
    repo_root: Path
    lab_root: Path
    frontend_root: Path
    state_dir: Path
    messages_dir: Path
    published_dir: Path
    scan_roots: tuple[str, ...]
    serve_roots: tuple[str, ...]
    git_pull_interval_seconds: int
    git_pull_enabled: bool
    git_pull_allow_dirty: bool
    git_expected_branch: str
    git_expected_remote: str
    orchestrator_url: str | None
    orchestrator_api_key: str | None
    auth_password: str | None
    auth_secret: str
    auth_cookie_secure: bool
    max_request_body_bytes: int
    trusted_origins: tuple[str, ...]
    trainbox_ssh_target: str | None
    trainbox_status_timeout_seconds: int
    trainbox_status_cache_seconds: int
    trainbox_status_stale_seconds: int
    message_codex_executable: str
    message_codex_model: str
    message_codex_timeout_seconds: int
    message_lease_seconds: int
    message_max_attempts: int

    @classmethod
    def from_env(cls) -> "LabConfig":
        backend_dir = Path(__file__).resolve().parent
        lab_root = backend_dir.parent
        repo_root = lab_root.parent
        scan_roots = tuple(
            part.strip()
            for part in os.environ.get(
                "LAB_SCAN_ROOTS",
                "training/logs,training/corpus,runs,checkpoints,chat,"
                "lab/messages/inbox,lab/messages/outbox",
            ).split(",")
            if part.strip()
        )
        serve_roots = tuple(
            part.strip().strip("/")
            for part in os.environ.get("LAB_SERVE_ROOTS", ",".join(scan_roots)).split(",")
            if part.strip()
        )
        trusted_origins = tuple(
            part.strip().rstrip("/")
            for part in os.environ.get("LAB_TRUSTED_ORIGINS", "").split(",")
            if part.strip()
        )
        return cls(
            repo_root=repo_root,
            lab_root=lab_root,
            frontend_root=lab_root / "frontend",
            state_dir=lab_root / "state",
            messages_dir=lab_root / "messages",
            published_dir=lab_root / "published",
            scan_roots=scan_roots,
            serve_roots=serve_roots,
            git_pull_interval_seconds=int(os.environ.get("LAB_GIT_PULL_INTERVAL", "120")),
            git_pull_enabled=os.environ.get("LAB_GIT_PULL", "1") != "0",
            git_pull_allow_dirty=os.environ.get("LAB_GIT_ALLOW_DIRTY", "0") == "1",
            git_expected_branch=os.environ.get("LAB_GIT_EXPECTED_BRANCH", "main"),
            git_expected_remote=os.environ.get("LAB_GIT_EXPECTED_REMOTE", "origin"),
            orchestrator_url=os.environ.get("LAB_ORCHESTRATOR_URL") or None,
            orchestrator_api_key=os.environ.get("LAB_ORCHESTRATOR_API_KEY") or None,
            auth_password=os.environ.get("LAB_AUTH_PASSWORD") or None,
            auth_secret=os.environ.get("LAB_AUTH_SECRET") or "dev-only-change-me",
            auth_cookie_secure=os.environ.get("LAB_AUTH_COOKIE_SECURE", "0") == "1",
            max_request_body_bytes=int(os.environ.get("LAB_MAX_REQUEST_BODY", str(1024 * 1024))),
            trusted_origins=trusted_origins,
            trainbox_ssh_target=os.environ.get(
                "LAB_TRAINBOX_SSH_TARGET", "ninereeds-trainbox-status"
            )
            or None,
            trainbox_status_timeout_seconds=int(
                os.environ.get("LAB_TRAINBOX_STATUS_TIMEOUT", "8")
            ),
            trainbox_status_cache_seconds=int(
                os.environ.get("LAB_TRAINBOX_STATUS_CACHE", "5")
            ),
            trainbox_status_stale_seconds=int(
                os.environ.get("LAB_TRAINBOX_STATUS_STALE", "180")
            ),
            message_codex_executable=os.environ.get(
                "LAB_MESSAGE_CODEX_EXECUTABLE",
                "/home/aomukai/.local/bin/codex",
            ),
            message_codex_model=os.environ.get(
                "LAB_MESSAGE_CODEX_MODEL",
                "gpt-5.6-sol",
            ),
            message_codex_timeout_seconds=int(
                os.environ.get("LAB_MESSAGE_CODEX_TIMEOUT", "900")
            ),
            message_lease_seconds=int(
                os.environ.get("LAB_MESSAGE_LEASE_SECONDS", "1200")
            ),
            message_max_attempts=int(
                os.environ.get("LAB_MESSAGE_MAX_ATTEMPTS", "3")
            ),
        )

    def ensure_dirs(self) -> None:
        for path in (
            self.state_dir,
            self.messages_dir / "inbox",
            self.messages_dir / "outbox",
            self.messages_dir / "claims",
            self.messages_dir / "receipts",
            self.messages_dir / "worker",
            self.published_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def resolve_repo_path(self, relative_path: str) -> Path:
        clean = relative_path.lstrip("/")
        candidate = (self.repo_root / clean).resolve()
        repo = self.repo_root.resolve()
        if candidate == repo or repo not in candidate.parents:
            raise ValueError("Path escapes repository root")
        if ".git" in candidate.relative_to(repo).parts:
            raise ValueError("Git internals are not served")
        relative = candidate.relative_to(repo)
        if not any(
            relative == Path(root) or Path(root) in relative.parents
            for root in self.serve_roots
        ):
            raise ValueError("Path is outside configured Lab serve roots")
        return candidate

    def validate_bind(self, host: str) -> None:
        local_hosts = {"127.0.0.1", "::1", "localhost"}
        if host in local_hosts or host.startswith("127."):
            return
        if not self.auth_password and not (self.state_dir / "auth.json").exists():
            raise RuntimeError(
                "Refusing non-loopback Lab bind without authentication. "
                "Set LAB_AUTH_PASSWORD or configure a stored password on localhost first."
            )
