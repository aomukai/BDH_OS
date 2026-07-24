from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Any

from lab.backend.config import LabConfig


class AuthService:
    def __init__(self, config: LabConfig) -> None:
        self.config = config
        self.state_path = config.state_dir / "auth.json"

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
        return self.status()

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
