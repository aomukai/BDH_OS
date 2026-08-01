from __future__ import annotations

import fcntl
import hashlib
import json
import os
import secrets
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


PLAN_SCHEMA = "ninereeds_control_plan_v1"
CLAIM_SCHEMA = "ninereeds_control_claim_v1"
RECEIPT_SCHEMA = "ninereeds_control_receipt_v1"
REPORT_SCHEMA = "ninereeds_control_report_v1"

PLAN_KINDS = {
    "strategic_decision",
    "phase_block",
    "cortex_block",
    "cortex_corpus_chunk",
    "cortex_evaluation",
    "executor_job",
    "trainer_session",
    "micro_update",
    "status_refresh",
}
PLAN_MODES = {"shadow", "live"}
TERMINAL_RECEIPT_STATUSES = {"completed", "blocked", "dead_letter"}
REPORT_STATUSES = {"succeeded", "failed", "blocked"}
MAX_ENVELOPE_BYTES = 256 * 1024


class LedgerError(RuntimeError):
    pass


def utc_now(timestamp: float | None = None) -> str:
    value = time.time() if timestamp is None else timestamp
    return (
        datetime.fromtimestamp(value, timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def content_hash(value: dict[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_json(unsigned)).hexdigest()


class ControlLedger:
    """Filesystem ledger with atomic transitions and replay-safe terminal states."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.plans_dir = self.root / "plans"
        self.claims_dir = self.root / "claims"
        self.receipts_dir = self.root / "receipts"
        self.reports_dir = self.root / "reports"
        self.worker_dir = self.root / "worker"
        self.wake_path = self.plans_dir / ".wake"
        self.lock_path = self.worker_dir / "ledger.lock"
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        for path in (
            self.root,
            self.plans_dir,
            self.claims_dir,
            self.receipts_dir,
            self.reports_dir,
            self.worker_dir,
        ):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
            try:
                path.chmod(0o700)
            except OSError:
                pass

    def create_plan(
        self,
        *,
        kind: str,
        mode: str,
        payload: dict[str, Any],
        created_by: str,
        authorization: dict[str, bool] | None = None,
        parent_plan_id: str | None = None,
        plan_id: str | None = None,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        timestamp = time.time()
        identifier = plan_id or (
            f"plan-{int(timestamp * 1000):013d}-{uuid.uuid4().hex[:12]}"
        )
        plan = {
            "schema_version": PLAN_SCHEMA,
            "plan_id": identifier,
            "created_at": utc_now(timestamp),
            "created_by": created_by,
            "kind": kind,
            "mode": mode,
            "parent_plan_id": parent_plan_id,
            "max_attempts": max_attempts,
            "authorization": authorization
            or {
                "allow_weight_updates": False,
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": False,
            },
            "payload": payload,
        }
        plan["content_sha256"] = content_hash(plan)
        return self.import_plan(plan)

    def import_plan(
        self,
        plan: dict[str, Any],
        *,
        notify: bool = True,
    ) -> dict[str, Any]:
        self.validate_plan(plan)
        plan_id = plan["plan_id"]
        with self._locked():
            path = self._path(self.plans_dir, plan_id)
            if path.exists():
                existing = self._read_json(path)
                if canonical_json(existing) != canonical_json(plan):
                    raise LedgerError(f"plan ID collision with different content: {plan_id}")
                return existing
            self._write_json_atomic(path, plan, exclusive=True)
            now = time.time()
            receipt = {
                "schema_version": RECEIPT_SCHEMA,
                "plan_id": plan_id,
                "plan_sha256": plan["content_sha256"],
                "status": "queued",
                "attempt_count": 0,
                "created_at": utc_now(now),
                "updated_at": utc_now(now),
                "claimed_by": None,
                "lease_expires_at": None,
                "next_attempt_at": now,
                "report_id": None,
                "last_error": None,
                "progress": None,
                "history": [
                    {
                        "status": "queued",
                        "at": utc_now(now),
                        "detail": "Plan accepted into the durable ledger.",
                    }
                ],
            }
            self._write_json_atomic(
                self._path(self.receipts_dir, plan_id),
                receipt,
                exclusive=True,
            )
            if notify:
                self.wake_path.touch(mode=0o600, exist_ok=True)
        return plan

    def plan(self, plan_id: str) -> dict[str, Any] | None:
        path = self._path(self.plans_dir, plan_id)
        if not path.exists():
            return None
        plan = self._read_json(path)
        self.validate_plan(plan)
        return plan

    def receipt(self, plan_id: str) -> dict[str, Any] | None:
        path = self._path(self.receipts_dir, plan_id)
        if not path.exists():
            return None
        receipt = self._read_json(path)
        if receipt.get("schema_version") != RECEIPT_SCHEMA:
            raise LedgerError(f"invalid receipt schema: {plan_id}")
        return receipt

    def report(self, plan_id: str) -> dict[str, Any] | None:
        path = self._path(self.reports_dir, plan_id)
        if not path.exists():
            return None
        report = self._read_json(path)
        self.validate_report(report)
        return report

    def accept_remote_report(
        self,
        plan_id: str,
        remote_receipt: dict[str, Any],
        report: dict[str, Any],
    ) -> dict[str, Any]:
        """Mirror an authoritative terminal trainbox report into this ledger."""
        self.validate_report(report)
        with self._locked():
            plan = self.plan(plan_id)
            receipt = self._required_receipt(plan_id)
            if plan is None:
                raise LedgerError(f"unknown local plan: {plan_id}")
            if remote_receipt.get("schema_version") != RECEIPT_SCHEMA:
                raise LedgerError("remote receipt has an invalid schema")
            if remote_receipt.get("plan_id") != plan_id:
                raise LedgerError("remote receipt plan_id mismatch")
            if remote_receipt.get("plan_sha256") != plan["content_sha256"]:
                raise LedgerError("remote receipt plan hash mismatch")
            if remote_receipt.get("status") not in TERMINAL_RECEIPT_STATUSES:
                raise LedgerError("remote receipt is not terminal")
            if report["plan_id"] != plan_id:
                raise LedgerError("remote report plan_id mismatch")
            if report["plan_sha256"] != plan["content_sha256"]:
                raise LedgerError("remote report plan hash mismatch")

            report_path = self._path(self.reports_dir, plan_id)
            if report_path.exists():
                existing = self._read_json(report_path)
                if canonical_json(existing) != canonical_json(report):
                    raise LedgerError("remote report conflicts with the mirrored report")
            else:
                self._write_json_atomic(report_path, report, exclusive=True)
            if receipt.get("status") in TERMINAL_RECEIPT_STATUSES:
                if receipt.get("report_id") != report["report_id"]:
                    raise LedgerError("terminal local receipt conflicts with remote report")
                return report
            self._transition_locked(
                receipt,
                str(remote_receipt["status"]),
                f"Mirrored terminal trainbox report {report['report_id']}.",
                report_id=report["report_id"],
                attempt_count=int(remote_receipt.get("attempt_count") or 0),
                claimed_by=remote_receipt.get("claimed_by"),
                lease_expires_at=None,
                next_attempt_at=None,
                last_error=remote_receipt.get("last_error"),
            )
            return report

    def accept_remote_dead_letter(
        self,
        plan_id: str,
        remote_receipt: dict[str, Any],
    ) -> dict[str, Any]:
        """Mirror a terminal remote failure that exhausted retries before reporting."""
        with self._locked():
            plan = self.plan(plan_id)
            receipt = self._required_receipt(plan_id)
            if plan is None:
                raise LedgerError(f"unknown local plan: {plan_id}")
            if remote_receipt.get("schema_version") != RECEIPT_SCHEMA:
                raise LedgerError("remote receipt has an invalid schema")
            if remote_receipt.get("plan_id") != plan_id:
                raise LedgerError("remote receipt plan_id mismatch")
            if remote_receipt.get("plan_sha256") != plan["content_sha256"]:
                raise LedgerError("remote receipt plan hash mismatch")
            if remote_receipt.get("status") != "dead_letter":
                raise LedgerError("remote receipt is not a reportless dead letter")
            if remote_receipt.get("report_id") is not None:
                raise LedgerError("remote dead letter unexpectedly references a report")
            if receipt.get("status") in TERMINAL_RECEIPT_STATUSES:
                if receipt.get("status") != "dead_letter":
                    raise LedgerError("terminal local receipt conflicts with remote dead letter")
                return receipt
            return self._transition_locked(
                receipt,
                "dead_letter",
                "Mirrored terminal trainbox failure without a report.",
                attempt_count=int(remote_receipt.get("attempt_count") or 0),
                claimed_by=None,
                lease_expires_at=None,
                next_attempt_at=None,
                report_id=None,
                last_error=remote_receipt.get("last_error"),
            )

    def pending_plans(self, *, now: float | None = None) -> list[dict[str, Any]]:
        current = time.time() if now is None else now
        pending: list[dict[str, Any]] = []
        for path in sorted(self.plans_dir.glob("*.json")):
            plan = self._read_json(path)
            receipt = self.receipt(plan["plan_id"])
            if receipt is None or receipt.get("status") in TERMINAL_RECEIPT_STATUSES:
                continue
            if float(receipt.get("next_attempt_at") or 0) > current:
                continue
            pending.append(plan)
        return pending

    def claim(
        self,
        plan_id: str,
        worker_id: str,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        if lease_seconds <= 0:
            raise LedgerError("lease_seconds must be positive")
        now = time.time()
        with self._locked():
            plan = self.plan(plan_id)
            receipt = self.receipt(plan_id)
            if plan is None or receipt is None:
                raise LedgerError(f"unknown plan: {plan_id}")
            if receipt.get("status") in TERMINAL_RECEIPT_STATUSES:
                return None
            claim_path = self._path(self.claims_dir, plan_id)
            if claim_path.exists():
                existing = self._read_json(claim_path)
                if float(existing.get("lease_expires_epoch") or 0) > now:
                    return None
            attempt = int(receipt.get("attempt_count") or 0) + 1
            if attempt > int(plan["max_attempts"]):
                self._transition_locked(
                    receipt,
                    "dead_letter",
                    "Maximum claim attempts exhausted.",
                    claimed_by=None,
                    lease_expires_at=None,
                    next_attempt_at=None,
                )
                claim_path.unlink(missing_ok=True)
                return None
            claim = {
                "schema_version": CLAIM_SCHEMA,
                "plan_id": plan_id,
                "plan_sha256": plan["content_sha256"],
                "worker_id": worker_id,
                "attempt": attempt,
                "claimed_at": utc_now(now),
                "lease_expires_at": utc_now(now + lease_seconds),
                "lease_expires_epoch": now + lease_seconds,
            }
            self._write_json_atomic(claim_path, claim)
            self._transition_locked(
                receipt,
                "claimed",
                f"Claimed by {worker_id}.",
                attempt_count=attempt,
                claimed_by=worker_id,
                lease_expires_at=claim["lease_expires_at"],
            )
            return claim

    def mark_running(self, plan_id: str, worker_id: str) -> dict[str, Any]:
        with self._locked():
            self._assert_claim_owner(plan_id, worker_id)
            receipt = self._required_receipt(plan_id)
            return self._transition_locked(
                receipt,
                "running",
                f"Execution started by {worker_id}.",
            )

    def renew_claim(
        self,
        plan_id: str,
        worker_id: str,
        lease_seconds: int,
        *,
        progress: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if lease_seconds <= 0:
            raise LedgerError("lease_seconds must be positive")
        if progress is not None:
            self._validate_progress(progress)
        with self._locked():
            self._assert_claim_owner(plan_id, worker_id)
            claim_path = self._path(self.claims_dir, plan_id)
            claim = self._read_json(claim_path)
            now = time.time()
            claim["lease_expires_at"] = utc_now(now + lease_seconds)
            claim["lease_expires_epoch"] = now + lease_seconds
            self._write_json_atomic(claim_path, claim)
            receipt = self._required_receipt(plan_id)
            self._transition_locked(
                receipt,
                str(receipt["status"]),
                f"Lease renewed by {worker_id}.",
                lease_expires_at=claim["lease_expires_at"],
                **({"progress": progress} if progress is not None else {}),
            )
            return claim

    @staticmethod
    def _validate_progress(progress: Any) -> None:
        if not isinstance(progress, dict):
            raise LedgerError("progress must be an object")
        required = {
            "kind",
            "phase",
            "completed_chunks",
            "active_chunk",
            "completed_examples",
            "target_examples",
            "semantic_attempt",
        }
        allowed = required | {"active_executor"}
        if (
            not required <= set(progress) <= allowed
            or progress.get("kind") != "cortex_curriculum"
        ):
            raise LedgerError("progress fields do not match the Cortex curriculum schema")
        if progress.get("phase") not in {"generating", "chunk_completed"}:
            raise LedgerError("progress phase is invalid")
        integer_fields = (
            "completed_chunks",
            "completed_examples",
            "target_examples",
            "semantic_attempt",
        )
        if any(
            isinstance(progress.get(field), bool)
            or not isinstance(progress.get(field), int)
            for field in integer_fields
        ):
            raise LedgerError("progress counters must be integers")
        completed_chunks = progress["completed_chunks"]
        completed_examples = progress["completed_examples"]
        target_examples = progress["target_examples"]
        semantic_attempt = progress["semantic_attempt"]
        active_chunk = progress["active_chunk"]
        active_executor = progress.get("active_executor")
        if (
            not 0 <= completed_chunks <= 200
            or not 0 <= completed_examples <= target_examples <= 5000
            or not 0 <= semantic_attempt <= 5
            or (
                active_chunk is not None
                and (
                    isinstance(active_chunk, bool)
                    or not isinstance(active_chunk, int)
                    or not 1 <= active_chunk <= 200
                )
            )
        ):
            raise LedgerError("progress counters are outside their bounds")
        if active_executor is not None and (
            not isinstance(active_executor, str)
            or not active_executor
            or len(active_executor) > 100
        ):
            raise LedgerError("progress active_executor is invalid")

    def complete(
        self,
        plan_id: str,
        worker_id: str,
        *,
        status: str,
        result: dict[str, Any],
        artifact_hashes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        with self._locked():
            receipt = self._required_receipt(plan_id)
            existing = self.report(plan_id)
            if receipt.get("status") in TERMINAL_RECEIPT_STATUSES:
                if existing is None:
                    raise LedgerError("terminal receipt has no report")
                return existing
            self._assert_claim_owner(plan_id, worker_id)
            report_id = f"report-{plan_id}"
            report = {
                "schema_version": REPORT_SCHEMA,
                "report_id": report_id,
                "plan_id": plan_id,
                "plan_sha256": receipt["plan_sha256"],
                "worker_id": worker_id,
                "completed_at": utc_now(),
                "status": status,
                "result": result,
                "artifact_hashes": artifact_hashes or {},
            }
            report["content_sha256"] = content_hash(report)
            self.validate_report(report)
            self._write_json_atomic(
                self._path(self.reports_dir, plan_id),
                report,
                exclusive=True,
            )
            receipt_status = {
                "succeeded": "completed",
                "failed": "dead_letter",
                "blocked": "blocked",
            }[status]
            self._transition_locked(
                receipt,
                receipt_status,
                f"Report {report_id} persisted.",
                report_id=report_id,
                claimed_by=worker_id,
                lease_expires_at=None,
                next_attempt_at=None,
                last_error=None if status == "succeeded" else result.get("error"),
            )
            self._path(self.claims_dir, plan_id).unlink(missing_ok=True)
            return report

    def fail_retryable(
        self,
        plan_id: str,
        worker_id: str,
        error: str,
    ) -> dict[str, Any]:
        with self._locked():
            self._assert_claim_owner(plan_id, worker_id)
            plan = self.plan(plan_id)
            receipt = self._required_receipt(plan_id)
            assert plan is not None
            attempts = int(receipt.get("attempt_count") or 0)
            terminal = attempts >= int(plan["max_attempts"])
            delay = min(300, 15 * (2 ** max(attempts - 1, 0)))
            updated = self._transition_locked(
                receipt,
                "dead_letter" if terminal else "retry_wait",
                "Worker attempt failed.",
                claimed_by=None,
                lease_expires_at=None,
                next_attempt_at=None if terminal else time.time() + delay,
                last_error=error[:4000],
            )
            self._path(self.claims_dir, plan_id).unlink(missing_ok=True)
            return updated

    def snapshot(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        latest: list[dict[str, Any]] = []
        for path in sorted(
            self.receipts_dir.glob("*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        ):
            receipt = self._read_json(path)
            status = str(receipt.get("status"))
            counts[status] = counts.get(status, 0) + 1
            if len(latest) < 20:
                latest.append(receipt)
        return {
            "schema_version": "ninereeds_control_snapshot_v1",
            "root": str(self.root),
            "counts": counts,
            "latest_receipts": latest,
        }

    @staticmethod
    def validate_plan(plan: Any) -> None:
        if not isinstance(plan, dict):
            raise LedgerError("plan must be an object")
        expected = {
            "schema_version",
            "plan_id",
            "created_at",
            "created_by",
            "kind",
            "mode",
            "parent_plan_id",
            "max_attempts",
            "authorization",
            "payload",
            "content_sha256",
        }
        if set(plan) != expected:
            raise LedgerError("plan fields do not match the v1 schema")
        if plan["schema_version"] != PLAN_SCHEMA:
            raise LedgerError("invalid plan schema_version")
        ControlLedger._validate_identifier(plan["plan_id"], "plan_id")
        if plan["kind"] not in PLAN_KINDS:
            raise LedgerError("invalid plan kind")
        if plan["mode"] not in PLAN_MODES:
            raise LedgerError("invalid plan mode")
        if not isinstance(plan["created_by"], str) or not plan["created_by"]:
            raise LedgerError("created_by must be a non-empty string")
        if plan["parent_plan_id"] is not None:
            ControlLedger._validate_identifier(plan["parent_plan_id"], "parent_plan_id")
        if (
            isinstance(plan["max_attempts"], bool)
            or not isinstance(plan["max_attempts"], int)
            or not 1 <= plan["max_attempts"] <= 10
        ):
            raise LedgerError("max_attempts must be an integer from 1 to 10")
        authorization = plan["authorization"]
        auth_keys = {
            "allow_weight_updates",
            "allow_checkpoint_promotion",
            "allow_auto_advance",
        }
        if (
            not isinstance(authorization, dict)
            or set(authorization) != auth_keys
            or not all(isinstance(value, bool) for value in authorization.values())
        ):
            raise LedgerError("authorization fields must be explicit booleans")
        if plan["mode"] == "shadow" and any(authorization.values()):
            raise LedgerError("shadow plans cannot authorize mutations or auto-advance")
        if not isinstance(plan["payload"], dict):
            raise LedgerError("payload must be an object")
        if len(canonical_json(plan)) > MAX_ENVELOPE_BYTES:
            raise LedgerError("plan exceeds the maximum envelope size")
        expected_hash = content_hash(plan)
        if not secrets.compare_digest(str(plan["content_sha256"]), expected_hash):
            raise LedgerError("plan content hash mismatch")

    @staticmethod
    def validate_report(report: Any) -> None:
        if not isinstance(report, dict):
            raise LedgerError("report must be an object")
        expected = {
            "schema_version",
            "report_id",
            "plan_id",
            "plan_sha256",
            "worker_id",
            "completed_at",
            "status",
            "result",
            "artifact_hashes",
            "content_sha256",
        }
        if set(report) != expected:
            raise LedgerError("report fields do not match the v1 schema")
        if report["schema_version"] != REPORT_SCHEMA:
            raise LedgerError("invalid report schema_version")
        ControlLedger._validate_identifier(report["plan_id"], "plan_id")
        if report["report_id"] != f"report-{report['plan_id']}":
            raise LedgerError("report_id does not correlate to plan_id")
        if report["status"] not in REPORT_STATUSES:
            raise LedgerError("invalid report status")
        if not isinstance(report["result"], dict):
            raise LedgerError("report result must be an object")
        if not isinstance(report["artifact_hashes"], dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in report["artifact_hashes"].items()
        ):
            raise LedgerError("artifact_hashes must map strings to strings")
        if not secrets.compare_digest(
            str(report["content_sha256"]), content_hash(report)
        ):
            raise LedgerError("report content hash mismatch")

    @staticmethod
    def _validate_identifier(value: Any, field: str) -> None:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 160
            or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._" for character in value)
        ):
            raise LedgerError(f"invalid {field}")

    def _required_receipt(self, plan_id: str) -> dict[str, Any]:
        receipt = self.receipt(plan_id)
        if receipt is None:
            raise LedgerError(f"missing receipt: {plan_id}")
        return receipt

    def _assert_claim_owner(self, plan_id: str, worker_id: str) -> None:
        path = self._path(self.claims_dir, plan_id)
        if not path.exists():
            raise LedgerError(f"plan is not claimed: {plan_id}")
        claim = self._read_json(path)
        if claim.get("worker_id") != worker_id:
            raise LedgerError(f"plan is claimed by another worker: {plan_id}")
        if float(claim.get("lease_expires_epoch") or 0) <= time.time():
            raise LedgerError(f"plan claim lease expired: {plan_id}")

    def _transition_locked(
        self,
        receipt: dict[str, Any],
        status: str,
        detail: str,
        **updates: Any,
    ) -> dict[str, Any]:
        if receipt.get("status") in TERMINAL_RECEIPT_STATUSES:
            return receipt
        now = utc_now()
        receipt.update(updates)
        receipt["status"] = status
        receipt["updated_at"] = now
        history = list(receipt.get("history") or [])
        history.append({"status": status, "at": now, "detail": detail})
        receipt["history"] = history[-100:]
        self._write_json_atomic(
            self._path(self.receipts_dir, receipt["plan_id"]),
            receipt,
        )
        return receipt

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LedgerError(f"cannot read {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise LedgerError(f"{path} must contain a JSON object")
        return value

    @staticmethod
    def _write_json_atomic(
        path: Path,
        value: dict[str, Any],
        *,
        exclusive: bool = False,
    ) -> None:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if exclusive and path.exists():
            raise LedgerError(f"refusing to overwrite {path}")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(canonical_json(value) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            if exclusive and path.exists():
                raise LedgerError(f"refusing to overwrite {path}")
            os.replace(temporary, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _path(directory: Path, identifier: str) -> Path:
        ControlLedger._validate_identifier(identifier, "identifier")
        return directory / f"{identifier}.json"
