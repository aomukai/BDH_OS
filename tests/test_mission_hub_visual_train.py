from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from mission_hub.handlers.visual_train import VisualProjectorTrainHandler


def artifact(tmp_path: Path, artifact_id: str, kind: str, payload: bytes, manifest: dict) -> dict:
    path = tmp_path / artifact_id
    path.write_bytes(payload)
    return {"id": artifact_id, "kind": kind, "uri": str(path), "sha256": hashlib.sha256(payload).hexdigest(), "byte_size": len(payload), "manifest": manifest}


def test_visual_training_boundary_is_projector_only_and_bounded(tmp_path: Path, monkeypatch) -> None:
    digest_a, digest_b = "a" * 64, "b" * 64
    artifacts = [
        artifact(tmp_path, "base.pt", "checkpoint", b"base", {}),
        artifact(tmp_path, "features.npz", "visual_features", b"features", {"asset_sha256": [digest_a, digest_b]}),
        artifact(tmp_path, "experience.json", "visual_experience", json.dumps({"events": []}).encode(), {}),
    ]
    def run(command, **kwargs):
        Path(command[command.index("--output-projector") + 1]).write_bytes(b"projector")
        Path(command[command.index("--output-report") + 1]).write_text(json.dumps({"schema_version": "report-v1"}), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")
    monkeypatch.setattr("mission_hub.handlers.visual_train.subprocess.run", run)
    payload = {
        "input_artifact_ids": ["base.pt", "features.npz", "experience.json"],
        "specification": {
            "training_scope": "projector_only", "epochs": 2, "batch_size": 1,
            "learning_rate": 0.001, "weight_decay": 0.01, "seed": 7,
            "pairs": [
                {"asset_sha256": digest_a, "text": "a red ball", "split": "train"},
                {"asset_sha256": digest_b, "text": "a blue ball", "split": "validation"},
            ],
        },
        "limits": {"max_exposures": 2},
    }
    result = VisualProjectorTrainHandler().execute(payload, {
        "state_root": str(tmp_path / "state"), "artifact_roots": [str(tmp_path)], "artifacts": artifacts,
        "run": {"id": "run-train"}, "release_root": str(tmp_path), "deployment_environment": {}, "timeout_seconds": 60,
    })
    assert result["stage"] == "model.visual_train"
    assert result["metrics"]["exposures"] == 2
    assert {item["kind"] for item in result["artifacts"]} == {"checkpoint", "training_report", "log"}
