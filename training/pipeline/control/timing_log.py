from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TIMING_SCHEMA = "ninereeds_pipeline_timing_v1"
RETENTION_SECONDS = 7 * 24 * 60 * 60
MAX_EVENTS = 20_000


def _iso_time(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _parse_time(value: str) -> float:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized).timestamp()


def plan_timing_fields(plan: dict[str, Any]) -> dict[str, Any]:
    payload = plan.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    workflow = payload.get("workflow")
    workflow = workflow if isinstance(workflow, dict) else {}
    task = payload.get("task")
    task = task if isinstance(task, dict) else {}
    task_title = task.get("title") or payload.get("title")
    task_id = task.get("job_id") or workflow.get("session_id")
    return {
        "requested_model": payload.get("model_id"),
        "workflow": workflow.get("type"),
        "task": task_title,
        "task_id": task_id,
    }


class PipelineTimingLog:
    """Small, privacy-bounded, seven-day operational event ledger."""

    def __init__(
        self,
        control_root: Path,
        *,
        retention_seconds: int = RETENTION_SECONDS,
        max_events: int = MAX_EVENTS,
    ) -> None:
        self.root = control_root.resolve() / "telemetry"
        self.path = self.root / "pipeline_timing.jsonl"
        self.lock_path = self.root / "pipeline_timing.lock"
        self.retention_seconds = retention_seconds
        self.max_events = max_events

    def record(
        self,
        event: str,
        component: str,
        *,
        timestamp: float | None = None,
        **fields: Any,
    ) -> dict[str, Any]:
        now = time.time()
        observed = now if timestamp is None else timestamp
        value = {
            "schema_version": TIMING_SCHEMA,
            "timestamp": _iso_time(observed),
            "epoch_seconds": round(observed, 3),
            "event": str(event)[:100],
            "component": str(component)[:100],
        }
        for key, field in fields.items():
            if field is not None and isinstance(field, (str, int, float, bool)):
                value[str(key)[:80]] = field
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            events = self._read_unlocked()
            cutoff = now - self.retention_seconds
            events = [
                item
                for item in events
                if float(item.get("epoch_seconds") or 0) >= cutoff
            ]
            events.append(value)
            self._write_unlocked(events[-self.max_events :])
        return value

    def events(self, *, limit: int = 300, now: float | None = None) -> list[dict[str, Any]]:
        current = time.time() if now is None else now
        bounded_limit = max(1, min(int(limit), 2000))
        try:
            with self.lock_path.open("a+", encoding="utf-8") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
                events = self._read_unlocked()
        except OSError:
            return []
        cutoff = current - self.retention_seconds
        retained = [
            item
            for item in events
            if float(item.get("epoch_seconds") or 0) >= cutoff
        ]
        retained.sort(key=lambda item: float(item.get("epoch_seconds") or 0))
        return retained[-bounded_limit:]

    def record_report(
        self,
        *,
        plan: dict[str, Any],
        receipt: dict[str, Any],
        report: dict[str, Any],
        source: str,
        observed_at: float | None = None,
    ) -> dict[str, Any]:
        result = report.get("result")
        result = result if isinstance(result, dict) else {}
        attempts = result.get("attempts")
        attempts = attempts if isinstance(attempts, list) else []
        chunk_results = result.get("chunk_results")
        chunk_results = chunk_results if isinstance(chunk_results, list) else []
        prompt_tokens = completion_tokens = total_tokens = 0
        model_attempt_seconds = 0.0
        peak_gpu_memory_mib: float | None = None
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            usage = attempt.get("usage")
            if isinstance(usage, dict):
                prompt_tokens += int(usage.get("prompt_tokens") or 0)
                completion_tokens += int(usage.get("completion_tokens") or 0)
                total_tokens += int(usage.get("total_tokens") or 0)
            model_attempt_seconds += float(attempt.get("elapsed_seconds") or 0)
            peak = attempt.get("peak_gpu_memory_mib")
            if isinstance(peak, (int, float)) and not isinstance(peak, bool):
                peak_gpu_memory_mib = max(peak_gpu_memory_mib or 0, float(peak))

        started_at = _history_time(receipt, "running")
        queued_at = _history_time(receipt, "queued")
        completed_at = _parse_time(report["completed_at"])
        observed = time.time() if observed_at is None else observed_at
        model = result.get("model") or result.get("model_id")
        if model is None:
            model = next(
                (
                    attempt.get("model_id")
                    for attempt in reversed(attempts)
                    if isinstance(attempt, dict)
                    and isinstance(attempt.get("model_id"), str)
                ),
                None,
            )
        provider = result.get("provider")
        if provider is None and isinstance(model, str):
            provider = "local" if not _looks_remote_model(model) else "remote"
        attempt_count = result.get("attempt_count")
        if not isinstance(attempt_count, int):
            attempt_count = sum(
                int(item.get("attempt_count") or 0)
                for item in chunk_results
                if isinstance(item, dict)
            ) or None
        script_attempt_count = (
            attempt_count if plan.get("kind") == "executor_job" else None
        )
        attribution = plan_timing_fields(plan)
        return self.record(
            "plan.report",
            "control-ledger",
            timestamp=completed_at,
            plan_id=plan.get("plan_id"),
            plan_kind=plan.get("kind"),
            role=_role_for_kind(str(plan.get("kind") or "")),
            workflow=attribution.get("workflow"),
            task=attribution.get("task"),
            task_id=attribution.get("task_id"),
            mode=plan.get("mode"),
            status=report.get("status"),
            source=source,
            worker_id=report.get("worker_id"),
            provider=provider,
            model=model,
            requested_model=result.get("requested_model_id"),
            attempt_count=attempt_count,
            script_attempt_count=script_attempt_count,
            semantic_attempt_count=(
                sum(
                    int(item.get("semantic_attempt") or 0)
                    for item in chunk_results
                    if isinstance(item, dict)
                )
                or None
            ),
            runtime_ms=(
                round((completed_at - started_at) * 1000)
                if started_at is not None
                else None
            ),
            queue_ms=(
                round((started_at - queued_at) * 1000)
                if started_at is not None and queued_at is not None
                else None
            ),
            handoff_ms=(
                round((observed - completed_at) * 1000)
                if source == "trainbox_sync"
                else None
            ),
            model_attempt_ms=round(model_attempt_seconds * 1000) or None,
            prompt_tokens=prompt_tokens or None,
            completion_tokens=completion_tokens or None,
            total_tokens=total_tokens or None,
            peak_gpu_memory_mib=peak_gpu_memory_mib,
            valid=result.get("valid"),
        )

    def _read_unlocked(self) -> list[dict[str, Any]]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        except OSError:
            return []
        events: list[dict[str, Any]] = []
        for line in lines[-self.max_events :]:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("schema_version") == TIMING_SCHEMA:
                events.append(value)
        return events

    def _write_unlocked(self, events: list[dict[str, Any]]) -> None:
        descriptor, name = tempfile.mkstemp(prefix=".pipeline_timing.", dir=self.root)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                for event in events:
                    handle.write(
                        json.dumps(
                            event,
                            ensure_ascii=False,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                        + "\n"
                    )
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)


def _history_time(receipt: dict[str, Any], status: str) -> float | None:
    for item in reversed(receipt.get("history") or []):
        if isinstance(item, dict) and item.get("status") == status:
            value = item.get("at")
            if isinstance(value, str):
                return _parse_time(value)
    return None


def _role_for_kind(kind: str) -> str:
    return {
        "strategic_decision": "orchestrator",
        "executor_job": "executor",
        "phase_block": "trainer",
        "cortex_block": "trainer",
        "cortex_corpus_chunk": "corpus",
        "cortex_evaluation": "evaluator",
        "trainer_session": "trainer",
        "micro_update": "trainer",
    }.get(kind, "control")


def _looks_remote_model(model: str) -> bool:
    lowered = model.casefold()
    return any(
        marker in lowered
        for marker in ("gpt-", "deepseek", "openrouter", "claude", "gemini")
    )
