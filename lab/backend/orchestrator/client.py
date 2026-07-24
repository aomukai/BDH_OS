from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from lab.backend.artifacts.indexer import ArtifactIndex
from lab.backend.config import LabConfig


class OrchestratorClient:
    def __init__(self, config: LabConfig, index: ArtifactIndex) -> None:
        self.config = config
        self.index = index

    def chat(self, prompt: str) -> dict[str, Any]:
        context = self._context()
        if not self.config.orchestrator_url:
            return {
                "mode": "orchestrator",
                "ok": False,
                "reply": "Remote orchestrator API is not configured. Set LAB_ORCHESTRATOR_URL.",
                "context": context,
            }
        payload = json.dumps({"prompt": prompt, "context": context}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.config.orchestrator_api_key:
            headers["Authorization"] = f"Bearer {self.config.orchestrator_api_key}"
        request = urllib.request.Request(self.config.orchestrator_url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            return {"mode": "orchestrator", "ok": False, "reply": str(exc), "context": context}
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {"reply": body}
        return {"mode": "orchestrator", "ok": True, "response": data, "context": context}

    def _context(self) -> dict[str, Any]:
        timeline = [event.to_dict() for event in self.index.timeline(limit=20)]
        dashboard = self.index.dashboard()
        reports = [artifact.to_dict() for artifact in self.index.all_artifacts() if artifact.type == "report"][:10]
        return {
            "dashboard": dashboard,
            "recent_timeline": timeline,
            "recent_reports": reports,
        }
