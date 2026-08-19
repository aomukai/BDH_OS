from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from mission_hub.config import load_config_bundle
from mission_hub.handlers.visual_train import VisualProjectorTrainHandler
from mission_hub.lesson_policy import policy_sha256


REPO = Path(__file__).resolve().parents[1]


def artifact(tmp_path: Path, artifact_id: str, kind: str, payload: bytes, manifest: dict) -> dict:
    path = tmp_path / artifact_id
    path.write_bytes(payload)
    return {"id": artifact_id, "kind": kind, "uri": str(path), "sha256": hashlib.sha256(payload).hexdigest(), "byte_size": len(payload), "manifest": manifest}


def test_visual_training_boundary_is_projector_only_and_bounded(tmp_path: Path, monkeypatch) -> None:
    identity_policy = load_config_bundle(REPO / "config/mission_hub").identity_policy
    digest_a, digest_b = "a" * 64, "b" * 64
    base_bytes = b"base"
    experience_bytes = json.dumps({"events": []}).encode()
    artifacts = [
        artifact(tmp_path, "base.pt", "checkpoint", base_bytes, {}),
        artifact(tmp_path, "features.npz", "visual_features", b"features", {"asset_sha256": [digest_a, digest_b]}),
        artifact(tmp_path, "experience.json", "visual_experience", experience_bytes, {}),
        artifact(tmp_path, "order.json", "validation_report", b"validated", {
            "schema_version": "ninereeds_dependency_order_validation_v1",
            "validation_scope": "dependency_order", "status": "passed",
            "subject_artifact_id": "experience.json",
            "subject_sha256": hashlib.sha256(experience_bytes).hexdigest(),
            "parent_artifact_id": "base.pt",
            "parent_sha256": hashlib.sha256(base_bytes).hexdigest(),
            "order_policy": "declared_only", "shuffle_allowed": False,
            "dependency_order_required": True, "dependency_evidence_sha256": "c" * 64,
            "lesson_policy_status": "passed", "lesson_policy_id": identity_policy["id"],
            "lesson_policy_version": identity_policy["version"],
            "lesson_policy_sha256": policy_sha256(identity_policy), "identity_scope": "excluded",
        }),
    ]
    def run(command, **kwargs):
        Path(command[command.index("--output-projector") + 1]).write_bytes(b"projector")
        Path(command[command.index("--output-report") + 1]).write_text(json.dumps({"schema_version": "report-v1"}), encoding="utf-8")
        Path(command[command.index("--output-observer") + 1]).write_text(json.dumps({"schema_version": "ninereeds_gate_credit_diagnostics_v1"}), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")
    monkeypatch.setattr("mission_hub.handlers.visual_train.subprocess.run", run)
    payload = {
        "input_artifact_ids": ["base.pt", "features.npz", "experience.json", "order.json"],
        "training_session": {"id": "visual-session", "campaign_contract_sha256": "d" * 64, "training_mode": "advancement", "branch_id": None, "identity_scope": "excluded", "ordered_concepts": [{"concept": "red ball", "depends_on": []}]},
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
        "training_policy": {
            "order_policy": "declared_only", "shuffle_allowed": False, "dependency_order_required": True,
            "observer_fixture": {"id": "gate-credit-v1", "version": 1, "required": True, "log_every_n_steps": 50, "max_sampled_steps": 64},
        },
        "identity_policy": identity_policy,
    })
    assert result["stage"] == "model.visual_train"
    assert result["metrics"]["exposures"] == 2
    assert {item["kind"] for item in result["artifacts"]} == {"checkpoint", "training_report", "gate_credit_report", "log"}
