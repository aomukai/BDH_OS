from __future__ import annotations

import json
import subprocess
import threading
import time
from typing import Any

from lab.backend.config import LabConfig
from training.pipeline.control.ledger import ControlLedger
from training.pipeline.control.timing_log import PipelineTimingLog, plan_timing_fields


SNAPSHOT_SCHEMA = "ninereeds_control_snapshot_v1"


class ControlStatusService:
    """Return bounded ledger metadata without exposing plan payloads."""

    def __init__(self, config: LabConfig) -> None:
        self.config = config
        self._lock = threading.Lock()
        self._cached: dict[str, Any] | None = None
        self._cached_at = 0.0

    def status(self, *, force: bool = False) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            if (
                not force
                and self._cached is not None
                and now - self._cached_at < self.config.control_status_cache_seconds
            ):
                result = dict(self._cached)
                result["cache_age_seconds"] = round(now - self._cached_at, 1)
                return result
            result = {
                "schema_version": "ninereeds_lab_control_status_v1",
                "observed_at": now,
                "local": self._local_snapshot(),
                "trainbox": self._remote_snapshot(),
                "providers": self._provider_snapshot(),
                "campaign": self._campaign_snapshot(),
                "schedule": self._schedule_snapshot(
                    "ninereeds-orchestrator-supervisor.timer"
                ),
                "services": {
                    "supervisor": self._service_active(
                        "ninereeds-orchestrator-supervisor.service"
                    ),
                    "supervisor_path": self._service_active(
                        "ninereeds-orchestrator-supervisor.path"
                    ),
                    "supervisor_timer": self._service_active(
                        "ninereeds-orchestrator-supervisor.timer"
                    ),
                },
            }
            result["ok"] = bool(
                result["local"]["ok"]
                and result["trainbox"]["ok"]
                and result["services"]["supervisor_path"]
                and result["services"]["supervisor_timer"]
            )
            result["cache_age_seconds"] = 0.0
            self._cached = result
            self._cached_at = now
            return dict(result)

    def _campaign_snapshot(self) -> dict[str, Any]:
        path = self.config.orchestrator_control_root / "campaign/state.json"
        wave_path = self._latest_allowlist_wave_state_path()
        if wave_path is not None:
            try:
                generic_mtime = path.stat().st_mtime
            except OSError:
                generic_mtime = -1.0
            try:
                wave_mtime = wave_path.stat().st_mtime
            except OSError:
                wave_mtime = -1.0
            if wave_mtime >= generic_mtime:
                wave = self._allowlist_wave_snapshot(wave_path)
                if wave is not None:
                    return wave
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            return {
                "configured": False,
                "status": "not_started",
                "error": str(exc),
            }
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != "ninereeds_autonomous_campaign_v1"
        ):
            return {
                "configured": False,
                "status": "invalid",
                "error": "unexpected campaign state schema",
            }
        budgets = value.get("budgets") if isinstance(value.get("budgets"), dict) else {}
        usage = value.get("usage") if isinstance(value.get("usage"), dict) else {}
        safe_keys = {
            "strategic_boundaries",
            "phase_blocks",
            "executor_jobs",
            "trainer_sessions",
        }
        campaign_id = str(value.get("campaign_id") or "unknown")[:100]
        display_name = campaign_id
        registry_path = self.config.repo_root / "training/logs/campaign_registry.json"
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            match = next(
                (
                    row
                    for row in registry.get("campaigns", [])
                    if isinstance(row, dict)
                    and row.get("campaign_id") == campaign_id
                ),
                None,
            )
            if match is not None and isinstance(match.get("display_name"), str):
                display_name = match["display_name"][:140]
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            pass
        play = value.get("play") if value.get("regime") == "play" else None
        play_snapshot = None
        if isinstance(play, dict) and isinstance(play.get("active_branch"), dict):
            branch = play["active_branch"]
            play_snapshot = {
                "branch_id": branch.get("branch_id"),
                "branch_index": branch.get("branch_index"),
                "strategy": branch.get("strategy"),
                "optimizer_steps": branch.get("optimizer_steps"),
                "target_steps": play.get("branch_target_steps"),
                "completed_branches": len(play.get("completed_branches") or []),
                "max_branches": play.get("max_branches"),
                "best_score": play.get("best_score"),
                "target_score": play.get("target_score"),
            }
        return {
            "configured": True,
            "campaign_id": campaign_id,
            "display_name": display_name,
            "status": str(value.get("status") or "unknown")[:40],
            "current_plan_id": (
                str(value.get("current_plan_id"))[:180]
                if value.get("current_plan_id") is not None
                else None
            ),
            "boundary_index": value.get("boundary_index"),
            "deadline_at": value.get("deadline_at"),
            "stop_reason": (
                str(value.get("stop_reason"))[:500]
                if value.get("stop_reason") is not None
                else None
            ),
            "budgets": {
                key: budgets.get(key)
                for key in safe_keys
                if isinstance(budgets.get(key), int)
            },
            "usage": {
                key: usage.get(key)
                for key in safe_keys
                if isinstance(usage.get(key), int)
            },
            "regime": str(value.get("regime") or "standard")[:40],
            "play": play_snapshot,
        }

    def _latest_allowlist_wave_state_path(self) -> Path | None:
        derived = self.config.orchestrator_control_root / "derived"
        paths = sorted(
            derived.glob("allowlist-*-state.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        return paths[0] if paths else None

    def _allowlist_wave_snapshot(
        self, path: Path | None = None
    ) -> dict[str, Any] | None:
        path = path or self._latest_allowlist_wave_state_path()
        if path is None:
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != "ninereeds_allowlist_wave_state_v1"
        ):
            return None
        campaign_id = str(value.get("wave_id") or "allowlist-wave")[:100]
        display_name = campaign_id
        registry_path = self.config.repo_root / "training/logs/campaign_registry.json"
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            entry = next(
                (
                    row
                    for row in registry.get("campaigns", [])
                    if isinstance(row, dict) and row.get("campaign_id") == campaign_id
                ),
                None,
            )
            if entry is not None:
                display_name = str(entry.get("display_name") or display_name)[:140]
        except (OSError, json.JSONDecodeError):
            pass
        block = int(value.get("block_index") or 0)
        accepted = value.get("accepted_blocks")
        rejected = value.get("rejected_attempts")
        accepted_count = len(accepted) if isinstance(accepted, list) else 0
        rejected_count = len(rejected) if isinstance(rejected, list) else 0
        status = str(value.get("status") or "unknown")[:40]
        phase = str(value.get("phase") or "unknown").replace("_", " ")
        handoff = value.get("handoff") if isinstance(value.get("handoff"), dict) else {}
        if status == "running":
            stop_reason = f"Block {min(block, 12)} of 12: {phase}."
        elif status == "completed":
            stop_reason = "All 12 allowlist blocks passed their admission gates."
        else:
            stop_reason = str(handoff.get("reason") or "The wave requires intervention.")[:500]
        return {
            "configured": True,
            "campaign_id": campaign_id,
            "display_name": display_name,
            "status": status,
            "current_plan_id": (
                str(value.get("current_plan_id"))[:180]
                if value.get("current_plan_id") is not None
                else None
            ),
            "boundary_index": min(block, 12),
            "deadline_at": None,
            "stop_reason": stop_reason,
            "budgets": {"phase_blocks": 12, "strategic_boundaries": 0},
            "usage": {
                "phase_blocks": accepted_count,
                "strategic_boundaries": 0,
                "rejected_attempts": rejected_count,
            },
            "wave": {
                "concepts_total": 1500,
                "concepts_admitted": accepted_count * 125,
                "blocks_total": 12,
                "blocks_admitted": accepted_count,
                "attempt_index": value.get("attempt_index"),
                "phase": value.get("phase"),
                "parent_checkpoint": value.get("parent_checkpoint"),
            },
        }

    def timing(self, *, limit: int = 300) -> dict[str, Any]:
        events = PipelineTimingLog(
            self.config.orchestrator_control_root
        ).events(limit=limit)
        ledger = ControlLedger(self.config.orchestrator_control_root)
        attribution: dict[str, dict[str, Any]] = {}
        enriched = []
        for event in events:
            value = dict(event)
            plan_id = value.get("plan_id")
            if isinstance(plan_id, str) and (
                not value.get("task") or not value.get("requested_model")
            ):
                if plan_id not in attribution:
                    plan = ledger.plan(plan_id)
                    attribution[plan_id] = (
                        plan_timing_fields(plan) if plan is not None else {}
                    )
                for key, field in attribution[plan_id].items():
                    if field is not None and value.get(key) is None:
                        value[key] = field
            enriched.append(value)
        return {
            "schema_version": "ninereeds_lab_pipeline_timing_v1",
            "retention_days": 7,
            "events": enriched,
        }

    def _provider_snapshot(self) -> dict[str, Any]:
        path = self.config.orchestrator_control_root / "provider/status.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "selected_provider": None,
                "reason": "status_unavailable",
                "error": str(exc),
                "codex": {"state": "unknown", "buckets": []},
                "fugu": {"state": "unknown"},
            }
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != "ninereeds_provider_status_v1"
        ):
            return {
                "ok": False,
                "selected_provider": None,
                "reason": "invalid_status",
                "error": "unexpected provider status schema",
                "codex": {"state": "unknown", "buckets": []},
                "fugu": {"state": "unknown"},
            }
        codex = value.get("codex") if isinstance(value.get("codex"), dict) else {}
        fugu = value.get("fugu") if isinstance(value.get("fugu"), dict) else {}
        buckets = codex.get("buckets") if isinstance(codex.get("buckets"), list) else []
        safe_buckets = []
        for bucket in buckets[:8]:
            if not isinstance(bucket, dict):
                continue
            windows = bucket.get("windows") if isinstance(bucket.get("windows"), list) else []
            safe_buckets.append(
                {
                    "limit_id": str(bucket.get("limit_id") or "unknown")[:100],
                    "limited": bool(bucket.get("limited")),
                    "windows": [
                        {
                            "role": str(window.get("role") or "unknown")[:20],
                            "used_percent": window.get("used_percent"),
                            "duration_minutes": window.get("duration_minutes"),
                            "resets_at": window.get("resets_at"),
                        }
                        for window in windows[:4]
                        if isinstance(window, dict)
                    ],
                }
            )
        return {
            "ok": codex.get("state") in {"available", "limited"},
            "observed_at": value.get("observed_at"),
            "selected_provider": value.get("selected_provider"),
            "reason": value.get("reason"),
            "codex": {
                "state": codex.get("state", "unknown"),
                "buckets": safe_buckets,
            },
            "fugu": {"state": fugu.get("state", "unknown")},
        }

    def _local_snapshot(self) -> dict[str, Any]:
        try:
            snapshot = ControlLedger(self.config.orchestrator_control_root).snapshot()
            return {"ok": True, **self._sanitize_snapshot(snapshot)}
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "counts": {}, "latest_receipts": []}

    def _remote_snapshot(self) -> dict[str, Any]:
        target = self.config.trainbox_control_ssh_target
        if not target:
            return {
                "ok": False,
                "reachable": False,
                "error": "Trainbox control target is not configured.",
                "counts": {},
                "latest_receipts": [],
            }
        started = time.monotonic()
        try:
            completed = subprocess.run(
                [
                    "/usr/bin/ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    f"ConnectTimeout={self.config.control_status_timeout_seconds}",
                    target,
                    "snapshot",
                ],
                text=True,
                capture_output=True,
                timeout=self.config.control_status_timeout_seconds + 2,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "ok": False,
                "reachable": False,
                "error": str(exc),
                "counts": {},
                "latest_receipts": [],
            }
        latency_ms = round((time.monotonic() - started) * 1000)
        if completed.returncode != 0:
            return {
                "ok": False,
                "reachable": False,
                "latency_ms": latency_ms,
                "error": (completed.stderr.strip() or "Control snapshot failed.")[:500],
                "counts": {},
                "latest_receipts": [],
            }
        try:
            envelope = json.loads(completed.stdout)
            snapshot = envelope["snapshot"]
            sanitized = self._sanitize_snapshot(snapshot)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return {
                "ok": False,
                "reachable": True,
                "latency_ms": latency_ms,
                "error": f"Invalid control snapshot: {exc}",
                "counts": {},
                "latest_receipts": [],
            }
        return {
            "ok": bool(envelope.get("ok")),
            "reachable": True,
            "latency_ms": latency_ms,
            **sanitized,
        }

    @staticmethod
    def _sanitize_snapshot(snapshot: Any) -> dict[str, Any]:
        if not isinstance(snapshot, dict) or snapshot.get("schema_version") != SNAPSHOT_SCHEMA:
            raise ValueError("unexpected control snapshot schema")
        counts = snapshot.get("counts")
        receipts = snapshot.get("latest_receipts")
        if not isinstance(counts, dict) or not isinstance(receipts, list):
            raise ValueError("control snapshot fields are malformed")
        safe_counts: dict[str, int] = {}
        for key, value in counts.items():
            if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("control snapshot counts are malformed")
            safe_counts[key] = value
        safe_receipts = []
        allowed = {
            "plan_id",
            "status",
            "attempt_count",
            "created_at",
            "updated_at",
            "claimed_by",
            "lease_expires_at",
            "next_attempt_at",
            "report_id",
            "last_error",
            "progress",
        }
        for receipt in receipts[:12]:
            if not isinstance(receipt, dict):
                raise ValueError("control receipt is malformed")
            safe_receipt = {key: receipt.get(key) for key in allowed}
            progress = safe_receipt.get("progress")
            if isinstance(progress, dict):
                progress_keys = {
                    "kind",
                    "phase",
                    "completed_chunks",
                    "active_chunk",
                    "completed_examples",
                    "target_examples",
                    "semantic_attempt",
                    "active_executor",
                }
                safe_receipt["progress"] = {
                    key: progress.get(key) for key in progress_keys
                }
            else:
                safe_receipt["progress"] = None
            history = receipt.get("history")
            if isinstance(history, list):
                safe_receipt["started_at"] = next(
                    (
                        item.get("at")
                        for item in history
                        if isinstance(item, dict)
                        and item.get("status") == "running"
                        and isinstance(item.get("at"), str)
                    ),
                    None,
                )
            else:
                safe_receipt["started_at"] = None
            safe_receipts.append(safe_receipt)
        return {
            "schema_version": SNAPSHOT_SCHEMA,
            "counts": safe_counts,
            "latest_receipts": safe_receipts,
        }

    @staticmethod
    def _service_active(unit: str) -> bool:
        try:
            result = subprocess.run(
                ["/usr/bin/systemctl", "--user", "is-active", "--quiet", unit],
                capture_output=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    @staticmethod
    def _timer_snapshot(unit: str) -> dict[str, Any]:
        try:
            result = subprocess.run(
                [
                    "/usr/bin/systemctl",
                    "--user",
                    "list-timers",
                    unit,
                    "--all",
                    "--no-legend",
                    "--no-pager",
                    "--output=json",
                ],
                text=True,
                capture_output=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "available": False,
                "status": "unavailable",
                "next_run_at": None,
                "last_run_at": None,
                "error": str(exc)[:300],
            }
        try:
            rows = json.loads(result.stdout) if result.returncode == 0 else []
            row = rows[0] if isinstance(rows, list) and rows else None
            if not isinstance(row, dict):
                raise ValueError("timer is not scheduled")
            next_usec = row.get("next")
            last_usec = row.get("last")
            if (
                isinstance(next_usec, bool)
                or not isinstance(next_usec, (int, float))
                or next_usec <= 0
            ):
                raise ValueError("timer has no next activation")
            return {
                "available": True,
                "status": "waiting_for_due_work",
                "next_run_at": next_usec / 1_000_000,
                "last_run_at": (
                    last_usec / 1_000_000
                    if isinstance(last_usec, (int, float))
                    and not isinstance(last_usec, bool)
                    and last_usec > 0
                    else None
                ),
                "unit": unit,
            }
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            detail = result.stderr.strip() or str(exc)
            return {
                "available": False,
                "status": "unavailable",
                "next_run_at": None,
                "last_run_at": None,
                "error": detail[:300],
            }

    def _schedule_snapshot(self, unit: str) -> dict[str, Any]:
        timer = self._timer_snapshot(unit)
        path = self.config.orchestrator_control_root / "scheduler/status.json"
        try:
            scheduler = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return timer
        if not isinstance(scheduler, dict):
            return timer
        action = scheduler.get("action")
        if not isinstance(action, str):
            return timer
        result = dict(timer)
        result["watcher_next_check_at"] = timer.get("next_run_at")
        result["status"] = action
        result["plan_id"] = str(scheduler.get("plan_id") or "")[:200] or None
        next_wake_at = scheduler.get("next_wake_at")
        result["next_run_at"] = (
            float(next_wake_at)
            if isinstance(next_wake_at, (int, float))
            and not isinstance(next_wake_at, bool)
            else None
        )
        result["observed_at"] = scheduler.get("observed_at")
        return result
