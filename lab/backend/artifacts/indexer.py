from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import threading
from collections import defaultdict
from pathlib import Path
from typing import Any

from lab.backend.config import LabConfig
from lab.backend.models import Artifact, Campaign, Event


CAMPAIGN_PATTERNS = (
    re.compile(r"campaign[_ -]?(\d+[a-z]?)", re.IGNORECASE),
    re.compile(r"\bc(\d+[a-z]?)(?=[_\-.\s])", re.IGNORECASE),
)
EPOCH_PATTERN = re.compile(r"(?:^|[_\-.])e(\d+)(?:[_\-.]|$)", re.IGNORECASE)


class ArtifactIndex:
    def __init__(self, config: LabConfig) -> None:
        self.config = config
        self._lock = threading.RLock()
        self._artifacts: dict[str, Artifact] = {}
        self._campaigns: dict[str, Campaign] = {}
        self._events: list[Event] = []
        self._last_scan_at = 0.0

    @property
    def last_scan_at(self) -> float:
        with self._lock:
            return self._last_scan_at

    def scan(self) -> dict[str, Any]:
        artifacts: dict[str, Artifact] = {}
        for root_name in self.config.scan_roots:
            root = self.config.repo_root / root_name
            if not root.exists():
                continue
            if root.is_file():
                candidates = [root]
            else:
                candidates = [path for path in root.rglob("*") if path.is_file()]
            for path in candidates:
                if self._should_skip(path):
                    continue
                artifact = self._artifact_from_path(path)
                artifacts[artifact.id] = artifact

        campaigns = self._build_campaigns(artifacts.values())
        events = self._build_events(artifacts.values(), campaigns)
        newest = max((artifact.mtime for artifact in artifacts.values()), default=0.0)

        with self._lock:
            old_ids = set(self._artifacts)
            self._artifacts = artifacts
            self._campaigns = campaigns
            self._events = events
            self._last_scan_at = newest
        return {
            "artifact_count": len(artifacts),
            "campaign_count": len(campaigns),
            "new_artifact_ids": sorted(set(artifacts) - old_ids),
        }

    def all_artifacts(self) -> list[Artifact]:
        with self._lock:
            return sorted(self._artifacts.values(), key=lambda item: item.mtime, reverse=True)

    def get_artifact(self, artifact_id: str) -> Artifact | None:
        with self._lock:
            return self._artifacts.get(artifact_id)

    def campaigns(self) -> list[Campaign]:
        with self._lock:
            return sorted(self._campaigns.values(), key=lambda item: item.latest_event_at, reverse=True)

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        with self._lock:
            return self._campaigns.get(campaign_id)

    def timeline(self, limit: int = 300) -> list[Event]:
        with self._lock:
            return sorted(self._events, key=lambda item: item.timestamp, reverse=True)[:limit]

    def latest_by_type(
        self, artifact_type: str, *, campaign_id: str | None = None
    ) -> Artifact | None:
        with self._lock:
            matches = [
                a
                for a in self._artifacts.values()
                if a.type == artifact_type
                and (campaign_id is None or a.campaign_id == campaign_id)
            ]
        return max(matches, key=lambda item: item.mtime, default=None)

    def latest_by_type_semantic(
        self, artifact_type: str, *, campaign_id: str | None = None
    ) -> Artifact | None:
        with self._lock:
            matches = [
                a
                for a in self._artifacts.values()
                if a.type == artifact_type
                and (campaign_id is None or a.campaign_id == campaign_id)
            ]
        return max(matches, key=self._semantic_sort_key, default=None)

    def search(self, query: str, limit: int = 80) -> list[dict[str, Any]]:
        terms = [term.casefold() for term in query.split() if term.strip()]
        if not terms:
            return []
        results: list[dict[str, Any]] = []
        with self._lock:
            artifacts = list(self._artifacts.values())
            campaigns = list(self._campaigns.values())

        for campaign in campaigns:
            haystack = f"{campaign.id} {campaign.title} {campaign.summary or ''}".casefold()
            if all(term in haystack for term in terms):
                results.append({"kind": "campaign", "score": 100, "item": campaign.to_dict()})

        for artifact in artifacts:
            haystack = f"{artifact.path} {artifact.title} {artifact.type} {' '.join(artifact.tags)}".casefold()
            score = 0
            if all(term in haystack for term in terms):
                score += 50
            if artifact.type in {"report", "message", "decision", "metrics"} and artifact.size < 512_000:
                try:
                    text = self.config.resolve_repo_path(artifact.path).read_text(
                        encoding="utf-8", errors="replace"
                    ).casefold()
                except OSError:
                    text = ""
                if all(term in text for term in terms):
                    score += 25
            if score:
                results.append({"kind": "artifact", "score": score, "item": artifact.to_dict()})

        return sorted(results, key=lambda row: (row["score"], row["item"].get("mtime", 0)), reverse=True)[:limit]

    def dashboard(self, published_build: dict[str, Any] | None = None) -> dict[str, Any]:
        campaigns = self.campaigns()
        current = campaigns[0] if campaigns else None
        campaign_id = current.id if current is not None else None
        latest_decision = self.latest_by_type(
            "decision", campaign_id=campaign_id
        )
        return {
            "current_campaign": current.to_dict() if current else None,
            "current_epoch": self._latest_epoch(current) if current else None,
            "latest_report": self._dict_or_none(
                self.latest_by_type("report", campaign_id=campaign_id)
            ),
            "latest_mri": self._dict_or_none(
                self.latest_by_type("mri", campaign_id=campaign_id)
            ),
            "latest_graph": self._dict_or_none(
                self.latest_by_type_semantic("graph", campaign_id=campaign_id)
            ),
            "latest_atlas": self._dict_or_none(
                self.latest_by_type("atlas", campaign_id=campaign_id)
            ),
            "current_bottleneck": self._bottleneck_from_decision(latest_decision),
            "last_orchestrator_decision": self._dict_or_none(latest_decision),
            "current_published_chat_build": published_build,
            "running_jobs": [],
            "artifact_count": len(self.all_artifacts()),
            "campaign_count": len(campaigns),
            "last_scan_at": self.last_scan_at,
        }

    def _artifact_from_path(self, path: Path) -> Artifact:
        relative = path.relative_to(self.config.repo_root).as_posix()
        stat = path.stat()
        artifact_id = hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16]
        artifact_type, tags = self._classify(relative)
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if artifact_type == "report" or path.suffix.lower() == ".md":
            media_type = "text/markdown; charset=utf-8"
        title = self._title_from_path(path)
        return Artifact(
            id=artifact_id,
            path=relative,
            type=artifact_type,
            title=title,
            media_type=media_type,
            size=stat.st_size,
            mtime=stat.st_mtime,
            campaign_id=self._campaign_from(relative),
            epoch=self._epoch_from(path.name),
            tags=tags,
        )

    def _should_skip(self, path: Path) -> bool:
        try:
            parts = path.relative_to(self.config.repo_root).parts
        except ValueError:
            return True
        blocked = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}
        if any(part in blocked for part in parts):
            return True
        if path.name.startswith("."):
            return True
        return False

    def _classify(self, relative: str) -> tuple[str, list[str]]:
        lower = relative.casefold()
        suffix = Path(relative).suffix.casefold()
        tags: list[str] = []
        if "/lab/messages/" in f"/{lower}":
            return "message", ["message"]
        if suffix in {".pt", ".ckpt", ".safetensors"}:
            return "checkpoint", ["checkpoint"]
        if suffix == ".html":
            if "atlas" in lower:
                return "atlas", ["visualization", "html"]
            if "graph" in lower or "current_graph" in lower or "3d_map" in lower:
                return "graph", ["visualization", "html", "3d"]
            if "mri" in lower or "brain" in lower or "graph" in lower:
                return "mri", ["visualization", "html"]
            return "html", ["html"]
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            if any(hint in lower for hint in ("brain", "mri", "scatter", "similarity", "hubs", "nohubs")):
                return "mri", ["visualization", "image"]
            return "image", ["image"]
        if suffix == ".md":
            if any(hint in lower for hint in ("report", "summary", "manual_gate", "handoff", "prelaunch", "grounding")):
                return "report", ["markdown"]
            return "markdown", ["markdown"]
        if suffix == ".json":
            name = Path(relative).name.casefold()
            if name == "decision.json" or "decision" in name:
                return "decision", ["json"]
            if name == "metrics.json" or "metrics" in name or "results" in name:
                return "metrics", ["json"]
            if "trace" in name:
                return "trace", ["json"]
            if "hub" in name or "hubs" in name:
                return "hub", ["json"]
            return "json", ["json"]
        if suffix == ".jsonl":
            return "trace", ["jsonl"]
        if suffix == ".log":
            return "trace", ["log"]
        return "other", []

    def _build_campaigns(self, artifacts: Any) -> dict[str, Campaign]:
        grouped: dict[str, list[Artifact]] = defaultdict(list)
        for artifact in artifacts:
            if artifact.campaign_id:
                grouped[artifact.campaign_id].append(artifact)
        campaigns: dict[str, Campaign] = {}
        for campaign_id, items in grouped.items():
            latest = max((item.mtime for item in items), default=0.0)
            metadata = self._campaign_manifest(items)
            title = (
                str(metadata.get("display_name"))
                if metadata is not None and metadata.get("display_name")
                else f"Campaign {campaign_id.upper()}"
            )
            summary = (
                str(metadata.get("objective"))
                if metadata is not None and metadata.get("objective")
                else self._summary_for(items)
            )
            campaigns[campaign_id] = Campaign(
                id=campaign_id,
                title=title,
                artifacts=sorted(items, key=lambda item: item.mtime, reverse=True),
                latest_event_at=latest,
                summary=summary,
            )
        return campaigns

    def _campaign_manifest(self, items: list[Artifact]) -> dict[str, Any] | None:
        artifact = next(
            (
                item
                for item in items
                if Path(item.path).name == "00_manifest.json"
            ),
            None,
        )
        if artifact is None:
            return None
        try:
            value = json.loads(
                self.config.resolve_repo_path(artifact.path).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _build_events(self, artifacts: Any, campaigns: dict[str, Campaign]) -> list[Event]:
        events: list[Event] = []
        for campaign in campaigns.values():
            earliest = min((artifact.mtime for artifact in campaign.artifacts), default=campaign.latest_event_at)
            events.append(
                Event(
                    id=f"campaign-{campaign.id}-started",
                    timestamp=earliest,
                    kind="campaign_started",
                    title=f"{campaign.title} started",
                    campaign_id=campaign.id,
                    details={"artifact_count": len(campaign.artifacts)},
                )
            )
            epochs: dict[int, float] = {}
            for artifact in campaign.artifacts:
                if artifact.epoch is not None:
                    epochs[artifact.epoch] = min(epochs.get(artifact.epoch, artifact.mtime), artifact.mtime)
            for epoch, timestamp in epochs.items():
                events.append(
                    Event(
                        id=f"campaign-{campaign.id}-epoch-{epoch}",
                        timestamp=timestamp,
                        kind="epoch",
                        title=f"Epoch {epoch}",
                        campaign_id=campaign.id,
                        details={"epoch": epoch},
                    )
                )

        for artifact in artifacts:
            kind = {
                "report": "report",
                "mri": "mri",
                "graph": "graph",
                "atlas": "atlas",
                "checkpoint": "checkpoint",
                "decision": "decision",
                "message": "message",
            }.get(artifact.type, "artifact_detected")
            events.append(
                Event(
                    id=f"artifact-{artifact.id}",
                    timestamp=artifact.mtime,
                    kind=kind,
                    title=self._event_title(artifact),
                    campaign_id=artifact.campaign_id,
                    artifact_id=artifact.id,
                    details={"path": artifact.path, "type": artifact.type, "epoch": artifact.epoch},
                )
            )
        return sorted(events, key=lambda item: item.timestamp, reverse=True)

    def _event_title(self, artifact: Artifact) -> str:
        labels = {
            "report": "Report published",
            "mri": "MRI generated",
            "graph": "3D map generated",
            "atlas": "Atlas generated",
            "checkpoint": "Checkpoint published",
            "decision": "Decision recorded",
            "message": "Message received",
        }
        return f"{labels.get(artifact.type, 'Artifact detected')}: {artifact.title}"

    def _campaign_from(self, relative: str) -> str | None:
        for pattern in CAMPAIGN_PATTERNS:
            match = pattern.search(relative)
            if match:
                return match.group(1).lower()
        return None

    def _epoch_from(self, name: str) -> int | None:
        match = EPOCH_PATTERN.search(name)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _title_from_path(self, path: Path) -> str:
        stem = path.stem.replace("_", " ").replace("-", " ").strip()
        return " ".join(part.capitalize() if not part.startswith("c") else part.upper() for part in stem.split())

    def _summary_for(self, artifacts: list[Artifact]) -> str | None:
        reports = [artifact for artifact in artifacts if artifact.type == "report"]
        if not reports:
            return None
        latest = max(reports, key=lambda item: item.mtime)
        try:
            text = self.config.resolve_repo_path(latest.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return latest.title
        for line in text.splitlines():
            clean = line.strip(" #")
            if clean:
                return clean[:220]
        return latest.title

    def _latest_epoch(self, campaign: Campaign) -> int | None:
        epochs = [artifact.epoch for artifact in campaign.artifacts if artifact.epoch is not None]
        return max(epochs, default=None)

    def _bottleneck_from_decision(self, artifact: Artifact | None) -> str | None:
        if artifact is None or artifact.size > 512_000:
            return None
        try:
            data = json.loads(self.config.resolve_repo_path(artifact.path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        failure_modes = data.get("failure_modes")
        if isinstance(failure_modes, list):
            labels = [
                str(value).replace("_", " ").strip()
                for value in failure_modes
                if str(value).strip()
            ]
            if labels:
                return " · ".join(labels)[:240]
        for key in ("reasoning_summary", "recommended_next_intervention", "status"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:240]
        return None

    def _dict_or_none(self, artifact: Artifact | None) -> dict[str, Any] | None:
        return artifact.to_dict() if artifact else None

    def _semantic_sort_key(self, artifact: Artifact) -> tuple[int, str, int, float]:
        numeric_campaign = -1
        campaign_suffix = artifact.campaign_id or ""
        if artifact.campaign_id:
            match = re.match(r"(\d+)(.*)", artifact.campaign_id)
            if match:
                numeric_campaign = int(match.group(1))
                campaign_suffix = match.group(2)
        return (numeric_campaign, campaign_suffix, artifact.epoch if artifact.epoch is not None else -1, artifact.mtime)
