"""Mission Hub-only deterministic schedule materialization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import ConfigBundle
from .store import MissionHubStore


class Scheduler:
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store = store
        self.bundle = bundle

    def tick(self, *, actor: str, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        created: list[dict[str, Any]] = []
        for schedule in self.bundle.schedules.values():
            if not schedule["enabled"]:
                continue
            interval = schedule["interval_seconds"]
            if schedule["trigger"] != "interval" or interval < 1:
                continue
            slot_number = int(now.timestamp()) // interval
            slot = f"interval-{interval}-{slot_number}"
            idempotency_key = f"schedule:{schedule['id']}:{slot}"
            job = self.store.create_job(
                self.bundle,
                job_type=schedule["job_type"],
                input_payload=schedule["input"],
                idempotency_key=idempotency_key,
                created_by=actor,
                requested_machine_id=schedule["machine_id"],
            )
            if self.store.record_schedule_firing(schedule_id=schedule["id"], slot=slot, job_id=job["id"]):
                created.append({"schedule_id": schedule["id"], "slot": slot, "job_id": job["id"]})
        return created
