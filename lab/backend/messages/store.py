from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab.backend.config import LabConfig
from lab.backend.models import Message


MESSAGE_SCHEMA = "lab_message_v1"
RECEIPT_SCHEMA = "lab_message_receipt_v1"
CLAIM_SCHEMA = "lab_message_claim_v1"
TERMINAL_STATUSES = {"completed", "dead_letter"}


def utc_now(timestamp: float | None = None) -> str:
    value = datetime.fromtimestamp(timestamp or time.time(), timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


class MessageStore:
    def __init__(self, config: LabConfig) -> None:
        self.config = config
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        for path in (
            self.config.messages_dir,
            self.config.messages_dir / "inbox",
            self.config.messages_dir / "outbox",
            self.config.messages_dir / "claims",
            self.config.messages_dir / "receipts",
            self.config.messages_dir / "worker",
        ):
            path.mkdir(parents=True, exist_ok=True)
            try:
                path.chmod(0o700)
            except OSError:
                pass

    def list_messages(self, box: str) -> list[Message]:
        box_dir = self._box_dir(box)
        messages: list[Message] = []
        for path in sorted(box_dir.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True):
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() not in {".md", ".txt", ".json"}:
                continue
            if path.suffix.lower() == ".json":
                try:
                    messages.append(self._message_from_envelope(path, box))
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
            else:
                messages.append(self._legacy_message(path, box))
        return messages

    def write_outbox(self, title: str, body: str) -> Message:
        title = title.strip() or "Message"
        body = body.strip()
        if len(title) > 200:
            raise ValueError("message title must not exceed 200 characters")
        if not body:
            raise ValueError("message body must not be empty")
        if len(body.encode("utf-8")) > 64 * 1024:
            raise ValueError("message body must not exceed 64 KiB")

        timestamp = time.time()
        message_id = f"msg-{int(timestamp * 1000):013d}-{uuid.uuid4().hex[:12]}"
        envelope = self._envelope(
            message_id=message_id,
            created_at=utc_now(timestamp),
            sender="human:andi",
            recipient="codex:lab-worker",
            kind="user_message",
            title=title,
            body=body,
        )
        self._write_json_atomic(self._message_path("outbox", message_id), envelope, exclusive=True)
        self._write_receipt(
            message_id,
            {
                "schema_version": RECEIPT_SCHEMA,
                "message_id": message_id,
                "status": "queued",
                "attempt_count": 0,
                "created_at": envelope["created_at"],
                "updated_at": envelope["created_at"],
                "claimed_by": None,
                "lease_expires_at": None,
                "next_attempt_at": timestamp,
                "response_message_id": None,
                "last_error": None,
                "history": [
                    {
                        "status": "queued",
                        "at": envelope["created_at"],
                        "detail": "Message accepted by Lab outbox.",
                    }
                ],
            },
            exclusive=True,
        )
        return self._message_from_envelope(self._message_path("outbox", message_id), "outbox")

    def pending_envelopes(self, *, now: float | None = None) -> list[dict[str, Any]]:
        current = time.time() if now is None else now
        pending: list[dict[str, Any]] = []
        for path in sorted(self._box_dir("outbox").glob("*.json")):
            try:
                envelope = self._read_envelope(path)
                receipt = self.receipt(envelope["message_id"])
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if receipt is None or receipt.get("status") in TERMINAL_STATUSES:
                continue
            if float(receipt.get("next_attempt_at") or 0) > current:
                continue
            pending.append(envelope)
        return pending

    def receipt(self, message_id: str) -> dict[str, Any] | None:
        path = self._receipt_path(message_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != RECEIPT_SCHEMA:
            raise ValueError("invalid message receipt")
        return data

    def claim(self, message_id: str, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
        now = time.time()
        claim_path = self._claim_path(message_id)
        if claim_path.exists():
            try:
                existing = json.loads(claim_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {}
            if float(existing.get("lease_expires_epoch") or 0) > now:
                return None

        receipt = self.receipt(message_id)
        if receipt is None or receipt.get("status") in TERMINAL_STATUSES:
            return None
        attempt = int(receipt.get("attempt_count") or 0) + 1
        claim = {
            "schema_version": CLAIM_SCHEMA,
            "message_id": message_id,
            "worker_id": worker_id,
            "attempt": attempt,
            "claimed_at": utc_now(now),
            "lease_expires_at": utc_now(now + lease_seconds),
            "lease_expires_epoch": now + lease_seconds,
        }
        self._write_json_atomic(claim_path, claim)
        self.transition(
            message_id,
            "claimed",
            detail=f"Claimed by {worker_id}.",
            claimed_by=worker_id,
            lease_expires_at=claim["lease_expires_at"],
            attempt_count=attempt,
        )
        return claim

    def mark_processing(self, message_id: str, worker_id: str) -> dict[str, Any]:
        return self.transition(
            message_id,
            "processing",
            detail=f"Codex invocation started by {worker_id}.",
        )

    def complete(
        self,
        request: dict[str, Any],
        reply: dict[str, Any],
        worker_id: str,
    ) -> Message:
        request_id = request["message_id"]
        response_id = f"reply-{request_id}"
        response_path = self._message_path("inbox", response_id)
        if not response_path.exists():
            envelope = self._envelope(
                message_id=response_id,
                created_at=utc_now(),
                sender="codex:lab-worker",
                recipient=request["sender"],
                kind="codex_reply",
                title=str(reply["subject"]).strip()[:200] or f"Re: {request['title']}",
                body=str(reply["body"]).strip(),
                correlation_id=request_id,
                reply_to=request_id,
                metadata={
                    "disposition": reply["disposition"],
                    "requires_interactive": bool(reply["requires_interactive"]),
                    "worker_id": worker_id,
                },
            )
            self._write_json_atomic(response_path, envelope, exclusive=True)
        self.transition(
            request_id,
            "completed",
            detail=f"Correlated response {response_id} persisted.",
            response_message_id=response_id,
            claimed_by=worker_id,
            lease_expires_at=None,
            next_attempt_at=None,
            last_error=None,
        )
        self.release_claim(request_id)
        return self._message_from_envelope(response_path, "inbox")

    def fail(self, message_id: str, error: str, *, max_attempts: int) -> dict[str, Any]:
        receipt = self.receipt(message_id)
        if receipt is None:
            raise ValueError("message receipt is missing")
        attempts = int(receipt.get("attempt_count") or 0)
        terminal = attempts >= max_attempts
        retry_delay = min(300, 15 * (2 ** max(attempts - 1, 0)))
        result = self.transition(
            message_id,
            "dead_letter" if terminal else "retry_wait",
            detail="Worker attempt failed.",
            last_error=error[:2000],
            claimed_by=None,
            lease_expires_at=None,
            next_attempt_at=None if terminal else time.time() + retry_delay,
        )
        self.release_claim(message_id)
        return result

    def transition(self, message_id: str, status: str, *, detail: str, **updates: Any) -> dict[str, Any]:
        receipt = self.receipt(message_id)
        if receipt is None:
            raise ValueError("message receipt is missing")
        if receipt.get("status") == "completed" and status != "completed":
            return receipt
        now = utc_now()
        receipt.update(updates)
        receipt["status"] = status
        receipt["updated_at"] = now
        history = list(receipt.get("history") or [])
        history.append({"status": status, "at": now, "detail": detail})
        receipt["history"] = history[-100:]
        self._write_receipt(message_id, receipt)
        return receipt

    def release_claim(self, message_id: str) -> None:
        try:
            self._claim_path(message_id).unlink()
        except FileNotFoundError:
            pass

    def _message_from_envelope(self, path: Path, box: str) -> Message:
        envelope = self._read_envelope(path)
        metadata = envelope.get("metadata") if isinstance(envelope.get("metadata"), dict) else {}
        receipt = self.receipt(envelope["message_id"]) if box == "outbox" else None
        relative = path.relative_to(self.config.repo_root).as_posix()
        return Message(
            id=envelope["message_id"],
            box=box,
            path=relative,
            title=envelope["title"],
            body=envelope["body"],
            timestamp=self._timestamp(envelope["created_at"]),
            schema_version=MESSAGE_SCHEMA,
            sender=envelope["sender"],
            recipient=envelope["recipient"],
            correlation_id=envelope.get("correlation_id"),
            reply_to=envelope.get("reply_to"),
            status=receipt.get("status") if receipt else "delivered",
            disposition=metadata.get("disposition"),
            requires_interactive=bool(metadata.get("requires_interactive")),
        )

    def _legacy_message(self, path: Path, box: str) -> Message:
        body = path.read_text(encoding="utf-8", errors="replace")
        title = path.stem
        for line in body.splitlines():
            clean = line.strip()
            if clean.startswith("#"):
                title = clean.strip("# ").strip() or title
                break
            if clean:
                title = clean[:80]
                break
        relative = path.relative_to(self.config.repo_root).as_posix()
        return Message(
            id=hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16],
            box=box,
            path=relative,
            title=title,
            body=body,
            timestamp=path.stat().st_mtime,
            status="legacy",
        )

    def _read_envelope(self, path: Path) -> dict[str, Any]:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(envelope, dict) or envelope.get("schema_version") != MESSAGE_SCHEMA:
            raise ValueError("invalid message envelope")
        required = {"message_id", "created_at", "sender", "recipient", "kind", "title", "body", "content_sha256"}
        if not required <= set(envelope):
            raise ValueError("message envelope is incomplete")
        expected = self._content_hash(
            envelope["sender"],
            envelope["recipient"],
            envelope["kind"],
            envelope["title"],
            envelope["body"],
        )
        if not secrets.compare_digest(str(envelope["content_sha256"]), expected):
            raise ValueError("message envelope content hash mismatch")
        return envelope

    def _envelope(
        self,
        *,
        message_id: str,
        created_at: str,
        sender: str,
        recipient: str,
        kind: str,
        title: str,
        body: str,
        correlation_id: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": MESSAGE_SCHEMA,
            "message_id": message_id,
            "created_at": created_at,
            "sender": sender,
            "recipient": recipient,
            "kind": kind,
            "title": title,
            "body": body,
            "correlation_id": correlation_id,
            "reply_to": reply_to,
            "content_sha256": self._content_hash(sender, recipient, kind, title, body),
            "metadata": metadata or {},
        }

    @staticmethod
    def _content_hash(sender: str, recipient: str, kind: str, title: str, body: str) -> str:
        canonical = json.dumps(
            {
                "sender": sender,
                "recipient": recipient,
                "kind": kind,
                "title": title,
                "body": body,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _box_dir(self, box: str) -> Path:
        if box not in {"inbox", "outbox"}:
            raise ValueError("box must be inbox or outbox")
        return self.config.messages_dir / box

    def _message_path(self, box: str, message_id: str) -> Path:
        return self._box_dir(box) / f"{message_id}.json"

    def _receipt_path(self, message_id: str) -> Path:
        return self.config.messages_dir / "receipts" / f"{message_id}.json"

    def _claim_path(self, message_id: str) -> Path:
        return self.config.messages_dir / "claims" / f"{message_id}.json"

    def _write_receipt(self, message_id: str, data: dict[str, Any], *, exclusive: bool = False) -> None:
        self._write_json_atomic(self._receipt_path(message_id), data, exclusive=exclusive)

    @staticmethod
    def _write_json_atomic(path: Path, data: dict[str, Any], *, exclusive: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if exclusive and path.exists():
            raise FileExistsError(path)
        tmp = path.parent / f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
        payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        try:
            with tmp.open("x", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if exclusive and path.exists():
                raise FileExistsError(path)
            tmp.replace(path)
            try:
                os.chmod(path, 0o600)
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
        finally:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _timestamp(value: str) -> float:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
