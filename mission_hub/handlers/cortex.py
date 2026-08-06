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
from ..jsonutil import content_hash
from ..lesson_policy import policy_sha256, require_lesson_material
from ..training_order import require_dependency_order


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
        order_validation = _artifact(context, payload["order_validation_artifact_id"])
        require_dependency_order(
            corpus, order_validation, context["training_policy"], parent=parent,
            identity_policy=context["identity_policy"],
            identity_scope=payload["training_session"]["identity_scope"],
        )
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
            "--order-policy", "declared_only",
            "--identity-policy-sha256", policy_sha256(context["identity_policy"]),
            "--identity-scope", payload["training_session"]["identity_scope"],
            "--campaign-contract-sha256", payload["training_session"]["campaign_contract_sha256"],
            "--training-mode", payload["training_session"]["training_mode"],
            "--branch-id", payload["training_session"]["branch_id"] or "unbranched",
        ]
        if parameters["stochastic_rounding"]:
            command.append("--stochastic-rounding")
        if parameters["local_files_only"]:
            command.append("--local-files-only")
        completed = _execute(command, environment=environment, timeout=context["timeout_seconds"], log_path=log_path)
        report = run_root / "training-report.json"
        try:
            training_report = json.loads(completed.stdout)
            metadata = training_report["metadata"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError("Cortex trainer returned an invalid training report") from exc
        optimizer = metadata.get("optimizer", {})
        expected = {
            "architecture": payload["architecture"],
            "examples": parameters["max_examples"],
            "epochs": parameters["epochs"],
            "batch_size": parameters["batch_size"],
            "lr": parameters["learning_rate"],
            "seed": parameters["seed"],
            "train_scope": parameters["train_scope"],
            "order_policy": "declared_only",
            "shuffle_allowed": False,
            "identity_policy_sha256": policy_sha256(context["identity_policy"]),
            "campaign_contract_sha256": payload["training_session"]["campaign_contract_sha256"],
            "training_mode": payload["training_session"]["training_mode"],
            "branch_id": payload["training_session"]["branch_id"],
            "identity_scope": payload["training_session"]["identity_scope"],
        }
        if any(metadata.get(key) != value for key, value in expected.items()):
            raise RuntimeError("Cortex training report does not match the commissioned session contract")
        if any((
            optimizer.get("rms_clip") != parameters["rms_clip"],
            optimizer.get("stochastic_rounding") != parameters["stochastic_rounding"],
            optimizer.get("weight_decay") != parameters["weight_decay"],
        )):
            raise RuntimeError("effective optimizer policy does not match the commissioned recipe")
        report.write_text(
            json.dumps(training_report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "status": "succeeded",
            "metrics": {},
            "failure": None,
            "artifacts": [
                _artifact_output("checkpoint", checkpoint, {
                    "architecture": payload["architecture"],
                    "parent_artifact_id": payload["parent_artifact_id"],
                    "corpus_artifact_id": payload["corpus_artifact_id"],
                    "campaign_contract_sha256": payload["training_session"]["campaign_contract_sha256"],
                    "training_mode": payload["training_session"]["training_mode"],
                    "branch_id": payload["training_session"]["branch_id"],
                    "session_id": payload["training_session"]["id"],
                    "order_validation_artifact_id": payload["order_validation_artifact_id"],
                }),
                _artifact_output("training_report", report, {
                    "run_id": context["run"]["id"],
                    "campaign_contract_sha256": payload["training_session"]["campaign_contract_sha256"],
                    "branch_id": payload["training_session"]["branch_id"],
                    "session_id": payload["training_session"]["id"],
                }),
                _artifact_output("log", log_path, {"run_id": context["run"]["id"]}),
            ],
        }


class CortexCheckpointProbeHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        checkpoint = _artifact(context, payload["checkpoint_artifact_id"])
        if checkpoint is None:
            raise SafetyError("checkpoint probe requires one checkpoint")
        executable, environment, run_root = _runtime(context)
        report = run_root / "checkpoint-probe.json"
        log_path = run_root / "checkpoint-probe-log.json"
        command = [
            str(executable),
            str(Path(context["release_root"]) / "meta/scripts/probe_cortex_checkpoint.py"),
            checkpoint["uri"],
            "--ingress-device", payload["ingress_device"],
            "--core-device", payload["core_device"],
        ]
        if payload["local_files_only"]:
            command.append("--local-files-only")
        completed = _execute(
            command, environment=environment,
            timeout=context["timeout_seconds"], log_path=log_path,
        )
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("checkpoint probe returned invalid JSON") from exc
        result.update({
            "schema_version": "ninereeds_cortex_checkpoint_probe_v2",
            "checkpoint_artifact_id": checkpoint["id"],
            "checkpoint_sha256": checkpoint["sha256"],
            "compatibility_certified": True,
        })
        report.write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "status": "succeeded", "metrics": {
                "optimizer_state_bytes": result["optimizer_state_bytes"],
                "compatibility_certified": True,
            },
            "failure": None,
            "artifacts": [
                _artifact_output("probe_report", report, {
                    "checkpoint_artifact_id": checkpoint["id"],
                    "checkpoint_sha256": checkpoint["sha256"],
                    "compatibility_certified": True,
                }),
                _artifact_output("log", log_path, {"run_id": context["run"]["id"]}),
            ],
        }


class TrainingCorpusValidateHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        corpus = _artifact(context, payload["corpus_artifact_id"])
        if corpus is None or corpus["kind"] != "corpus":
            raise SafetyError("corpus validation requires one corpus artifact")
        rows: list[dict[str, Any]] = []
        concepts: list[dict[str, Any]] = []
        with Path(corpus["uri"]).open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SafetyError(f"corpus line {line_number} is not JSON") from exc
                if not isinstance(row, dict) or not all(isinstance(row.get(key), str) and row[key].strip() for key in ("prompt", "completion")):
                    raise SafetyError(f"corpus line {line_number} lacks teaching text")
                if len(row["completion"].encode("utf-8")) > context["training_policy"]["max_completion_utf8_bytes"]:
                    raise SafetyError(f"corpus line {line_number} exceeds the completion byte bound")
                if "concept" in row or "depends_on" in row:
                    if not isinstance(row.get("concept"), str) or not isinstance(row.get("depends_on"), list):
                        raise SafetyError(f"corpus line {line_number} has invalid concept-order metadata")
                    concepts.append({"concept": row["concept"], "depends_on": row["depends_on"]})
                rows.append(row)
        if len(rows) != payload["expected_rows"]:
            raise SafetyError("corpus row count does not match its validation contract")
        if concepts != payload["ordered_concepts"]:
            raise SafetyError("corpus concept order does not match its validation contract")
        require_lesson_material(rows, context["identity_policy"])
        report_value = {
            "schema_version": "ninereeds_training_corpus_validation_v2",
            "status": "passed", "corpus_artifact_id": corpus["id"],
            "corpus_sha256": corpus["sha256"], "row_count": len(rows),
            "concept_count": len(concepts), "concept_sequence_sha256": content_hash(concepts),
            "identity_scope": payload["identity_scope"],
            "identity_policy_sha256": policy_sha256(context["identity_policy"]),
            "example_order": "declared", "shuffle_allowed": False,
        }
        executable, environment, run_root = _runtime(context)
        del executable, environment
        report = run_root / "corpus-validation.json"
        report.write_text(json.dumps(report_value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return {
            "status": "succeeded", "metrics": {"rows": len(rows), "concepts": len(concepts)},
            "failure": None,
            "artifacts": [_artifact_output("validation_report", report, report_value)],
        }


class CortexEvaluateHandler:
    def execute(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        if context["evaluation_policy"] != {
            "basis": ["behavioral_chat", "mri_activation"],
            "loss_role": "telemetry_only",
        }:
            raise SafetyError("Cortex evaluation requires behavioral chat and MRI; loss is telemetry only")
        candidate = _artifact(context, payload["candidate_artifact_id"])
        parent = _artifact(context, payload.get("parent_artifact_id"))
        suite = _artifact(context, payload["suite_artifact_id"])
        if parent is None:
            raise SafetyError("Cortex evaluation requires an explicit parent artifact")
        executable, environment, run_root = _runtime(context)
        report = run_root / "evaluation.json"
        log_path = run_root / "evaluation-log.json"
        evaluation_context_path = run_root / "evaluation-context.json"
        evaluation_context_path.write_text(
            json.dumps(payload["evaluation_context"], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        parameters = payload["parameters"]
        command = [
            str(executable), str(Path(context["release_root"]) / "meta/scripts/evaluate_cortex.py"),
            "--candidate", candidate["uri"], "--parent", parent["uri"], "--suite", suite["uri"],
            "--campaign-id", context["campaign_id"],
            "--evaluation-context", str(evaluation_context_path),
            "--ingress-device", parameters["ingress_device"], "--core-device", parameters["core_device"],
            "--max-new-tokens", str(parameters["max_new_tokens"]), "--output", str(report),
        ]
        _execute(command, environment=environment, timeout=context["timeout_seconds"], log_path=log_path)
        try:
            evaluation = json.loads(report.read_text(encoding="utf-8"))
            certificate = evaluation["certificate"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise RuntimeError("Cortex evaluator returned an invalid evaluation report") from exc
        if any((
            evaluation.get("schema_version") != "ninereeds_cortex_candidate_evaluation_v2",
            evaluation.get("evaluation_basis") != ["behavioral_chat", "mri_activation"],
            evaluation.get("loss_role") != "telemetry_only",
            evaluation.get("campaign_id") != context["campaign_id"],
            evaluation.get("evaluation_context") != payload["evaluation_context"],
            certificate.get("evaluation_context") != payload["evaluation_context"],
            certificate.get("candidate_sha256") != candidate["sha256"],
            certificate.get("parent_sha256") != parent["sha256"],
        )):
            raise RuntimeError("Cortex evaluation report does not match the commissioned evidence contract")
        return {
            "status": "succeeded",
            "metrics": {},
            "failure": None,
            "artifacts": [
                _artifact_output("evaluation_report", report, {
                    "candidate_artifact_id": payload["candidate_artifact_id"],
                    "candidate_sha256": candidate["sha256"],
                    "parent_artifact_id": payload["parent_artifact_id"],
                    "parent_sha256": parent["sha256"],
                    "suite_artifact_id": payload["suite_artifact_id"],
                    "suite_sha256": suite["sha256"],
                    "campaign_contract_sha256": payload["evaluation_context"]["campaign_contract_sha256"],
                    "training_mode": payload["evaluation_context"]["mode"],
                    "development_stage": payload["evaluation_context"]["development_stage"],
                    "branch_id": payload["evaluation_context"]["branch_id"],
                    "branch_complete": payload["evaluation_context"]["branch_complete"],
                    "evaluation_basis": ["behavioral_chat", "mri_activation"],
                    "loss_role": "telemetry_only",
                }),
                _artifact_output("log", log_path, {"run_id": context["run"]["id"]}),
            ],
        }
