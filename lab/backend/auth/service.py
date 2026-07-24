from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from lab.backend.config import LabConfig


class AuthService:
    SESSION_SECONDS = 60 * 60 * 12
    REMEMBERED_SESSION_SECONDS = 60 * 60 * 24 * 30

    def __init__(self, config: LabConfig) -> None:
        self.config = config
        self.state_path = config.state_dir / "auth.json"
        self.sessions_path = config.state_dir / "sessions.json"
        self._ephemeral_sessions: dict[str, float] = {}
        self._session_lock = threading.Lock()

    def enabled(self) -> bool:
        return bool(self.config.auth_password) or self.state_path.exists()

    def status(self) -> dict[str, Any]:
        state = self._read_state()
        return {
            "enabled": self.enabled(),
            "mode": "environment" if self.config.auth_password else ("stored" if state else "none"),
            "created_at": state.get("created_at") if state else None,
            "updated_at": state.get("updated_at") if state else None,
        }

    def verify(self, password: str) -> bool:
        if self.config.auth_password:
            return hmac.compare_digest(
                self._env_digest(password),
                self._env_digest(self.config.auth_password),
            )
        state = self._read_state()
        if not state:
            return False
        salt = bytes.fromhex(str(state["salt"]))
        expected = str(state["password_hash"])
        candidate = self._stored_digest(password, salt)
        return hmac.compare_digest(candidate, expected)

    def set_password(self, password: str) -> dict[str, Any]:
        if self.config.auth_password:
            raise ValueError("Password is managed by LAB_AUTH_PASSWORD.")
        if len(password) < 12:
            raise ValueError("Password must be at least 12 characters.")
        now = time.time()
        previous = self._read_state()
        salt = secrets.token_bytes(16)
        state = {
            "version": 1,
            "salt": salt.hex(),
            "password_hash": self._stored_digest(password, salt),
            "created_at": previous.get("created_at", now) if previous else now,
            "updated_at": now,
        }
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.state_path)
        self.sessions_path.unlink(missing_ok=True)
        with self._session_lock:
            self._ephemeral_sessions.clear()
        return self.status()

    def create_session(self, *, remember: bool) -> tuple[str, int]:
        token = secrets.token_urlsafe(32)
        lifetime = self.REMEMBERED_SESSION_SECONDS if remember else self.SESSION_SECONDS
        expiry = time.time() + lifetime
        token_hash = self._token_hash(token)
        with self._session_lock:
            if remember:
                sessions = self._read_sessions()
                sessions[token_hash] = expiry
                self._write_sessions(sessions)
            else:
                self._ephemeral_sessions[token_hash] = expiry
        return token, lifetime

    def verify_session(self, token: str) -> bool:
        token_hash = self._token_hash(token)
        now = time.time()
        with self._session_lock:
            expiry = self._ephemeral_sessions.get(token_hash)
            if expiry is not None:
                if expiry >= now:
                    return True
                self._ephemeral_sessions.pop(token_hash, None)
            sessions = self._read_sessions()
            expiry = sessions.get(token_hash)
            if expiry is None:
                return False
            if expiry < now:
                sessions.pop(token_hash, None)
                self._write_sessions(sessions)
                return False
            return True

    def revoke_session(self, token: str) -> None:
        token_hash = self._token_hash(token)
        with self._session_lock:
            self._ephemeral_sessions.pop(token_hash, None)
            sessions = self._read_sessions()
            if token_hash in sessions:
                sessions.pop(token_hash)
                self._write_sessions(sessions)

    def _read_state(self) -> dict[str, Any] | None:
        if not self.state_path.exists():
            return None
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or "salt" not in data or "password_hash" not in data:
            return None
        return data

    def _env_digest(self, password: str) -> str:
        return hmac.new(
            self.config.auth_secret.encode("utf-8"),
            password.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _stored_digest(self, password: str, salt: bytes) -> str:
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=32,
        ).hex()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _auth_fingerprint(self) -> str:
        if self.config.auth_password:
            material = self._env_digest(self.config.auth_password)
        else:
            state = self._read_state()
            material = str(state.get("password_hash") if state else "")
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _read_sessions(self) -> dict[str, float]:
        if not self.sessions_path.exists():
            return {}
        try:
            value = json.loads(self.sessions_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if (
            not isinstance(value, dict)
            or value.get("version") != 1
            or value.get("auth_fingerprint") != self._auth_fingerprint()
            or not isinstance(value.get("sessions"), dict)
        ):
            return {}
        sessions: dict[str, float] = {}
        for token_hash, expiry in value["sessions"].items():
            if (
                isinstance(token_hash, str)
                and len(token_hash) == 64
                and isinstance(expiry, (int, float))
            ):
                sessions[token_hash] = float(expiry)
        return sessions

    def _write_sessions(self, sessions: dict[str, float]) -> None:
        self.sessions_path.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        value = {
            "version": 1,
            "auth_fingerprint": self._auth_fingerprint(),
            "sessions": {
                token_hash: expiry
                for token_hash, expiry in sessions.items()
                if expiry >= now
            },
        }
        tmp = self.sessions_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(self.sessions_path)
