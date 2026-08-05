from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from mission_hub.config import load_config_bundle
from mission_hub.scheduler import Scheduler
from mission_hub.store import MissionHubStore


REPO = Path(__file__).resolve().parents[1]


def test_schedule_slot_is_materialized_once(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.schedules["trainbox-health"]["enabled"] = True
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    scheduler = Scheduler(store, bundle)
    now = datetime(2026, 8, 5, tzinfo=timezone.utc)
    assert len(scheduler.tick(actor="scheduler", now=now)) == 1
    assert scheduler.tick(actor="scheduler", now=now) == []
    assert len(store.list_rows("jobs")) == 1
