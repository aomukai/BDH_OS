from __future__ import annotations

from training.pipeline.control.timing_log import PipelineTimingLog


def test_timing_log_keeps_only_the_latest_seven_days(tmp_path, monkeypatch) -> None:
    now = 2_000_000.0
    monkeypatch.setattr(
        "training.pipeline.control.timing_log.time.time",
        lambda: now,
    )
    timing = PipelineTimingLog(tmp_path / "control")

    timing.record(
        "old.event",
        "test",
        timestamp=now - 8 * 24 * 60 * 60,
    )
    timing.record("current.event", "test", timestamp=now)

    events = timing.events(now=now)
    assert [event["event"] for event in events] == ["current.event"]
    assert timing.path.stat().st_mode & 0o777 == 0o600
