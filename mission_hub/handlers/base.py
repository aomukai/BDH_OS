from __future__ import annotations

from typing import Any, Protocol


class JobHandler(Protocol):
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]: ...
