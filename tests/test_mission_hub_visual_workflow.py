from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.errors import SafetyError
from mission_hub.store import MissionHubStore
from mission_hub.visual_workflow import VisualWorkflowCoordinator


REPO = Path(__file__).resolve().parents[1]


def test_visual_workflow_cannot_start_while_execution_is_locked(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    with pytest.raises(SafetyError, match="complete visual workflow"):
        store.create_visual_workflow(
            bundle,
            {"plan": {"goal": "one object"}, "experience_events": [{"type": "page_turn"}], "limits": {}},
            actor="test",
        )


def test_visual_stage_pacing_is_anchored_to_predecessor_completion() -> None:
    coordinator = VisualWorkflowCoordinator.__new__(VisualWorkflowCoordinator)
    coordinator.bundle = SimpleNamespace(visual={"stage_cooldown_seconds": 900})
    captured = {}

    def create(workflow, key, job_type, artifact_ids, specification, available_at, actor):
        captured.update({"available_at": available_at, "key": key})
        return {"status": "queued", "stage": key}

    coordinator._create = create
    predecessor = ({}, [], "2026-08-06T01:02:03.000000Z")
    coordinator._next({"id": "visual-test"}, "generate", "visual.generate", [], predecessor, "test")
    assert captured == {"available_at": "2026-08-06T01:17:03.000000Z", "key": "generate"}
