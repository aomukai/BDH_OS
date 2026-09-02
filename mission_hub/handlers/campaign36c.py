"""Bounded Campaign 36C Stage-1 execution on the commissioned trainbox."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from typing import Any

from ..errors import ProtocolError, RemoteJobError, SafetyError


CELL_LAB_RESULT_SCHEMA = "ninereeds_campaign36c_cell_lab_result_v0"
WAVE_LAB_RESULT_SCHEMA = "ninereeds_campaign36c_wave_lab_result_v0"
LEARNING_LAB_RESULT_SCHEMA = "ninereeds_campaign36c_learning_lab_result_v0"
DEVELOPMENT_LAB_RESULT_SCHEMA = "ninereeds_campaign36c_development_lab_result_v0"
PERSISTENCE_LAB_RESULT_SCHEMA = "ninereeds_campaign36c_persistence_lab_result_v0"
STRUCTURAL_LAB_RESULT_SCHEMA = "ninereeds_campaign36c_structural_lab_result_v0"
HYGIENE_LAB_RESULT_SCHEMA = "ninereeds_campaign36c_hygiene_lab_result_v0"
ORGANISM_BOOTSTRAP_RECEIPT_SCHEMA = (
    "ninereeds_campaign36c_multimodal_bootstrap_launch_v3"
)
ORGANISM_ARCHIVE_SCHEMA = "ninereeds_campaign36c_organism_archive_v1"
BOOTSTRAP_MANIFEST_IDENTITY = (
    "e1d760e264717d05676076429a2e13e46cd05da6d8376169feaad579121ac2fb"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _run_root(context: dict[str, Any]) -> Path:
    root = Path(context["state_root"]) / "runs" / context["run"]["id"]
    root.mkdir(parents=True, exist_ok=False)
    return root


def _input_artifact(
    context: dict[str, Any],
    artifact_id: str,
    *,
    expected_kind: str,
) -> tuple[dict[str, Any], Path]:
    matches = [
        artifact
        for artifact in context["artifacts"]
        if artifact["id"] == artifact_id
    ]
    if len(matches) != 1:
        raise ProtocolError(
            f"job did not receive exactly one artifact reference: {artifact_id}"
        )
    artifact = matches[0]
    if artifact["kind"] != expected_kind:
        raise SafetyError(
            f"artifact {artifact_id} has kind {artifact['kind']}, "
            f"expected {expected_kind}"
        )
    path = Path(artifact["uri"]).resolve()
    roots = [
        Path(context["state_root"]).resolve(),
        *(Path(value).resolve() for value in context["artifact_roots"]),
    ]
    if not path.is_file() or not any(path == root or root in path.parents for root in roots):
        raise SafetyError(f"cell-lab input is outside configured roots: {artifact_id}")
    if path.stat().st_size != artifact["byte_size"] or _sha256(path) != artifact["sha256"]:
        raise SafetyError(f"cell-lab input bytes do not match the envelope: {artifact_id}")
    return artifact, path


def _artifact_output(
    kind: str,
    path: Path,
    *,
    lifecycle: str,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": kind,
        "sha256": _sha256(path),
        "byte_size": path.stat().st_size,
        "uri": str(path),
        "lifecycle": lifecycle,
        "manifest": manifest,
    }


class Campaign36CCellLabHandler:
    """Execute one immutable cell-cohort sweep without enabling later 36C stages."""

    def execute(
        self,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if payload["mode"] == "latent_task":
            if payload["latent_task_artifact_id"] is None or payload["synthetic"] is not None:
                raise SafetyError(
                    "latent_task mode requires one artifact and no synthetic specification"
                )
        elif payload["latent_task_artifact_id"] is not None or payload["synthetic"] is None:
            raise SafetyError(
                "synthetic mode requires one specification and no latent-task artifact"
            )
        run_root = _run_root(context)
        report_path = run_root / "campaign36c-cell-lab.json"
        log_path = run_root / "campaign36c-cell-lab.log.json"
        release_root = Path(context["release_root"]).resolve()
        executable = Path(context["deployment_environment"]["python_executable"])
        command = [
            str(executable),
            str(release_root / "meta/scripts/cortex_runtime.py"),
            str(release_root / "meta/scripts/run_campaign36c_cell_lab.py"),
            "--output",
            str(report_path),
            "--pair-counts",
            *(str(value) for value in payload["pair_counts"]),
            "--training-steps",
            str(payload["training_steps"]),
            "--learning-rate",
            str(payload["learning_rate"]),
            "--benchmark-warmup",
            str(payload["benchmark_warmup"]),
            "--benchmark-iterations",
            str(payload["benchmark_iterations"]),
            "--residual-scale",
            str(payload["residual_scale"]),
            "--mechanical-tolerance",
            str(payload["mechanical_tolerance"]),
            "--minimum-improvement-fraction",
            str(payload["minimum_improvement_fraction"]),
            "--seed",
            str(payload["seed"]),
            "--devices",
            *(f"cuda:{index}" for index in payload["device_indices"]),
            "--dtype",
            payload["dtype"],
        ]
        input_manifest: dict[str, Any]
        if payload["mode"] == "latent_task":
            artifact, path = _input_artifact(
                context,
                payload["latent_task_artifact_id"],
                expected_kind="campaign36c_latent_task",
            )
            command.extend(["--latent-bundle", str(path)])
            input_manifest = {
                "mode": "latent_task",
                "artifact_id": artifact["id"],
                "sha256": artifact["sha256"],
            }
        else:
            synthetic = payload["synthetic"]
            command.extend([
                "--synthetic-width",
                str(synthetic["width"]),
                "--synthetic-sequence-length",
                str(synthetic["sequence_length"]),
                "--synthetic-training-examples",
                str(synthetic["training_examples"]),
                "--synthetic-evaluation-examples",
                str(synthetic["evaluation_examples"]),
                "--synthetic-teacher-pairs",
                str(synthetic["teacher_pairs"]),
            ])
            input_manifest = {"mode": "synthetic", **synthetic}

        environment = dict(os.environ)
        python_path = [str(release_root)]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(python_path)
        site_paths = context["deployment_environment"].get("python_site_paths", [])
        if site_paths:
            environment["NINEREEDS_TORCH_SITE"] = site_paths[0]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=environment,
            timeout=context["timeout_seconds"],
            check=False,
        )
        log_path.write_text(
            json.dumps(
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if completed.returncode != 0:
            lowered = completed.stderr.lower()
            if "cuda out of memory" in lowered or "torch.outofmemoryerror" in lowered:
                raise RemoteJobError(
                    f"Campaign 36C cell lab ran out of CUDA memory; evidence: {log_path}",
                    failure_class="operational_transient",
                    code="resource_temporarily_unavailable",
                )
            raise RuntimeError(
                "Campaign 36C cell lab failed with exit code "
                f"{completed.returncode}; evidence: {log_path}"
            )
        if not report_path.is_file():
            raise RuntimeError("Campaign 36C cell lab produced no report")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Campaign 36C cell lab report is not valid JSON") from exc
        if report.get("schema_version") != CELL_LAB_RESULT_SCHEMA:
            raise RuntimeError("Campaign 36C cell lab returned an unsupported report")
        observed_pairs = [
            trial.get("rotary_pairs") for trial in report.get("trials", [])
        ]
        if observed_pairs != payload["pair_counts"]:
            raise RuntimeError("Campaign 36C cell lab report changed the commissioned cohort sweep")
        expected_lab_config = {
            "pair_counts": payload["pair_counts"],
            "training_steps": payload["training_steps"],
            "benchmark_warmup": payload["benchmark_warmup"],
            "benchmark_iterations": payload["benchmark_iterations"],
            "residual_scale": payload["residual_scale"],
            "seed": payload["seed"],
            "mechanical_tolerance": payload["mechanical_tolerance"],
            "minimum_improvement_fraction": payload[
                "minimum_improvement_fraction"
            ],
        }
        if report.get("lab_config") != expected_lab_config:
            raise RuntimeError(
                "Campaign 36C cell lab report changed the commissioned experiment bounds"
            )
        expected_optimizer = {
            "learning_rate": payload["learning_rate"],
            "betas": [0.9, 0.999],
            "epsilon": 1e-8,
            "weight_decay": 0.0,
            "amsgrad": False,
            "policy": "torch_adamw_uid_local_full_moments_v1",
        }
        if report.get("optimizer_config") != expected_optimizer:
            raise RuntimeError(
                "Campaign 36C cell lab report changed the commissioned optimizer"
            )
        execution = report.get("execution", {})
        device_reports = execution.get("devices", [execution])
        observed_devices = [item.get("device") for item in device_reports]
        expected_devices = [f"cuda:{index}" for index in payload["device_indices"]]
        expected_dtype = f"torch.{payload['dtype']}"
        if observed_devices != expected_devices or any(
            item.get("dtype") != expected_dtype for item in device_reports
        ):
            raise RuntimeError(
                "Campaign 36C cell lab report changed the commissioned device policy"
            )
        if payload["mode"] == "synthetic":
            task = report.get("task", {})
            metadata = task.get("metadata", {})
            if (
                task.get("width") != payload["synthetic"]["width"]
                or metadata.get("behavioral_evidence") is not False
                or metadata.get("kind")
                != "deterministic_synthetic_mechanical_smoke"
            ):
                raise RuntimeError(
                    "Campaign 36C synthetic smoke misreported its evidence scope"
                )
        selection = report.get("selection", {})
        manifest = {
            "schema_version": CELL_LAB_RESULT_SCHEMA,
            "run_id": context["run"]["id"],
            "input": input_manifest,
            "pair_counts": payload["pair_counts"],
            "device_indices": payload["device_indices"],
            "selected_rotary_pairs": selection.get("selected_rotary_pairs"),
            "stage1_exit_gate_met": selection.get("stage1_exit_gate_met"),
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _artifact_output(
                    "cell_lab_report",
                    report_path,
                    lifecycle="observed",
                    manifest=manifest,
                ),
                _artifact_output(
                    "log",
                    log_path,
                    lifecycle="observed",
                    manifest={"run_id": context["run"]["id"]},
                ),
            ],
            "metrics": {
                "trial_count": len(report["trials"]),
                "selected_rotary_pairs": selection.get("selected_rotary_pairs"),
                "stage1_exit_gate_met": selection.get("stage1_exit_gate_met"),
                "device_indices": payload["device_indices"],
            },
            "failure": None,
        }


class Campaign36CWaveLabHandler:
    """Execute the fixed-graph Stage-2 wave lab without enabling growth."""

    def execute(
        self,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        run_root = _run_root(context)
        report_path = run_root / "campaign36c-wave-lab.json"
        log_path = run_root / "campaign36c-wave-lab.log.json"
        release_root = Path(context["release_root"]).resolve()
        executable = Path(context["deployment_environment"]["python_executable"])
        command = [
            str(executable),
            str(release_root / "meta/scripts/cortex_runtime.py"),
            str(release_root / "meta/scripts/run_campaign36c_wave_lab.py"),
            "--output",
            str(report_path),
            "--width",
            str(payload["width"]),
            "--rotary-pairs",
            str(payload["rotary_pairs"]),
            "--sequence-length",
            str(payload["sequence_length"]),
            "--disconnected-cell-counts",
            *(str(value) for value in payload["disconnected_cell_counts"]),
            "--benchmark-warmup",
            str(payload["benchmark_warmup"]),
            "--benchmark-iterations",
            str(payload["benchmark_iterations"]),
            "--maximum-material-latency-ratio",
            str(payload["maximum_material_latency_ratio"]),
            "--maximum-serviceable-p95-ms",
            str(payload["maximum_serviceable_p95_ms"]),
            "--seed",
            str(payload["seed"]),
            "--devices",
            *(f"cuda:{index}" for index in payload["device_indices"]),
            "--dtype",
            payload["dtype"],
        ]
        environment = dict(os.environ)
        python_path = [str(release_root)]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(python_path)
        site_paths = context["deployment_environment"].get("python_site_paths", [])
        if site_paths:
            environment["NINEREEDS_TORCH_SITE"] = site_paths[0]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=environment,
            timeout=context["timeout_seconds"],
            check=False,
        )
        log_path.write_text(
            json.dumps(
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if completed.returncode != 0:
            lowered = completed.stderr.lower()
            if "cuda out of memory" in lowered or "torch.outofmemoryerror" in lowered:
                raise RemoteJobError(
                    f"Campaign 36C wave lab ran out of CUDA memory; evidence: {log_path}",
                    failure_class="operational_transient",
                    code="resource_temporarily_unavailable",
                )
            raise RuntimeError(
                "Campaign 36C wave lab failed with exit code "
                f"{completed.returncode}; evidence: {log_path}"
            )
        if not report_path.is_file():
            raise RuntimeError("Campaign 36C wave lab produced no report")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Campaign 36C wave lab report is not valid JSON") from exc
        if report.get("schema_version") != WAVE_LAB_RESULT_SCHEMA:
            raise RuntimeError("Campaign 36C wave lab returned an unsupported report")
        expected_config = {
            "width": payload["width"],
            "rotary_pairs": payload["rotary_pairs"],
            "sequence_length": payload["sequence_length"],
            "disconnected_cell_counts": payload["disconnected_cell_counts"],
            "benchmark_warmup": payload["benchmark_warmup"],
            "benchmark_iterations": payload["benchmark_iterations"],
            "maximum_material_latency_ratio": payload[
                "maximum_material_latency_ratio"
            ],
            "maximum_serviceable_p95_ms": payload[
                "maximum_serviceable_p95_ms"
            ],
            "seed": payload["seed"],
        }
        if report.get("lab_config") != expected_config:
            raise RuntimeError(
                "Campaign 36C wave lab changed the commissioned experiment bounds"
            )
        execution = report.get("execution", {})
        device_reports = execution.get("devices", [execution])
        expected_devices = [f"cuda:{index}" for index in payload["device_indices"]]
        expected_dtype = f"torch.{payload['dtype']}"
        if [item.get("device") for item in device_reports] != expected_devices or any(
            item.get("dtype") != expected_dtype for item in device_reports
        ):
            raise RuntimeError(
                "Campaign 36C wave lab changed the commissioned device policy"
            )
        selection = report.get("selection", {})
        manifest = {
            "schema_version": WAVE_LAB_RESULT_SCHEMA,
            "run_id": context["run"]["id"],
            "device_indices": payload["device_indices"],
            "disconnected_cell_counts": payload["disconnected_cell_counts"],
            "stage2_exit_gate_met": selection.get("stage2_exit_gate_met"),
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _artifact_output(
                    "wave_lab_report",
                    report_path,
                    lifecycle="observed",
                    manifest=manifest,
                ),
                _artifact_output(
                    "log",
                    log_path,
                    lifecycle="observed",
                    manifest={"run_id": context["run"]["id"]},
                ),
            ],
            "metrics": {
                "stage2_exit_gate_met": selection.get("stage2_exit_gate_met"),
                "device_indices": payload["device_indices"],
                "maximum_disconnected_cells": max(
                    payload["disconnected_cell_counts"]
                ),
            },
            "failure": None,
        }


class Campaign36CLearningLabHandler:
    """Execute bounded Stage-3 sparse learning without growth or promotion."""

    def execute(
        self,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        run_root = _run_root(context)
        report_path = run_root / "campaign36c-learning-lab.json"
        log_path = run_root / "campaign36c-learning-lab.log.json"
        release_root = Path(context["release_root"]).resolve()
        executable = Path(context["deployment_environment"]["python_executable"])
        command = [
            str(executable),
            str(release_root / "meta/scripts/cortex_runtime.py"),
            str(release_root / "meta/scripts/run_campaign36c_learning_lab.py"),
            "--output",
            str(report_path),
            "--width",
            str(payload["width"]),
            "--rotary-pairs",
            str(payload["rotary_pairs"]),
            "--sequence-length",
            str(payload["sequence_length"]),
            "--training-examples",
            str(payload["training_examples"]),
            "--evaluation-examples",
            str(payload["evaluation_examples"]),
            "--training-steps",
            str(payload["training_steps"]),
            "--black-swan-steps",
            str(payload["black_swan_steps"]),
            "--common-replay-steps",
            str(payload["common_replay_steps"]),
            "--disconnected-cells",
            str(payload["disconnected_cells"]),
            "--learning-rate",
            str(payload["learning_rate"]),
            "--minimum-heldout-improvement-fraction",
            str(payload["minimum_heldout_improvement_fraction"]),
            "--seed",
            str(payload["seed"]),
            "--devices",
            *(f"cuda:{index}" for index in payload["device_indices"]),
            "--dtype",
            payload["dtype"],
        ]
        environment = dict(os.environ)
        python_path = [str(release_root)]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(python_path)
        site_paths = context["deployment_environment"].get("python_site_paths", [])
        if site_paths:
            environment["NINEREEDS_TORCH_SITE"] = site_paths[0]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=environment,
            timeout=context["timeout_seconds"],
            check=False,
        )
        log_path.write_text(
            json.dumps(
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if completed.returncode != 0:
            lowered = completed.stderr.lower()
            if "cuda out of memory" in lowered or "torch.outofmemoryerror" in lowered:
                raise RemoteJobError(
                    f"Campaign 36C learning lab ran out of CUDA memory; evidence: {log_path}",
                    failure_class="operational_transient",
                    code="resource_temporarily_unavailable",
                )
            raise RuntimeError(
                "Campaign 36C learning lab failed with exit code "
                f"{completed.returncode}; evidence: {log_path}"
            )
        if not report_path.is_file():
            raise RuntimeError("Campaign 36C learning lab produced no report")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Campaign 36C learning lab report is not valid JSON"
            ) from exc
        if report.get("schema_version") != LEARNING_LAB_RESULT_SCHEMA:
            raise RuntimeError(
                "Campaign 36C learning lab returned an unsupported report"
            )
        expected_config = {
            key: payload[key]
            for key in (
                "width",
                "rotary_pairs",
                "sequence_length",
                "training_examples",
                "evaluation_examples",
                "training_steps",
                "black_swan_steps",
                "common_replay_steps",
                "disconnected_cells",
                "learning_rate",
                "minimum_heldout_improvement_fraction",
                "seed",
            )
        }
        if report.get("lab_config") != expected_config:
            raise RuntimeError(
                "Campaign 36C learning lab changed the commissioned experiment bounds"
            )
        execution = report.get("execution", {})
        device_reports = execution.get("devices", [execution])
        expected_devices = [f"cuda:{index}" for index in payload["device_indices"]]
        expected_dtype = f"torch.{payload['dtype']}"
        if [item.get("device") for item in device_reports] != expected_devices or any(
            item.get("dtype") != expected_dtype for item in device_reports
        ):
            raise RuntimeError(
                "Campaign 36C learning lab changed the commissioned device policy"
            )
        selection = report.get("selection", {})
        manifest = {
            "schema_version": LEARNING_LAB_RESULT_SCHEMA,
            "run_id": context["run"]["id"],
            "device_indices": payload["device_indices"],
            "stage3_exit_gate_met": selection.get("stage3_exit_gate_met"),
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _artifact_output(
                    "learning_lab_report",
                    report_path,
                    lifecycle="observed",
                    manifest=manifest,
                ),
                _artifact_output(
                    "log",
                    log_path,
                    lifecycle="observed",
                    manifest={"run_id": context["run"]["id"]},
                ),
            ],
            "metrics": {
                "stage3_exit_gate_met": selection.get("stage3_exit_gate_met"),
                "device_indices": payload["device_indices"],
                "disconnected_cells": payload["disconnected_cells"],
            },
            "failure": None,
        }


class Campaign36CDevelopmentLabHandler:
    """Execute Stage-4 diagnosis and provisional growth under operator approval."""

    _CONFIG_KEYS = (
        "width",
        "rotary_pairs",
        "sequence_length",
        "training_examples",
        "evaluation_examples",
        "shadow_training_steps",
        "disconnected_cells",
        "learning_rate",
        "minimum_shadow_improvement_fraction",
        "minimum_residual_coherence",
        "seed",
    )

    def execute(
        self,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        run_root = _run_root(context)
        report_path = run_root / "campaign36c-development-lab.json"
        log_path = run_root / "campaign36c-development-lab.log.json"
        release_root = Path(context["release_root"]).resolve()
        executable = Path(context["deployment_environment"]["python_executable"])
        command = [
            str(executable),
            str(release_root / "meta/scripts/cortex_runtime.py"),
            str(release_root / "meta/scripts/run_campaign36c_development_lab.py"),
            "--output",
            str(report_path),
            "--width",
            str(payload["width"]),
            "--rotary-pairs",
            str(payload["rotary_pairs"]),
            "--sequence-length",
            str(payload["sequence_length"]),
            "--training-examples",
            str(payload["training_examples"]),
            "--evaluation-examples",
            str(payload["evaluation_examples"]),
            "--shadow-training-steps",
            str(payload["shadow_training_steps"]),
            "--disconnected-cells",
            str(payload["disconnected_cells"]),
            "--learning-rate",
            str(payload["learning_rate"]),
            "--minimum-shadow-improvement-fraction",
            str(payload["minimum_shadow_improvement_fraction"]),
            "--minimum-residual-coherence",
            str(payload["minimum_residual_coherence"]),
            "--seed",
            str(payload["seed"]),
            "--devices",
            *(f"cuda:{index}" for index in payload["device_indices"]),
            "--dtype",
            payload["dtype"],
        ]
        environment = dict(os.environ)
        python_path = [str(release_root)]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(python_path)
        site_paths = context["deployment_environment"].get("python_site_paths", [])
        if site_paths:
            environment["NINEREEDS_TORCH_SITE"] = site_paths[0]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=environment,
            timeout=context["timeout_seconds"],
            check=False,
        )
        log_path.write_text(
            json.dumps(
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if completed.returncode != 0:
            lowered = completed.stderr.lower()
            if "cuda out of memory" in lowered or "torch.outofmemoryerror" in lowered:
                raise RemoteJobError(
                    f"Campaign 36C development lab ran out of CUDA memory; evidence: {log_path}",
                    failure_class="operational_transient",
                    code="resource_temporarily_unavailable",
                )
            raise RuntimeError(
                "Campaign 36C development lab failed with exit code "
                f"{completed.returncode}; evidence: {log_path}"
            )
        if not report_path.is_file():
            raise RuntimeError("Campaign 36C development lab produced no report")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Campaign 36C development lab report is not valid JSON"
            ) from exc
        if report.get("schema_version") != DEVELOPMENT_LAB_RESULT_SCHEMA:
            raise RuntimeError(
                "Campaign 36C development lab returned an unsupported report"
            )
        expected_config = {key: payload[key] for key in self._CONFIG_KEYS}
        if report.get("lab_config") != expected_config:
            raise RuntimeError(
                "Campaign 36C development lab changed the commissioned experiment bounds"
            )
        execution = report.get("execution", {})
        device_reports = execution.get("devices", [execution])
        expected_devices = [f"cuda:{index}" for index in payload["device_indices"]]
        expected_dtype = f"torch.{payload['dtype']}"
        if [item.get("device") for item in device_reports] != expected_devices or any(
            item.get("dtype") != expected_dtype for item in device_reports
        ):
            raise RuntimeError(
                "Campaign 36C development lab changed the commissioned device policy"
            )
        selection = report.get("selection", {})
        development_telemetry = report.get("development_telemetry")
        if not isinstance(development_telemetry, dict):
            raise RuntimeError(
                "Campaign 36C development lab omitted authoritative telemetry"
            )
        manifest = {
            "schema_version": DEVELOPMENT_LAB_RESULT_SCHEMA,
            "run_id": context["run"]["id"],
            "device_indices": payload["device_indices"],
            "stage4_exit_gate_met": selection.get("stage4_exit_gate_met"),
            "development_telemetry": development_telemetry,
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _artifact_output(
                    "development_lab_report",
                    report_path,
                    lifecycle="observed",
                    manifest=manifest,
                ),
                _artifact_output(
                    "log",
                    log_path,
                    lifecycle="observed",
                    manifest={"run_id": context["run"]["id"]},
                ),
            ],
            "metrics": {
                "stage4_exit_gate_met": selection.get("stage4_exit_gate_met"),
                "device_indices": payload["device_indices"],
                "disconnected_cells": payload["disconnected_cells"],
                "development_telemetry": development_telemetry,
            },
            "failure": None,
        }


class Campaign36CPersistenceLabHandler:
    """Execute Stage-5 packed persistence and graph-residency validation."""

    _CONFIG_KEYS = (
        "width",
        "rotary_pairs",
        "sequence_length",
        "disconnected_cells",
        "page_capacities",
        "access_set_sizes",
        "dirty_update_events",
        "seed",
    )

    def execute(
        self,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        run_root = _run_root(context)
        report_path = run_root / "campaign36c-persistence-lab.json"
        log_path = run_root / "campaign36c-persistence-lab.log.json"
        release_root = Path(context["release_root"]).resolve()
        executable = Path(context["deployment_environment"]["python_executable"])
        command = [
            str(executable),
            str(release_root / "meta/scripts/cortex_runtime.py"),
            str(release_root / "meta/scripts/run_campaign36c_persistence_lab.py"),
            "--output",
            str(report_path),
            "--scratch-root",
            str(run_root / "stage5-scratch"),
            "--width",
            str(payload["width"]),
            "--rotary-pairs",
            str(payload["rotary_pairs"]),
            "--sequence-length",
            str(payload["sequence_length"]),
            "--disconnected-cells",
            str(payload["disconnected_cells"]),
            "--page-capacities",
            *(str(value) for value in payload["page_capacities"]),
            "--access-set-sizes",
            *(str(value) for value in payload["access_set_sizes"]),
            "--dirty-update-events",
            str(payload["dirty_update_events"]),
            "--seed",
            str(payload["seed"]),
            "--devices",
            *(f"cuda:{index}" for index in payload["device_indices"]),
            "--dtype",
            payload["dtype"],
        ]
        environment = dict(os.environ)
        python_path = [str(release_root)]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(python_path)
        site_paths = context["deployment_environment"].get("python_site_paths", [])
        if site_paths:
            environment["NINEREEDS_TORCH_SITE"] = site_paths[0]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=environment,
            timeout=context["timeout_seconds"],
            check=False,
        )
        log_path.write_text(
            json.dumps(
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if completed.returncode != 0:
            lowered = completed.stderr.lower()
            if "cuda out of memory" in lowered or "torch.outofmemoryerror" in lowered:
                raise RemoteJobError(
                    f"Campaign 36C persistence lab ran out of CUDA memory; evidence: {log_path}",
                    failure_class="operational_transient",
                    code="resource_temporarily_unavailable",
                )
            raise RuntimeError(
                "Campaign 36C persistence lab failed with exit code "
                f"{completed.returncode}; evidence: {log_path}"
            )
        if not report_path.is_file():
            raise RuntimeError("Campaign 36C persistence lab produced no report")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Campaign 36C persistence lab report is not valid JSON"
            ) from exc
        if report.get("schema_version") != PERSISTENCE_LAB_RESULT_SCHEMA:
            raise RuntimeError(
                "Campaign 36C persistence lab returned an unsupported report"
            )
        expected_config = {key: payload[key] for key in self._CONFIG_KEYS}
        if report.get("lab_config") != expected_config:
            raise RuntimeError(
                "Campaign 36C persistence lab changed the commissioned experiment bounds"
            )
        execution = report.get("execution", {})
        device_reports = execution.get("devices", [execution])
        expected_devices = [f"cuda:{index}" for index in payload["device_indices"]]
        expected_dtype = f"torch.{payload['dtype']}"
        if [item.get("device") for item in device_reports] != expected_devices or any(
            item.get("dtype") != expected_dtype for item in device_reports
        ):
            raise RuntimeError(
                "Campaign 36C persistence lab changed the commissioned device policy"
            )
        selection = report.get("selection", {})
        manifest = {
            "schema_version": PERSISTENCE_LAB_RESULT_SCHEMA,
            "run_id": context["run"]["id"],
            "device_indices": payload["device_indices"],
            "stage5_exit_gate_met": selection.get("stage5_exit_gate_met"),
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _artifact_output(
                    "persistence_lab_report",
                    report_path,
                    lifecycle="observed",
                    manifest=manifest,
                ),
                _artifact_output(
                    "log",
                    log_path,
                    lifecycle="observed",
                    manifest={"run_id": context["run"]["id"]},
                ),
            ],
            "metrics": {
                "stage5_exit_gate_met": selection.get("stage5_exit_gate_met"),
                "device_indices": payload["device_indices"],
                "disconnected_cells": payload["disconnected_cells"],
                "selected_page_capacities": selection.get(
                    "selected_page_capacities",
                    [selection.get("selected_page_capacity")],
                ),
            },
            "failure": None,
        }


class Campaign36CStructuralLabHandler:
    """Execute Stage-6 reversible fusion and seam-gated fission validation."""

    _CONFIG_KEYS = (
        "width",
        "rotary_pairs",
        "sequence_length",
        "benchmark_warmup",
        "benchmark_iterations",
        "page_capacity",
        "maximum_composite_leaves",
        "behavior_tolerance",
        "maximum_seam_regression",
        "seed",
    )

    def execute(
        self,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        run_root = _run_root(context)
        report_path = run_root / "campaign36c-structural-lab.json"
        log_path = run_root / "campaign36c-structural-lab.log.json"
        release_root = Path(context["release_root"]).resolve()
        executable = Path(context["deployment_environment"]["python_executable"])
        command = [
            str(executable),
            str(release_root / "meta/scripts/cortex_runtime.py"),
            str(release_root / "meta/scripts/run_campaign36c_structural_lab.py"),
            "--output",
            str(report_path),
            "--scratch-root",
            str(run_root / "stage6-scratch"),
            "--width",
            str(payload["width"]),
            "--rotary-pairs",
            str(payload["rotary_pairs"]),
            "--sequence-length",
            str(payload["sequence_length"]),
            "--benchmark-warmup",
            str(payload["benchmark_warmup"]),
            "--benchmark-iterations",
            str(payload["benchmark_iterations"]),
            "--page-capacity",
            str(payload["page_capacity"]),
            "--maximum-composite-leaves",
            str(payload["maximum_composite_leaves"]),
            "--behavior-tolerance",
            str(payload["behavior_tolerance"]),
            "--maximum-seam-regression",
            str(payload["maximum_seam_regression"]),
            "--seed",
            str(payload["seed"]),
            "--devices",
            *(f"cuda:{index}" for index in payload["device_indices"]),
            "--dtype",
            payload["dtype"],
        ]
        environment = dict(os.environ)
        python_path = [str(release_root)]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(python_path)
        site_paths = context["deployment_environment"].get("python_site_paths", [])
        if site_paths:
            environment["NINEREEDS_TORCH_SITE"] = site_paths[0]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=environment,
            timeout=context["timeout_seconds"],
            check=False,
        )
        log_path.write_text(
            json.dumps(
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if completed.returncode != 0:
            lowered = completed.stderr.lower()
            if "cuda out of memory" in lowered or "torch.outofmemoryerror" in lowered:
                raise RemoteJobError(
                    f"Campaign 36C structural lab ran out of CUDA memory; evidence: {log_path}",
                    failure_class="operational_transient",
                    code="resource_temporarily_unavailable",
                )
            raise RuntimeError(
                "Campaign 36C structural lab failed with exit code "
                f"{completed.returncode}; evidence: {log_path}"
            )
        if not report_path.is_file():
            raise RuntimeError("Campaign 36C structural lab produced no report")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Campaign 36C structural lab report is not valid JSON"
            ) from exc
        if report.get("schema_version") != STRUCTURAL_LAB_RESULT_SCHEMA:
            raise RuntimeError(
                "Campaign 36C structural lab returned an unsupported report"
            )
        expected_config = {key: payload[key] for key in self._CONFIG_KEYS}
        if report.get("lab_config") != expected_config:
            raise RuntimeError(
                "Campaign 36C structural lab changed the commissioned experiment bounds"
            )
        execution = report.get("execution", {})
        device_reports = execution.get("devices", [execution])
        expected_devices = [f"cuda:{index}" for index in payload["device_indices"]]
        expected_dtype = f"torch.{payload['dtype']}"
        if [item.get("device") for item in device_reports] != expected_devices or any(
            item.get("dtype") != expected_dtype for item in device_reports
        ):
            raise RuntimeError(
                "Campaign 36C structural lab changed the commissioned device policy"
            )
        selection = report.get("selection", {})
        manifest = {
            "schema_version": STRUCTURAL_LAB_RESULT_SCHEMA,
            "run_id": context["run"]["id"],
            "device_indices": payload["device_indices"],
            "stage6_exit_gate_met": selection.get("stage6_exit_gate_met"),
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _artifact_output(
                    "structural_lab_report",
                    report_path,
                    lifecycle="observed",
                    manifest=manifest,
                ),
                _artifact_output(
                    "log",
                    log_path,
                    lifecycle="observed",
                    manifest={"run_id": context["run"]["id"]},
                ),
            ],
            "metrics": {
                "stage6_exit_gate_met": selection.get("stage6_exit_gate_met"),
                "device_indices": payload["device_indices"],
                "maximum_composite_leaves": payload["maximum_composite_leaves"],
            },
            "failure": None,
        }


class Campaign36CHygieneLabHandler:
    """Execute Stage-7 vitality, quarantine, revival, and purge validation."""

    _CONFIG_KEYS = (
        "width",
        "rotary_pairs",
        "sequence_length",
        "page_capacity",
        "senescence_interval",
        "minimum_senescence_sweeps",
        "maximum_revival_candidates",
        "minimum_revival_similarity",
        "minimum_revival_improvement_fraction",
        "maximum_revival_regression",
        "seed",
    )

    def execute(
        self,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        run_root = _run_root(context)
        report_path = run_root / "campaign36c-hygiene-lab.json"
        log_path = run_root / "campaign36c-hygiene-lab.log.json"
        release_root = Path(context["release_root"]).resolve()
        executable = Path(context["deployment_environment"]["python_executable"])
        command = [
            str(executable),
            str(release_root / "meta/scripts/cortex_runtime.py"),
            str(release_root / "meta/scripts/run_campaign36c_hygiene_lab.py"),
            "--output",
            str(report_path),
            "--scratch-root",
            str(run_root / "stage7-scratch"),
            "--width",
            str(payload["width"]),
            "--rotary-pairs",
            str(payload["rotary_pairs"]),
            "--sequence-length",
            str(payload["sequence_length"]),
            "--page-capacity",
            str(payload["page_capacity"]),
            "--senescence-interval",
            str(payload["senescence_interval"]),
            "--minimum-senescence-sweeps",
            str(payload["minimum_senescence_sweeps"]),
            "--maximum-revival-candidates",
            str(payload["maximum_revival_candidates"]),
            "--minimum-revival-similarity",
            str(payload["minimum_revival_similarity"]),
            "--minimum-revival-improvement-fraction",
            str(payload["minimum_revival_improvement_fraction"]),
            "--maximum-revival-regression",
            str(payload["maximum_revival_regression"]),
            "--seed",
            str(payload["seed"]),
            "--devices",
            *(f"cuda:{index}" for index in payload["device_indices"]),
            "--dtype",
            payload["dtype"],
        ]
        environment = dict(os.environ)
        python_path = [str(release_root)]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(python_path)
        site_paths = context["deployment_environment"].get("python_site_paths", [])
        if site_paths:
            environment["NINEREEDS_TORCH_SITE"] = site_paths[0]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=environment,
            timeout=context["timeout_seconds"],
            check=False,
        )
        log_path.write_text(
            json.dumps(
                {
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if completed.returncode != 0:
            lowered = completed.stderr.lower()
            if "cuda out of memory" in lowered or "torch.outofmemoryerror" in lowered:
                raise RemoteJobError(
                    f"Campaign 36C hygiene lab ran out of CUDA memory; evidence: {log_path}",
                    failure_class="operational_transient",
                    code="resource_temporarily_unavailable",
                )
            raise RuntimeError(
                "Campaign 36C hygiene lab failed with exit code "
                f"{completed.returncode}; evidence: {log_path}"
            )
        if not report_path.is_file():
            raise RuntimeError("Campaign 36C hygiene lab produced no report")
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                "Campaign 36C hygiene lab report is not valid JSON"
            ) from exc
        if report.get("schema_version") != HYGIENE_LAB_RESULT_SCHEMA:
            raise RuntimeError(
                "Campaign 36C hygiene lab returned an unsupported report"
            )
        expected_config = {key: payload[key] for key in self._CONFIG_KEYS}
        if report.get("lab_config") != expected_config:
            raise RuntimeError(
                "Campaign 36C hygiene lab changed the commissioned experiment bounds"
            )
        execution = report.get("execution", {})
        device_reports = execution.get("devices", [execution])
        expected_devices = [f"cuda:{index}" for index in payload["device_indices"]]
        expected_dtype = f"torch.{payload['dtype']}"
        if [item.get("device") for item in device_reports] != expected_devices or any(
            item.get("dtype") != expected_dtype for item in device_reports
        ):
            raise RuntimeError(
                "Campaign 36C hygiene lab changed the commissioned device policy"
            )
        selection = report.get("selection", {})
        manifest = {
            "schema_version": HYGIENE_LAB_RESULT_SCHEMA,
            "run_id": context["run"]["id"],
            "device_indices": payload["device_indices"],
            "stage7_exit_gate_met": selection.get("stage7_exit_gate_met"),
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _artifact_output(
                    "hygiene_lab_report",
                    report_path,
                    lifecycle="observed",
                    manifest=manifest,
                ),
                _artifact_output(
                    "log",
                    log_path,
                    lifecycle="observed",
                    manifest={"run_id": context["run"]["id"]},
                ),
            ],
            "metrics": {
                "stage7_exit_gate_met": selection.get("stage7_exit_gate_met"),
                "device_indices": payload["device_indices"],
                "maximum_revival_candidates": payload[
                    "maximum_revival_candidates"
                ],
            },
            "failure": None,
        }


class Campaign36COrganismBootstrapHandler:
    """Run a bounded smoke or launch the durable multi-session organism course."""

    @staticmethod
    def _manifest(state_root: Path) -> Path:
        candidates = sorted(
            path
            for root in state_root.glob("foundation-visual-3022-v1*")
            if root.is_dir()
            for path in root.rglob("manifest.json")
            if path.is_file()
        )
        matches: list[Path] = []
        for path in candidates:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if (
                value.get("schema_version")
                == "ninereeds_foundation_visual_material_v1"
                and value.get("input_manifest_sha256")
                == BOOTSTRAP_MANIFEST_IDENTITY
                and value.get("event_count") == 30_220
                and value.get("session_count") == 31
                and value.get("order_policy") == "declared_only"
                and value.get("shuffle_allowed") is False
            ):
                matches.append(path.resolve())
        if not matches:
            raise SafetyError("Trainbox does not retain the frozen 3,022-word manifest")
        return min(matches, key=lambda path: (len(path.parts), str(path)))

    @staticmethod
    def _organ_donor(context: dict[str, Any]) -> Path:
        roots = [
            Path(context["state_root"]).resolve(),
            *(Path(value).resolve() for value in context["artifact_roots"]),
        ]
        declared = Path(
            "/home/aomukai/.local/share/ninereeds/campaign36b/amorphous-root.pt"
        ).resolve()
        candidates = [declared] if declared.is_file() else []
        for root in roots:
            if not root.is_dir():
                continue
            candidates.extend(
                path.resolve()
                for path in root.rglob("amorphous-root.pt")
                if path.is_file()
            )
        bounded = sorted({path for path in candidates if any(
            path == root or root in path.parents for root in roots
        )})
        if not bounded:
            raise SafetyError(
                "Campaign 36B organ-initialization donor is unavailable in bounded Trainbox roots"
            )
        return min(bounded, key=lambda path: (len(path.parts), str(path)))

    def execute(
        self,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if payload["device_indices"] != [0, 1]:
            raise SafetyError("Campaign 36C bootstrap requires the commissioned two-GPU partition")
        research_fields = (
            "campaign_id", "experiment_id", "max_sessions",
            "max_events_per_session", "controls",
        )
        research_values = [payload.get(name) for name in research_fields]
        research_experiment = any(value is not None for value in research_values)
        if research_experiment and (
            payload["mode"] != "launch"
            or any(value is None for value in research_values)
        ):
            raise SafetyError(
                "isolated research launch requires campaign, experiment, bounds, and controls"
            )
        if research_experiment and payload["max_events_per_session"] % 10:
            raise SafetyError("research event bound must preserve complete ten-image concept blocks")
        state_root = Path(context["state_root"]).resolve()
        release_root = Path(context["release_root"]).resolve()
        executable = Path(context["deployment_environment"]["python_executable"])
        model_paths = {
            item.get("id"): item
            for item in context["deployment_environment"].get(
                "required_model_paths", []
            )
        }
        visual_model = model_paths.get("siglip2-base-patch16-naflex")
        if not visual_model or not visual_model.get("path"):
            raise SafetyError("Campaign 36C visual cortex has no attested receptor snapshot")
        manifest_path = self._manifest(state_root)
        donor_path = self._organ_donor(context)
        run_root = _run_root(context)
        receipt_path = run_root / "campaign36c-bootstrap-receipt.json"
        log_path = run_root / "campaign36c-bootstrap-launch.log.json"
        if payload["mode"] == "smoke":
            output_root = state_root / "campaign36c-bootstrap" / f"smoke-{context['run']['id']}"
        elif research_experiment:
            output_root = (
                state_root / "research-lab" / payload["campaign_id"] / payload["experiment_id"]
            ).resolve()
            research_root = (state_root / "research-lab").resolve()
            if research_root not in output_root.parents:
                raise SafetyError("research experiment output escaped its bounded Trainbox root")
        else:
            output_root = state_root / "campaign36c-bootstrap" / "course-v2"
        latest = output_root / "organism" / "latest.json"
        if payload["resume"] != latest.is_file():
            expected = "resume" if latest.is_file() else "fresh launch"
            raise SafetyError(
                f"bootstrap output state requires {expected}; refusing ambiguous overwrite"
            )

        command = [
            str(executable),
            str(release_root / "meta/scripts/cortex_runtime.py"),
            str(release_root / "meta/scripts/train_campaign36c_bootstrap.py"),
            "--manifest",
            str(manifest_path),
            "--organ-donor",
            str(donor_path),
            "--visual-receptor-snapshot",
            str(visual_model["path"]),
            "--output-dir",
            str(output_root),
            "--core-device",
            f"cuda:{payload['device_indices'][0]}",
            "--tissue-device",
            f"cuda:{payload['device_indices'][1]}",
            "--dtype",
            payload["dtype"],
            "--local-files-only",
        ]
        if payload["resume"]:
            command.append("--resume")
        if payload["mode"] == "smoke":
            command.extend(["--max-sessions", "1", "--max-events-per-session", "10"])
        elif research_experiment:
            controls = payload["controls"]
            command.extend([
                "--max-sessions", str(payload["max_sessions"]),
                "--max-events-per-session", str(payload["max_events_per_session"]),
                "--seed", str(controls["seed"]),
                "--learning-rate", str(controls["learning_rate"]),
                "--cell-learning-rate", str(controls["cell_learning_rate"]),
                "--weight-decay", str(controls["weight_decay"]),
                "--seed-ingress-cells", str(controls["seed_ingress_cells"]),
                "--cell-rotary-pairs", str(controls["cell_rotary_pairs"]),
                "--initial-route-energy", str(controls["initial_route_energy"]),
                "--branch-energy-floor", str(controls["branch_energy_floor"]),
                "--max-waves", str(controls["max_waves"]),
                "--max-total-activations", str(controls["max_total_activations"]),
                "--max-degree", str(controls["max_degree"]),
                "--max-fanout", str(controls["max_fanout"]),
                "--minimum-observations", str(controls["minimum_observations"]),
                "--minimum-independent-lineages", str(controls["minimum_independent_lineages"]),
                "--minimum-source-families", str(controls["minimum_source_families"]),
                "--minimum-residual-coherence", str(controls["minimum_residual_coherence"]),
                "--shadow-training-steps", str(controls["shadow_training_steps"]),
                "--shadow-learning-rate", str(controls["shadow_learning_rate"]),
            ])

        environment = dict(os.environ)
        python_path = [str(release_root)]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment["PYTHONPATH"] = os.pathsep.join(python_path)
        site_paths = context["deployment_environment"].get("python_site_paths", [])
        if site_paths:
            environment["NINEREEDS_TORCH_SITE"] = site_paths[0]

        if payload["mode"] == "smoke":
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                env=environment,
                timeout=context["timeout_seconds"],
                check=False,
            )
            launch_command = command
            unit = None
            active_state = "completed" if completed.returncode == 0 else "failed"
        else:
            unit = (
                f"ninereeds-lab-{context['run']['id']}"
                if research_experiment
                else f"ninereeds-campaign36c-{context['run']['id']}"
            )
            launch_command = [
                "systemd-run",
                "--user",
                f"--unit={unit}",
                "--collect",
                "--property=Restart=no",
                f"--setenv=PYTHONPATH={environment['PYTHONPATH']}",
            ]
            if environment.get("NINEREEDS_TORCH_SITE"):
                launch_command.append(
                    f"--setenv=NINEREEDS_TORCH_SITE={environment['NINEREEDS_TORCH_SITE']}"
                )
            launch_command.extend([
                "--",
                "flock",
                "--exclusive",
                str(state_root / "gpu-resource.lock"),
                *command,
            ])
            completed = subprocess.run(
                launch_command,
                capture_output=True,
                text=True,
                env=environment,
                timeout=60,
                check=False,
            )
            active_state = "unknown"
            if completed.returncode == 0:
                observed = subprocess.run(
                    [
                        "systemctl",
                        "--user",
                        "show",
                        unit,
                        "--property=ActiveState",
                        "--value",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if observed.returncode == 0:
                    active_state = observed.stdout.strip()

        log_path.write_text(
            json.dumps(
                {
                    "command": launch_command,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "active_state": active_state,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if completed.returncode != 0:
            lowered = completed.stderr.lower()
            if "cuda out of memory" in lowered or "torch.outofmemoryerror" in lowered:
                raise RemoteJobError(
                    f"Campaign 36C bootstrap ran out of CUDA memory; evidence: {log_path}",
                    failure_class="operational_transient",
                    code="resource_temporarily_unavailable",
                )
            raise RuntimeError(
                f"Campaign 36C bootstrap {payload['mode']} failed; evidence: {log_path}"
            )
        if payload["mode"] == "smoke":
            progress_path = output_root / "progress.json"
            if not progress_path.is_file() or not latest.is_file():
                raise RuntimeError("Campaign 36C smoke did not produce a durable organism snapshot")
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
            if (
                progress.get("events_consumed") != 11
                or progress.get("visual_events_consumed") != 10
                or progress.get("text_events_consumed") != 1
                or progress.get("organ_preflight", {}).get("status") != "passed"
            ):
                raise RuntimeError("Campaign 36C smoke did not consume exactly one concept block")
        else:
            progress_path = output_root / "progress.json"
            completed_before_observation = False
            if progress_path.is_file():
                observed_progress = json.loads(progress_path.read_text(encoding="utf-8"))
                completed_before_observation = observed_progress.get("status") == "complete"
            if active_state not in {"active", "activating"} and not completed_before_observation:
                raise RuntimeError(
                    f"Campaign 36C service did not enter an active state: {active_state}"
                )
            progress = observed_progress if completed_before_observation else {
                "status": "launched", "events_consumed": 0 if not payload["resume"] else None,
            }
        receipt = {
            "schema_version": ORGANISM_BOOTSTRAP_RECEIPT_SCHEMA,
            "run_id": context["run"]["id"],
            "mode": payload["mode"],
            "resume": payload["resume"],
            "unit": unit,
            "active_state": active_state,
            "release_root": str(release_root),
            "manifest_path": str(manifest_path),
            "manifest_identity": BOOTSTRAP_MANIFEST_IDENTITY,
            "organ_donor_path": str(donor_path),
            "organ_donor_sha256": _sha256(donor_path),
            "output_root": str(output_root),
            "device_indices": payload["device_indices"],
            "dtype": payload["dtype"],
            "campaign_id": payload.get("campaign_id"),
            "experiment_id": payload.get("experiment_id"),
            "max_sessions": payload.get("max_sessions"),
            "max_events_per_session": payload.get("max_events_per_session"),
            "controls": payload.get("controls"),
            "progress": progress,
        }
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        artifact_manifest = {
            "schema_version": ORGANISM_BOOTSTRAP_RECEIPT_SCHEMA,
            "run_id": context["run"]["id"],
            "mode": payload["mode"],
            "manifest_identity": BOOTSTRAP_MANIFEST_IDENTITY,
            "unit": unit,
            "output_root": str(output_root),
            "campaign_id": payload.get("campaign_id"),
            "experiment_id": payload.get("experiment_id"),
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _artifact_output(
                    "organism_bootstrap_receipt",
                    receipt_path,
                    lifecycle="observed",
                    manifest=artifact_manifest,
                ),
                _artifact_output(
                    "log",
                    log_path,
                    lifecycle="observed",
                    manifest={"run_id": context["run"]["id"]},
                ),
            ],
            "metrics": {
                "mode": payload["mode"],
                "active_state": active_state,
                "device_indices": payload["device_indices"],
                "events_consumed": progress.get("events_consumed"),
            },
            "failure": None,
        }


class Campaign36COrganismStatusHandler:
    """Observe the detached Stage-8 service without acquiring its GPU lock."""

    @staticmethod
    def _service_state(unit: str) -> dict[str, Any]:
        command = [
            "systemctl",
            "--user",
            "show",
            unit,
            "--property=ActiveState",
            "--property=SubState",
            "--property=Result",
            "--property=ExecMainStatus",
            "--no-pager",
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return {"query_ok": False, "error": f"{type(exc).__name__}: {exc}"}
        values: dict[str, Any] = {
            "query_ok": completed.returncode == 0,
            "returncode": completed.returncode,
        }
        for line in completed.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator and key in {
                "ActiveState",
                "SubState",
                "Result",
                "ExecMainStatus",
            }:
                values[key] = value
        if completed.returncode != 0:
            values["error"] = completed.stderr.strip()[:512]
        return values

    @staticmethod
    def _gpu_observation() -> list[dict[str, int]] | None:
        command = [
            "nvidia-smi",
            "--query-gpu=index,memory.used,utilization.gpu,temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            result = []
            for line in completed.stdout.splitlines():
                fields = [field.strip() for field in line.split(",")]
                if len(fields) == 4:
                    result.append({
                        "index": int(fields[0]),
                        "memory_used_mib": int(fields[1]),
                        "utilization_percent": int(fields[2]),
                        "temperature_c": int(fields[3]),
                    })
            return result
        except (OSError, subprocess.SubprocessError, ValueError):
            return None

    def execute(
        self,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        launch_run_id = payload["launch_run_id"]
        if payload.get("campaign_id") and payload.get("experiment_id"):
            unit = f"ninereeds-lab-{launch_run_id}"
            output_root = (
                Path(context["state_root"]).resolve()
                / "research-lab" / payload["campaign_id"] / payload["experiment_id"]
            )
        elif payload.get("campaign_id") or payload.get("experiment_id"):
            raise SafetyError("organism status requires both campaign and experiment identity")
        else:
            unit = f"ninereeds-campaign36c-{launch_run_id}"
            output_root = (
                Path(context["state_root"]).resolve()
                / "campaign36c-bootstrap"
                / "course-v2"
            )
        progress_path = output_root / "progress.json"
        latest_path = output_root / "organism" / "latest.json"

        progress = None
        if progress_path.is_file():
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
        latest = None
        if latest_path.is_file():
            latest = json.loads(latest_path.read_text(encoding="utf-8"))
        service = self._service_state(unit)
        active_state = service.get("ActiveState", "unknown")
        training_status = progress.get("status") if progress else "starting"
        if training_status == "complete":
            organism_status = "complete"
        elif active_state in {"active", "activating"}:
            organism_status = "training"
        elif active_state == "failed":
            organism_status = "failed"
        else:
            organism_status = "unknown"

        return {
            "status": "succeeded",
            "artifacts": [],
            "metrics": {
                "organism_status": organism_status,
                "launch_run_id": launch_run_id,
                "campaign_id": payload.get("campaign_id"),
                "experiment_id": payload.get("experiment_id"),
                "unit": unit,
                "service": service,
                "progress": progress,
                "progress_observed_mtime_ns": (
                    progress_path.stat().st_mtime_ns
                    if progress_path.is_file()
                    else None
                ),
                "latest_snapshot": latest,
                "gpu": self._gpu_observation(),
            },
            "failure": None,
        }


class Campaign36COrganismArchiveHandler:
    """Archive one exact completed organism together with its source release."""

    @staticmethod
    def _bounded_files(root: Path, *, prefix: str) -> list[tuple[Path, str]]:
        files: list[tuple[Path, str]] = []
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise SafetyError(f"organism archive refuses symbolic link: {path}")
            if path.is_file():
                files.append((path, f"{prefix}/{path.relative_to(root).as_posix()}"))
        if not files:
            raise SafetyError(f"organism archive source is empty: {root}")
        return files

    def execute(
        self,
        payload: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        state_root = Path(context["state_root"]).resolve()
        course_root = state_root / "campaign36c-bootstrap" / "course-v1"
        progress_path = course_root / "progress.json"
        latest_path = course_root / "organism" / "latest.json"
        if not progress_path.is_file() or not latest_path.is_file():
            raise SafetyError("completed Campaign 36C organism is unavailable")
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        if (
            progress.get("status") != "complete"
            or progress.get("events_consumed") != 30_220
            or progress.get("sessions_completed") != 31
        ):
            raise SafetyError("organism archive requires the completed 30,220-event course")
        if (
            latest.get("snapshot_name") != payload["snapshot_name"]
            or latest.get("shared_sha256") != payload["shared_sha256"]
            or latest.get("progress", {}).get("status") != "complete"
        ):
            raise SafetyError("organism archive snapshot identity does not match the request")
        shared_path = Path(latest["shared_path"]).resolve()
        if (
            not shared_path.is_file()
            or course_root not in shared_path.parents
            or _sha256(shared_path) != payload["shared_sha256"]
        ):
            raise SafetyError("organism archive shared state failed identity validation")

        release_parent = Path(context["release_root"]).resolve().parent
        source_release = (release_parent / payload["source_release_id"]).resolve()
        if (
            source_release.parent != release_parent
            or not source_release.is_dir()
            or not (source_release / "RELEASE-MANIFEST.json").is_file()
        ):
            raise SafetyError("organism archive source release is unavailable")

        archive_roots = [Path(value).resolve() for value in context["artifact_roots"]]
        matches = [root for root in archive_roots if root.name == "ninereeds-archives"]
        if len(matches) != 1:
            raise SafetyError("organism archive root is not uniquely configured")
        archive_root = matches[0]
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_path = archive_root / payload["archive_name"]
        if archive_path.exists():
            raise SafetyError("organism archive destination already exists")

        inputs = [
            *self._bounded_files(course_root, prefix="organism-course"),
            *self._bounded_files(source_release, prefix="source-release"),
        ]
        inventory = [
            {
                "archive_path": member,
                "byte_size": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path, member in inputs
        ]
        input_bytes = sum(item["byte_size"] for item in inventory)
        free_bytes = shutil.disk_usage(archive_root).free
        reserve_bytes = max(1 << 30, input_bytes // 10)
        if free_bytes < input_bytes + reserve_bytes:
            raise SafetyError("insufficient free space for a recoverable organism archive")

        manifest = {
            "schema_version": ORGANISM_ARCHIVE_SCHEMA,
            "campaign_id": context["campaign_id"],
            "launch_run_id": payload["launch_run_id"],
            "archive_run_id": context["run"]["id"],
            "source_release_id": payload["source_release_id"],
            "snapshot_name": payload["snapshot_name"],
            "shared_sha256": payload["shared_sha256"],
            "progress": progress,
            "latest_snapshot": latest,
            "file_count": len(inventory),
            "input_bytes": input_bytes,
            "files": inventory,
        }
        temporary_path = archive_root / f".{payload['archive_name']}.{context['run']['id']}.tmp"
        try:
            with zipfile.ZipFile(
                temporary_path,
                mode="x",
                compression=zipfile.ZIP_STORED,
                allowZip64=True,
                strict_timestamps=False,
            ) as archive:
                archive.writestr(
                    "ARCHIVE-MANIFEST.json",
                    json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                )
                for path, member in inputs:
                    archive.write(path, member)
            os.chmod(temporary_path, 0o440)
            os.replace(temporary_path, archive_path)
        finally:
            temporary_path.unlink(missing_ok=True)

        run_root = _run_root(context)
        manifest_path = run_root / "campaign36c-organism-archive.json"
        manifest_path.write_text(
            json.dumps(
                {
                    **manifest,
                    "archive_path": str(archive_path),
                    "archive_byte_size": archive_path.stat().st_size,
                    "archive_sha256": _sha256(archive_path),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        artifact_manifest = {
            "schema_version": ORGANISM_ARCHIVE_SCHEMA,
            "campaign_id": context["campaign_id"],
            "source_release_id": payload["source_release_id"],
            "snapshot_name": payload["snapshot_name"],
            "shared_sha256": payload["shared_sha256"],
            "file_count": len(inventory),
        }
        return {
            "status": "succeeded",
            "artifacts": [
                _artifact_output(
                    "organism_archive",
                    archive_path,
                    lifecycle="observed",
                    manifest=artifact_manifest,
                ),
                _artifact_output(
                    "organism_archive_manifest",
                    manifest_path,
                    lifecycle="observed",
                    manifest=artifact_manifest,
                ),
            ],
            "metrics": {
                "file_count": len(inventory),
                "input_bytes": input_bytes,
                "archive_bytes": archive_path.stat().st_size,
                "snapshot_name": payload["snapshot_name"],
            },
            "failure": None,
        }
