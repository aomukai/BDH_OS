"""Read-only cross-modal Cortex evaluation boundary."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from ..errors import SafetyError
from .cortex import _artifact_output, _cortex_command, _runtime
from .visual import _verified_inputs


class MultimodalCortexEvaluateHandler:
    def execute(self, payload, context):
        inputs = _verified_inputs(context, payload["input_artifact_ids"])
        by_kind = {item["kind"]: item for item in inputs}
        if set(by_kind) != {"checkpoint", "visual_features", "visual_experience"} or len(inputs) != 3:
            raise SafetyError("cross-modal evaluation requires one checkpoint, feature archive, and experience ledger")
        checkpoint, features, experience = (by_kind[kind] for kind in ("checkpoint", "visual_features", "visual_experience"))
        executable, environment, run_root = _runtime(context)
        report, log = run_root / "crossmodal-evaluation.json", run_root / "crossmodal-evaluation-log.json"
        parameters = payload["parameters"]
        command = [
            *_cortex_command(executable, context, "meta/scripts/evaluate_multimodal_cortex.py"),
            "--checkpoint", checkpoint["uri"], "--features", features["uri"], "--experience", experience["uri"],
            "--checkpoint-sha256", checkpoint["sha256"], "--features-sha256", features["sha256"], "--experience-sha256", experience["sha256"],
            "--campaign-id", context["campaign_id"], "--branch-id", payload["branch_id"],
            "--ingress-device", parameters["ingress_device"], "--core-device", parameters["core_device"],
            "--max-new-tokens", str(parameters["max_new_tokens"]), "--output", str(report),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=context["timeout_seconds"], check=False)
        log.write_text(json.dumps({"command": command, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if completed.returncode or not report.is_file():
            raise RuntimeError(f"cross-modal evaluation failed; evidence: {log}")
        value = json.loads(report.read_text(encoding="utf-8"))
        if value.get("schema_version") != "ninereeds_crossmodal_evaluation_v1" or value.get("checkpoint_sha256") != checkpoint["sha256"] or value.get("branch_id") != payload["branch_id"]:
            raise RuntimeError("cross-modal evaluator returned evidence for the wrong checkpoint or branch")
        manifest = {"branch_id": payload["branch_id"], "checkpoint_artifact_id": checkpoint["id"], "checkpoint_sha256": checkpoint["sha256"], "evaluation_basis": ["image_to_text", "cross_modal_retrieval"], "loss_role": "telemetry_only"}
        return {"status": "succeeded", "metrics": {"visual_adapter_present": value["visual_adapter_present"], "retrieval_accuracy": value["retrieval"]["accuracy"]}, "failure": None, "artifacts": [_artifact_output("crossmodal_evaluation_report", report, manifest), _artifact_output("log", log, {"run_id": context["run"]["id"]})]}
