"""Bounded projector-only visual training boundary."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from ..errors import SafetyError
from ..lesson_policy import policy_sha256
from ..training_order import require_dependency_order
from .visual import _runtime_declaration, _verified_inputs


class VisualProjectorTrainHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if payload["specification"]["training_scope"] != "projector_only":
            raise SafetyError("initial visual training is restricted to projector_only")
        inputs = _verified_inputs(context, payload["input_artifact_ids"])
        by_kind: dict[str, list[dict[str, Any]]] = {}
        for item in inputs:
            by_kind.setdefault(item["kind"], []).append(item)
        if len(by_kind.get("checkpoint", [])) != 1 or len(by_kind.get("visual_features", [])) != 1 or len(by_kind.get("visual_experience", [])) != 1 or len(by_kind.get("validation_report", [])) != 1:
            raise SafetyError("visual projector training requires one checkpoint, visual-features artifact, visual experience, and dependency-order validation")
        require_dependency_order(
            by_kind["visual_experience"][0], by_kind["validation_report"][0],
            context["training_policy"], parent=by_kind["checkpoint"][0],
            identity_policy=context["identity_policy"],
            identity_scope=payload["training_session"]["identity_scope"],
        )
        spec = payload["specification"]
        train_count = sum(pair["split"] == "train" for pair in spec["pairs"])
        validation_count = sum(pair["split"] == "validation" for pair in spec["pairs"])
        exposures = train_count * spec["epochs"]
        if train_count < 1 or validation_count < 1:
            raise SafetyError("visual training requires explicit train and validation pairs")
        if exposures > payload["limits"]["max_exposures"]:
            raise SafetyError("visual training exceeds its exposure bound")
        run_root = Path(context["state_root"]).resolve() / "runs" / context["run"]["id"]
        run_root.mkdir(parents=True, exist_ok=False)
        request_path = run_root / "visual-train-request.json"
        request_path.write_text(json.dumps({
            "schema_version": "ninereeds_visual_projector_train_request_v1",
            "training_policy": context["training_policy"],
            "identity_policy_sha256": policy_sha256(context["identity_policy"]),
            "identity_scope": payload["training_session"]["identity_scope"],
            "campaign_contract_sha256": payload["training_session"]["campaign_contract_sha256"],
            "training_mode": payload["training_session"]["training_mode"],
            "branch_id": payload["training_session"]["branch_id"],
            "base_checkpoint": by_kind["checkpoint"][0], "visual_features": by_kind["visual_features"][0],
            "visual_experience": by_kind["visual_experience"][0], "specification": spec,
            "limits": payload["limits"],
        }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        checkpoint = run_root / "visual-projector.pt"
        report = run_root / "visual-training-report.json"
        log_path = run_root / "visual-training-log.json"
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join([
            str(Path(context["release_root"]).resolve()),
            *context["deployment_environment"].get("python_site_paths", []),
        ])
        command = [
            str(Path(sys.executable).resolve()),
            str(Path(context["release_root"]) / "meta/scripts/train_visual_projector.py"),
            "--request", str(request_path), "--output-projector", str(checkpoint),
            "--output-report", str(report),
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, env=environment,
                timeout=context["timeout_seconds"], check=False,
            )
        except subprocess.TimeoutExpired as exc:
            log_path.write_text(json.dumps({"command": command, "timeout": True, "stdout": exc.stdout, "stderr": exc.stderr}, default=str, indent=2) + "\n", encoding="utf-8")
            raise RuntimeError(f"visual training timed out; evidence: {log_path}") from exc
        log_path.write_text(json.dumps({
            "command": command, "returncode": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr,
        }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if completed.returncode != 0 or not checkpoint.is_file() or not report.is_file():
            raise RuntimeError(f"visual projector training failed; evidence: {log_path}")
        report_doc = json.loads(report.read_text(encoding="utf-8"))
        manifest = {
            "training_scope": "projector_only", "base_checkpoint_artifact_id": by_kind["checkpoint"][0]["id"],
            "visual_features_artifact_id": by_kind["visual_features"][0]["id"],
            "visual_experience_artifact_id": by_kind["visual_experience"][0]["id"],
            "epochs": spec["epochs"], "exposures": exposures, "seed": spec["seed"],
            "language_core_frozen": True, "report_schema": report_doc.get("schema_version"),
        }
        return {
            "status": "succeeded", "stage": "model.visual_train",
            "metrics": {"epochs": spec["epochs"], "exposures": exposures, "train_pairs": train_count, "validation_pairs": validation_count},
            "artifacts": [
                _runtime_declaration("checkpoint", checkpoint, manifest),
                _runtime_declaration("training_report", report, manifest),
                _runtime_declaration("log", log_path, {"run_id": context["run"]["id"], "stage": "model.visual_train"}),
            ],
            "failure": None,
        }
