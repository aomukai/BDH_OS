"""Deterministic root initialization and architecture-specific merge jobs."""

from __future__ import annotations

from pathlib import Path

from ..errors import SafetyError
from .cortex import _artifact_output, _cortex_command, _execute, _runtime
from .visual import _verified_inputs


class CortexInitializeHandler:
    def execute(self, payload, context):
        executable, environment, root = _runtime(context)
        checkpoint, report, log = root / "neutral-root.pt", root / "initialization-report.json", root / "initialization-log.json"
        command = [*_cortex_command(executable, context, "meta/scripts/initialize_cortex.py"), "--output", str(checkpoint), "--report", str(report), "--seed", str(payload["seed"])]
        if payload["local_files_only"]:
            command.append("--local-files-only")
        _execute(command, environment=environment, timeout=context["timeout_seconds"], log_path=log)
        manifest = {"schema_version": "ninereeds_neutral_root_artifact_v1", "seed": payload["seed"], "training_events": 0, "weight_updates": 0}
        return {"status": "succeeded", "metrics": {"seed": payload["seed"]}, "artifacts": [_artifact_output("checkpoint", checkpoint, manifest), _artifact_output("initialization_report", report, manifest), _artifact_output("log", log, {"stage": "model.initialize"})], "failure": None}


class CortexMergeHandler:
    def execute(self, payload, context):
        inputs = _verified_inputs(context, payload["input_artifact_ids"])
        checkpoints = [item for item in inputs if item["kind"] == "checkpoint"]
        if len(checkpoints) != 2 or len(inputs) != 2:
            raise SafetyError("model.merge requires exactly two checkpoint artifacts")
        by_id = {item["id"]: item for item in checkpoints}
        if set(by_id) != set(payload["input_artifact_ids"]):
            raise SafetyError("merge source identity changed")
        left, right = (by_id[item] for item in payload["input_artifact_ids"])
        executable, environment, root = _runtime(context)
        checkpoint, report, log = root / "merged.pt", root / "merge-report.json", root / "merge-log.json"
        command = [*_cortex_command(executable, context, "meta/scripts/merge_cortex.py"), "--left", left["uri"], "--right", right["uri"], "--output", str(checkpoint), "--report", str(report)]
        _execute(command, environment=environment, timeout=context["timeout_seconds"], log_path=log)
        manifest = {"schema_version": "ninereeds_merge_artifact_v1", "campaign_id": context["campaign_id"], "branch_id": payload["output_branch_id"], "left_artifact_id": left["id"], "right_artifact_id": right["id"], "merge_policy": payload["merge_policy"]}
        return {"status": "succeeded", "metrics": {"sources": 2}, "artifacts": [_artifact_output("checkpoint", checkpoint, manifest), _artifact_output("merge_report", report, manifest), _artifact_output("log", log, {"stage": "model.merge"})], "failure": None}
