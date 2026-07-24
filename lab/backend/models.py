from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Artifact:
    id: str
    path: str
    type: str
    title: str
    media_type: str
    size: int
    mtime: float
    campaign_id: str | None = None
    epoch: int | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Campaign:
    id: str
    title: str
    artifacts: list[Artifact] = field(default_factory=list)
    latest_event_at: float = 0
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        return data


@dataclass(slots=True)
class Event:
    id: str
    timestamp: float
    kind: str
    title: str
    campaign_id: str | None = None
    artifact_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Message:
    id: str
    box: str
    path: str
    title: str
    body: str
    timestamp: float
    schema_version: str = "legacy"
    sender: str | None = None
    recipient: str | None = None
    correlation_id: str | None = None
    reply_to: str | None = None
    status: str | None = None
    disposition: str | None = None
    requires_interactive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PublishedBuild:
    id: str
    label: str
    checkpoint_artifact_id: str
    path: str
    published_at: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
