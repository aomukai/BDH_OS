"""Disabled-by-config Cortex subprocess handlers for later commissioning."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from ..errors import ProtocolError, SafetyError


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(context: dict[str, Any], artifact_id: str | None) -> dict[str, Any] | None:
    if artifact_id is None:
        return None
    for artifact in context["artifacts"]:
        if artifact["id"] == artifact_id:
            path = Path(artifact["uri"]).resolve()
            roots = [Path(context["state_root"]).resolve(), *(Path(value).resolve() for value in context["artifact_roots"])]
            if not any(path == root or root in path.parents for root in roots):
                raise SafetyError(f"artifact path is outside configured roots: {artifact_id}")
            if not path.is_file():
                raise SafetyError(f"artifact is not a file on this machine: {artifact_id}")
            if _sha256(path) != artifact["sha256"]:
                raise SafetyError(f"artifact content hash mismatch: {artifact_id}")
            return artifact
    raise ProtocolError(f"job did not receive artifact reference: {artifact_id}")


def _runtime(context: dict[str, Any]) -> tuple[Path, dict[str, str], Path]:
    release_root = Path(context["release_root"]).resolve()
    executable = Path(sys.executable).resolve()
    environment = dict(os.environ)
    deployment_environment = context["deployment_environment"]
    site_paths = deployment_environment.get("python_site_paths", [])
    python_path = [str(release_root), *site_paths]
    if environment.get("PYTHONPATH"):
        python_path.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_path)
    run_root = Path(context["state_root"]) / "runs" / context["run"]["id"]
    run_root.mkdir(parents=True, exist_ok=False)
    return executable, environment, run_root


def _execute(command: list[str], *, environment: dict[str, str], timeout: int, log_path: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=timeout, check=False)
    log_path.write_text(
        json.dumps(
            {"command": command, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Cortex subprocess failed with exit code {completed.returncode}; evidence: {log_path}")
    return completed


def _artifact_output(kind: str, path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "sha256": _sha256(path),
        "byte_size": path.stat().st_size,
        "uri": str(path),
        "lifecycle": "candidate",
        "manifest": manifest,
    }


class CortexTrainHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        corpus = _artifact(context, payload["corpus_artifact_id"])
        parent = _artifact(context, payload["parent_artifact_id"])
        executable, environment, run_root = _runtime(context)
        checkpoint = run_root / "candidate.pt"
        log_path = run_root / "training.json"
        parameters = payload["parameters"]
        command = [
            str(executable), str(Path(context["release_root"]) / "meta/scripts/train_cortex.py"),
            "--jsonl", corpus["uri"], "--output", str(checkpoint),
            "--parent", parent["uri"] if parent else "scratch",
            "--epochs", str(parameters["epochs"]), "--batch-size", str(parameters["batch_size"]),
            "--max-examples", str(parameters["max_examples"]), "--lr", str(parameters["learning_rate"]),
            "--weight-decay", str(parameters["weight_decay"]), "--seed", str(parameters["seed"]),
            "--ingress-device", parameters["ingress_device"], "--core-device", parameters["core_device"],
            "--train-scope", parameters["train_scope"], "--rms-clip", str(parameters["rms_clip"]),
            "--probe-max-new-tokens", str(parameters["probe_max_new_tokens"]),
            "--source-concept", parameters["source_concept"],
        ]
        if parameters["stochastic_rounding"]:
            command.append("--stochastic-rounding")
        if parameters["local_files_only"]:
            command.append("--local-files-only")
        completed = _execute(command, environment=environment, timeout=context["timeout_seconds"], log_path=log_path)
        report = run_root / "training-report.json"
        report.write_text(completed.stdout.strip() + "\n", encoding="utf-8")
        return {
            "status": "succeeded",
            "metrics": {},
            "failure": None,
            "artifacts": [
                _artifact_output("checkpoint", checkpoint, {"architecture": payload["architecture"], "parent_artifact_id": payload["parent_artifact_id"], "corpus_artifact_id": payload["corpus_artifact_id"]}),
                _artifact_output("training_report", report, {"run_id": context["run"]["id"]}),
                _artifact_output("log", log_path, {"run_id": context["run"]["id"]}),
            ],
        }


class CortexEvaluateHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        candidate = _artifact(context, payload["candidate_artifact_id"])
        parent = _artifact(context, payload.get("parent_artifact_id"))
        suite = _artifact(context, payload["suite_artifact_id"])
        if parent is None:
            raise SafetyError("Cortex evaluation requires an explicit parent artifact")
        executable, environment, run_root = _runtime(context)
        report = run_root / "evaluation.json"
        log_path = run_root / "evaluation-log.json"
        parameters = payload["parameters"]
        command = [
            str(executable), str(Path(context["release_root"]) / "meta/scripts/evaluate_cortex.py"),
            "--candidate", candidate["uri"], "--parent", parent["uri"], "--suite", suite["uri"],
            "--campaign-id", payload.get("campaign_id", "uncampaigned"),
            "--development-stage", payload["development_stage"],
            "--ingress-device", parameters["ingress_device"], "--core-device", parameters["core_device"],
            "--max-new-tokens", str(parameters["max_new_tokens"]), "--output", str(report),
        ]
        _execute(command, environment=environment, timeout=context["timeout_seconds"], log_path=log_path)
        return {
            "status": "succeeded",
            "metrics": {},
            "failure": None,
            "artifacts": [
                _artifact_output("evaluation_report", report, {"candidate_artifact_id": payload["candidate_artifact_id"], "suite_artifact_id": payload["suite_artifact_id"]}),
                _artifact_output("log", log_path, {"run_id": context["run"]["id"]}),
            ],
        }
