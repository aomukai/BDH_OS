from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any

from .config import GrowthPolicyConfig


@dataclass(frozen=True)
class GrowthObservation:
    """One explicit observation supplied to the allocation policy.

    Internal residual may nominate growth.  The two booleans keep organism-level
    evidence and local capacity diagnosis separate from that nomination.
    """

    internal_residual: float
    externally_verified_failure: bool
    capacity_saturated: bool
    event_id: str


class GrowthController:
    """Deterministic, stateful birth gate with patience and cooldown."""

    def __init__(self, config: GrowthPolicyConfig | None = None) -> None:
        self.config = config or GrowthPolicyConfig()
        self.config.validate()
        self.qualifying_streak = 0
        self.cooldown_remaining = 0
        self.birth_count = 0
        self.last_event_id: str | None = None

    def observe(self, observation: GrowthObservation) -> bool:
        if not observation.event_id:
            raise ValueError("event_id must be non-empty")
        if observation.event_id == self.last_event_id:
            raise ValueError("a growth event may be observed only once")
        if not math.isfinite(observation.internal_residual):
            raise ValueError("internal_residual must be finite")
        self.last_event_id = observation.event_id

        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            self.qualifying_streak = 0
            return False

        qualifies = observation.internal_residual >= self.config.residual_threshold
        if self.config.require_external_failure:
            qualifies = qualifies and observation.externally_verified_failure
        if self.config.require_capacity_saturation:
            qualifies = qualifies and observation.capacity_saturated

        self.qualifying_streak = self.qualifying_streak + 1 if qualifies else 0
        if self.qualifying_streak < self.config.qualifying_observations:
            return False

        self.qualifying_streak = 0
        self.cooldown_remaining = self.config.cooldown_observations
        self.birth_count += 1
        return True

    def state_dict(self) -> dict[str, Any]:
        return {
            "config": dataclasses.asdict(self.config),
            "qualifying_streak": self.qualifying_streak,
            "cooldown_remaining": self.cooldown_remaining,
            "birth_count": self.birth_count,
            "last_event_id": self.last_event_id,
        }

    @classmethod
    def from_state_dict(cls, value: dict[str, Any]) -> "GrowthController":
        controller = cls(GrowthPolicyConfig(**value["config"]))
        controller.qualifying_streak = int(value["qualifying_streak"])
        controller.cooldown_remaining = int(value["cooldown_remaining"])
        controller.birth_count = int(value["birth_count"])
        controller.last_event_id = value.get("last_event_id")
        return controller
