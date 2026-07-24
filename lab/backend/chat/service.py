from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from lab.backend.artifacts.indexer import ArtifactIndex
from lab.backend.config import LabConfig
from lab.backend.models import PublishedBuild


class ChatService:
    def __init__(self, config: LabConfig, index: ArtifactIndex) -> None:
        self.config = config
        self.index = index
        self.state_path = config.state_dir / "published_build.json"

    def current_build(self) -> dict[str, Any] | None:
        if not self.state_path.exists():
            return None
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def builds(self) -> list[dict[str, Any]]:
        checkpoints = [artifact for artifact in self.index.all_artifacts() if artifact.type == "checkpoint"]
        builds: list[dict[str, Any]] = []
        for artifact in checkpoints:
            label = artifact.title
            if "winner" in artifact.path.casefold():
                label = f"Latest Winner: {artifact.title}"
            builds.append(
                {
                    "id": artifact.id,
                    "label": label,
                    "checkpoint_artifact_id": artifact.id,
                    "path": artifact.path,
                    "mtime": artifact.mtime,
                    "campaign_id": artifact.campaign_id,
                    "epoch": artifact.epoch,
                }
            )
        return builds

    def publish(self, checkpoint_artifact_id: str, label: str | None = None) -> dict[str, Any]:
        artifact = self.index.get_artifact(checkpoint_artifact_id)
        if artifact is None or artifact.type != "checkpoint":
            raise ValueError("checkpoint artifact not found")
        published = PublishedBuild(
            id=f"build-{checkpoint_artifact_id}",
            label=label or artifact.title,
            checkpoint_artifact_id=artifact.id,
            path=artifact.path,
            published_at=time.time(),
        )
        data = published.to_dict()
        self.state_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        pointer = self.config.published_dir / "current.json"
        pointer.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return data

    def chat_ninereeds(self, prompt: str) -> dict[str, Any]:
        build = self.current_build()
        if build is None:
            return {
                "mode": "ninereeds",
                "ok": False,
                "reply": "No checkpoint is published for chat.",
                "build": None,
            }
        return {
            "mode": "ninereeds",
            "ok": True,
            "build": build,
            "reply": (
                "Ninereeds checkpoint selected, but local inference is not enabled in this "
                "Lab build. The checkpoint was not loaded and no GPU resources were used."
            ),
            "echo": prompt,
        }
