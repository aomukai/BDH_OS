from __future__ import annotations

from typing import Any

from ..errors import SafetyError


class DisabledHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        raise SafetyError("handler has not been commissioned")
