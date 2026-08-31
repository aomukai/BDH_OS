"""Full-Cortex ordered visual and joint training boundary."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any

from ..errors import RemoteJobError, SafetyError
from ..lesson_policy import policy_sha256
from ..training_order import require_dependency_order
from .cortex import _cortex_command, _runtime
from .visual import _local_runtime_failure, _runtime_declaration, _verified_inputs


class MultimodalCortexTrainHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        inputs = _verified_inputs(context, payload["input_artifact_ids"])
        by_kind: dict[str, list[dict[str, Any]]] = {}
        for item in inputs:
            by_kind.setdefault(item["kind"], []).append(item)
        required = {"checkpoint", "visual_features", "visual_experience", "validation_report"}
        if set(by_kind) != required or any(len(by_kind[kind]) != 1 for kind in required):
            raise SafetyError("multimodal training requires one checkpoint, feature archive, experience, and order validation")
        require_dependency_order(
            by_kind["visual_experience"][0], by_kind["validation_report"][0],
            context["training_policy"], parent=by_kind["checkpoint"][0],
            identity_policy=context["identity_policy"],
            identity_scope=payload["training_session"]["identity_scope"],
        )
        certificate = by_kind["validation_report"][0]["manifest"]
        if certificate.get("session_plan_sha256") is None:
            raise SafetyError("multimodal order certificate lacks its immutable session binding")
        events = payload["specification"]["events"]
        if len(events) * payload["specification"]["parameters"]["epochs"] > payload["limits"]["max_exposures"]:
            raise SafetyError("multimodal training exceeds its exposure ceiling")
        fixture = context["training_policy"]["observer_fixture"]
        if not fixture["required"]:
            raise SafetyError("multimodal training requires the observer fixture")

        checkpoint = by_kind["checkpoint"][0]
        features = by_kind["visual_features"][0]
        experience = by_kind["visual_experience"][0]
        session = payload["training_session"]
        executable, environment, run_root = _runtime(context)
        request_path = run_root / "multimodal-train-request.json"
        request_path.write_text(json.dumps({
            "schema_version": "ninereeds_multimodal_train_request_v1",
            "campaign_id": context["campaign_id"], "branch_id": session["branch_id"],
            "campaign_contract_sha256": session["campaign_contract_sha256"],
            "identity_policy_sha256": policy_sha256(context["identity_policy"]),
            "identity_scope": session["identity_scope"],
            "order_policy": "declared_only", "shuffle_allowed": False,
            "mode": payload["specification"]["mode"],
            "events": events, "parameters": payload["specification"]["parameters"],
            "observer_fixture": fixture,
            "parent_checkpoint": checkpoint["uri"], "parent_sha256": checkpoint["sha256"],
            "visual_features": features["uri"], "visual_features_sha256": features["sha256"],
            "visual_experience_sha256": experience["sha256"],
        }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        output = run_root / "multimodal-cortex.pt"
        report = run_root / "multimodal-training-report.json"
        observer = run_root / "gate-credit.json"
        log = run_root / "multimodal-training-log.json"
        command = [
            *_cortex_command(executable, context, "meta/scripts/train_multimodal_cortex.py"),
            "--request", str(request_path), "--output", str(output),
            "--output-report", str(report), "--output-observer", str(observer),
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, env=environment,
                timeout=context["timeout_seconds"], check=False,
            )
        except subprocess.TimeoutExpired as exc:
            log.write_text(json.dumps({"command": command, "timeout": True, "stdout": exc.stdout, "stderr": exc.stderr}, default=str, indent=2) + "\n", encoding="utf-8")
            raise RemoteJobError(
                f"multimodal training timed out; evidence: {log}",
                failure_class="operational_transient", code="process_interrupted",
                evidence={"log": str(log)},
            ) from exc
        log.write_text(json.dumps({
            "command": command, "returncode": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr,
        }, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if completed.returncode != 0 or not all(path.is_file() for path in (output, report, observer)):
            failure_class, failure_code = _local_runtime_failure(
                completed.returncode, completed.stderr,
            )
            raise RemoteJobError(
                f"multimodal training failed; evidence: {log}",
                failure_class=failure_class or "deterministic_specification",
                code=failure_code, evidence={"log": str(log)},
            )
        manifest = {
            "training_scope": "full_cortex", "modality": payload["specification"]["mode"],
            "parent_checkpoint_artifact_id": checkpoint["id"],
            "visual_features_artifact_id": features["id"],
            "visual_experience_artifact_id": experience["id"],
            "event_count": len(events), "branch_id": session["branch_id"],
            "observer_fixture_id": fixture["id"], "observer_fixture_version": fixture["version"],
        }
        return {
            "status": "succeeded", "stage": "model.multimodal_train",
            "metrics": {"events": len(events), "mode": payload["specification"]["mode"]},
            "artifacts": [
                _runtime_declaration("checkpoint", output, manifest),
                _runtime_declaration("training_report", report, manifest),
                _runtime_declaration("gate_credit_report", observer, {**manifest, "loss_role": "telemetry_only"}),
                _runtime_declaration("log", log, {"run_id": context["run"]["id"], "stage": "model.multimodal_train"}),
            ],
            "failure": None,
        }
