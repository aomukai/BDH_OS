from __future__ import annotations

from mission_hub.store import strategic_available_at


def test_strategic_cooldown_is_anchored_to_terminal_completion() -> None:
    assert strategic_available_at("2026-08-06T01:02:03.000000Z", 900) == "2026-08-06T01:17:03.000000Z"


def test_strategic_cooldown_can_be_explicitly_zero() -> None:
    assert strategic_available_at("2026-08-06T01:02:03.123456Z", 0) == "2026-08-06T01:02:03.123456Z"
